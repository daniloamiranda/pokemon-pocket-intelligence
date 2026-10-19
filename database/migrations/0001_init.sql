-- 0001_init.sql — Fase 2 · Schema canônico do SQLite Pokémon Pocket Intelligence
-- Fonte: docs/FASE1-DIAGNOSTICO.md §8 (modelo relacional auditado).
-- Princípios: chaves estáveis, UNIQUE em chave natural, upsert sem overwrite destrutivo,
-- audit_logs em toda alteração, foreign_keys sempre ativas (PRAGMA pela conexão).

PRAGMA foreign_keys = ON;

-- ========================================================= FONTE DE VERDADE
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    checksum    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    base_url    TEXT,
    kind        TEXT NOT NULL CHECK (kind IN ('api','scrape','dataset','manual','rulebook')),
    tier        TEXT NOT NULL CHECK (tier IN ('canonical','crosscheck','enrichment')),
    policy      TEXT,
    requires_key INTEGER NOT NULL DEFAULT 0 CHECK (requires_key IN (0,1)),
    notes       TEXT
);

-- ========================================================= NÚCLEO DE CARTAS
CREATE TABLE IF NOT EXISTS expansions (
    id           TEXT PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    series       TEXT,
    release_date TEXT NOT NULL,
    card_count   INTEGER NOT NULL DEFAULT 0 CHECK (card_count >= 0),
    source_id    TEXT NOT NULL REFERENCES sources(id),
    collected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    verified_at  TEXT
);

