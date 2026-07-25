"""Safe sprint execution with automatic rollback."""

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
        path.write_text(action.content, encoding="utf-8", newline="\n")

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
