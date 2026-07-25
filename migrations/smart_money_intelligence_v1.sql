CREATE TABLE IF NOT EXISTS smart_money_market_signals (
    market_id TEXT NOT NULL,
    title TEXT,
    outcome TEXT NOT NULL,
    category TEXT,
    wallet_count INTEGER NOT NULL DEFAULT 0,
    elite_wallet_count INTEGER NOT NULL DEFAULT 0,
    consensus_wallet_count INTEGER NOT NULL DEFAULT 0,
    combined_capital REAL NOT NULL DEFAULT 0,
    weighted_capital REAL NOT NULL DEFAULT 0,
    agreement_ratio REAL NOT NULL DEFAULT 0,
    disagreement_ratio REAL NOT NULL DEFAULT 0,
    average_wallet_score REAL NOT NULL DEFAULT 0,
    leader_wallet TEXT,
    leader_score REAL NOT NULL DEFAULT 0,
    heat_score REAL NOT NULL DEFAULT 0,
    signal_grade TEXT,
    signal_status TEXT,
    rationale_json TEXT,
    evidence_json TEXT,
    signal_checksum TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market_id, outcome)
);

CREATE INDEX IF NOT EXISTS idx_smart_money_signal_heat
ON smart_money_market_signals(heat_score DESC);

CREATE INDEX IF NOT EXISTS idx_smart_money_signal_status
ON smart_money_market_signals(signal_status, heat_score DESC);

CREATE INDEX IF NOT EXISTS idx_smart_money_signal_category
ON smart_money_market_signals(category, heat_score DESC);

CREATE TABLE IF NOT EXISTS smart_money_signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    title TEXT,
    outcome TEXT NOT NULL,
    category TEXT,
    wallet_count INTEGER NOT NULL DEFAULT 0,
    elite_wallet_count INTEGER NOT NULL DEFAULT 0,
    combined_capital REAL NOT NULL DEFAULT 0,
    weighted_capital REAL NOT NULL DEFAULT 0,
    agreement_ratio REAL NOT NULL DEFAULT 0,
    disagreement_ratio REAL NOT NULL DEFAULT 0,
    average_wallet_score REAL NOT NULL DEFAULT 0,
    leader_wallet TEXT,
    leader_score REAL NOT NULL DEFAULT 0,
    heat_score REAL NOT NULL DEFAULT 0,
    signal_grade TEXT,
    signal_status TEXT,
    rationale_json TEXT,
    evidence_json TEXT,
    signal_checksum TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    UNIQUE(market_id, outcome, signal_checksum)
);

CREATE INDEX IF NOT EXISTS idx_smart_money_history_market_time
ON smart_money_signal_history(market_id, outcome, observed_at DESC);

DROP VIEW IF EXISTS ranked_smart_money_signals;
CREATE VIEW ranked_smart_money_signals AS
SELECT
    market_id,
    title,
    outcome,
    category,
    wallet_count,
    elite_wallet_count,
    consensus_wallet_count,
    combined_capital,
    weighted_capital,
    agreement_ratio,
    disagreement_ratio,
    average_wallet_score,
    leader_wallet,
    leader_score,
    heat_score,
    signal_grade,
    signal_status,
    rationale_json,
    evidence_json,
    first_observed_at,
    last_observed_at,
    ROW_NUMBER() OVER (
        ORDER BY heat_score DESC,
                 elite_wallet_count DESC,
                 weighted_capital DESC,
                 wallet_count DESC,
                 market_id,
                 outcome
    ) AS smart_money_rank
FROM smart_money_market_signals;

DROP VIEW IF EXISTS smart_money_disagreement_board;
CREATE VIEW smart_money_disagreement_board AS
SELECT
    market_id,
    title,
    outcome,
    category,
    wallet_count,
    elite_wallet_count,
    combined_capital,
    disagreement_ratio,
    heat_score,
    signal_grade,
    signal_status,
    leader_wallet,
    last_observed_at
FROM smart_money_market_signals
WHERE signal_status = 'ELITE_DISAGREEMENT'
ORDER BY disagreement_ratio DESC, heat_score DESC;

DROP VIEW IF EXISTS smart_money_signal_trends;
CREATE VIEW smart_money_signal_trends AS
WITH ordered AS (
    SELECT
        market_id,
        outcome,
        observed_at,
        heat_score,
        combined_capital,
        wallet_count,
        LAG(heat_score) OVER (
            PARTITION BY market_id, outcome ORDER BY observed_at
        ) AS previous_heat_score,
        LAG(combined_capital) OVER (
            PARTITION BY market_id, outcome ORDER BY observed_at
        ) AS previous_capital,
        LAG(wallet_count) OVER (
            PARTITION BY market_id, outcome ORDER BY observed_at
        ) AS previous_wallet_count
    FROM smart_money_signal_history
)
SELECT
    market_id,
    outcome,
    observed_at,
    heat_score,
    previous_heat_score,
    heat_score - previous_heat_score AS heat_score_change,
    combined_capital,
    previous_capital,
    combined_capital - previous_capital AS capital_change,
    wallet_count,
    previous_wallet_count,
    wallet_count - previous_wallet_count AS wallet_count_change,
    CASE
        WHEN previous_heat_score IS NULL THEN 'NEW'
        WHEN heat_score - previous_heat_score >= 5 THEN 'ACCELERATING'
        WHEN heat_score - previous_heat_score <= -5 THEN 'WEAKENING'
        ELSE 'STABLE'
    END AS trend_status
FROM ordered;