CREATE TABLE IF NOT EXISTS cards (
    id               TEXT PRIMARY KEY,
    canonical_name   TEXT NOT NULL,
    category         TEXT NOT NULL CHECK (category IN
                       ('pokemon','trainer_item','trainer_supporter','trainer_stadium',
                        'pokemon_tool','energy_basic','energy_special')),
    element          TEXT CHECK (element IN ('grass','fire','water','lightning','psychic',
                                             'fighting','darkness','metal','dragon','colorless')),
    stage            TEXT CHECK (stage IN ('basic','stage1','stage2','mega_ex')),
    evolves_from_id  TEXT REFERENCES cards(id),
    hp               INTEGER CHECK (hp IS NULL OR hp >= 0),
    weakness_element TEXT CHECK (weakness_element IS NULL OR weakness_element IN
                       ('grass','fire','water','lightning','psychic','fighting','darkness','metal')),
    retreat_cost     INTEGER CHECK (retreat_cost IS NULL OR retreat_cost BETWEEN 0 AND 4),
    special_rule     TEXT,
    mechanical_hash  TEXT NOT NULL,
    is_ex            INTEGER NOT NULL DEFAULT 0 CHECK (is_ex IN (0,1)),
    source_id        TEXT NOT NULL REFERENCES sources(id),
    collected_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    verified_at      TEXT,
    validation_status TEXT NOT NULL DEFAULT 'pending'
                       CHECK (validation_status IN ('pending','verified','divergent','rejected'))
);
CREATE INDEX IF NOT EXISTS idx_cards_canonical_name ON cards(canonical_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_mech_hash ON cards(mechanical_hash, source_id);

CREATE TABLE IF NOT EXISTS card_attacks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    energy_cost TEXT NOT NULL DEFAULT '[]',        -- JSON array de elementos
    damage      INTEGER,
    effect_text TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_card_attacks_card ON card_attacks(card_id);

CREATE TABLE IF NOT EXISTS card_abilities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'ability' CHECK (kind IN ('ability','ancient_trait')),
    effect_text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_card_abilities_card ON card_abilities(card_id);

CREATE TABLE IF NOT EXISTS card_evolutions (
    card_id        TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    pre_evo_card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE RESTRICT,
    stage          TEXT NOT NULL CHECK (stage IN ('stage1','stage2','mega_ex')),
    PRIMARY KEY (card_id, pre_evo_card_id)
);

CREATE TABLE IF NOT EXISTS card_localizations (
    card_id     TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    lang        TEXT NOT NULL CHECK (LENGTH(lang) = 5),   -- 'en', 'pt-BR'
    name        TEXT NOT NULL,
    effect_text TEXT,
    PRIMARY KEY (card_id, lang)
);

CREATE TABLE IF NOT EXISTS card_prints (
    id           TEXT PRIMARY KEY,
    card_id      TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    set_code     TEXT NOT NULL REFERENCES expansions(code),
    number       TEXT NOT NULL,
    rarity       TEXT,
    artist       TEXT,
    image_url    TEXT,        -- URL apenas; nenhuma arte redistribuída
    is_promo     INTEGER NOT NULL DEFAULT 0 CHECK (is_promo IN (0,1)),
    source_id    TEXT NOT NULL REFERENCES sources(id),
    collected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (card_id, set_code, number)
);
CREATE INDEX IF NOT EXISTS idx_card_prints_set_num ON card_prints(set_code, number);

CREATE TABLE IF NOT EXISTS card_legality (
    card_id   TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    format    TEXT NOT NULL,
    legal     INTEGER NOT NULL CHECK (legal IN (0,1)),
    from_date TEXT NOT NULL,
    to_date   TEXT,
    reason    TEXT,
    PRIMARY KEY (card_id, format, from_date)
);

-- ========================================================= REGRAS
CREATE TABLE IF NOT EXISTS rules (
    id          TEXT PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    category    TEXT NOT NULL CHECK (category IN
                  ('deck_size','copies_limit','legality','evolution','restriction','format','governance')),
    source_id   TEXT NOT NULL REFERENCES sources(id),
    verified_at TEXT NOT NULL,
    valid_from  TEXT NOT NULL,
    valid_to    TEXT,
    exceptions  TEXT NOT NULL DEFAULT '[]',   -- JSON array
    examples    TEXT NOT NULL DEFAULT '[]'    -- JSON array
);

-- ========================================================= METAGAME
CREATE TABLE IF NOT EXISTS meta_archetypes (
    id        TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    tier      TEXT CHECK (tier IN ('A','B','C','D','F','unknown')),
    tier_basis TEXT,                          -- obrigatório preenchido quando tier != NULL (app-level)
    core_cards TEXT NOT NULL DEFAULT '[]',    -- JSON array de card_id
    source_id TEXT NOT NULL REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS archetype_cards (
    archetype_id TEXT NOT NULL REFERENCES meta_archetypes(id) ON DELETE CASCADE,
    card_id      TEXT NOT NULL REFERENCES cards(id),
    PRIMARY KEY (archetype_id, card_id)
);

CREATE TABLE IF NOT EXISTS meta_snapshots (
    id               TEXT PRIMARY KEY,
    window_start     TEXT NOT NULL,
    window_end       TEXT NOT NULL,
    scope            TEXT NOT NULL,
    tournament_count INTEGER NOT NULL DEFAULT 0 CHECK (tournament_count >= 0),
    decklist_count   INTEGER NOT NULL DEFAULT 0 CHECK (decklist_count >= 0),
    match_count      INTEGER NOT NULL DEFAULT 0 CHECK (match_count >= 0),
    source_id        TEXT NOT NULL REFERENCES sources(id),
    collected_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS meta_snapshot_archetypes (
    snapshot_id   TEXT NOT NULL REFERENCES meta_snapshots(id) ON DELETE CASCADE,
    archetype_id  TEXT NOT NULL REFERENCES meta_archetypes(id),
    share_pct     REAL CHECK (share_pct IS NULL OR share_pct BETWEEN 0 AND 100),
    win_rate_pct  REAL CHECK (win_rate_pct IS NULL OR win_rate_pct BETWEEN 0 AND 100),
    tier          TEXT CHECK (tier IN ('A','B','C','D','F','unknown')),
    PRIMARY KEY (snapshot_id, archetype_id)
);

CREATE TABLE IF NOT EXISTS matchups (
    id             TEXT PRIMARY KEY,
    archetype_a    TEXT NOT NULL REFERENCES meta_archetypes(id),
    archetype_b    TEXT NOT NULL REFERENCES meta_archetypes(id),
    win_rate_a_pct REAL NOT NULL CHECK (win_rate_a_pct BETWEEN 0 AND 100),
    sample_size    INTEGER NOT NULL CHECK (sample_size >= 1),
    window_period  TEXT NOT NULL,
    source_id      TEXT NOT NULL REFERENCES sources(id),
    confidence     TEXT NOT NULL CHECK (confidence IN ('low','medium','high')),
    UNIQUE (archetype_a, archetype_b, window_period, source_id)
);
CREATE INDEX IF NOT EXISTS idx_matchups_pair ON matchups(archetype_a, archetype_b, window_period);

CREATE TABLE IF NOT EXISTS tiers (
    id           TEXT PRIMARY KEY,
    snapshot_id  TEXT NOT NULL REFERENCES meta_snapshots(id) ON DELETE CASCADE,
    archetype_id TEXT NOT NULL REFERENCES meta_archetypes(id),
    tier         TEXT NOT NULL CHECK (tier IN ('A','B','C','D','F','unknown')),
    basis        TEXT NOT NULL,
    UNIQUE (snapshot_id, archetype_id)
);

CREATE TABLE IF NOT EXISTS tournaments (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    date        TEXT NOT NULL,
    format      TEXT NOT NULL,
    source_id   TEXT NOT NULL REFERENCES sources(id),
    collected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS tournament_results (
    tournament_id TEXT NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    placement     INTEGER NOT NULL CHECK (placement >= 1),
    deck_id       TEXT REFERENCES decks(id),
    archetype_id  TEXT REFERENCES meta_archetypes(id),
    PRIMARY KEY (tournament_id, placement, deck_id)
);

-- ========================================================= DECKS
CREATE TABLE IF NOT EXISTS decks (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    format       TEXT NOT NULL,
    total_cards  INTEGER NOT NULL CHECK (total_cards = 20),
    archetype_id TEXT REFERENCES meta_archetypes(id),
    source_id    TEXT NOT NULL REFERENCES sources(id),
    collected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS deck_cards (
    deck_id  TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id  TEXT NOT NULL REFERENCES cards(id),
    print_id TEXT REFERENCES card_prints(id),
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 2),
    PRIMARY KEY (deck_id, card_id, print_id)
);

CREATE TABLE IF NOT EXISTS deck_evaluations (
    id           TEXT PRIMARY KEY,
    deck_id      TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    overall_score REAL NOT NULL CHECK (overall_score BETWEEN 0 AND 10),
    dimensions   TEXT NOT NULL,                -- JSON [{name,score,weight,reason}]
    weights_doc  TEXT NOT NULL,
    confidence   TEXT NOT NULL CHECK (confidence IN ('theoretical','low','medium','high')),
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS evaluation_dimensions (
    name    TEXT PRIMARY KEY,
    default_weight REAL NOT NULL CHECK (default_weight BETWEEN 0 AND 1),
    description TEXT
);

-- ========================================================= GOVERNANÇA DE DADOS
CREATE TABLE IF NOT EXISTS source_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL REFERENCES sources(id),
    table_name   TEXT NOT NULL,
    record_key   TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    seen_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (source_id, table_name, record_key)
);

CREATE TABLE IF NOT EXISTS sync_jobs (
    id           TEXT PRIMARY KEY,
    source_id    TEXT NOT NULL REFERENCES sources(id),
    direction    TEXT NOT NULL CHECK (direction IN ('pull','push')),
    entity       TEXT NOT NULL CHECK (entity IN ('cards','card_prints','meta','decks','matchups','sheets')),
    cursor       TEXT,
    status       TEXT NOT NULL CHECK (status IN ('pending','running','success','failed','skipped')),
    started_at   TEXT,
    finished_at  TEXT,
    items_changed INTEGER NOT NULL DEFAULT 0 CHECK (items_changed >= 0),
    error        TEXT
);

CREATE TABLE IF NOT EXISTS sync_changes (
    job_id      TEXT NOT NULL REFERENCES sync_jobs(id) ON DELETE CASCADE,
    table_name  TEXT NOT NULL,
    record_key  TEXT NOT NULL,
    change_kind TEXT NOT NULL CHECK (change_kind IN ('insert','update','delete','conflict')),
    content_hash TEXT NOT NULL,
    PRIMARY KEY (job_id, table_name, record_key)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    actor       TEXT NOT NULL,
    table_name  TEXT NOT NULL,
    record_key  TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('insert','update','delete','restore')),
    before_json TEXT,
    after_json  TEXT,
    reason      TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_table ON audit_logs(table_name, record_key);

-- ========================================================= FTS5 (nomes/efeitos)
CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(
    card_id UNINDEXED,
    name,
    text
);
-- Rebuild triggers: manter em sync com cards / card_attacks / card_abilities
CREATE TRIGGER IF NOT EXISTS trg_cards_fts_insert AFTER INSERT ON cards BEGIN
    INSERT INTO cards_fts(card_id, name, text)
    VALUES (NEW.id, NEW.canonical_name, COALESCE(NEW.special_rule,''));
END;
CREATE TRIGGER IF NOT EXISTS trg_cards_fts_delete AFTER DELETE ON cards BEGIN
    DELETE FROM cards_fts WHERE card_id = OLD.id;
END;

PRAGMA foreign_keys = ON;
