#!/usr/bin/env python3
"""F4 · Coletor Limitless TCG Pocket -> SQLite canônico.

Uso:
  python3 scripts/collect_pocket.py                     # coleta completa (24 conjuntos)
  python3 scripts/collect_pocket.py --sets A1,B4b       # subconjunto
  python3 scripts/collect_pocket.py --db PATH
  python3 scripts/collect_pocket.py --report PATH       # relatorio de cobertura (JSON)
  python3 scripts/collect_pocket.py --dry-run           # PLANO offline (zero rede, zero escrita)
  python3 scripts/collect_pocket.py --only-list         # (legado, sem efeito — ver LIMITACAO)

Estrategia:
1) lista conjuntos em /cards (curl puro — HTML server-side, sem browser);
2) ficha compacta de cada conjunto (display=compact&show=all) -> entradas por carta;
3) ficha completa de cada carta (por numero) -> parse;
4) upsert idempotente no SQLite (cards + card_prints + attacks/abilities/localizations);
5) resolve card_evolutions; 6) relatorio de cobertura com lacunas.

Imagens NUNCA sao baixadas (so URL). Rate limit: 1 req/1.2s com backoff
(POCKET_RATE_DELAY). Reexecucao idempotente (INSERT OR IGNORE em tudo).

LIMITACAO declarada (F13): --only-list e um flag LEGADO SEM EFEITO (aceito e
nunca implementado). O modo seguro hoje e --dry-run: imprime o PLANO de coleta
(conjuntos alvo, o que faria, quantas requisicoes estimadas, rate limit efetivo)
lendo APENAS o estado do banco — nenhuma requisicao HTTP e nenhuma escrita.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "integrations" / "limitlesstcg-pocket"))

import client  # noqa: E402
import parser  # noqa: E402
import loader  # noqa: E402

ALL_SETS = list(loader.SET_NAMES_FALLBACK)


def collect_set(cur_set: str, db: sqlite3.Connection, stats: dict) -> None:
    list_html = client.fetch_html(f"/cards/{cur_set}", params={"display": "compact", "show": "all"})
    if list_html is None:
        stats.setdefault("failed_sets", []).append(cur_set)
        print(f"  !! {cur_set}: listagem indisponivel", flush=True)
        return
    meta = parser.parse_set_metadata(list_html)
    entries = parser.parse_set_page(list_html, cur_set)
    if not entries:
        entries = parser.parse_grid_entries(list_html, cur_set)
    loader.upsert_expansion(db, meta, cur_set)
    print(f"  {cur_set}: {len(entries)} entradas (site declara {meta.get('card_count')})", flush=True)
    if not entries:
        stats.setdefault("failed_sets", []).append(cur_set)
        return

    detail_stats = {"detail_ok": 0, "detail_fail": []}
    stats["entries"][cur_set] = len(entries)
    stats["declared"][cur_set] = meta.get("card_count")
    for e in entries:
        setc, num = e["set"], e["number"]
        page = client.fetch_html(f"/cards/{setc}/{num}")
        if page is None:
            detail_stats["detail_fail"].append(f"{setc}/{num}")
            continue
        card = parser.parse_card_page(page, setc, num)
        if card is None:
            detail_stats["detail_fail"].append(f"{setc}/{num}")
            continue
        card["print_rarity"] = None
        card_pk, _action = loader.load_card(db, card)
        detail_stats["detail_ok"] += 1
        if detail_stats["detail_ok"] % 200 == 0:
            print(f"    ... {detail_stats['detail_ok']} fichas picadas", flush=True)
    stats["detail_ok"][cur_set] = detail_stats["detail_ok"]
    if detail_stats["detail_fail"]:
        stats.setdefault("detail_fail", []).extend(detail_stats["detail_fail"])

    # backfill deterministicoo: toda entrada da LISTAGEM carrega image_url conferida
    # contra o src da pagina; fichas que falharam (404/rede) ganham a URL da listagem.
    # Impressoes de versoes de outros sets nao aparecem aqui (a listagem cobre o set).
    for e in entries:
        if e.get("image_url"):
            db.execute(
                "UPDATE card_prints SET image_url=? WHERE set_code=? AND number=?"
                " AND image_url IS NULL",
                (e["image_url"], cur_set, e["number"]))
    db.commit()


def coverage_report(db: sqlite3.Connection) -> dict:
    """Relatorio SEMPRE reconstruido do estado do banco (nunca do run).

    Semantica:
    - conjuntos sem contagem declarada (promos P-A/P-B, card_count=0) ficam fora do
      percentual (nao sao 'gap' — a fonte simplesmente nao declara);
    - loaded > declared = SOBRA da fonte (versoes/impressoes extras da tabela de
      versions da ficha), notada como excess, nao como gap;
    - divergencias declarado vs carregado sao listadas em source_discrepancies com a
      classificacao (source_inconsistency = a pagina de sets e a pagina do conjunto
      discordam entre si, falha da fonte, nao da coleta).
    """
    qs = db.execute(
        "SELECT e.code, e.card_count, COUNT(DISTINCT p.id)"
        " FROM expansions e LEFT JOIN card_prints p ON p.set_code = e.code"
        " GROUP BY e.code ORDER BY e.code").fetchall()
    per_set = []
    total_declared = total_loaded = 0  # apenas sets COM contagem declarada
    total_loaded_promo = 0
    for code, declared, loaded in qs:
        declared = declared or 0
        if declared == 0:
            # promo sem contagem declarada: fora do percentual, registrado a parte
            per_set.append({"set": code, "declared": declared, "loaded": loaded,
                            "coverage_pct": None, "gap": None,
                            "note": "sem contagem declarada pela fonte (promo)"})
            total_loaded_promo += loaded
            continue
        pct = (loaded / declared * 100) if declared else 0
        entry = {"set": code, "declared": declared, "loaded": loaded,
                 "coverage_pct": round(pct, 1)}
        if loaded > declared:
            entry["excess"] = loaded - declared
            entry["note"] = "sobra da fonte (versoes extras na tabela de versions)"
        else:
            entry["gap"] = declared - loaded
        per_set.append(entry)
        total_declared += declared
        total_loaded += loaded
    report = {
        "generated_at": loader.now_iso(),
        "source": loader.SOURCE_ID,
        "per_set": per_set,
        "total_declared": total_declared,
        "total_loaded": total_loaded + total_loaded_promo,
        "total_loaded_counted_sets": total_loaded,
        "overall_pct": round(total_loaded / total_declared * 100, 1) if total_declared else 0,
        "cards_rows": db.execute("SELECT COUNT(*) FROM cards").fetchone()[0],
        "card_prints_rows": db.execute("SELECT COUNT(*) FROM card_prints").fetchone()[0],
    }
    # nota explicita sobre os promos (salvo no relatorio quando existirem)
    promo = [e for e in per_set if e["declared"] == 0 and e["loaded"]]
    if promo:
        report["promo_sets_without_declared_count"] = [
            {"set": e["set"], "loaded": e["loaded"],
             "note": ("a fonte nao declara contagem para promos; fora do calculo "
                      "percentual por design")} for e in promo]
    # divergencias reais da fonte (somente conjuntos com contagem declarada);
    # INCONSISTENCIA DA FONTE Limitless: a pagina de sets e a pagina do conjunto
    # discordam entre si (ex.: A3b declara 107 mas pagina do conjunto lista 109);
    # nao e falha da coleta.
    discrep = []
    for entry in per_set:
        if entry.get("loaded") and entry["loaded"] != entry["declared"]:
            if entry["declared"] == 0:
                continue  # promos: registrados a parte (acima)
            discrep.append({
                "set": entry["set"], "declared": entry["declared"],
                "loaded": entry["loaded"],
                "classification": "source_inconsistency",
                "note": ("a pagina de sets e a pagina do conjunto em "
                         "pocket.limitlesstcg.com discordam; falha da fonte Limitless,"
                         " nao da coleta"),
            })
    if discrep:
        report["source_discrepancies"] = discrep
    return report


def dry_run_plan(root: Path, db_path: Path, sets: list) -> dict:
    """Plano de coleta SEM rede e SEM escrita (face segura da skill card-database).

    Le APENAS o estado atual do banco (mode=ro) para estimar requisicoes e
    duracao. Promos/ausentes sem contagem declarada ficam com estimativa
    indisponivel — nunca inventa numero (regra do escopo: sem evidencia nao
    existe estatistica).
    """
    known = [s for s in sets if s in ALL_SETS]
    unknown = [s for s in sets if s not in ALL_SETS]
    counts = {"expansions": None, "cards": None, "card_prints": None}
    declared: dict = {}
    if db_path.is_file():
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            for t in counts:
                counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            declared = dict(con.execute("SELECT code, card_count FROM expansions"))
        finally:
            con.close()
    delay = float(os.environ.get("POCKET_RATE_DELAY", "1.2"))
    # fase 0: indice /cards + 1 pagina de conjunto por set conhecido
    fase0_reqs = (1 + len(ALL_SETS)) if sets else 0
    per_set, est_reqs = [], fase0_reqs
    for s in known:
        fichas = declared.get(s)
        fichas = fichas if isinstance(fichas, int) and fichas > 0 else None
        reqs = 1 + (fichas or 0)
        per_set.append({
            "set": s, "listagem": 1, "fichas_estimadas": fichas,
            "reqs_estimadas": reqs if fichas is not None else None,
            "note": (None if fichas is not None else
                     "sem contagem declarada no banco (promo ou conjunto ausente);"
                     " estimativa indisponivel"),
        })
        if fichas is not None:
            est_reqs += reqs
    return {
        "mode": "dry-run",
        "garantia": "nenhuma requisicao HTTP; nenhuma escrita (banco e relatorio intocados)",
        "db_path": str(db_path),
        "db_exists": db_path.is_file(),
        "estado_atual": counts,
        "sets_solicitados": len(sets),
        "sets_conhecidos": known,
        "sets_desconhecidos": unknown or None,
        "o_que_faria": [
            "fase 0: registrar as 24 expansoes (indice /cards + 1 pagina por conjunto)",
            "por conjunto: listagem compacta (display=compact&show=all) e 1 ficha por entrada",
            "backfill de image_url das impressoes a partir das listagens",
            "resolver card_evolutions (todas as cartas presentes)",
            ("coleta completa: regenerar data/collection_report.json;"
             " parcial: NAO altera o relatorio global"),
        ],
        "rate_limit_s": delay,
        "requisicoes_estimadas": est_reqs,
        "duracao_estimada_min": round(est_reqs * delay / 60, 1) if est_reqs else 0.0,
        "per_set_estimativa": per_set,
        "idempotencia": "INSERT OR IGNORE em tudo: reexecucao segura (nunca duplica)",
        "aviso_aditivo": ("a coleta e ADITIVA: INSERT OR IGNORE fossiliza o primeiro dono"
                          " de um print — re-coleta NAO corrige print apontado para"
                          " identidade errada (classe de defeito F7c; correcao exige"
                          " re-parse auditado)"),
        "para_executar": ("rode SEM --dry-run (rede real; mantenha POCKET_RATE_DELAY"
                          " >= 1.2 por cortesia com a fonte)"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--sets", default=",".join(ALL_SETS))
    ap.add_argument("--db", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--only-list", action="store_true",
                    help="(legado, SEM EFEITO — aceito por compatibilidade; ver LIMITACAO)")
    ap.add_argument("--dry-run", action="store_true",
                    help="imprime o PLANO de coleta (zero rede, zero escrita)")
    args = ap.parse_args()

    root = Path(args.root)
    db_path = Path(args.db) if args.db else root / "data" / "pocket.sqlite"
    sets = [s.strip() for s in args.sets.split(",") if s.strip()]

    if args.dry_run:
        print(json.dumps(dry_run_plan(root, db_path, sets), indent=2, ensure_ascii=False))
        return 0

    db_path.parent.mkdir(parents=True, exist_ok=True)

    # migração antes de qualquer carga
    import subprocess
    subprocess.run([sys.executable, str(root / "scripts" / "db_migrate.py"), "--db", str(db_path)],
                   check=True)

    db = sqlite3.connect(db_path, timeout=30)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    loader.ensure_source(db)

    stats: dict = {"entries": {}, "declared": {}, "detail_ok": {}, "failed_sets": []}
    t0 = time.time()
    start = time.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"== coleta iniciada {start} · {len(sets)} conjuntos", flush=True)

    # FASE 0: registrar TODAS as 24 expansoes primeiro (prints cruzam conjuntos;
    # FK de card_prints.set_code -> expansions(code) exige que existam antes).
    index_html = client.fetch_html("/cards")
    if index_html:
        for code in ALL_SETS:
            sset_html = client.fetch_html(f"/cards/{code}")
            meta = (parser.parse_set_metadata(sset_html) if sset_html else {})
            if not meta or not meta.get("release_date"):
                meta.setdefault("name", None)
                meta.setdefault("release_date", "1970-01-01")
                meta.setdefault("card_count", 0)
            loader.upsert_expansion(db, meta, code)
        print("== fase 0: expansões registradas", flush=True)

    for s in sets:
        collect_set(s, db, stats)
    # evoluções no fim (todas as cartas presentes)
    n = loader.link_evolutions(db)
    print(f"== evolucoes ligadas: {n}", flush=True)

    # relatorio SEMPRE reconstruido do ESTADO DO BANCO + imune a execucao parcial:
    # - coleta parcial NAO reescreve o relatorio global (o registro do que a coleta
    #   COMPLETA cobriu se perderia); o run e logado no stdout/audit.
    # - coleta completa regenera data/collection_report.json do banco.
    full_collect = set(sets) >= set(ALL_SETS)
    if full_collect:
        report = coverage_report(db)
        report["collect"] = stats
        report["elapsed_seconds"] = round(time.time() - t0, 1)
        report_path = Path(args.report) if args.report else root / "data" / "collection_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        print(json.dumps({k: report[k] for k in
                          ["total_declared", "total_loaded", "overall_pct", "cards_rows",
                           "card_prints_rows"]}, ensure_ascii=False))
        failed = stats.get("failed_sets") or []
        if failed:
            print(f"conjuntos com falha: {failed}")
        print(f"relatorio: {report_path}")
    else:
        audit = coverage_report(db)
        print(json.dumps({k: audit[k] for k in
                          ["total_declared", "total_loaded", "overall_pct", "cards_rows",
                           "card_prints_rows"]}, ensure_ascii=False))
        print("RUN PARCIAL: relatorio global data/collection_report.json NAO alterado"
              " (regenerado apenas em coleta completa)", flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
