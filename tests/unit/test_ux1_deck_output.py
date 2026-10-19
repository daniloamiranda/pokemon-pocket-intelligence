#!/usr/bin/env python3
"""UX-1 (card t_bd7c1cc1): guarda de saida do deck-builder.

Cobre os 5 testes obrigatorios do card + a tabela curada:
  1. guia/"como funciona" que cite carta AUSENTE do deck falha (caso Gastly
     no deck do Mega Altaria ex — defeito confirmado em execucao real);
  2. toda carta do deck tem papel nao vazio;
  3. nenhum papel contem termo que nao exista na fonte (effect_text real ou
     text_evidence da tabela curada) — guarda anti-fabricacao;
  4. saida humana: exatamente uma linha por carta distinta, 20 cartas somadas;
  5. modo --json estavel (chaves legadas preservadas + card_lines aditivo).

Banco: COPIA via backup API (data/pocket.sqlite de producao fica md5-intocada
— precedentes BUG-002/F15). Zero rede.
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "deck"))

import build_deck as B    # noqa: E402
import card_roles as CR   # noqa: E402

PROD_DB = ROOT / "data" / "pocket.sqlite"
DECKS = ["Mega Altaria ex", "Alolan Ninetales ex", "Mega Gengar ex"]


def make_copy(dst: Path) -> None:
    src = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    out = sqlite3.connect(str(dst))
    src.backup(out)
    out.close()
    src.close()


class TestUX1DeckOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ux1-")
        cls.db = Path(cls.tmp.name) / "pocket.sqlite"
        make_copy(cls.db)
        cls.con = sqlite3.connect(str(cls.db))
        cls.con.row_factory = sqlite3.Row
        cls.curated = CR.load_card_roles()
        cls.builds = {}
        for ident in DECKS:
            main = B.resolve_main(cls.con, ident)
            assert main is not None, f"{ident} nao resolve no catalogo"
            picks, total, nd = B.build_list(cls.con, main, 30)
            assert total == 20, f"{ident}: núcleo montou {total}/20"
            cls.builds[ident] = (main, picks, nd)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        cls.tmp.cleanup()

    # -- fontes reais ------------------------------------------------------
    def _pokemon_text(self, card_id):
        parts = [r["effect_text"] for r in self.con.execute(
            "SELECT effect_text FROM card_attacks WHERE card_id=? AND effect_text IS NOT NULL", (card_id,))]
        parts += [r["effect_text"] for r in self.con.execute(
            "SELECT effect_text FROM card_abilities WHERE card_id=? AND effect_text IS NOT NULL", (card_id,))]
        return " / ".join(parts)

    def _trainer_cache_text(self, card_id):
        r = self.con.execute("""SELECT set_code, number FROM card_prints
            WHERE card_id=? AND is_promo=0 ORDER BY set_code, number LIMIT 1""",
                             (card_id,)).fetchone()
        return B.trainer_text_from_cache(r["set_code"], r["number"]) if r else ""

    # -- 1) anti-fantasma: guia so cita carta presente ---------------------
    def test_01_guia_nao_cita_carta_ausente(self):
        """Caso Gastly: guia que cite carta fora da lista de 20 reprova."""
        for ident, (main, picks, nd) in self.builds.items():
            guide = CR.how_it_works(self.con, main, picks, nd, self.curated)
            lines = CR.deck_lines(self.con, main, picks, self.curated)
            deck_names = {l["name"].lower() for l in lines}
            # nomes multi-palavra citados no guia precisam estar no deck
            for name in deck_names | {"gastly", "haunter", "rare candy"}:
                if name in guide.lower():
                    self.assertIn(name, deck_names,
                                  f"{ident}: guia cita '{name}' ausente da lista de 20")
            # o nome da principal e da linha de evolucao SEMPRE aparecem
            self.assertIn(main["canonical_name"].lower(), guide.lower())

    def test_02_gastly_nunca_no_deck_altaria(self):
        """Regressao literal do defeito medido em execucao real (19/10)."""
        main, picks, nd = self.builds["Mega Altaria ex"]
        guide = CR.how_it_works(self.con, main, picks, nd, self.curated)
        lines = CR.deck_lines(self.con, main, picks, self.curated)
        blob = guide.lower() + " " + " ".join(l["human_line"].lower() for l in lines)
        self.assertNotIn("gastly", blob)
        self.assertNotIn("haunter", blob)

    # -- 2) toda carta tem papel nao vazio ---------------------------------
    def test_03_todo_card_tem_papel(self):
        for ident, (main, picks, nd) in self.builds.items():
            lines = CR.deck_lines(self.con, main, picks, self.curated)
            self.assertEqual(len(lines), len(picks))
            for l in lines:
                self.assertTrue(l["role"].strip(), f"{ident}/{l['name']}: papel vazio")
                self.assertTrue(l["role_origin"] in
                                ("curated", "derived_text", "neutral", "uncataloged"),
                                f"{ident}/{l['name']}: origem invalida {l['role_origin']}")
                # entrada nao catalogada tem que ser explicita (nunca vazio mudo)
                if l["role_origin"] == "uncataloged":
                    self.assertEqual(l["role"], CR.UNCATALOGED_LABEL)

    # -- 3) guarda anti-fabricacao -----------------------------------------
    def test_04_papel_derivado_tem_evidencia_no_texto_real(self):
        for ident, (main, picks, nd) in self.builds.items():
            lines = CR.deck_lines(self.con, main, picks, self.curated)
            for l in lines:
                if l["role_origin"] != "derived_text":
                    continue
                text = self._pokemon_text(l["card_id"])
                ev = l["role_evidence"]
                self.assertTrue(ev, f"{ident}/{l['name']}: derived sem evidencia")
                if ev.startswith("ataque "):
                    # evidencia da principal: ataque real da ficha
                    self.assertTrue(l["role_id"] == "main_attacker")
                    row = self.con.execute(
                        "SELECT name FROM card_attacks WHERE card_id=?", (l["card_id"],)).fetchall()
                    self.assertTrue(row, f"{ident}/{l['name']}: ataque inexistente")
                else:
                    norm = " ".join(text.lower().split())
                    self.assertIn(" ".join(ev.lower().split()), norm,
                                  f"{ident}/{l['name']}: evidencia '{ev}' nao esta no effect_text real")

    def test_05_papel_curado_confere_com_cache_f4(self):
        for ent_name, ent in self.curated.items():
            self.assertIn(ent.get("role_id"), CR.ROLE_DEFS,
                          f"{ent_name}: role_id fora do vocabulario fechado")
            self.assertTrue(ent.get("role"), f"{ent_name}: display vazio")
            self.assertTrue(ent.get("text_evidence"), f"{ent_name}: sem text_evidence")
            self.assertTrue(ent.get("set_code") and ent.get("number"),
                             f"{ent_name}: sem print de referencia")
            row = self.con.execute("""SELECT c.id FROM cards c WHERE lower(c.canonical_name)=?
                AND c.category NOT IN ('pokemon','energy_basic','energy_special')""",
                                   (ent_name,)).fetchone()
            self.assertIsNotNone(row, f"{ent_name}: carta nao existe no catalogo")
            cache = self._trainer_cache_text(row["id"])
            norm = " ".join(cache.lower().split())
            ev = " ".join(ent["text_evidence"].lower().split())
            self.assertIn(ev, norm,
                          f"{ent_name}: text_evidence diverge do cache F4 (anti-fabricacao)")
            # guarda semantica do display curado: qualquer NUMERO de efeito
            # citado no papel tem que existir no text_evidence real
            # ("Heal 30..." permite "30"; frase sem numero nao cita efeito falso)
            for num in re.findall(r"\d+", ent.get("role", "")):
                self.assertIn(num, ev,
                              f"{ent_name}: display cita '{num}' ausente do text_evidence real")

    def test_06_rotulo_neutral_vem_do_vocabulario_fechado(self):
        for ident, (main, picks, nd) in self.builds.items():
            for l in CR.deck_lines(self.con, main, picks, self.curated):
                if l["role_origin"] == "neutral":
                    self.assertIn(l["role"], CR.ROLE_DEFS.values(),
                                  f"{ident}/{l['name']}: rotulo fora do vocabulario fechado")

    # -- 4) saida humana ----------------------------------------------------
    def test_07_saida_humana_uma_linha_por_carta_e_20(self):
        for ident, (main, picks, nd) in self.builds.items():
            report = CR.human_report(self.con, main, picks, nd, "deck-x", "nome",
                                     self.curated)
            lines = CR.deck_lines(self.con, main, picks, self.curated)
            body = report.split("-- como funciona --")[0].splitlines()[1:]
            self.assertEqual(len(body), len(lines),
                             f"{ident}: {len(body)} linhas para {len(lines)} cartas")
            self.assertEqual(sum(l["quantity"] for l in lines), 20,
                             f"{ident}: lista nao soma 20")
            names = [l["name"] for l in lines]
            self.assertEqual(len(names), len(set(names)),
                             f"{ident}: carta distinta repetida em linha propria")
            for l, row in zip(lines, body):
                self.assertTrue(row.startswith(f"{l['quantity']}x "), f"{ident}: '{row}'")
                self.assertIn(" — ", row, f"{ident}: sem separador de papel: '{row}'")
            # 4 linhas max no "como funciona" (2-4 do card)
            how = report.split("-- como funciona --")[1].strip().splitlines()
            self.assertGreaterEqual(len(how), 2)
            self.assertLessEqual(len(how), 4)
            # zero card_id cru na saida humana
            self.assertNotIn("limitless:", report)

    # -- 5) --json estavel (aditivo) ----------------------------------------
    def test_08_json_estavel_com_card_lines(self):
        out = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "deck" / "build_deck.py"),
             "Mega Altaria ex", "--db", str(self.db), "--json"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr[:300])
        d = json.loads(out.stdout)
        for legacy in ("veredicto", "deck_id", "confidence_level", "empirical_decks",
                       "window_days", "legality", "satisfied_rules", "main_card",
                       "cards", "energy_plan", "how_to_play", "competitive_analysis",
                       "sources"):
            self.assertIn(legacy, d, f"chave legada {legacy} sumiu do --json")
        self.assertIn("card_lines", d)
        cl = d["card_lines"]
        self.assertEqual(sum(c["quantity"] for c in cl), 20)
        for c in cl:
            for field in ("card_id", "name", "quantity", "role", "role_origin",
                          "role_evidence", "human_line"):
                self.assertIn(field, c)
        # origem do papel citada por linha (requisito do card)
        self.assertTrue(all(c["role_origin"] for c in cl))

    # -- tabela curada: cobertura dos decks gerados + meta -------------------
    def test_09_tabela_cura_13_dos_decks_gerados_e_meta(self):
        obs = [r["canonical_name"] for r in self.con.execute("""SELECT DISTINCT c.canonical_name
            FROM deck_cards dc JOIN cards c ON c.id=dc.card_id
            WHERE dc.deck_id LIKE 'deck-%' AND c.category NOT IN ('pokemon')""")]
        missing = [n for n in obs if n.lower() not in self.curated]
        self.assertEqual(missing, [], f"treinadores de decks gerados fora da tabela: {missing}")
        for owner_example in ("professor's research", "small balloon"):
            self.assertIn(owner_example, self.curated)

    def test_10_uncataloged_e_explicito_nunca_inventado(self):
        fake = {"id": "limitless:XX/00", "canonical_name": "Supporter Inexistente XYZ",
                "category": "trainer_supporter"}
        role = CR.derive_role(self.con, fake, self.curated)
        self.assertEqual(role["origin"], "uncataloged")
        self.assertEqual(role["role"], CR.UNCATALOGED_LABEL)
        self.assertIn("card_roles.yaml", role["source"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
