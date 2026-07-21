from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


def connect_database() -> sqlite3.Connection:
    """Open the main platform SQLite database."""

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_wallet_profiles_table(
    connection: sqlite3.Connection,
) -> None:
    """
    Store the newest reusable intelligence profile for each wallet.

    One wallet has one current profile. Later engine runs update it.
    """

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_profiles (
            wallet TEXT PRIMARY KEY,

            wallet_score REAL NOT NULL DEFAULT 0,
            wallet_grade TEXT NOT NULL DEFAULT 'UNRATED',

            scan_count INTEGER NOT NULL DEFAULT 0,
            active_position_count INTEGER NOT NULL DEFAULT 0,
            meaningful_position_count INTEGER NOT NULL DEFAULT 0,

            total_current_value REAL NOT NULL DEFAULT 0,
            total_open_pnl REAL NOT NULL DEFAULT 0,
            open_pnl_ratio REAL NOT NULL DEFAULT 0,

            profitable_position_rate REAL NOT NULL DEFAULT 0,
            average_position_value REAL NOT NULL DEFAULT 0,
            median_position_value REAL NOT NULL DEFAULT 0,
            largest_position_value REAL NOT NULL DEFAULT 0,
            concentration_ratio REAL NOT NULL DEFAULT 0,

            average_entry_price REAL NOT NULL DEFAULT 0,
            average_current_price REAL NOT NULL DEFAULT 0,
            average_observed_move REAL NOT NULL DEFAULT 0,

            sports_exposure REAL NOT NULL DEFAULT 0,
            politics_exposure REAL NOT NULL DEFAULT 0,
            crypto_exposure REAL NOT NULL DEFAULT 0,
            macro_exposure REAL NOT NULL DEFAULT 0,
            entertainment_exposure REAL NOT NULL DEFAULT 0,
            other_exposure REAL NOT NULL DEFAULT 0,

            favorite_category TEXT NOT NULL DEFAULT 'Unknown',
            activity_style TEXT NOT NULL DEFAULT 'Unknown',
            risk_profile TEXT NOT NULL DEFAULT 'Unknown',

            leader_score REAL NOT NULL DEFAULT 0,
            activity_score REAL NOT NULL DEFAULT 0,
            specialization_score REAL NOT NULL DEFAULT 0,
            dna_score REAL NOT NULL DEFAULT 0,
            dna_grade TEXT NOT NULL DEFAULT 'UNRATED',

            first_observed_at TEXT,
            latest_observed_at TEXT,
            calculated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_profiles_dna_score
        ON wallet_profiles(dna_score DESC)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_profiles_wallet_score
        ON wallet_profiles(wallet_score DESC)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_profiles_favorite_category
        ON wallet_profiles(favorite_category)
        """
    )


def create_wallet_profile_history_table(
    connection: sqlite3.Connection,
) -> None:
    """Store historical Wallet DNA snapshots."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_profile_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,

            wallet_score REAL NOT NULL DEFAULT 0,
            wallet_grade TEXT NOT NULL DEFAULT 'UNRATED',

            total_current_value REAL NOT NULL DEFAULT 0,
            total_open_pnl REAL NOT NULL DEFAULT 0,
            open_pnl_ratio REAL NOT NULL DEFAULT 0,

            active_position_count INTEGER NOT NULL DEFAULT 0,
            meaningful_position_count INTEGER NOT NULL DEFAULT 0,
            profitable_position_rate REAL NOT NULL DEFAULT 0,
            concentration_ratio REAL NOT NULL DEFAULT 0,

            favorite_category TEXT NOT NULL DEFAULT 'Unknown',
            activity_style TEXT NOT NULL DEFAULT 'Unknown',
            risk_profile TEXT NOT NULL DEFAULT 'Unknown',

            leader_score REAL NOT NULL DEFAULT 0,
            activity_score REAL NOT NULL DEFAULT 0,
            specialization_score REAL NOT NULL DEFAULT 0,
            dna_score REAL NOT NULL DEFAULT 0,
            dna_grade TEXT NOT NULL DEFAULT 'UNRATED',

            calculated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_profile_history_wallet
        ON wallet_profile_history(wallet)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_profile_history_calculated_at
        ON wallet_profile_history(calculated_at)
        """
    )


def create_wallet_activity_table(
    connection: sqlite3.Connection,
) -> None:
    """Store normalized wallet position changes."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            wallet TEXT NOT NULL,
            scan_id INTEGER,
            previous_scan_id INTEGER,

            market_id TEXT,
            title TEXT NOT NULL,
            outcome TEXT,

            activity_type TEXT NOT NULL,

            previous_shares REAL NOT NULL DEFAULT 0,
            current_shares REAL NOT NULL DEFAULT 0,
            share_change REAL NOT NULL DEFAULT 0,

            previous_value REAL NOT NULL DEFAULT 0,
            current_value REAL NOT NULL DEFAULT 0,
            value_change REAL NOT NULL DEFAULT 0,

            previous_price REAL NOT NULL DEFAULT 0,
            current_price REAL NOT NULL DEFAULT 0,
            price_change REAL NOT NULL DEFAULT 0,

            detected_at TEXT NOT NULL,

            FOREIGN KEY (scan_id)
                REFERENCES wallet_scans(id),

            FOREIGN KEY (previous_scan_id)
                REFERENCES wallet_scans(id)
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_activity_wallet
        ON wallet_activity(wallet)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_activity_market
        ON wallet_activity(market_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_activity_type
        ON wallet_activity(activity_type)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_activity_detected_at
        ON wallet_activity(detected_at)
        """
    )

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_wallet_activity_unique_change
        ON wallet_activity(
            wallet,
            scan_id,
            market_id,
            outcome,
            activity_type
        )
        """
    )


def create_wallet_clusters_table(
    connection: sqlite3.Connection,
) -> None:
    """Store detected groups of wallets with similar portfolios."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cluster_key TEXT NOT NULL,
            cluster_name TEXT NOT NULL,

            wallet_count INTEGER NOT NULL DEFAULT 0,
            shared_market_count INTEGER NOT NULL DEFAULT 0,

            average_overlap_score REAL NOT NULL DEFAULT 0,
            average_wallet_score REAL NOT NULL DEFAULT 0,
            combined_current_value REAL NOT NULL DEFAULT 0,

            dominant_category TEXT NOT NULL DEFAULT 'Unknown',
            cluster_grade TEXT NOT NULL DEFAULT 'UNRATED',

            calculated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_clusters_key
        ON wallet_clusters(cluster_key)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_clusters_score
        ON wallet_clusters(average_overlap_score DESC)
        """
    )


