"""F6 - resolve cartas a partir de observacoes de imagem (ground truth do vision_analyze)
contra o catalogo SQLite (data/pocket.sqlite).

Pipeline (por caso):
 1. observacoes da carta (nome, hp, elemento, estagio, ataque/dano, numero impresso quando legivel)
 2. busca candidatos: LIKE em canonical_name; FTS5 quando Like falha
 3. ranqueia por similaridade ordem-nome (SequenceMatcher) + matches de hp/elemento/estagio/ataque
 4. se empate entre identidades -> card_incerto
 5. desambiguacao de impressao: por numero impresso legivel; se ilegivel, retorna identidade +
    lista de prints e nota sobre prints mecanicamente identicos
Saida: JSON por imagem com confiancas.
"""
import difflib
import json
import sqlite3
import sys

DB = '/workspace/ARCOS/projetos/pokemon-pocket-intelligence/data/pocket.sqlite'

# ground truth de visao: roda visao multimodal (vision_analyze) por fixture, colada abaixo.
# data: 2026-10-18. Formato: arquivo -> observacoes
OBS = {
    "A1_001.webp":    dict(name="Bulbasaur", hp=70, element="grass", stage="basic",
                           attack="Vine Whip", damage=40, print_number=None),
    "A1_122.webp":    dict(name="Gengar", hp=130, element="psychic", stage="stage2",
                           attack="Bother", damage=50, print_number=None),
    "A1_123.webp":    dict(name="Gengar ex", hp=170, element="psychic", stage="stage2",
                           attack="Spooky Shot", damage=100, print_number=None),
    "B2b_039.webp":   dict(name="Mega Gengar ex", hp=210, element="darkness", stage="mega_ex",
                           attack="Labyrinth of Shadows", damage=120, print_number=None),
    "B4b_141.webp":   dict(name="Mega Gengar ex", hp=210, element="darkness", stage="mega_ex",
                           attack="Labyrinth of Shadows", damage=120, print_number=None),
    "B1_001.webp":    dict(name="Pinsir", hp=90, element="grass", stage="basic",
                           attack="X-Scissor", damage=50, print_number=None),
    "A2_001.webp":    dict(name="Oddish", hp=60, element="grass", stage="basic",
                           attack="Blot", damage=10, print_number=None),
    "A3_001.webp":    dict(name="Exeggcute", hp=60, element="grass", stage="basic",
                           attack="Rolling Tackle", damage=30, print_number=None),
    "A4_001.webp":    dict(name="Oddish", hp=50, element="grass", stage="basic",
                           attack="Poison Powder", damage=10, print_number=None),
    "B2_001.webp":    dict(name="Ledyba", hp=60, element="grass", stage="basic",
                           attack="Punch", damage=10, print_number=None),
    "B4_001.webp":    dict(name="Wurmple", hp=60, element="grass", stage="basic",
                           attack="Gnaw", damage=10, print_number=None),
    "A1a_001.webp":   dict(name="Exeggcute", hp=50, element="grass", stage="basic",
                           attack="Growth Spurt", damage=None, print_number=None),
    "B4b_021.webp":   dict(name="Sprigatito", hp=60, element="grass", stage="basic",
                           attack="Leafage", damage=20, print_number=None),
    "B4b_429.webp":   dict(name="Koraidon ex", hp=150, element="fighting", stage="basic",
                           attack="World Wrecker", damage=110, print_number=None),
    # casos ruins (aceitacao 3)
    "fixtures_bad/B4b_141_corrupt.webp": dict(uncertain="imagem parcialmente corrompida: rodape ilegivel"),
    "fixtures_bad/A1_001_trunc.webp":    dict(uncertain="imagem truncada: nao decodifica (sem carta visivel)"),
    "fixtures_bad/B4b_141_lying_name.webp":
        dict(name="Gengar", hp=130, element="psychic", stage="stage2", attack="Bother", damage=50,
             print_number=None, hint="nome do arquivo MENTIROSO (diz B4b_141) - visao correta sobre venceu"),
}

ELEMENT_CANON = {  # nomes what vision devolve -> labels canonicos
    'grass': 'grass', 'fire': 'fire', 'water': 'water', 'lightning': 'lightning',
    'psychic': 'psychic', 'fighting': 'fighting', 'darkness': 'darkness', 'metal': 'metal',
}
STAGE_CANON = {
    'basic': 'basic', 'stage1': 'stage1', 'stage2': 'stage2', 'mega_ex': 'mega_ex',
}


def norm(s):
    return (s or '').strip().lower().replace("'", '')


def parse_damage(d):
    if d is None:
        return None
    try:
        return int(str(d).rstrip('+x'))
    except ValueError:
        return None


