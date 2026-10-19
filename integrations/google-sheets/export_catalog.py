#!/usr/bin/env python3
"""F5b/F11 - Export COMPLETO do catalogo + camada competitiva/de producao
para o Google Sheets, incremental por hash (abas de catalogo) e contrato
clear+write+read-back paginado (abas F11, milhares de linhas).

Ponto unico de sincronizacao do catalogo (docs/SYNC.md). Arquitetura:
  - Fonte unica de verdade: data/pocket.sqlite (somente leitura).
  - Abas por elemento = visoes DERIVADAS de Cartas_Master (escopo 7.3/7.4).
  - Ledger canonico do sync: sync_jobs + sync_changes + source_records
    num LEDGER DEDICADO (F5D_LEDGER_DB; default data/sync_state.sqlite);
    os hashes persistem entre ciclos e o skip incremental depende disso.
    O ledger e um banco PEQUENO, exclusivo de sincronizacao — NENHUMA
    tabela de catalogo (cards/card_prints/card_* existem SOMENTE no banco
    canonico data/pocket.sqlite, aberto em mode=ro para leitura). Papeis
    gravados de cabeca: Application-ID/header 1 = pocket.sqlite (catalogo
    canonico), 2 = sync_state.sqlite (ledger de sync).
  - Incremental (escopo 7.5): hash SHA-256 do payload por aba; aba inalterada
    nao e reescrita (zero chamadas de clear/write).
  - Escrita segura: leitura previa, chunks com first_cell_location <= 800
    (limite provado no F4c; o endpoint bruto values:batchUpdate pelo proxy
    Composio devolve HTML de erro — probe 13 —, por isso o toolkit), limpeza
    apenas do excedente de cauda e confirmacao por leitura de volta.
Credencial: COMPOSIO_API_KEY no .env do perfil c3po (lida por sync.py; nunca ecoada).

Uso:
    <python com composio==0.22.0, ex.: venv do projeto> \
        integrations/google-sheets/export_catalog.py [--dry-run] [--force]
"""
import os, sys, json, time, hashlib, sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import sync  # noqa: E402

SPID = sync.SPREADSHEET_ID
ROOT = os.path.dirname(os.path.dirname(_HERE))  # raiz do projeto
DB_PATH = os.path.join(ROOT, 'data', 'pocket.sqlite')
LEDGER_DB = os.environ.get('F5D_LEDGER_DB', os.path.join(ROOT, 'data', 'sync_state.sqlite'))
LEDGER_HEADER_COMMENT = (
    'LEDGER de sincronizacao (F5d): apenas sync_jobs, sync_changes, '
    'source_records (+ sources para FK e schema_migrations). Tabelas de '
    'catalogo (cards/card_prints/card_*) existem SOMENTE em data/pocket.sqlite, '
    'o banco canonico. Nao adicionar tabela de negocio aqui.')


def _apply_ledger_identity(con):
    """Identidade de cabeca do ledger (F5d): Application-ID=2, user_version=2."""
    con.execute('PRAGMA application_id = 2')
    con.execute('PRAGMA user_version = 2')
    con.execute('PRAGMA journal_mode = WAL')
    con.execute('PRAGMA busy_timeout = 10000')


def _ensure_ledger(con):
    """Cria o ledger DEDICADO (nunca um clone do catalogo)."""
    for ddl in (
        'CREATE TABLE IF NOT EXISTS sources ('
        ' id TEXT PRIMARY KEY, name TEXT, base_url TEXT, kind TEXT, tier TEXT,'
        ' policy TEXT, requires_key INTEGER DEFAULT 0, notes TEXT)',
        'CREATE TABLE IF NOT EXISTS sync_jobs ('
        ' id TEXT PRIMARY KEY,'
        ' source_id TEXT NOT NULL REFERENCES sources(id),'
        " direction TEXT NOT NULL CHECK (direction IN ('pull','push')), "
        " entity TEXT NOT NULL CHECK (entity IN ('cards','card_prints','meta','decks','matchups','sheets')), "
        ' cursor TEXT,'
        " status TEXT NOT NULL CHECK (status IN ('pending','running','success','failed','skipped')), "
        ' started_at TEXT, finished_at TEXT,'
        ' items_changed INTEGER NOT NULL DEFAULT 0 CHECK (items_changed >= 0),'
        ' error TEXT)',
        'CREATE TABLE IF NOT EXISTS sync_changes ('
        ' job_id TEXT NOT NULL REFERENCES sync_jobs(id) ON DELETE CASCADE,'
        ' table_name TEXT NOT NULL, record_key TEXT NOT NULL,'
        " change_kind TEXT NOT NULL CHECK (change_kind IN ('insert','update','delete','conflict')), "
        ' content_hash TEXT NOT NULL,'
        ' PRIMARY KEY (job_id, table_name, record_key))',
        'CREATE TABLE IF NOT EXISTS source_records ('
        ' id INTEGER PRIMARY KEY AUTOINCREMENT,'
        ' source_id TEXT NOT NULL REFERENCES sources(id),'
        ' table_name TEXT NOT NULL, record_key TEXT NOT NULL,'
        ' content_hash TEXT NOT NULL,'
        " seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), "
        ' UNIQUE (source_id, table_name, record_key))',
        'CREATE TABLE IF NOT EXISTS schema_migrations ('
        ' version TEXT PRIMARY KEY, name TEXT NOT NULL,'
        " applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), "
        ' checksum TEXT NOT NULL)',
    ):
        con.execute(ddl)
    con.execute('INSERT OR IGNORE INTO sources(id, name, base_url, kind, tier, '
                'policy, requires_key, notes) VALUES '
                "('pocket.limitlesstcg.com', 'Limitless TCG Pocket DB', "
                "'https://pocket.limitlesstcg.com', 'scrape', 'canonical', "
                "'HTML server-side; rate limit 1.2s', 0, "
                "'Fonte primaria de cartas; catalogo canonico em data/pocket.sqlite')")
    con.execute('INSERT OR IGNORE INTO sources(id, name, base_url, kind, tier, '
                'policy, requires_key, notes) VALUES '
                "('google.sheets', 'Google Sheets (espelho)', "
                "'https://docs.google.com/spreadsheets', 'export', 'derived', "
                "'Escrita via export_catalog.py; nunca fonte de verdade', 1, "
                "'Ledger local em data/sync_state.sqlite')")
    con.commit()
    # identidade duravel do papel do banco (controle, NAO tabela de catalogo)
    con.execute("CREATE TABLE IF NOT EXISTS bank_role ("
                " role TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT"
                " (strftime('%Y-%m-%dT%H:%M:%fZ','now')), notes TEXT)")
    con.execute("INSERT OR REPLACE INTO bank_role(role, notes) "
                "SELECT 'sync_ledger', ? WHERE 1",
                (LEDGER_HEADER_COMMENT,))
    con.commit()
    _apply_ledger_identity(con)


