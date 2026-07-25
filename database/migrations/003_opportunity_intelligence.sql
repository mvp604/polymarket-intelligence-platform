PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS opportunity_engine_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    source_table TEXT,
    markets_reviewed INTEGER NOT NULL DEFAULT 0,
    scores_inserted INTEGER NOT NULL DEFAULT 0,
    scores_updated INTEGER NOT NULL DEFAULT 0,
    actionable_count INTEGER NOT NULL DEFAULT 0,
    watchlist_count INTEGER NOT NULL DEFAULT 0,
    pass_count INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS opportunity_scores (
    market_id TEXT PRIMARY KEY,
    question TEXT,
    category TEXT,
    selected_outcome TEXT,
    current_price REAL,
    opportunity_score REAL NOT NULL DEFAULT 0,
    confidence_score REAL NOT NULL DEFAULT 0,
    wallet_component REAL NOT NULL DEFAULT 0,
    consensus_component REAL NOT NULL DEFAULT 0,
    health_component REAL NOT NULL DEFAULT 0,
    liquidity_component REAL NOT NULL DEFAULT 0,
    momentum_component REAL NOT NULL DEFAULT 0,
    risk_penalty REAL NOT NULL DEFAULT 0,
    data_quality_score REAL NOT NULL DEFAULT 0,
    recommendation TEXT NOT NULL DEFAULT 'PASS',
    signal_grade TEXT NOT NULL DEFAULT 'PASS',
    risk_level TEXT NOT NULL DEFAULT 'HIGH',
    explanation_json TEXT NOT NULL DEFAULT '{}',
    source_table TEXT NOT NULL DEFAULT '',
    source_updated_at TEXT,
    calculated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS opportunity_score_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    opportunity_score REAL NOT NULL,
    confidence_score REAL NOT NULL,
    recommendation TEXT NOT NULL,
    signal_grade TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES opportunity_engine_runs(run_id)
);