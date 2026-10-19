#!/usr/bin/env python3
"""Card t_fafb754f · teste/guarda do rules_refresh (manutencao sob demanda).

Cobertura exigida pelo card:
  (a) mudanca detectada -> codigo 10 + relatorio com secoes afetadas;
  (b) sem mudanca -> codigo 0, snapshot intacto;
  (c) primeira captura -> codigo 0 como linha de base;
  (d) captura vazia / curta / sem estrutura -> codigo 4 (erro declarado,
      NUNCA interpretado como "sem mudanca", NUNCA grava snapshot);
  (e) sem conexao Composio/Firecrawl -> codigo 3 com instrucao de reconexao
      (sem retry infinito, sem rede);
  (f) GUARDA: validate_deck.py, build_deck.py e evaluate_deck.py continuam
      SEM qualquer referencia a rede/Firecrawl/Composio (e sem importar o
      rules_refresh — o oposto tambem valeria: runtime chamar manutencao).

Todos os casos rodam SEM REDE (--offline injeta captura; o caso (e) falha na
credencial antes de qualquer SDK/rede) e em diretorios temporarios (nunca na
producao do repo)."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import rules_refresh as RR  # noqa: E402

OLD_TEXT = (
    "## Section one\n"
    "alpha line\n"
    "beta line\n"
    "\n"
    "## Section two\n"
    "gamma line (Pokemon)"  # sem \n final (normalizacao corta \n de cauda)
)
NEW_TEXT_CHANGED = (
    "## Section one\n"
    "alpha line\n"
    "beta line\n"
    "\n"
    "## Section two\n"
    "gamma line agora diferente (Pokemon)\n"
    "delta line novo"      # sem \n final
)
# > 3000 chars, contem "Pokemon" (sanity ok) e NENHUM header '## '
# -> normalize_capture deve reprovar por estrutura
NO_STRUCTURE_TEXT = "Pokemon conteudo sem estrutura de secao. " * 200

RC = {"ok": 0, "usage": 2, "no_conn": 3, "bad_capture": 4, "changed": 10}

RUNTIME_FILES = (
    "scripts/validate_deck.py",
    "scripts/deck/build_deck.py",
    "scripts/eval/evaluate_deck.py",
)
FORBIDDEN_RUNTIME = (
    "firecrawl", "composio", "rules_refresh",
    "import requests", "import urllib", "from urllib", "import socket",
    "import httpx", "import http.client", "from http", "urlopen",
    "requests.", "urllib.", "socket.", "http://", "https://",
)


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _run_main(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = RR.main(argv)
    return rc, buf.getvalue()


class TestFluxoSnapshot(unittest.TestCase):
    """Fluxo offline: linha de base, sem mudanca, mudanca e capturas ruins."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.snap = self.tmp / "snaps"
        self.captura = self.tmp / "captura.md"
        # textos sinteticos < 3000 bytes: plausibilidade relaxada nos fluxos
        # (os casos d1-d3 exercitam o limiar default a parte)
        self.minb = ["--min-bytes", "10"]

    def test_a_primeira_captura_e_linha_de_base_rc0(self):
        _write(self.captura, OLD_TEXT)
        rc, out = _run_main(["--offline", str(self.captura), "--source-id",
                             "faq-gameplay", "--snapshot-dir", str(self.snap)]
                            + self.minb)
        self.assertEqual(RC["ok"], rc)
        self.assertIn("primeira captura", out)
        txt, meta = RR.snapshot_paths(self.snap, "faq-gameplay")
        self.assertTrue(txt.is_file())
        self.assertTrue(meta.is_file())
        m = json.loads(meta.read_text(encoding="utf-8"))
        self.assertEqual(m["method"], "offline")
        self.assertIsNone(m["toolkit_version"])
        self.assertEqual(m["sha256"], hashlib.sha256(
            OLD_TEXT.encode("utf-8")).hexdigest())

    def test_b_sem_mudanca_rc0_snapshot_intacto(self):
        _write(self.captura, OLD_TEXT)
        rc1, _ = _run_main(["--offline", str(self.captura), "--source-id",
                            "faq-battle", "--snapshot-dir", str(self.snap)]
                           + self.minb)
        txt_path, meta_path = RR.snapshot_paths(self.snap, "faq-battle")
        antes = txt_path.read_text(encoding="utf-8")
        meta_antes = meta_path.read_text(encoding="utf-8")
        rc2, out = _run_main(["--offline", str(self.captura), "--source-id",
                              "faq-battle", "--snapshot-dir", str(self.snap)]
                             + self.minb)
        self.assertEqual(RC["ok"], rc1)
        self.assertEqual(RC["ok"], rc2)
        self.assertIn("sem mudanca", out)
        self.assertNotIn("MUDANCA", out)
        self.assertEqual(antes, txt_path.read_text(encoding="utf-8"))
        self.assertEqual(meta_antes, meta_path.read_text(encoding="utf-8"))

    def test_c_mudanca_detectada_rc10_com_secoes_e_diff(self):
        _write(self.captura, OLD_TEXT)
        rc_base, _ = _run_main(["--offline", str(self.captura), "--source-id",
                                "faq-battle", "--snapshot-dir", str(self.snap)]
                               + self.minb)
        _write(self.captura, NEW_TEXT_CHANGED)
        rc, out = _run_main(["--offline", str(self.captura), "--source-id",
                             "faq-battle", "--snapshot-dir", str(self.snap)]
                            + self.minb)
        self.assertEqual(RC["ok"], rc_base)
        self.assertEqual(RC["changed"], rc)
        self.assertIn("MUDANCA DETECTADA", out)
        self.assertIn("e alterado automaticamente", out)
        self.assertIn('"Section two"', out)    # secao afetada nomeada
        self.assertNotIn('"Section one"', out)  # a ilesa nao e listada
        self.assertIn("```diff", out)          # diff unificado presente
        self.assertIn("+gamma line agora diferente", out)
        m = json.loads(RR.snapshot_paths(self.snap, "faq-battle")[1]
                       .read_text(encoding="utf-8"))
        self.assertEqual(m["sha256"], hashlib.sha256(
            NEW_TEXT_CHANGED.encode("utf-8")).hexdigest())

    def test_d1_captura_vazia_rc4_sem_snapshot(self):
        _write(self.captura, "")
        rc, out = _run_main(["--offline", str(self.captura), "--source-id",
                             "faq-battle", "--snapshot-dir", str(self.snap)])
        self.assertEqual(RC["bad_capture"], rc)
        self.assertIn("ERRO", out)
        self.assertFalse((self.snap / "faq-battle.txt").exists(),
                         "captura reprovada NUNCA vira snapshot")

    def test_d2_captura_abaixo_do_plausivel_rc4(self):
        _write(self.captura, "## x\nconteudo curto demais\n")
        rc, out = _run_main(["--offline", str(self.captura), "--source-id",
                             "faq-battle", "--snapshot-dir", str(self.snap)])
        self.assertEqual(RC["bad_capture"], rc)
        self.assertIn("abaixo do plausivel", out)

    def test_d3_captura_sem_estrutura_rc4(self):
        _write(self.captura, NO_STRUCTURE_TEXT)
        rc, out = _run_main(["--offline", str(self.captura), "--source-id",
                             "faq-battle", "--snapshot-dir", str(self.snap)])
        self.assertEqual(RC["bad_capture"], rc)
        self.assertIn("header", out)

    def test_d4_http_nao_200_reprovado(self):
        with self.assertRaises(RR.CaptureError) as cm:
            RR.check_plausible("x" * 5000, {"statusCode": 403}, 3000)
        self.assertIn("403", str(cm.exception))

    def test_e_offline_exige_uma_fonte(self):
        rc, _ = _run_main(["--offline", str(self.captura),
                           "--snapshot-dir", str(self.snap)])
        self.assertEqual(RC["usage"], rc)


