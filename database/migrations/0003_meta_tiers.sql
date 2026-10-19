-- 0003_meta_tiers.sql — F7 · Metagame: tier S, amostras, taxonomia Limitless e matches
-- Fonte: cartao t_04f33c18 (escopo F7) + docs/FASE1-DIAGNOSTICO.md §5/§8.
-- Aditivo (nenhuma coluna/tabela destruida): CHECKs novos nao podem restringir linhas
-- existentes — tabelas de meta estao vazias na data da migracao (prova no cartao).
-- Nota tecnica: CHECK de coluna nao e reescritavel em SQLite; para permitir tier 'S'
-- as tabelas tocadas sao reconstruidas e copiadas. vazio=sem evidencia (regra do escopo).

PRAGMA foreign_keys = OFF;

-- ---------- meta_archetypes: tier ganha 'S' e coluna de amostra ----------
CREATE TABLE meta_archetypes_new (
    id        TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    tier      TEXT CHECK (tier IN ('S','A','B','C','D','F','unknown','')),
    tier_basis TEXT,                          -- obrigatorio preenchido quando tier != NULL (app-level)
    core_cards TEXT NOT NULL DEFAULT '[]',    -- JSON array de card_id
    sample_decks INTEGER,                     -- decks do arquetipo na janela do tier (amostra citavel)
    source_id TEXT NOT NULL REFERENCES sources(id)
);
INSERT INTO meta_archetypes_new SELECT id, name, tier, tier_basis, core_cards, NULL, source_id FROM meta_archetypes;
DROP TABLE meta_archetypes;
ALTER TABLE meta_archetypes_new RENAME TO meta_archetypes;

-- ---------- meta_snapshot_archetypes: tier ganha 'S' + colunas de amostra ----------
CREATE TABLE meta_snapshot_archetypes_new (
    snapshot_id   TEXT NOT NULL REFERENCES meta_snapshots(id) ON DELETE CASCADE,
    archetype_id  TEXT NOT NULL REFERENCES meta_archetypes(id),
    share_pct     REAL CHECK (share_pct IS NULL OR share_pct BETWEEN 0 AND 100),
    win_rate_pct  REAL CHECK (win_rate_pct IS NULL OR win_rate_pct BETWEEN 0 AND 100),
    tier          TEXT CHECK (tier IN ('S','A','B','C','D','F','unknown','')),
    sample_decks  INTEGER,
    sample_matches INTEGER,
    PRIMARY KEY (snapshot_id, archetype_id)
);
INSERT INTO meta_snapshot_archetypes_new SELECT snapshot_id, archetype_id, share_pct, win_rate_pct, tier, NULL, NULL FROM meta_snapshot_archetypes;
DROP TABLE meta_snapshot_archetypes;
ALTER TABLE meta_snapshot_archetypes_new RENAME TO meta_snapshot_archetypes;

-- ---------- tiers: idem, com amostra citavel ----------
CREATE TABLE tiers_new (
    id           TEXT PRIMARY KEY,
    snapshot_id  TEXT NOT NULL REFERENCES meta_snapshots(id) ON DELETE CASCADE,
    archetype_id TEXT NOT NULL REFERENCES meta_archetypes(id),
    tier         TEXT NOT NULL CHECK (tier IN ('S','A','B','C','D','F','unknown','')),
    basis        TEXT NOT NULL,
    sample_decks  INTEGER,
    sample_matches INTEGER,
    UNIQUE (snapshot_id, archetype_id)
);
INSERT INTO tiers_new SELECT id, snapshot_id, archetype_id, tier, basis, NULL, NULL FROM tiers;
DROP TABLE tiers;
ALTER TABLE tiers_new RENAME TO tiers;

-- ---------- matchups: sample_matches citavel por confronto (aditivo) ----------
ALTER TABLE matchups ADD COLUMN sample_matches INTEGER;

-- ---------- matches individuais (base do winrate por confronto) ----------
CREATE TABLE IF NOT EXISTS tournament_matches (
    id             TEXT PRIMARY KEY,          -- {tournament_id}:{phase}:{round}:{seq}
    tournament_id  TEXT NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    phase          INTEGER NOT NULL,
    round          INTEGER NOT NULL,
    seq            INTEGER NOT NULL DEFAULT 0,
    player1        TEXT NOT NULL,
    player2        TEXT NOT NULL DEFAULT '',
    winner         TEXT NOT NULL DEFAULT '',  -- player id | '' empate/-1 double loss | 'bye'
    archetype1_id  TEXT REFERENCES meta_archetypes(id),
    archetype2_id  TEXT REFERENCES meta_archetypes(id),
    collected_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_tournament_matches_pair
    ON tournament_matches(archetype1_id, archetype2_id);

PRAGMA foreign_keys = ON;
