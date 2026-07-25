from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.pdk.sprint_runner import (
    FileOperation,
    ManifestValidationError,
    SprintManifest,
    SprintRunner,
    SprintValidationError,
)


class SprintRunnerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()

        self.backups = self.root / "backups"
        self.runner = SprintRunner(
            self.repository,
            backup_root=self.backups,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_source(
        self,
        relative_path: str,
        content: str,
    ) -> Path:
        path = self.repository / "sprints" / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def build_manifest(
        self,
        *,
        source: Path,
        target: str,
        commands: tuple[tuple[str, ...], ...] = (),
    ) -> SprintManifest:
        return SprintManifest(
            name="test sprint",
            files=(
                FileOperation(
                    source=source,
                    target=self.repository / target,
                ),
            ),
            commands=commands,
        )


class SprintRunnerSuccessTests(SprintRunnerTestCase):
    def test_writes_new_file(self) -> None:
        source = self.create_source(
            "payload/example.py",
            "value = 42\n",
        )

        result = self.runner.apply(
            self.build_manifest(
                source=source,
                target="src/example.py",
            )
        )

        target = self.repository / "src/example.py"

        self.assertEqual(
            target.read_text(encoding="utf-8"),
            "value = 42\n",
        )
        self.assertEqual(
            result.changed_files,
            (target,),
        )

    def test_overwrites_existing_file(self) -> None:
        target = self.repository / "src/example.py"
        target.parent.mkdir(parents=True)
        target.write_text("old\n", encoding="utf-8")

        source = self.create_source(
            "payload/example.py",
            "new\n",
        )

        self.runner.apply(
            self.build_manifest(
                source=source,
                target="src/example.py",
            )
        )

        self.assertEqual(
            target.read_text(encoding="utf-8"),
            "new\n",
        )

    def test_runs_validation_command_from_repository_root(self) -> None:
        source = self.create_source(
            "payload/example.py",
            "value = 42\n",
        )

        marker_script = self.create_source(
            "create_marker.py",
            (
                "from pathlib import Path\n"
                "Path('command-ran.txt').write_text("
                "'yes', encoding='utf-8')\n"
            ),
        )

        relative_script = marker_script.relative_to(
            self.repository
        )

        self.runner.apply(
            self.build_manifest(
                source=source,
                target="src/example.py",
                commands=(
                    (
                        sys.executable,
                        str(relative_script),
                    ),
                ),
            )
        )

        self.assertEqual(
            (
                self.repository / "command-ran.txt"
            ).read_text(encoding="utf-8"),
            "yes",
        )

    def test_creates_backup_directory(self) -> None:
        source = self.create_source(
            "payload/example.py",
            "value = 42\n",
        )

        result = self.runner.apply(
            self.build_manifest(
                source=source,
                target="src/example.py",
            )
        )

        self.assertTrue(result.backup_directory.exists())
        self.assertTrue(
            result.backup_directory.is_dir()
        )


class SprintRunnerRollbackTests(SprintRunnerTestCase):
    def failing_command(self) -> tuple[str, ...]:
        return (
            sys.executable,
            "-c",
            "raise SystemExit(7)",
        )

    def test_restores_existing_file_after_failure(self) -> None:
        target = self.repository / "src/example.py"
        target.parent.mkdir(parents=True)
        target.write_text(
            "original\n",
            encoding="utf-8",
        )

        source = self.create_source(
            "payload/example.py",
            "replacement\n",
        )

        with self.assertRaises(SprintValidationError):
            self.runner.apply(
                self.build_manifest(
                    source=source,
                    target="src/example.py",
                    commands=(self.failing_command(),),
                )
            )

        self.assertEqual(
            target.read_text(encoding="utf-8"),
            "original\n",
        )

    def test_removes_new_file_after_failure(self) -> None:
        source = self.create_source(
            "payload/example.py",
            "replacement\n",
        )

        target = self.repository / "src/example.py"

        with self.assertRaises(SprintValidationError):
            self.runner.apply(
                self.build_manifest(
                    source=source,
                    target="src/example.py",
                    commands=(self.failing_command(),),
                )
            )

        self.assertFalse(target.exists())

    def test_reports_failed_command_and_return_code(self) -> None:
        source = self.create_source(
            "payload/example.py",
            "replacement\n",
        )

        command = self.failing_command()

        with self.assertRaises(
            SprintValidationError
        ) as context:
            self.runner.apply(
                self.build_manifest(
                    source=source,
                    target="src/example.py",
                    commands=(command,),
                )
            )

        self.assertEqual(
            context.exception.command,
            command,
        )
        self.assertEqual(
            context.exception.returncode,
            7,
        )

    def test_rolls_back_when_atomic_copy_raises(self) -> None:
        first_target = self.repository / "src/first.py"
        first_target.parent.mkdir(parents=True)
        first_target.write_text(
            "original\n",
            encoding="utf-8",
        )

        first_source = self.create_source(
            "payload/first.py",
            "updated\n",
        )
        second_source = self.create_source(
            "payload/second.py",
            "second\n",
        )

        manifest = SprintManifest(
            name="copy failure",
            files=(
                FileOperation(
                    source=first_source,
                    target=first_target,
                ),
                FileOperation(
                    source=second_source,
                    target=self.repository / "src/second.py",
                ),
            ),
            commands=(),
        )

        real_atomic_copy = self.runner._atomic_copy
        invocation_count = 0

        def controlled_copy(
            source: Path,
            target: Path,
        ) -> None:
            nonlocal invocation_count
            invocation_count += 1

            if invocation_count == 2:
                raise OSError("simulated copy failure")

            real_atomic_copy(source, target)

        with patch.object(
            self.runner,
            "_atomic_copy",
            side_effect=controlled_copy,
        ):
            with self.assertRaisesRegex(
                OSError,
                "simulated copy failure",
            ):
                self.runner.apply(manifest)

        self.assertEqual(
            first_target.read_text(encoding="utf-8"),
            "original\n",
        )


class SprintManifestTests(SprintRunnerTestCase):
    def write_manifest(
        self,
        data: object,
    ) -> Path:
        path = self.repository / "sprints/manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data),
            encoding="utf-8",
        )
        return path

    def test_loads_valid_manifest(self) -> None:
        source = self.create_source(
            "payload/example.py",
            "value = 42\n",
        )

        manifest_path = self.write_manifest(
            {
                "name": "example",
                "files": [
                    {
                        "source": str(
                            source.relative_to(
                                manifest_path_parent := (
                                    self.repository / "sprints"
                                )
                            )
                        ),
                        "target": "src/example.py",
                    }
                ],
                "commands": [
                    [
                        sys.executable,
                        "-m",
                        "py_compile",
                        "src/example.py",
                    ]
                ],
            }
        )

        manifest = self.runner.load_manifest(
            manifest_path
        )

        self.assertEqual(manifest.name, "example")
        self.assertEqual(len(manifest.files), 1)
        self.assertEqual(len(manifest.commands), 1)

    def test_rejects_path_traversal_target(self) -> None:
        source = self.create_source(
            "payload/example.py",
            "value = 42\n",
        )

        data = {
            "name": "unsafe",
            "files": [
                {
                    "source": str(
                        source.relative_to(
                            self.repository / "sprints"
                        )
                    ),
                    "target": "../outside.py",
                }
            ],
        }

        with self.assertRaisesRegex(
            ManifestValidationError,
            "escapes its allowed directory",
        ):
            self.runner.parse_manifest(
                data,
                manifest_directory=(
                    self.repository / "sprints"
                ),
            )

    def test_rejects_path_traversal_source(self) -> None:
        outside_source = self.repository / "outside.py"
        outside_source.write_text(
            "value = 42\n",
            encoding="utf-8",
        )

        data = {
            "name": "unsafe",
            "files": [
                {
                    "source": "../outside.py",
                    "target": "src/example.py",
                }
            ],
        }

        with self.assertRaisesRegex(
            ManifestValidationError,
            "escapes its allowed directory",
        ):
            self.runner.parse_manifest(
                data,
                manifest_directory=(
                    self.repository / "sprints"
                ),
            )

    def test_rejects_duplicate_targets(self) -> None:
        first = self.create_source(
            "payload/first.py",
            "first\n",
        )
        second = self.create_source(
            "payload/second.py",
            "second\n",
        )

        sprint_directory = self.repository / "sprints"

        data = {
            "name": "duplicates",
            "files": [
                {
                    "source": str(
                        first.relative_to(sprint_directory)
                    ),
                    "target": "src/example.py",
                },
                {
                    "source": str(
                        second.relative_to(sprint_directory)
                    ),
                    "target": "src/example.py",
                },
            ],
        }

        with self.assertRaisesRegex(
            ManifestValidationError,
            "Duplicate sprint target",
        ):
            self.runner.parse_manifest(
                data,
                manifest_directory=sprint_directory,
            )

    def test_rejects_missing_source(self) -> None:
        data = {
            "name": "missing",
            "files": [
                {
                    "source": "payload/missing.py",
                    "target": "src/example.py",
                }
            ],
        }

        with self.assertRaisesRegex(
            ManifestValidationError,
            "does not exist",
        ):
            self.runner.parse_manifest(
                data,
                manifest_directory=(
                    self.repository / "sprints"
                ),
            )

    def test_rejects_empty_file_list(self) -> None:
        with self.assertRaisesRegex(
            ManifestValidationError,
            "non-empty list",
        ):
            self.runner.parse_manifest(
                {
                    "name": "empty",
                    "files": [],
                },
                manifest_directory=self.repository,
            )

    def test_rejects_invalid_command(self) -> None:
        source = self.create_source(
            "payload/example.py",
            "value = 42\n",
        )

        with self.assertRaisesRegex(
            ManifestValidationError,
            "non-empty list",
        ):
            self.runner.parse_manifest(
                {
                    "name": "invalid command",
                    "files": [
                        {
                            "source": str(
                                source.relative_to(
                                    self.repository
                                )
                            ),
                            "target": "src/example.py",
                        }
                    ],
                    "commands": [[]],
                },
                manifest_directory=self.repository,
            )


if __name__ == "__main__":
    unittest.main()