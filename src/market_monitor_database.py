from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


def connect_database() -> sqlite3.Connection:
    """Open the main Polymarket Intelligence database."""

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


def create_market_metadata_table(
    connection: sqlite3.Connection,
) -> None:
    """
    Store current scheduling, lifecycle and resolution information
    for every tracked market.
    """

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS market_metadata (
            market_id TEXT PRIMARY KEY,

            gamma_market_id TEXT,
            condition_id TEXT,
            event_id TEXT,

            title TEXT NOT NULL,
            event_title TEXT,
            outcome TEXT,

            market_slug TEXT,
            event_slug TEXT,
            sports_slug TEXT,

            category TEXT,
            sport TEXT,
            league TEXT,

            start_time TEXT,
            game_start_time TEXT,
            end_time TEXT,

            lifecycle_status TEXT NOT NULL
                DEFAULT 'UNKNOWN',

            is_pregame INTEGER NOT NULL DEFAULT 0,
            is_live INTEGER NOT NULL DEFAULT 0,
            is_ended INTEGER NOT NULL DEFAULT 0,
            is_closed INTEGER NOT NULL DEFAULT 0,
            is_resolved INTEGER NOT NULL DEFAULT 0,

            score TEXT,
            period TEXT,
            elapsed TEXT,

            winning_outcome TEXT,
            resolution_status TEXT
                NOT NULL DEFAULT 'UNRESOLVED',

            active INTEGER NOT NULL DEFAULT 0,
            accepting_orders INTEGER NOT NULL DEFAULT 0,

            current_price REAL,
            outcome_prices_json TEXT,

            seconds_to_start INTEGER,
            seconds_since_start INTEGER,

            source_updated_at TEXT,
            first_seen_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_metadata_status
        ON market_metadata(lifecycle_status)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_metadata_start_time
        ON market_metadata(game_start_time)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_metadata_sports_slug
        ON market_metadata(sports_slug)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_metadata_live
        ON market_metadata(is_live, is_ended)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_metadata_resolution
        ON market_metadata(
            is_resolved,
            resolution_status
        )
        """
    )


def create_market_status_history_table(
    connection: sqlite3.Connection,
) -> None:
    """Store lifecycle changes for every monitored market."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS market_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            market_id TEXT NOT NULL,

            lifecycle_status TEXT NOT NULL,

            is_pregame INTEGER NOT NULL DEFAULT 0,
            is_live INTEGER NOT NULL DEFAULT 0,
            is_ended INTEGER NOT NULL DEFAULT 0,
            is_closed INTEGER NOT NULL DEFAULT 0,
            is_resolved INTEGER NOT NULL DEFAULT 0,

            start_time TEXT,
            game_start_time TEXT,

            score TEXT,
            period TEXT,
            elapsed TEXT,

            winning_outcome TEXT,
            resolution_status TEXT,

            seconds_to_start INTEGER,
            current_price REAL,

            observed_at TEXT NOT NULL,

            FOREIGN KEY (market_id)
                REFERENCES market_metadata(market_id)
                ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_status_history_market
        ON market_status_history(
            market_id,
            observed_at
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_status_history_status
        ON market_status_history(
            lifecycle_status,
            observed_at
        )
        """
    )


def create_monitor_alerts_table(
    connection: sqlite3.Connection,
) -> None:
    """Store fast-monitor alerts separately from research alerts."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            alert_key TEXT NOT NULL UNIQUE,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,

            market_id TEXT,
            wallet TEXT,

            title TEXT NOT NULL,
            outcome TEXT,

            message TEXT NOT NULL,

            lifecycle_status TEXT,

            seconds_to_start INTEGER,
            wallet_count INTEGER,
            conviction_score REAL,

            capital_change REAL,
            wallet_change INTEGER,
            conviction_change REAL,
            price_change REAL,

            score TEXT,
            period TEXT,
            elapsed TEXT,

            source_time TEXT,
            created_at TEXT NOT NULL,

            acknowledged INTEGER
                NOT NULL DEFAULT 0,

            delivered_dashboard INTEGER
                NOT NULL DEFAULT 0,

            delivered_discord INTEGER
                NOT NULL DEFAULT 0,

            delivered_email INTEGER
                NOT NULL DEFAULT 0,

            FOREIGN KEY (market_id)
                REFERENCES market_metadata(market_id)
                ON DELETE SET NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_monitor_alerts_created
        ON monitor_alerts(created_at DESC)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_monitor_alerts_market
        ON monitor_alerts(market_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_monitor_alerts_unacknowledged
        ON monitor_alerts(
            acknowledged,
            created_at DESC
        )
        """
    )


def create_monitor_runs_table(
    connection: sqlite3.Connection,
) -> None:
    """Store every continuous-monitor execution."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_id TEXT NOT NULL UNIQUE,

            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,

            elapsed_seconds REAL,

            markets_checked INTEGER
                NOT NULL DEFAULT 0,

            markets_updated INTEGER
                NOT NULL DEFAULT 0,

            live_games INTEGER
                NOT NULL DEFAULT 0,

            ended_games INTEGER
                NOT NULL DEFAULT 0,

            resolved_markets INTEGER
                NOT NULL DEFAULT 0,

            wallets_scanned INTEGER
                NOT NULL DEFAULT 0,

            activities_created INTEGER
                NOT NULL DEFAULT 0,

            alerts_created INTEGER
                NOT NULL DEFAULT 0,

            error_type TEXT,
            error_message TEXT,
            log_path TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_monitor_runs_started
        ON monitor_runs(started_at DESC)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_monitor_runs_status
        ON monitor_runs(status)
        """
    )


def create_monitor_settings_table(
    connection: sqlite3.Connection,
) -> None:
    """Store continuous-monitor configuration."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )


def create_tracked_markets_table(
    connection: sqlite3.Connection,
) -> None:
    """Store which markets should receive high-frequency monitoring."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_markets (
            market_id TEXT PRIMARY KEY,

            title TEXT NOT NULL,
            outcome TEXT,

            priority INTEGER NOT NULL DEFAULT 5,

            monitor_wallets INTEGER
                NOT NULL DEFAULT 1,

            monitor_status INTEGER
                NOT NULL DEFAULT 1,

            monitor_price INTEGER
                NOT NULL DEFAULT 1,

            monitor_resolution INTEGER
                NOT NULL DEFAULT 1,

            enabled INTEGER NOT NULL DEFAULT 1,

            source TEXT NOT NULL DEFAULT 'AUTO',

            added_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY (market_id)
                REFERENCES market_metadata(market_id)
                ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_tracked_markets_enabled
        ON tracked_markets(
            enabled,
            priority DESC
        )
        """
    )


def create_monitor_locks_table(
    connection: sqlite3.Connection,
) -> None:
    """
    Prevent two monitor processes from running simultaneously.
    """

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_locks (
            lock_name TEXT PRIMARY KEY,
            process_id INTEGER,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )


def insert_default_settings(
    connection: sqlite3.Connection,
) -> None:
    """Insert safe default monitoring settings."""

    default_settings = [
        (
            "fast_monitor_interval_seconds",
            "180",
            "Seconds between fast monitor cycles.",
        ),
        (
            "full_pipeline_interval_seconds",
            "3600",
            "Seconds between complete platform runs.",
        ),
        (
            "pregame_alert_minutes",
            "120,60,30,15,5",
            "T-minus alert thresholds.",
        ),
        (
            "late_entry_warning_minutes",
            "15",
            "Warn when a signal appears close to game start.",
        ),
        (
            "capital_surge_threshold",
            "25000",
            "Minimum capital increase for a surge alert.",
        ),
        (
            "wallet_surge_threshold",
            "1",
            "Minimum wallet-count increase for an alert.",
        ),
        (
            "conviction_surge_threshold",
            "5",
            "Minimum conviction-score increase for an alert.",
        ),
        (
            "price_chase_threshold",
            "0.10",
            "Price movement considered chase risk.",
        ),
        (
            "dashboard_alerts_enabled",
            "1",
            "Enable dashboard monitor alerts.",
        ),
        (
            "discord_alerts_enabled",
            "0",
            "Enable Discord webhook delivery.",
        ),
        (
            "email_alerts_enabled",
            "0",
            "Enable email alert delivery.",
        ),
        (
            "continuous_monitor_enabled",
            "0",
            "Master continuous-monitor switch.",
        ),
    ]

    connection.executemany(
        """
        INSERT OR IGNORE INTO monitor_settings (
            setting_key,
            setting_value,
            description,
            updated_at
        )
        VALUES (
            ?,
            ?,
            ?,
            CURRENT_TIMESTAMP
        )
        """,
        default_settings,
    )


def create_market_monitor_tables() -> None:
    """Create all market-monitoring tables."""

    connection = connect_database()

    try:
        create_market_metadata_table(connection)
        create_market_status_history_table(connection)
        create_monitor_alerts_table(connection)
        create_monitor_runs_table(connection)
        create_monitor_settings_table(connection)
        create_tracked_markets_table(connection)
        create_monitor_locks_table(connection)

        insert_default_settings(connection)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def table_row_count(
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    """Return the number of rows in one table."""

    row = connection.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM {table_name}
        """
    ).fetchone()

    return int(row["total"]) if row else 0


def inspect_market_monitor_tables() -> None:
    """Print monitoring table row counts."""

    table_names = [
        "market_metadata",
        "market_status_history",
        "tracked_markets",
        "monitor_alerts",
        "monitor_runs",
        "monitor_settings",
        "monitor_locks",
    ]

    connection = connect_database()

    try:
        print()
        print("=" * 92)
        print("POLYMARKET MARKET MONITOR DATABASE")
        print("=" * 92)

        for table_name in table_names:
            total = table_row_count(
                connection,
                table_name,
            )

            print(
                f"{table_name:<32}"
                f"{total:>12} rows"
            )

        print("=" * 92)

    finally:
        connection.close()


def main() -> None:
    """Create and inspect the market-monitor database."""

    print()
    print("=" * 92)
    print("CREATING MARKET MONITOR DATABASE")
    print("=" * 92)
    print(f"Database: {DATABASE_PATH}")

    create_market_monitor_tables()

    print()
    print(
        "Market-monitor tables created successfully."
    )

    inspect_market_monitor_tables()

    print()
    print(
        "Existing scans, positions, wallet intelligence, "
        "consensus, alerts and backtests were not changed."
    )


if __name__ == "__main__":
    main()