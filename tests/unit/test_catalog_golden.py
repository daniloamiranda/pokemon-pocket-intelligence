"""Testes de regressao do catalogo F4 (cartas/paginas douradas)."""
import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "integrations" / "limitlesstcg-pocket"))
import parser as pm  # noqa: E402

GOLDEN = json.loads((ROOT / "tests" / "golden" / "limitless_pocket_golden.json").read_text(encoding="utf-8"))


def _golden_card(g):
    return next(c for c in GOLDEN["cards"] if c["canonical_name"] == g)


class CatalogGoldenTest(unittest.TestCase):
    def test_golden_file_exists(self):
        self.assertEqual(GOLDEN["source"], "pocket.limitlesstcg.com")
        self.assertGreaterEqual(len(GOLDEN["cards"]), 4)

    def test_mega_gengar_golden_reference(self):
        g = _golden_card("Mega Gengar ex")
        self.assertEqual(g["element"], "darkness")
        self.assertEqual(g["hp"], 210)
        self.assertEqual(g["stage"], "mega_ex")
        self.assertEqual(g["attack"]["damage"], 120)
        self.assertEqual(g["attack"]["name"], "Labyrinth of Shadows")
        self.assertEqual(len(g["expected_prints"]), 5)

    def test_parse_card_page_matches_golden_mega_gengar(self):
        fixture = ROOT / "tests" / "golden" / "fixtures_card_B4b_141.html"
        if not fixture.exists():
            self.skipTest("fixture de HTML ausente")
        html = fixture.read_text(encoding="utf-8")
        card = pm.parse_card_page(html, "B4b", "141")
        g = _golden_card("Mega Gengar ex")
        self.assertEqual(card["name"], g["canonical_name"])
        self.assertEqual(card["element"], g["element"])
        self.assertEqual(card["hp"], g["hp"])
        self.assertEqual(card["stage"], g["stage"])
        self.assertEqual(card["attacks"][0]["name"], g["attack"]["name"])

    def test_db_canonical_state_if_present(self):
        db_path = ROOT / "data" / "pocket.sqlite"
        if not db_path.exists():
            self.skipTest("banco canonico ausente")
        db = sqlite3.connect(db_path)
        cards = db.execute("SELECT id FROM cards WHERE canonical_name='Mega Gengar ex'").fetchall()
        self.assertEqual(len(cards), 1)
        prints = db.execute("SELECT COUNT(*) FROM card_prints WHERE card_id=?",
                            (cards[0][0],)).fetchone()[0]
        self.assertEqual(prints, 5)
        dup = db.execute("SELECT set_code, number, COUNT(*) c FROM card_prints"
                         " GROUP BY set_code, number HAVING c > 1").fetchall()
        self.assertEqual(dup, [])
        db.close()

    def test_mechanical_hash_shape(self):
        g = _golden_card("Mega Gengar ex")
        from loader import compute_mechanical_hash
        card = {
            "name": g["canonical_name"], "category": g["category"], "element": g["element"],
            "stage": g["stage"], "hp": g["hp"], "weakness_element": g["weakness_element"],
            "retreat_cost": g["retreat_cost"], "special_rule": g["rule"], "is_ex": g["is_ex"],
            "attacks": [g["attack"]], "abilities": [],
        }
        h = compute_mechanical_hash(card)
        self.assertEqual(len(h), 64)
        self.assertEqual(h, compute_mechanical_hash(card))


if __name__ == "__main__":
    unittest.main()
