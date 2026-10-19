#!/usr/bin/env python3
"""Coletor de torneios da Limitless Developer API -> data/meta/raw.

- Backfill/checkpoint: pages de /tournaments?game=POCKET e standings/pairings por
  torneio sao gravados no disco ANTES do proximo fetch; reexecucao pula o que ja
  existe (idempotente). Nada em /tmp (escopo §21).
- Escopo de coleta: game=POCKET, format STANDARD apenas (format null no /tournaments
  e resolvido pelo /details; NOEX/CUSTOM ficam de fora — regra documentada no SKILL.md).
- Rate limit 50/5min respeitado via api_client (MIN_INTERVAL_S=6.2s).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = Path(os.environ.get("POCKET_META_RAW", ROOT / "data" / "meta" / "raw"))
GAME = "POCKET"
PAGE_SIZE = 50
MAX_PAGES = 40          # 40*50 = 2000 torneios: teto de seguranca
DAYS = int(os.environ.get("POCKET_META_DAYS", "35"))

sys.path.insert(0, str(ROOT / "integrations" / "limitless"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # fallback local
import api_client  # noqa: E402



def list_tournaments() -> list[dict]:
    """Enumera torneios POCKET recentes com paginacao e checkpoint por pagina."""
    pages_dir = RAW / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - DAYS * 86400))
    rows: list[dict] = []
    page = 1
    while page <= MAX_PAGES:
        ppath = pages_dir / f"page_{page}.json"
        if ppath.exists():
            data = json.loads(ppath.read_text())
        else:
            data = api_client.get_json(f"/tournaments?game={GAME}&limit={PAGE_SIZE}&page={page}")
            _atomic(ppath, json.dumps(data))
        rows.extend(data)
        print(f"  page {page}: {len(data)} torneios (cutoff {cutoff})", flush=True)
        if len(data) < PAGE_SIZE:
            break
        if data[-1]["date"][:10] < cutoff:
            break
        page += 1
    return rows


def fetch_tournament(tid: str) -> None:
    """Baixa details/standings/pairings de um torneio, com checkpoint por arquivo."""
    tdir = RAW / "tournaments" / tid
    tdir.mkdir(parents=True, exist_ok=True)
    for name in ("details", "standings", "pairings"):
        fpath = tdir / f"{name}.json"
        if fpath.exists():
            continue
        try:
            data = api_client.get_json(f"/tournaments/{tid}/{name}")
            _atomic(fpath, json.dumps(data))
        except api_client.LimitlessAPIError as e:
            if "404" in str(e):
                # sem pairings/sem decklists publicos: memoriza vazio e segue
                _atomic(fpath, json.dumps({"_http404": True}))
            else:
                raise


def _atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"[collect] raw={RAW}", flush=True)
    tournaments = list_tournaments()
    tdir_list = RAW / "tournaments"
    tdir_list.mkdir(exist_ok=True)
    # prioriza maiores (mais informacao por chamada) mas processa todos do periodo
    tournaments.sort(key=lambda t: -(t.get("players") or 0))
    n = len(tournaments)
    print(f"[collect] {n} torneios no periodo de {DAYS} dias", flush=True)
    for i, t in enumerate(tournaments, 1):
        tid = t["id"]
        if i % 10 == 0 or i == n:
            print(f"[collect] {i}/{n} (players={t.get('players')} {t['date'][:10]} {t['name'][:40]!r})", flush=True)
        fetch_tournament(tid)
    print("[collect] DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
