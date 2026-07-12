import sqlite3
from datetime import datetime, timezone
from pathlib import Path


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
    """Create the database tables if they do not already exist."""

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

    connection.commit()
    connection.close()


def safe_number(value: object) -> float:
    """Convert an API value to a number without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def save_wallet_scan(wallet: str, positions: list[dict]) -> int:
    """
    Save one wallet scan and all positions connected to that scan.

    Returns the newly created scan ID.
    """

    create_tables()

    connection = connect_database()
    cursor = connection.cursor()

    scanned_at = datetime.now(timezone.utc).isoformat()

    cursor.execute(
        """
        INSERT INTO wallet_scans (wallet, scanned_at)
        VALUES (?, ?)
        """,
        (wallet, scanned_at),
    )

    scan_id = cursor.lastrowid

    if scan_id is None:
        connection.close()
        raise RuntimeError("SQLite did not return a scan ID.")

    for position in positions:
        market_id = (
            position.get("conditionId")
            or position.get("marketId")
            or position.get("slug")
            or position.get("asset")
            or ""
        )

        title = position.get("title") or "Unknown market"
        outcome = position.get("outcome") or "Unknown"

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
                market_id,
                title,
                outcome,
                safe_number(position.get("size")),
                safe_number(position.get("avgPrice")),
                safe_number(position.get("curPrice")),
                safe_number(position.get("currentValue")),
                safe_number(position.get("cashPnl")),
                safe_number(position.get("percentPnl")),
            ),
        )

    connection.commit()
    connection.close()

    return scan_id


def count_wallet_scans(wallet: str) -> int:
    """Return the number of stored scans for one wallet."""

    connection = connect_database()

    row = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM wallet_scans
        WHERE wallet = ?
        """,
        (wallet,),
    ).fetchone()

    connection.close()

    return int(row["total"]) if row else 0


if __name__ == "__main__":
    create_tables()
    print("SQLite database created successfully.")
    print(f"Database location: {DATABASE_PATH}")