class TestUnidadesPuras(unittest.TestCase):
    """normalize/diff secoes — o relatorio fala por secoes, nao por linhas soltas."""

    def test_normalize_corta_nav_e_crlf(self):
        nav = "[Skip to main content](https://x)\n### Articles in this section\n- a\n"
        body = "## Real FAQ\nlinha 1\r\nlinha 2\n"
        out = RR.normalize_capture(nav + body)
        self.assertTrue(out.startswith("## Real FAQ"))
        self.assertNotIn("\r", out)
        self.assertNotIn("Articles in this section", out)

    def test_sem_header_algum_reprova(self):
        with self.assertRaises(RR.CaptureError):
            RR.normalize_capture("so texto corrido\nsem secoes\n")

    def test_diff_reporta_secao_afetada(self):
        secs = RR.diff_sections(OLD_TEXT, NEW_TEXT_CHANGED)
        self.assertEqual(1, len(secs))
        sec, plus, minus = secs[0]
        self.assertEqual("Section two", sec)
        self.assertGreaterEqual(plus, 2)
        self.assertGreaterEqual(minus, 1)


class TestSemConexao(unittest.TestCase):
    """(e) sem conexao = codigo 3 + instrucao, ANTES de qualquer rede."""

    def test_sem_credencial_rc3_com_instrucao(self):
        env = dict(os.environ)
        env.pop("COMPOSIO_API_KEY", None)  # sessao nao empresta a chave
        env.pop("RULES_REFRESH_ENV_FILE", None)
        fake_env = self._tmp_env_sem_chave()
        argv = ["--sources", "faq-gameplay", "--snapshot-dir",
                str(self.snapdir), "--env-file", str(fake_env)]
        with mock.patch.object(RR.os, "environ", env):
            buf_err = io.StringIO()
            with contextlib.redirect_stderr(buf_err):
                rc = RR.main(argv)
        self.assertEqual(RC["no_conn"], rc)
        err = buf_err.getvalue()
        self.assertIn("ERRO DE CONEXAO", err)
        self.assertTrue(("reconect" in err.lower()) or ("exporte" in err.lower()),
                        f"instrucao de reconexao ausente: {err!r}")

    def test_env_file_sem_chave_rc3(self):
        env = dict(os.environ)
        env.pop("COMPOSIO_API_KEY", None)
        env.pop("RULES_REFRESH_ENV_FILE", None)
        fake_env = self._tmp_env_com_outras_chaves()
        argv = ["--sources", "faq-battle", "--snapshot-dir",
                str(self.snapdir), "--env-file", str(fake_env)]
        with mock.patch.object(RR.os, "environ", env):
            rc = RR.main(argv)
        self.assertEqual(RC["no_conn"], rc)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.snapdir = self.tmp / "snaps"

    def _tmp_env_sem_chave(self) -> Path:
        p = self.tmp / "env_sem_chave"
        p.write_text("OUTRA_VAR=1\n# COMPOSIO_API_KEY comentada nao vale\n",
                     encoding="utf-8")
        return p

    def _tmp_env_com_outras_chaves(self) -> Path:
        p = self.tmp / "env_sem_composio"
        p.write_text("FIRECRAWL_API_KEY=valor-irrelevante-para-este-teste\n",
                     encoding="utf-8")
        return p


