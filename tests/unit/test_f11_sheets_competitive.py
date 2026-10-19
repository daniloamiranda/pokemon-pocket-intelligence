"""F11 - guarda da camada competitiva na planilha (DEV-01 da F10).

Regra do card t_e62a74dc: nenhuma aba pode sair com placeholder "AGUARDANDO"
nem ficar vazia quando a tabela de origem tem dados. Estes testes travam a
RECORRENCIA em tres niveis:

  1. AST: nenhuma ocorrencia de "AGUARDANDO" no export (o gerador de
     placeholder build_future_tab foi REMOVIDO);
  2. Banco real (mode=ro): os 6 builders produzem linhas SEM placeholder e a
     contagem de cada aba bate EXATAMENTE com o SQL de origem declarado em
     COMPETITIVE_SOURCES (fonte da verdade do aceite);
  3. Fluxo de escrita F11 (transporte FALSO, sem rede): uma aba que devolve
     placeholder/vazio com origem populada quebra o assert de leitura de
     volta => o sync nunca aceita silenciosamente.

Sem rede e sem escrita: o banco canonico e aberto SOMENTE em mode=ro e o
transporte Composio e simulado (nota CEO F5d: nenhum teste toca os bancos
de producao em modo escrita). Suite verde em qualquer interprete (o SDK
composio nao e necessario aqui porque o transporte e falso).
"""
import ast
import io
import re
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "integrations" / "google-sheets"))

import export_catalog as E  # noqa: E402  (nao importa composio)

CANON = ROOT / "data" / "pocket.sqlite"
PLACEHOLDER = re.compile(r"AGUARDANDO", re.IGNORECASE)

F11_TABS = ("Decks_Meta", "Decks_Cartas", "Matchups",
            "Decks_Criados", "Deck_Cartas", "Avaliacoes")


def _open_ro():
    con = sqlite3.connect("file:%s?mode=ro" % CANON, uri=True)
    con.row_factory = sqlite3.Row
    return con


