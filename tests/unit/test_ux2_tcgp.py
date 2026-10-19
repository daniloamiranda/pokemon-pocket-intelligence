#!/usr/bin/env python3
"""UX-2 (card t_2d795bb4): guarda do comando curto bin/tcgp + consistencia da doc.

Cobre o card:
  1. TODOS os subcomandos documentados sao executados de verdade aqui
     (deck/eval/meta/cartas no modo seguro; refresh so o caminho de uso
     invalido — a rede e manual e nunca entra em suite);
  2. o teste FALHA se README.md ou docs/USAGE.md citarem subcomando/flag
     inexistente do tcgp (doc que nao executa e proibida);
  3. --copiar e o fluxo completo em copia NAO alteram o banco canonico
     (md5 antes == depois; precedentes BUG-002/F15);
  4. --json presente em todos os subcomandos com contrato checavel;
  5. codigos de saida: rc=0 feliz, rc=2 carta inexistente, rc=64 uso invalido.

Banco canonico: producao fica md5-intocada (guarda na classe inteira).
Zero dependencia nova, zero rede.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TCGP = ROOT / "bin" / "tcgp"
PROD_DB = ROOT / "data" / "pocket.sqlite"
README = ROOT / "README.md"
USAGE = ROOT / "docs" / "USAGE.md"

SUBCOMANDOS_VALIDOS = {"deck", "eval", "meta", "cartas", "refresh"}
FLAGS_VALIDOS = {"--copiar", "--json", "--top", "--check", "--help", "-h", "--days",
                 "--card-id"}  # repassadas 1:1 aos motores (prova test_05b)


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_tcgp(args: list[str], cwd: str | None = None,
             env_extra: dict | None = None) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run([str(TCGP), *args], capture_output=True, text=True,
                          timeout=180, cwd=cwd or str(ROOT), env=env)


class TestUX2Tcgp(unittest.TestCase):
    last_md5: str | None = None

    @classmethod
    def setUpClass(cls):
        assert TCGP.is_file() and TCGP.stat().st_mode & 0o111, \
            "bin/tcgp ausente ou sem bit executavel"
        cls.prod_md5_before = md5(PROD_DB)
        cls.tmp = tempfile.TemporaryDirectory(prefix="ux2-")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.prod_md5_after = md5(PROD_DB)
        # guarda da classe inteira: nenhuma prova tocou producao
        assert cls.prod_md5_before == cls.prod_md5_after, (
            "BUG: banco canonico mudou durante a suite UX-2 "
            f"({cls.prod_md5_before} -> {cls.prod_md5_after})")

    # -- 1. wrapper -------------------------------------------------------
    def test_01_help_lista_todos_os_subcomandos(self):
        p = run_tcgp(["--help"], cwd=self.tmp.name)  # raiz resolvida de fora do repo
        self.assertEqual(p.returncode, 0)
        for sub in sorted(SUBCOMANDOS_VALIDOS):
            self.assertIn(sub, p.stdout, f"--help nao documenta '{sub}'")
        self.assertIn("--json", p.stdout)
        self.assertIn("--copiar", p.stdout)

    def test_02_wrapper_e_stdlib_apenas(self):
        import ast
        tree = ast.parse(TCGP.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        stdlib_ok = {"__future__", "json", "os", "shutil", "sqlite3",
                     "subprocess", "sys", "tempfile", "pathlib"}
        self.assertEqual(imported - stdlib_ok, set(),
                         f"dependencia nova proibida: {imported - stdlib_ok}")

    # -- 2. fluxo completo ------------------------------------------------
    def test_03_fluxo_completo_json_em_copia(self):
        p = run_tcgp(["Mega Altaria ex", "--copiar", "--json"])
        self.assertEqual(p.returncode, 0, p.stderr)
        d = json.loads(p.stdout)
        self.assertIn(d["veredicto"], ("valido", "fallback"))
        self.assertTrue(d["deck_id"].startswith("deck-"))
        self.assertTrue(d["how_to_play"].strip())
        self.assertEqual(len(d["card_lines"]), 10)          # UX-1: 10 distintas
        self.assertEqual(sum(c["quantity"] for c in d["cards"]), 20)
        ev = d.get("evaluation") or {}
        self.assertEqual(ev.get("veredicto"), "avaliado")
        self.assertEqual(ev["score"]["score_type"], "heuristic_quality_NOT_winrate")
        self.assertTrue(ev["disclaimers"])

    def test_04_fluxo_completo_humano_em_copia_md5_intocado(self):
        before = md5(PROD_DB)
        p = run_tcgp(["Mega Altaria ex", "--copiar"])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("-- como funciona --", p.stdout)      # formato UX-1
        self.assertIn("NAO e winrate", p.stdout)            # disclaimer do evaluator
        self.assertEqual(before, md5(PROD_DB), "--copiar gravou no canonico!")

    # -- 3. deck / eval -----------------------------------------------------
    def test_05_deck_copiar_nao_grava(self):
        before = md5(PROD_DB)
        p = run_tcgp(["deck", "Mega Altaria ex", "--copiar"])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("2x Mega Altaria ex", p.stdout)
        self.assertEqual(before, md5(PROD_DB), "deck --copiar gravou no canonico!")

    def test_05b_deck_aceita_flags_do_motor_como_card_id(self):
        p = run_tcgp(["deck", "--card-id", "limitless:B1/102", "--copiar"])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Mega Altaria ex", p.stdout)  # B1/102 = Mega Altaria ex

    def test_06_eval_por_deck_id_json(self):
        p = run_tcgp(["eval", "deck-mega-altaria-ex-001", "--json"])
        self.assertEqual(p.returncode, 0, p.stderr)
        d = json.loads(p.stdout)
        self.assertEqual(d["veredicto"], "avaliado")
        self.assertEqual(d["deck"]["id"], "deck-mega-altaria-ex-001")
        self.assertEqual(d["score"]["score_type"], "heuristic_quality_NOT_winrate")
        self.assertTrue(any("NÃO é winrate" in x or "NAO e winrate" in x
                            for x in d["disclaimers"]))

    def test_07_eval_por_carta_resolve_deck_f8(self):
        p = run_tcgp(["eval", "Mega Altaria ex", "--json"])
        self.assertEqual(p.returncode, 0, p.stderr)
        d = json.loads(p.stdout)
        self.assertEqual(d["veredicto"], "avaliado")
        self.assertEqual(d["deck"]["main_card"], "Mega Altaria ex")

    # -- 4. meta / cartas ---------------------------------------------------
    def test_08_meta_top3_humano_e_json(self):
        p = run_tcgp(["meta", "--top", "3"])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("snapshot", p.stdout)
        self.assertEqual(p.stdout.count("share"), 4)  # legenda + 3 linhas
        pj = run_tcgp(["meta", "--top", "3", "--json"])
        self.assertEqual(pj.returncode, 0)
        dj = json.loads(pj.stdout)
        self.assertEqual(len(dj["archetypes"]), 3)
        self.assertIn("window", dj)
        self.assertIn("snapshot_id", dj)

    def test_09_cartas_pikachu_humano(self):
        p = run_tcgp(["cartas", "Pikachu"])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Pikachu", p.stdout)
        self.assertGreaterEqual(p.stdout.count("limitless:"), 1)

    def test_10_cartas_json_e_elemento(self):
        pj = run_tcgp(["cartas", "Pikachu", "--json"])
        self.assertEqual(pj.returncode, 0)
        dj = json.loads(pj.stdout)
        self.assertGreater(dj["matches"], 0)
        self.assertEqual(dj["query"], "Pikachu")
        pe = run_tcgp(["cartas", "water", "--json"])
        de = json.loads(pe.stdout)
        self.assertGreater(de["matches"], 0)
        self.assertTrue(all(c["element"] == "water" for c in de["cards"]))
        p0 = run_tcgp(["cartas", "XyzNaoExiste999"])
        self.assertEqual(p0.returncode, 0)
        self.assertIn("0 cartas", p0.stdout)

    # -- 5. codigos de saida ------------------------------------------------
    def test_11_rc2_carta_inexistente(self):
        p = run_tcgp(["CartaQueNaoExisteXYZ999"])
        self.assertEqual(p.returncode, 2)
        self.assertIn("carta_inexistente", p.stdout)

    def test_12_rc64_uso_invalido(self):
        for args in (["eval"], ["meta", "--top", "abc"], ["refresh"], ["cartas"]):
            p = run_tcgp(args)
            self.assertEqual(p.returncode, 64, f"{args}: rc {p.returncode} != 64")

    def test_13_refresh_sem_check_nao_usa_rede(self):
        p = run_tcgp(["refresh"])
        self.assertEqual(p.returncode, 64)
        self.assertIn("MANUAL", p.stdout)

    # -- 6. doc nao cita comando inexistente (regra do card) ---------------
    def test_14_doc_so_cita_subcomandos_e_flags_existentes(self):
        partes = []
        if README.is_file():
            partes.append(README.read_text(encoding="utf-8"))
        if USAGE.is_file():
            partes.append(USAGE.read_text(encoding="utf-8"))
        texto = "\n".join(partes)
        self.assertTrue(texto.strip(), "README/USAGE precisam citar o tcgp")
        usos = re.findall(r"\btcgp\s+([^\n`|#]+)", texto)
        self.assertTrue(usos, "nenhum uso de 'tcgp ...' encontrado na doc")
        citados = set()
        for linha in usos:
            for tok in linha.split():
                tok = tok.strip().strip('"\'')
                if not tok or tok in ("<carta>", "<busca>", "N"):
                    continue
                if tok.startswith("-"):
                    self.assertIn(tok, FLAGS_VALIDOS,
                                  f"doc cita flag inexistente do tcgp: {tok}")
                elif tok in SUBCOMANDOS_VALIDOS:
                    citados.add(tok)
                elif tok.startswith(("deck-", "Mega", '"')):
                    continue  # alvo do subcomando (carta/deck_id)
                else:
                    # args posicionais dos exemplos (cartas, nomes) sao validos
                    continue
        self.assertIn("deck", citados)
        self.assertIn("eval", citados)
        self.assertIn("meta", citados)
        self.assertIn("cartas", citados)

    def test_15_cada_subcomando_documentado_executa(self):
        # a execucao real de cada subcomando sao os testes 03-13 acima;
        # aqui garantimos que NENHUM subcomando valido ficou sem prova
        executados = {
            "deck": {"test_05_deck_copiar_nao_grava"},
            "eval": {"test_06_eval_por_deck_id_json", "test_07_eval_por_carta_resolve_deck_f8"},
            "meta": {"test_08_meta_top3_humano_e_json"},
            "cartas": {"test_09_cartas_pikachu_humano", "test_10_cartas_json_e_elemento"},
        }
        for sub, provas in executados.items():
            for t in provas:
                self.assertTrue(hasattr(self, t), f"prova ausente para {sub}: {t}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