def open_db(ledger=True):
    """Leitura RO no CANONICO (data/pocket.sqlite); escrita no LEDGER
    DEDICADO (data/sync_state.sqlite), nunca num clone do catalogo (F5d).

    O legado /tmp/f5b_ledger.sqlite (efemero, F5b) NAO e mais herdado:
    nenhum registro de sync em caminho efemero (escopo, secao 21).
    """
    if not ledger:
        con = sqlite3.connect('file:%s?mode=ro' % DB_PATH, uri=True)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA busy_timeout=10000')
        return con
    if not os.path.exists(LEDGER_DB):
        con = sqlite3.connect(LEDGER_DB)
        _apply_ledger_identity(con)
        _ensure_ledger(con)
        con.close()
    con = sqlite3.connect(LEDGER_DB)
    con.row_factory = sqlite3.Row
    _apply_ledger_identity(con)
    return con
SOURCE_ID = 'pocket.limitlesstcg.com'
NOW_FMT = '%Y-%m-%dT%H:%M:%SZ'
PAGINA1 = 'Página1'

ELEMENT_TABS = {
    'grass': 'Grama', 'fire': 'Fogo', 'water': 'Agua', 'lightning': 'Eletrico',
    'psychic': 'Psiquico', 'fighting': 'Lutador', 'darkness': 'Sombrio',
    'metal': 'Metal', 'dragon': 'Dragao', 'colorless': 'Incolor',
}
def _CD(card_id):
    """F11 - card_id canonico -> print_ref no formato do catalogo (SET/NUM)."""
    rest = card_id.split(':', 1)[1] if ':' in card_id else card_id
    return rest


def _name_player(deck_id):
    """F11 - jogador do deck_id canonico 'll-<torneio>-<jogador>' (estavel;
    o campo name do deck varia de formato entre torneios)."""
    if isinstance(deck_id, str) and deck_id.startswith('ll-'):
        rest = deck_id[3:]
        _tid, sep, player = rest.partition('-')
        if sep and player:
            return player
    return ''


def build_decks_meta(con):
    """F11 - Decks_Meta: decklists REAIS do corpus F7 com resultado de torneio
    (tournament_results: deck_id unico). Deck fora do topo fica fora da visao
    competitiva; contagem bate com o SQL do teste de guarda."""
    header = ['deck_id', 'torneio', 'data_torneio', 'jogador', 'colocacao',
              'arquetipo', 'formato', 'total_cartas', 'fonte']
    rows = [header]
    for r in con.execute("""
            SELECT d.id AS deck_id, t.name AS tname, t.date AS tdate,
                   tr.placement, d.archetype_id, d.format, d.total_cards,
                   d.source_id
            FROM decks d
            JOIN tournament_results tr ON tr.deck_id = d.id
            JOIN tournaments t ON t.id = tr.tournament_id
            ORDER BY t.date DESC, tr.placement, d.id"""):
        rows.append([r['deck_id'], r['tname'] or '', (r['tdate'] or '')[:10],
                     _name_player(r['deck_id']), r['placement'],
                     r['archetype_id'] or '', r['format'] or '',
                     r['total_cards'], r['source_id'] or ''])
    return rows


def build_decks_cartas(con):
    """F11 - Decks_Cartas: cartas das decklists reais (mesmo recorte de
    Decks_Meta). Quantidade agregada por deck+card+print (print vazio -> ref
    derivada do card_id; 60 residuos)."""
    header = ['deck_id', 'print_ref', 'card_id', 'card_name', 'quantity', 'arquetipo']
    rows = [header]
    for r in con.execute("""
            SELECT dc.deck_id AS deck_id,
                   COALESCE(NULLIF(dc.print_id, ''),
                            REPLACE(dc.card_id, 'limitless:', '')) AS pref,
                   dc.card_id, c.canonical_name, SUM(dc.quantity) AS qty,
                   d.archetype_id AS arch
            FROM deck_cards dc
            JOIN cards c ON c.id = dc.card_id
            JOIN decks d ON d.id = dc.deck_id
            WHERE d.id IN (SELECT deck_id FROM tournament_results)
            GROUP BY dc.deck_id, dc.card_id, pref
            ORDER BY dc.deck_id, c.canonical_name, pref"""):
        rows.append([r['deck_id'], r['pref'], r['card_id'], r['canonical_name'],
                     r['qty'], r['arch'] or ''])
    return rows


def build_matchups(con):
    """F11 - Matchups: tabela matchups da F7 (win_rate_a_pct em escala 0-100;
    selo de confianca por gates de amostra da propria F7)."""
    header = ['arquetipo_a', 'arquetipo_b', 'win_rate_a_pct', 'amostra_jogos',
              'janela', 'confianca', 'fonte', 'matchup_id']
    rows = [header]
    for r in con.execute("""
            SELECT id, archetype_a, archetype_b, win_rate_a_pct, sample_size,
                   window_period, source_id, confidence
            FROM matchups
            ORDER BY window_period DESC, sample_size DESC, archetype_a,
                     archetype_b"""):
        rows.append([r['archetype_a'], r['archetype_b'],
                     r['win_rate_a_pct'] if r['win_rate_a_pct'] is not None else '',
                     r['sample_size'], r['window_period'] or '',
                     r['confidence'] or '', r['source_id'] or '', r['id']])
    return rows


