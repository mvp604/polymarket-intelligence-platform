from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from data_access import DATABASE_PATH
except ImportError:
    from src.data_access import DATABASE_PATH


RUNS_TABLE = "wallet_discovery_runs"
SNAPSHOTS_TABLE = "wallet_leaderboard_snapshots"


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table' AND name=?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[str]:
    if not table_exists(connection, table_name):
        return []

    rows = connection.execute(
        f"PRAGMA table_info({quote_identifier(table_name)})"
    ).fetchall()
    return [str(row[1]) for row in rows]


def foreign_keys(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[sqlite3.Row]:
    if not table_exists(connection, table_name):
        return []

    return connection.execute(
        f"PRAGMA foreign_key_list({quote_identifier(table_name)})"
    ).fetchall()


def print_schema(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    print(f"\n{table_name}")
    if not table_exists(connection, table_name):
        print("  MISSING")
        return

    for row in connection.execute(
        f"PRAGMA table_info({quote_identifier(table_name)})"
    ):
        print(" ", tuple(row))


def create_current_runs_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(RUNS_TABLE)} (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            mode TEXT NOT NULL,
            categories_scanned INTEGER NOT NULL DEFAULT 0,
            periods_scanned INTEGER NOT NULL DEFAULT 0,
            API_queries INTEGER NOT NULL DEFAULT 0,
            leaderboard_rows INTEGER NOT NULL DEFAULT 0,
            unique_wallets INTEGER NOT NULL DEFAULT 0,
            wallet_rows_upserted INTEGER NOT NULL DEFAULT 0,
            snapshot_rows_inserted INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            error_message TEXT
        )
        """
    )


def create_current_snapshots_table(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    connection.execute(
        f"""
        CREATE TABLE {quote_identifier(table_name)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            wallet TEXT NOT NULL,
            username TEXT,
            category TEXT NOT NULL,
            time_period TEXT NOT NULL,
            order_by TEXT NOT NULL,
            leaderboard_rank INTEGER,
            pnl REAL NOT NULL DEFAULT 0,
            volume REAL NOT NULL DEFAULT 0,
            roi_proxy REAL NOT NULL DEFAULT 0,
            verified_badge INTEGER NOT NULL DEFAULT 0,
            observed_at TEXT NOT NULL,
            FOREIGN KEY(run_id)
                REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                ON DELETE CASCADE
        )
        """
    )


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    database_path = Path(DATABASE_PATH)
    print("=" * 100)
    print("WALLET DISCOVERY SCHEMA MIGRATION")
    print("=" * 100)
    print(f"Database: {database_path}")

    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    legacy_runs_table = f"{RUNS_TABLE}_legacy_{timestamp}"
    snapshots_backup_table = f"{SNAPSHOTS_TABLE}_backup_{timestamp}"
    snapshots_new_table = f"{SNAPSHOTS_TABLE}_new_{timestamp}"

    try:
        existing_runs_columns = table_columns(connection, RUNS_TABLE)

        expected_runs_columns = {
            "run_id",
            "started_at",
            "finished_at",
            "mode",
            "categories_scanned",
            "periods_scanned",
            "API_queries",
            "leaderboard_rows",
            "unique_wallets",
            "wallet_rows_upserted",
            "snapshot_rows_inserted",
            "status",
            "error_message",
        }

        if set(existing_runs_columns) == expected_runs_columns:
            print("\nNo migration required.")
            print("wallet_discovery_runs already uses the current schema.")
            print_schema(connection, RUNS_TABLE)
            return

        print("\nLegacy schema detected.")
        print(f"Current columns: {existing_runs_columns}")

        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")

        if table_exists(connection, RUNS_TABLE):
            connection.execute(
                f"""
                ALTER TABLE {quote_identifier(RUNS_TABLE)}
                RENAME TO {quote_identifier(legacy_runs_table)}
                """
            )
            print(f"Preserved old run table as: {legacy_runs_table}")

        create_current_runs_table(connection)
        print("Created current wallet_discovery_runs schema.")

        snapshot_rows = 0
        snapshot_run_ids: list[str] = []

        if table_exists(connection, SNAPSHOTS_TABLE):
            snapshot_rows = int(
                connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {quote_identifier(SNAPSHOTS_TABLE)}
                    """
                ).fetchone()[0]
            )

            snapshot_run_ids = [
                str(row[0])
                for row in connection.execute(
                    f"""
                    SELECT DISTINCT run_id
                    FROM {quote_identifier(SNAPSHOTS_TABLE)}
                    WHERE run_id IS NOT NULL
                      AND TRIM(run_id) <> ''
                    """
                ).fetchall()
            ]

            connection.execute(
                f"""
                ALTER TABLE {quote_identifier(SNAPSHOTS_TABLE)}
                RENAME TO {quote_identifier(snapshots_backup_table)}
                """
            )

            create_current_snapshots_table(
                connection,
                snapshots_new_table,
            )

            now = utc_now_iso()
            for run_id in snapshot_run_ids:
                connection.execute(
                    f"""
                    INSERT OR IGNORE INTO {quote_identifier(RUNS_TABLE)} (
                        run_id,
                        started_at,
                        finished_at,
                        mode,
                        categories_scanned,
                        periods_scanned,
                        API_queries,
                        leaderboard_rows,
                        unique_wallets,
                        wallet_rows_upserted,
                        snapshot_rows_inserted,
                        status,
                        error_message
                    )
                    VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, ?, ?)
                    """,
                    (
                        run_id,
                        now,
                        now,
                        "LEGACY_IMPORT",
                        "MIGRATED",
                        "Placeholder run created while preserving legacy snapshots.",
                    ),
                )

            old_snapshot_columns = set(
                table_columns(connection, snapshots_backup_table)
            )
            required_snapshot_columns = {
                "id",
                "run_id",
                "wallet",
                "username",
                "category",
                "time_period",
                "order_by",
                "leaderboard_rank",
                "pnl",
                "volume",
                "roi_proxy",
                "verified_badge",
                "observed_at",
            }

            if required_snapshot_columns.issubset(old_snapshot_columns):
                connection.execute(
                    f"""
                    INSERT INTO {quote_identifier(snapshots_new_table)} (
                        id,
                        run_id,
                        wallet,
                        username,
                        category,
                        time_period,
                        order_by,
                        leaderboard_rank,
                        pnl,
                        volume,
                        roi_proxy,
                        verified_badge,
                        observed_at
                    )
                    SELECT
                        id,
                        run_id,
                        wallet,
                        username,
                        category,
                        time_period,
                        order_by,
                        leaderboard_rank,
                        pnl,
                        volume,
                        roi_proxy,
                        verified_badge,
                        observed_at
                    FROM {quote_identifier(snapshots_backup_table)}
                    """
                )
            elif snapshot_rows:
                raise RuntimeError(
                    "The existing snapshot table contains rows but does not "
                    "have the expected columns. Migration stopped safely."
                )

            connection.execute(
                f"""
                ALTER TABLE {quote_identifier(snapshots_new_table)}
                RENAME TO {quote_identifier(SNAPSHOTS_TABLE)}
                """
            )
            print(
                f"Rebuilt {SNAPSHOTS_TABLE} with a valid run_id foreign key."
            )
            print(
                f"Preserved the previous snapshot table as: "
                f"{snapshots_backup_table}"
            )
            print(f"Snapshot rows preserved: {snapshot_rows}")
        else:
            create_current_snapshots_table(
                connection,
                SNAPSHOTS_TABLE,
            )
            print(f"Created missing {SNAPSHOTS_TABLE} table.")

        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_wallet_time
            ON {quote_identifier(SNAPSHOTS_TABLE)}(
                wallet,
                observed_at DESC
            )
            """
        )
        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_category_period
            ON {quote_identifier(SNAPSHOTS_TABLE)}(
                category,
                time_period,
                leaderboard_rank
            )
            """
        )

        connection.commit()
        connection.execute("PRAGMA foreign_keys = ON")

        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print("\nMIGRATION RESULT")
        print("-" * 100)
        print("Status: SUCCESS")
        print(f"Legacy run table: {legacy_runs_table}")
        print(f"Snapshot rows preserved: {snapshot_rows}")
        print(f"Placeholder legacy runs created: {len(snapshot_run_ids)}")
        print(f"Foreign-key violations: {len(violations)}")

        print_schema(connection, RUNS_TABLE)
        print_schema(connection, SNAPSHOTS_TABLE)

        print("\nNEXT COMMAND")
        print("-" * 100)
        print(
            "python .\\src\\elite_wallet_discovery_engine.py "
            "--categories SPORTS --periods WEEK,MONTH,ALL --limit 20"
        )
        print("=" * 100)

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()