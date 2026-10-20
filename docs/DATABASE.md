# DATABASE.md — SQLite Canônico do Pokémon Pocket Intelligence

**Fase:** 2 · Estrutura, contratos JSON e migrations
**Owner:** tony_stark (CTO) · **Status:** aprovado (acceptance 1–4 verificados por teste)

## 1. Princípios

1. **SQLite é a fonte canônica** (FASE1 §7). Sheets/xlsx são interfaces derivadas.
2. **foreign_keys=ON e journal_mode=WAL em toda conexão** — o runner (`scripts/db_migrate.py`) enforce.
3. **FTS5** indexa nome + regra especial de cada carta (tabela `cards_fts`, triggers automáticos em cards).
4. **Separação identidade mecânica × impressão**: `cards` nunca muda quando a arte/set muda; impressões vivem em `card_prints` (UNIQUE card_id+set_code+number).
5. Rastreabilidade: toda linha de dados carrega `source_id` → `sources` (tier: canonical/crosscheck/enrichment).
6. Nenhuma sobrescrita destrutiva: upserts passam por `source_records` (hash) + `audit_logs`.
7. Migrations **imutáveis** (checksum SHA-256 em `schema_migrations`); divergência = erro alto.

## 2. Arquivos

| Caminho | Papel |
|---|---|
| `database/migrations/0001_init.sql` | Schema completo (27 tabelas + FTS5 + triggers) |
| `scripts/db_migrate.py` | Runner idempotente (--db, --status, --dry-run) |
| `credentials/contracts/*.json` → **`contracts/`** | 12 contratos JSON Schema (draft 2020-12) |
| `scripts/contract_check.py` | Validador de contrato (subset stdlib, sem pip) |
| `scripts/gen_contracts.py` | Gerador dos 12 contratos (fonte da verdade) |
| `tests/unit/test_migrations.py` | 10 testes: migração, idempotência, FK, FTS5, checks; também valida os 12 contratos e seus x-examples |

## 3. Tabelas principais

- **Núcleo de cartas:** `expansions`, `cards` (identidade mecânica: nome, categoria, element, stage, hp, weakness, retreat, special_rule, mechanical_hash), `card_prints` (impressão/arte: set_code, number, rarity, artist, image_url), `card_attacks`, `card_abilities`, `card_evolutions` (card_id ↔ pre_evo_card_id ↔ stage), `card_localizations`, `card_legality`.
- **Regras:** `rules` (id estável tipo `DECK-001`, source_id, verified_at, vigência, exceções).
- **Metagame (F7, migration 0003):** `meta_archetypes` (tier S/A/B/C/D ou vazio=sem evidência; tier_basis obrigatório quando tier ≠ NULL; sample_decks), `archetype_cards` (núcleo citável por arquétipo), `meta_snapshots` (apend-only POR JANELA — 7/14/30 dias coexistem), `meta_snapshot_archetypes` (share_pct, win_rate_pct, tier, sample_decks, sample_matches), `matchups` (sample_size ≥ 1 + sample_matches + confidence high≥200/medium≥50/low), `tiers` (gates ≥20 listas e ≥100 jogos; faixas S≥55/A≥52/B≥49/C≥45/D<45 — regra F7 v1 em docs/META.md), `tournaments`, `tournament_results`, `tournament_matches` (jogos individuais auditáveis, NOVA em 0003).
- **Decks:** `decks` (CHECK total_cards = 20), `deck_cards` (CHECK quantity entre 1 e 2), `deck_evaluations`, `evaluation_dimensions`.
- **Governança:** `sources`, `source_records` (hash de conteúdo), `sync_jobs`, `sync_changes`, `audit_logs`, `schema_migrations`.

## 4. Uso

    python3 scripts/db_migrate.py                    # aplica migrações (idempotente)
    python3 scripts/db_migrate.py --status           # mostra estado
    python3 scripts/db_migrate.py --db /tmp/teste.sqlite   # banco alternativo
    python3 scripts/contract_check.py                # valida os 12 contratos

Banco canônico operacional: **`data/pocket.sqlite`** (+ `-wal`, `-shm`) — ÚNICO caminho
default de dados (F4b; decisão do CEO). `database/` é exclusivo de migrations, schemas
e backups: o runner NUNCA cria banco em caminho concorrente. Ignorado por .gitignore
(dado, não código) — ver commit 9a67b99.