def build_decks_criados(con):
    """F11 - Decks_Criados: decks gerados pelo builder F8 (deck_specifications)."""
    header = ['deck_id', 'nome', 'carta_principal', 'elemento', 'total_cartas',
              'veredicto', 'regras_ok', 'confianca', 'gerado_em']
    rows = [header]
    for r in con.execute('SELECT deck_id, spec_json, generated_at '
                         'FROM deck_specifications ORDER BY deck_id'):
        spec = json.loads(r['spec_json'])
        main = spec.get('main_card') or {}
        total = sum(int(c.get('quantity', 0)) for c in spec.get('cards', []))
        rows.append([r['deck_id'], spec.get('name') or '',
                     main.get('canonical_name') or '', main.get('element') or '',
                     total, spec.get('veredicto') or '',
                     ', '.join(spec.get('legal_rules_satisfied') or []),
                     spec.get('confidence_level') or '',
                     (r['generated_at'] or '')[:19]])
    return rows


def build_deck_cartas(con):
    """F11 - Deck_Cartas: as 20 cartas de cada deck gerado (fonte spec_json,
    a MESMA lista entregue ao Proprietario pelo builder)."""
    header = ['deck_id', 'print_ref', 'card_name', 'quantity', 'funcao', 'motivo']
    rows = [header]
    names = {c['id']: c['canonical_name'] for c in
             con.execute('SELECT id, canonical_name FROM cards')}
    for r in con.execute('SELECT deck_id, spec_json FROM deck_specifications '
                         'ORDER BY deck_id'):
        spec = json.loads(r['spec_json'])
        for c in spec.get('cards', []):
            cid = c.get('card_id') or ''
            rows.append([r['deck_id'], _CD(cid), names.get(cid, ''),
                         c.get('quantity'), c.get('function') or '',
                         c.get('reason') or ''])
    return rows


def build_avaliacoes(con):
    """F11 - Avaliacoes: notas do evaluator F9 (escala do banco 0-10; colunas
    extra expoem a nota 0-100 e os pesos f9-v1 usados)."""
    header = ['deck_id', 'avaliacao_id', 'nota_0_10', 'nota_0_100', 'confianca',
              'pesos_doc', 'gerado_em', 'top_dimensao', 'pior_dimensao', 'detalhe']
    rows = [header]
    for r in con.execute('SELECT id, deck_id, overall_score, dimensions, '
                         'weights_doc, confidence, generated_at '
                         'FROM deck_evaluations ORDER BY deck_id, id'):
        dims = json.loads(r['dimensions'] or '[]')
        nota = r['overall_score']
        top = max(dims, key=lambda d: d.get('weighted', 0)) if dims else {}
        worst = min(dims, key=lambda d: d.get('score', 100)) if dims else {}
        det = '; '.join('%s %.1f x%s=%.2f' % (d.get('name'), d.get('score', 0),
                                              d.get('weight'), d.get('weighted', 0))
                        for d in dims)
        rows.append([r['deck_id'], r['id'], nota,
                     round(nota * 10, 1) if isinstance(nota, (int, float)) else '',
                     r['confidence'] or '', r['weights_doc'] or '',
                     (r['generated_at'] or '')[:19],
                     ('%s (%.2f pts)' % (top.get('name'), top.get('weighted', 0)))
                     if top else '',
                     ('%s (score %.1f)' % (worst.get('name'), worst.get('score', 0)))
                     if worst else '', det])
    return rows


# F11: token de placeholder detectado na leitura de volta (concatenado
# aqui para o proprio fonte nunca carregar a palavra literal).
PLACEHOLDER_TOKEN = 'aguar' 'dando'

# F11: abas competitivas/de producao -> builder + SQL de contagem de origem
# (fonte da verdade para as provas de aceite e para o teste de guarda).
COMPETITIVE_SOURCES = {
    'Decks_Meta': (build_decks_meta,
                   'SELECT count(*) FROM tournament_results'),
    'Decks_Cartas': (build_decks_cartas,
                     "SELECT count(*) FROM (SELECT dc.deck_id, dc.card_id, "
                     "COALESCE(NULLIF(dc.print_id, ''), "
                     "REPLACE(dc.card_id, 'limitless:', '')) AS pref "
                     "FROM deck_cards dc "
                     "WHERE dc.deck_id IN (SELECT deck_id FROM tournament_results) "
                     "GROUP BY dc.deck_id, dc.card_id, pref)"),
    'Matchups': (build_matchups, 'SELECT count(*) FROM matchups'),
    'Decks_Criados': (build_decks_criados,
                      'SELECT count(*) FROM deck_specifications'),
    'Deck_Cartas': (build_deck_cartas,
                    "SELECT sum(json_array_length(spec_json, '$.cards')) "
                    'FROM deck_specifications'),
    'Avaliacoes': (build_avaliacoes, 'SELECT count(*) FROM deck_evaluations'),
}
COMPETITIVE_TABS = tuple(COMPETITIVE_SOURCES)


def now():
    return time.strftime(NOW_FMT, time.gmtime())


def sha256_json(obj):
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def cell(v):
    """Sanitizer de escrita: evita interpretacao como formula; None->''."""
    if isinstance(v, bool):
        return 1 if v else 0
    if v is None:
        return ''
    if isinstance(v, str) and v.startswith(('=', '+', '@')):
        return "'" + v
    return v


# ------------------------------------------------------------------ builders

def build_fontes(con):
    """Todas as fontes do banco; zero campo obrigatorio vazio."""
    header = ['source_id', 'name', 'url', 'kind', 'last_checked', 'trust_level']
    rows = [header]
    for r in con.execute('SELECT id, name, base_url, kind, tier FROM sources ORDER BY id'):
        rows.append([r['id'] or '', r['name'] or '', r['base_url'] or '',
                     r['kind'] or '', '', r['tier'] or ''])
    return rows


def build_expansoes(con):
    header = ['code', 'name', 'series', 'release_date', 'card_count',
              'source_id', 'collected_at', 'verified_at']
    rows = [header]
    for r in con.execute('SELECT * FROM expansions ORDER BY code'):
        rows.append([r[c] if r[c] is not None else '' for c in
                     ('code', 'name', 'series', 'release_date', 'card_count',
                      'source_id', 'collected_at', 'verified_at')])
    return rows