class TestGuardaRuntimeOffline(unittest.TestCase):
    """(f) O runtime do deck NAO conhece rede — grep de guarda do card."""

    def test_runtime_sem_referencia_a_rede(self):
        ofensores = []
        for rel in RUNTIME_FILES:
            path = ROOT / rel
            self.assertTrue(path.is_file(), f"arquivo sumiu: {rel}")
            for i, ln in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                low = ln.lower()
                for pat in FORBIDDEN_RUNTIME:
                    if pat in low:
                        ofensores.append(f"{rel}:{i} padrao '{pat}': "
                                         f"{ln.strip()[:80]}")
        self.assertEqual(
            [], ofensores,
            "validate_deck/build_deck/evaluate_deck devem ser 100% offline; "
            "manutencao externa e do rules_refresh.py (sob demanda manual):\n"
            + "\n".join(ofensores))

    def test_maintainer_usa_sdk_e_nao_libs_de_rede_diretas(self):
        src = (ROOT / "scripts" / "rules_refresh.py").read_text(encoding="utf-8")
        self.assertIn("from composio import Composio", src)
        self.assertIn("COMPOSIO_API_KEY", src)  # credencial por env, nao argv
        for proibido in ("import requests", "import urllib", "import socket",
                         "import httpx", "urlopen"):
            self.assertNotIn(proibido, src)

    def test_scrape_exige_user_id_e_connected_account(self):
        """Contrato da API (code 1811, provado em producao 19/10/2026):
        connected account sem user_id e rejeitada. O script envia o par."""
        src = (ROOT / "scripts" / "rules_refresh.py").read_text(encoding="utf-8")
        self.assertIn("user_id=user_id", src)
        self.assertIn("connected_account_id=ca_id", src)

    def test_nenhuma_agendacao_no_maintainer(self):
        """Nunca cron: nada de scheduler/agendamento embutido."""
        src = (ROOT / "scripts" / "rules_refresh.py").read_text(encoding="utf-8")
        for padrao in ("crontab", "schedule.", "APScheduler", "celery"):
            self.assertNotIn(padrao, src)


if __name__ == "__main__":
    unittest.main()
