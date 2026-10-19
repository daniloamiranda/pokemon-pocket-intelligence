#!/usr/bin/env python3
"""F3b-TESTES: EVOL-001 cobre stage mega_ex — regressao do 'Mega ex orfao'.

Card t_87df73e6. O defeito: a checagem EVOL-001 do validador so exigia
pre-requisito para stage in ('stage1','stage2') — 'mega_ex' NAO era coberto.
O deck-mega-gengar-ex-001 antigo (Mega Gengar ex sem Haunter no deck) passava
como legal apenas porque a regra nao alcancava o stage mega.

Casos OBRIGATORIOS do card:
  (i)   deck feito a mao com Mega Gengar ex SEM Gastly/Haunter -> EVOL-001 violada
        (falhava ANTES do fix: aprovado como legal);
  (ii)  deck completo (Gastly + Haunter + Mega Gengar ex) -> LEGAL, com EVOL-001
        citada em satisfied_rules;
  (iii) mega com pre amarrado a uma identidade A ('haunter-fantasma') e o deck
        trazendo outra identidade B do mesmo nome ('haunter-outro') -> LEGAL
        (mesma semantica por nome da F8b para stage2);
  (iv)  mega orfao onde NEM id NEM nome do pre existem no deck -> EVOL-001 violada;
  (v)   deck real persistido (ultimo deck-mega-gengar-ex-*): todo mega do deck
        tem o pre-requisito pelo nome (linha completa).
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_deck as V3  # noqa: E402

DB = ROOT / "data" / "pocket.sqlite"
CATALOG = json.loads((ROOT / "tests/fixtures/catalog_fixture.json").read_text())


def dek(name, cards):
    return {"id": name, "name": name, "format": "standard", "cards": cards}


# Completar 20 cartas do fixture: 9 x 2 = 18 (nota: vulpix-GG/retired sao
# legal:false — so entram no deck do caso orfao, onde outras violacoes coexistem)
FILLER_FIXTURE = [{"card_id": cid, "quantity": 2} for cid in (
    "cynthia-EX", "red-GM", "misty-A1", "wally-A2", "sabrina-A2", "iono-A2",
    "profresearch-A2", "vulpix-GG", "retired-promo-001",
)]  # 9 x 2 = 18

# Apenas treinadores legais: 7 x 2 = 14 (para decks que precisam ficar LIMPOS)
FILLER_CLEAN = [{"card_id": cid, "quantity": 2} for cid in (
    "cynthia-EX", "red-GM", "misty-A1", "wally-A2", "sabrina-A2", "iono-A2",
    "profresearch-A2",
)]  # 7 x 2 = 14


def synth_catalog(with_haunter=True):
    """Catalogo sintetico: mega com pre amarrado a um id ('haunter-fantasma')
    que existe no catalogo sob o nome 'Haunter'; com_haunter controla se o deck
    pode usar uma SEGUNDA identidade do mesmo nome ('haunter-outro')."""
    cards = [
        {"card_id": "mega-fix", "name": "Mega Test ex", "category": "pokemon",
         "stage": "mega_ex", "evolves_from": "haunter-fantasma",
         "legal": True, "legal_formats": ["standard"]},
        {"card_id": "gastly-fix", "name": "Gastly", "category": "pokemon",
         "stage": "basic", "evolves_from": None,
         "legal": True, "legal_formats": ["standard"]},
        {"card_id": "haunter-fantasma", "name": "Haunter", "category": "pokemon",
         "stage": "stage1", "evolves_from": "gastly-fix",
         "legal": True, "legal_formats": ["standard"]},
    ]
    if with_haunter:
        # identidade DIFERENTE do id declarado em evolves_from — resolucao por nome
        cards.append({"card_id": "haunter-outro", "name": "Haunter", "category": "pokemon",
                      "stage": "stage1", "evolves_from": "gastly-fix",
                      "legal": True, "legal_formats": ["standard"]})
    cards += [{"card_id": f"tr{i}", "name": f"Treinador {i}", "category": "trainer",
               "stage": "basic", "evolves_from": None,
               "legal": True, "legal_formats": ["standard"]} for i in range(10)]
    return {"cards": cards}


class TestF3bEvol001MegaEx(unittest.TestCase):
    """Os casos obrigatorios do card t_87df73e6."""

    def _violated(self, deck, catalog=None):
        v = V3.validate_deck(deck, catalog or CATALOG)
        return v, {x["rule_id"] for x in v["violations"]}

    def test_i_mega_orphan_rejected(self):
        # (i) Mega Gengar ex SEM Gastly/Haunter no deck -> EVOL-001 (antes: legal!)
        deck = dek("f3b-i", [
            {"card_id": "mega-gengar-f3b", "quantity": 2},
        ] + FILLER_FIXTURE)
        self.assertEqual(20, sum(c["quantity"] for c in deck["cards"]))
        v, ids = self._violated(deck)
        self.assertEqual("illegal", v["legality"])
        self.assertIn("EVOL-001", ids)
        evol = [x for x in v["violations"] if x["rule_id"] == "EVOL-001"]
        self.assertTrue(any("mega_ex" in x["message"] for x in evol), v["violations"])

    def test_ii_full_mega_line_legal(self):
        # (ii) linha completa Gastly -> Haunter -> Mega Gengar ex -> LEGAL
        deck = dek("f3b-ii", [
            {"card_id": "mega-gengar-f3b", "quantity": 2},
            {"card_id": "haunter-A2", "quantity": 2},
            {"card_id": "gastly-A2", "quantity": 2},
        ] + FILLER_CLEAN)
        self.assertEqual(20, sum(c["quantity"] for c in deck["cards"]))
        v, ids = self._violated(deck)
        self.assertEqual("legal", v["legality"], v["violations"])
        self.assertEqual([], v["violations"])
        self.assertIn("EVOL-001", v["satisfied_rules"])

    def test_iii_mega_pre_by_name_accepted(self):
        # (iii) pre amarrado ao id A; deck traz identidade B do mesmo nome
        deck = dek("f3b-iii", [
            {"card_id": "mega-fix", "quantity": 2},
            {"card_id": "haunter-outro", "quantity": 2},
            {"card_id": "gastly-fix", "quantity": 2},
        ] + [{"card_id": f"tr{i}", "quantity": 2} for i in range(7)])
        self.assertEqual(20, sum(c["quantity"] for c in deck["cards"]))
        v, ids = self._violated(deck, synth_catalog(with_haunter=True))
        self.assertEqual("legal", v["legality"], v["violations"])
        self.assertIn("EVOL-001", v["satisfied_rules"])

    def test_iv_mega_pre_absent_rejected(self):
        # (iv) nem id nem nome do pre existem no deck -> EVOL-001
        deck = dek("f3b-iv", [
            {"card_id": "mega-fix", "quantity": 2},
            {"card_id": "gastly-fix", "quantity": 2},
        ] + [{"card_id": f"tr{i}", "quantity": 2} for i in range(8)])
        self.assertEqual(20, sum(c["quantity"] for c in deck["cards"]))
        v, ids = self._violated(deck, synth_catalog(with_haunter=False))
        self.assertEqual("illegal", v["legality"])
        self.assertIn("EVOL-001", ids)

    def test_v_real_persisted_mega_gengar_line_complete(self):
        # (v) deck real persistido: todo mega tem o pre pelo nome (linha completa).
        # Guarda de regressao do estado do banco (apos revalidacao F3b).
        con = sqlite3.connect(str(DB))
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT deck_id FROM deck_specifications "
                "WHERE deck_id LIKE 'deck-mega-gengar-ex-%' ORDER BY deck_id DESC LIMIT 1"
            ).fetchall()
            if not rows:
                self.skipTest("nenhum deck-mega-gengar-ex-* persistido")
            did = rows[0]["deck_id"]
            pokemons = con.execute("""
                SELECT c.canonical_name nome, c.stage, SUM(dc.quantity) tot
                FROM deck_cards dc JOIN cards c ON c.id=dc.card_id
                WHERE dc.deck_id=? AND c.category='pokemon'
                GROUP BY c.canonical_name, c.stage
            """, (did,)).fetchall()
            megas = con.execute("""
                SELECT c.canonical_name mega_nome, c2.canonical_name pre_nome
                FROM deck_cards dc
                JOIN cards c ON c.id=dc.card_id
                LEFT JOIN card_evolutions e ON e.card_id=c.id
                LEFT JOIN cards c2 ON c2.id=e.pre_evo_card_id
                WHERE dc.deck_id=? AND c.stage='mega_ex'
            """, (did,)).fetchall()
        finally:
            con.close()
        names = {r["nome"] for r in pokemons}
        for m in megas:
            self.assertIsNotNone(m["pre_nome"], f"{did}: mega sem pre declarado")
            self.assertIn(m["pre_nome"], names,
                          f"{did}: '{m['mega_nome']}' sem '{m['pre_nome']}' no deck")


if __name__ == "__main__":
    unittest.main(verbosity=2)
