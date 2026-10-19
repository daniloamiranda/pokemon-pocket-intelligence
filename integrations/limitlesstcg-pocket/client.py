"""Cliente HTTP para pocket.limitlesstcg.com (fonte canonica de cartas, nivel A).

Politica (docs/FASE1-DIAGNOSTICO.md):
- Rate limit conservador (RATE_DELAY, default 1.2s) com backoff exponencial em 429/5xx.
- User-Agent identificado (uso respeitoso, sem redistribuicao de imagens).
- Cache PERSISTENTE em disco (data/cache/pages, dentro do projeto): pagina
  baixada nao e baixada de novo (idempotencia). Cache em /tmp e PROIBIDO
  pelo escopo (secao 21: nada de dado operacional em caminho efemero) —
  o default de POCKET_CACHE e o caminho persistente do repositorio.
- Imagens NUNCA sao baixadas: apenas a URL e registrada.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://pocket.limitlesstcg.com"
UA = "ARCSEC-PocketIntel/0.1 (non-commercial card catalog; contact: dev@arcsec.local)"
# Cache persistente do projeto (F5d): nunca em /tmp (efemero, escopo §21).
DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[2] / "data" / "cache"
RATE_DELAY = float(os.environ.get("POCKET_RATE_DELAY", "1.2"))
MAX_RETRIES = int(os.environ.get("POCKET_MAX_RETRIES", "4"))


def _cache_dir(cache_root: Path) -> Path:
    d = cache_root / "pages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(url: str, params: dict | None) -> str:
    canon = url + ("?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items())))
    return hashlib.sha1(canon.encode()).hexdigest()[:24]


def fetch_html(url: str, params: dict | None = None, cache_root: Path | None = None,
               max_age_s: int = 3600) -> str | None:
    """GET HTML com cache. Retorna None em falha persistente/404."""
    ck = _cache_key(url, params)
    env_root = os.environ.get("POCKET_CACHE", "").strip()
    # POCKET_CACHE so e honrado se EXPLICITO (nunca resolve para cwd "/.");
    # default SEMPRE data/cache do projeto (persistente, F5d).
    root = cache_root or (Path(env_root) if env_root else DEFAULT_CACHE_ROOT)
    if root.resolve() == Path("/tmp") or str(root).startswith("/tmp/"):
        # caminho efemero proibido (escopo §21): usa o persistente
        root = DEFAULT_CACHE_ROOT
    cache = _cache_dir(root)
    cpath = cache / f"{ck}.html"
    mpath = cache / f"{ck}.meta.json"
    if cpath.exists():
        age = time.time() - cpath.stat().st_mtime
        if age <= max_age_s:
            return cpath.read_text(encoding="utf-8", errors="replace")
    # 404 memorizado por 24h (cache negativo)
    if mpath.exists():
        meta = json.loads(mpath.read_text())
        if meta.get("status") == 404 and time.time() - meta.get("at", 0) < 86400:
            return None
    full = BASE + url if url.startswith("/") else url
    if params:
        from urllib.parse import urlencode
        full += "?" + urlencode(params)
    delay = RATE_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            cpath.write_text(body, encoding="utf-8")
            mpath.write_text(json.dumps({"status": 200, "url": full, "at": time.time()}))
            time.sleep(delay)
            return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                mpath.write_text(json.dumps({"status": 404, "url": full, "at": time.time()}))
                return None
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(delay * (2 ** attempt))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(delay * (2 ** attempt))
    return None
