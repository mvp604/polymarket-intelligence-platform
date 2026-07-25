"""Tests for project backup utilities."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.devkit.backup import backup_files


class BackupTests(unittest.TestCase):
    def test_existing_file_is_backed_up(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            source_file = (
                project_root
                / "tools"
                / "sample.py"
            )

            source_file.parent.mkdir(
                parents=True
            )

            source_file.write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )

            backup_root = backup_files(
                project_root,
                [source_file],
            )

            self.assertIsNotNone(
                backup_root
            )

            assert backup_root is not None

            backup_file = (
                backup_root
                / "tools"
                / "sample.py"
            )

            self.assertTrue(
                backup_file.exists()
            )

            self.assertEqual(
                backup_file.read_text(
                    encoding="utf-8"
                ),
                "VALUE = 1\n",
            )

    def test_no_backup_for_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            backup_root = backup_files(
                project_root,
                [
                    project_root
                    / "missing.py"
                ],
            )

            self.assertIsNone(
                backup_root
            )


if __name__ == "__main__":
    unittest.main()
