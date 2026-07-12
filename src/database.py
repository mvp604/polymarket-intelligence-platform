import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DATABASE_PATH = Path("database/polymarket.db")


def connect_database() -> sqlite3.Connection:
    """Open a connection to the local SQLite database."""

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

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
            scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

    print("SQLite database created successfully.")
    print(f"Database location: {DATABASE_PATH}")


if __name__ == "__main__":
    create_tables()