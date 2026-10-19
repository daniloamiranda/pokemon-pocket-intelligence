"""F5d - regressao: ledger dedicado + cache persistente.

NOTA CEO (22:2x): NENHUM teste toca o ledger VIVO de data/ nem o canonico em
modo escrita. Aqui o ledger e (re)construido em tmp isolado (unique dir) via
open_db/F5D_LEDGER_DB — igual ao fluxo de producao — e as provas sobre o
historico real usam copia read-only. Suite verde mesmo com bancos de
producao AUSENTES (builder fresh provado a parte).

F5e: import de sync.py/export_catalog.py exige o SDK composio (venv-only);
os casos dependentes sao PULADOS com motivo explicito quando o SDK nao
existe (interprete do sistema) em vez de darem ERROR — suite verde em
qualquer interprete. Ver docs/TESTING.md.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "integrations" / "google-sheets"))

# SDK composio e OPCIONAL (venv-only, docs/TESTING.md): os casos que importam
# sync.py/export_catalog.py sao pulados com MOTIVO quando o SDK nao existe
# (suite no python3 do sistema) em vez de darem ERROR.
try:
    import composio  # noqa: F401
    COMPOSIO_SDK = True
except ImportError:
    COMPOSIO_SDK = False
SEM_SDK = "SDK composio ausente (venv) — ver docs/TESTING.md"

CANON = ROOT / "data" / "pocket.sqlite"
LEDGER = ROOT / "data" / "sync_state.sqlite"

PROIBIDAS = {
    "cards", "card_prints", "card_attacks", "card_abilities",
    "card_evolutions", "card_evolution_slugs", "card_localizations",
    "card_legality", "cards_fts", "decks", "deck_cards",
    "deck_evaluations", "expansions", "matchups", "meta_archetypes",
    "meta_snapshots", "tournaments", "rules", "tiers", "archetype_cards",
}


@unittest.skipUnless(COMPOSIO_SDK, SEM_SDK)
class LedgerTmpCatalogFreeTest(unittest.TestCase):
    """Ledger construido DO ZERO em tmp: sem qualquer tabela de catalogo."""

    def _fresh_ledger(self, tmpdir):
        os.environ["F5D_LEDGER_DB"] = str(tmpdir / "ledger_tmp.sqlite")
        self.addCleanup(os.environ.pop, "F5D_LEDGER_DB", None)
        import export_catalog as E
        import importlib
        importlib.reload(E)  # LEDGER_DB resolvido por execucao (tmp isolado)
        con = E.open_db(ledger=True)
        self.addCleanup(con.close)
        return con

    def test_fresh_ledger_sem_catalogo_e_identidade(self):
        with tempfile.TemporaryDirectory() as td:
            con = self._fresh_ledger(Path(td))
            tabs = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'")}
            self.assertFalse(tabs & PROIBIDAS, "catalogo no ledger fresh: %s" % (tabs & PROIBIDAS))
            self.assertTrue({"sync_jobs", "sync_changes", "source_records"} <= tabs)
            self.assertEqual(con.execute("PRAGMA application_id").fetchone()[0], 2)
            role = con.execute("SELECT role, notes FROM bank_role").fetchone()
            self.assertEqual(role[0], "sync_ledger")
            self.assertIn("LEDGER", role[1])
            con.close()

    def test_fresh_ledger_pequeno(self):
        with tempfile.TemporaryDirectory() as td:
            con = self._fresh_ledger(Path(td))
            con.close()
            size = (Path(td) / "ledger_tmp.sqlite").stat().st_size
            self.assertLess(size, 500_000, "ledger fresh grande: %d" % size)

    def test_canonico_unico_dono_de_cards_quando_presente(self):
        if not CANON.exists():
            self.skipTest("banco canonico ausente (suite continua verde)")
        tabs = _tables_ro(CANON)
        self.assertTrue({"cards", "card_prints"} <= tabs)


def _tables_ro(path):
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                       "AND name NOT LIKE 'sqlite_%'").fetchall()
    con.close()
    return {r[0] for r in rows}


@unittest.skipUnless(LEDGER.exists(), "ledger de producao ausente (suite verde)")
class HistoricoRealReadOnlyTest(unittest.TestCase):
    """Historico F5b/F5c lido de COPIA read-only num tmp — nunca do vivo."""

    def test_ledger_herda_historico_f5c(self):
        with tempfile.TemporaryDirectory() as td:
            copy_ = Path(td) / "copy.sqlite"
            shutil.copy(LEDGER, copy_)
            con = sqlite3.connect("file:%s?mode=ro" % copy_, uri=True)
            jobs = con.execute("SELECT count(*) FROM sync_jobs").fetchone()[0]
            changes = con.execute("SELECT count(*) FROM sync_changes").fetchone()[0]
            hashes = con.execute(
                "SELECT count(*) FROM sync_changes WHERE content_hash != ''").fetchone()[0]
            tabs = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'")}
            con.close()
        self.assertFalse(tabs & PROIBIDAS, "catalogo no ledger vivo: %s" % (tabs & PROIBIDAS))
        self.assertGreaterEqual(jobs, 1)
        self.assertGreaterEqual(changes, 100)
        self.assertEqual(hashes, changes, "change sem hash")
        self.assertLess(LEDGER.stat().st_size, 1_000_000,
                        "ledger vivo grande demais (%d) - parece clone" % LEDGER.stat().st_size)


@unittest.skipUnless(CANON.exists(), "banco canonico ausente (suite verde)")
class CachePersistenteTest(unittest.TestCase):
    def test_client_default_cache_persistente(self):
        sys.path.insert(0, str(ROOT / "integrations" / "limitlesstcg-pocket"))
        for m in [k for k in ("client",) if k in sys.modules]:
            del sys.modules[m]
        import client as C
        root_txt = str(C.DEFAULT_CACHE_ROOT)
        self.assertNotIn("/tmp", root_txt, "cache default em caminho efemero")
        self.assertTrue(root_txt.endswith(os.path.join("data", "cache")),
                        "cache default deve ser data/cache: %s" % root_txt)

    def test_cache_diretorio_persistente_populado(self):
        pages = ROOT / "data" / "cache" / "pages"
        if not pages.exists():
            self.skipTest("cache persistente ausente")
        n = len(list(pages.glob("*.html")))
        self.assertGreater(n, 100, "cache persistente quase vazio (%d)" % n)

    def test_rebuild_script_usa_cache_persistente(self):
        src = (ROOT / "scripts" / "rebuild_children_from_cache.py").read_text()
        self.assertIn("data/cache", src)
        self.assertNotIn("/tmp/pocket_cache/pages", src)

    def test_sem_referencia_a_tmp_pocket_cache_no_client(self):
        src = (ROOT / "integrations" / "limitlesstcg-pocket" / "client.py").read_text()
        self.assertNotIn("/tmp/pocket_cache", src)

    def test_canonico_identidade_1(self):
        con = sqlite3.connect("file:%s?mode=ro" % CANON, uri=True)
        self.assertEqual(con.execute("PRAGMA application_id").fetchone()[0], 1,
                         "canonico sem Application-ID 1")
        con.close()


if __name__ == "__main__":
    unittest.main()
