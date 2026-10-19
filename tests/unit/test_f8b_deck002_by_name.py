#!/usr/bin/env python3
"""F8b-TESTES: DECK-002 por NOME — regressao do defeito 'deck ilegal aprovado como legal'.

Card t_f29d4466 (prioridade maxima). O defeito: o validador checava a quantidade
de CADA entrada isolada (nunca agregava por nome), e o builder misturava
identidades de mesmo nome (Gastly psiquico em linha sombria).

Casos OBRIGATORIOS do card (dimensao da regra, nao so magnitude):
  (a) 3 cartas de mesmo nome com 2 identidades diferentes -> DECK-002 violada;
  (b) 1+1+1 em entradas separadas da mesma carta -> violada;
  (c) 2+2 do mesmo nome -> violada;
  (d) 2 copias exatas do mesmo nome -> legal;
  (e) deck do caso real (Mega Gengar ex) regenerado -> DECK-002 satisfeita,
      sem 3 nomes iguais e com linha de evolucao de tipo coerente.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "deck"))

import build_deck as B      # noqa: E402
import validate_deck as V3  # noqa: E402

DB = ROOT / "data" / "pocket.sqlite"


def dek(name, cards):
    return {"id": name, "name": name, "format": "standard", "cards": cards}


def synth_catalog():
    """Catalogo sintetico: 2 identidades de Gastly (psiquica/sombria) + linha + trainers."""
    return {"cards": [
        {"card_id": "gastly-A1", "name": "Gastly", "category": "pokemon", "stage": "basic",
         "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
        {"card_id": "gastly-B2b", "name": "Gastly", "category": "pokemon", "stage": "basic",
         "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
        {"card_id": "haunter-B2b", "name": "Haunter", "category": "pokemon", "stage": "stage1",
         "evolves_from": "gastly-A1", "legal": True, "legal_formats": ["standard"]},
        {"card_id": "mega-gengar-B2b", "name": "Mega Gengar ex", "category": "pokemon",
         "stage": "stage2", "evolves_from": "haunter-B2b", "legal": True,
         "legal_formats": ["standard"]},
        {"card_id": "cynt", "name": "Cynthia", "category": "trainer", "stage": "basic",
         "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
        {"card_id": "red", "name": "Red", "category": "trainer", "stage": "basic",
         "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
        {"card_id": "misty", "name": "Misty", "category": "trainer", "stage": "basic",
         "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
        {"card_id": "wally", "name": "Wally", "category": "trainer", "stage": "basic",
         "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
        {"card_id": "sabrina", "name": "Sabrina", "category": "trainer", "stage": "basic",
         "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
        {"card_id": "iono", "name": "Iono", "category": "trainer", "stage": "basic",
         "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
        {"card_id": "prof", "name": "Professor's Research", "category": "trainer",
         "stage": "basic", "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
        {"card_id": "ball", "name": "Poke Ball", "category": "trainer", "stage": "basic",
         "evolves_from": None, "legal": True, "legal_formats": ["standard"]},
    ]}


FILLER = [{"card_id": "cynt", "quantity": 2},
          {"card_id": "red", "quantity": 2},
          {"card_id": "misty", "quantity": 2},
          {"card_id": "wally", "quantity": 2},
          {"card_id": "sabrina", "quantity": 2},
          {"card_id": "iono", "quantity": 2},
          {"card_id": "prof", "quantity": 2}]


class TestF8bDeck002ByName(unittest.TestCase):
    """Os 5 casos obrigatorios do card t_f29d4466."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = synth_catalog()

    def _violated(self, deck):
        v = V3.validate_deck(deck, self.catalog)
        return v, {x["rule_id"] for x in v["violations"]}

    def test_a_3_same_name_2_identities_violated(self):
        # (a) 2x Gastly B2b/37 + 1x Gastly A1/120 = 3 cartas "Gastly" -> ILEGAL
        deck = dek("f8b-a", [
            {"card_id": "mega-gengar-B2b", "quantity": 2},
            {"card_id": "haunter-B2b", "quantity": 2},
            {"card_id": "gastly-B2b", "quantity": 2},
            {"card_id": "gastly-A1", "quantity": 1},
        ] + FILLER)
        v, ids = self._violated(deck)
        self.assertEqual("illegal", v["legality"])
        self.assertIn("DECK-002", ids)
        self.assertTrue(any("Gastly" in x["message"] and "soma 3" in x["message"]
                            for x in v["violations"]), v["violations"])

    def test_b_1_plus_1_plus_1_same_card_violated(self):
        # (b) mesma carta 3x em TRES entradas separadas -> ILEGAL (antes passava!)
        deck = dek("f8b-b", [
            {"card_id": "mega-gengar-B2b", "quantity": 2},
            {"card_id": "haunter-B2b", "quantity": 2},
            {"card_id": "gastly-B2b", "quantity": 1},
            {"card_id": "gastly-B2b", "quantity": 1},
            {"card_id": "gastly-B2b", "quantity": 1},
        ] + FILLER)
        v, ids = self._violated(deck)
        self.assertEqual("illegal", v["legality"])
        self.assertIn("DECK-002", ids)

    def test_c_2_plus_2_same_name_violated(self):
        # (c) 2 + 2 do mesmo nome (identidades distintas) -> ILEGAL
        deck = dek("f8b-c", [
            {"card_id": "mega-gengar-B2b", "quantity": 2},
            {"card_id": "haunter-B2b", "quantity": 2},
            {"card_id": "gastly-B2b", "quantity": 2},
            {"card_id": "gastly-A1", "quantity": 2},
        ] + FILLER)
        v, ids = self._violated(deck)
        self.assertEqual("illegal", v["legality"])
        self.assertIn("DECK-002", ids)

    def test_d_exact_2_copies_legal(self):
        # (d) 2 copias exatas do mesmo nome -> LEGAL (controle)
        deck = dek("f8b-d", [
            {"card_id": "mega-gengar-B2b", "quantity": 2},
            {"card_id": "haunter-B2b", "quantity": 2},
            {"card_id": "gastly-B2b", "quantity": 2},
        ] + FILLER)
        v, ids = self._violated(deck)
        self.assertEqual("legal", v["legality"], v["violations"])

    def test_e_real_mega_gengar_deck_clean_after_fix(self):
        # (e) deck do CASO REAL regenerado (ultimo deck-mega-gengar-ex-*):
        # nenhum nome acima de 2 copias + linha de evolucao sombria coerente.
        con = sqlite3.connect(str(DB))
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT deck_id FROM deck_specifications WHERE deck_id LIKE 'deck-mega-gengar-ex-%' "
                "ORDER BY deck_id DESC LIMIT 1").fetchall()
            self.assertTrue(rows, "nenhum deck regenerado do Mega Gengar ex encontrado")
            did = rows[0]["deck_id"]
            cards = con.execute("""SELECT dc.card_id, dc.quantity, ca.canonical_name, ca.element
                FROM deck_cards dc JOIN cards ca ON ca.id=dc.card_id
                WHERE dc.deck_id=? ORDER BY dc.card_id""", (did,)).fetchall()
        finally:
            con.close()
        names = {}
        for c in cards:
            names[c["canonical_name"]] = names.get(c["canonical_name"], 0) + c["quantity"]
        for n, tot in names.items():
            self.assertLessEqual(tot, 2, f"{did}: '{n}' tem {tot} copias")
        self.assertEqual(20, sum(c["quantity"] for c in cards))
        el = {c["element"] for c in cards if c["element"]}
        self.assertNotIn("psychic", el, f"{did}: linha Gastly/Haunter psiquica em deck sombrio")
        self.assertIn("darkness", el)


