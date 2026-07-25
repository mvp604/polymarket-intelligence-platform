from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.config.database import DatabaseSettings
from src.infrastructure.database import (
    DatabaseConnectionFactory,
    DatabaseSession,
)
from src.infrastructure.repositories import BaseRepository


class TestRepository(BaseRepository):
    def create_schema(self) -> None:
        self.execute(
            """
            CREATE TABLE repository_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                score REAL NOT NULL
            )
            """
        )

    def insert_record(
        self,
        name: str,
        score: float,
    ) -> int:
        return self.execute_insert(
            """
            INSERT INTO repository_records (
                name,
                score
            )
            VALUES (?, ?)
            """,
            (
                name,
                score,
            ),
        )


class BaseRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()

        database_path = (
            Path(self.temporary_directory.name)
            / "repository_test.db"
        )

        settings = DatabaseSettings(
            sqlite_path=database_path,
            enable_foreign_keys=True,
        )

        factory = DatabaseConnectionFactory(
            settings=settings,
            enable_wal=False,
        )

        session = DatabaseSession(factory)

        self.repository = TestRepository(session)
        self.repository.create_schema()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_insert_and_fetch_one(self) -> None:
        record_id = self.repository.insert_record(
            "wallet_alpha",
            91.5,
        )

        row = self.repository.fetch_one(
            """
            SELECT
                id,
                name,
                score
            FROM repository_records
            WHERE id = ?
            """,
            (record_id,),
        )

        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "wallet_alpha")
        self.assertEqual(row["score"], 91.5)

    def test_execute_many_and_fetch_all(self) -> None:
        inserted = self.repository.execute_many(
            """
            INSERT INTO repository_records (
                name,
                score
            )
            VALUES (?, ?)
            """,
            [
                ("wallet_one", 80.0),
                ("wallet_two", 85.0),
                ("wallet_three", 90.0),
            ],
        )

        rows = self.repository.fetch_all(
            """
            SELECT
                name,
                score
            FROM repository_records
            ORDER BY score DESC
            """
        )

        self.assertEqual(inserted, 3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["name"], "wallet_three")

    def test_table_exists(self) -> None:
        self.assertTrue(
            self.repository.table_exists(
                "repository_records"
            )
        )

        self.assertFalse(
            self.repository.table_exists(
                "missing_table"
            )
        )


if __name__ == "__main__":
    unittest.main()