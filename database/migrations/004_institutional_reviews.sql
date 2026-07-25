PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS institutional_review_runs (
    run_id TEXT PRIMARY KEY,
    engine_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    source_events_read INTEGER NOT NULL DEFAULT 0,
    reviews_created INTEGER NOT NULL DEFAULT 0,
    reviews_skipped INTEGER NOT NULL DEFAULT 0,
    events_published INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS institutional_reviews (
    review_id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    title TEXT,
    category TEXT,

    source_event_id TEXT,
    source_event_type TEXT,
    source_state_checksum TEXT NOT NULL,

    opportunity_score REAL NOT NULL,
    opportunity_grade TEXT NOT NULL,
    opportunity_recommendation TEXT NOT NULL,

    institutional_confidence_score REAL NOT NULL,
    institutional_grade TEXT NOT NULL,
    institutional_decision TEXT NOT NULL,
    risk_level TEXT NOT NULL,

    wallet_strength_score REAL NOT NULL,
    capital_strength_score REAL NOT NULL,
    timing_strength_score REAL NOT NULL,
    market_quality_score REAL NOT NULL,
    reliability_score REAL NOT NULL,

    wallet_count INTEGER NOT NULL,
    elite_wallet_count INTEGER NOT NULL,
    combined_capital REAL NOT NULL,
    current_price REAL,
    timing_status TEXT NOT NULL,

    rationale TEXT NOT NULL,
    risk_flags_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '{}',

    model_version TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    run_id TEXT NOT NULL,

    UNIQUE(opportunity_id, source_state_checksum, model_version),
    FOREIGN KEY(run_id) REFERENCES institutional_review_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_institutional_reviews_opportunity_time
ON institutional_reviews(opportunity_id, reviewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_institutional_reviews_decision_score
ON institutional_reviews(institutional_decision, institutional_confidence_score DESC);

CREATE INDEX IF NOT EXISTS idx_institutional_reviews_market
ON institutional_reviews(market_id, outcome);

CREATE TABLE IF NOT EXISTS event_consumer_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consumer_name TEXT NOT NULL,
    event_id TEXT NOT NULL,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(consumer_name, event_id)
);

DROP VIEW IF EXISTS current_institutional_reviews;
CREATE VIEW current_institutional_reviews AS
SELECT r.*
FROM institutional_reviews AS r
JOIN (
    SELECT opportunity_id, MAX(reviewed_at) AS reviewed_at
    FROM institutional_reviews
    GROUP BY opportunity_id
) AS latest
  ON latest.opportunity_id = r.opportunity_id
 AND latest.reviewed_at = r.reviewed_at;

DROP VIEW IF EXISTS ranked_institutional_reviews;
CREATE VIEW ranked_institutional_reviews AS
SELECT
    ROW_NUMBER() OVER (
        ORDER BY
            CASE institutional_decision
                WHEN 'APPROVE' THEN 1
                WHEN 'REVIEW' THEN 2
                WHEN 'MONITOR' THEN 3
                ELSE 4
            END,
            institutional_confidence_score DESC,
            combined_capital DESC
    ) AS rank,
    *
FROM current_institutional_reviews;
