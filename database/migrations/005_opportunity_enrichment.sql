PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS opportunity_enrichment_runs (
    run_id TEXT PRIMARY KEY,
    engine_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    opportunities_read INTEGER NOT NULL DEFAULT 0,
    enrichments_created INTEGER NOT NULL DEFAULT 0,
    enrichments_updated INTEGER NOT NULL DEFAULT 0,
    events_published INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS opportunity_enrichment_current (
    opportunity_id TEXT PRIMARY KEY,
    market_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    title TEXT,
    category TEXT,

    source_state_checksum TEXT NOT NULL,
    enrichment_checksum TEXT NOT NULL,

    opportunity_score REAL NOT NULL,
    opportunity_grade TEXT NOT NULL,
    recommendation TEXT NOT NULL,

    wallet_count INTEGER NOT NULL DEFAULT 0,
    elite_wallet_count INTEGER NOT NULL DEFAULT 0,
    combined_capital REAL NOT NULL DEFAULT 0,

    wallet_quality_score REAL NOT NULL DEFAULT 0,
    capital_strength_score REAL NOT NULL DEFAULT 0,
    timing_score REAL NOT NULL DEFAULT 0,
    timing_status TEXT NOT NULL DEFAULT 'UNKNOWN',

    current_price REAL,
    liquidity REAL,
    spread REAL,
    market_structure_score REAL NOT NULL DEFAULT 0,
    historical_reliability_score REAL NOT NULL DEFAULT 0,
    data_completeness_score REAL NOT NULL DEFAULT 0,

    source_cluster_id TEXT,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    model_version TEXT NOT NULL,
    first_enriched_at TEXT NOT NULL,
    last_enriched_at TEXT NOT NULL,
    last_run_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enrichment_rank
ON opportunity_enrichment_current(
    recommendation,
    opportunity_score DESC,
    data_completeness_score DESC
);

CREATE INDEX IF NOT EXISTS idx_enrichment_market
ON opportunity_enrichment_current(market_id, outcome);

CREATE TABLE IF NOT EXISTS opportunity_enrichment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    enrichment_checksum TEXT NOT NULL,
    opportunity_score REAL NOT NULL,
    recommendation TEXT NOT NULL,
    wallet_count INTEGER NOT NULL,
    elite_wallet_count INTEGER NOT NULL,
    combined_capital REAL NOT NULL,
    wallet_quality_score REAL NOT NULL,
    capital_strength_score REAL NOT NULL,
    timing_score REAL NOT NULL,
    market_structure_score REAL NOT NULL,
    historical_reliability_score REAL NOT NULL,
    data_completeness_score REAL NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    run_id TEXT NOT NULL,
    UNIQUE(opportunity_id, enrichment_checksum)
);

DROP VIEW IF EXISTS ranked_opportunity_enrichment;
CREATE VIEW ranked_opportunity_enrichment AS
SELECT
    ROW_NUMBER() OVER (
        ORDER BY
            CASE recommendation
                WHEN 'ACTIONABLE' THEN 1
                WHEN 'WATCHLIST' THEN 2
                WHEN 'MONITOR' THEN 3
                ELSE 4
            END,
            opportunity_score DESC,
            data_completeness_score DESC,
            combined_capital DESC
    ) AS rank,
    *
FROM opportunity_enrichment_current;
