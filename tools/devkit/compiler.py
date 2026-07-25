"""Python source compilation utilities."""

from __future__ import annotations

import py_compile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """Result returned by project compilation."""

    successful: bool
    compiled_files: tuple[Path, ...]
    errors: tuple[str, ...]


def discover_python_files(
    project_root: Path,
    source_directories: tuple[str, ...] = (
        "src",
        "tests",
        "tools",
    ),
) -> tuple[Path, ...]:
    """Discover Python files inside configured source directories."""

    files: list[Path] = []

    for directory_name in source_directories:
        directory = project_root / directory_name

        if not directory.exists():
            continue

        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue

            files.append(path)

    return tuple(files)


def compile_project(
    project_root: Path,
    source_directories: tuple[str, ...] = (
        "src",
        "tests",
        "tools",
    ),
) -> CompilationResult:
    """Compile all discovered Python source files."""

    compiled_files: list[Path] = []
    errors: list[str] = []

    for path in discover_python_files(
        project_root,
        source_directories,
    ):
        try:
            py_compile.compile(
                str(path),
                doraise=True,
            )

            compiled_files.append(path)

        except py_compile.PyCompileError as error:
            errors.append(
                f"{path}: {error.msg}"
            )

        except Exception as error:
            errors.append(
                f"{path}: {error}"
            )

    return CompilationResult(
        successful=not errors,
        compiled_files=tuple(compiled_files),
        errors=tuple(errors),
    )