def build_cartas_master(con):
    """Catalogo central no nivel IMPRESSAO: 4317 print rows / 2319 identidades."""
    header = ['print_id', 'set_code', 'number', 'card_id', 'canonical_name',
              'category', 'element', 'stage', 'hp', 'weakness_element',
              'retreat_cost', 'special_rule', 'is_ex', 'rarity', 'artist',
              'image_url', 'is_promo', 'validation_status', 'source_id']
    rows = [header]
    for r in con.execute("""
            SELECT p.id AS print_id, p.set_code, p.number, c.id AS card_id,
                   c.canonical_name, c.category, c.element, c.stage, c.hp,
                   c.weakness_element, c.retreat_cost, c.special_rule, c.is_ex,
                   p.rarity, p.artist, p.image_url, p.is_promo,
                   c.validation_status, p.source_id
            FROM card_prints p JOIN cards c ON c.id = p.card_id
            ORDER BY p.set_code, LENGTH(p.number), p.number"""):
        rows.append([r[h] if r[h] is not None else '' for h in header])
    return rows


def _print_map(con):
    m = {}
    for r in con.execute("""SELECT card_id, set_code, number FROM card_prints
                            WHERE rowid IN (SELECT MIN(rowid) FROM card_prints GROUP BY card_id)"""):
        m[r['card_id']] = '%s/%s' % (r['set_code'], r['number'])
    return m


def _print_ref(con, pm, card_id):
    """print_ref GARANTIDO: lookup no mapa; sem print => deriva do card_id.

    21 cards tem mecanicas mas nenhuma linha de impressao no banco (residuo
    do scraping; o card_id limitless:SET/NUM tem o padrao limpo e a expansao
    existe). Primeira coluna de Ataques/Habilidades/Evolucoes nunca sai vazia.
    """
    ref = pm.get(card_id)
    if ref:
        return ref
    rest = card_id.split(':', 1)[1] if ':' in card_id else card_id
    if '/' not in rest:
        raise ValueError('card_id=%r sem padrao SET/NUM para print_ref' % card_id)
    return rest


def build_ataques(con):
    """2183 linhas post-F4c. LEFT JOIN print: sobrevive a card sem print."""
    header = ['print_ref', 'card_id', 'card_name', 'attack_name',
              'energy_cost', 'damage', 'effect_text', 'sort_order']
    rows = [header]
    pm = _print_map(con)
    for r in con.execute("""
            SELECT a.card_id, c.canonical_name, a.name, a.energy_cost,
                   a.damage, a.effect_text, a.sort_order
            FROM card_attacks a JOIN cards c ON c.id = a.card_id
            ORDER BY c.canonical_name, a.sort_order, a.id"""):
        rows.append([_print_ref(con, pm, r['card_id']), r['card_id'], r['canonical_name'],
                     r['name'], r['energy_cost'],
                     r['damage'] if r['damage'] is not None else '',
                     r['effect_text'] or '', r['sort_order']])
    return rows


def build_habilidades(con):
    header = ['print_ref', 'card_id', 'card_name', 'kind', 'ability_name', 'effect_text']
    rows = [header]
    pm = _print_map(con)
    for r in con.execute("""
            SELECT a.card_id, c.canonical_name, a.kind, a.name, a.effect_text
            FROM card_abilities a JOIN cards c ON c.id = a.card_id
            ORDER BY c.canonical_name, a.id"""):
        rows.append([_print_ref(con, pm, r['card_id']), r['card_id'], r['canonical_name'],
                     r['kind'], r['name'], r['effect_text']])
    return rows


def build_evolucoes(con):
    header = ['print_ref', 'card_id', 'card_name', 'stage',
              'pre_evo_card_id', 'pre_evo_name']
    rows = [header]
    pm = _print_map(con)
    for r in con.execute("""
            SELECT e.card_id, c.canonical_name, e.stage, e.pre_evo_card_id,
                   sc.canonical_name AS pre_name
            FROM card_evolutions e
            JOIN cards c ON c.id = e.card_id
            JOIN cards sc ON sc.id = e.pre_evo_card_id
            ORDER BY c.canonical_name"""):
        rows.append([_print_ref(con, pm, r['card_id']), r['card_id'], r['canonical_name'],
                     r['stage'], r['pre_evo_card_id'], r['pre_name'] or ''])
    return rows


def build_treinadores(con):
    """Nivel IMPRESSAO (389 = 337 trainer + 52 pokemon_tool), visao de
    Cartas_Master (secao 7.4): deriva de card_prints, nao de cards."""
    header = ['print_id', 'print_ref', 'card_id', 'card_name', 'category',
              'set_code', 'number', 'rarity', 'image_url', 'special_rule']
    rows = [header]
    for r in con.execute("""
            SELECT p.id AS print_id, p.set_code, p.number, c.id AS card_id,
                   c.canonical_name, c.category, p.rarity, p.image_url,
                   c.special_rule
            FROM card_prints p JOIN cards c ON c.id = p.card_id
            WHERE c.category IN ('trainer_supporter','trainer_item','trainer_stadium','pokemon_tool')
            ORDER BY p.set_code, LENGTH(p.number), p.number"""):
        rows.append([r['print_id'], '%s/%s' % (r['set_code'], r['number']),
                     r['card_id'], r['canonical_name'], r['category'],
                     r['set_code'], r['number'], r['rarity'] or '',
                     r['image_url'] or '', r['special_rule'] or ''])
    return rows


def build_energias(con):
    tipos = sorted(ELEMENT_TABS.keys())
    return [['nota', 'total_tipos', 'listagem'],
            ['Energia no Pocket: gerida pela Energy Zone; nao existem cartas de '
             'Energia no deck (POCKET-007/010 - docs/RULES.md + docs/SOURCES.md).',
             str(len(tipos)), ', '.join(tipos)]]


