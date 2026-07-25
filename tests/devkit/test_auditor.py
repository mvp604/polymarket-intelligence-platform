"""Tests for repository auditing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.devkit.auditor import (
    audit_repository,
    format_audit_report,
    write_audit_report,
)


class RepositoryAuditTests(unittest.TestCase):
    def test_repository_files_are_categorized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            source_directory = project_root / "src"
            test_directory = project_root / "tests"
            documentation_directory = project_root / "docs"
            database_directory = project_root / "database"

            source_directory.mkdir()
            test_directory.mkdir()
            documentation_directory.mkdir()
            database_directory.mkdir()

            (source_directory / "engine.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )

            (test_directory / "test_engine.py").write_text(
                "def test_example():\n    assert True\n",
                encoding="utf-8",
            )

            (project_root / "pyproject.toml").write_text(
                "[project]\nname = 'example'\n",
                encoding="utf-8",
            )

            (documentation_directory / "README.md").write_text(
                "# Example\n",
                encoding="utf-8",
            )

            (database_directory / "platform.db").write_bytes(
                b""
            )

            audit = audit_repository(project_root)

            self.assertEqual(
                audit.python_module_count,
                1,
            )

            self.assertEqual(
                audit.test_count,
                1,
            )

            self.assertIn(
                Path("src/engine.py"),
                audit.source_files,
            )

            self.assertIn(
                Path("tests/test_engine.py"),
                audit.test_files,
            )

            self.assertIn(
                Path("pyproject.toml"),
                audit.configuration_files,
            )

            self.assertIn(
                Path("docs/README.md"),
                audit.documentation_files,
            )

            self.assertIn(
                Path("database/platform.db"),
                audit.database_files,
            )

    def test_excluded_directories_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            virtual_environment = (
                project_root
                / ".venv"
                / "Lib"
            )

            virtual_environment.mkdir(
                parents=True
            )

            (virtual_environment / "ignored.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )

            audit = audit_repository(project_root)

            self.assertEqual(
                audit.python_files,
                (),
            )

    def test_report_contains_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            source_directory = project_root / "src"
            source_directory.mkdir()

            (source_directory / "engine.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )

            audit = audit_repository(project_root)
            report = format_audit_report(audit)

            self.assertIn(
                "REPOSITORY AUDIT",
                report,
            )

            self.assertIn(
                "Production Python modules: 1",
                report,
            )

            self.assertIn(
                "src",
                report,
            )

    def test_report_is_written_to_disk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            (project_root / "src").mkdir()

            audit = audit_repository(project_root)

            output_path = (
                project_root
                / "reports"
                / "repository_audit.txt"
            )

            result = write_audit_report(
                audit,
                output_path,
            )

            self.assertEqual(
                result,
                output_path.resolve(),
            )

            self.assertTrue(
                output_path.exists()
            )

            self.assertIn(
                "REPOSITORY AUDIT",
                output_path.read_text(
                    encoding="utf-8"
                ),
            )

    def test_missing_project_root_is_rejected(self) -> None:
        missing_path = (
            Path(tempfile.gettempdir())
            / "missing-polymarket-project-root"
        )

        with self.assertRaises(FileNotFoundError):
            audit_repository(missing_path)


if __name__ == "__main__":
    unittest.main()