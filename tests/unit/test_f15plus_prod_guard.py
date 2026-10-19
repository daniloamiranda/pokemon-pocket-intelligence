#!/usr/bin/env python3
"""F15+ BUG-002 · guarda anti-regressao: a SUITE nunca escreve em producao
(card t_91d448dd, R2 — contrato do docs/TESTING.md secao 4 + 9).

Classe do defeito: tests/unit/test_f9_deck_evaluator.py chamava
E.evaluate(..., persist=True, db_path=producao) — cada run da suite alterava
3 linhas de producao (audit_logs ator 'tony_stark:f9'; deck_evaluations
upsertada com updated_at novo). Trilha de auditoria poluida e md5 do arquivo
oscilando por churn de WAL sem mudanca logica. E o setUpClass conectava
sqlite3.connect() comum no caminho canonico: em checkout cru CRIAVA um
data/pocket.sqlite VAZIO (defeito collateral observado no aceite BUG-001).

Criterio do card (aceite): suite verde com producao byte-intocada — md5
antes == depois de um run completo; fail-fast de open_eval_db() vigiado em
tmp (nunca tocando producao). O escopo do run completo aqui e a SUITE F9
(test_f9_deck_evaluator) NAO esta guarda — subprocess que se contivesse
seria recursao infinita (prova corrigida no rascunho).

Vigiado aqui (SOMENTE LEITURA sobre producao):
  (1) open_eval_db fail-fast com banco ausente — prova em tmp, a AUSENCIA
      do arquivo depois da chamada e a prova (nada fabricado);
  (2) persist=True no caminho canonico recusado SEM BUG002_ALLOW_PERSIST
      (e a recusa NAO altera producao);
  (3) run completo da suite F9 deixa data/pocket.sqlite byte-intocada
      (md5 antes == depois) e sem residuo -wal/-shm criado em data/;
  (4) fonte sem o padrao da classe: evaluator com open_eval_db + guarda de
      persist canonico, suite sem persist contra o canonico e nenhum teste
      setando BUG002_ALLOW_PERSIST=1.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "eval"))

PROD_DB = ROOT / "data" / "pocket.sqlite"
VENV_PY = Path("/opt/data/f5_venv/bin/python3")
INTERP = str(VENV_PY) if VENV_PY.is_file() else sys.executable


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TestF15PlusProdGuard(unittest.TestCase):
    """A classe 'suite escreve em producao' fica extinta e vigiada aqui."""

    @classmethod
    def setUpClass(cls):
        if os.environ.get("BUG002_ALLOW_PERSIST") == "1":
            raise unittest.SkipTest(
                "BUG002_ALLOW_PERSIST=1 no ambiente — guarda BUG-002 fica sem "
                "sentido sob override deliberado; rode a suite sem a chave")

    # -- (1) fail-fast com banco ausente NUNCA cria o arquivo
    def test_01_open_eval_db_failfast_sem_criar_arquivo(self):
        import evaluate_deck as E
        nonexistent = Path(tempfile.mkdtemp(prefix="bug002-guard-")) / "nao-existe.sqlite"
        self.assertFalse(nonexistent.is_file())
        with self.assertRaises(RuntimeError):
            E.evaluate({"deck_id": "x"}, persist=False, db_path=nonexistent)
        self.assertFalse(nonexistent.is_file(),
                         "sqlite foi criado vazio — defeito BUG-002 de volta")

    # -- (2) persist no canonico recusado SEM a deliberacao humana
    def test_02_open_eval_db_recusa_persist_canonico_sem_chave(self):
        if not PROD_DB.is_file():
            self.skipTest("catalogo ausente neste checkout (a suite NUNCA "
                          "cria o banco — BUG-002)")
        import evaluate_deck as E
        os.environ.pop("BUG002_ALLOW_PERSIST", None)
        md5_antes = _md5(PROD_DB)
        with self.assertRaises(RuntimeError):
            E.evaluate({"deck_id": "deck-hoopa-ex-001"}, persist=True,
                       db_path=PROD_DB)
        self.assertEqual(md5_antes, _md5(PROD_DB),
                         "a RECUSA alterou producao — inaceitavel")

    # -- (2b) idem provado SEM depender de producao (copia tmp como 'canonico')
    def test_03_recusa_persist_canonico_via_copia_tmp(self):
        import evaluate_deck as E
        tmpdb = Path(tempfile.mkdtemp(prefix="bug002-guard3-")) / "pocket.sqlite"
        con = sqlite3.connect(str(tmpdb))
        con.close()
        original = E.DB_PATH
        try:
            E.DB_PATH = tmpdb                 # caminho 'canonico' da copia
            os.environ.pop("BUG002_ALLOW_PERSIST", None)
            with self.assertRaises(RuntimeError):
                E.evaluate({"deck_id": "x"}, persist=True, db_path=tmpdb)
        finally:
            E.DB_PATH = original

    # -- (3) run COMPLETO da suite F9: producao byte-intocada, sem residuo
    def test_04_suite_completa_producao_byte_intocada(self):
        if not PROD_DB.is_file():
            self.skipTest("catalogo ausente neste checkout — nada a proteger")
        wal = Path(str(PROD_DB) + "-wal")
        shm = Path(str(PROD_DB) + "-shm")
        md5_antes = _md5(PROD_DB)
        wal_antes = wal.stat().st_size if wal.is_file() else -1
        shm_todos = sorted(p.name for p in PROD_DB.parent.glob("*.sqlite-shm"))
        proc = subprocess.run(
            [INTERP, "-m", "unittest", "tests.unit.test_f9_deck_evaluator", "-v"],
            capture_output=True, text=True, timeout=560, cwd=str(ROOT),
            env={**os.environ, "BUG002_ALLOW_PERSIST": ""})
        md5_depois = _md5(PROD_DB)
        wal_depois = wal.stat().st_size if wal.is_file() else -1
        shm_todos_depois = sorted(p.name for p in PROD_DB.parent.glob("*.sqlite-shm"))
        self.assertEqual(0, proc.returncode,
                         f"suite F9 nao verde no interprete {INTERP}:\n"
                         f"{proc.stderr[-2000:]}")
        self.assertEqual(md5_antes, md5_depois,
                         f"data/pocket.sqlite ALTERADO pelo run da suite "
                         f"(BUG-002 de volta): antes={md5_antes} depois={md5_depois}")
        self.assertEqual(wal_antes if wal_antes >= 0 else 0,
                         wal_depois if wal_depois >= 0 else 0,
                         "residuo -wal em data/ alterado pelo run da suite")
        self.assertEqual(shm_todos, shm_todos_depois,
                         "residuo -shm novo em data/ criado pelo run da suite")

    # -- (4) fonte sem o padrao que causou a classe
    def test_05_fonte_sem_padrao_bug002(self):
        ed = (ROOT / "scripts" / "eval" / "evaluate_deck.py").read_text(encoding="utf-8")
        tf = (ROOT / "tests" / "unit" / "test_f9_deck_evaluator.py").read_text(encoding="utf-8")
        self.assertIn("def open_eval_db", ed,
                      "evaluate_deck.py perdeu a abertura controlada BUG-002")
        self.assertIn("BUG002_ALLOW_PERSIST", ed,
                      "guarda de persist canonico ausente do evaluator")
        self.assertNotRegex(ed, r'sqlite3\.connect\(str\(db_path or DB_PATH\)\)',
                            "connect comum de volta — fail-fast extinto")
        self.assertNotIn("persist=True, db_path=CANONICAL_DB", tf,
                         "suite voltou a persist=True no canonico")
        self.assertIn("db_path=self.DB", tf,
                      "suite perdeu o fixture de copia efemera (BUG-002)")
        self.assertNotIn('BUG002_ALLOW_PERSIST", "1"', tf,
                         "nenhum teste pode setar BUG002_ALLOW_PERSIST=1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
