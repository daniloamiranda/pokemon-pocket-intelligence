"""Testes unitarios do validador de legalidade (F3) — skill pokemon-pocket-rules.

Casos obrigatorios do card t_d984f234:
1. deck_SIZE != 20 reprovado (DECK-001)
2. mais de 2 copias reprovado (DECK-002)
3. carta inexistente no catalogo reprovada (DECK-003)
4. carta ilegal no formato reprovada (DECK-004)
5. evolucao sem pre-requisito reprovada (EVOL-001)
6. restricao especifica reprovada (REST-001)
7. deck legal de fixture aprovado, com regras citando no veredicto
"""

import json
import sys
import unittest
from pathlib import Path

WORKSPACE = Path("/workspace/ARCOS/projetos/pokemon-pocket-intelligence")
sys.path.insert(0, str(WORKSPACE / "scripts"))

from validate_deck import validate_deck, RULE_IDS  # noqa: E402

CATALOG = json.loads((WORKSPACE / "tests/fixtures/catalog_fixture.json").read_text())
DECKS = json.loads((WORKSPACE / "tests/fixtures/decks_fixture.json").read_text())["cases"]


def find(deck_id):
    return DECKS[deck_id]


class TestDeckValidator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legal_verdict = validate_deck(find("legal_deck"), CATALOG)

    def test_registry_has_all_rules(self):
        expected = {"DECK-001", "DECK-002", "DECK-003", "DECK-004", "EVOL-001", "EVOL-002", "REST-001"}
        self.assertEqual(set(RULE_IDS), expected)

    def test_legal_deck_approved_with_rules_cited(self):
        self.assertEqual(self.legal_verdict["legality"], "legal")
        self.assertEqual(self.legal_verdict["violations"], [])
        # Aceitacao 4: deck legal precisa CITAR as regras que o permitem
        self.assertIn("DECK-001", self.legal_verdict["satisfied_rules"])
        self.assertIn("DECK-002", self.legal_verdict["satisfied_rules"])
        self.assertIn("EVOL-001", self.legal_verdict["satisfied_rules"])

    def test_deck_size_not_20_rejected(self):
        v = validate_deck(find("violation_deck_size"), CATALOG)
        self.assertEqual(v["legality"], "illegal")
        self.assertIn("DECK-001", {x["rule_id"] for x in v["violations"]})

    def test_3_copies_rejected(self):
        v = validate_deck(find("violation_copies_limit"), CATALOG)
        self.assertEqual(v["legality"], "illegal")
        self.assertIn("DECK-002", {x["rule_id"] for x in v["violations"]})

    def test_card_not_in_catalog_rejected(self):
        v = validate_deck(find("violation_card_not_in_catalog"), CATALOG)
        ids = {x["rule_id"] for x in v["violations"]}
        self.assertEqual(v["legality"], "illegal")
        self.assertIn("DECK-003", ids)

    def test_card_illegal_in_format_rejected(self):
        v = validate_deck(find("violation_card_illegal_in_format"), CATALOG)
        ids = {x["rule_id"] for x in v["violations"]}
        self.assertEqual(v["legality"], "illegal")
        self.assertIn("DECK-004", ids)

    def test_evolution_without_pre_evo_rejected(self):
        v = validate_deck(find("violation_evolution_without_pre_evo"), CATALOG)
        ids = {x["rule_id"] for x in v["violations"]}
        self.assertEqual(v["legality"], "illegal")
        self.assertIn("EVOL-001", ids)

    def test_restriction_deck_limit_rejected(self):
        deck = {
            "id": "fx-deck-rest-limit",
            "format": "standard",
            "cards": [
                {"card_id": "mega-art-ex-01", "quantity": 2},  # special_rule.deck_limit = 1
            ] + [
                {"card_id": "gastly-A2", "quantity": 2},
                {"card_id": "haunter-A2", "quantity": 2},
                {"card_id": "cynthia-EX", "quantity": 2},
                {"card_id": "red-GM", "quantity": 2},
                {"card_id": "misty-A1", "quantity": 2},
                {"card_id": "cynthia-EX", "quantity": 2},
                {"card_id": "red-GM", "quantity": 2},
                {"card_id": "misty-A1", "quantity": 2},
                {"card_id": "haunter-A2", "quantity": 2},
            ],
        }
        v = validate_deck(deck, CATALOG)
        ids = {x["rule_id"] for x in v["violations"]}
        self.assertEqual(v["legality"], "illegal")
        self.assertIn("REST-001", ids)

    def test_legal_deck_size_is_20(self):
        total = sum(c["quantity"] for c in find("legal_deck")["cards"])
        self.assertEqual(total, 20)


if __name__ == "__main__":
    unittest.main()
