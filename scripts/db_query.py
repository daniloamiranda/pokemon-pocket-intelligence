#!/usr/bin/env python3
"""F13 · Consulta READ-ONLY ao catalogo (skill pokemon-pocket-card-database).

Face de CONSULTA da skill (sem rede, sem escrita). A face de ATUALIZACAO
(coleta incremental) e o proprio scripts/collect_pocket.py — esta skill ENVOLVE
as ferramentas canonicas, nunca reimplementa coleta.

Uso:
  python3 scripts/db_query.py stats                 # contagens globais
  python3 scripts/db_query.py coverage              # cobertura por conjunto
  python3 scripts/db_query.py card "Mega Gengar ex" # ficha + prints + evolucao
  python3 scripts/db_query.py --db PATH stats

Regras inegociaveis:
- Abre o banco SEMPRE em mode=ro (SQLite URI). Consulta NAO altera producao.
- Banco unico do projeto: <repo>/data/pocket.sqlite (nunca copia paralela).
- print errado e PIOR que print ausente: a ficha lista o que o banco TEM e
  aponta lacunas, nunca adivinha impressao (promos sem href nao se adivinham —
  causa-raiz do F7c).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "pocket.sqlite"


def open_ro(db_path: Path) -> sqlite3.Connection:
    """Abre o catalogo em modo somente-leitura (falha se o arquivo nao existir)."""
    if not db_path.is_file():
        print(f"ERRO: catalogo ausente: {db_path}", file=sys.stderr)
        print("      Consulta NAO coleta na rede. Para popular o banco rode a face", file=sys.stderr)
        print("      de atualizacao da skill: python3 scripts/collect_pocket.py (ver SKILL).", file=sys.stderr)
        raise SystemExit(3)
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    return db


def cmd_stats(db: sqlite3.Connection) -> dict:
    """Contagens globais do catalogo (fonte da verdade para o aceite da skill)."""
    stats = {
        "database": "data/pocket.sqlite",
        "expansions": db.execute("SELECT COUNT(*) FROM expansions").fetchone()[0],
        "cards": db.execute("SELECT COUNT(*) FROM cards").fetchone()[0],
        "card_prints": db.execute("SELECT COUNT(*) FROM card_prints").fetchone()[0],
        "evolutions": db.execute("SELECT COUNT(*) FROM card_evolutions").fetchone()[0],
        "validation_status": dict(db.execute(
            "SELECT validation_status, COUNT(*) FROM cards GROUP BY validation_status")),
    }
    by_cat = db.execute(
        "SELECT category, COUNT(*) AS n FROM cards GROUP BY category ORDER BY n DESC")
    stats["cards_by_category"] = {r["category"]: r["n"] for r in by_cat}
    return stats


def cmd_coverage(db: sqlite3.Connection) -> dict:
    """Cobertura por conjunto: declarado pela fonte vs carregado no banco.

    Mesma semantica do relatorio canonico (collect_pocket.coverage_report):
    promos sem contagem declarada ficam fora do percentual (note, nao gap) e
    loaded > declared e excess da fonte, nao falha da coleta.
    """
    rows = db.execute(
        "SELECT e.code, e.name, e.card_count, COUNT(p.id) AS loaded"
        " FROM expansions e LEFT JOIN card_prints p ON p.set_code = e.code"
        " GROUP BY e.code ORDER BY e.code").fetchall()
    per_set, gaps, excesses = [], [], []
    for r in rows:
        declared, loaded = r["card_count"] or 0, r["loaded"]
        entry = {"set": r["code"], "name": r["name"], "declared": declared, "loaded": loaded}
        if declared == 0:
            entry["note"] = "sem contagem declarada pela fonte (promo); fora do percentual"
        else:
            entry["coverage_pct"] = round(loaded / declared * 100, 1)
            if loaded < declared:
                entry["gap"] = declared - loaded
                gaps.append(f"{r['code']}: faltam {entry['gap']} de {declared}")
            elif loaded > declared:
                entry["excess"] = loaded - declared
                excesses.append(f"{r['code']}: {entry['excess']} alem do declarado (sobra da fonte)")
        per_set.append(entry)
    counted = [e for e in per_set if e.get("coverage_pct") is not None]
    overall = (sum(e["loaded"] for e in counted) /
               sum(e["declared"] for e in counted) * 100) if counted else 0.0
    return {
        "per_set": per_set,
        "overall_pct": round(overall, 1),
        "sets_with_gap": gaps,
        "sets_with_excess": excesses,
        "promo_sets": [e["set"] for e in per_set if e["declared"] == 0],
    }


def cmd_card(db: sqlite3.Connection, term: str) -> dict:
    """Ficha de carta por termo de busca (nome, exato ou LIKE) ou ID canonico.

    Resolve IDENTIDADE mecanica primeiro (cards); impressoes (card_prints) vem
    listadas a parte — prints da mesma identidade sao mecanicamente identicos.
    """
    exact = db.execute("SELECT * FROM cards WHERE canonical_name = ? COLLATE NOCASE", (term,)).fetchone()
    if exact is None:
        by_id = db.execute("SELECT * FROM cards WHERE id = ?", (term,)).fetchone()
        if by_id is not None:
            exact, term_note = by_id, f"resolvido por card_id {term}"
    if exact is None:
        like = db.execute(
            "SELECT * FROM cards WHERE canonical_name LIKE ? ORDER BY canonical_name LIMIT 10",
            (f"%{term}%",)).fetchall()
        if not like:
            raise SystemExit(f"nenhuma carta encontrada para: {term!r}")
        if len(like) == 1:
            exact, term_note = like[0], "unica correspondencia LIKE"
        else:
            return {
                "status": "ambiguo",
                "term": term,
                "note": f"{len(like)} identidades batem; refine o termo (max 10 listadas)",
                "candidates": [dict(id=c["id"], canonical_name=c["canonical_name"],
                                    category=c["category"], element=c["element"],
                                    stage=c["stage"], hp=c["hp"]) for c in like],
            }
    else:
        term_note = "nome exato" if exact["canonical_name"].lower() == term.lower() else term_note

    c = exact
    prints = [dict(id=p["id"], set_code=p["set_code"], number=p["number"],
                   rarity=p["rarity"], artist=p["artist"], is_promo=bool(p["is_promo"]),
                   has_image_url=p["image_url"] is not None)
              for p in db.execute(
                  "SELECT * FROM card_prints WHERE card_id = ? ORDER BY set_code, number",
                  (c["id"],))]
    attacks = [dict(name=a["name"], energy_cost=json.loads(a["energy_cost"]),
                    damage=a["damage"], effect_text=a["effect_text"])
               for a in db.execute(
                   "SELECT * FROM card_attacks WHERE card_id = ? ORDER BY sort_order",
                   (c["id"],))]
    abilities = [dict(name=a["name"], kind=a["kind"], effect_text=a["effect_text"])
                 for a in db.execute(
                     "SELECT * FROM card_abilities WHERE card_id = ?", (c["id"],))]
    evolves_from = db.execute(
        "SELECT e.pre_evo_card_id, e.stage, p.canonical_name FROM card_evolutions e"
        " JOIN cards p ON p.id = e.pre_evo_card_id WHERE e.card_id = ?", (c["id"],)).fetchone()
    evolves_to = [dict(card_id=r["card_id"], stage=r["stage"], name=r["canonical_name"])
                  for r in db.execute(
                      "SELECT e.card_id, e.stage, p.canonical_name FROM card_evolutions e"
                      " JOIN cards p ON p.id = e.card_id WHERE e.pre_evo_card_id = ?", (c["id"],))]
    return {
        "status": "ok",
        "resolved_by": term_note,
        "card": dict(id=c["id"], canonical_name=c["canonical_name"], category=c["category"],
                     element=c["element"], stage=c["stage"],
                     evolves_from_id=c["evolves_from_id"], hp=c["hp"],
                     weakness_element=c["weakness_element"], retreat_cost=c["retreat_cost"],
                     special_rule=c["special_rule"], is_ex=bool(c["is_ex"]),
                     mechanical_hash=c["mechanical_hash"],
                     validation_status=c["validation_status"]),
        "prints": prints,
        "attacks": attacks,
        "abilities": abilities,
        "evolves_from": (dict(evolves_from) if evolves_from else None),
        "evolves_to": evolves_to,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("command", choices=["stats", "coverage", "card"])
    ap.add_argument("term", nargs="?", default=None,
                    help="obrigatorio para 'card': nome (exato ou parte) ou card_id")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    if args.command == "card" and not args.term:
        ap.error("comando 'card' exige o termo de busca")

    db = open_ro(Path(args.db))
    try:
        if args.command == "stats":
            out = cmd_stats(db)
        elif args.command == "coverage":
            out = cmd_coverage(db)
        else:
            out = cmd_card(db, args.term)
    finally:
        db.close()
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
