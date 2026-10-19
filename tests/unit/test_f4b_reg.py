"""F4b · TDD: testes de regressao dos 4 achados.

1. parser: regex de set na tabela de versions casa codigo COM hifen (P-A, P-B);
2. loader: image_url da ficha persiste na impressao correspondente;
3. coletor: coverage_report exclui promos (declared=0) do percentual e divergencias
   recem-capturadas... (testes de unidade sem rede: setUp cria DB temporario).
4. relatorio completo: overall_pct nunca >100 quando declared presente.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "integrations" / "limitlesstcg-pocket"))
sys.path.insert(0, str(ROOT / "scripts"))

import parser as P  # noqa: E402
import loader as L  # noqa: E402
import collect_pocket as C  # noqa: E402
import sqlite3  # noqa: E402


HTML_FICHA_PROMO_VERSIONS = """
<div class="card-profile">
<div class="card-image"><img src="https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/A3b/A3b_056_EN_SM.webp"></div>
<span class="card-text-name"><a href="/cards/A3b/56">Eevee ex</a></span>
<p class="card-text-title">Eevee ex - Colorless - 90 HP</p>
<p class="card-text-type">Pokémon - Basic</p>
</div>
<div class="card-prints"><table class="card-prints-versions">
<tr class="current"><td><a>Eevee Grove<span class="prints-table-card-number">#56</span></a></td><td>◊◊◊◊</td></tr>
<tr><td><a href="/cards/P-A/109">Promo-A<span class="prints-table-card-number">#109</span></a></td><td></td></tr>
</table></div>
"""


class TestParserHyphenSets(unittest.TestCase):
    """Bug F4b: regex [A-Z0-9ab]+ nao casava 'P-A' → print rotulado com set da ficha."""

    def test_versions_hyphen_set_resolved(self):
        card = P.parse_card_page(HTML_FICHA_PROMO_VERSIONS, "A3b", "56")
        sets = {v["set"]: v["number"] for v in card["versions"]}
        self.assertEqual(sets.get("P-A"), "109")  # antes vinha 'A3b' (fantasma)
        self.assertEqual(sets.get("A3b"), "56")

    def test_card_image_url_extracted(self):
        card = P.parse_card_page(HTML_FICHA_PROMO_VERSIONS, "A3b", "56")
        self.assertEqual(
            card["image_url"],
            "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/A3b/A3b_056_EN_SM.webp")


class TestLoaderImagePersistence(unittest.TestCase):
    """Aceite 1: image_url preenchida nas impressoes."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE sources(id TEXT PRIMARY KEY, name TEXT, base_url TEXT, kind TEXT,
                                 tier TEXT, policy TEXT, requires_key INTEGER, notes TEXT);
            CREATE TABLE cards(id TEXT PRIMARY KEY, canonical_name TEXT, category TEXT,
                element TEXT, stage TEXT, hp INTEGER, weakness_element TEXT,
                retreat_cost INTEGER, special_rule TEXT, mechanical_hash TEXT,
                is_ex INTEGER, source_id TEXT REFERENCES sources(id), verified_at TEXT,
                validation_status TEXT, evolves_from_id TEXT);
            CREATE TABLE card_attacks(card_id TEXT, name TEXT, energy_cost TEXT,
                damage INTEGER, effect_text TEXT, sort_order INTEGER,
                PRIMARY KEY (card_id, sort_order));
            CREATE TABLE card_abilities(card_id TEXT, name TEXT, kind TEXT,
                effect_text TEXT, PRIMARY KEY (card_id, name));
            CREATE TABLE card_localizations(card_id TEXT, lang TEXT, name TEXT,
                PRIMARY KEY (card_id, lang));
            CREATE TABLE card_prints(id TEXT PRIMARY KEY, card_id TEXT, set_code TEXT,
                number TEXT, rarity TEXT, artist TEXT, image_url TEXT,
                source_id TEXT REFERENCES sources(id), UNIQUE(card_id, set_code, number));
            CREATE TABLE card_evolution_slugs(card_id TEXT PRIMARY KEY, slug TEXT NOT NULL);
            CREATE TABLE card_evolutions(card_id TEXT, pre_evo_card_id TEXT, stage TEXT);
        """)
        self.db.execute("INSERT INTO sources(id) VALUES (?)", (L.SOURCE_ID,))

    def test_image_url_persisted_on_own_print(self):
        card = {
            "set": "A3b", "number": "56", "name": "Eevee ex", "category": "pokemon",
            "stage": "basic", "hp": 90, "element": "colorless", "is_ex": 1,
            "special_rule": "ex rule: x", "image_url": "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/A3b/A3b_056_EN_SM.webp",
            "attacks": [], "abilities": [], "versions": [],
        }
        L.load_card(self.db, card)
        img = self.db.execute(
            "SELECT image_url FROM card_prints WHERE id='A3b#56'").fetchone()[0]
        self.assertEqual(img, card["image_url"])

    def test_reload_fills_missing_image(self):
        card1 = {"set": "A3b", "number": "56", "name": "Eevee ex", "category": "pokemon",
                 "stage": "basic", "hp": 90, "element": "colorless", "is_ex": 1,
                 "attacks": [], "abilities": [], "versions": []}
        L.load_card(self.db, card1)  # sem imagem (coleta antiga)
        img = self.db.execute(
            "SELECT image_url FROM card_prints WHERE id='A3b#56'").fetchone()[0]
        self.assertIsNone(img)
        card2 = dict(card1, image_url="https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/A3b/A3b_056_EN_SM.webp")
        L.load_card(self.db, card2)
        img = self.db.execute(
            "SELECT image_url FROM card_prints WHERE id='A3b#56'").fetchone()[0]
        self.assertEqual(img, card2["image_url"])


class TestCoverageReportSemantics(unittest.TestCase):
    """Aceite 3: sem percentual >100%, promos fora do calculo, divergencias nomeadas."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE expansions(id TEXT PRIMARY KEY, code TEXT UNIQUE, name TEXT,
                release_date TEXT, card_count INTEGER, source_id TEXT, verified_at TEXT);
            CREATE TABLE cards(id TEXT PRIMARY KEY, canonical_name TEXT);
            CREATE TABLE card_prints(id TEXT PRIMARY KEY, card_id TEXT, set_code TEXT,
                number TEXT, rarity TEXT, artist TEXT, image_url TEXT,
                source_id TEXT, UNIQUE(card_id, set_code, number));
        """)
        db = self.db
        db.execute("INSERT INTO expansions VALUES ('A3b','A3b','Eevee Grove','1970-01-01',107,'x','now')")
        db.execute("INSERT INTO expansions VALUES ('P-A','P-A','Promo A','1970-01-01',0,'x','now')")
        # A3b: 107/107 (sem divergencia no estado: segue a LISTAGEM)
        for n in range(1, 108):
            db.execute("INSERT INTO card_prints VALUES (?,?,?,?,?,?,NULL,'x')",
                       (f"A3b#{n}", f"c{n}", "A3b", str(n), None, None))
        # promo: 117 carregados sem contagem declarada
        for n in range(1, 118):
            db.execute("INSERT INTO card_prints VALUES (?,?,?,?,?,?,NULL,'x')",
                       (f"P-A#{n}", f"p{n}", "P-A", str(n), None, None))

    def test_no_percent_above_100_and_promos_excluded(self):
        rep = C.coverage_report(self.db)
        self.assertEqual(rep["overall_pct"], 100.0)
        self.assertLessEqual(rep["overall_pct"], 100.0)
        promo = [e for e in rep["per_set"] if e["set"] == "P-A"]
        self.assertIsNone(promo[0]["coverage_pct"])
        self.assertIsNone(promo[0]["gap"])
        self.assertEqual(rep["total_loaded"], 224)  # 107 counted + 117 promos
        self.assertEqual(rep["total_loaded_counted_sets"], 107)
        self.assertEqual(rep["total_declared"], 107)

    def test_sourced_loaded_above_declared_marked_not_gap(self):
        # A4a-armado: declared 105, loaded 109 → excess, nunca 'gap' negativo
        self.db.execute("INSERT INTO expansions VALUES ('A4a','A4a','Tidal','1970-01-01',105,'x','now')")
        for n in range(1, 110):
            self.db.execute("INSERT OR IGNORE INTO card_prints VALUES (?,?,?,?,?,?,NULL,'x')",
                            (f"A4a#{n}", f"z{n}", "A4a", str(n), None, None))
        self.db.commit()
        rep = C.coverage_report(self.db)
        a4a = [e for e in rep["per_set"] if e["set"] == "A4a"][0]
        self.assertNotIn("gap", a4a)
        self.assertEqual(a4a["excess"], 4)
        self.assertIn("source_discrepancies", rep)
        d = [x for x in rep["source_discrepancies"] if x["set"] == "A4a"][0]
        self.assertEqual(d["classification"], "source_inconsistency")

    def test_promos_not_listed_as_source_discrepancy(self):
        rep = C.coverage_report(self.db)
        sets_disc = [x["set"] for x in rep.get("source_discrepancies", [])]
        self.assertNotIn("P-A", sets_disc)
        self.assertNotIn("P-B", sets_disc)


if __name__ == "__main__":
    unittest.main()
