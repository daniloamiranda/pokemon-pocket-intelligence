"""F4c · TDD: idempotência do loader em tabelas-filhas.

Regressão do defeito F4b achado na auditoria: INSERT OR IGNORE sem UNIQUE
re-inseria linhas idênticas a cada reprocesso (card_attacks 3.22x,
card_abilities 4.4x). O loader corrigido usa UNIQUE(card_id,name) +
ON CONFLICT DO UPDATE. Teste: mesma entrada carregada DUAS vezes deve
deixar todas as contagens idênticas entre executions 1 e 2.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "integrations" / "limitlesstcg-pocket"))

import sqlite3  # noqa: E402
import loader as L  # noqa: E402


def make_db():
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE sources(id TEXT PRIMARY KEY, name TEXT, base_url TEXT, kind TEXT,
                             tier TEXT, policy TEXT, requires_key INTEGER, notes TEXT);
        CREATE TABLE cards(id TEXT PRIMARY KEY, canonical_name TEXT, category TEXT,
            element TEXT, stage TEXT, hp INTEGER, weakness_element TEXT,
            retreat_cost INTEGER, special_rule TEXT, mechanical_hash TEXT UNIQUE,
            is_ex INTEGER, source_id TEXT REFERENCES sources(id), verified_at TEXT,
            validation_status TEXT, evolves_from_id TEXT);
        CREATE TABLE card_attacks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT REFERENCES cards(id) ON DELETE CASCADE,
            name TEXT, energy_cost TEXT DEFAULT '[]', damage INTEGER,
            effect_text TEXT, sort_order INTEGER DEFAULT 0,
            UNIQUE (card_id, name));
        CREATE TABLE card_abilities(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT REFERENCES cards(id) ON DELETE CASCADE,
            name TEXT, kind TEXT DEFAULT 'ability', effect_text TEXT,
            UNIQUE (card_id, name));
        CREATE TABLE card_localizations(card_id TEXT, lang TEXT, name TEXT,
            PRIMARY KEY (card_id, lang));
        CREATE TABLE card_prints(id TEXT PRIMARY KEY, card_id TEXT, set_code TEXT,
            number TEXT, rarity TEXT, artist TEXT, image_url TEXT,
            source_id TEXT REFERENCES sources(id), UNIQUE(card_id, set_code, number));
        CREATE TABLE card_evolutions(card_id TEXT REFERENCES cards(id) ON DELETE CASCADE,
            pre_evo_card_id TEXT REFERENCES cards(id), stage TEXT,
            PRIMARY KEY (card_id, pre_evo_card_id));
        CREATE TABLE card_evolution_slugs(card_id TEXT PRIMARY KEY, slug TEXT NOT NULL);
    """)
    db.execute("INSERT INTO sources(id) VALUES (?)", (L.SOURCE_ID,))
    return db


CARD = {
    "set": "A1", "number": "129", "name": "Mewtwo ex", "category": "pokemon",
    "stage": "basic", "hp": 180, "element": "psychic", "is_ex": 1,
    "attacks": [
        {"name": "Psychic Sphere", "energy_cost": ["psychic", "colorless"],
         "damage": 50, "effect_text": None},
        {"name": "Psydrive", "energy_cost": ["psychic", "psychic", "colorless"],
         "damage": 150, "effect_text": "Discard 2 [P] Energy from this Pokémon."},
    ],
    "abilities": [{"name": "PS Psychic", "kind": "ability",
                   "effect_text": "Once during your turn, you may..."}],
    "versions": [], "print_rarity": None, "image_url": None,
}


class TestLoaderIdempotentChildren(unittest.TestCase):
    """Aceite F4c: DUAS execucoes do loader => contagens identicas."""

    def test_two_runs_identical_counts(self):
        db = make_db()
        for _ in range(2):
            L.load_card(db, CARD)
        counts = lambda: (
            db.execute("SELECT count(*) FROM cards").fetchone()[0],
            db.execute("SELECT count(*) FROM card_attacks").fetchone()[0],
            db.execute("SELECT count(*) FROM card_abilities").fetchone()[0],
            db.execute("SELECT count(*) FROM card_prints").fetchone()[0],
        )
        c2 = counts()
        self.assertEqual(c2[1], 2)  # 2 ataques, nao 4
        self.assertEqual(c2[2], 1)  # 1 habilidade, nao 2
        for _ in range(3):          # execucoes repetidas NAO mudam nada
            L.load_card(db, CARD)
        self.assertEqual(counts(), c2)

    def test_mewtwo_exactly_two_attacks(self):
        db = make_db()
        L.load_card(db, CARD)
        L.load_card(db, CARD)
        rows = db.execute(
            "SELECT name, damage FROM card_attacks ORDER BY sort_order").fetchall()
        self.assertEqual(rows, [("Psychic Sphere", 50), ("Psydrive", 150)])

    def test_zero_dupe_pairs(self):
        db = make_db()
        for _ in range(2):
            L.load_card(db, CARD)
        d_atk = db.execute(
            "SELECT count(*) FROM (SELECT card_id,name FROM card_attacks "
            "GROUP BY card_id,name HAVING count(*)>1)").fetchone()[0]
        d_ab = db.execute(
            "SELECT count(*) FROM (SELECT card_id,name FROM card_abilities "
            "GROUP BY card_id,name HAVING count(*)>1)").fetchone()[0]
        self.assertEqual((d_atk, d_ab), (0, 0))

    def test_upsert_refreshes_changed_damage(self):
        db = make_db()
        L.load_card(db, CARD)
        changed = {**CARD, "attacks": [dict(CARD["attacks"][0], damage=60),
                                       CARD["attacks"][1]]}
        L.load_card(db, changed)
        dmg = db.execute("SELECT damage FROM card_attacks WHERE name='Psychic Sphere'"
                         ).fetchone()[0]
        self.assertEqual(dmg, 60)
        self.assertEqual(db.execute(
            "SELECT count(*) FROM card_attacks").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
