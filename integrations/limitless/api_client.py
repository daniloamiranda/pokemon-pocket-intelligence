"""Cliente HTTP da Limitless Developer API (dados de torneio, nivel A para meta).

Fonte: https://docs.limitlesstcg.com/developer (lido em 2026-10-19, prova no cartao F7).
- Base: https://play.limitlesstcg.com/api
- Endpoints usados: GET /tournaments, /tournaments/{id}/details, /standings, /pairings
- Nao exige API key para esse escopo (so /games/{id}/decks exige — nao usado).
- Rate limit declarado por header: `RateLimit: "50-in-5min"; r=N; t=S`.
  Cliente conservador: intervalo minimo entre chamadas + parada quando r <= 1
  + backoff exponencial em 429/5xx. Sem scraping de HTML (API resolve — regra F7).
- Resposta sempre salva pelo chamador (data/meta/raw) — aqui nao ha cache.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://play.limitlesstcg.com/api"
UA = "ARCSEC-PocketIntel/0.1 (non-commercial metagame research; contact: dev@arcsec.local)"
MIN_INTERVAL_S = float(6.2)   # 50 req / 300 s declarados; 6.2 s ≈ 9.7 req/min (folga)
MAX_RETRIES = 5

_last_call_at = 0.0


class LimitlessAPIError(RuntimeError):
    """Falha persistente de rede/API apos retries."""


def _throttle(remaining: int | None, window_s: int | None) -> None:
    global _last_call_at
    now = time.time()
    gap = now - _last_call_at
    if gap < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - gap)
    if remaining is not None and remaining <= 1 and window_s:
        # janela esgotada: espera o reset declarado no header (+1 s de folga)
        time.sleep(window_s + 1.0)
    _last_call_at = time.time()


def parse_rate_limit(headers) -> tuple[int | None, int | None]:
    """Extrai (remaining, window_s) do header RateLimit RFC-style do Limitless."""
    raw = headers.get("RateLimit") or headers.get("X-RateLimit") or ""
    m = re.search(r"r=(\d+)", raw)
    t = re.search(r"t=(\d+)", raw)
    return (int(m.group(1)) if m else None, int(t.group(1)) if t else None)


def get_json(path: str, timeout_s: int = 30) -> dict | list:
    """GET com throttle, backoff e parse JSON. Levanta LimitlessAPIError no fim."""
    url = BASE + path
    last_err = None
    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                remaining, window_s = parse_rate_limit(resp.headers)
                body = resp.read().decode("utf-8", errors="replace")
            _throttle(remaining, window_s)
            return json.loads(body)
        except urllib.error.HTTPError as e:
            remaining, window_s = parse_rate_limit(e.headers or {})
            if e.code == 404:
                # recurso sem dados (ex.: torneio sem pairings publicos) — nao e erro de rede
                _throttle(remaining, window_s)
                raise LimitlessAPIError(f"404 {url}") from e
            last_err = f"HTTP {e.code}"
            wait = 60.0 if e.code == 429 else MIN_INTERVAL_S * (2 ** attempt)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            last_err = str(e)
            time.sleep(MIN_INTERVAL_S * (2 ** attempt))
    raise LimitlessAPIError(f"falta persistente em {url}: {last_err}")
