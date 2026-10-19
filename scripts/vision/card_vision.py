#!/usr/bin/env python3
"""F6 - card-vision: reconhecimento de cartas do Pokemon TCG Pocket via imagem -> catalogo.

Uso (como skill):
    python3 scripts/vision/card_vision.py <imagem> [--catalog data/pocket.sqlite]
    python3 scripts/vision/card_vision.py --batch <dir_de_imagens>

Pipeline:
 1. OBSERVACAO   - extrai observacoes da imagem via visao multimodal (LLM de visao).
                   A observacao IA pode ser gerada por: extract_observations.py (vision_analyze)
                   ou colada a mao. Este script NAO depende so de OCR (obrigatorio pela F6).
 2. RESOLUCAO    - busca candidatos no SQLite (LIKE + FTS5) e ranqueia por
                   similaridade de nome + HP + elemento + estagio + ataque/dano.
 3. DESAMBIGUACAO- identidade mecanica primeiro (mechanical_hash), depois print
                   por set_code#number se o numero impresso for legivel.
 4. VEREDICTO    - status ok/incerto + grau de confianca (alta/media/baixa) + motivo.

Imagem ilegivel ou corrupcao => status 'incerto' com motivo (NUNCA chutar).

Casos de "incerto" e avisos (F6b):
  - carta inexistente  : a melhor identidade fica ABAIXO do limiar (0.60) -> motivo diz
                         que a carta PODE NAO EXISTIR no catalogo/Pocket; sem best_guess
                         que sugira uma carta errada (alternatives fica, so como contexto).
  - empate legitimo    : >= 2 identidades empatadas (>= 0.95*max) COM score >= 0.60
                         -> motivo de desambiguacao por arte/moldura/set impresso.
  - conflito_elemento  : nome+HP+ataque concordam mas elemento diverge -> campo
                         'conflito_elemento: observado=X catalogo=Y' no veredicto 'ok',
                         para o operador saber QUAL campo duvidar (nao perde score
                         silenciosamente).
  - nenhum candidato   : grafia nao casa nem com LIKE nem com FTS5 -> motivo tambem
                         diz que a carta pode nao existir no Pocket.

Decisao de desenho documentada (docs/FASE1-DIAGNOSTICO.md, secao 4.1):
  visao multimodal e a fonte de observacoes; OCR puro e insuficiente em webp 367x512.
"""
import argparse
import difflib
import json
import sqlite3
import sys
from pathlib import Path

DB_DEFAULT = Path(__file__).resolve().parents[2] / 'data' / 'pocket.sqlite'


def resolve(db_path, observations, print_number=None):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        return _resolve(db, observations, print_number)
    finally:
        db.close()


