CREATE TABLE IF NOT EXISTS elite_wallet_profile_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet TEXT NOT NULL,
    eligibility_status TEXT,
    elite_tier TEXT,
    overall_grade TEXT,
    trust_score REAL,
    skill_score REAL,
    repeatability_score REAL,
    profitability_quality_score REAL,
    calibration_score REAL,
    consistency_score REAL,
    risk_control_score REAL,
    sample_strength_score REAL,
    confidence_adjusted_score REAL,
    resolved_positions INTEGER,
    wins INTEGER,
    losses INTEGER,
    raw_win_rate REAL,
    raw_roi REAL,
    profit_factor REAL,
    data_confidence REAL,
    influence_weight REAL,
    profile_checksum TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    UNIQUE(wallet, profile_checksum)
);

CREATE INDEX IF NOT EXISTS idx_elite_wallet_profile_history_wallet_time
ON elite_wallet_profile_history(wallet, calculated_at DESC);

CREATE INDEX IF NOT EXISTS idx_elite_wallet_profile_history_score
ON elite_wallet_profile_history(confidence_adjusted_score DESC);

CREATE TABLE IF NOT EXISTS elite_wallet_category_profiles (
    wallet TEXT NOT NULL,
    category TEXT NOT NULL,
    resolved_positions INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    bayesian_win_rate REAL NOT NULL DEFAULT 0,
    raw_roi REAL NOT NULL DEFAULT 0,
    profit_factor REAL NOT NULL DEFAULT 0,
    sample_strength_score REAL NOT NULL DEFAULT 0,
    confidence_adjusted_score REAL NOT NULL DEFAULT 0,
    category_grade TEXT,
    consensus_eligible INTEGER NOT NULL DEFAULT 0,
    elite_eligible INTEGER NOT NULL DEFAULT 0,
    engine_version TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(wallet, category)
);

CREATE INDEX IF NOT EXISTS idx_elite_wallet_category_rank
ON elite_wallet_category_profiles(category, confidence_adjusted_score DESC);

DROP VIEW IF EXISTS ranked_elite_wallets;
CREATE VIEW ranked_elite_wallets AS
SELECT
    wallet,
    eligibility_status,
    eligibility_reason,
    elite_tier,
    overall_grade,
    trust_score,
    skill_score,
    repeatability_score,
    profitability_quality_score,
    calibration_score,
    consistency_score,
    risk_control_score,
    sample_strength_score,
    confidence_adjusted_score,
    resolved_positions,
    wins,
    losses,
    raw_win_rate,
    bayesian_win_rate,
    raw_roi,
    profit_factor,
    data_confidence,
    influence_weight,
    consensus_eligible,
    elite_eligible,
    calculated_at,
    ROW_NUMBER() OVER (
        ORDER BY confidence_adjusted_score DESC,
                 sample_strength_score DESC,
                 resolved_positions DESC,
                 wallet
    ) AS overall_rank
FROM elite_wallet_profiles;

DROP VIEW IF EXISTS ranked_elite_wallet_categories;
CREATE VIEW ranked_elite_wallet_categories AS
SELECT
    wallet,
    category,
    resolved_positions,
    wins,
    losses,
    bayesian_win_rate,
    raw_roi,
    profit_factor,
    sample_strength_score,
    confidence_adjusted_score,
    category_grade,
    consensus_eligible,
    elite_eligible,
    calculated_at,
    ROW_NUMBER() OVER (
        PARTITION BY category
        ORDER BY confidence_adjusted_score DESC,
                 sample_strength_score DESC,
                 resolved_positions DESC,
                 wallet
    ) AS category_rank
FROM elite_wallet_category_profiles;

DROP VIEW IF EXISTS elite_wallet_trends;
CREATE VIEW elite_wallet_trends AS
WITH ordered AS (
    SELECT
        wallet,
        calculated_at,
        confidence_adjusted_score,
        trust_score,
        skill_score,
        sample_strength_score,
        LAG(confidence_adjusted_score) OVER (
            PARTITION BY wallet ORDER BY calculated_at
        ) AS previous_score
    FROM elite_wallet_profile_history
)
SELECT
    wallet,
    calculated_at,
    confidence_adjusted_score,
    previous_score,
    confidence_adjusted_score - previous_score AS score_change,
    CASE
        WHEN previous_score IS NULL THEN 'NEW'
        WHEN confidence_adjusted_score - previous_score >= 3 THEN 'IMPROVING'
        WHEN confidence_adjusted_score - previous_score <= -3 THEN 'DECLINING'
        ELSE 'STABLE'
    END AS trend_status,
    trust_score,
    skill_score,
    sample_strength_score
FROM ordered;
