from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("database/polymarket.db")


def connect_database() -> sqlite3.Connection:
    """Open a connection to the local SQLite database."""

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    # Make SQLite enforce relationships between tables.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_tables() -> None:
    """Create all database tables if they do not already exist."""

    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            scanned_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            wallet TEXT NOT NULL,
            market_id TEXT,
            title TEXT NOT NULL,
            outcome TEXT,
            shares REAL DEFAULT 0,
            average_price REAL DEFAULT 0,
            current_price REAL DEFAULT 0,
            current_value REAL DEFAULT 0,
            cash_pnl REAL DEFAULT 0,
            percent_pnl REAL DEFAULT 0,
            FOREIGN KEY (scan_id) REFERENCES wallet_scans(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS consensus_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT NOT NULL,
            title TEXT NOT NULL,
            outcome TEXT NOT NULL,
            wallet_count INTEGER NOT NULL,
            combined_shares REAL NOT NULL,
            combined_value REAL NOT NULL,
            combined_pnl REAL NOT NULL,
            conviction_score REAL NOT NULL,
            conviction_grade TEXT NOT NULL,
            average_entry_price REAL,
            average_current_price REAL,
            observed_price_move REAL,
            scanned_at TEXT NOT NULL
        )
        """
    )

    # Helpful indexes for faster history and wallet queries.
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wallet_scans_wallet
        ON wallet_scans(wallet)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_positions_scan_id
        ON positions(scan_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_positions_market_outcome
        ON positions(market_id, outcome)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_consensus_history_market_outcome
        ON consensus_history(market_id, outcome)
        """
    )

    connection.commit()
    connection.close()


def safe_number(value: Any) -> float:
    """Convert an API or dictionary value to a float without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def save_consensus_history(results: list[dict[str, Any]]) -> int:
    """
    Save one historical snapshot for every scored consensus result.

    All results from the same conviction-engine run receive the same
    UTC timestamp.

    Returns:
        Number of consensus rows saved.
    """

    if not results:
        return 0

    create_tables()

    connection = connect_database()
    cursor = connection.cursor()

    scanned_at = datetime.now(timezone.utc).isoformat()

    try:
        for result in results:
            market_id = str(result.get("market_id") or "").strip()
            title = str(
                result.get("title") or "Unknown market"
            ).strip()
            outcome = str(
                result.get("outcome") or "Unknown"
            ).strip()

            if not market_id:
                # Do not store unusable consensus records.
                continue

            cursor.execute(
                """
                INSERT INTO consensus_history (
                    market_id,
                    title,
                    outcome,
                    wallet_count,
                    combined_shares,
                    combined_value,
                    combined_pnl,
                    conviction_score,
                    conviction_grade,
                    average_entry_price,
                    average_current_price,
                    observed_price_move,
                    scanned_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    market_id,
                    title,
                    outcome,
                    int(result.get("wallet_count") or 0),
                    safe_number(result.get("combined_shares")),
                    safe_number(result.get("combined_value")),
                    safe_number(result.get("combined_pnl")),
                    safe_number(result.get("conviction_score")),
                    str(result.get("grade") or "UNRATED"),
                    safe_number(result.get("average_entry_price")),
                    safe_number(result.get("average_current_price")),
                    safe_number(result.get("price_move")),
                    scanned_at,
                ),
            )

        connection.commit()

        return cursor.rowcount if cursor.rowcount > 0 else len(results)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_wallet_scan(
    wallet: str,
    positions: list[dict[str, Any]],
) -> int:
    """
    Save one wallet scan and every position connected to that scan.

    Returns:
        Newly created scan ID.
    """

    create_tables()

    connection = connect_database()
    cursor = connection.cursor()

    scanned_at = datetime.now(timezone.utc).isoformat()

    try:
        cursor.execute(
            """
            INSERT INTO wallet_scans (
                wallet,
                scanned_at
            )
            VALUES (?, ?)
            """,
            (
                wallet,
                scanned_at,
            ),
        )

        scan_id = cursor.lastrowid

        if scan_id is None:
            raise RuntimeError(
                "SQLite did not return a wallet scan ID."
            )

        for position in positions:
            market_id = (
                position.get("conditionId")
                or position.get("marketId")
                or position.get("slug")
                or position.get("asset")
                or ""
            )

            title = (
                position.get("title")
                or "Unknown market"
            )

            outcome = (
                position.get("outcome")
                or "Unknown"
            )

            cursor.execute(
                """
                INSERT INTO positions (
                    scan_id,
                    wallet,
                    market_id,
                    title,
                    outcome,
                    shares,
                    average_price,
                    current_price,
                    current_value,
                    cash_pnl,
                    percent_pnl
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_id,
                    wallet,
                    str(market_id),
                    str(title),
                    str(outcome),
                    safe_number(position.get("size")),
                    safe_number(position.get("avgPrice")),
                    safe_number(position.get("curPrice")),
                    safe_number(position.get("currentValue")),
                    safe_number(position.get("cashPnl")),
                    safe_number(position.get("percentPnl")),
                ),
            )

        connection.commit()
        return int(scan_id)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def count_wallet_scans(wallet: str) -> int:
    """Return the number of stored scans for one wallet."""

    connection = connect_database()

    try:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM wallet_scans
            WHERE wallet = ?
            """,
            (wallet,),
        ).fetchone()

        return int(row["total"]) if row else 0

    finally:
        connection.close()


def get_previous_scan_id(
    wallet: str,
    current_scan_id: int,
) -> int | None:
    """Return the scan immediately before the current scan."""

    connection = connect_database()

    try:
        row = connection.execute(
            """
            SELECT id
            FROM wallet_scans
            WHERE wallet = ?
              AND id < ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                wallet,
                current_scan_id,
            ),
        ).fetchone()

        if row is None:
            return None

        return int(row["id"])

    finally:
        connection.close()


def get_positions_for_scan(
    scan_id: int,
) -> list[dict[str, Any]]:
    """Return all stored positions belonging to one scan."""

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT
                market_id,
                title,
                outcome,
                shares,
                average_price,
                current_price,
                current_value,
                cash_pnl,
                percent_pnl
            FROM positions
            WHERE scan_id = ?
            """,
            (scan_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


if __name__ == "__main__":
    create_tables()

    print("SQLite database created successfully.")
    print(f"Database location: {DATABASE_PATH.resolve()}")