from __future__ import annotations

from pathlib import Path

FILES: dict[str, str] = {
    "tools/pdk/__init__.py": '''"""Platform Development Kit public API."""

from .executor import SprintExecutionError, SprintExecutor
from .sprint import Sprint

__all__ = [
    "Sprint",
    "SprintExecutionError",
    "SprintExecutor",
]
''',

    "tools/pdk/actions.py": '''"""Typed actions supported by the Platform Development Kit."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CreateFile:
    """Create a UTF-8 source file."""

    path: Path
    content: str
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class CompilePython:
    """Compile Python paths to validate syntax."""

    paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class RunTests:
    """Run unittest discovery."""

    directory: Path
    pattern: str = "test*.py"
    verbose: bool = True


@dataclass(frozen=True, slots=True)
class GitDiffCheck:
    """Run Git whitespace validation."""


SprintAction = CreateFile | CompilePython | RunTests | GitDiffCheck
''',

    "tools/pdk/executor.py": '''"""Safe sprint execution with automatic rollback."""

from __future__ import annotations

import compileall
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .actions import (
    CompilePython,
    CreateFile,
    GitDiffCheck,
    RunTests,
    SprintAction,
)


class SprintExecutionError(RuntimeError):
    """Raised when a PDK sprint cannot be completed safely."""


@dataclass(slots=True)
class _FileBackup:
    path: Path
    existed: bool
    content: bytes | None


class SprintExecutor:
    """Execute a collection of typed sprint actions."""

    def __init__(self, root: Path | str = ".") -> None:
        self.root = Path(root).resolve()
        self._backups: list[_FileBackup] = []

    def execute(
        self,
        *,
        name: str,
        version: str,
        actions: tuple[SprintAction, ...],
    ) -> None:
        """Execute all actions and roll back file writes on failure."""

        print()
        print(f"Sprint {version}: {name}")
        print("=" * max(20, len(name) + len(version) + 10))

        try:
            total = len(actions)

            for index, action in enumerate(actions, start=1):
                print(
                    f"[{index}/{total}] "
                    f"{type(action).__name__}"
                )
                self._execute_action(action)

        except Exception as error:
            print()
            print("Sprint failed. Rolling back file changes...")
            self._rollback()

            if isinstance(error, SprintExecutionError):
                raise

            raise SprintExecutionError(str(error)) from error

        self._backups.clear()

        print()
        print("Sprint completed successfully.")

    def _execute_action(self, action: SprintAction) -> None:
        if isinstance(action, CreateFile):
            self._create_file(action)
            return

        if isinstance(action, CompilePython):
            self._compile_python(action)
            return

        if isinstance(action, RunTests):
            self._run_tests(action)
            return

        if isinstance(action, GitDiffCheck):
            self._git_diff_check()
            return

        raise SprintExecutionError(
            f"Unsupported sprint action: {type(action).__name__}"
        )

    def _create_file(self, action: CreateFile) -> None:
        path = self._resolve(action.path)

        if path.exists() and not action.overwrite:
            raise SprintExecutionError(
                f"File already exists and overwrite is disabled: "
                f"{action.path}"
            )

        self._backups.append(
            _FileBackup(
                path=path,
                existed=path.exists(),
                content=path.read_bytes() if path.exists() else None,
            )
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(action.content, encoding="utf-8", newline="\\n")

    def _compile_python(self, action: CompilePython) -> None:
        for relative_path in action.paths:
            path = self._resolve(relative_path)

            if not path.exists():
                raise SprintExecutionError(
                    f"Compile path does not exist: {relative_path}"
                )

            success = compileall.compile_dir(
                str(path),
                quiet=1,
                force=True,
            )

            if not success:
                raise SprintExecutionError(
                    f"Python compilation failed: {relative_path}"
                )

    def _run_tests(self, action: RunTests) -> None:
        directory = self._resolve(action.directory)

        if not directory.exists():
            raise SprintExecutionError(
                f"Test directory does not exist: {action.directory}"
            )

        command = [
            "python",
            "-m",
            "unittest",
            "discover",
            "-s",
            str(directory),
            "-p",
            action.pattern,
        ]

        if action.verbose:
            command.append("-v")

        self._run_command(command, "Project tests failed.")

    def _git_diff_check(self) -> None:
        self._run_command(
            ["git", "diff", "--check"],
            "Git whitespace validation failed.",
        )

    def _run_command(
        self,
        command: list[str],
        failure_message: str,
    ) -> None:
        result = subprocess.run(
            command,
            cwd=self.root,
            check=False,
        )

        if result.returncode != 0:
            raise SprintExecutionError(failure_message)

    def _resolve(self, relative_path: Path) -> Path:
        candidate = (self.root / relative_path).resolve()

        try:
            candidate.relative_to(self.root)
        except ValueError as error:
            raise SprintExecutionError(
                f"Path escapes the repository root: {relative_path}"
            ) from error

        return candidate

    def _rollback(self) -> None:
        for backup in reversed(self._backups):
            if backup.existed:
                if backup.content is None:
                    raise SprintExecutionError(
                        f"Missing backup data for {backup.path}"
                    )

                backup.path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                backup.path.write_bytes(backup.content)
            elif backup.path.exists():
                backup.path.unlink()

        self._backups.clear()
''',

    "tools/pdk/sprint.py": '''"""Fluent sprint-definition API."""

from __future__ import annotations

from pathlib import Path

from .actions import (
    CompilePython,
    CreateFile,
    GitDiffCheck,
    RunTests,
    SprintAction,
)
from .executor import SprintExecutor


class Sprint:
    """Build and execute a repeatable development sprint."""

    def __init__(
        self,
        *,
        version: str,
        name: str,
        root: Path | str = ".",
    ) -> None:
        self.version = self._required_text(version, "version")
        self.name = self._required_text(name, "name")
        self.root = Path(root)
        self._actions: list[SprintAction] = []

    def create_file(
        self,
        path: Path | str,
        content: str,
        *,
        overwrite: bool = False,
    ) -> Sprint:
        """Add a safe UTF-8 file-creation action."""

        self._actions.append(
            CreateFile(
                path=Path(path),
                content=content,
                overwrite=overwrite,
            )
        )
        return self

    def compile_python(
        self,
        *paths: Path | str,
    ) -> Sprint:
        """Add Python syntax validation."""

        if not paths:
            raise ValueError(
                "compile_python requires at least one path."
            )

        self._actions.append(
            CompilePython(
                paths=tuple(Path(path) for path in paths)
            )
        )
        return self

    def run_tests(
        self,
        directory: Path | str = "tests",
        *,
        pattern: str = "test*.py",
        verbose: bool = True,
    ) -> Sprint:
        """Add unittest discovery."""

        self._actions.append(
            RunTests(
                directory=Path(directory),
                pattern=self._required_text(
                    pattern,
                    "test pattern",
                ),
                verbose=verbose,
            )
        )
        return self

    def git_diff_check(self) -> Sprint:
        """Add Git whitespace validation."""

        self._actions.append(GitDiffCheck())
        return self

    def execute(self) -> None:
        """Execute the configured sprint."""

        if not self._actions:
            raise ValueError(
                "A sprint must contain at least one action."
            )

        SprintExecutor(self.root).execute(
            name=self.name,
            version=self.version,
            actions=tuple(self._actions),
        )

    @property
    def actions(self) -> tuple[SprintAction, ...]:
        """Return the immutable action sequence."""

        return tuple(self._actions)

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string.")

        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} cannot be empty.")

        return normalized
''',

    "tests/test_pdk.py": '''from __future__ import annotations

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
            .create_file("src/example.py", "VALUE = 1\\n")
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
                    "MESSAGE = \\"hello\\"\\n",
                )
                .execute()
            )

            created = root / "src" / "example.py"

            self.assertTrue(created.exists())
            self.assertEqual(
                created.read_text(encoding="utf-8"),
                "MESSAGE = \\"hello\\"\\n",
            )
            self.assertFalse(
                created.read_bytes().startswith(
                    b"\\xef\\xbb\\xbf"
                )
            )

    def test_existing_file_is_protected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "existing.py"
            path.write_text(
                "ORIGINAL = True\\n",
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
                    "CHANGED = True\\n",
                )
            )

            with self.assertRaises(SprintExecutionError):
                sprint.execute()

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "ORIGINAL = True\\n",
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
                .create_file("created.py", "VALUE = 1\\n")
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
                "ORIGINAL = True\\n",
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
                    "CHANGED = True\\n",
                    overwrite=True,
                )
                .compile_python("missing_directory")
            )

            with self.assertRaises(SprintExecutionError):
                sprint.execute()

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "ORIGINAL = True\\n",
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
                .create_file("../outside.py", "VALUE = 1\\n")
            )

            with self.assertRaises(SprintExecutionError):
                sprint.execute()


if __name__ == "__main__":
    unittest.main()
''',

    "examples/pdk_example.py": '''"""Minimal example of the Platform Development Kit."""

from tools.pdk import Sprint


def main() -> None:
    (
        Sprint(
            version="1.0.0",
            name="Example Sprint",
        )
        .create_file(
            "generated/example.py",
            "MESSAGE = \\"Generated by the PDK\\"\\n",
        )
        .compile_python("generated")
        .run_tests("tests")
        .git_diff_check()
        .execute()
    )


if __name__ == "__main__":
    main()
''',
}


def main() -> None:
    root = Path.cwd()

    for relative_path, content in FILES.items():
        path = root / relative_path

        if path.exists():
            raise RuntimeError(
                f"Refusing to overwrite existing file: {relative_path}"
            )

    for relative_path, content in FILES.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            content,
            encoding="utf-8",
            newline="\n",
        )
        print(f"Created {relative_path}")

    print()
    print("PDK bootstrap completed.")


if __name__ == "__main__":
    main()