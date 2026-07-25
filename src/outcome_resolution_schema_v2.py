from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

TABLE_COLUMNS: dict[str, dict[str, str]] = {
    "market_resolutions": {
        "market_id": "TEXT NOT NULL DEFAULT ''",
        "outcome": "TEXT NOT NULL DEFAULT ''",
        "final_result": "TEXT NOT NULL DEFAULT 'UNRESOLVED'",
        "resolved_value": "REAL",
        "resolution_status": "TEXT NOT NULL DEFAULT 'PENDING'",
        "resolution_source": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
        "resolved_at": "TEXT",
        "notes": "TEXT",
        "resolution_checksum": "TEXT NOT NULL DEFAULT ''",
        "engine_version": "TEXT NOT NULL DEFAULT '2.0.0'",
        "created_at": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    },
    "resolved_signal_results": {
        "market_id": "TEXT NOT NULL DEFAULT ''",
        "title": "TEXT",
        "outcome": "TEXT NOT NULL DEFAULT ''",
        "category": "TEXT",
        "heat_score": "REAL NOT NULL DEFAULT 0",
        "signal_grade": "TEXT",
        "signal_status": "TEXT",
        "combined_capital": "REAL NOT NULL DEFAULT 0",
        "wallet_count": "INTEGER NOT NULL DEFAULT 0",
        "elite_wallet_count": "INTEGER NOT NULL DEFAULT 0",
        "final_result": "TEXT NOT NULL DEFAULT 'UNRESOLVED'",
        "resolved_value": "REAL",
        "evaluation": "TEXT NOT NULL DEFAULT 'PENDING'",
        "hit_value": "REAL",
        "resolution_source": "TEXT",
        "signal_observed_at": "TEXT",
        "resolved_at": "TEXT",
        "engine_version": "TEXT NOT NULL DEFAULT '2.0.0'",
        "created_at": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    },
    "daily_intelligence_reports": {
        "report_date": "TEXT NOT NULL DEFAULT ''",
        "report_type": "TEXT NOT NULL DEFAULT 'DAILY'",
        "report_checksum": "TEXT NOT NULL DEFAULT ''",
        "summary_json": "TEXT NOT NULL DEFAULT '{}'",
        "report_markdown": "TEXT NOT NULL DEFAULT ''",
        "report_path": "TEXT",
        "engine_version": "TEXT NOT NULL DEFAULT '2.0.0'",
        "generated_at": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    },
}


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def object_exists(
    connection: sqlite3.Connection,
    object_type: str,
    name: str,
) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type=? AND name=?",
        (object_type, name),
    ).fetchone() is not None


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not object_exists(connection, "table", table_name):
        return set()
    return {
        str(row[1])
        for row in connection.execute(
            f"PRAGMA table_info({quote(table_name)})"
        ).fetchall()
    }