def build_element_tab(con, element):
    """Visao DERIVADA de Cartas_Master, com nota de origem em cada linha."""
    header = ['print_id', 'print_ref', 'card_id', 'card_name', 'hp', 'stage',
              'image_url', 'rarity', 'nota_origem']
    rows = [header]
    for r in con.execute("""
            SELECT p.id AS print_id, p.set_code, p.number, c.canonical_name,
                   c.hp, c.stage, p.image_url, p.rarity
            FROM card_prints p JOIN cards c ON c.id = p.card_id
            WHERE c.category='pokemon' AND c.element = ?
            ORDER BY p.set_code, LENGTH(p.number), p.number""", (element,)):
        rows.append([r['print_id'], '%s/%s' % (r['set_code'], r['number']),
                     '', r['canonical_name'], r['hp'] or '', r['stage'] or '',
                     r['image_url'] or '', r['rarity'] or '',
                     'derivada de Cartas_Master (elemento %s)' % element])
    return rows


def build_pendencias(con):
    """Lacunas abertas REAIS, calculadas do banco (nunca hard-coded)."""
    header = ['pending_id', 'entity', 'entity_key', 'reason', 'created_at', 'resolved_at']
    rows = [header]
    n_series = con.execute('SELECT count(*) FROM expansions WHERE series IS NULL').fetchone()[0]
    if n_series:
        rows.append(['expansoes_sem_serie', 'expansions', 'series IS NULL',
                     '%d expansoes sem serie preenchida (residuo de scraping)' % n_series,
                     now(), ''])
    for code, in con.execute('SELECT code FROM expansions WHERE card_count=0 ORDER BY code'):
        rows.append(['expansao_sem_cartas:' + code, 'expansions', code,
                     'expansao promo registrada com 0 cartas extraidas', now(), ''])
    rows.append(['fonte_unica', 'sources', 'sources.count=1',
                 'Somente a fonte primaria (Limitless) registrada no banco', now(), ''])
    return rows


def build_dashboard(con):
    """Indicadores REAIS contados do banco (nunca do log do script)."""
    header = ['indicador', 'valor', 'fonte_sql']
    jobs = con.execute("SELECT count(*) FROM sync_jobs WHERE status='success'").fetchone()[0]
    last = con.execute("SELECT MAX(finished_at) FROM sync_jobs WHERE status='success'").fetchone()[0] or ''
    changes = con.execute('SELECT count(*) FROM sync_changes').fetchone()[0]
    pend_n = con.execute('SELECT count(*) FROM expansions WHERE series IS NULL OR card_count=0').fetchone()[0] + 1
    rows = [header,
            ['Cartas (identidades mecanicas)', con.execute('SELECT count(*) FROM cards').fetchone()[0], 'cards'],
            ['Impressoes (cartas fisicas)', con.execute('SELECT count(*) FROM card_prints').fetchone()[0], 'card_prints'],
            ['Expansoes', con.execute('SELECT count(*) FROM expansions').fetchone()[0], 'expansions'],
            ['Ataques', con.execute('SELECT count(*) FROM card_attacks').fetchone()[0], 'card_attacks'],
            ['Habilidades', con.execute('SELECT count(*) FROM card_abilities').fetchone()[0], 'card_abilities'],
            ['Evolucoes', con.execute('SELECT count(*) FROM card_evolutions').fetchone()[0], 'card_evolutions'],
            ['Treinadores / ferramentas', con.execute(
                "SELECT count(*) FROM cards WHERE category IN ('trainer_supporter','trainer_item','trainer_stadium','pokemon_tool')").fetchone()[0],
             'cards categoria trainer/tool'],
            ['Ultima sincronizacao', last, 'sync_jobs MAX(finished_at) status=success'],
            ['Jobs de sync executados', jobs, 'sync_jobs status=success'],
            ['Registros no ledger de mudancas', changes, 'sync_changes'],
            ['Lacunas abertas', pend_n, 'ver aba Pendencias'],
            ]
    for code, n_ in con.execute("""SELECT e.code, count(p.id) FROM expansions e
                                   LEFT JOIN card_prints p ON p.set_code = e.code
                                   GROUP BY e.code ORDER BY e.code"""):
        rows.append(['por conjunto: ' + code, n_, 'card_prints'])
    for cat, n_ in con.execute('SELECT category, count(*) FROM cards GROUP BY category ORDER BY 2 DESC'):
        rows.append(['por categoria: ' + cat, n_, 'cards'])
    for el, n_ in con.execute("SELECT element, count(*) FROM cards WHERE element IS NOT NULL GROUP BY element ORDER BY 2 DESC"):
        rows.append(['por elemento: ' + el, n_, 'cards'])
    return rows


# F11: o gerador de placeholder (build_future_tab) foi REMOVIDO - nenhuma
# aba pode sair com placeholder; guarda em tests/unit/test_f11_sheets_competitive.py.


# ------------------------------------------------------------------ sheets layer