Desde o F5d (19/10) existe exatamente UM banco com dados de cartas:
`data/pocket.sqlite` (Application-ID 1 = catalogo canonico). O ledger de
sincronização `data/sync_state.sqlite` (Application-ID 2) é um banco
PEQUENO, exclusivo de sync (sync_jobs/sync_changes/source_records +
schema_migrations) — NÃO contém cards/card_prints/card_attacks nem nenhuma
tabela de catalogo. Cache HTTP da coleta: `data/cache/pages` (persistente;
proibido /tmp — escopo §21). Raw de metagame (F7): `data/meta/raw/` (JSON de torneios da
Limitless Developer API, apend-only, nunca apagado) e relatórios em
`data/meta/reports/` — ambos fora do git (dado de terceiros, §.gitignore).

## 5. Integridade — o que deve falhar

- FK para `source_id` inexistente → `IntegrityError` (testado).
- `decks.total_cards != 20` → `IntegrityError` (testado).
- `deck_cards.quantity = 3` → `IntegrityError` (testado; §contract deck_card: max 2).
- `matchups.sample_size = 0` → `IntegrityError` (sem evidência não há matchup).
- Checksum de migration divergente → `RuntimeError` no runner (testado).

## 6. Contratos (versão 2.0.0, stage F2)

`card`, `card_variant`, `deck`, `deck_card`, `evaluation`, `expansion`, `matchup`,
`meta_archetype`, `meta_snapshot`, `rule`, `source`, `sync_job` — cada um com `$id`,
`x-version`, `x-skills`, `additionalProperties: false` e `x-example`.

Convenção de ID: `^[a-zA-Z0-9_.-]+$` (aceita suffixo de set como `B4b` — códigos de conjunto têm maiúscula). `rule.id` é `^[A-Z][A-Z0-9_-]+$` (ex.: `DECK-001`).

## 7. Nota de冶 ambiente

- Python 3.13.5 sem pip (PEP 668), `uv` bloqueado por guard de rede nesta sessão —
  por isso o validador de JSON Schema vive hoje em `scripts/contract_check.py` (stdlib).
  Quando `pytest`/`jsonschema` estiverem instalados no ambiente do CI, os testes rodam
  com pytest e o validador pode ser substituído pelo pacote full em um ponto único
  (`contract_check.validate`).

## 8. Verificação executada nesta Fase 2

- `python3 scripts/db_migrate.py` do zero + segunda execução → skip idempotente, pós-condições OK.
- `python3 -m unittest tests.unit.test_migrations` → **Ran 10 tests · OK**.
- 12/12 contratos auto-validados com seus x-examples.

## 9. Manutenção F7c — prints fantasma do catálogo e re-ingestão (19/10/2026)

Achado (card t_a36b22ce): 9 listas reais do corpus F7 (`decks.id LIKE 'll-%'`) somavam
3 cópias do mesmo nome canônico (8× Gible, 1× Bulbasaur) — impossível em lista oficial
de Pocket (máx 2 por nome).

**Causa-raiz (duas camadas, catálogo — não a ingestão F7):**

1. **Parser F4 original (c81a388):** a linha de versão da promo (ex.: `P-A#46`) era
   servida pela fonte como `<a>` **sem href**; o parser caía no fallback
   `vset = set_code` e atribuía o print da promo ao número **hômônimo** do próprio
   set — a promo #46 do Gible virava o print `A2a#46`, que na verdade é o **Gabite**
   (print fantasma). 61 prints ficaram com identidade mecânica errada.
2. **Loader F4c (`INSERT OR IGNORE` em `card_prints`):** primeiro dono ganha para
   sempre — o re-parse correto de 22:22 (parser 440e5df já com regex de hífen)
   nunca corrigiu os donos errados já gravados.

A ingestão F7 (`meta_pipeline.resolve_decklist`) só fez o join
`print_index[(set, number)]` confiar no catálogo envenenado: a linha do Gabite
contava como Gible e, nas 9 listas que TINHAM o Gible legítimo, a soma estourou 3.

**Reparo aplicado (R2, backup `data/pocket.sqlite.bak-f7c-1`):**

- Parser: linha de versão não-current **sem href é pulada** (print errado é pior que
  print ausente — `INSERT OR IGNORE` fossiliza).
