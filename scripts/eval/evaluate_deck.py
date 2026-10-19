#!/usr/bin/env python3
"""F9 · Deck-evaluator heurístico do Pokemon TCG Pocket (card t_3afdfbcb, R2).

Avalia, compara e otimiza decks com nota heurística 0-100 REPRODUZÍVEL
(pesos em skills/pokemon-pocket-deck-evaluator/weights.json) e matchups
contra os principais arquetipos do meta real (snapshots/matchups da F7).

REGRAS DE HONESTIDADE (proibições do card):
  - A nota é QUALIDADE HEURÍSTICA (score_type=heuristic_quality_NOT_winrate).
    NUNCA é winrate nem previsão de resultado de torneio.
  - Matchup tem EVIDÊNCIA declarada: 'real' (tabela matchups da F7, com
    sample_size e confidence) ou 'teorico' (fatores derivados de fichas
    REAIS do catálogo: HP, dano, custo — cada fator citado).
  - Nenhum número é inventado: todo fator vem de cards/card_attacks/
    meta_snapshots/matchups/tournament_matches ou do corpus F7 (decks).
  - Legalidade é GATE: o validador F3 roda sempre antes da nota.

Pipeline (determinístico, zero rede):
  1) resolve o deck (--deck-id | --spec arquivo.json | --name via FTS5);
  2) valida F3 (scripts/validate_deck.py) — ilegal não recebe nota nem persiste;
  3) carrega snapshot mais recente (ou --snapshot) e os top-N arquetipos por share;
  4) dimensões (10) com pesos do arquivo — cada score com motivo citável;
  5) matchups por arquetipo: análogo resolvido por nome/carta; real quando a
     F7 tem amostra, teórico quando não — sempre com selo;
  6) recomendações de troca (benefício e custo, presença real citada);
  7) persiste em deck_evaluations + evaluation_dimensions (seeds) + audit_logs,
     id determinístico eval-{deck_id}-{snapshot_id} (re-execução idempotente);
  8) relatório JSON em data/eval/reports/.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Raiz do projeto: POCKET_ROOT sobrescreve (ex.: execução fora da árvore do repo);
# default assume scripts/eval/ dentro do repo (parents[2]).
ROOT = Path(os.environ.get("POCKET_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "deck"))

import validate_deck as V3        # noqa: E402
import build_deck as B            # noqa: E402

DB_PATH = ROOT / "data" / "pocket.sqlite"
WEIGHTS_PATH = ROOT / "skills" / "pokemon-pocket-deck-evaluator" / "weights.json"
REPORTS_DIR = ROOT / "data" / "eval" / "reports"
DIM_NAMES = ["legality", "consistency", "speed", "offensive_power", "resilience",
             "energy_efficiency", "flexibility", "recovery", "combo_dependency",
             "meta_coverage"]
NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# pesos (arquivo versionado — aceitação 1)
# ---------------------------------------------------------------------------

def load_weights(path: Path | None = None) -> dict:
    p = Path(path) if path else WEIGHTS_PATH
    w = json.loads(p.read_text(encoding="utf-8"))
    dims = w["dimensions"]
    missing = [n for n in DIM_NAMES if n not in dims]
    extra = [n for n in dims if n not in DIM_NAMES]
    if missing or extra:
        raise ValueError(f"weights.json fora do contrato F9: faltando={missing} extra={extra}")
    total = sum(dims[n]["weight"] for n in DIM_NAMES)
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"pesos somam {total}, exigido 1.0")
    return w


# ---------------------------------------------------------------------------
# resolução do deck
# ---------------------------------------------------------------------------

def deck_from_db(con, deck_id: str) -> dict | None:
    row = con.execute("SELECT id, name, format, total_cards FROM decks WHERE id=?",
                      (deck_id,)).fetchone()
    if row is None:
        return None
    cards = [dict(r) for r in con.execute("""
        SELECT dc.card_id, dc.quantity, c.canonical_name, c.category, c.stage,
               c.element, c.hp, c.weakness_element, c.retreat_cost, c.special_rule, c.is_ex
        FROM deck_cards dc JOIN cards c ON c.id=dc.card_id
        WHERE dc.deck_id=? ORDER BY dc.quantity DESC, c.id""", (deck_id,))]
    spec_row = con.execute("SELECT spec_json FROM deck_specifications WHERE deck_id=?",
                           (deck_id,)).fetchone()
    spec = json.loads(spec_row["spec_json"]) if spec_row else None
    return {"id": row["id"], "name": row["name"], "format": row["format"],
            "total_cards": sum(c["quantity"] for c in cards), "cards": cards, "spec": spec}


def deck_from_spec_file(con, path: str) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [c["card_id"] for c in spec["cards"]]
    if not ids:
        raise ValueError("spec sem cartas")
    q = ",".join("?" * len(ids))
    fichas = {r["id"]: dict(r) for r in con.execute(f"""
        SELECT id, canonical_name, category, stage, element, hp, weakness_element,
               retreat_cost, special_rule, is_ex FROM cards WHERE id IN ({q})""", ids)}
    cards = []
    for c in spec["cards"]:
        f = fichas.get(c["card_id"])
        if f is None:
            raise ValueError(f"carta inexistente no catálogo: {c['card_id']}")
        f["quantity"] = c["quantity"]
        cards.append(f)
    return {"id": spec.get("deck_id") or f"spec-{spec.get('name', 'deck')}",
            "name": spec.get("name") or "deck via spec", "format": spec.get("format", "standard"),
            "total_cards": sum(c["quantity"] for c in cards), "cards": cards, "spec": spec}


def infer_main(deck: dict) -> dict:
    """Carta principal: spec.main_card; senão o Pokémon de maior quantity/HP (declarado)."""
    spec = deck.get("spec") or {}
    mc = spec.get("main_card") or {}
    if mc.get("id"):
        for c in deck["cards"]:
            if (c.get("card_id") or c.get("id")) == mc["id"]:
                return {**c, "card_id": c.get("card_id") or c.get("id"),
                        "canonical_name": c["canonical_name"], "_inferred": False}
    pokes = [c for c in deck["cards"] if c["category"] == "pokemon"]
    if not pokes:
        raise ValueError("deck sem carta Pokemon — impossivel inferir principal")
    pokes.sort(key=lambda c: (-c["quantity"], -(c["hp"] or 0)))
    return {**pokes[0], "_inferred": True}


# ---------------------------------------------------------------------------
# contexto de meta (snapshot F7) e análogos
# ---------------------------------------------------------------------------

def latest_snapshot(con, snapshot_id: str | None = None) -> dict:
    if snapshot_id:
        r = con.execute("SELECT * FROM meta_snapshots WHERE id=?", (snapshot_id,)).fetchone()
    else:
        r = con.execute("""SELECT * FROM meta_snapshots
            ORDER BY window_end DESC, tournament_count DESC LIMIT 1""").fetchone()
    if r is None:
        raise ValueError("nenhum meta_snapshots no banco — rode a F7 antes (meta_pipeline)")
    return dict(r)


def top_archetypes(con, snapshot_id: str, top_n: int) -> list[dict]:
    rows = con.execute("""
        SELECT a.id, a.name, s.share_pct, s.win_rate_pct, s.tier, s.sample_decks, s.sample_matches
        FROM meta_snapshot_archetypes s JOIN meta_archetypes a ON a.id=s.archetype_id
        WHERE s.snapshot_id=? AND s.share_pct IS NOT NULL
        ORDER BY s.share_pct DESC LIMIT ?""", (snapshot_id, top_n)).fetchall()
    return [dict(r) for r in rows]


def _pokemon_names(con) -> list[str]:
    return [r["canonical_name"] for r in con.execute(
        "SELECT DISTINCT canonical_name FROM cards WHERE category='pokemon'")]


def archetype_mains(con, arch_name: str, cache: dict) -> list[dict]:
    """Cartas principais REAIS do arquetipo: nomes canônicos de Pokémon contidos
    no nome do arquetipo (match guloso maior→menor). Ficha real, nada inventado."""
    if arch_name in cache:
        return cache[arch_name]
    remaining = arch_name.lower()
    mains = []
    for name in sorted(set(_pokemon_names(con)), key=len, reverse=True):
        nl = name.lower()
        if len(nl) >= 4 and nl in remaining:
            r = con.execute("""SELECT id, canonical_name, element, hp, weakness_element, stage
                FROM cards WHERE canonical_name=? AND category='pokemon'
                ORDER BY hp DESC LIMIT 1""", (name,)).fetchone()
            if r:
                mains.append(dict(r))
            remaining = remaining.replace(nl, " ", 1)
    cache[arch_name] = mains
    return mains


def best_attack(con, card_id: str, cache: dict) -> dict | None:
    if card_id in cache:
        return cache[card_id]
    best = None
    for r in con.execute("""SELECT name, energy_cost, damage, effect_text
            FROM card_attacks WHERE card_id=?""", (card_id,)):
        d = dict(r)
        if best is None or (d["damage"] or 0) > (best["damage"] or 0):
            best = d
    cache[card_id] = best
    return best


def find_analog(con, main: dict, snapshot_id: str) -> dict | None:
    """Arquetipo análogo do deck: contém a carta principal no nome (ou nome é
    contido); prefere com tier, depois maior amostra de jogos. Declarado na saída."""
    main_name = (main.get("canonical_name") or "").lower()
    rows = con.execute("""
        SELECT a.id, a.name, s.tier, s.sample_decks, s.sample_matches
        FROM meta_snapshot_archetypes s JOIN meta_archetypes a ON a.id=s.archetype_id
        WHERE s.snapshot_id=?""", (snapshot_id,)).fetchall()
    cands = []
    for r in rows:
        an = r["name"].lower()
        if main_name and (main_name in an or an in main_name):
            cands.append(dict(r))
    if not cands:
        return None
    cands.sort(key=lambda c: (c["tier"] not in ("", None), -(c["sample_matches"] or 0)))
    return cands[0]


def real_matchup(con, analog_id: str, opp_id: str, window_period: str) -> dict | None:
    """Matchup REAL da F7 orientado ao lado do deck (análogo), se existir."""
    r = con.execute("""SELECT win_rate_a_pct, sample_size, confidence, archetype_a, archetype_b
        FROM matchups WHERE window_period=? AND archetype_a=? AND archetype_b=?""",
        (window_period, analog_id, opp_id)).fetchone()
    if r is None:
        r = con.execute("""SELECT win_rate_a_pct, sample_size, confidence, archetype_a, archetype_b
            FROM matchups WHERE window_period=? AND archetype_a=? AND archetype_b=?""",
            (window_period, opp_id, analog_id)).fetchone()
        if r is None:
            return None
    wr = r["win_rate_a_pct"] if r["archetype_a"] == analog_id else 100.0 - r["win_rate_a_pct"]
    return {"win_rate_deck_side_pct": round(wr, 2), "sample_size": r["sample_size"],
            "confidence": r["confidence"]}


# ---------------------------------------------------------------------------
# dimensões (cada score com motivo citável; tudo de ficha/amostra REAL)
# ---------------------------------------------------------------------------

def _qty(deck_cards: list[dict], fn_name: str, functions: dict) -> int:
    return sum(c["quantity"] for c in deck_cards if functions.get(c["card_id"]) == fn_name)


def chain_len(con, card_id: str) -> int:
    n, cur, seen = 1, card_id, {card_id}
    while True:
        r = con.execute("SELECT pre_evo_card_id FROM card_evolutions WHERE card_id=?",
                        (cur,)).fetchone()
        if r is None or r["pre_evo_card_id"] in seen:
            return n
        cur = r["pre_evo_card_id"]
        seen.add(cur)
        n += 1


def evaluate_dimensions(con, deck: dict, main: dict, functions: dict,
                        presence: dict, n_decks: int, opp_ctx: dict,
                        weights: dict) -> tuple[dict, dict]:
    """Retorna ({nome: {score, weighted, reason}}, insumos para matchups)."""
    cards = deck["cards"]
    att = best_attack(con, main["card_id"], opp_ctx["atk_cache"])
    dmg = (att or {}).get("damage") or 0
    cost = json.loads((att or {}).get("energy_cost") or "[]") if att else []
    cl = chain_len(con, main["card_id"])
    candy = sum(c["quantity"] for c in cards if (c["canonical_name"] or "").lower() == "rare candy")
    wally = sum(c["quantity"] for c in cards if (c["canonical_name"] or "").lower() == "wally")
    xspeed = _qty(cards, "mobility", functions)
    eaccel = _qty(cards, "energy-accel", functions)
    draw_q = _qty(cards, "draw", functions)
    search_q = _qty(cards, "search", functions)
    heal_q = _qty(cards, "heal", functions) + _qty(cards, "protection", functions)
    prot_names = [(c["canonical_name"], c["quantity"]) for c in cards
                  if functions.get(c["card_id"]) in ("protection", "heal")]
    reserve = [c for c in cards if c["category"] == "pokemon" and c["card_id"] != main["card_id"]]
    reserve_best = max((best_attack(con, c["card_id"], opp_ctx["atk_cache"]) or {}).get("damage") or 0
                       for c in reserve) if reserve else 0
    mega_risk = "3 points" in (main.get("special_rule") or "")
    fns = sorted({f for cid, f in functions.items() if f != "main-card"})
    supporters = {c["canonical_name"] for c in cards if c["category"] == "trainer_supporter"}

    d = {}

    # legality (gate F3 — preenchido pelo chamador via opp_ctx['legality'])
    leg = opp_ctx["legality"]
    d["legality"] = {
        "score": 100.0 if leg["legal"] else 0.0,
        "reason": ("validador F3 aprovou: " + ", ".join(leg["satisfied_rules"][:6])
                   + (" ..." if len(leg["satisfied_rules"]) > 6 else ""))
                  if leg["legal"] else "violacoes F3: " + "; ".join(leg["violations"])}

    hand_engine = min(1.0, (draw_q + search_q) / 6)
    onus_raw = max(0, (cl - 1) - (candy + wally) / 2)
    onus_score = 1 - min(1.0, onus_raw / 3)
    emp_avg = (sum(presence.values()) / len(presence)) if presence else 0.0
    d["consistency"] = {
        "score": round(100 * (0.40 * hand_engine + 0.30 * onus_score + 0.30 * emp_avg), 1),
        "reason": f"motor de mao {draw_q}+{search_q} cartas (índice {hand_engine:.2f}); "
                  f"ônus de evolução cadeia={cl} com {candy}x Rare Candy + {wally}x Wally "
                  f"(índice {onus_score:.2f}); presença empírica média das picks no núcleo real "
                  f"({n_decks} listas): {100*emp_avg:.0f}%"}

    base = 1.0 if dmg >= 120 else 0.7 if dmg >= 80 else 0.4 if dmg >= 50 else (0.1 if dmg == 0 else 0.2)
    cost_f = 1.0 - 0.05 * max(0, len(cost) - 2)
    accel = (0.10 if (candy + wally) > 0 else 0.0) + (0.05 if xspeed > 0 else 0.0)
    d["speed"] = {
        "score": round(100 * min(1.0, base * cost_f + accel), 1),
        "reason": f"ataque principal {dmg} de dano (base {base:.2f}), custo de {len(cost)} energias "
                  f"(fator {cost_f:.2f}), aceleração de evolução {'sim' if (candy+wally)>0 else 'não'}"}

    opp_mains = opp_ctx["opp_mains"]  # [{arch_id, hp, ...}]
    if opp_mains:
        ohko = sum(1 for o in opp_mains if (o["hp"] or 0) and dmg >= o["hp"]) / len(opp_mains)
        ratios = [min(1.0, dmg / o["hp"]) for o in opp_mains if o["hp"]]
        ratio = sum(ratios) / len(ratios) if ratios else 0.0
        d["offensive_power"] = {
            "score": round(100 * (0.6 * ohko + 0.4 * ratio), 1),
            "reason": f"{dmg} de dano vs HP real das {len(opp_mains)} principais dos "
                      f"top-{len(opp_ctx['top'])} arquetipos por share: "
                      f"OHKO em {100*ohko:.0f}% delas, razão média de dano/HP {100*ratio:.0f}% "
                      f"(sem ponderar fraqueza — nada simulado)"}
    else:
        d["offensive_power"] = {"score": 50.0,
                                "reason": "sem HP resolvível dos top arquetipos — valor neutro TEORICO"}

    hp_score = min(1.0, (main["hp"] or 0) / 200)
    reserve_f = 1.0 if reserve_best >= 80 else 0.0
    prot_f = min(1.0, heal_q / 4)
    d["resilience"] = {
        "score": round(100 * max(0.0, 0.5 * hp_score + 0.2 * reserve_f + 0.3 * prot_f
                                 - (0.15 if mega_risk else 0.0)), 1),
        "reason": f"HP real da principal {main['hp']} (índice {hp_score:.2f}); melhor atacante de "
                  f"reserva {reserve_best} de dano; proteção/cura {heal_q} cartas "
                  f"({', '.join(f'{n} x{q}' for n, q in prot_names) or 'nenhuma'}); "
                  f"{'penalidade -15%: regra real Mega ex (oponente ganha 3 pontos)' if mega_risk else 'sem penalidade mega'}"}

    e_base = {1: 1.0, 2: 1.0, 3: 0.8, 4: 0.6}.get(len(cost), 0.4 if cost else 0.5)
    hybrid = -0.15 if len(set(cost)) > 1 else 0.0
    mob = min(0.25, 0.05 * xspeed + 0.05 * eaccel)
    d["energy_efficiency"] = {
        "score": round(100 * min(1.0, e_base + hybrid + mob), 1),
        "reason": f"custo real do ataque: {len(cost)} energia(s) (índice {e_base:.2f})"
                  + (", custo HÍBRIDO de tipos (-0.15)" if hybrid else "")
                  + (f", mobilidade/aceleração na lista (X Speed {xspeed}, energy-accel {eaccel})" if mob else "")}

    has_search = search_q > 0
    sup_f = 1.0 if len(supporters) >= 2 else (0.5 if supporters else 0.0)
    d["flexibility"] = {
        "score": round(100 * (0.5 * min(1.0, len(fns) / 6) + 0.2 * (1.0 if has_search else 0.0)
                              + 0.3 * sup_f), 1),
        "reason": f"{len(fns)} funções mecânicas distintas fora da principal "
                  f"({', '.join(fns) or 'nenhuma'}); busca {'presente' if has_search else 'ausente'}; "
                  f"{len(supporters)} Supporter distinto(s)"}

    d["recovery"] = {
        "score": round(100 * (0.5 * reserve_f + 0.25 * min(1.0, heal_q / 2)
                              + 0.25 * min(1.0, draw_q / 4)), 1),
        "reason": f"atacante de reserva com {reserve_best} de dano; cura/proteção {heal_q}; "
                  f"compra {draw_q} cartas — capacidade de reagir após perder a principal"}

    evo_score = 1.0 if cl == 1 else (0.7 if (candy + wally) >= 2 else 0.4)
    d["combo_dependency"] = {
        "score": round(100 * (0.7 * evo_score + 0.3 * (1.0 if search_q >= 2 else 0.0)), 1),
        "reason": f"ESCORE INVERTIDO (alto = baixa dependência): cadeia de {cl} peça(s) "
                  f"{'mitigada por Rare Candy/Wally' if (candy + wally) >= 2 else 'sem mitigação completa'};"
                  f" busca {'garante as peças' if search_q >= 2 else 'não garante as peças'}"}

    # meta_coverage: média ponderada por share dos scores de matchup
    per = opp_ctx["matchup_scores"]  # [{arch_id, share, score, evidence}]
    if per:
        tot = sum(p["share"] or 0 for p in per) or 1.0
        mc = sum((p["share"] or 0) * p["score"] for p in per) / tot
        n_real = sum(1 for p in per if p["evidence"] == "real")
        d["meta_coverage"] = {
            "score": round(100 * mc, 1),
            "reason": f"média ponderada por share dos matchups vs top-{len(per)}: {n_real} com "
                      f"evidência REAL da F7, {len(per)-n_real} TEÓRICOS (ficha real, sem torneio)"}
    else:
        d["meta_coverage"] = {"score": 50.0, "reason": "sem arquetipos resolvíveis — valor neutro TEORICO"}

    out = {}
    for n in DIM_NAMES:
        w = weights["dimensions"][n]["weight"]
        out[n] = {"score": d[n]["score"], "weight": w,
                  "weighted": round(d[n]["score"] * w, 2), "reason": d[n]["reason"]}
    return out, {"attack": att, "dmg": dmg, "cost": cost, "chain_len": cl,
                 "candy": candy, "wally": wally, "mega_risk": mega_risk}


# ---------------------------------------------------------------------------
# matchups (evidência real vs teórica — sempre selada)
# ---------------------------------------------------------------------------

def build_matchups(con, deck, main, opp_ctx, snapshot, ins) -> list[dict]:
    analog = find_analog(con, main, snapshot["id"])
    wp = f"{snapshot['window_start']}..{snapshot['window_end']}"  # formato da coluna matchups.window_period (F7)
    out = []
    dmg = ins["dmg"]
    for opp in opp_ctx["top"]:
        mains = archetype_mains(con, opp["name"], opp_ctx["main_cache"])
        their_best = 0
        for m in mains:
            a = best_attack(con, m["id"], opp_ctx["atk_cache"])
            their_best = max(their_best, (a or {}).get("damage") or 0)
        entry = {"archetype_id": opp["id"], "archetype_name": opp["name"],
                 "tier": opp["tier"], "share_pct": opp["share_pct"],
                 "win_rate_meta_pct": opp["win_rate_pct"],
                 "sample_decks": opp["sample_decks"],
                 "opponent_mains": [m["canonical_name"] for m in mains],
                 "strengths": [], "weaknesses": [], "decisive_cards": [],
                 "win_condition": "", "evidence": None, "score": None}

        my_hp = main["hp"] or 0
        if mains and my_hp and dmg:
            ohko = [m for m in mains if (m["hp"] or 0) and dmg >= m["hp"]]
            if ohko:
                entry["strengths"].append(
                    f"o ataque da principal ({dmg} de dano) derruba {', '.join(m['canonical_name'] for m in ohko)}"
                    f" (HP {', '.join(str(m['hp']) for m in ohko)}) em um ataque")
            fails = [m for m in mains if (m["hp"] or 0) and dmg < m["hp"]]
            if fails:
                entry["weaknesses"].append(
                    f"{dmg} de dano NÃO derruba {', '.join(m['canonical_name'] for m in fails)}"
                    f" (HP {', '.join(str(m['hp']) for m in fails)}) em um ataque")
            survives = [m for m in mains if (m["hp"] or 0) and my_hp > their_best]
            if not survives and their_best:
                entry["weaknesses"].append(
                    f"a principal adversária devolve até {their_best} de dano e a nossa "
                    f"({my_hp} HP) não sobrevive — é preciso atacar primeiro")
            for m in mains:
                if m["weakness_element"] and m["weakness_element"] == main.get("element"):
                    entry["strengths"].append(
                        f"fraqueza real de {m['canonical_name']} é {m['weakness_element']} — "
                        f"mesmo elemento da nossa principal (bandeira; o formato Pocket soma dano fixo, não simulado)")
                if main.get("weakness_element") and main["weakness_element"] == m.get("element"):
                    entry["weaknesses"].append(
                        f"nossa principal tem fraqueza {main['weakness_element']} e {m['canonical_name']} "
                        f"é {m['element']} (bandeira; dano fixo, não simulado)")
        # cartas decisivas do deck neste confronto (função real + efeito real)
        dec = [{"name": main["canonical_name"], "why": f"ataque principal {dmg} de dano (ficha real)"}]
        for c in deck["cards"]:
            fn = opp_ctx["functions"].get(c["card_id"])
            if fn in ("evolution", "control", "protection") and c["card_id"] != main["card_id"]:
                dec.append({"name": c["canonical_name"],
                            "why": f"função {fn} na lista (presença real no corpus citada na lista do deck)"})
        entry["decisive_cards"] = dec[:4]
        if ins["mega_risk"]:
            entry["weaknesses"].append("regra real Mega Evolution ex: o oponente ganha 3 pontos "
                                       "quando a principal é nocauteada — cada troca custa caro")
        entry["win_condition"] = (
            f"pressão de dano com {main['canonical_name']} ({dmg}/turno)"
            + (" + trava de Trainer (efeito real do ataque)" if "trainer" in ((ins["attack"] or {}).get("effect_text") or "").lower() else "")
            + (" com suporte de controle na lista" if any(opp_ctx["functions"].get(c["card_id"]) == "control" for c in deck["cards"]) else ""))

        # evidência
        rm = real_matchup(con, analog["id"], opp["id"], wp) if analog else None
        if rm:
            score = min(1.0, max(0.0, (rm["win_rate_deck_side_pct"] - 40) / 20))
            entry["evidence"] = {"kind": "real", "analog_archetype_id": analog["id"],
                                 "analog_name": analog["name"],
                                 "analog_tier": analog.get("tier") or "sem_evidencia",
                                 "win_rate_deck_side_pct": rm["win_rate_deck_side_pct"],
                                 "sample_size": rm["sample_size"],
                                 "confidence": rm["confidence"],
                                 "source": "tabela matchups da F7 (tournament_matches)"}
            entry["strengths"].append(f"amostra REAL: {rm['sample_size']} jogos, "
                                      f"{rm['win_rate_deck_side_pct']}% para o lado do deck ({rm['confidence']})")
        else:
            ohko_r = (sum(1 for m in mains if (m["hp"] or 0) and dmg >= m["hp"]) / len(mains)) if mains and dmg else 0.0
            surv_r = (sum(1 for m in mains if (m["hp"] or 0) and my_hp > ((best_attack(con, m["id"], opp_ctx["atk_cache"]) or {}).get("damage") or 0)) / len(mains)) if mains and my_hp else 0.5
            teo = min(1.0, max(0.0, 0.5 + 0.5 * (ohko_r - surv_r)))
            score = teo
            entry["evidence"] = {
                "kind": "teorico",
                "factors": [
                    {"factor": "OHKO da nossa principal vs HP das principais adversárias",
                     "value": f"{100*ohko_r:.0f}%"},
                    {"factor": "sobrevivência da nossa principal vs melhor dano adversário",
                     "value": f"{100*surv_r:.0f}%"},
                    {"factor": "fonte dos números", "value": "fichas reais (cards/card_attacks); SEM amostra de torneio para este par"}],
                "note": "estimativa TEÓRICA derivada de fichas reais — NÃO é resultado de torneio"}
        entry["score"] = round(score, 3)
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# trocas recomendadas (benefício e custo, presença real citada)
# ---------------------------------------------------------------------------

def swap_recommendations(con, deck, main, functions, presence, n_decks, tally) -> list[dict]:
    in_deck = {c["card_id"] for c in deck["cards"]}
    cands = []
    for cid, (nd, tot) in sorted(tally.items(), key=lambda kv: (-kv[1][0], -kv[1][1])):
        if cid in in_deck or nd < max(3, int(0.2 * n_decks)):
            continue
        r = con.execute("""SELECT id, canonical_name, category FROM cards WHERE id=?""", (cid,)).fetchone()
        if r is None or r["category"] not in ("trainer_item", "trainer_supporter", "pokemon_tool"):
            continue
        card = dict(r)
        fn, why = B.mechanical_function(card, B.main_text(con, card))
        if fn in ("support", "utility", "stadium"):
            continue
        # candidato de saída: menor presença empírica da MESMA classe de carta
        same_class = [c for c in deck["cards"]
                      if c["category"] == card["category"] and c["card_id"] != main["card_id"]]
        if not same_class:
            continue
        out_c = min(same_class, key=lambda c: presence.get(c["card_id"], 0))
        if presence.get(cid, 0) <= presence.get(out_c["card_id"], 0):
            continue
        cands.append({
            "remove": {"card_id": out_c["card_id"], "name": out_c["canonical_name"],
                       "quantity": out_c["quantity"],
                       "presence": f"{presence.get(out_c['card_id'], 0)*100:.0f}% do núcleo real"},
            "include": {"card_id": cid, "name": card["canonical_name"], "function": fn,
                        "presence": f"{nd}/{n_decks} listas reais com a principal"},
            "benefit": f"ganha {fn}: {why} (presente em {nd}/{n_decks} listas reais com {main['canonical_name']})",
            "cost": f"perde {out_c['canonical_name']} (presença de {presence.get(out_c['card_id'], 0)*100:.0f}% "
                    f"no núcleo real) — a lista continua com {deck['total_cards']} cartas e 2 cópias no máximo",
            "why_benefit_first": "presença empírica maior no mesmo núcleo = consenso maior de quem jogou a principal"})
        if len(cands) >= 3:
            break
    return cands


# ---------------------------------------------------------------------------
# pipeline principal
# ---------------------------------------------------------------------------

def open_eval_db(db_path: Path | None, *, persist: bool) -> sqlite3.Connection:
    """Abertura do banco pelo evaluate() — BUG-002 (F15+, card t_91d448dd).

    Contrato (docs/TESTING.md secao 4): NENHUM teste escreve no banco canonico.
    Duas propriedades vigiadas aqui:
    1. fail-fast: banco ausente levanta RuntimeError SEM criar o arquivo
       (sqlite3.connect() comum CRIA arquivo vazio — defeito observado em
       checkout cru durante o aceite BUG-001, setUpClass do test_f9);
    2. escrita controlada: persist=True em banco DIFERENTE do canonico segue
       livre (copia efemera do fixture da suite, banco de homologacao). Ja
       persist=True no CAMINHO CANONICO fica RECUSADO por default com
       RuntimeError ANTES de tocar o arquivo — a suite esquecida de novo nao
       polui audit_logs de producao nunca mais. Agregador/operador ABORDANDO
       producao deliberadamente seta BUG002_ALLOW_PERSIST=1 no ambiente.
    """
    p = Path(db_path or DB_PATH)
    if not p.is_file():
        raise RuntimeError(
            f"banco ausente: {p} — evaluate() NUNCA cria o arquivo (BUG-002, F15+). "
            "Em checkout cru rode scripts/collect_pocket.py FORA da suite; "
            "docs/TESTING.md secao 4.")
    canonical = p.resolve() == DB_PATH.resolve()
    if persist and canonical:
        import os
        if os.environ.get("BUG002_ALLOW_PERSIST") != "1":
            raise RuntimeError(
                "persist=True no banco CANONICO (data/pocket.sqlite) e recusado "
                "por BUG-002 (F15+, t_91d448dd): nenhuma execucao automatica "
                "escreve em producao. Escreva numa COPIA (padrao backup API, "
                "docs/TESTING.md secao 4) — ou sete BUG002_ALLOW_PERSIST=1 se "
                "voce e o operador humano com intencao deliberada.")
    if persist and not canonical:
        con = sqlite3.connect(str(p))          # copia efemera: writable de verdade
    else:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)  # leitura pura
    con.row_factory = sqlite3.Row
    return con


def evaluate(deck_ref: dict, snapshot_id: str | None = None, top_n: int = 12,
             days: int = 30, db_path: Path | None = None,
             weights_path: Path | None = None, persist: bool = True,
             out_path: Path | None = None) -> tuple[dict, int]:
    con = open_eval_db(db_path, persist=persist)
    try:
        weights = load_weights(weights_path)
        if deck_ref.get("spec_file"):
            deck = deck_from_spec_file(con, deck_ref["spec_file"])
        else:
            deck = deck_from_db(con, deck_ref["deck_id"])
        if deck is None:
            return {"veredicto": "deck_inexistente", "query": deck_ref}, 2

        try:
            main = infer_main(deck)
        except ValueError as e:
            return {"veredicto": "inconsistente",
                    "deck": {"id": deck["id"], "name": deck["name"]},
                    "reason": str(e),
                    "note": "nenhuma nota atribuida; nada persistido"}, 3
        payload = {"id": deck["id"], "name": deck["name"], "format": deck["format"],
                   "cards": [{"card_id": c.get("card_id") or c.get("id"), "quantity": c["quantity"]}
                             for c in deck["cards"]]}
        verdict = V3.validate_deck(payload, B.catalog_projection(con))
        legality = {"legal": verdict["legality"] == "legal",
                    "violations": verdict.get("violations", []),
                    "satisfied_rules": verdict.get("satisfied_rules", [])}
        if not legality["legal"]:
            rep = {"veredicto": "ilegal", "deck_id": deck["id"], "main_card": main["canonical_name"],
                   "legality": legality,
                   "note": "deck ilegal NÃO recebe nota nem é persistido (gate F3)"}
            if persist:
                con.execute("""INSERT INTO audit_logs (actor, table_name, record_key, action, reason)
                    VALUES (?,?,?,?,?)""",
                    ("tony_stark:f9", "deck_evaluations", f"recusa:{deck['id']}", "insert",
                     "avaliacao recusada: deck ilegal (gate F3); nenhuma nota atribuida"))
                con.commit()
            return rep, 4

        snapshot = latest_snapshot(con, snapshot_id)
        top = top_archetypes(con, snapshot["id"], top_n)

        # funções mecânicas (F8) + presença empírica no núcleo real
        functions = {}
        for c in deck["cards"]:
            fn, _ = B.mechanical_function({**c, "id": c["card_id"]}, B.main_text(con, {**c, "id": c["card_id"]}))
            functions[c["card_id"]] = fn
        n_lists, tally = B.empirical_nucleus(con, main["card_id"], days)
        presence = {c["card_id"]: (tally.get(c["card_id"], (0, 0))[0] / n_lists if n_lists else 0.0)
                    for c in deck["cards"]}

        opp_mains, main_cache, atk_cache = [], {}, {}
        for opp in top:
            for m in archetype_mains(con, opp["name"], main_cache):
                opp_mains.append({**m, "arch_id": opp["id"]})

        opp_ctx = {"top": top, "opp_mains": opp_mains, "main_cache": main_cache,
                   "atk_cache": atk_cache, "legality": legality, "functions": functions}

        # primeira passada: insumos (ataque etc.) para build_matchups
        dims_probe, ins = evaluate_dimensions(con, deck, main, functions, presence,
                                              n_lists, {**opp_ctx, "matchup_scores": []}, weights)
        matchups = build_matchups(con, deck, main, opp_ctx, snapshot, ins)
        opp_ctx["matchup_scores"] = [{"share": m["share_pct"], "score": m["score"],
                                      "evidence": m["evidence"]["kind"]} for m in matchups]
        dims, ins = evaluate_dimensions(con, deck, main, functions, presence,
                                        n_lists, opp_ctx, weights)
        overall = round(sum(dims[n]["weighted"] for n in DIM_NAMES), 1)

        n_real = sum(1 for m in matchups if m["evidence"]["kind"] == "real")
        confs = [m["evidence"]["confidence"] for m in matchups if m["evidence"]["kind"] == "real"]
        if n_real == 0:
            confidence = "theoretical"
        elif n_real < len(matchups) or (confs and min(confs) == "low"):
            confidence = "low"
        elif confs and min(confs) == "high":
            confidence = "high"
        else:
            confidence = "medium"

        analog = find_analog(con, main, snapshot["id"])
        swaps = swap_recommendations(con, deck, main, functions, presence, n_lists, tally)

        closest = None
        if analog:
            r = con.execute("""
                SELECT s.win_rate_pct, s.tier FROM meta_snapshot_archetypes s
                WHERE s.snapshot_id=? AND s.archetype_id=?""",
                (snapshot["id"], analog["id"])).fetchone()
            closest = {"analog_archetype_id": analog["id"], "analog_name": analog["name"],
                       "tier": (r["tier"] if r and r["tier"] else "sem_evidencia"),
                       "win_rate_pct": r["win_rate_pct"] if r else None,
                       "note": "arquetipo do meta real que compartilha a carta principal — "
                               "win_rate é do ARQUETIPO em torneio, não do deck avaliado"}

        disclaimers = [
            "A nota 0-100 é QUALIDADE HEURÍSTICA (score_type=heuristic_quality_NOT_winrate); "
            "NÃO é winrate, NÃO é previsão de resultado de torneio e não tem precisão estatística.",
            "Matchups marcados kind=teorico derivam de fichas reais do catálogo SEM amostra de "
            "torneio para o par — nunca apresentar como resultado de torneio.",
            "Modelo v1 incompleto: dimensões com pesos documentados em weights.json (versão "
            f"{weights['version']}); mudou o arquivo, muda a nota — cite a versão.",
        ]

        report = {
            "veredicto": "avaliado",
            "deck": {"id": deck["id"], "name": deck["name"], "total_cards": deck["total_cards"],
                     "main_card": main["canonical_name"], "main_card_id": main["card_id"],
                     "main_inferred": bool(main.get("_inferred")),
                     "cards": [{"card_id": c["card_id"], "name": c["canonical_name"],
                                "quantity": c["quantity"], "function": functions[c["card_id"]],
                                "presence_in_real_core": f"{presence[c['card_id']]*100:.0f}%"}
                               for c in deck["cards"]]},
            "legality": legality,
            "score": {"overall": overall, "scale": "0-100",
                      "score_type": weights["score_type"],
                      "weights_file": str(weights_path or WEIGHTS_PATH),
                      "weights_version": weights["version"],
                      "dimensions": [dict(name=n, **{k: v for k, v in dims[n].items()})
                                     for n in DIM_NAMES]},
            "meta": {"snapshot_id": snapshot["id"], "window": snapshot["window_period"]
                     if "window_period" in snapshot else f"{snapshot['window_start']}..{snapshot['window_end']}",
                     "tournament_count": snapshot["tournament_count"],
                     "decklist_count": snapshot["decklist_count"],
                     "match_count": snapshot["match_count"],
                     "top_n": top_n,
                     "empirical_window_days": days,
                     "empirical_lists_with_main": n_lists},
            "matchups": matchups,
            "swap_recommendations": swaps,
            "comparison": {"closest_meta_archetype": closest,
                           "shared_main_with_meta": bool(analog),
                           "positioning": (
                               f"nota heurística {overall}/100 vs win_rate de torneio do análogo "
                               f"({closest['win_rate_pct']}%, tier {closest['tier']}) — NÚMEROS "
                               "NÃO COMPARÁVEIS por natureza (heurística de qualidade ≠ winrate); "
                               "o posicionamento honesto é o análogo + tier, não a nota"),
                           "shared_mains_top12": [
                               {"archetype_id": o["id"], "shared": [m["canonical_name"]
                                    for m in archetype_mains(con, o["name"], main_cache)
                                    if m["canonical_name"] in {c["canonical_name"] for c in deck["cards"]}]}
                               for o in top[:12]]},
            "evidence": {"matchups_real": n_real, "matchups_teorico": len(matchups) - n_real,
                         "empirical_corpus": {"lists_with_main": n_lists,
                                              "window_note": "janela sobre collected_at do corpus "
                                                  "F7 (ingestão 2026-10-19); torneios 2026-09-09..2026-10-18"},
                         "confidence": confidence},
            "disclaimers": disclaimers,
            "generated_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sources": [
                {"id": "play.limitlesstcg.com", "role": "corpus de decklists e matchups de torneio (F7)"},
                {"id": "scripts/validate_deck.py", "role": "gate de legalidade F3"},
                {"id": "skills/pokemon-pocket-deck-evaluator/weights.json",
                 "role": f"pesos das dimensões ({weights['version']})"}],
        }

        if persist:
            pid = persist_evaluation(con, deck, snapshot, report, weights)
            report["persistence"] = {"deck_evaluation_id": pid, "table": "deck_evaluations",
                                     "evaluation_dimensions_seeded": len(DIM_NAMES)}

        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                encoding="utf-8")
            report.setdefault("report_file", str(out_path))
        return report, 0
    finally:
        con.close()


def persist_evaluation(con, deck: dict, snapshot: dict, report: dict, weights: dict) -> str:
    """Idempotente: id determinístico eval-{deck_id}-{snapshot_id}; upsert não-destrutivo."""
    for n in DIM_NAMES:
        con.execute("""INSERT INTO evaluation_dimensions (name, default_weight, description)
            VALUES (?,?,?)
            ON CONFLICT(name) DO UPDATE SET default_weight=excluded.default_weight""",
            (n, weights["dimensions"][n]["weight"], weights["dimensions"][n]["description"]))
    pid = f"eval-{deck['id']}-{snapshot['id']}"
    dims_json = json.dumps(report["score"]["dimensions"], ensure_ascii=False)
    overall10 = round(report["score"]["overall"] / 10.0, 2)
    conf = report["evidence"]["confidence"]
    weights_doc = f"{report['score']['weights_file']}@{report['score']['weights_version']}"
    exists = con.execute("SELECT 1 FROM deck_evaluations WHERE id=?", (pid,)).fetchone()
    action = "update" if exists else "insert"
    if exists:
        con.execute("""UPDATE deck_evaluations SET overall_score=?, dimensions=?, weights_doc=?,
            confidence=?, generated_at=? WHERE id=?""",
            (overall10, dims_json, weights_doc, conf,
             NOW.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z", pid))
    else:
        con.execute("""INSERT INTO deck_evaluations (id, deck_id, overall_score, dimensions,
            weights_doc, confidence) VALUES (?,?,?,?,?,?)""",
            (pid, deck["id"], overall10, dims_json, weights_doc, conf))
    con.execute("""INSERT INTO audit_logs (actor, table_name, record_key, action, before_json, after_json, reason)
        VALUES (?,?,?,?,?,?,?)""",
        ("tony_stark:f9", "deck_evaluations", pid, action, None,
         json.dumps({"deck_id": deck["id"], "overall_score": overall10,
                     "confidence": conf, "weights_doc": weights_doc,
                     "snapshot_id": snapshot["id"]}, ensure_ascii=False),
         "F9 deck-evaluator: avaliação heurística reprodutível (pesos em weights.json); "
         "nota NÃO é winrate"))
    con.commit()
    return pid


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="F9 deck-evaluator (nota heurística + matchups)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--deck-id", help="deck_id do banco (ex.: deck-mega-gengar-ex-001)")
    g.add_argument("--spec", help="arquivo JSON de especificação do deck")
    g.add_argument("--name", help="nome FTS5 de carta principal (usa o deck F8 dela)")
    ap.add_argument("--snapshot", default=None, help="meta_snapshots.id (default: mais recente)")
    ap.add_argument("--top", type=int, default=12, help="arquetipos do meta (default 12)")
    ap.add_argument("--days", type=int, default=30, help="janela empírica (default 30)")
    ap.add_argument("--weights", default=None,
                    help="caminho alternativo do weights.json (default: skills/pokemon-pocket-deck-evaluator/weights.json)")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--out", default=None, help="arquivo de relatório JSON")
    ap.add_argument("--no-persist", action="store_true")
    args = ap.parse_args(argv)

    deck_ref = {}
    if args.deck_id:
        deck_ref = {"deck_id": args.deck_id}
    elif args.spec:
        deck_ref = {"spec_file": args.spec}
    else:
        con = sqlite3.connect(args.db)
        con.row_factory = sqlite3.Row
        m = B.resolve_main(con, args.name)
        con.close()
        if m is None:
            print(json.dumps({"veredicto": "carta_inexistente", "query": args.name},
                             ensure_ascii=False, indent=2))
            return 2
        deck_ref = {"deck_id": f"deck-{_slug(m['canonical_name'])}-001"}

    out_path = Path(args.out) if args.out else None
    report, rc = evaluate(deck_ref, snapshot_id=args.snapshot, top_n=args.top,
                          days=args.days, db_path=Path(args.db), persist=not args.no_persist,
                          out_path=out_path,
                          weights_path=Path(args.weights) if args.weights else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return rc


def _slug(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", (name or "main").lower()).strip("-")


if __name__ == "__main__":
    sys.exit(main())
