"""Tests for project compilation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.devkit.compiler import (
    compile_project,
    discover_python_files,
)


class CompilerTests(unittest.TestCase):
    def test_python_files_are_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            source_directory = project_root / "src"
            source_directory.mkdir()

            source_file = source_directory / "sample.py"

            source_file.write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )

            files = discover_python_files(
                project_root
            )

            self.assertEqual(
                files,
                (source_file,),
            )

    def test_valid_python_file_compiles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            source_directory = project_root / "src"
            source_directory.mkdir()

            source_file = source_directory / "sample.py"

            source_file.write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )

            result = compile_project(
                project_root
            )

            self.assertTrue(
                result.successful
            )

            self.assertIn(
                source_file,
                result.compiled_files,
            )

            self.assertEqual(
                result.errors,
                (),
            )

    def test_invalid_python_file_fails_compilation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            source_directory = project_root / "src"
            source_directory.mkdir()

            source_file = source_directory / "broken.py"

            source_file.write_text(
                "def broken(:\n",
                encoding="utf-8",
            )

            result = compile_project(
                project_root
            )

            self.assertFalse(
                result.successful
            )

            self.assertTrue(
                result.errors
            )


if __name__ == "__main__":
    unittest.main()
