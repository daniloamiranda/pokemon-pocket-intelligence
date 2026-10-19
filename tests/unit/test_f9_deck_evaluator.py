#!/usr/bin/env python3
"""F9-TESTES: suite unittest do deck-evaluator (dados reais do repo; sem rede)."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "eval"))
sys.path.insert(0, str(ROOT / "scripts" / "deck"))

import evaluate_deck as E          # noqa: E402
import validate_deck as V3         # noqa: E402
import build_deck as B             # noqa: E402

# BUG-002 (F15+, card t_91d448dd): a suite NUNCA aponta db_path para o banco
# canonico — o caminho de producao fica aqui so como FONTE da copia efemera
# (contrato vigiado em docs/TESTING.md secao 4 e pela guarda do BUG-002).
CANONICAL_DB = ROOT / "data" / "pocket.sqlite"
WEIGHTS = ROOT / "skills" / "pokemon-pocket-deck-evaluator" / "weights.json"

# persistence CONTRA PRODUCAO e recusada pelo evaluate() solito: a suite fica
# verde SEM a chave BUG002_ALLOW_PERSIST (a copia efemera Invalida persist=True).
os.environ.pop("BUG002_ALLOW_PERSIST", None)


def _tmp_spec(obj) -> Path:
    """Especificacao temporaria no tmpdir do SISTEMA — nunca dentro de data/
    (o residuo .json de runs anteriores era lixo no diretorio de producao)."""
    fd, name = tempfile.mkstemp(suffix=".json")
    f = Path(name)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj))
    return f


class TestF9Weights(unittest.TestCase):
    def _tmp_weights(self, obj) -> Path:
        f = _tmp_spec(obj)
        self.addCleanup(f.unlink, missing_ok=True)
        return f

    def test_01_pesos_no_arquivo_somam_1(self):
        w = E.load_weights(WEIGHTS)
        self.assertEqual(1.0, sum(d["weight"] for d in w["dimensions"].values()))
        for n in E.DIM_NAMES:
            self.assertIn(n, w["dimensions"])

    def test_02_weights_fora_do_contrato_reprova(self):
        bad = {"version": "x", "dimensions": {n: {"weight": 0.1} for n in E.DIM_NAMES[:-1]}}
        with self.assertRaises(ValueError):
            E.load_weights(self._tmp_weights(bad))

    def test_03_pesos_duplicados_100_reprova(self):
        bad = {"version": "x", "dimensions": {n: {"weight": 0.2} for n in E.DIM_NAMES}}
        with self.assertRaises(ValueError):
            E.load_weights(self._tmp_weights(bad))


def make_ephemeral_copy(target: Path) -> Path:
    """Copia EFEMERA do banco canonico via sqlite3 backup API (leitura do
    original em mode=ro; escrita NUNCA no arquivo real; residuo -wal/-shm da
    copia fica no tmp, fora do data/ de producao)."""
    src = sqlite3.connect(f"file:{CANONICAL_DB}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return target


class TestF9Evaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CANONICAL_DB.is_file():
            # BUG-002: a suite NAO cria data/pocket.sqlite vazio em checkout
            # cru (defeito do setUpClass antigo) — skip com motivo explicito.
            raise unittest.SkipTest(
                "catalogo ausente neste checkout — a suite NUNCA cria "
                "data/pocket.sqlite (BUG-002, F15+); rode "
                "scripts/collect_pocket.py FORA da suite; docs/TESTING.md secao 4")
        cls.tmpdir = tempfile.TemporaryDirectory(prefix="bug002-f9-")
        cls.addClassCleanup(cls.tmpdir.cleanup)
        cls.DB = make_ephemeral_copy(Path(cls.tmpdir.name) / "pocket-copy.sqlite")
        cls.con = sqlite3.connect(str(cls.DB))
        cls.con.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def _eval(self, deck_id="deck-mega-gengar-ex-003", **kw):
        return E.evaluate({"deck_id": deck_id}, persist=False, db_path=self.DB,
                          weights_path=WEIGHTS, **kw)

    def test_10_nota_reproduzivel_mega_gengar(self):
        rep1, rc1 = self._eval()
        rep2, rc2 = self._eval()
        self.assertEqual(0, rc1)
        self.assertEqual(0, rc2)
        self.assertEqual(rep1["score"]["overall"], rep2["score"]["overall"])
        self.assertEqual(70.1, rep1["score"]["overall"])  # golden f9-v1 (F3b: deck de referencia mudou de deck-mega-gengar-ex-001 para -003; o -001 foi removido com trilha audit_logs por violar EVOL-001 com mega_ex coberto — Mega Gengar ex sem Haunter no deck)
        self.assertEqual("heuristic_quality_NOT_winrate", rep1["score"]["score_type"])
        self.assertEqual("f9-v1", rep1["score"]["weights_version"])

    def test_11_dimensoes_10_com_motivo(self):
        rep, rc = self._eval()
        self.assertEqual(0, rc)
        dims = rep["score"]["dimensions"]
        self.assertEqual(10, len(dims))
        self.assertEqual([d["name"] for d in dims], E.DIM_NAMES)
        for d in dims:
            self.assertTrue(d["reason"])
            self.assertGreaterEqual(d["score"], 0.0)
            self.assertLessEqual(d["score"], 100.0)
            self.assertAlmostEqual(d["score"] * d["weight"], d["weighted"], places=1)

    def test_12_deck_ilegal_nao_tem_nota_e_registra_recusa(self):
        # deck sintético ILEGAL: 3 cópias de uma carta (DECK-002 violada) + Pokémon real como principal
        spec = {"name": "sintetico-ilegal", "format": "standard",
                "main_card": {"id": "limitless:B4/103", "canonical_name": "Hoopa ex"},
                "cards": [{"card_id": "limitless:B4/103", "quantity": 2},
                          {"card_id": "limitless:A4b/373", "quantity": 3}]}
        f = _tmp_spec(spec)
        self.addCleanup(f.unlink, missing_ok=True)
        rep, rc = E.evaluate({"spec_file": str(f)}, persist=True, db_path=self.DB,
                             weights_path=WEIGHTS)
        self.assertEqual(4, rc)
        self.assertEqual("ilegal", rep["veredicto"])
        self.assertNotIn("score", rep)          # nenhuma nota para deck ilegal
        self.assertTrue(rep["legality"]["violations"])
        # audit log da recusa
        n = self.con.execute("""SELECT COUNT(*) FROM audit_logs
            WHERE table_name='deck_evaluations' AND reason LIKE '%ilegal%'""").fetchone()[0]
        self.assertGreaterEqual(n, 1)

    def test_20_matchups_top12_selo_real_ou_teorico(self):
        rep, rc = self._eval()
        self.assertEqual(0, rc)
        self.assertEqual(12, len(rep["matchups"]))
        for m in rep["matchups"]:
            self.assertIn(m["evidence"]["kind"], ("real", "teorico"))
            self.assertTrue(m["strengths"] or m["weaknesses"])
            self.assertTrue(m["win_condition"])
            self.assertTrue(m["decisive_cards"])
            if m["evidence"]["kind"] == "real":
                self.assertGreaterEqual(m["evidence"]["sample_size"], 1)
                self.assertIn(m["evidence"]["confidence"], ("low", "medium", "high"))
            else:
                self.assertTrue(m["evidence"]["factors"])
                self.assertIn("torneio", m["evidence"]["note"])
        self.assertGreaterEqual(rep["evidence"]["matchups_real"], 1)
        self.assertGreaterEqual(rep["evidence"]["matchups_teorico"], 1)

    def test_21_matchup_contra_dado_real_da_f7(self):
        rep, rc = self._eval()
        self.assertEqual(0, rc)
        altaria = [m for m in rep["matchups"]
                   if m["archetype_id"] == "mega-altaria-ex-b1-espeon-b3a"][0]
        self.assertEqual("real", altaria["evidence"]["kind"])
        # dado REAL lido de matchups (window_period full): analog hoopa-gengar x altaria-espeon
        row = self.con.execute("""
            SELECT win_rate_a_pct, sample_size FROM matchups
            WHERE window_period='2026-09-09..2026-10-19'
              AND archetype_a='hoopa-ex-b4-mega-gengar-ex-b2b'
              AND archetype_b='mega-altaria-ex-b1-espeon-b3a'""").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["sample_size"], altaria["evidence"]["sample_size"])
        self.assertEqual(row["win_rate_a_pct"], altaria["evidence"]["win_rate_deck_side_pct"])

    def test_30_persistencia_idempotente(self):
        rep, rc = E.evaluate({"deck_id": "deck-hoopa-ex-001"}, persist=True,
                             db_path=self.DB, weights_path=WEIGHTS)
        self.assertEqual(0, rc)
        pid = rep["persistence"]["deck_evaluation_id"]
        row = self.con.execute("SELECT * FROM deck_evaluations WHERE id=?", (pid,)).fetchone()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(rep["score"]["overall"] / 10.0, row["overall_score"], places=2)
        self.assertIn(row["confidence"], ("theoretical", "low", "medium", "high"))
        dims = json.loads(row["dimensions"])
        self.assertEqual(10, len(dims))
        # seeds das 10 dimensões
        n = self.con.execute("SELECT COUNT(*) FROM evaluation_dimensions").fetchone()[0]
        self.assertEqual(10, n)
        # idempotência: re-executar não muda overall
        E.evaluate({"deck_id": "deck-hoopa-ex-001"}, persist=True, db_path=self.DB,
                   weights_path=WEIGHTS)
        row2 = self.con.execute("SELECT overall_score FROM deck_evaluations WHERE id=?",
                                (pid,)).fetchone()
        self.assertEqual(row["overall_score"], row2["overall_score"])

    def test_40_deck_inexistente(self):
        rep, rc = self._eval(deck_id="deck-nao-existe-999")
        self.assertEqual(2, rc)
        self.assertEqual("deck_inexistente", rep["veredicto"])

    def test_50_relatorio_gengar_vs_meta_top12(self):
        rep, rc = self._eval()
        self.assertEqual(0, rc)
        self.assertTrue(rep["comparison"]["closest_meta_archetype"])
        self.assertIn("positioning", rep["comparison"])
        self.assertIn("NÃO COMPARÁVEIS", rep["comparison"]["positioning"])
        self.assertEqual(0, rep["deck"]["main_inferred"])

    def test_51_confidence_e_selo_disclaimer(self):
        rep, rc = self._eval()
        self.assertEqual(0, rc)
        self.assertIn(rep["evidence"]["confidence"], ("theoretical", "low", "medium", "high"))
        self.assertEqual(3, len(rep["disclaimers"]))
        self.assertTrue(any("heuristic_quality_NOT_winrate" in d for d in rep["disclaimers"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