def create_wallet_cluster_members_table(
    connection: sqlite3.Connection,
) -> None:
    """Connect wallets to detected clusters."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_cluster_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cluster_id INTEGER NOT NULL,
            wallet TEXT NOT NULL,

            overlap_score REAL NOT NULL DEFAULT 0,
            wallet_score REAL NOT NULL DEFAULT 0,
            cluster_capital_share REAL NOT NULL DEFAULT 0,

            calculated_at TEXT NOT NULL,

            FOREIGN KEY (cluster_id)
                REFERENCES wallet_clusters(id)
                ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_cluster_members_cluster
        ON wallet_cluster_members(cluster_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wallet_cluster_members_wallet
        ON wallet_cluster_members(wallet)
        """
    )


def create_market_leaders_table(
    connection: sqlite3.Connection,
) -> None:
    """Store reusable market-leadership rankings."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS market_leaders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            market_id TEXT NOT NULL,
            title TEXT NOT NULL,
            outcome TEXT NOT NULL,

            wallet TEXT NOT NULL,
            leadership_rank INTEGER NOT NULL,

            leadership_score REAL NOT NULL DEFAULT 0,
            wallet_score REAL NOT NULL DEFAULT 0,
            wallet_grade TEXT NOT NULL DEFAULT 'UNRATED',

            current_value REAL NOT NULL DEFAULT 0,
            current_shares REAL NOT NULL DEFAULT 0,
            capital_share REAL NOT NULL DEFAULT 0,

            recent_value_change REAL NOT NULL DEFAULT 0,
            recent_share_change REAL NOT NULL DEFAULT 0,

            average_entry_price REAL NOT NULL DEFAULT 0,
            current_price REAL NOT NULL DEFAULT 0,
            open_pnl REAL NOT NULL DEFAULT 0,

            first_observed_at TEXT,
            latest_observed_at TEXT,
            calculated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_leaders_market
        ON market_leaders(market_id, outcome)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_leaders_wallet
        ON market_leaders(wallet)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_market_leaders_rank
        ON market_leaders(
            market_id,
            outcome,
            leadership_rank
        )
        """
    )


