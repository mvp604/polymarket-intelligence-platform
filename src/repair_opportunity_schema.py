from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

EXPECTED_COLUMNS: dict[str, str] = {
    "market_id": "TEXT",
    "question": "TEXT",
    "category": "TEXT",
    "selected_outcome": "TEXT",
    "current_price": "REAL",
    "opportunity_score": "REAL NOT NULL DEFAULT 0",
    "confidence_score": "REAL NOT NULL DEFAULT 0",
    "wallet_component": "REAL NOT NULL DEFAULT 0",
    "consensus_component": "REAL NOT NULL DEFAULT 0",
    "health_component": "REAL NOT NULL DEFAULT 0",
    "liquidity_component": "REAL NOT NULL DEFAULT 0",
    "momentum_component": "REAL NOT NULL DEFAULT 0",
    "risk_penalty": "REAL NOT NULL DEFAULT 0",
    "data_quality_score": "REAL NOT NULL DEFAULT 0",
    "recommendation": "TEXT NOT NULL DEFAULT 'PASS'",
    "signal_grade": "TEXT NOT NULL DEFAULT 'PASS'",
    "risk_level": "TEXT NOT NULL DEFAULT 'HIGH'",
    "explanation_json": "TEXT NOT NULL DEFAULT '{}'",
    "source_table": "TEXT NOT NULL DEFAULT ''",
    "source_updated_at": "TEXT",
    "calculated_at": "TEXT NOT NULL DEFAULT ''",
}


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name=?
            """,
            (table,),
        ).fetchone()
        is not None
    )


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    }


def ensure_runs_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
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
        )
        """
    )


def ensure_scores_table(connection: sqlite3.Connection) -> list[str]:
    changes: list[str] = []

    if not table_exists(connection, "opportunity_scores"):
        connection.execute(
            """
            CREATE TABLE opportunity_scores (
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
            )
            """
        )
        changes.append("Created opportunity_scores")
        return changes

    existing = columns(connection, "opportunity_scores")
    for column, definition in EXPECTED_COLUMNS.items():
        if column in existing:
            continue

        if column == "market_id":
            raise RuntimeError(
                "Existing opportunity_scores table has no market_id column. "
                "Automatic repair cannot safely infer its primary key."
            )

        connection.execute(
            f'ALTER TABLE opportunity_scores ADD COLUMN "{column}" {definition}'
        )
        changes.append(f"Added opportunity_scores.{column}")

    return changes


def ensure_history_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
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
        )
        """
    )


def rebuild_indexes_and_view(connection: sqlite3.Connection) -> None:
    connection.execute("DROP VIEW IF EXISTS opportunity_daily_board")

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunity_score_rank
        ON opportunity_scores(opportunity_score DESC, confidence_score DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunity_recommendation
        ON opportunity_scores(recommendation, signal_grade, risk_level)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunity_history_market
        ON opportunity_score_history(market_id, calculated_at DESC)
        """
    )

    connection.execute(
        """
        CREATE VIEW opportunity_daily_board AS
        SELECT
            market_id,
            question,
            category,
            selected_outcome,
            current_price,
            opportunity_score,
            confidence_score,
            recommendation,
            signal_grade,
            risk_level,
            explanation_json,
            calculated_at
        FROM opportunity_scores
        WHERE recommendation IN ('ACTIONABLE', 'WATCHLIST')
        ORDER BY
            CASE recommendation WHEN 'ACTIONABLE' THEN 0 ELSE 1 END,
            opportunity_score DESC,
            confidence_score DESC,
            risk_level ASC
        """
    )


def validate(connection: sqlite3.Connection) -> None:
    actual = columns(connection, "opportunity_scores")
    missing = sorted(set(EXPECTED_COLUMNS) - actual)
    if missing:
        raise RuntimeError(f"Schema validation failed; missing columns: {missing}")

    connection.execute(
        """
        SELECT
            market_id,
            opportunity_score,
            confidence_score,
            recommendation
        FROM opportunity_daily_board
        LIMIT 1
        """
    ).fetchall()


def main() -> int:
    print("=" * 108)
    print("OPPORTUNITY INTELLIGENCE SCHEMA REPAIR")
    print("=" * 108)
    print(f"Database: {DATABASE_PATH}")

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")

        ensure_runs_table(connection)
        changes = ensure_scores_table(connection)
        ensure_history_table(connection)
        rebuild_indexes_and_view(connection)
        validate(connection)
        connection.commit()

        print()
        print("REPAIR SUMMARY")
        print("-" * 108)
        if changes:
            for change in changes:
                print(f"SUCCESS: {change}")
        else:
            print("No missing opportunity_scores columns were found.")
        print("SUCCESS: Rebuilt indexes")
        print("SUCCESS: Rebuilt opportunity_daily_board")
        print("SUCCESS: Schema validation passed")
        print("=" * 108)
        print("OPPORTUNITY SCHEMA REPAIR COMPLETE")
        print("=" * 108)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())