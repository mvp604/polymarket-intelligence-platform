"""Repository inventory and architecture audit utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        ".devkit_backups",
        "node_modules",
    }
)

CONFIGURATION_SUFFIXES = frozenset(
    {
        ".ini",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
    }
)

DOCUMENTATION_SUFFIXES = frozenset(
    {
        ".md",
        ".rst",
        ".txt",
    }
)

DATABASE_SUFFIXES = frozenset(
    {
        ".db",
        ".sqlite",
        ".sqlite3",
    }
)


@dataclass(frozen=True, slots=True)
class RepositoryAudit:
    """Immutable inventory of a project repository."""

    project_root: Path
    top_level_directories: tuple[Path, ...]
    python_files: tuple[Path, ...]
    source_files: tuple[Path, ...]
    test_files: tuple[Path, ...]
    configuration_files: tuple[Path, ...]
    documentation_files: tuple[Path, ...]
    database_files: tuple[Path, ...]
    other_files: tuple[Path, ...]

    @property
    def total_files(self) -> int:
        """Return the total number of inventoried files."""

        return (
            len(self.python_files)
            + len(self.configuration_files)
            + len(self.documentation_files)
            + len(self.database_files)
            + len(self.other_files)
        )

    @property
    def python_module_count(self) -> int:
        """Return the number of non-test Python files."""

        return len(self.source_files)

    @property
    def test_count(self) -> int:
        """Return the number of discovered Python test files."""

        return len(self.test_files)


def _is_excluded(
    path: Path,
    project_root: Path,
    excluded_directories: frozenset[str],
) -> bool:
    """Return whether a path belongs to an excluded directory."""

    try:
        relative_path = path.relative_to(project_root)
    except ValueError:
        return True

    return any(
        part in excluded_directories
        for part in relative_path.parts
    )


def _relative_paths(
    project_root: Path,
    paths: Iterable[Path],
) -> tuple[Path, ...]:
    """Convert paths to sorted repository-relative paths."""

    return tuple(
        sorted(
            path.relative_to(project_root)
            for path in paths
        )
    )


def _is_test_file(
    relative_path: Path,
) -> bool:
    """Return whether a Python path represents a test module."""

    filename = relative_path.name.lower()

    return (
        "tests" in relative_path.parts
        or filename.startswith("test_")
        or filename.endswith("_test.py")
    )


def audit_repository(
    project_root: Path,
    excluded_directories: frozenset[str] = (
        DEFAULT_EXCLUDED_DIRECTORIES
    ),
) -> RepositoryAudit:
    """Create a categorized inventory of a repository."""

    project_root = project_root.resolve()

    if not project_root.exists():
        raise FileNotFoundError(
            f"Project root does not exist: {project_root}"
        )

    if not project_root.is_dir():
        raise NotADirectoryError(
            f"Project root is not a directory: {project_root}"
        )

    top_level_directories = tuple(
        sorted(
            path.relative_to(project_root)
            for path in project_root.iterdir()
            if (
                path.is_dir()
                and path.name not in excluded_directories
            )
        )
    )

    python_files: list[Path] = []
    source_files: list[Path] = []
    test_files: list[Path] = []
    configuration_files: list[Path] = []
    documentation_files: list[Path] = []
    database_files: list[Path] = []
    other_files: list[Path] = []

    for path in project_root.rglob("*"):
        if not path.is_file():
            continue

        if _is_excluded(
            path,
            project_root,
            excluded_directories,
        ):
            continue

        relative_path = path.relative_to(project_root)
        suffix = path.suffix.lower()

        if suffix == ".py":
            python_files.append(path)

            if _is_test_file(relative_path):
                test_files.append(path)
            else:
                source_files.append(path)

        elif suffix in CONFIGURATION_SUFFIXES:
            configuration_files.append(path)

        elif suffix in DOCUMENTATION_SUFFIXES:
            documentation_files.append(path)

        elif suffix in DATABASE_SUFFIXES:
            database_files.append(path)

        else:
            other_files.append(path)

    return RepositoryAudit(
        project_root=project_root,
        top_level_directories=top_level_directories,
        python_files=_relative_paths(
            project_root,
            python_files,
        ),
        source_files=_relative_paths(
            project_root,
            source_files,
        ),
        test_files=_relative_paths(
            project_root,
            test_files,
        ),
        configuration_files=_relative_paths(
            project_root,
            configuration_files,
        ),
        documentation_files=_relative_paths(
            project_root,
            documentation_files,
        ),
        database_files=_relative_paths(
            project_root,
            database_files,
        ),
        other_files=_relative_paths(
            project_root,
            other_files,
        ),
    )


def format_audit_report(
    audit: RepositoryAudit,
) -> str:
    """Format a repository audit as readable plain text."""

    lines = [
        "POLYMARKET INTELLIGENCE PLATFORM",
        "REPOSITORY AUDIT",
        "=" * 64,
        f"Project root: {audit.project_root}",
        "",
        "SUMMARY",
        "-" * 64,
        f"Top-level directories: {len(audit.top_level_directories)}",
        f"Total inventoried files: {audit.total_files}",
        f"Python files: {len(audit.python_files)}",
        f"Production Python modules: {audit.python_module_count}",
        f"Python test modules: {audit.test_count}",
        f"Configuration files: {len(audit.configuration_files)}",
        f"Documentation files: {len(audit.documentation_files)}",
        f"Database files: {len(audit.database_files)}",
        f"Other files: {len(audit.other_files)}",
        "",
        "TOP-LEVEL DIRECTORIES",
        "-" * 64,
    ]

    if audit.top_level_directories:
        lines.extend(
            f"- {path}"
            for path in audit.top_level_directories
        )
    else:
        lines.append("- None")

    sections = (
        ("PRODUCTION PYTHON MODULES", audit.source_files),
        ("PYTHON TEST MODULES", audit.test_files),
        ("CONFIGURATION FILES", audit.configuration_files),
        ("DOCUMENTATION FILES", audit.documentation_files),
        ("DATABASE FILES", audit.database_files),
    )

    for title, paths in sections:
        lines.extend(
            [
                "",
                title,
                "-" * 64,
            ]
        )

        if paths:
            lines.extend(
                f"- {path}"
                for path in paths
            )
        else:
            lines.append("- None")

    return "\n".join(lines) + "\n"


def write_audit_report(
    audit: RepositoryAudit,
    output_path: Path,
) -> Path:
    """Write a repository audit report to disk."""

    output_path = output_path.resolve()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        format_audit_report(audit),
        encoding="utf-8",
        newline="\n",
    )

    return output_path