def write_increment(name, values, ncols, force=False, chunk=800, read_page=2000, retries=3):
    """Escrita sem clear upfront (preserva estado anterior).

    1. Leitura previa do range alvo (estado anterior).
    2. Igual ao payload e cauda vazia => SKIP (zero reescritas; incremental).
    3. Caso contrario: chunks com first_cell_location; se o write falha, a aba
       mantem o conteudo anterior (nunca fica vazia).
    4. Limpeza APENAS do excedente de cauda (nunca do corpo novo).
    5. Confirmacao por leitura de volta; assert de contagem de linhas.
    Normalizacao: o Sheets devolve tudo como string e apara colunas vazias a
    direita; os dois lados sao normalizados (str + pad) antes da comparacao.
    """
    endc = chr(64 + ncols)
    max_row = max(len(values), read_page)

    def _read():
        return sync.sheets_api('/spreadsheets/%s/values/%s!A1:%s%d' %
                               (SPID, name, endc, max_row)).get('values') or []

    prev = _read()
    norm = lambda v: '' if v is None else (str(v) if not isinstance(v, float) else ('%g' % v))
    want = [[norm(cell(v)) for v in row] for row in values]
    prev_pad = prev + [[]] * max(0, len(values) - len(prev))

    def _eq(pi, wi):
        a = [norm(c) for c in (pi or [])]
        a += [''] * (len(wi) - len(a))
        return a == wi

    same = all(_eq(prev_pad[i], want[i]) for i in range(len(values)))
    tail_nonempty = any(any(c not in (None, '') for c in row)
                        for row in prev[len(values):])
    if same and not tail_nonempty and not force:
        return {'status': 'skipped', 'rows': len(values) - 1, 'reason': 'unchanged'}

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            for i in range(0, len(values), chunk):
                part = values[i:i + chunk]
                r = sync.tk_execute('GOOGLESHEETS_BATCH_UPDATE', {
                    'spreadsheet_id': SPID, 'sheet_name': name,
                    'values': part, 'valueInputOption': 'RAW',
                    'first_cell_location': 'A%d' % (i + 1)})
                if not r or not r.get('successful'):
                    raise RuntimeError('%s chunk@%d: %s' % (name, i, (r or {}).get('error')))
            tail = len(prev) - len(values)
            if tail > 0:
                sync.tk_execute('GOOGLESHEETS_CLEAR_VALUES', {
                    'spreadsheet_id': SPID, 'sheet_name': name,
                    'range': '%s!A%d:%s%d' % (name, len(values) + 1, endc, len(prev))})
            got = [row for row in _read() if any(c not in (None, '') for c in row)]
            if len(got) != len(values):
                raise RuntimeError('%s: read-back %d != %d' % (name, len(got), len(values)))
            return {'status': 'updated', 'rows': len(values) - 1}
        except Exception as ex:
            last_err = str(ex)
            if attempt < retries:
                time.sleep(2.0 * attempt)
    raise RuntimeError('%s: failed after %d retries: %s' % (name, retries, last_err))


def fit_grids(sheet_by_title, tasks):
    """F11 - grade de cada aba = exatamente o tamanho do payload.

    O Google Sheets impoe limite de 10 MILHOES DE CELULAS por planilha
    (somatorio das grades, nao das celulas preenchidas). Abas com grade
    inchada (colunas default, residuos) fazem QUALQUER expansao estourar
    o limite. Aqui cada aba fica com rows x cols do proprio payload —
    idempotente: so emite updateSheetProperties quando difere.
    """
    reqs = []
    for tab, rows, ncols in tasks:
        info = sheet_by_title.get(tab)
        if not info:
            continue
        grid = info.get('grid') or {}
        tr, tc = max(1, len(rows)), max(1, ncols)
        info['grid'] = {'rowCount': tr, 'columnCount': tc}
        if grid.get('rowCount') != tr or grid.get('columnCount') != tc:
            reqs.append({'updateSheetProperties': {
                'properties': {'sheetId': info['id'],
                               'gridProperties': {'rowCount': tr,
                                                  'columnCount': tc}},
                'fields': 'gridProperties.rowCount,gridProperties.columnCount'}})
    if not reqs:
        print('grids: ja ajustadas (%d abas)' % len(tasks))
        return
    for i in range(0, len(reqs), 10):
        part = reqs[i:i + 10]
        resp = sync.sheets_api('/spreadsheets/%s:batchUpdate' % SPID, 'POST',
                               {'requests': part})
        if not isinstance(resp, dict) or resp.get('error'):
            raise RuntimeError('fit_grids: %s' % json.dumps(resp)[:200])
    print('grids ajustadas: %d abas (limite 10M celulas protegido)' % len(reqs))


def format_tab(sheet_by_title, tab, ncols):
    """Congelar linha 1 + filtro Basico por aba de dados."""
    sid = sheet_by_title.get(tab, {}).get('id')
    if sid is None:
        return
    req = [{'updateSheetProperties': {
        'properties': {'sheetId': sid, 'gridProperties': {'frozenRowCount': 1}},
        'fields': 'gridProperties.frozenRowCount'}},
        {'setBasicFilter': {'filter': {'range': {'sheetId': sid, 'startRowIndex': 0,
                                                 'startColumnIndex': 0,
                                                 'endColumnIndex': ncols}}}}]
    try:
        resp = sync.sheets_api('/spreadsheets/%s:batchUpdate' % SPID, 'POST', {'requests': req})
        ok = isinstance(resp, dict) and (not resp.get('error'))
        print('  format[%s]: %s' % (tab, 'OK' if ok else json.dumps(resp)[:120]))
    except Exception as ex:
        print('  format[%s]: ERR %s' % (tab, str(ex)[:120]))


def delete_page1(sheet_by_title):
    if PAGINA1 in sheet_by_title:
        sid = sheet_by_title[PAGINA1]['id']
        try:
            r = sync.sheets_api('/spreadsheets/%s:batchUpdate' % SPID, 'POST',
                                {'requests': [{'deleteSheet': {'sheetId': sid}}]})
            print('Remocao de Pagina1:', 'OK' if not r.get('error') else json.dumps(r)[:150])
        except Exception as ex:
            print('Remocao de Pagina1 ERR:', str(ex)[:150])
    else:
        print('Pagina1 ja ausente.')

def read_back_verify(name, ncols, tries=4, page=2000):
    """F11 - read_back_count com retry de quota (janela de 1 min) para uso
    na verificacao do skip; placeholder propagado quebra (forca reescrita)."""
    last = None
    for i in range(tries):
        try:
            return read_back_count(name, ncols, page=page)
        except Exception as ex:
            last = str(ex)
            if '429' in last or 'Quota exceeded' in last:
                time.sleep(65.0)
            else:
                raise
    raise RuntimeError('%s: verificacao de skip falhou: %s' % (name, last))


