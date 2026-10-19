-- 0002_dedupe_child_tables.sql - F4c - Deduplicacao das tabelas-filhas + UNIQUE:
-- loader usava INSERT OR IGNORE sem UNIQUE em card_attacks/card_abilities;
-- cada reprocesso re-inseria linhas identicas. Auditoria (audit_dupes.py)
-- provou duplicatas byte-identicas: dedupe por MIN(id) e lossless.
PRAGMA foreign_keys = OFF;
DROP TABLE IF EXISTS card_attacks_dup_bak;
ALTER TABLE card_attacks RENAME TO card_attacks_dup_bak;
CREATE TABLE IF NOT EXISTS card_attacks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    energy_cost TEXT NOT NULL DEFAULT '[]',
    damage      INTEGER,
    effect_text TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (card_id, name)
);
CREATE INDEX IF NOT EXISTS idx_card_attacks_card ON card_attacks(card_id);
INSERT INTO card_attacks(id, card_id, name, energy_cost, damage, effect_text, sort_order)
SELECT MIN(id), card_id, name, energy_cost, damage, effect_text, sort_order
FROM card_attacks_dup_bak GROUP BY card_id, name;
DROP TABLE card_attacks_dup_bak;
DROP TABLE IF EXISTS card_abilities_dup_bak;
ALTER TABLE card_abilities RENAME TO card_abilities_dup_bak;
CREATE TABLE IF NOT EXISTS card_abilities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'ability' CHECK (kind IN ('ability','ancient_trait')),
    effect_text TEXT NOT NULL,
    UNIQUE (card_id, name)
);
CREATE INDEX IF NOT EXISTS idx_card_abilities_card ON card_abilities(card_id);
INSERT INTO card_abilities(id, card_id, name, kind, effect_text)
SELECT MIN(id), card_id, name, kind, effect_text
FROM card_abilities_dup_bak GROUP BY card_id, name;
DROP TABLE card_abilities_dup_bak;
PRAGMA foreign_keys = ON;