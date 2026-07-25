"""Project structure and environment validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result returned by project validation."""

    valid: bool
    checked_paths: tuple[Path, ...]
    missing_paths: tuple[Path, ...]
    errors: tuple[str, ...]


DEFAULT_REQUIRED_PATHS = (
    Path("src"),
    Path("tests"),
    Path("tools"),
)


def validate_project(
    project_root: Path,
    required_paths: tuple[Path, ...] = DEFAULT_REQUIRED_PATHS,
) -> ValidationResult:
    """Validate the expected project structure."""

    checked_paths = tuple(
        project_root / path
        for path in required_paths
    )

    missing_paths = tuple(
        path
        for path in required_paths
        if not (project_root / path).exists()
    )

    errors: list[str] = []

    if not project_root.exists():
        errors.append(
            f"Project root does not exist: {project_root}"
        )

    if not project_root.is_dir():
        errors.append(
            f"Project root is not a directory: {project_root}"
        )

    for relative_path in required_paths:
        absolute_path = project_root / relative_path

        if absolute_path.exists() and not absolute_path.is_dir():
            errors.append(
                f"Expected directory but found file: {relative_path}"
            )

    valid = not missing_paths and not errors

    return ValidationResult(
        valid=valid,
        checked_paths=checked_paths,
        missing_paths=missing_paths,
        errors=tuple(errors),
    )
