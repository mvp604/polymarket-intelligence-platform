CREATE TABLE IF NOT EXISTS market_resolutions (
    market_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    final_result TEXT NOT NULL,
    resolved_value REAL,
    resolution_status TEXT NOT NULL,
    resolution_source TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    notes TEXT,
    resolution_checksum TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market_id, outcome)
);

CREATE INDEX IF NOT EXISTS idx_market_resolutions_status_time
ON market_resolutions(resolution_status, resolved_at DESC);

CREATE TABLE IF NOT EXISTS resolved_signal_results (
    market_id TEXT NOT NULL,
    title TEXT,
    outcome TEXT NOT NULL,
    category TEXT,
    heat_score REAL NOT NULL DEFAULT 0,
    signal_grade TEXT,
    signal_status TEXT,
    combined_capital REAL NOT NULL DEFAULT 0,
    wallet_count INTEGER NOT NULL DEFAULT 0,
    elite_wallet_count INTEGER NOT NULL DEFAULT 0,
    final_result TEXT NOT NULL,
    resolved_value REAL,
    evaluation TEXT NOT NULL,
    hit_value REAL,
    resolution_source TEXT,
    signal_observed_at TEXT,
    resolved_at TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market_id, outcome)
);

CREATE INDEX IF NOT EXISTS idx_resolved_signal_results_date
ON resolved_signal_results(resolved_at DESC);

CREATE INDEX IF NOT EXISTS idx_resolved_signal_results_grade
ON resolved_signal_results(signal_grade, evaluation);

CREATE INDEX IF NOT EXISTS idx_resolved_signal_results_category
ON resolved_signal_results(category, evaluation);

CREATE TABLE IF NOT EXISTS daily_intelligence_reports (
    report_date TEXT NOT NULL,
    report_type TEXT NOT NULL,
    report_checksum TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    report_markdown TEXT NOT NULL,
    report_path TEXT,
    engine_version TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (report_date, report_type)
);

DROP VIEW IF EXISTS resolved_signal_performance;
CREATE VIEW resolved_signal_performance AS
SELECT
    market_id,
    title,
    outcome,
    category,
    heat_score,
    signal_grade,
    signal_status,
    combined_capital,
    wallet_count,
    elite_wallet_count,
    final_result,
    evaluation,
    hit_value,
    resolved_at
FROM resolved_signal_results;

DROP VIEW IF EXISTS daily_signal_performance;
CREATE VIEW daily_signal_performance AS
SELECT
    SUBSTR(resolved_at, 1, 10) AS report_date,
    COUNT(*) AS total_resolved,
    SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) AS hits,
    SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) AS misses,
    SUM(CASE WHEN evaluation='VOID' THEN 1 ELSE 0 END) AS voids,
    SUM(CASE WHEN evaluation='NO_ACTION' THEN 1 ELSE 0 END) AS no_action,
    AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) AS hit_rate,
    AVG(heat_score) AS average_heat_score,
    MAX(heat_score) AS maximum_heat_score,
    SUM(combined_capital) AS combined_capital
FROM resolved_signal_results
GROUP BY SUBSTR(resolved_at, 1, 10);

DROP VIEW IF EXISTS signal_grade_performance;
CREATE VIEW signal_grade_performance AS
SELECT
    signal_grade,
    COUNT(*) AS total_resolved,
    SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) AS hits,
    SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) AS misses,
    AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) AS hit_rate,
    AVG(heat_score) AS average_heat_score,
    SUM(combined_capital) AS combined_capital
FROM resolved_signal_results
GROUP BY signal_grade;

DROP VIEW IF EXISTS category_signal_performance;
CREATE VIEW category_signal_performance AS
SELECT
    category,
    COUNT(*) AS total_resolved,
    SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) AS hits,
    SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) AS misses,
    AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) AS hit_rate,
    AVG(heat_score) AS average_heat_score,
    SUM(combined_capital) AS combined_capital
FROM resolved_signal_results
GROUP BY category;
