#!/usr/bin/env python3
"""Validador de legalidade de decks do Pokemon TCG Pocket (skill pokemon-pocket-rules).

Uso:
    python3 scripts/validate_deck.py <deck.json> --catalog <catalog.json>

Catalogo: ate a Fase 4, use apenas a fixture (`tests/fixtures/catalog_fixture.json`).
Regras citadas: registry em skills/pokemon-pocket-rules/references/RULES.md (IDs DECK-001..REST-001).

Veredicto JSON:
    {
      "deck_id": "...",
      "legality": "legal" | "illegal",
      "violations": [{"rule_id": "DECK-001", "message": "..."}],
      "satisfied_rules": ["DECK-001", ...]   # nenhum deck legal sem citar as regras que o permitem
    }
"""

import argparse
import json
import sys
from collections import Counter

# Registry de regras aplicadas por este validador (fonte: references/RULES.md)
RULE_IDS = {
    "DECK-001": "deck_size_20",
    "DECK-002": "copies_max_2",
    "DECK-003": "card_exists",
    "DECK-004": "format_legality",
    "EVOL-001": "evolution_pre_req",
    "EVOL-002": "needs_basic",
    "REST-001": "special_rule_limits",
}

RULES_ORDER = ("DECK-001", "DECK-002", "DECK-003", "DECK-004", "EVOL-001", "EVOL-002", "REST-001")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def card_name(card):
    """Nome canonico da carta: canonical_name (catalogo canônico F4) ou name (fixture F3)."""
    return card.get("canonical_name") or card.get("name") or ""


def validate_deck(deck, catalog):
    """Valida deck contra catalog e retorna veredicto (dict). Catalog: {"cards": [...]}."""
    by_id = {c["card_id"]: c for c in catalog.get("cards", [])}
    violations = []

    entries = deck.get("cards", [])
    total = sum(int(e.get("quantity", 0)) for e in entries)

    # DECK-001 — exatamente 20 cartas
    if total != 20:
        violations.append({"rule_id": "DECK-001",
                           "message": f"deck tem {total} cartas; exigido exatamente 20"})

    # DECK-002 — max 2 copias por NOME (registry: "Max 2 copias por nome").
    # Duas dimensoes, ambas devem passar:
    #   (i)  por IDENTIDADE mecanica (card_id): nenhuma entrada isolada > 2 copias;
    #   (ii) por NOME canonico: soma das copias de TODAS as entradas e TODAS as
    #        identidades que compartilham o mesmo nome (ex: 2x Gastly B2b/37 +
    #        1x Gastly A1/120 = 3 cartas chamadas Gastly = ILEGAL).
    name_by_id = {cid: card_name(c) for cid, c in by_id.items()}
    copies_by_name = Counter()
    for e in entries:
        q = int(e.get("quantity", 0))
        if q > 2:
            violations.append({"rule_id": "DECK-002",
                               "message": f"{e['card_id']} tem {e.get('quantity')} copias; maximo 2"})
        if q > 0:
            cname = name_by_id.get(e["card_id"])
            if cname:
                copies_by_name[cname] += q
    for cname in sorted(copies_by_name):
        if copies_by_name[cname] > 2:
            violations.append({"rule_id": "DECK-002",
                               "message": f"'{cname}' soma {copies_by_name[cname]} copias no deck "
                                          f"(somando todas as identidades/entradas); maximo 2 por nome"})

    # DECK-003 — carta existe no catalogo
    for e in entries:
        if e["card_id"] not in by_id:
            violations.append({"rule_id": "DECK-003",
                               "message": f"carta '{e['card_id']}' nao existe no catalogo"})

    # DECK-004 — legalidade no formato do deck
    deck_format = deck.get("format", "standard")
    for e in entries:
        c = by_id.get(e["card_id"])
        if c and not c.get("legal", True):
            fine = c.get("legal_formats", [deck_format])
            if deck_format not in fine:
                violations.append({"rule_id": "DECK-004",
                                   "message": f"carta '{e['card_id']}' ilegal no formato {deck_format}"})

    # EVOL-001 — evolucao exige pre-requisito no deck.
    # F8b: a ficha declara o pre-requisito por NOME ("Evolves from Gastly").
    # Quando o catalogo amarra pre por card_id (card_evolutions), tambem
    # aceita outra IDENTIDADE do mesmo nome — desde que a cadeia do deck
    # fique coerente (o pre no deck evolui, por nome, para o que exige).
    present_ids = {e["card_id"] for e in entries if e["card_id"] in by_id}
    present_names = {name_by_id[i] for i in present_ids if name_by_id.get(i)}
    for e in entries:
        c = by_id.get(e["card_id"])
        if not c:
            continue
        pre = c.get("evolves_from")
        # F3b: 'mega_ex' entra na checagem — a cadeia Mega exige o pre pelo
        # nome/id, igual stage2 (Mega Gengar ex orfao nao pode passar como legal).
        if c.get("stage") in ("stage1", "stage2", "mega_ex") and pre:
            pre_name = name_by_id.get(pre)
            if pre not in present_ids and (not pre_name or pre_name not in present_names):
                violations.append({"rule_id": "EVOL-001",
                                   "message": f"carta '{e['card_id']}' ({c.get('stage')}) evolui de '{pre}', ausente no deck"})

    # EVOL-002 — pelo menos 1 Pokemon Basico
    has_basic = any((by_id.get(e["card_id"]) or {}).get("stage") == "basic" for e in entries)
    if present_ids and not has_basic:
        violations.append({"rule_id": "EVOL-002",
                           "message": "deck nao inclui nenhum Pokemon Basico"})

    # REST-001 — restricoes declaradas na ficha (special_rule.deck_limit); sem declaracao, nao se aplica
    for e in entries:
        c = by_id.get(e["card_id"])
        if not c:
            continue
        lim = (c.get("special_rule") or {}).get("deck_limit")
        if lim is not None and int(e.get("quantity", 0)) > int(lim):
            violations.append({"rule_id": "REST-001",
                               "message": f"carta '{e['card_id']}' excede limite especial de {lim}"})

    # Citacao das regras aplicaveis no veredicto (aceitacao 4)
    violated = {v["rule_id"] for v in violations}
    satisfied = [rid for rid in RULES_ORDER if rid not in violated]

    return {
        "deck_id": deck.get("id"),
        "format": deck_format,
        "legality": "illegal" if violations else "legal",
        "violations": violations,
        "satisfied_rules": satisfied,
        "rules_registry": RULE_IDS,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validador de legalidade de decks Pokemon TCG Pocket")
    ap.add_argument("deck", help="arquivo deck.json (contrato contracts/deck.json)")
    ap.add_argument("--catalog", required=True, help="catalogo de cartas (fixture ate a F4)")
    args = ap.parse_args(argv)

    verdict = validate_deck(load_json(args.deck), load_json(args.catalog))
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict["legality"] == "legal" else 1


if __name__ == "__main__":
    sys.exit(main())
