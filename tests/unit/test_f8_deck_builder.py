#!/usr/bin/env python3
"""F8-TESTES: suite unittest do deck-builder (dados reais do repo; sem rede)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "deck"))

import build_deck as B      # noqa: E402
import validate_deck as V3  # noqa: E402

DB = ROOT / "data" / "pocket.sqlite"


class TestF8DeckBuilder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(str(DB))
        cls.con.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def _build(self, ident, days=30):
        main = B.resolve_main(self.con, ident)
        self.assertIsNotNone(main, f"main {ident} não resolvida no catálogo")
        picks, total, nd = B.build_list(self.con, main, days)
        deck = {"id": "test-f8", "name": f"test-{main['canonical_name']}",
                "format": "standard",
                "cards": [{"card_id": p["card_id"], "quantity": p["quantity"]}
                          for p in picks]}
        verdict = V3.validate_deck(deck, B.catalog_projection(self.con))
        return main, picks, total, nd, verdict

    def assertLegal(self, ident):
        main, picks, total, nd, verdict = self._build(ident)
        self.assertEqual(20, total, f"{ident}: lista com {total} cartas")
        self.assertEqual("legal", verdict["legality"],
                         f"{ident}: {verdict['violations']}")
        # a carta principal SEMPRE presente
        self.assertIn(main["id"], [p["card_id"] for p in picks])
        # cada pick tem função mecânica e motivo citável
        for p in picks:
            self.assertIn("function", p)
            self.assertTrue(p.get("reason"))
        return main, picks, nd

    def test_01_mega_gengar_legal(self):
        main, picks, nd = self.assertLegal("Mega Gengar ex")
        self.assertGreaterEqual(nd, 1)

    def test_02_hoopa_legal(self):
        self.assertLegal("Hoopa ex")

    def test_03_greninja_legal(self):
        self.assertLegal("Greninja")

    def test_04_blaziken_legal(self):
        self.assertLegal("Mega Blaziken ex")

    def test_05_altaria_legal(self):
        self.assertLegal("Mega Altaria ex")

    def test_06_carta_inexistente(self):
        self.assertIsNone(B.resolve_main(self.con, "Carta Que Nao Existe 123"))
        self.assertIsNone(B.resolve_main(self.con, "gengar-de-marte"))

    def test_07_main_text_nunca_inventado(self):
        main = B.resolve_main(self.con, "Mega Gengar ex")
        t = B.main_text(self.con, main)
        self.assertIn("Labyrinth of Shadows", t)
        self.assertIn("Trainer", t)     # efeito real da ficha

    def test_08_mec_functions_conhecidas(self):
        card = dict(self.con.execute(
            "SELECT * FROM cards WHERE id='limitless:A4b/373'").fetchone())
        fn, why = B.mechanical_function(card, "")
        self.assertEqual("draw", fn)
        self.assertTrue(why)
        card = dict(self.con.execute(
            "SELECT * FROM cards WHERE id='limitless:A3/144'").fetchone())
        fn, why = B.mechanical_function(card, "")
        self.assertEqual("evolution", fn)

    def test_09_list_mains(self):
        res = B.list_mains(self.con, 30)
        self.assertGreaterEqual(len(res["supported_mains"]), 3)

    def test_10_energy_plan_pocket(self):
        main = B.resolve_main(self.con, "Mega Gengar ex")
        plan, costs = B.energy_plan(self.con, main)
        self.assertIn("Labyrinth of Shadows", plan)
        self.assertIn("Escuridão", plan)
        # nenhuma linha de energia na lista real do Pocket
        self.assertNotIn("energy_basic", [c for c, *_ in
                                          [(p["card_id"],) for p in []]])
        # -teste: lista não tem cartas de energia (corpus prova)
        _, picks, _, _, _ = self._build("Mega Gengar ex")
        for p in picks:
            row = self.con.execute("SELECT category FROM cards WHERE id=?",
                                   (p["card_id"],)).fetchone()
            self.assertNotIn(row["category"], ("energy_basic", "energy_special"))


import sqlite3   # noqa: E402  (pos-runtimes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