def _resolve(db, o, print_number=None):
    if 'uncertain' in o:
        return {'status': 'incerto', 'motivo': o['uncertain']}
    name = o.get('name') or ''
    rows = db.execute("SELECT id, canonical_name, hp, element, stage, is_ex FROM cards "
                      "WHERE canonical_name LIKE ? LIMIT 8", ('%' + name + '%',)).fetchall()
    if not rows:
        toks = ' OR '.join(t for t in name.lower().split() if len(t) > 2)
        rows = db.execute("SELECT c.id, c.canonical_name, c.hp, c.element, c.stage, c.is_ex "
                          "FROM cards c JOIN cards_fts f ON f.card_id = c.id "
                          "WHERE cards_fts MATCH ? LIMIT 8", (toks,)).fetchall()
    scored = []
    for cid, canon, hp, el, st, is_ex in rows:
        s = 0.55 * _ratio(norm(canon), norm(name))
        hp_ok = o.get('hp') is not None and hp is not None and int(o['hp']) == int(hp)
        if hp_ok:
            s += 0.15
        el_match = bool(o.get('element') and el and _canon(o['element']) == el)
        if el_match:
            s += 0.10
        if o.get('stage') and st and _canon(o['stage']) in (st, st + '_ex'):
            s += 0.10
        attack_ok = False
        for an, cost, dmg, eff in db.execute(
                "SELECT name, energy_cost, damage, NULL FROM card_attacks WHERE card_id=?", (cid,)):
            r = _ratio(norm(an), norm(o.get('attack') or ''))
            dmg_ok = o.get('damage') is not None and _damage(dmg) == int(o['damage'])
            if r > 0.85 or (dmg_ok and not o.get('attack')):
                s += 0.15 * max(r, 1.0 if dmg_ok else 0)
                attack_ok = True
                break
        scored.append({'card_id': cid, 'name': canon, 'score': round(min(s, 1.0), 3),
                       'catalogo_element': el, 'corroborado': bool(hp_ok or attack_ok)})
    scored.sort(key=lambda x: (-x['score'], x['card_id']))
    if not scored:
        return {'status': 'incerto',
                'motivo': 'nenhuma identidade do catalogo corresponde a carta observada; '
                          'verifique grafia ou a carta pode nao existir no Pocket'}

    max_score = max(scored[0]['score'], 0.001)
    top = scored[0]
    # Empate APENAS com score forte — runners em 0.60- NAO empatam, caem na regra de
    # carta inexistente abaixo (nao existem duas identidades fortes ao mesmo tempo).
    runners = [x for x in scored[1:] if x['score'] >= max_score * 0.95]

    # Carta inexistente: nenhuma correspondencia REAL. Duas rotas para incerto aqui:
    #  (a) score abaixo do limiar duro (0.60), ou
    #  (b) score ate 0.69 SEM corroboracao de HP nem de ataque (elemento+estagio+
    #      similaridade de nome constroem score generico que nao prova identidade —
    #      ex.: Charizard VMAX observada: nenhum HP 330 / nenhum G-Max Wildfire).
    # Sem best_guess que sugira uma carta errada; alternatives apenas contexto.
    if top['score'] < 0.60 or (top['score'] < 0.70 and not top['corroborado']):
        motivo = ('melhor candidato abaixo do limiar de existencia (score %.2f): nenhuma '
                  'identidade do catalogo corresponde a carta observada — provavelmente '
                  'nao existe no Pocket' % top['score'])
        out = {'status': 'incerto', 'motivo': motivo}
        if runners:
            out['alternatives'] = runners   # contexto (o que chegou perto), NAO sugestao
        return out

    # Empate legitimo APENAS quando o grupo inteiro e forte (todos >= 0.60)
    if runners:
        return {'status': 'incerto',
                'motivo': 'empate entre identidades mecanicas: escolha por arte/moldura/set impresso',
                'best_guess': top, 'alternatives': runners}

    conf = 'alta' if top['score'] >= 0.9 else 'media'
    # Conflito de campo: nome/HP/ataque concordam mas elemento diverge -> reportar de
    # forma explicita (nao abaixar o score silenciosamente)
    conflitos = []
    if o.get('element') and top.get('catalogo_element') \
            and _canon(o['element']) != _canon(top['catalogo_element']):
        conflitos.append("conflito_elemento: observado=%s catalogo=%s — provavel erro de "
                         "leitura a 367px" % (o['element'], top['catalogo_element']))
    result = {'status': 'ok', 'confianca': conf, **top}
    result.pop('catalogo_element', None)
    result.pop('corroborado', None)   # flag de diagnostico interno, nao opera a veredicto
    prs = db.execute("SELECT set_code, number, rarity FROM card_prints WHERE card_id=? "
                     "ORDER BY set_code, number", (top['card_id'],)).fetchall()
    result['prints'] = [{'set_code': s, 'number': n, 'rarity': r} for s, n, r in prs]
    if print_number:
        match = [p for p in result['prints'] if p['number'] == print_number]
        if match:
            result['resolved_print'] = match[0]
    else:
        result['impressao'] = (
            'numero de colecao ilegivel; %d impressoes mecanicamente identicas: '
            'diferencie por set_code#number na imagem de alta resolucao' % len(prs))
    if conflitos:
        result['conflicto'] = conflitos[0]
    return result


def _ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _canon(v):
    return str(v or '').strip().lower().replace("'", '').replace(' ', '_')


def _damage(d):
    try:
        return int(str(d).rstrip('+x'))
    except (TypeError, ValueError):
        return None


norm = _canon


def main(argv=None):
    ap = argparse.ArgumentParser(description='card-vision: imagem -> carta do catalogo')
    ap.add_argument('image', nargs='?', help='caminho da imagem da carta')
    ap.add_argument('--catalog', default=str(DB_DEFAULT), help='SQLite do catalogo')
    ap.add_argument('--observation', help='JSON com observacoes da visao (inline ou @arquivo); '
                                          'sem ele, o campo passa por stdin')
    args = ap.parse_args(argv)
    if args.observation and args.observation.startswith('@'):
        obs = json.loads(Path(args.observation[1:]).read_text(encoding='utf-8'))
    elif args.observation:
        obs = json.loads(args.observation)
    else:
        obs = json.load(sys.stdin)
    verdict = resolve(args.catalog, obs)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict.get('status') == 'ok' else 2


if __name__ == '__main__':
    sys.exit(main())