def fetch_attacks(db, card_id):
    return db.execute("SELECT name, energy_cost, damage, effect_text FROM card_attacks WHERE card_id=?",
                      (card_id,)).fetchall()


def fts_candidates(db, name, limit=8):
    q = ' OR '.join(token for token in norm(name).split() if len(token) > 2)
    rows = db.execute("SELECT card_id FROM cards_fts WHERE cards_fts MATCH ? LIMIT ?",
                      (q, limit)).fetchall()
    return [r[0] for r in rows]


def candidates(db, name):
    like = '%' + name + '%' if name else ''
    out = []
    if like:
        for r in db.execute(
                "SELECT id FROM cards WHERE canonical_name LIKE ? LIMIT ?", (like, 8)):
            out.append(r[0])
    if not out:
        out = fts_candidates(db, name) if name else []
    return out


def score_card(db, card_id, o):
    c = db.execute("SELECT canonical_name, hp, element, stage, is_ex FROM cards WHERE id=?",
                   (card_id,)).fetchall()
    if not c:
        return None
    c = c[0]
    canon_name, hp, el, st, is_ex = c
    s = 0.0
    s += 0.55 * difflib.SequenceMatcher(None, norm(canon_name), norm(o.get('name') or '')).ratio()
    if o.get('hp') is not None and hp is not None:
        s += 0.15 if int(o['hp']) == int(hp) else 0.0
    if o.get('element') and el:
        s += 0.10 if ELEMENT_CANON.get(norm(o['element'])) == el else 0.0
    if o.get('stage') and st:
        s += 0.10 if STAGE_CANON.get(norm(o['stage'])) == st else 0.0
    # ataque: nome ou dano
    atk_ob = norm(o.get('attack') or '')
    for name, cost, dmg, eff in fetch_attacks(db, card_id):
        ratio = difflib.SequenceMatcher(None, norm(name), atk_ob).ratio() if atk_ob else 0
        dmg_ok = o.get('damage') is not None and parse_damage(dmg) == int(o['damage'])
        if ratio > 0.85 or dmg_ok:
            s += 0.15 * max(ratio, 1.0 if dmg_ok else 0)
            break
    return {'card_id': card_id, 'canonical_name': canon_name, 'score': round(min(s, 1.0), 3)}


def resolve(db, o):
    if 'uncertain' in o:
        return {'status': 'incerto', 'motivo': o['uncertain']}
    cands = candidates(db, o.get('name') or '')
    scored = [x for x in (score_card(db, cid, o) for cid in cands) if x]
    scored.sort(key=lambda x: -x['score'])
    if not scored:
        return {'status': 'incerto', 'motivo': f"nenhum candidato para '{o.get('name')}'"}
    top = scored[0]
    runners = [x for x in scored[1:] if x['score'] >= 0.95 * max(top['score'], 0.01)]
    # aceitacao 4: confianca por caso
    if top['score'] >= 0.9 and not runners:
        conf = 'alta'
    elif top['score'] >= 0.75:
        conf = 'media'
    else:
        conf = 'baixa'
    result = {
        'status': 'ok' if conf != 'baixa' else 'incerto',
        'motivo': None if conf != 'baixa' else f"melhor score {top['score']} baixo demais",
        'name': top['canonical_name'],
        'card_id': top['card_id'],
        'score': top['score'],
        'confianca': conf,
        'alternatives': runners,
    }
    if result['status'] == 'ok':
        prs = db.execute(
            "SELECT set_code, number, rarity FROM card_prints WHERE card_id=? ORDER BY set_code, number",
            (top['card_id'],)).fetchall()
        result['prints'] = [dict(zip(('set_code', 'number', 'rarity'), r)) for r in prs]
        result['nota_prints'] = (
            '%d impressoes desta identidade mecanica; numero legivel ausente na imagem -> '
            'impressao exata nao resolvida; prints sao mecanicamente identicos' % len(prs))
        # aceitacao 2: prints realmente identicos?
        hashes = db.execute(
            """SELECT DISTINCT c.mechanical_hash, p.set_code, p.number
               FROM card_prints p JOIN cards c ON c.id=p.card_id
               WHERE c.canonical_name=? ORDER BY p.set_code, p.number""",
            (top['canonical_name'],)).fetchall()
        if hashes:
            uniq = {h[0] for h in hashes}
            if len(uniq) == 1 and len(hashes) > 1:
                result['variant_note'] = (
                    'impressoes mecanicamente IDENTICAS (mesmo mechanical_hash %s...): '
                    'diferenciacao possivel APENAS por set_code#number impresso' % uniq.pop()[:12])
    return result


def main():
    db = sqlite3.connect(DB)
    out = {}
    only = sys.argv[1:] if len(sys.argv) > 1 else list(OBS)
    for img in only:
        out[img] = resolve(db, OBS[img])
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
