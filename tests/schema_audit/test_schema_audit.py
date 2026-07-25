from __future__ import annotations

import sys
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

AUDITOR_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "audit_database_schema.py"
)

module_spec = (
    importlib.util.spec_from_file_location(
        "audit_database_schema",
        AUDITOR_PATH,
    )
)

if (
    module_spec is None
    or module_spec.loader is None
):
    raise RuntimeError(
        "Unable to load schema audit module."
    )

audit_module = (
    importlib.util.module_from_spec(
        module_spec
    )
)

sys.modules[module_spec.name] = audit_module
module_spec.loader.exec_module(
    audit_module
)


class SchemaAuditTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory()
        )

        self.root = Path(
            self.temporary_directory.name
        )

        self.database_path = (
            self.root
            / "schema_audit_test.db"
        )

        connection = sqlite3.connect(
            self.database_path
        )

        connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE wallet_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                scanned_at TEXT NOT NULL
            );

            CREATE TABLE positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                market_id TEXT NOT NULL,
                current_value REAL NOT NULL,

                FOREIGN KEY (scan_id)
                    REFERENCES wallet_scans(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX idx_positions_wallet
            ON positions(wallet);
            """
        )

        connection.execute(
            """
            INSERT INTO wallet_scans (
                wallet,
                scanned_at
            )
            VALUES (?, ?)
            """,
            (
                "0xabc",
                "2026-07-22T00:00:00+00:00",
            ),
        )

        connection.commit()
        connection.close()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_audit_discovers_tables(
        self,
    ) -> None:
        audit = audit_module.build_audit(
            self.database_path
        )

        self.assertEqual(
            audit.integrity_check,
            "ok",
        )

        self.assertEqual(
            audit.table_count,
            2,
        )

        tables = {
            table.name: table
            for table in audit.tables
        }

        self.assertIn(
            "wallet_scans",
            tables,
        )

        self.assertIn(
            "positions",
            tables,
        )

        self.assertEqual(
            tables[
                "wallet_scans"
            ].row_count,
            1,
        )

        self.assertEqual(
            len(
                tables[
                    "positions"
                ].foreign_keys
            ),
            1,
        )

        self.assertEqual(
            len(
                tables[
                    "positions"
                ].indexes
            ),
            1,
        )

    def test_outputs_are_created(
        self,
    ) -> None:
        audit = audit_module.build_audit(
            self.database_path
        )

        markdown_path = (
            self.root
            / "schema.md"
        )

        json_path = (
            self.root
            / "schema.json"
        )

        audit_module.write_outputs(
            audit,
            markdown_path,
            json_path,
        )

        self.assertTrue(
            markdown_path.exists()
        )

        self.assertTrue(
            json_path.exists()
        )

        markdown = (
            markdown_path.read_text(
                encoding="utf-8"
            )
        )

        self.assertIn(
            (
                "Database Schema "
                "Specification v1.0"
            ),
            markdown,
        )


if __name__ == "__main__":
    unittest.main()
