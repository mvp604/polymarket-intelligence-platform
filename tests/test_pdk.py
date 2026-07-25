from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.pdk import Sprint, SprintExecutionError
from tools.pdk.actions import (
    CompilePython,
    CreateFile,
    GitDiffCheck,
    RunTests,
)


class SprintDefinitionTests(unittest.TestCase):
    def test_fluent_api_builds_typed_actions(self) -> None:
        sprint = (
            Sprint(version="1.0.0", name="Example")
            .create_file("src/example.py", "VALUE = 1\n")
            .compile_python("src")
            .run_tests("tests")
            .git_diff_check()
        )

        self.assertEqual(len(sprint.actions), 4)
        self.assertIsInstance(sprint.actions[0], CreateFile)
        self.assertIsInstance(sprint.actions[1], CompilePython)
        self.assertIsInstance(sprint.actions[2], RunTests)
        self.assertIsInstance(sprint.actions[3], GitDiffCheck)

    def test_empty_sprint_cannot_execute(self) -> None:
        with self.assertRaises(ValueError):
            Sprint(
                version="1.0.0",
                name="Empty",
            ).execute()

    def test_compile_requires_a_path(self) -> None:
        sprint = Sprint(version="1.0.0", name="Compile")

        with self.assertRaises(ValueError):
            sprint.compile_python()


class SprintExecutionTests(unittest.TestCase):
    def test_create_file_writes_utf8_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            (
                Sprint(
                    version="1.0.0",
                    name="Create file",
                    root=root,
                )
                .create_file(
                    "src/example.py",
                    "MESSAGE = \"hello\"\n",
                )
                .execute()
            )

            created = root / "src" / "example.py"

            self.assertTrue(created.exists())
            self.assertEqual(
                created.read_text(encoding="utf-8"),
                "MESSAGE = \"hello\"\n",
            )
            self.assertFalse(
                created.read_bytes().startswith(
                    b"\xef\xbb\xbf"
                )
            )

    def test_existing_file_is_protected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "existing.py"
            path.write_text(
                "ORIGINAL = True\n",
                encoding="utf-8",
            )

            sprint = (
                Sprint(
                    version="1.0.0",
                    name="Protection",
                    root=root,
                )
                .create_file(
                    "existing.py",
                    "CHANGED = True\n",
                )
            )

            with self.assertRaises(SprintExecutionError):
                sprint.execute()

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "ORIGINAL = True\n",
            )

    def test_failed_sprint_rolls_back_created_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            sprint = (
                Sprint(
                    version="1.0.0",
                    name="Rollback",
                    root=root,
                )
                .create_file("created.py", "VALUE = 1\n")
                .compile_python("missing_directory")
            )

            with self.assertRaises(SprintExecutionError):
                sprint.execute()

            self.assertFalse(
                (root / "created.py").exists()
            )

    def test_overwrite_restores_original_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "existing.py"
            path.write_text(
                "ORIGINAL = True\n",
                encoding="utf-8",
            )

            sprint = (
                Sprint(
                    version="1.0.0",
                    name="Restore",
                    root=root,
                )
                .create_file(
                    "existing.py",
                    "CHANGED = True\n",
                    overwrite=True,
                )
                .compile_python("missing_directory")
            )

            with self.assertRaises(SprintExecutionError):
                sprint.execute()

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "ORIGINAL = True\n",
            )

    def test_repository_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            sprint = (
                Sprint(
                    version="1.0.0",
                    name="Path safety",
                    root=root,
                )
                .create_file("../outside.py", "VALUE = 1\n")
            )

            with self.assertRaises(SprintExecutionError):
                sprint.execute()


if __name__ == "__main__":
    unittest.main()