- Catálogo: 61 `card_prints.card_id` repontados para a identidade mecânica da própria
  página do print (re-parse auditado das 4317 fichas em cache; own_id quando existe,
  senão a identidade fundida por `mechanical_hash` — 19 casos). Trilha: **61 linhas
  em `audit_logs`** (`actor='tony_stark:f7c'`, before/after por print).
- Ingestão: 4 snapshots regenerados do raw (`--full`, 7d, 14d, 30d — todos do dia
  19/10 estavam poluídos); `decks`/`deck_cards` reescritos pelo pipeline
  (DELETE+reinsert por deck, id determinístico).

**Delta medido (backup × pós):** violações ll-* por nome >2: **9 → 0** (query de
aceite vazia, inclusive varredura ampla sobre todos os decks); cópias de Gible no
corpus: 202 → 194 (−8); Bulbasaur: 55 → 53 (−2); linhas `deck_cards`: 115.801 →
115.781 (−20; as linhas dobradas saem, Gabite/Exeggutor ex re-atribuídos);
`card_prints`: 4.317 → 4.317 (0 prints a menos — correção de dono, não exclusão);
top-6 do snapshot full por share: **inalterado** (efeito fino no agregado).
Suite do projeto: **112/112 verde** (3 skipped por design). `PRAGMA
foreign_key_check` vazio; `integrity_check` ok. Relatórios pós:
`report_{full,7d,14d,30d}_pos_f7c.json` na área de trabalho local do executor
(fora do repo, dados grandes).

## 10. Manutenção F13+ — nomes dos promos P-A/P-B poluídos com comentário HTML (19/10/2026)

Achado no aceite da F13 (card t_24f07bbc → filha t_8bc6cf98):
`db_query.py coverage` exibia `expansions.name` de P-A/P-B como
`Promo-A – Limitless TCG Pocket Database <!-- Google tag`.

**Causa-raiz:** nas páginas de set promocional (sem infobox), o fallback de
`parse_set_metadata` para o `<title>` usava a regex `<title>([^(]+)[(]` — o
`[^(]` casa com `<`, `/` e espaço, então a captura **atravessava o `</title>`**
até o primeiro `(` do documento, que está no comentário do GTM
(`<!-- Google tag (gtag.js) -->`). O `INSERT OR IGNORE` do `upsert_expansion`
(loader F4c) fossilizou o valor errado — mesma classe do F7c (primeiro dono
eterno).

**Reparo (R2, backup `data/pocket.sqlite.bak-f13plus-1`):**

- Parser (`integrations/limitlesstcg-pocket/parser.py`): (1) strip global de
  comentários HTML `<!--...-->` antes de qualquer extração de nome; (2) fallback
  `<title>` **preso ao elemento** (`<title>[^<]*</title>`) — após o strip, o JS
  inline `function gtag(` viraria o novo vazamento; (3) sufixo de fonte
  `– Limitless TCG Pocket Database` removido (`clean_expansion_name`). Semântica
  legada preservada: corte no `(` do código do conjunto
  (`Genetic Apex (A1) – ...` → `Genetic Apex`). TDD: 5 testes novos
  (`tests/unit/test_f13plus_promo_names.py`), RED provado antes do fix.
- Catálogo: **2 linhas** em `expansions` corrigidas por UPDATE dirigido (P-A →
  `Promo-A`, P-B → `Promo-B`; **não re-coleta**; release_date/card_count dos
  promos intocados — a fonte não declara, `1970-01-01`/0 é o placeholder da era
  F4). Trilha: **2 linhas em `audit_logs`** (`actor='tony_stark:f13plus'`,
  before/after do nome).

**Prova pós:** `db_query.py coverage` com `Promo-A`/`Promo-B` limpos (overall
100.0, zero gap); diff do parser novo × antigo sobre TODAS as 4.366 páginas em
cache = **5 diferenças, todas esperadas** (P-A/P-B nas duas variantes de URL +
página-índice `/cards`, que agora sai `Sets` limpo); varredura de `expansions`
inteira sem nenhum nome com comentário/sufixo; `foreign_key_check` vazio e
`integrity_check` ok; suite **136/136 nos 2 intérpretes** (3 skipped de SDK por
design). Não afeta identidade mecânica, legality nem joins (chaves são `code`).
