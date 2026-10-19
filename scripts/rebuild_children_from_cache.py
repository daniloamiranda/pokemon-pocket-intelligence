#!/usr/bin/env python3
"""F4c etapa 3 (atualizado F5d): rebuild dos filhos 100% offline usando o
CACHE PERSISTENTE do projeto (data/cache/pages) e, como fonte historica
de prova, /opt/data/pocket_probe/pages/pages. Duas execucoes, contagens
identicas = loader idempotente provado."""
import sys, os, time
from pathlib import Path

ROOT = Path("/workspace/ARCOS/projetos/pokemon-pocket-intelligence")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "integrations" / "limitlesstcg-pocket"))
import sqlite3, json, hashlib
import parser as P
import loader as L
import client as C

PERSISTENT = ROOT / "data" / "cache" / "pages"
CACHES = [PERSISTENT, Path("/opt/data/pocket_probe/pages/pages")]
MAIN = ROOT / "data" / "pocket.sqlite"
SETS = ["A1","A1a","A2","A2a","A2b","A3","A3a","A3b","A4","A4a","A4b",
        "B1","B1a","B2","B2a","B2b","B3","B3a","B3b","B4","B4a","B4b","P-A","P-B"]

def frozen_fetch(url, params=None, cache_root=None, max_age_s=None):
    ck = C._cache_key(url, params)
    for pages in CACHES:
        cpath = pages / f"{ck}.html"
        mpath = pages / f"{ck}.meta.json"
        if cpath.exists():
            return cpath.read_text(encoding="utf-8", errors="replace")
        if mpath.exists():
            meta = json.loads(mpath.read_text())
            if meta.get("status") == 404:
                return None
    return None

def run():
    conn = sqlite3.connect(MAIN, timeout=30)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    L.ensure_source(conn)
    misses = []
    for s in SETS:
        lh = frozen_fetch(f"/cards/{s}", params={"display": "compact", "show": "all"}) \
             or frozen_fetch(f"/cards/{s}")
        if lh is None:
            misses.append(f"list:{s}")
            continue
        entries = P.parse_set_page(lh, s) or P.parse_grid_entries(lh, s)
        L.upsert_expansion(conn, P.parse_set_metadata(lh), s)
        ok = 0
        for e in entries:
            page = frozen_fetch(f"/cards/{e['set']}/{e['number']}")
            if page is None:
                misses.append(f"{e['set']}/{e['number']}")
                continue
            card = P.parse_card_page(page, e["set"], e["number"])
            if card is None:
                misses.append(f"parse:{e['set']}/{e['number']}")
                continue
            card["print_rarity"] = None
            L.load_card(conn, card)
            ok += 1
        print(f"  {s}: {ok}/{len(entries)} fichas", flush=True)
    L.link_evolutions(conn)
    counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
              for t in ("cards","card_attacks","card_abilities","card_prints","card_evolutions")}
    conn.commit()
    conn.close()
    return counts, misses

if __name__ == "__main__":
    t0 = time.time()
    c1, m1 = run()
    print("run1:", c1, "misses:", len(m1), m1[:8])
    c2, m2 = run()
    print("run2:", c2, "misses:", len(m2), m2[:8])
    print("ESTAVEL:", c1 == c2)
    conn = sqlite3.connect(MAIN)
    print("integrity:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    print("mewtwo:", conn.execute(
        "SELECT name,damage FROM card_attacks WHERE card_id='limitless:A1/129'").fetchall())
    print("max ataques/carta:", conn.execute(
        "SELECT max(n) FROM (SELECT count(DISTINCT name) n FROM card_attacks GROUP BY card_id)"
    ).fetchone()[0])
    print("dups residuais (atk,ab):", conn.execute(
        "SELECT count(*) FROM (SELECT card_id,name FROM card_attacks GROUP BY card_id,name HAVING count(*)>1)"
    ).fetchone()[0],
        conn.execute(
        "SELECT count(*) FROM (SELECT card_id,name FROM card_abilities GROUP BY card_id,name HAVING count(*)>1)"
    ).fetchone()[0])
    print(f"elapsed {time.time()-t0:.1f}s")
