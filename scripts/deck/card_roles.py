#!/usr/bin/env python3
"""UX-1 (card t_bd7c1cc1): papeis de carta e relatorio humano do deck-builder.

Anti-invencao por design — nenhum texto aqui e escrito de proposito livre:
  curated      : data/card_roles.yaml (tabela versionada; cada entrada cita o
                 print e o texto real do cache F4 como evidencia) — para
                 treinadores/ferramentas/estadios, que tem ZERO texto no
                 catalogo (card_localizations vazio);
  derived_text : effect_text REAL de card_attacks/card_abilities mapeado por
                 palavras-chave de um vocabulario FECHADO (ROLE_DEFS); a
                 evidencia (trecho casado) viaja na saida;
  neutral      : rotulo honesto do vocabulario fechado quando nada casa
                 (ex.: "Atacante de dano direto" ancorado no dano real da
                 ficha; "Sem efeito de texto no catalogo").

Guarda anti-fabricacao (vigia test_ux1_deck_output.py): papel derivado exige
evidence que existe no texto de origem; rotulos saem SOMENTE do vocabulario
fechado; entrada curada carrega text_evidence conferido contra o cache F4.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES_YAML = ROOT / "data" / "card_roles.yaml"

# ---------------------------------------------------------------------------
# Vocabulario FECHADO de rotulos (unico lugar de onde sai rotulo derivado)
# ---------------------------------------------------------------------------
ROLE_DEFS = {
    "main_attacker": "Atacante principal",
    "attacker_scale_bench": "Atacante que escala com banco cheio",
    "bench_spread": "Dano ao banco adversário",
    "sleep_control": "Controle por sono",
    "lock_trainer": "Trava os Trainer adversários",
    "energy_burst": "Disrupção atrelada ao anexo de energia",
    "retreat_switch": "Mobilidade por ataque",
    "attacker": "Atacante de dano direto",
    "no_text": "Sem efeito de texto no catálogo",
    "draw": "Compra de cartas",
    "search": "Busca no deck",
    "control": "Pressão de troca e captura",
    "heal": "Cura",
    "protection": "Proteção",
    "mobility": "Mobilidade",
    "evolution": "Acelera a evolução",
    "energy_accel": "Aceleração de energia",
    "meta_response": "Resposta ao meta",
    "support": "Suporte",
    "stadium": "Estádio de apoio",
}
UNCATALOGED_LABEL = "Papel não catalogado"

# (role_id, padroes no effect_text REAL, case-insensitive). Primeiro casamento
# vence; a evidencia emitida e o trecho casado (provavelmente contido no texto).
POKEMON_TEXT_RULES = [
    ("lock_trainer", (r"can't play any trainer",)),
    ("attacker_scale_bench", (r"more damage for each of your benched",)),
    ("bench_spread", (r"does \d+ damage to \d+ of your opponent's benched",)),
    ("energy_burst", (r"whenever you attach .{0,60}energy.{0,60}do \d+ damage",)),
    ("sleep_control", (r"is now asleep",)),
    ("retreat_switch", (r"switch this pok[eé]mon with",)),
    ("draw", (r"draw (cards|\d+|a card)",)),
    ("heal", (r"heals? \d+ damage",)),
    ("search", (r"(search|look at).{0,40}deck",)),
]

ELEMENT_PT = {"grass": "Grama", "fire": "Fogo", "water": "Água", "lightning": "Elétrico",
              "psychic": "Psíquico", "fighting": "Luta", "darkness": "Escuridão",
              "metal": "Metal", "dragon": "Dragão", "colorless": "Incolor"}


# ---------------------------------------------------------------------------
# tabela curada (parser minimo — PyYAML NAO e dependencia do projeto)
# ---------------------------------------------------------------------------
def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def load_card_roles(path=None) -> dict:
    """Carrega data/card_roles.yaml (secao roles:) -> {nome_lower: entrada}.

    Parser minimo intencional: o arquivo usa apenas listas de mapas com chaves
    de uma linha e valores escalares entre aspas — sem ancoragem em YAML
    externo (sem dependencia nova; prove-se nos testes).
    """
    p = Path(path or ROLES_YAML)
    entries = []
    in_roles = False
    cur = None
    for raw in p.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw.rstrip() == "roles:":
            in_roles, cur = True, None
            continue
        if not in_roles:
            continue
        if raw.startswith("  - "):
            cur = {}
            entries.append(cur)
            body = raw[4:].strip()
        elif raw.startswith("    ") and cur is not None:
            body = stripped
        else:
            continue
        k, _, v = body.partition(":")
        cur[k.strip()] = _unquote(v)
    out = {}
    for e in entries:
        if e.get("name"):
            out[e["name"].lower()] = e
    return out


# ---------------------------------------------------------------------------
# consulta local a ficha real (sem importar build_deck — evita ciclo)
# ---------------------------------------------------------------------------
def _pokemon_text(con: sqlite3.Connection, card_id: str) -> str:
    parts = []
    for r in con.execute("SELECT effect_text FROM card_attacks WHERE card_id=?", (card_id,)):
        if r["effect_text"]:
            parts.append(r["effect_text"])
    for r in con.execute("SELECT effect_text FROM card_abilities WHERE card_id=?", (card_id,)):
        if r["effect_text"]:
            parts.append(r["effect_text"])
    return " / ".join(parts)


def _best_attack(con: sqlite3.Connection, card_id: str):
    best = None
    for r in con.execute("""SELECT name, energy_cost, damage, effect_text
            FROM card_attacks WHERE card_id=? ORDER BY sort_order""", (card_id,)):
        d = dict(r)
        if best is None or (d["damage"] or 0) > (best["damage"] or 0):
            best = d
    return best


# ---------------------------------------------------------------------------
# derivacao do papel de UMA carta
# ---------------------------------------------------------------------------
def derive_role(con: sqlite3.Connection, card: dict, curated: dict | None = None,
                is_main: bool = False) -> dict:
    """Papel de uma carta a partir de fonte real; nunca de proposito livre.

    Retorna dict(role_id, role, origin, evidence, source) com origin em
    {curated, derived_text, neutral, uncataloged}.
    """
    name = card.get("canonical_name") or ""
    cat = card.get("category") or ""

    if cat != "pokemon":
        ent = (curated or {}).get(name.lower())
        if ent:
            return {"role_id": ent.get("role_id") or "support",
                    "role": ent.get("role") or ROLE_DEFS.get(ent.get("role_id"), UNCATALOGED_LABEL),
                    "origin": "curated",
                    "evidence": ent.get("text_evidence") or "",
                    "source": f"card_roles.yaml (print {ent.get('set_code', '?')}/{ent.get('number', '?')}, cache F4)"}
        return {"role_id": "uncataloged", "role": UNCATALOGED_LABEL,
                "origin": "uncataloged", "evidence": "",
                "source": "sem entrada em card_roles.yaml e sem texto no catálogo"}

    if is_main:
        att = _best_attack(con, card["id"])
        ev = f"ataque {att['name']} (dano {att['damage']}, custo {att['energy_cost']})" if att else "carta principal pedida"
        return {"role_id": "main_attacker", "role": ROLE_DEFS["main_attacker"],
                "origin": "derived_text", "evidence": ev,
                "source": "card_attacks (ficha real)"}

    text = _pokemon_text(con, card["id"])
    if text:
        for role_id, patterns in POKEMON_TEXT_RULES:
            for pat in patterns:
                m = re.search(pat, text, re.I)
                if m:
                    return {"role_id": role_id, "role": ROLE_DEFS[role_id],
                            "origin": "derived_text", "evidence": m.group(0),
                            "source": "effect_text real (card_attacks/card_abilities)"}
    att = _best_attack(con, card["id"])
    if att and att["damage"]:
        return {"role_id": "attacker", "role": ROLE_DEFS["attacker"],
                "origin": "neutral",
                "evidence": f"damage {att['damage']} (card_attacks)",
                "source": "card_attacks (ficha real, sem efeito de texto)"}
    return {"role_id": "no_text", "role": ROLE_DEFS["no_text"],
            "origin": "neutral", "evidence": "",
            "source": "ficha real sem efeito de texto"}


# ---------------------------------------------------------------------------
# saida: uma linha por carta + "como funciona"
# ---------------------------------------------------------------------------
def _pick_names(con, picks) -> dict:
    out = {}
    for p in picks:
        r = con.execute("SELECT canonical_name FROM cards WHERE id=?",
                        (p["card_id"],)).fetchone()
        if r:
            out[p["card_id"]] = r["canonical_name"]
    return out


def deck_lines(con: sqlite3.Connection, main: dict, picks: list, curated: dict | None = None) -> list:
    """Uma entrada por carta distinta, com papel e linha humana alinhada."""
    names = _pick_names(con, picks)
    deck_names = set(names.values())
    evo = {r["card_id"]: r["pre_evo_card_id"] for r in con.execute(
        "SELECT card_id, pre_evo_card_id FROM card_evolutions")}

    raw = []
    for p in picks:
        card = dict(con.execute("""SELECT id, canonical_name, category, element, stage, hp, is_ex
            FROM cards WHERE id=?""", (p["card_id"],)).fetchone())
        role = derive_role(con, card, curated, is_main=(card["id"] == main["id"]))
        left = f"{p['quantity']}x {card['canonical_name']}"
        if card["category"] == "pokemon" and card["id"] == main["id"]:
            left += f" ({card['element']}, {card['hp']} HP, {card['stage']})"
        suffix = ""
        if card["category"] == "pokemon":
            pre_id = evo.get(card["id"])
            if pre_id:
                pre_row = con.execute("SELECT canonical_name FROM cards WHERE id=?",
                                      (pre_id,)).fetchone()
                if pre_row and pre_row["canonical_name"] in deck_names:
                    suffix = f"; evolui de {pre_row['canonical_name']}"
        raw.append({"card_id": p["card_id"], "name": card["canonical_name"],
                    "quantity": p["quantity"], "role_id": role["role_id"],
                    "role": role["role"], "role_origin": role["origin"],
                    "role_evidence": role["evidence"], "source": role["source"],
                    "_left": left, "_suffix": suffix})

    width = max((len(r["_left"]) for r in raw), default=0)
    for r in raw:
        r["human_line"] = f"{r['_left']:<{width}} — {r['role']}{r['_suffix']}"
        del r["_left"], r["_suffix"]
    return raw


def how_it_works(con: sqlite3.Connection, main: dict, picks: list, n_decks: int,
                 curated: dict | None = None) -> str:
    """2-4 linhas geradas do que o deck REALMENTE contem (nunca guia fixa)."""
    names = _pick_names(con, picks)
    deck_names = set(names.values())

    # linha 1 — abertura pela linha de evolucao REALMENTE presente no deck
    parts = []
    pre_row = con.execute("""SELECT c.canonical_name FROM card_evolutions e
        JOIN cards c ON c.id=e.pre_evo_card_id WHERE e.card_id=?""",
                          (main["id"],)).fetchone()
    pre_name = pre_row["canonical_name"] if pre_row else None
    if pre_name and pre_name in deck_names:
        # anti-fantasma: "via Rare Candy" so quando Rare Candy esta na lista
        has_candy = any(n.lower() == "rare candy" for n in deck_names)
        parts.append(f"Abra com {pre_name} no ativo e evolua para "
                     f"{main['canonical_name']} (turno 2+"
                     + (" ou via Rare Candy)" if has_candy else ")"))
    else:
        parts.append(f"Abra com {main['canonical_name']} no ativo")
    att = _best_attack(con, main["id"])
    if att and att["effect_text"] and re.search(
            r"(\d+) more damage for each of your benched", att["effect_text"], re.I):
        bonus = re.search(r"(\d+) more damage for each of your benched",
                          att["effect_text"], re.I).group(1)
        parts.append(f"o ataque {att['name']} ganha +{bonus} por Pokémon no seu banco"
                     " — encha o banco antes de atacar")
    lines = ["; ".join(parts) + f" — núcleo calibrado em {n_decks} lista(s) real(is) do corpus."]

    # linhas 2-3 — motores e apoio, agrupados pelo papel declarado das cartas
    cur = curated if curated is not None else load_card_roles()
    groups = {"engine": [], "support": []}
    engine_ids = {"draw", "search", "evolution", "energy_accel"}
    for cid, cname in names.items():
        if cid == main["id"]:
            continue
        card = dict(con.execute("SELECT id, canonical_name, category FROM cards WHERE id=?",
                                (cid,)).fetchone())
        role = derive_role(con, card, cur)
        if role["origin"] == "uncataloged":
            continue
        bucket = "engine" if role["role_id"] in engine_ids else "support"
        groups[bucket].append(f"{cname} — {role['role']}")
    if groups["engine"]:
        lines.append("Motor de cartas: " + "; ".join(groups["engine"]) + ".")
    if groups["support"]:
        lines.append("Apoio: " + "; ".join(groups["support"]) + ".")

    # linha 4 — plano de energia do ataque real da principal
    if att:
        costs = [ELEMENT_PT.get(e, e) for e in json_loads(att["energy_cost"] or "[]")]
        lines.append(f"Energia: {att['name']} pede "
                     f"{', '.join(costs) if costs else 'nenhuma'} — commit por partida; "
                     "energia não entra na lista de 20.")
    return "\n".join(lines[:4])


def json_loads(s: str):
    import json
    return json.loads(s)


def human_report(con: sqlite3.Connection, main: dict, picks: list, n_decks: int,
                 deck_id: str, deck_name: str, curated: dict | None = None) -> str:
    """Bloco humano completo: uma linha por carta + como funciona."""
    lines = deck_lines(con, main, picks, curated)
    hiw = how_it_works(con, main, picks, n_decks, curated)
    out = [f"=== {deck_id} · {deck_name} ==="]
    out += [l["human_line"] for l in lines]
    out.append("-- como funciona --")
    out.append(hiw)
    return "\n".join(out)
