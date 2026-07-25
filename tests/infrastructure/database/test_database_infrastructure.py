from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.config.database import DatabaseSettings
from src.infrastructure.database import (
    DatabaseConnectionFactory,
    DatabaseSession,
)


class DatabaseInfrastructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()

        self.database_path = (
            Path(self.temporary_directory.name)
            / "infrastructure_test.db"
        )

        settings = DatabaseSettings(
            sqlite_path=self.database_path,
            enable_foreign_keys=True,
        )

        self.factory = DatabaseConnectionFactory(
            settings=settings,
            enable_wal=False,
        )

        self.session = DatabaseSession(self.factory)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_connection_factory_creates_database(self) -> None:
        with self.session.connection() as connection:
            version = connection.execute(
                "SELECT sqlite_version()"
            ).fetchone()[0]

        self.assertTrue(version)
        self.assertTrue(self.database_path.exists())

    def test_row_factory_returns_named_rows(self) -> None:
        with self.session.connection() as connection:
            row = connection.execute(
                "SELECT 42 AS answer"
            ).fetchone()

        self.assertIsInstance(row, sqlite3.Row)
        self.assertEqual(row["answer"], 42)

    def test_foreign_keys_are_enabled(self) -> None:
        with self.session.connection() as connection:
            enabled = connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]

        self.assertEqual(enabled, 1)

    def test_transaction_commits_on_success(self) -> None:
        with self.session.transaction() as connection:
            connection.execute(
                """
                CREATE TABLE test_records (
                    id INTEGER PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                INSERT INTO test_records (value)
                VALUES (?)
                """,
                ("committed",),
            )

        with self.session.connection(
            read_only=True
        ) as connection:
            row = connection.execute(
                """
                SELECT value
                FROM test_records
                """
            ).fetchone()

        self.assertEqual(row["value"], "committed")

    def test_transaction_rolls_back_on_failure(self) -> None:
        with self.session.transaction() as connection:
            connection.execute(
                """
                CREATE TABLE rollback_records (
                    id INTEGER PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

        with self.assertRaises(RuntimeError):
            with self.session.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO rollback_records (value)
                    VALUES (?)
                    """,
                    ("must_not_survive",),
                )

                raise RuntimeError("Force rollback.")

        with self.session.connection(
            read_only=True
        ) as connection:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM rollback_records
                """
            ).fetchone()[0]

        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()