class NoPlaceholderTest(unittest.TestCase):
    """Nivel 1 - o codigo-fonte nao sabe gerar placeholder."""

    def test_no_aguardando_in_export_source(self):
        with io.open(E.__file__, encoding="utf-8") as fh:
            src = fh.read()
        bad = [i for i, line in enumerate(src.splitlines(), 1)
               if PLACEHOLDER.search(line)]
        self.assertEqual(
            bad, [],
            "export_catalog.py contem 'AGUARDANDO' nas linhas %s" % bad)

    def test_placeholder_builder_removed_and_tabs_wired(self):
        with io.open(E.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        funcs = {n.name for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertNotIn("build_future_tab", funcs,
                         "gerador de placeholder ainda existe")
        self.assertTrue(hasattr(E, "COMPETITIVE_TABS"))
        for tab in F11_TABS:
            self.assertIn(tab, E.COMPETITIVE_TABS)
            self.assertIn(tab, E.COMPETITIVE_SOURCES)


@unittest.skipUnless(CANON.exists(), "banco canonico ausente")
class BuildersMatchSourceTest(unittest.TestCase):
    """Nivel 2 - dados REAIS: sem placeholder e contagem == SQL de origem."""

    @classmethod
    def setUpClass(cls):
        cls.con = _open_ro()

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def test_builders_have_no_placeholder_cells(self):
        for tab in F11_TABS:
            builder, _sql = E.COMPETITIVE_SOURCES[tab]
            rows = builder(self.con)
            for r_i, row in enumerate(rows):
                for c_i, val in enumerate(row):
                    self.assertFalse(
                        isinstance(val, str) and PLACEHOLDER.search(val),
                        "placeholder em %s linha %d col %d: %r" % (tab, r_i, c_i, val))

    def test_counts_match_source_sql(self):
        for tab in F11_TABS:
            builder, sql = E.COMPETITIVE_SOURCES[tab]
            rows = builder(self.con)
            expected = self.con.execute(sql).fetchone()[0]
            self.assertEqual(
                len(rows) - 1, expected,
                "aba %s: %d linhas != origem %d" % (tab, len(rows) - 1, expected))
            if expected:
                self.assertGreaterEqual(
                    len(rows) - 1, 1,
                    "aba %s vazia com origem populada" % tab)

    def test_pendencias_sem_ayer_f7_f9(self):
        rows = E.build_pendencias(self.con)
        for row in rows:
            joined = " ".join(str(c) for c in row)
            self.assertNotIn("F7-F9", joined,
                             "pendencia do placeholder antigo ainda listada: %r" % joined)

    def test_decks_meta_ids_no_formato_do_catalogo(self):
        rows = E.build_decks_meta(self.con)
        header, data = rows[0], rows[1:]
        self.assertEqual(header[4], "colocacao")
        for row in data[:100]:
            self.assertTrue(row[0].startswith("ll-"), "deck_id fora do padrao: %r" % row[0])
            self.assertTrue(row[3], "jogador vazio para %r" % row[0])
            self.assertIsInstance(row[4], int)

    def test_deck_cartas_formato_catalogo_e_soma_20(self):
        rows = E.build_deck_cartas(self.con)
        header, data = rows[0], rows[1:]
        self.assertEqual(header[1], "print_ref")
        by_deck = {}
        for row in data:
            self.assertRegex(row[1], r"^[A-Za-z0-9-]+/[A-Za-z0-9]+$",
                             "print_ref fora do formato SET/NUM: %r" % row[1])
            self.assertTrue(row[2], "carta sem nome: %r" % row[:3])
            by_deck[row[0]] = by_deck.get(row[0], 0) + row[3]
        self.assertEqual(len(by_deck), E.build_decks_criados(self.con).__len__() - 1,
                         "decks no Deck_Cartas != decks em Decks_Criados")
        for deck_id, total in by_deck.items():
            self.assertEqual(total, 20, "%s somando %d cartas" % (deck_id, total))

    def test_task_list_covers_all_tabs(self):
        tasks = {tab for tab, _rows, _ncols in E._task_list(self.con)}
        for tab in F11_TABS:
            self.assertIn(tab, tasks)


class _FakeTransport(object):
    """Transporte falso: responde com um ROWSET fixo por leitura."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def sheets_api(self, path, method="GET", body=None):
        self.calls.append(("read", path))
        return {"values": self.rows}


class GuardFailsOnPlaceholderTest(unittest.TestCase):
    """Nivel 3 - o fluxo F11 REPROVA aba com placeholder/vazia (transporte falso)."""

    def _run_flow(self, fake_rows, values):
        fake = _FakeTransport(fake_rows)
        orig_api, orig_exec = E.sync.sheets_api, E.sync.tk_execute
        E.sync.sheets_api = fake.sheets_api
        E.sync.tk_execute = lambda slug, args: {"successful": True, "slug": slug}
        self.addCleanup(setattr, E.sync, "sheets_api", orig_api)
        self.addCleanup(setattr, E.sync, "tk_execute", orig_exec)
        E.write_tab_full("Decks_Meta", values, ncols=9)

    def test_placeholder_sheet_fails_read_back_assert(self):
        # origem populada (2 linhas de dados + header) vs aba devolvendo
        # o placeholder antigo (2 linhas): a guarda da leitura de volta
        # FALHA NA CELULA (conteudo) antes mesmo do assert de contagem —
        # placeholder nao passa nem com contagem casada.
        values = [["deck_id", "torneio", "data_torneio", "jogador", "colocacao",
                   "arquetipo", "formato", "total_cartas", "fonte"],
                  ["ll-x-1", "T", "2026-10-19", "p1", 1, "a", "STANDARD", 20, "s"],
                  ["ll-x-2", "T", "2026-10-19", "p2", 2, "b", "STANDARD", 20, "s"]]
        with self.assertRaises(RuntimeError) as ctx:
            self._run_flow([["Decks_Meta", "status", "nota"],
                            ["Decks_Meta", "AGUARDANDO F7-F9", "reservado"]], values)
        msg = str(ctx.exception)
        self.assertTrue(
            "read-back contem placeholder" in msg or "read-back 2 != 3" in msg,
            "guarda nao detectou a aba placeholder: %r" % msg)
        self.assertIn("failed after 5 retries", msg)

    def test_empty_sheet_with_populated_source_fails(self):
        # origem populada vs aba esvaziada pelo clear que falhou em escrever:
        # o assert de contagem quebra (a aba nunca fica vazia em silencio).
        values = [["deck_id", "torneio", "data_torneio", "jogador", "colocacao",
                   "arquetipo", "formato", "total_cartas", "fonte"],
                  ["ll-x-1", "T", "2026-10-19", "p1", 1, "a", "STANDARD", 20, "s"]]
        with self.assertRaises(RuntimeError) as ctx:
            self._run_flow([], values)
        self.assertIn("read-back 0 != 2", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
