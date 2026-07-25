from __future__ import annotations

import argparse
import importlib.util
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Iterable


DEFAULT_DATABASE_PATH = Path("database/polymarket.db")
DEFAULT_MIGRATIONS_PATH = Path("database/migrations")


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    name: str
    path: Path
    module: ModuleType


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root() / path
    return path.resolve()


def connect_database(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            checksum TEXT NOT NULL,
            execution_seconds REAL NOT NULL DEFAULT 0
        )
        """
    )
    connection.commit()


def load_module(path: Path) -> ModuleType:
    module_name = f"migration_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load migration: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_migrations(path: Path) -> list[Migration]:
    migrations: list[Migration] = []

    for file_path in sorted(path.glob("[0-9][0-9][0-9][0-9]_*.py")):
        module = load_module(file_path)

        version = str(getattr(module, "VERSION", file_path.stem[:4]))
        name = str(getattr(module, "NAME", file_path.stem[5:]))

        if not hasattr(module, "upgrade"):
            raise RuntimeError(
                f"Migration {file_path.name} has no upgrade(connection) function."
            )

        migrations.append(
            Migration(
                version=version,
                name=name,
                path=file_path,
                module=module,
            )
        )

    versions = [migration.version for migration in migrations]
    if len(versions) != len(set(versions)):
        raise RuntimeError("Duplicate migration versions detected.")

    return migrations


def file_checksum(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def applied_migrations(
    connection: sqlite3.Connection,
) -> dict[str, sqlite3.Row]:
    rows = connection.execute(
        """
        SELECT version, name, checksum, applied_at
        FROM schema_migrations
        ORDER BY version
        """
    ).fetchall()

    return {str(row["version"]): row for row in rows}


def create_backup(database_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = database_path.with_name(
        f"{database_path.stem}_before_migrations_{stamp}{database_path.suffix}"
    )
    shutil.copy2(database_path, backup_path)
    return backup_path


def apply_migration(
    connection: sqlite3.Connection,
    migration: Migration,
) -> float:
    import time

    started = time.perf_counter()
    connection.execute("BEGIN IMMEDIATE")

    try:
        migration.module.upgrade(connection)
        runtime = time.perf_counter() - started
        connection.execute(
            """
            INSERT INTO schema_migrations (
                version,
                name,
                applied_at,
                checksum,
                execution_seconds
            )
            VALUES (?, ?, datetime('now'), ?, ?)
            """,
            (
                migration.version,
                migration.name,
                file_checksum(migration.path),
                runtime,
            ),
        )
        connection.commit()
        return runtime
    except Exception:
        connection.rollback()
        raise


def print_status(
    migrations: Iterable[Migration],
    applied: dict[str, sqlite3.Row],
) -> None:
    print("=" * 104)
    print("DATABASE MIGRATION STATUS")
    print("=" * 104)

    for migration in migrations:
        row = applied.get(migration.version)
        status = "APPLIED" if row else "PENDING"
        print(
            f"{migration.version}  {status:<8}  "
            f"{migration.name:<34}  {migration.path.name}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply versioned SQLite schema migrations."
    )
    parser.add_argument(
        "--database",
        default=str(DEFAULT_DATABASE_PATH),
        help="SQLite database path.",
    )
    parser.add_argument(
        "--migrations",
        default=str(DEFAULT_MIGRATIONS_PATH),
        help="Migration directory.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status without applying changes.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip the automatic database backup.",
    )
    parser.add_argument(
        "--target",
        help="Apply migrations through this version only.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    database_path = resolve_project_path(args.database)
    migrations_path = resolve_project_path(args.migrations)

    if not migrations_path.exists():
        raise FileNotFoundError(
            f"Migration directory not found: {migrations_path}"
        )

    migrations = discover_migrations(migrations_path)
    connection = connect_database(database_path)
    ensure_migration_table(connection)

    applied = applied_migrations(connection)

    for migration in migrations:
        row = applied.get(migration.version)
        if row is None:
            continue

        current_checksum = file_checksum(migration.path)
        stored_checksum = str(row["checksum"])
        if current_checksum != stored_checksum:
            raise RuntimeError(
                f"Applied migration {migration.version} was modified after "
                f"execution. Stored checksum={stored_checksum}, "
                f"current checksum={current_checksum}"
            )

    if args.status:
        print_status(migrations, applied)
        connection.close()
        return 0

    pending = [
        migration
        for migration in migrations
        if migration.version not in applied
        and (
            args.target is None
            or migration.version <= str(args.target)
        )
    ]

    print("=" * 104)
    print("DATABASE MIGRATION RUNNER")
    print("=" * 104)
    print(f"Database:   {database_path}")
    print(f"Migrations: {migrations_path}")
    print(f"Discovered: {len(migrations)}")
    print(f"Applied:    {len(applied)}")
    print(f"Pending:    {len(pending)}")

    if not pending:
        print("Database schema is current.")
        connection.close()
        return 0

    if not args.no_backup:
        backup_path = create_backup(database_path)
        print(f"Backup:     {backup_path}")

    try:
        for migration in pending:
            print(
                f"Applying {migration.version} "
                f"{migration.name}...",
                end=" ",
                flush=True,
            )
            runtime = apply_migration(connection, migration)
            print(f"SUCCESS ({runtime:.3f}s)")
    except Exception as error:
        print("FAILED")
        print(f"Migration error: {error}", file=sys.stderr)
        connection.close()
        return 1

    print("=" * 104)
    print("DATABASE MIGRATIONS COMPLETE")
    print("=" * 104)

    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

