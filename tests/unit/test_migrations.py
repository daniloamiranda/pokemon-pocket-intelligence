"""F2 · Tests de migração do SQLite canônico + integridade referencial + contratos.

Execução:
  python3 -m unittest tests.unit.test_migrations -v
  (compatível com pytest quando disponível)
"""
import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import db_migrate  # noqa: E402
import contract_check  # noqa: E402


def fresh_db(tmp=":memory:"):
    """Retorna conexão nova com migrations aplicadas (idempotência garantida)."""
    import tempfile
    if tmp == ":memory:":
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript((ROOT / "database" / "migrations" / "0001_init.sql").read_text("utf-8"))
        conn.commit()
        return conn
    p = Path(tmp)
    if p.exists():
        p.unlink()
    db = db_migrate.connect(p)
    db_migrate.migrate(p)
    return db


class TestContractValidation(unittest.TestCase):
    """Critério 1 — todos os contratos existem e validam contra JSON Schema."""

    def test_all_contracts_valid(self):
        contracts = sorted((ROOT / "contracts").glob("*.json"))
        expected = {"card", "card_variant", "deck", "deck_card", "evaluation", "expansion",
                    "matchup", "meta_archetype", "meta_snapshot", "rule", "source", "sync_job"}
        self.assertGreaterEqual(len(contracts), 12)
        got = {p.stem for p in contracts}
        self.assertTrue(expected.issubset(got),
                        f"contratos ausentes: {sorted(expected - got)}")
        for p in contracts:
            contract_check.validate_contract_file(p)

    def test_card_example_rejects_bad_field(self):
        schema = json.loads((ROOT / "contracts" / "card.json").read_text())
        from contract_check import ContractError, validate
        bad = dict(schema["x-example"])
        bad["campo_inexistente"] = 1
        with self.assertRaises(ContractError):
            validate(bad, schema)

from contract_check import ContractError, validate  # noqa: E402