def ensure_base_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS market_resolutions (
            market_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            final_result TEXT NOT NULL,
            resolved_value REAL,
            resolution_status TEXT NOT NULL,
            resolution_source TEXT NOT NULL,
            resolved_at TEXT,
            notes TEXT,
            resolution_checksum TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (market_id, outcome)
        )
        """
    )
    connection.execute(
        """
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
            resolved_at TEXT,
            engine_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (market_id, outcome)
        )
        """
    )
    connection.execute(
        """
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
        )
        """
    )


def repair_missing_columns(connection: sqlite3.Connection) -> list[str]:
    repairs: list[str] = []
    for table_name, definitions in TABLE_COLUMNS.items():
        existing = table_columns(connection, table_name)
        for column_name, definition in definitions.items():
            if column_name in existing:
                continue
            connection.execute(
                f"ALTER TABLE {quote(table_name)} "
                f"ADD COLUMN {quote(column_name)} {definition}"
            )
            repairs.append(f"{table_name}.{column_name}")
    return repairs


def ensure_unique_keys(connection: sqlite3.Connection) -> list[str]:
    """Repair legacy tables so column-targeted SQLite UPSERTs are valid.

    Older repository versions may already contain these tables without their
    intended composite primary keys. SQLite cannot add a primary key with
    ALTER TABLE, so we remove duplicate logical rows deterministically and
    create equivalent UNIQUE indexes.
    """
    repairs: list[str] = []
    unique_keys = {
        "market_resolutions": ("market_id", "outcome"),
        "resolved_signal_results": ("market_id", "outcome"),
        "daily_intelligence_reports": ("report_date", "report_type"),
    }

    for table_name, columns in unique_keys.items():
        if not object_exists(connection, "table", table_name):
            continue
        available = table_columns(connection, table_name)
        if not set(columns).issubset(available):
            continue

        quoted_columns = ", ".join(quote(column) for column in columns)
        # Preserve the newest physical row for each logical key. This makes
        # the migration safe even when a partially-installed legacy module
        # inserted duplicates before the unique constraint existed.
        cursor = connection.execute(
            f"""
            DELETE FROM {quote(table_name)}
            WHERE rowid NOT IN (
                SELECT MAX(rowid)
                FROM {quote(table_name)}
                GROUP BY {quoted_columns}
            )
            """
        )
        if cursor.rowcount and cursor.rowcount > 0:
            repairs.append(
                f"{table_name}.deduplicated_rows={cursor.rowcount}"
            )

        index_name = f"uq_{table_name}_{'_'.join(columns)}"
        existed = object_exists(connection, "index", index_name)
        connection.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {quote(index_name)} "
            f"ON {quote(table_name)} ({quoted_columns})"
        )
        if not existed:
            repairs.append(f"{table_name}.unique_key")

    return repairs


def ensure_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_resolutions_status_time
        ON market_resolutions(resolution_status, resolved_at DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_resolved_signal_results_date
        ON resolved_signal_results(resolved_at DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_resolved_signal_results_grade
        ON resolved_signal_results(signal_grade, evaluation)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_resolved_signal_results_category
        ON resolved_signal_results(category, evaluation)
        """
    )


def ensure_views(connection: sqlite3.Connection) -> None:
    for view in (
        "resolved_signal_performance",
        "daily_signal_performance",
        "weekly_signal_performance",
        "monthly_signal_performance",
        "signal_grade_performance",
        "category_signal_performance",
    ):
        connection.execute(f"DROP VIEW IF EXISTS {quote(view)}")

    connection.executescript(
        """
        CREATE VIEW resolved_signal_performance AS
        SELECT
            market_id, title, outcome, category, heat_score,
            signal_grade, signal_status, combined_capital,
            wallet_count, elite_wallet_count, final_result,
            evaluation, hit_value, resolved_at
        FROM resolved_signal_results;

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
        WHERE resolved_at IS NOT NULL
        GROUP BY SUBSTR(resolved_at, 1, 10);

        CREATE VIEW weekly_signal_performance AS
        SELECT
            STRFTIME('%Y-W%W', resolved_at) AS report_week,
            COUNT(*) AS total_resolved,
            SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) AS hits,
            SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) AS misses,
            AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) AS hit_rate,
            AVG(heat_score) AS average_heat_score,
            SUM(combined_capital) AS combined_capital
        FROM resolved_signal_results
        WHERE resolved_at IS NOT NULL
        GROUP BY STRFTIME('%Y-W%W', resolved_at);

        CREATE VIEW monthly_signal_performance AS
        SELECT
            SUBSTR(resolved_at, 1, 7) AS report_month,
            COUNT(*) AS total_resolved,
            SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) AS hits,
            SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) AS misses,
            AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) AS hit_rate,
            AVG(heat_score) AS average_heat_score,
            SUM(combined_capital) AS combined_capital
        FROM resolved_signal_results
        WHERE resolved_at IS NOT NULL
        GROUP BY SUBSTR(resolved_at, 1, 7);

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
        """
    )


def ensure_schema(
    connection: sqlite3.Connection,
) -> list[str]:
    ensure_base_tables(connection)
    repairs = repair_missing_columns(connection)
    repairs.extend(ensure_unique_keys(connection))
    ensure_indexes(connection)
    ensure_views(connection)
    return repairs
