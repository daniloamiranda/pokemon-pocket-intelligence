#!/usr/bin/env python3
"""rules_refresh — atualizacao da base de regras SOB DEMANDA (card t_fafb754f).

PRINCIPIO: a base de regras e ESTATICA e local (docs/RULES.md). O Firecrawl
NAO e dependencia de runtime — e ferramenta de MANUTENCAO, acionada MANUALMENTE
quando houver suspeita de atualizacao oficial. Este script:
  * nunca e agendado (nada de cron);
  * nunca e chamado por validate_deck.py / build_deck.py / evaluate_deck.py
    (guarda em tests/unit/test_rules_refresh.py);
  * NUNCA edita o docs/RULES.md — apenas compara e reporta; quem decide a
    mudanca e o Proprietario (procedimento em docs/SOURCES.md).

Fontes capturadas (via Firecrawl/Composio, conta ACTIVE obrigatoria):
  faq-gameplay — Pokemon TCG Pocket Gameplay FAQ (support.pokemon.com)
  faq-battle   — Pokemon TCG Pocket Battle Rules FAQ (support.pokemon.com)

Comparacao: texto capturado (normalizado) x snapshot anterior em
data/rules_snapshots/ (FORA do git) por sha256 e diff de linhas, com relatorio
legivel das secoes (headers '## ') afetadas.

Codigos de saida:
  0  sem mudanca (ou primeira captura = linha de base)
 10  mudanca detectada (relatorio impresso; snapshot atualizado)
  2  uso invalido
  3  sem conexao Composio/Firecrawl (instrucao de reconexao na mensagem;
     sem retry infinito) — interrompe na primeira fonte afetada
  4  captura implausivel (vazia / abaixo do minimo / HTTP != 200 / sem
     estrutura esperada) — NUNCA e interpretada como "sem mudanca"
  Prioridade do codigo: 3 interrompe tudo; senao 4 > 10 > 0 (erro de
  captura exige atencao humana de qualquer forma).

A credencial Composio NUNCA vai em argv: vem da variavel de processo
COMPOSIO_API_KEY (se exportada) ou do arquivo de ambiente
(RULES_REFRESH_ENV_FILE, default o mesmo do sync F11).

Uso:
  python3 scripts/rules_refresh.py                 # captura as duas FAQs
  python3 scripts/rules_refresh.py --report out.md # + salva o relatorio
  python3 scripts/rules_refresh.py --sources faq-gameplay
  python3 scripts/rules_refresh.py --offline captura.md [--source-id faq-battle]

Testabilidade: --offline injeta um texto como captura (revisao manual e testes
unitarios) sem tocar rede.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RC_OK = 0
RC_USAGE = 2
RC_NO_CONNECTION = 3
RC_BAD_CAPTURE = 4
RC_CHANGED = 10

SNAPSHOT_DIR_DEFAULT = ROOT / "data" / "rules_snapshots"
# Default portavel: .env do perfil c3po na raiz Hermes do usuario (igual ao
# sync F11); override por C3PO_ENV, RULES_REFRESH_ENV_FILE ou --env-file.
ENV_FILE_DEFAULT = Path.home() / ".hermes" / "profiles" / "c3po" / ".env"
TK_VERSION = "20261014_01"          # pin consciente (igual padrao F11)
SCRAPE_TIMEOUT_S = 120              # teto por fonte; estouro = erro declarado
MIN_BYTES_DEFAULT = 3000            # gameplay ~18.9k, battle ~6k (19/10/2026)
MAX_DIFF_LINES = 200                # truncagem do diff no relatorio

# Fontes oficiais do registry (docs/SOURCES.md [FAQ-GAMEPLAY] e [FAQ-BATTLE]).
SOURCES = {
    "faq-gameplay": (
        "https://support.pokemon.com/hc/en-us/articles/"
        "30330309361172-Pokemon-TCG-Pocket-Gameplay-FAQ"
    ),
    "faq-battle": (
        "https://support.pokemon.com/hc/en-us/articles/"
        "38906248102292-Pokemon-TCG-Pocket-Battle-Rules-FAQ"
    ),
}


class RulesRefreshError(Exception):
    """Erro declarado (nunca silencioso)."""


class NoConnectionError(RulesRefreshError):
    """Sem SDK/credencial/conta ACTIVE — instrucao de reconexao na mensagem."""


class CaptureError(RulesRefreshError):
    """Captura implausivel (vazia, curta, HTTP != 200, estrutura atipica)."""


# ---------------------------------------------------------------------------
# Credencial e conexao (composio) — sem segredo em argv, sem retry infinito
# ---------------------------------------------------------------------------

def load_credential(env_file: str, environ: dict | None = None) -> str:
    """COMPOSIO_API_KEY da variavel de processo ou do arquivo de ambiente.

    O valor nunca e logado; erros dizem ONDE procurar, nao o valor."""
    env = os.environ if environ is None else environ
    val = (env.get("COMPOSIO_API_KEY") or "").strip()
    if val:
        return val
    path = Path(env_file)
    if not path.is_file():
        raise NoConnectionError(
            "Sem credencial Composio: COMPOSIO_API_KEY nao exportada no "
            f"processo e arquivo de ambiente ausente: {path}. Exporte a "
            "variavel ou aponte RULES_REFRESH_ENV_FILE para o .env correto."
        )
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        if k.strip() == "COMPOSIO_API_KEY":
            val = v.strip().strip('"').strip("'")
            if val:
                return val
    raise NoConnectionError(
        f"Arquivo {path} existe mas nao declara COMPOSIO_API_KEY ativa "
        "(linha nao comentada). Sem conexao nao ha captura — rodar apenas "
        "quando a conta estiver reconectada."
    )


def _attr(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def pick_firecrawl_account(accounts) -> tuple[str, str]:
    """Escolhe a connected account do toolkit firecrawl com status ACTIVE.

    O user_id da conta pode ser id de projeto (nao "default") — o script
    descobre o par (connected_account_id, user_id) automaticamente."""
    for acc in accounts:
        toolkit = _attr(acc, "toolkit")
        slug = _attr(toolkit, "slug") if toolkit is not None else None
        if slug != "firecrawl":
            continue
        if _attr(acc, "status") == "ACTIVE":
            ca_id = _attr(acc, "id")
            user_id = _attr(acc, "user_id") or _attr(acc, "userId")
            if ca_id and user_id:
                return str(ca_id), str(user_id)
    raise NoConnectionError(
        "Nenhuma connected account do toolkit 'firecrawl' com status ACTIVE "
        "no Composio. Reconecte: dashboard Composio -> Toolkits -> Firecrawl "
        "-> Connect (ou o fluxo de connected accounts que voce usar). Depois "
        "de reconectar, rode este script novamente — sem retry automatico."
    )


def list_connected_accounts(credential: str):
    """Lista connected accounts via SDK (exige composio no interprete)."""
    try:
        from composio import Composio  # import tardio: modulo roda sem SDK
    except ImportError as ex:
        raise NoConnectionError(
            "SDK composio ausente neste interprete — use o venv "
            "o venv do projeto (<venv local>; composio==0.22.0; ver "
            "docs/TESTING.md secao 2). Sem SDK nao ha captura."
        ) from ex
    client = Composio(api_key=credential)
    resp = client.connected_accounts.list()
    items = getattr(resp, "items", None) or []
    return client, list(items)


# ---------------------------------------------------------------------------
# Captura
# ---------------------------------------------------------------------------

def extract_markdown(result) -> tuple[str, dict]:
    """Extrai (markdown, metadata) do retorno do FIRECRAWL_SCRAPE.

    Estrutura observada 19/10/2026: r['data'] = {'data': {'markdown': ...,
    'metadata': {...}}, 'successful': bool} (com fallback r['data']['markdown']).
    Estrutura atipica = erro declarado, nunca conteudo vazio silencioso."""
    if not isinstance(result, dict):
        raise CaptureError(f"retorno atipico do toolkit: {type(result).__name__}")
    outer = result.get("data")
    if not isinstance(outer, dict):
        raise CaptureError(
            f"retorno sem bloco 'data': chaves={sorted(result.keys())}"
        )
    inner = outer.get("data") if isinstance(outer.get("data"), dict) else outer
    md = inner.get("markdown")
    if not isinstance(md, str) or not md.strip():
        raise CaptureError(
            "HTTP-level ok mas markdown vazio/ausente — captura tratada como "
            f"ERRO (chaves do bloco: {sorted(inner.keys())})."
        )
    meta = inner.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    return md, meta


def capture_firecrawl(url: str, client, ca_id: str, user_id: str,
                      timeout_s: int = SCRAPE_TIMEOUT_S):
    """1 tentativa, teto de tempo proprio; falha = erro declarado.

    `user_id` e `connected_account_id` sao OBRIGATORIOS em conjunto (a API
    recusa connected account sem entity id — code 1811, provado em producao
    em 19/10/2026 e vigiado por teste)."""
    outcome: list = []

    def _run():
        try:
            res = client.tools.execute(
                "FIRECRAWL_SCRAPE",
                arguments={"url": url, "formats": ["markdown"]},
                version=TK_VERSION,
                user_id=user_id,
                connected_account_id=ca_id,
            )
            outcome.append(("ok", res))
        except Exception as ex:  # erro de rede/SDK — declarado, sem retry
            outcome.append(("err", ex))

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        raise CaptureError(
            f"Firecrawl excedeu {timeout_s}s para {url} — abortado sem retry."
        )
    kind, payload = outcome[0] if outcome else ("err", RuntimeError("sem resultado"))
    if kind == "err":
        raise CaptureError(f"Firecrawl falhou para {url}: {payload!r}")
    return extract_markdown(payload if isinstance(payload, dict) else {"data": getattr(payload, "data", payload)})


def capture_offline(path: str) -> tuple[str, dict]:
    p = Path(path)
    if not p.is_file():
        raise CaptureError(f"--offline: arquivo nao encontrado: {p}")
    md = p.read_text(encoding="utf-8")
    return md, {"sourceURL": f"file://{p}", "offline": True}


# ---------------------------------------------------------------------------
# Normalizacao, plausibilidade, diff
# ---------------------------------------------------------------------------

def normalize_capture(raw_md: str) -> str:
    """\\r\\n -> \\n e corte da navegacao anterior ao primeiro header '## '.

    O bloco '### Articles in this section' do Zendesk muda por razoes
    irrelevantes (outros artigos da secao); o conteudo util comeca no
    primeiro '## '."""
    text = raw_md.replace("\r\n", "\n")
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            return "\n".join(lines[i:]).rstrip("\n")
    raise CaptureError(
        "Captura sem nenhum header '## ' — formato inesperado da fonte "
        "(nada e comparado nem salvo em caso de duvida)."
    )


def check_plausible(raw_md: str, meta: dict, min_bytes: int) -> None:
    """HTTP 200 com conteudo vazio/curto = erro declarado (nunca silencioso)."""
    status = meta.get("statusCode")
    if status is not None and str(status) != "200":
        raise CaptureError(f"HTTP {status} (esperado 200) — captura rejeitada.")
    size = len(raw_md.encode("utf-8"))
    if size == 0:
        raise CaptureError("Captura vazia (0 bytes) — erro declarado.")
    if size < min_bytes:
        raise CaptureError(
            f"Captura abaixo do plausivel: {size} bytes < minimo {min_bytes}."
        )
    if not re.search(r"Pok[eé]mon", raw_md):
        raise CaptureError(
            "Captura nao contem 'Pokemon' — provavel pagina de erro/anti-bot."
        )


def current_sections(text: str) -> list[str]:
    return [ln[3:].strip() for ln in text.split("\n") if ln.startswith("## ")]


def diff_sections(old_text: str, new_text: str) -> list[tuple[str, int, int]]:
    """[(secao do novo texto, +linhas, -linhas)] na ordem em que aparecem."""
    sections: dict[int, str] = {}
    cur = "(topo)"
    for i, ln in enumerate(new_text.split("\n")):
        if ln.startswith("## "):
            cur = ln[3:].strip()
        sections[i] = cur
    out: list[tuple[str, int, int]] = []
    for tag, a1, a2, b1, b2 in difflib.SequenceMatcher(
        a=old_text.split("\n"), b=new_text.split("\n")
    ).get_opcodes():
        if tag == "equal":
            continue
        added, removed = b2 - b1, a2 - a1
        sec = sections.get(b1, "(fim)")
        if out and out[-1][0] == sec:
            p, plus, minus = out[-1]
            out[-1] = (p, plus + added, minus + removed)
        else:
            out.append((sec, added, removed))
    return out


def unified_diff(old_text: str, new_text: str, max_lines: int = MAX_DIFF_LINES) -> str:
    lines = list(difflib.unified_diff(
        old_text.split("\n"), new_text.split("\n"),
        fromfile="snapshot anterior", tofile="captura atual", lineterm=""))
    body = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        body += f"\n... ({len(lines) - max_lines} linhas de diff omitidas)"
    return body


# ---------------------------------------------------------------------------
# Snapshot e relatorio
# ---------------------------------------------------------------------------

def snapshot_paths(snap_dir: Path, source_id: str) -> tuple[Path, Path]:
    return snap_dir / f"{source_id}.txt", snap_dir / f"{source_id}.json"


def load_snapshot(snap_dir: Path, source_id: str) -> tuple[str | None, dict | None]:
    txt, meta = snapshot_paths(snap_dir, source_id)
    if not txt.is_file():
        return None, None
    prev_meta = {}
    if meta.is_file():
        try:
            prev_meta = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prev_meta = {"nota": "meta anterior ilegivel"}
    return txt.read_text(encoding="utf-8"), prev_meta


def save_snapshot(snap_dir: Path, source_id: str, text: str, url: str, method: str) -> str:
    snap_dir.mkdir(parents=True, exist_ok=True)
    txt_path, meta_path = snapshot_paths(snap_dir, source_id)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    tmp = txt_path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, txt_path)  # atomico: nunca snapshot pela metade
    meta_path.write_text(json.dumps({
        "source_id": source_id,
        "url": url,
        "method": method,
        "captured_at_utc": _now_utc(),
        "sha256": digest,
        "bytes": len(text.encode("utf-8")),
        "toolkit_version": None if method == "offline" else TK_VERSION,
    }, indent=2) + "\n", encoding="utf-8")
    return digest


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_report(entries: list[dict]) -> str:
    out = [f"# rules_refresh — relatorio {_now_utc()}", ""]
    for e in entries:
        out.append(f"## Fonte: {e['source_id']}")
        out.append(f"- URL: {e['url']}")
        if e.get("error"):
            out.append(f"- RESULTADO: ERRO — {e['error']}")
            out.append("")
            continue
        if e["baseline"]:
            out.append("- RESULTADO: primeira captura — snapshot criado (linha de base).")
        elif e["changed"]:
            out.append("- RESULTADO: MUDANCA DETECTADA (docs/RULES.md NAO e alterado "
                       "automaticamente — decisao humana; procedimento em docs/SOURCES.md).")
        else:
            out.append("- RESULTADO: sem mudanca.")
        out.append(f"- Captura atual: sha256={e['new_sha']} ({e['new_bytes']} bytes, metodo {e['method']})")
        if e.get("prev_sha"):
            when = e.get("prev_meta", {}).get("captured_at_utc", "?")
            out.append(f"- Snapshot anterior: sha256={e['prev_sha']} (capturado {when})")
        if e.get("sections"):
            out.append("- Secoes afetadas (headers '## ' do novo texto):")
            for sec, plus, minus in e["sections"]:
                out.append(f"    - \"{sec}\" (+{plus}/-{minus} linhas)")
        if e.get("diff"):
            out.append("- Diff (unificado):")
            out.append("```diff")
            out.append(e["diff"])
            out.append("```")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Atualizacao da base de regras SOB DEMANDA (Firecrawl = "
                    "manutencao, nunca runtime). Nao agenda, nao roda em "
                    "servico, nao edita RULES.md.")
    ap.add_argument("--sources", default=",".join(SOURCES),
                    help="ids separados por virgula (default: todos)")
    ap.add_argument("--offline", metavar="ARQUIVO",
                    help="injeta o arquivo como captura (sem rede; 1 fonte)")
    ap.add_argument("--source-id", choices=sorted(SOURCES),
                    help="fonte associada ao --offline")
    ap.add_argument("--snapshot-dir", default=str(SNAPSHOT_DIR_DEFAULT))
    ap.add_argument("--env-file", default=os.environ.get("RULES_REFRESH_ENV_FILE", ENV_FILE_DEFAULT))
    ap.add_argument("--min-bytes", type=int, default=MIN_BYTES_DEFAULT)
    ap.add_argument("--report", metavar="ARQUIVO", help="salva o relatorio")
    args = ap.parse_args(argv)

    source_ids = [s.strip() for s in args.sources.split(",") if s.strip()]
    if args.offline and args.source_id:
        source_ids = [args.source_id]
    unknown = [s for s in source_ids if s not in SOURCES]
    if unknown:
        print(f"ERRO: fontes desconhecidas: {unknown}; validas: {sorted(SOURCES)}",
              file=sys.stderr)
        return RC_USAGE
    if args.offline and len(source_ids) != 1:
        print("ERRO: --offline exige exatamente uma fonte (--sources com um id).",
              file=sys.stderr)
        return RC_USAGE

    snap_dir = Path(args.snapshot_dir)
    entries: list[dict] = []
    any_error = False

    # Conexao resolvida UMA vez (sem retry); offline nao precisa de conexao.
    client = ca_id = user_id = None
    if not args.offline:
        try:
            credential = load_credential(args.env_file)
            client, accounts = list_connected_accounts(credential)
            ca_id, user_id = pick_firecrawl_account(accounts)
        except NoConnectionError as ex:
            print(f"ERRO DE CONEXAO (codigo {RC_NO_CONNECTION}): {ex}",
                  file=sys.stderr)
            return RC_NO_CONNECTION

    for sid in source_ids:
        url = SOURCES[sid]
        entry = {
            "source_id": sid, "url": url, "baseline": False, "changed": False,
            "sections": [], "diff": "", "prev_sha": None, "new_sha": None,
            "new_bytes": 0, "method": "offline" if args.offline else "firecrawl",
        }
        try:
            if args.offline:
                raw_md, meta = capture_offline(args.offline)
            else:
                raw_md, meta = capture_firecrawl(
                    url, client, ca_id, user_id)
            check_plausible(raw_md, meta, args.min_bytes)
            new_text = normalize_capture(raw_md)
            old_text, prev_meta = load_snapshot(snap_dir, sid)
            new_sha = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
            entry["new_sha"] = new_sha
            entry["new_bytes"] = len(new_text.encode("utf-8"))
            if old_text is None:
                entry["baseline"] = True
                save_snapshot(snap_dir, sid, new_text, url, entry["method"])
            elif old_text == new_text:
                pass  # sem mudanca: snapshot fica byte-intocado (nada reescrito)
            else:
                entry["changed"] = True
                entry["sections"] = diff_sections(old_text, new_text)
                entry["diff"] = unified_diff(old_text, new_text)
                entry["prev_sha"] = hashlib.sha256(
                    old_text.encode("utf-8")).hexdigest()
                entry["prev_meta"] = prev_meta or {}
                save_snapshot(snap_dir, sid, new_text, url, entry["method"])
        except NoConnectionError as ex:
            # Sem conexao nao e falha de captura: interrompe com codigo 3
            # e instrucao de reconexao (nunca retry infinito).
            print(f"ERRO DE CONEXAO (codigo {RC_NO_CONNECTION}): {ex}",
                  file=sys.stderr)
            return RC_NO_CONNECTION
        except RulesRefreshError as ex:
            any_error = True
            entry["error"] = str(ex)
        entries.append(entry)

    report = build_report(entries)
    print(report)
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"[relatorio salvo em {args.report}]")

    if any_error:
        return RC_BAD_CAPTURE
    if any(e["changed"] for e in entries):
        return RC_CHANGED
    return RC_OK


if __name__ == "__main__":
    sys.exit(main())
