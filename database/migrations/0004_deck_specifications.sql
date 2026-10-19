-- F8 · migration 0004 (ADITIVA): especificações de deck builder.
-- Execucao: python3 scripts/db_migrate.py (runner idempotente; checksum em schema_migrations).
CREATE TABLE IF NOT EXISTS deck_specifications (
    deck_id      TEXT PRIMARY KEY REFERENCES decks(id) ON DELETE CASCADE,
    spec_json    TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
