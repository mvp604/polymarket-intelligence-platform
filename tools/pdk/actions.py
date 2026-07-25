"""Typed actions supported by the Platform Development Kit."""

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
