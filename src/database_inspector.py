from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


def count_objects(connection: sqlite3.Connection, kind: str) -> int:
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type=?",
            (kind,),
        ).fetchone()[0]
    )


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    healthy = True
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]

        tables = count_objects(connection, "table")
        views = count_objects(connection, "view")
        indexes = count_objects(connection, "index")
        triggers = count_objects(connection, "trigger")

        applied = 0
        failed_attempts = 0
        if connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='schema_migrations'"
        ).fetchone():
            applied = connection.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE status='SUCCESS'"
            ).fetchone()[0]
        if connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='schema_migration_attempts'"
        ).fetchone():
            failed_attempts = connection.execute(
                """
                SELECT COUNT(*)
                FROM schema_migration_attempts
                WHERE status='FAILED'
                """
            ).fetchone()[0]

        healthy &= integrity == "ok"
        healthy &= len(foreign_keys) == 0

        print("=" * 78)
        print("DATABASE INSPECTOR")
        print("=" * 78)
        print(f"{'Integrity check':<42} {integrity}")
        print(f"{'Foreign-key violations':<42} {len(foreign_keys):,}")
        print(f"{'Tables':<42} {tables:,}")
        print(f"{'Views':<42} {views:,}")
        print(f"{'Indexes':<42} {indexes:,}")
        print(f"{'Triggers':<42} {triggers:,}")
        print(f"{'Applied migrations':<42} {applied:,}")
        print(f"{'Failed migration attempts (history)':<42} {failed_attempts:,}")
        print("=" * 78)
        print(f"OVERALL STATUS: {'HEALTHY' if healthy else 'ATTENTION REQUIRED'}")
        print("=" * 78)

    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