def create_portfolio_overlap_table(
    connection: sqlite3.Connection,
) -> None:
    """Store pairwise wallet portfolio similarity."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_overlap (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            wallet_a TEXT NOT NULL,
            wallet_b TEXT NOT NULL,

            wallet_a_market_count INTEGER NOT NULL DEFAULT 0,
            wallet_b_market_count INTEGER NOT NULL DEFAULT 0,
            shared_market_count INTEGER NOT NULL DEFAULT 0,

            jaccard_similarity REAL NOT NULL DEFAULT 0,
            weighted_overlap_score REAL NOT NULL DEFAULT 0,

            shared_current_value REAL NOT NULL DEFAULT 0,
            combined_current_value REAL NOT NULL DEFAULT 0,

            same_direction_count INTEGER NOT NULL DEFAULT 0,
            opposing_direction_count INTEGER NOT NULL DEFAULT 0,

            calculated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_portfolio_overlap_wallet_a
        ON portfolio_overlap(wallet_a)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_portfolio_overlap_wallet_b
        ON portfolio_overlap(wallet_b)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_portfolio_overlap_similarity
        ON portfolio_overlap(
            weighted_overlap_score DESC
        )
        """
    )

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_portfolio_overlap_unique_pair
        ON portfolio_overlap(
            wallet_a,
            wallet_b,
            calculated_at
        )
        """
    )


def create_ai_reports_table(
    connection: sqlite3.Connection,
) -> None:
    """Store AI reports as structured database records."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            report_type TEXT NOT NULL,
            report_title TEXT NOT NULL,

            subject_type TEXT,
            subject_id TEXT,

            model_name TEXT,
            report_text TEXT NOT NULL,

            source_snapshot_time TEXT,
            generated_at TEXT NOT NULL,

            file_path TEXT,
            token_usage INTEGER,
            estimated_cost REAL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_ai_reports_type
        ON ai_reports(report_type)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_ai_reports_subject
        ON ai_reports(subject_type, subject_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_ai_reports_generated_at
        ON ai_reports(generated_at)
        """
    )


def create_engine_runs_table(
    connection: sqlite3.Connection,
) -> None:
    """Store structured run records for every platform engine."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS engine_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_group_id TEXT,
            engine_name TEXT NOT NULL,

            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,

            elapsed_seconds REAL,
            return_code INTEGER,

            records_read INTEGER,
            records_created INTEGER,
            records_updated INTEGER,

            error_type TEXT,
            error_message TEXT,
            log_path TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_engine_runs_group
        ON engine_runs(run_group_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_engine_runs_engine
        ON engine_runs(engine_name)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_engine_runs_started_at
        ON engine_runs(started_at)
        """
    )


def create_intelligence_tables() -> None:
    """Create every Intelligence Database table."""

    connection = connect_database()

    try:
        create_wallet_profiles_table(connection)
        create_wallet_profile_history_table(connection)
        create_wallet_activity_table(connection)

        create_wallet_clusters_table(connection)
        create_wallet_cluster_members_table(connection)

        create_market_leaders_table(connection)
        create_portfolio_overlap_table(connection)

        create_ai_reports_table(connection)
        create_engine_runs_table(connection)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def inspect_intelligence_tables() -> None:
    """Print the new table names and current row counts."""

    intelligence_tables = [
        "wallet_profiles",
        "wallet_profile_history",
        "wallet_activity",
        "wallet_clusters",
        "wallet_cluster_members",
        "market_leaders",
        "portfolio_overlap",
        "ai_reports",
        "engine_runs",
    ]

    connection = connect_database()

    try:
        print()
        print("=" * 88)
        print("POLYMARKET INTELLIGENCE DATABASE")
        print("=" * 88)

        for table_name in intelligence_tables:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM {table_name}
                """
            ).fetchone()

            total = int(row["total"]) if row else 0

            print(
                f"{table_name:<32} "
                f"{total:>10} rows"
            )

        print("=" * 88)

    finally:
        connection.close()


def main() -> None:
    """Create and inspect the Intelligence Database."""

    print()
    print("=" * 88)
    print("CREATING POLYMARKET INTELLIGENCE DATABASE")
    print("=" * 88)
    print(f"Database: {DATABASE_PATH}")

    create_intelligence_tables()

    print()
    print("Intelligence tables created successfully.")

    inspect_intelligence_tables()

    print()
    print(
        "Existing wallet scans, positions, consensus history, "
        "ratings, alerts and backtests were not changed."
    )


if __name__ == "__main__":
    main()