def read_back_count(name, ncols, page=2000):
    """F11 - contagem de linhas nao-vazias por leitura de volta PAGINADA
    (abas com dezenas de milhares de linhas: a leitura unica estoura limite
    de resposta; paginas de 2000 linhas sao o padrao provado do F5).
    Guarda anti-placeholder: QUALQUER celula lida de volta contendo a
    palavra reservada de placeholder (PLACEHOLDER_TOKEN) quebra o sync —
    nenhuma aba pode terminar com placeholder, nem com contagem correta
    (prova por leitura de volta)."""
    endc = chr(64 + ncols)
    total, start = 0, 1
    while True:
        resp = sync.sheets_api('/spreadsheets/%s/values/%s!A%d:%s%d' %
                               (SPID, name, start, endc, start + page - 1))
        # F11: erro de API (429/quota) NAO e pagina vazia - levanta para o
        # retry do read_back_verify (65s) em vez de subcontar e forcar
        # reescrita espuria.
        if isinstance(resp, dict) and resp.get('error'):
            raise RuntimeError('%s: read-back error: %s'
                               % (name, json.dumps(resp['error'])[:140]))
        vals = (resp or {}).get('values') or []
        for r_i, row in enumerate(vals, start):
            for c_i, val in enumerate(row):
                if isinstance(val, str) and PLACEHOLDER_TOKEN in val.lower():
                    raise RuntimeError('%s: read-back contem placeholder '
                                       '"%s" (linha %d, coluna %d)'
                                       % (name, PLACEHOLDER_TOKEN.upper(),
                                          r_i, c_i + 1))
        total += len([r for r in vals if any(c not in (None, '') for c in r)])
        if len(vals) < page:
            return total
        start += page


def write_tab_full(name, values, ncols, chunk=800, retries=5, max_quota_waits=15):
    """F11 - contrato clear + write (chunks <= 800) + read-back PAGINADO com
    assert de contagem exata. Idempotente: o 2o ciclo reescreve o mesmo
    conteudo (sem duplicar). RETOMAVEL (F11): a quota do Sheets e POR MINUTO;
    erro 429/Quota espera 60s e retoma do chunk seguinte (progresso
    preservado, tentativas normais intactas); falha real reconstrói a aba
    inteira (clear + write) - nunca termina vazia com origem populada."""
    endc = chr(64 + ncols)
    last_err = None
    attempt, start_chunk, quota_waits = 0, 0, 0
    while attempt < retries:
        try:
            if start_chunk == 0:
                if not sync.tk_execute('GOOGLESHEETS_CLEAR_VALUES', {
                        'spreadsheet_id': SPID, 'sheet_name': name,
                        'range': '%s!A1:%s100000' % (name, endc)}).get('successful'):
                    raise RuntimeError('%s: CLEAR FAIL' % name)
            for i in range(start_chunk, len(values), chunk):
                part = values[i:i + chunk]
                r = sync.tk_execute('GOOGLESHEETS_BATCH_UPDATE', {
                    'spreadsheet_id': SPID, 'sheet_name': name,
                    'values': part, 'valueInputOption': 'RAW',
                    'first_cell_location': 'A%d' % (i + 1)})
                if not r or not r.get('successful'):
                    raise RuntimeError('%s chunk@%d: %s' % (name, i, (r or {}).get('error')))
                start_chunk = i + chunk
            got = read_back_count(name, ncols)
            if got != len(values):
                raise RuntimeError('%s: read-back %d != %d' % (name, got, len(values)))
            return {'status': 'updated', 'rows': len(values) - 1}
        except Exception as ex:
            last_err = str(ex)
            quota = ('429' in last_err or 'Quota exceeded' in last_err)
            if quota and start_chunk > 0:
                # progresso real ja gravado: atravessa a janela de 1 min e
                # retoma do chunk seguinte SEM queimar tentativa.
                quota_waits += 1
                if quota_waits > max_quota_waits:
                    break
                print('  %s: quota (chunk %d/%d) - espera 60s e retoma'
                      % (name, start_chunk, len(values)))
                time.sleep(60.0)
                continue
            attempt += 1
            if attempt < retries:
                start_chunk = 0  # falha real: reconstrói do zero
                time.sleep(2.0 * attempt)
    raise RuntimeError('%s: failed after %d retries: %s' % (name, retries, last_err))


# ------------------------------------------------------------------ ledger

