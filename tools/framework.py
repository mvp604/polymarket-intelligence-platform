"""Reusable migration framework services."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Result returned by a child process."""

    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0


class MigrationError(RuntimeError):
    """Raised when an automated migration cannot safely continue."""


class MigrationSession:
    """
    Manage backups, writes, validation, and rollback for one operation.
    """

    def __init__(
        self,
        project_root: Path,
        operation_name: str,
    ) -> None:
        self.project_root = project_root.resolve()
        self.operation_name = operation_name

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.backup_directory = (
            self.project_root
            / "backups"
            / f"{operation_name}_{timestamp}"
        )

        self.report_directory = (
            self.project_root
            / "reports"
            / operation_name
        )

        self.backup_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.report_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._tracked_paths: list[Path] = []
        self._originally_missing: set[Path] = set()
        self._committed = False

    def resolve(self, relative_path: str | Path) -> Path:
        """Resolve and validate a project-relative path."""

        path = (self.project_root / relative_path).resolve()

        try:
            path.relative_to(self.project_root)
        except ValueError as exc:
            raise MigrationError(
                f"Path escapes the project root: {relative_path}"
            ) from exc

        return path

    def require_paths(
        self,
        relative_paths: Iterable[str | Path],
    ) -> None:
        """Require paths before beginning an operation."""

        missing: list[str] = []

        for relative_path in relative_paths:
            path = self.resolve(relative_path)

            if not path.exists():
                missing.append(str(relative_path))

        if missing:
            formatted = "\n".join(
                f"  - {path}"
                for path in missing
            )

            raise MigrationError(
                "Required project paths are missing:\n"
                f"{formatted}"
            )

    def backup(self, relative_path: str | Path) -> Path:
        """Back up a file before modifying it."""

        source = self.resolve(relative_path)
        relative = source.relative_to(self.project_root)
        destination = self.backup_directory / relative

        if source in self._tracked_paths:
            return destination

        self._tracked_paths.append(source)

        if not source.exists():
            self._originally_missing.add(source)
            return destination

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if source.is_dir():
            shutil.copytree(
                source,
                destination,
                dirs_exist_ok=True,
            )
        else:
            shutil.copy2(
                source,
                destination,
            )

        return destination

    def write_text(
        self,
        relative_path: str | Path,
        content: str,
    ) -> Path:
        """Back up and write a UTF-8 text file."""

        path = self.resolve(relative_path)
        self.backup(relative_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        normalized = content.rstrip() + "\n"

        path.write_text(
            normalized,
            encoding="utf-8",
        )

        return path

    def read_text(
        self,
        relative_path: str | Path,
    ) -> str:
        """Read a UTF-8 source file while tolerating a BOM."""

        path = self.resolve(relative_path)

        return path.read_text(
            encoding="utf-8-sig",
        )

    def run_command(
        self,
        command: Sequence[str],
    ) -> CommandResult:
        """Run a child command from the project root."""

        completed = subprocess.run(
            list(command),
            cwd=self.project_root,
            text=True,
            capture_output=True,
            check=False,
        )

        return CommandResult(
            command=tuple(command),
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def run_python(
        self,
        *arguments: str,
    ) -> CommandResult:
        """Run the active Python interpreter."""

        return self.run_command(
            [sys.executable, *arguments]
        )

    def save_report(
        self,
        filename: str,
        lines: Iterable[str],
    ) -> Path:
        """Save an operation report."""

        path = self.report_directory / filename

        path.write_text(
            "\n".join(lines).rstrip() + "\n",
            encoding="utf-8",
        )

        return path

    def commit(self) -> None:
        """Mark the migration as successful."""

        self._committed = True

    def rollback(self) -> None:
        """Restore every tracked file to its original state."""

        for target in reversed(self._tracked_paths):
            relative = target.relative_to(self.project_root)
            backup = self.backup_directory / relative

            if target in self._originally_missing:
                if target.is_dir():
                    shutil.rmtree(
                        target,
                        ignore_errors=True,
                    )
                elif target.exists():
                    target.unlink()

                continue

            if not backup.exists():
                continue

            if backup.is_dir():
                if target.exists():
                    shutil.rmtree(
                        target,
                        ignore_errors=True,
                    )

                shutil.copytree(
                    backup,
                    target,
                )
            else:
                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(
                    backup,
                    target,
                )

    def __enter__(self) -> MigrationSession:
        return self

    def __exit__(
        self,
        exception_type,
        exception,
        traceback,
    ) -> bool:
        if exception_type is not None or not self._committed:
            self.rollback()

        return False
