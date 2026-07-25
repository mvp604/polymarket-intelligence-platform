from __future__ import annotations

import sqlite3
from pathlib import Path

from src.repository_compatibility_adapter import (
    event_consumer_adapter,
    migration_adapter,
)
from src.repository_schema_discovery import discover_repository


def test_discovers_unknown_schema_without_assumptions(
    tmp_path: Path,
) -> None:
    database = tmp_path / "test.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations "
            "(version TEXT PRIMARY KEY, executed_at TEXT)"
        )
        connection.execute(
            "CREATE TABLE event_consumers "
            "(name TEXT PRIMARY KEY, active INTEGER)"
        )
        connection.execute(
            "CREATE TABLE elite_wallet_profiles "
            "(wallet TEXT PRIMARY KEY)"
        )

    report = discover_repository(database)

    assert "version" in {
        column["name"]
        for column in report["tables"]["schema_migrations"]["columns"]
    }
    assert migration_adapter(report)["id"] == "version"
    assert event_consumer_adapter(report)["enabled"] == "active"


def test_foreign_key_check_failure_is_reported_not_raised(
    tmp_path: Path,
) -> None:
    database = tmp_path / "test.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE parent (id INTEGER PRIMARY KEY)"
        )
        connection.execute(
            """
            CREATE TABLE child (
                parent_id INTEGER,
                FOREIGN KEY(parent_id) REFERENCES parent(missing)
            )
            """
        )

    report = discover_repository(database)

    assert "foreign_key_check_error" in report["database"]


def test_legacy_objects_are_identified(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE positions_backup_20260725 (id INTEGER)"
        )
        connection.execute(
            "CREATE TABLE wallet_runs_legacy (id INTEGER)"
        )

    report = discover_repository(database)
    legacy = report["compatibility"]["legacy_or_backup_objects"]

    assert "positions_backup_20260725" in legacy
    assert "wallet_runs_legacy" in legacy
