"""Fluent sprint-definition API."""

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