class TestF8bPickPreIdentity(unittest.TestCase):
    """Unidade: resolucao de identidade do pre-requisito por nome + tipo."""

    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(str(DB))
        cls.con.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def test_01_prefere_elemento_da_linha_principal(self):
        # pre registrado A1/120 (psychic); principal darkness -> escolhe B2b/37
        got = B.pick_pre_identity(self.con, "limitless:A1/120",
                                  {"element": "darkness", "canonical_name": "Mega Gengar ex"})
        self.assertEqual("limitless:B2b/37", got)

    def test_02_mantem_quando_coerente(self):
        got = B.pick_pre_identity(self.con, "limitless:B2b/37",
                                  {"element": "darkness", "canonical_name": "Mega Gengar ex"})
        self.assertEqual("limitless:B2b/37", got)

    def test_03_sem_identidade_alternativa_mantem_original(self):
        got = B.pick_pre_identity(self.con, "limitless:A4a/20",
                                  {"element": "fire", "canonical_name": "Mega Blaziken ex"})
        self.assertEqual("limitless:A4a/20", got)

    def test_04_nucleo_empirico_exclui_decks_gerados(self):
        # F8b: decks 'deck-%' (saida do proprio motor) nunca entram no nucleo
        con2 = sqlite3.connect(str(DB))
        con2.row_factory = sqlite3.Row
        try:
            real = con2.execute("""SELECT COUNT(DISTINCT d.id) n FROM decks d
                JOIN deck_cards dc ON dc.deck_id=d.id
                WHERE dc.card_id=? AND d.id NOT LIKE 'deck-%'""",
                ("limitless:B2b/39",)).fetchone()["n"]
            gerados = con2.execute("""SELECT COUNT(DISTINCT d.id) n FROM decks d
                JOIN deck_cards dc ON dc.deck_id=d.id
                WHERE dc.card_id=? AND d.id LIKE 'deck-%'""",
                ("limitless:B2b/39",)).fetchone()["n"]
        finally:
            con2.close()
        self.assertGreaterEqual(gerados, 1, "pre-condicao: existiriam decks gerados no banco")
        nd, _ = B.empirical_nucleus(self.con, "limitless:B2b/39", 30)
        self.assertEqual(real, nd, "nucleo deve conter SO lists reais (deck-% excluido)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
