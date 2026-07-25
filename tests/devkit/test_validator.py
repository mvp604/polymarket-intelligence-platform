"""Tests for project validation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.devkit.validator import validate_project


class ValidationTests(unittest.TestCase):
    def test_valid_project_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            for folder_name in (
                "src",
                "tests",
                "tools",
            ):
                (
                    project_root
                    / folder_name
                ).mkdir()

            result = validate_project(
                project_root
            )

            self.assertTrue(result.valid)
            self.assertEqual(
                result.missing_paths,
                (),
            )
            self.assertEqual(
                result.errors,
                (),
            )

    def test_missing_directories_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            (
                project_root
                / "src"
            ).mkdir()

            result = validate_project(
                project_root
            )

            self.assertFalse(result.valid)

            self.assertIn(
                Path("tests"),
                result.missing_paths,
            )

            self.assertIn(
                Path("tools"),
                result.missing_paths,
            )


if __name__ == "__main__":
    unittest.main()
