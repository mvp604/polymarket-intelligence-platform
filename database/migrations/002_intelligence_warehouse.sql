PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS intelligence_warehouse_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    wallet_rows INTEGER NOT NULL DEFAULT 0,
    market_rows INTEGER NOT NULL DEFAULT 0,
    signal_rows INTEGER NOT NULL DEFAULT 0,
    source_tables_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS intelligence_wallets (
    wallet TEXT PRIMARY KEY,
    performance_score REAL,
    performance_grade TEXT,
    confidence_score REAL,
    data_confidence TEXT,
    resolved_positions INTEGER,
    wins INTEGER,
    losses INTEGER,
    win_rate REAL,
    estimated_profit REAL,
    estimated_roi REAL,
    average_entry_price REAL,
    calibration_score REAL,
    unresolved_positions INTEGER,
    trend TEXT,
    source_table TEXT,
    source_updated_at TEXT,
    warehouse_updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS intelligence_markets (
    market_id TEXT PRIMARY KEY,
    question TEXT,
    category TEXT,
    outcome TEXT,
    current_price REAL,
    liquidity REAL,
    volume REAL,
    spread REAL,
    opportunity_score REAL,
    health_score REAL,
    risk_score REAL,
    wallet_score REAL,
    consensus_score REAL,
    signal_grade TEXT,
    signal_status TEXT,
    source_table TEXT,
    source_updated_at TEXT,
    warehouse_updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS intelligence_signals (
    signal_key TEXT PRIMARY KEY,
    market_id TEXT,
    question TEXT,
    selected_outcome TEXT,
    signal_grade TEXT,
    signal_score REAL,
    confidence_score REAL,
    entry_price REAL,
    result_status TEXT,
    units_result REAL,
    roi REAL,
    generated_at TEXT,
    resolved_at TEXT,
    source_table TEXT,
    warehouse_updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_intelligence_wallet_grade
    ON intelligence_wallets(performance_grade, performance_score DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_market_opportunity
    ON intelligence_markets(opportunity_score DESC, health_score DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_market_status
    ON intelligence_markets(signal_status, signal_grade);

CREATE INDEX IF NOT EXISTS idx_intelligence_signal_result
    ON intelligence_signals(result_status, signal_grade);

CREATE VIEW IF NOT EXISTS intelligence_top_wallets AS
SELECT *
FROM intelligence_wallets
ORDER BY
    CASE WHEN performance_grade = 'UNRATED' THEN 1 ELSE 0 END,
    performance_score DESC,
    confidence_score DESC;

CREATE VIEW IF NOT EXISTS intelligence_top_markets AS
SELECT *
FROM intelligence_markets
ORDER BY
    opportunity_score DESC,
    health_score DESC,
    risk_score ASC;

CREATE VIEW IF NOT EXISTS intelligence_signal_ledger AS
SELECT *
FROM intelligence_signals
ORDER BY
    COALESCE(generated_at, warehouse_updated_at) DESC;