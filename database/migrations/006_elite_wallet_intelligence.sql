PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS elite_wallet_intelligence_runs (
    run_id TEXT PRIMARY KEY,
    engine_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    wallets_read INTEGER NOT NULL DEFAULT 0,
    profiles_created INTEGER NOT NULL DEFAULT 0,
    profiles_updated INTEGER NOT NULL DEFAULT 0,
    profiles_unchanged INTEGER NOT NULL DEFAULT 0,
    events_published INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS elite_wallet_profiles (
    wallet TEXT PRIMARY KEY,
    profile_checksum TEXT NOT NULL,
    wallet_score REAL NOT NULL DEFAULT 0,
    wallet_grade TEXT NOT NULL DEFAULT 'PASS',
    elite_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    total_positions INTEGER NOT NULL DEFAULT 0,
    resolved_positions INTEGER NOT NULL DEFAULT 0,
    winning_positions INTEGER NOT NULL DEFAULT 0,
    losing_positions INTEGER NOT NULL DEFAULT 0,
    realized_pnl REAL NOT NULL DEFAULT 0,
    unrealized_pnl REAL NOT NULL DEFAULT 0,
    total_pnl REAL NOT NULL DEFAULT 0,
    deployed_capital REAL NOT NULL DEFAULT 0,
    roi_percent REAL NOT NULL DEFAULT 0,
    hit_rate REAL NOT NULL DEFAULT 0,
    consistency_score REAL NOT NULL DEFAULT 0,
    conviction_score REAL NOT NULL DEFAULT 0,
    sizing_discipline_score REAL NOT NULL DEFAULT 0,
    specialization_score REAL NOT NULL DEFAULT 0,
    activity_score REAL NOT NULL DEFAULT 0,
    data_quality_score REAL NOT NULL DEFAULT 0,
    primary_category TEXT,
    category_count INTEGER NOT NULL DEFAULT 0,
    average_position_value REAL NOT NULL DEFAULT 0,
    largest_position_value REAL NOT NULL DEFAULT 0,
    average_entry_price REAL,
    average_current_price REAL,
    first_seen_at TEXT,
    last_seen_at TEXT,
    model_version TEXT NOT NULL,
    first_profiled_at TEXT NOT NULL,
    last_profiled_at TEXT NOT NULL,
    last_run_id TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_elite_wallet_score
ON elite_wallet_profiles(elite_status, wallet_score DESC);

CREATE INDEX IF NOT EXISTS idx_elite_wallet_category
ON elite_wallet_profiles(primary_category, wallet_score DESC);

CREATE TABLE IF NOT EXISTS elite_wallet_profile_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    profile_checksum TEXT NOT NULL,
    wallet_score REAL NOT NULL,
    wallet_grade TEXT NOT NULL,
    elite_status TEXT NOT NULL,
    total_positions INTEGER NOT NULL,
    resolved_positions INTEGER NOT NULL,
    winning_positions INTEGER NOT NULL,
    losing_positions INTEGER NOT NULL,
    total_pnl REAL NOT NULL,
    deployed_capital REAL NOT NULL,
    roi_percent REAL NOT NULL,
    hit_rate REAL NOT NULL,
    consistency_score REAL NOT NULL,
    conviction_score REAL NOT NULL,
    sizing_discipline_score REAL NOT NULL,
    specialization_score REAL NOT NULL,
    activity_score REAL NOT NULL,
    data_quality_score REAL NOT NULL,
    primary_category TEXT,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    run_id TEXT NOT NULL,
    UNIQUE(wallet, profile_checksum)
);

CREATE TABLE IF NOT EXISTS elite_wallet_category_profiles (
    wallet TEXT NOT NULL,
    category TEXT NOT NULL,
    profile_checksum TEXT NOT NULL,
    position_count INTEGER NOT NULL DEFAULT 0,
    resolved_positions INTEGER NOT NULL DEFAULT 0,
    winning_positions INTEGER NOT NULL DEFAULT 0,
    losing_positions INTEGER NOT NULL DEFAULT 0,
    total_pnl REAL NOT NULL DEFAULT 0,
    deployed_capital REAL NOT NULL DEFAULT 0,
    roi_percent REAL NOT NULL DEFAULT 0,
    hit_rate REAL NOT NULL DEFAULT 0,
    category_score REAL NOT NULL DEFAULT 0,
    category_grade TEXT NOT NULL DEFAULT 'PASS',
    first_seen_at TEXT,
    last_seen_at TEXT,
    last_run_id TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(wallet, category)
);

DROP VIEW IF EXISTS ranked_elite_wallets;
CREATE VIEW ranked_elite_wallets AS
SELECT
    ROW_NUMBER() OVER (
        ORDER BY
            CASE elite_status
                WHEN 'ELITE' THEN 1
                WHEN 'QUALIFIED' THEN 2
                WHEN 'WATCHLIST' THEN 3
                ELSE 4
            END,
            wallet_score DESC,
            total_pnl DESC,
            resolved_positions DESC
    ) AS rank,
    *
FROM elite_wallet_profiles;

DROP VIEW IF EXISTS ranked_elite_wallet_categories;
CREATE VIEW ranked_elite_wallet_categories AS
SELECT
    ROW_NUMBER() OVER (
        PARTITION BY category
        ORDER BY category_score DESC, total_pnl DESC, resolved_positions DESC
    ) AS category_rank,
    *
FROM elite_wallet_category_profiles;
