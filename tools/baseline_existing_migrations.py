from __future__ import annotations

import hashlib
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
MIGRATIONS_PATH = PROJECT_ROOT / "database" / "migrations"
BASELINE_BEFORE = "006_"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def ensure_tracking(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            execution_ms INTEGER NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migration_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            checksum TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            execution_ms INTEGER,
            status TEXT NOT NULL,
            error_message TEXT
        )
        """
    )
    connection.commit()


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    required_existing_tables = {
        "positions",
        "platform_events",
        "opportunity_enrichment_current",
        "institutional_reviews",
    }

    with sqlite3.connect(DATABASE_PATH) as connection:
        ensure_tracking(connection)
        missing = [
            name
            for name in sorted(required_existing_tables)
            if not table_exists(connection, name)
        ]
        if missing:
            print(
                "Refusing to baseline because expected live tables are missing: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            return 1

        files = [
            path
            for path in sorted(MIGRATIONS_PATH.glob("*.sql"))
            if path.name < BASELINE_BEFORE
        ]
        added = 0
        for path in files:
            migration_id = path.stem
            exists = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE migration_id=?",
                (migration_id,),
            ).fetchone()
            if exists:
                continue
            connection.execute(
                """
                INSERT INTO schema_migrations (
                    migration_id, filename, checksum, applied_at,
                    execution_ms, status, error_message
                ) VALUES (?, ?, ?, ?, 0, 'SUCCESS', 'BASELINED_EXISTING_SCHEMA')
                """,
                (
                    migration_id,
                    path.name,
                    checksum(path),
                    utc_now(),
                ),
            )
            added += 1
        connection.commit()

    print(f"Historical migrations baselined: {added}")
    print("Existing schema was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