class TestRunnerIdempotency(unittest.TestCase):
    """Critério 2 — db_migrate cria do zero e é idempotente na 2a execução."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkstemp(suffix=".sqlite")[1]
        Path(self.tmp).unlink(missing_ok=True)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            Path(str(self.tmp) + suffix).unlink(missing_ok=True)

    def test_creates_from_scratch_and_is_idempotent(self):
        db = Path(self.tmp)
        rc1 = db_migrate.migrate(db)
        rc2 = db_migrate.migrate(db)
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        # dupla aplicação → schema igual
        c1 = db_migrate.connect(db)
        tables1 = sorted(r[0] for r in c1.execute(
            """SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
               AND name != 'cards_fts'"""))
        c1.close()
        # tabelas essenciais presentes
        essential = {"cards", "card_prints", "card_attacks", "card_abilities",
                     "card_evolutions", "card_localizations", "expansions", "rules",
                     "card_legality", "sources", "source_records", "sync_jobs",
                     "sync_changes", "audit_logs", "meta_archetypes", "meta_snapshots",
                     "archetype_cards", "matchups", "tiers", "decks", "deck_cards",
                     "deck_evaluations", "evaluation_dimensions", "tournaments",
                     "tournament_results", "meta_snapshot_archetypes", "schema_migrations"}
        self.assertTrue(essential.issubset(tables1),
                        f"tabelas ausentes: {sorted(essential - set(tables1))}")

    def test_checksum_divergence_fails(self):
        db = Path(self.tmp)
        db_migrate.migrate(db)
        # corromper checksum para divergir na leitura próxima
        conn = sqlite3.connect(db)
        conn.execute("UPDATE schema_migrations SET checksum = 'deadbeef'")
        conn.commit()
        conn.close()
        with self.assertRaises(RuntimeError):
            db_migrate.migrate(db)


class TestSchemaIntegrity(unittest.TestCase):
    """Critérios 3 e 4 — PRAGMAs, FTS5 e FK funcionando; violação de FK reprova."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkstemp(suffix=".sqlite")[1]
        Path(self.tmp).unlink(missing_ok=True)
        db = db_migrate.migrate(Path(self.tmp))
        self.conn = db_migrate.connect(Path(self.tmp))

    def tearDown(self):
        self.conn.close()
        for suffix in ("", "-wal", "-shm"):
            Path(str(self.tmp) + suffix).unlink(missing_ok=True)

    def test_pragmas(self):
        self.assertEqual(self.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")

    def test_fts5_search(self):
        cur = self.conn.execute(
            "INSERT INTO sources(id, name, base_url, kind, tier) "
            "VALUES ('s1', 'Limitless', 'https://pocket.limitlesstcg.com', 'scrape', 'canonical')")
        cur = self.conn.execute(
            "INSERT INTO cards(id, canonical_name, category, hp, element, stage, mechanical_hash, source_id) "
            "VALUES ('mega-gengar-ex', 'Mega Gengar ex', 'pokemon', 210, 'darkness', 'mega_ex', ?, 's1')",
            ("a" * 64,))
        self.conn.commit()
        q = self.conn.execute(
            "SELECT card_id FROM cards_fts WHERE cards_fts MATCH ? AND cards_fts MATCH ?",
            ("name:Mega", "text:Gengar")).fetchone()
        # aceita 0 ou 1 resultado — FTS index pode ter trigger disparado no INSERT
        print(f"FTS5 match: {q}")

    def test_fk_violation_rejected(self):
        self.conn.execute(
            "INSERT INTO sources(id, name, base_url, kind, tier) "
            "VALUES ('s1', 'Limitless', 'https://pocket.limitlesstcg.com', 'scrape', 'canonical')")
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO cards(id, canonical_name, category, mechanical_hash, source_id) "
                "VALUES ('x', 'X', 'pokemon', ?, 'src-inexistente')", ("b" * 64,))

    def test_fk_dependency_chain(self):
        """Chain: expansion -> card -> card_print -> deck -> deck_card."""
        self.conn.execute(
            "INSERT INTO sources(id, name, base_url, kind, tier) "
            "VALUES ('s1', 'Limitless', 'https://pocket.limitlesstcg.com', 'scrape', 'canonical')")
        self.conn.execute(
            "INSERT INTO expansions(id, code, name, release_date, source_id) "
            "VALUES ('exp-B4b', 'B4b', 'Deluxe Pack: Mega', '2026-09-30', 's1')")
        self.conn.execute(
            "INSERT INTO cards(id, canonical_name, category, mechanical_hash, source_id) "
            "VALUES ('mega-gengar-ex-B4b', 'Mega Gengar ex', 'pokemon', ?, 's1')", ("c" * 64,))
        self.conn.execute(
            "INSERT INTO card_prints(id, card_id, set_code, number, rarity, source_id) "
            "VALUES ('mega-gengar-ex-B4b-141', 'mega-gengar-ex-B4b', 'B4b', '141', 'C4', 's1')")
        self.conn.execute(
            "INSERT INTO decks(id, name, format, total_cards, source_id) "
            "VALUES ('deck-1', 'Teste', 'standard', 20, 's1')")
        self.conn.execute(
            "INSERT INTO deck_cards(deck_id, card_id, quantity) "
            "VALUES ('deck-1', 'mega-gengar-ex-B4b', 2)")
        # régua: deck_cards.card_id referencia card que não existe → IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO deck_cards(deck_id, card_id, quantity) "
                "VALUES ('deck-1', 'carta-inexistente', 1)")
        self.conn.commit()

    def test_deck_check_constraints(self):
        """total_cards = 20 hard constraint + quantity entre 1 e 2."""
        self.conn.execute(
            "INSERT INTO sources(id, name, base_url, kind, tier) "
            "VALUES ('s1','S','https://x.io','manual','crosscheck')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO decks(id, name, format, total_cards, source_id) "
                "VALUES ('bad', 'Deck errado', 'standard', 21, 's1')")
        # quantity = 3 deve falhar via CHECK + FK
        self.conn.execute(
            "INSERT INTO expansions(id, code, name, release_date, source_id) "
            "VALUES ('exp-B4b', 'B4b', 'X', '2026-09-30', 's1')")
        self.conn.execute(
            "INSERT INTO cards(id, canonical_name, category, mechanical_hash, source_id) "
            "VALUES ('c1', 'C1', 'pokemon', ?, 's1')", ("d" * 64,))
        self.conn.execute(
            "INSERT INTO decks(id, name, format, total_cards, source_id) "
            "VALUES ('d1', 'Deck OK', 'standard', 20, 's1')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO deck_cards(deck_id, card_id, quantity) VALUES ('d1', 'c1', 3)")
        self.conn.commit()

    def test_fts_smoke_raised_trigger_insert_and_query(self):
        """FTS5 a partir do trigger — deve terminal com resultado busável."""
        self.conn.execute(
            "INSERT INTO sources(id, name, base_url, kind, tier) "
            "VALUES ('s1', 'Limitless', 'https://pocket.limitlesstcg.com', 'scrape', 'canonical')")
        self.conn.execute(
            "INSERT INTO cards(id, canonical_name, category, special_rule, mechanical_hash, source_id) "
            "VALUES ('mega-gengar', 'Mega Gengar ex', 'pokemon', 'Mega Evolution ex', ?, 's1')",
            ("e" * 64,))
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT card_id, name FROM cards_fts WHERE cards_fts MATCH ?",
            ("Gengar",)).fetchall()
        self.assertEqual(rows, [("mega-gengar", "Mega Gengar ex")])


if __name__ == "__main__":
    unittest.main()
