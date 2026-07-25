from __future__ import annotations

import hashlib
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
MIGRATIONS_PATH = PROJECT_ROOT / "database" / "migrations"


@dataclass(frozen=True)
class Migration:
    migration_id: str
    path: Path
    checksum: str
    sql: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def split_sql_statements(script: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []

    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        candidate = "\n".join(buffer).strip()
        if sqlite3.complete_statement(candidate):
            statements.append(candidate)
            buffer = []

    trailing = "\n".join(buffer).strip()
    if trailing:
        raise ValueError("Migration contains an incomplete SQL statement.")
    return statements


def ensure_tracking_tables(connection: sqlite3.Connection) -> None:
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


def discover_migrations(path: Path = MIGRATIONS_PATH) -> list[Migration]:
    if not path.exists():
        raise RuntimeError(f"Migrations directory not found: {path}")

    migrations: list[Migration] = []
    for file_path in sorted(path.glob("*.sql")):
        sql = file_path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                migration_id=file_path.stem,
                path=file_path,
                checksum=sha256_text(sql),
                sql=sql,
            )
        )
    return migrations


def applied_migrations(connection: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return {
        row["migration_id"]: row
        for row in connection.execute(
            """
            SELECT migration_id, filename, checksum, applied_at,
                   execution_ms, status, error_message
            FROM schema_migrations
            """
        )
    }


def validate_checksums(
    migrations: Iterable[Migration],
    applied: dict[str, sqlite3.Row],
) -> None:
    for migration in migrations:
        previous = applied.get(migration.migration_id)
        if previous and previous["checksum"] != migration.checksum:
            raise RuntimeError(
                "Applied migration checksum changed: "
                f"{migration.migration_id}\n"
                f"Stored:  {previous['checksum']}\n"
                f"Current: {migration.checksum}"
            )


def apply_migration(
    connection: sqlite3.Connection,
    migration: Migration,
) -> None:
    started_at = utc_now()
    started = time.perf_counter()

    cursor = connection.execute(
        """
        INSERT INTO schema_migration_attempts (
            migration_id, filename, checksum, started_at, status
        ) VALUES (?, ?, ?, ?, 'RUNNING')
        """,
        (
            migration.migration_id,
            migration.path.name,
            migration.checksum,
            started_at,
        ),
    )
    attempt_id = int(cursor.lastrowid)
    connection.commit()

    try:
        statements = split_sql_statements(migration.sql)
        connection.execute("BEGIN IMMEDIATE")
        for statement in statements:
            connection.execute(statement)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        connection.execute(
            """
            INSERT INTO schema_migrations (
                migration_id, filename, checksum, applied_at,
                execution_ms, status, error_message
            ) VALUES (?, ?, ?, ?, ?, 'SUCCESS', NULL)
            """,
            (
                migration.migration_id,
                migration.path.name,
                migration.checksum,
                utc_now(),
                elapsed_ms,
            ),
        )
        connection.commit()

        connection.execute(
            """
            UPDATE schema_migration_attempts
            SET completed_at=?, execution_ms=?, status='SUCCESS'
            WHERE id=?
            """,
            (utc_now(), elapsed_ms, attempt_id),
        )
        connection.commit()
    except Exception as error:
        connection.rollback()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        connection.execute(
            """
            UPDATE schema_migration_attempts
            SET completed_at=?, execution_ms=?, status='FAILED',
                error_message=?
            WHERE id=?
            """,
            (utc_now(), elapsed_ms, str(error)[:4000], attempt_id),
        )
        connection.commit()
        raise


def run_migrations(
    database_path: Path = DATABASE_PATH,
    migrations_path: Path = MIGRATIONS_PATH,
) -> tuple[int, int]:
    if not database_path.exists():
        raise RuntimeError(f"Database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        ensure_tracking_tables(connection)

        migrations = discover_migrations(migrations_path)
        applied = applied_migrations(connection)
        validate_checksums(migrations, applied)

        pending = [
            migration
            for migration in migrations
            if migration.migration_id not in applied
        ]

        for migration in pending:
            print(f"Applying {migration.path.name} ...")
            apply_migration(connection, migration)
            print(f"Applied  {migration.path.name}")

        return len(migrations), len(pending)


def main() -> int:
    try:
        total, applied = run_migrations()
    except Exception as error:
        print(f"MIGRATION FAILED: {error}", file=sys.stderr)
        return 1

    print()
    print("=" * 72)
    print("DATABASE MIGRATIONS")
    print("=" * 72)
    print(f"Discovered migrations: {total}")
    print(f"Applied this run:      {applied}")
    print(f"Pending migrations:   0")
    print("STATUS: HEALTHY")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
