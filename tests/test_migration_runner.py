from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import src.migration_runner as runner


def write_migration(path: Path, name: str, sql: str) -> None:
    (path / name).write_text(sql, encoding="utf-8")


def test_migrations_apply_once(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    sqlite3.connect(database).close()

    write_migration(
        migrations,
        "001_create_test.sql",
        "CREATE TABLE test_items (id INTEGER PRIMARY KEY);",
    )

    total, applied = runner.run_migrations(database, migrations)
    total_again, applied_again = runner.run_migrations(database, migrations)

    assert (total, applied) == (1, 1)
    assert (total_again, applied_again) == (1, 0)


def test_failed_migration_rolls_back(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    sqlite3.connect(database).close()

    write_migration(
        migrations,
        "001_bad.sql",
        """
        CREATE TABLE should_rollback (id INTEGER PRIMARY KEY);
        CREATE INDEX bad_index ON missing_table(missing_column);
        """,
    )

    with pytest.raises(sqlite3.OperationalError):
        runner.run_migrations(database, migrations)

    with sqlite3.connect(database) as connection:
        exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='should_rollback'
            """
        ).fetchone()

    assert exists is None


def test_checksum_changes_are_rejected(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    sqlite3.connect(database).close()

    migration = migrations / "001_test.sql"
    migration.write_text(
        "CREATE TABLE checksum_test (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    runner.run_migrations(database, migrations)

    migration.write_text(
        "CREATE TABLE checksum_test (id INTEGER PRIMARY KEY, value TEXT);",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="checksum changed"):
        runner.run_migrations(database, migrations)