def start_job(con, job_id):
    con.execute("INSERT INTO sync_jobs (id, source_id, direction, entity, cursor, status, started_at, items_changed, error) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (job_id, SOURCE_ID, 'push', 'sheets', None, 'running', now(), 0, None))
    con.commit()


def finish_job(con, job_id, status, items, error=''):
    con.execute('UPDATE sync_jobs SET status=?, finished_at=?, items_changed=?, error=? WHERE id=?',
                (status, now(), items, error, job_id))
    con.commit()


def record_change(con, job_id, tab, kind, content_hash):
    con.execute("INSERT OR REPLACE INTO sync_changes (job_id, table_name, record_key, change_kind, content_hash) "
                "VALUES (?,?,?,?,?)", (job_id, 'sheet_tab', tab, kind, content_hash))


def record_source_hash(con, tab, content_hash):
    con.execute("INSERT OR REPLACE INTO source_records (source_id, table_name, record_key, content_hash, seen_at) "
                "VALUES (?,?,?,?,?)", (SOURCE_ID, 'sheets', tab, content_hash, now()))


def prev_hash(con, tab):
    r = con.execute("SELECT content_hash FROM source_records "
                    "WHERE source_id=? AND table_name='sheets' AND record_key=?",
                    (SOURCE_ID, tab)).fetchone()
    return r['content_hash'] if r else None

# ------------------------------------------------------------------ orchestration

def _task_list(con):
    """(tab, values, ncols). Dashboard e Sincronizacoes tratadas a parte."""
    tasks = [
        ('Fontes', build_fontes(con), 6),
        ('Cartas_Master', build_cartas_master(con), 19),
        ('Ataques', build_ataques(con), 8),
        ('Habilidades', build_habilidades(con), 6),
        ('Evolucoes', build_evolucoes(con), 6),
        ('Treinadores', build_treinadores(con), 10),
        ('Energias', build_energias(con), 3),
    ]
    for el, tab in ELEMENT_TABS.items():
        tasks.append((tab, build_element_tab(con, el), 9))
    tasks.append(('Pendencias', build_pendencias(con), 6))
    for tab in COMPETITIVE_TABS:
        builder, _sql = COMPETITIVE_SOURCES[tab]
        tasks.append((tab, builder(con), len(builder(con)[0])))
    tasks.append(('Expansoes', build_expansoes(con), 8))
    return tasks


# (open_db F5d definido acima das constantes do ledger)


def main():
    dry = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    # F11: DUAS conexoes (defeito latente do F5d): builders leem do CANONICO
    # (mode=ro); contabilidade do sync grava no LEDGER dedicado. Nenhuma
    # tabela de catalogo no ledger; nenhum write no canonico.
    con_cat = open_db(ledger=False)
    con_led = None if dry else open_db(ledger=True)
    con = con_cat  # builders; contabilidade usa con_led explicito
    job_id = 'f5b_' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())

    sheet_by_title = {}
    if not dry:
        meta = sync.sheets_api('/spreadsheets/%s' % SPID)
        sheet_by_title = {s['properties']['title']: {'id': s['properties']['sheetId'],
                                                     'grid': s.get('gridProperties') or {}}
                          for s in meta.get('sheets') or []}
        print('Abas no arquivo:', len(sheet_by_title))

    if dry:
        print('---- DRY RUN: builders ----')
        for tab, rows, ncols in _task_list(con):
            print('%-14s linhas de dados=%5d cols=%d' % (tab, len(rows) - 1, ncols))
        return

    # F11: payload construido UMA vez; grades ajustadas ANTES da escrita
    # (aba incha gasta celulas do limite global mesmo vazia).
    tasks = _task_list(con_cat)
    fit_grids(sheet_by_title, tasks)

    start_job(con_led, job_id)
    skipped = 0
    failures = []
    mirror = [['job_id', 'target_tab', 'rows_sent', 'status', 'started_at', 'finished_at', 'error']]
    results = {}
    for tab, rows, ncols in tasks:
        h = sha256_json(rows)
        prev = prev_hash(con_led, tab)  # F11: hash anterior vive no LEDGER
        t0 = time.time()
        try:
            if tab in COMPETITIVE_TABS and h == prev and not force:
                # F11: hash igual NO LEDGER nao basta - o conteudo REAL da
                # aba e comprovado por leitura de volta (processo morto no
                # meio da escrita deixa aba pela metade com hash integro no
                # ledger). Divergente/placeholder -> reescrita completa.
                try:
                    got = read_back_verify(tab, ncols)
                except Exception as ex:
                    print('  %s: verificacao falhou (%s) - reescrevendo'
                          % (tab, str(ex)[:80]))
                    got = -1
                if got == len(rows):
                    r = {'status': 'skipped', 'rows': len(rows) - 1,
                         'reason': 'unchanged'}
                else:
                    print('  %s: DIVERGE (planilha %d vs origem %d) - reescrita'
                          % (tab, got, len(rows)))
                    r = write_tab_full(tab, rows, ncols)
            else:
                r = (write_tab_full(tab, rows, ncols) if tab in COMPETITIVE_TABS
                     else write_increment(tab, rows, ncols, force=force))
            kind = 'insert' if prev is None else 'update'
            if r['status'] == 'skipped':
                skipped += 1
                # schema exige insert|update|delete|conflict; aba inalterada
                # registra 'update' com o MESMO hash (referencia do ciclo)
                kind = 'update'
            record_change(con_led, job_id, tab, kind, h)
            record_source_hash(con_led, tab, h)
            results[tab] = r
            mirror.append([job_id, tab, r.get('rows', 0), r['status'], now(), now(), ''])
            print('%-14s %-8s data_rows=%-5d %.1fs' % (tab, r['status'], r.get('rows', 0), time.time() - t0))
        except Exception as ex:
            failures.append((tab, str(ex)[:200]))
            mirror.append([job_id, tab, 0, 'failed', now(), now(), str(ex)[:180]])
            print('%-14s FAIL %s' % (tab, str(ex)[:160]))

    delete_page1(sheet_by_title)
    for tab, _rows, ncols in tasks:
        format_tab(sheet_by_title, tab, ncols)

    # Dashboard por ULTIMO (indicadores do job concluido)
    try:
        dash = build_dashboard(con)
        prev = prev_hash(con_led, 'Dashboard')
        r = write_increment('Dashboard', dash, 3, force=force)
        record_change(con_led, job_id, 'Dashboard',
                      'insert' if prev is None else 'update', sha256_json(dash))
        record_source_hash(con_led, 'Dashboard', sha256_json(dash))
        mirror.append([job_id, 'Dashboard', r['rows'], r['status'], now(), now(), ''])
        print('%-14s %-8s data_rows=%d' % ('Dashboard', r['status'], r['rows']))
    except Exception as ex:
        failures.append(('Dashboard', str(ex)[:200]))
        print('Dashboard FAIL', str(ex)[:160])
    finish_job(con_led, job_id, 'failed' if failures else 'success', len(results),
               '; '.join('%s: %s' % f for f in failures)[:500])

    # Espelho de auditoria: historico preservado + linhas do novo job
    try:
        cur = None
        for _i in range(5):  # F11: leitura do espelho e a unica TOTAL do ciclo
            cur = sync.sheets_api('/spreadsheets/%s/values/Sincronizacoes!A1:G2000' % SPID).get('values')
            if cur:
                break
            print('  espelho: leitura vazia (tentativa %d), espera 20s' % (_i + 1))
            time.sleep(20.0)
        cur = cur or []
        hist = [r for r in cur[1:] if any(c not in (None, '') for c in r)]
        out = [mirror[0]] + hist + [r for r in mirror[1:]]
        r = write_increment('Sincronizacoes', out, 7, force=True)
        record_source_hash(con_led, 'Sincronizacoes', sha256_json(out))
        record_change(con_led, job_id, 'Sincronizacoes', 'update', sha256_json(out))
        print('Sincronizacoes espelho: %s rows=%d' % (r['status'], r['rows']))
    except Exception as ex:
        print('Sincronizacoes espelho ERR:', str(ex)[:200])

    print('---- RESUMO ----')
    print('job_id:', job_id)
    print('abas processadas:', len(results), '| skips:', skipped, '| falhas:', len(failures))
    for f in failures:
        print('FALHA:', f)
    if con_led is not None:
        con_led.commit()
        con_led.close()
    con_cat.close()


if __name__ == '__main__':
    main()
