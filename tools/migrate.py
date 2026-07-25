"""Run automated project migrations and audits."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable


def discover_project_root() -> Path:
    """Find and validate the project root."""

    root = Path(__file__).resolve().parents[1]

    required = (
        root / "src",
        root / "tests",
    )

    missing = [
        path
        for path in required
        if not path.exists()
    ]

    if missing:
        formatted = ", ".join(
            str(path)
            for path in missing
        )

        raise RuntimeError(
            f"Project root validation failed. Missing: {formatted}"
        )

    return root


def validate_operation_name(name: str) -> str:
    """Validate an operation module name."""

    if not name:
        raise ValueError(
            "An operation name is required."
        )

    if not name.replace("_", "").isalnum():
        raise ValueError(
            "Operation names may contain only letters, "
            "numbers, and underscores."
        )

    return name


def load_operation(name: str) -> ModuleType:
    """Import an operation from tools.migrations."""

    validated_name = validate_operation_name(name)
    module_name = f"tools.migrations.{validated_name}"

    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise RuntimeError(
                f"Unknown migration or audit: {validated_name}"
            ) from exc

        raise


def operation_runner(
    module: ModuleType,
) -> Callable[[Path], int | None]:
    """Retrieve and validate an operation's run function."""

    run = getattr(module, "run", None)

    if not callable(run):
        raise RuntimeError(
            f"{module.__name__} does not define "
            "run(project_root)."
        )

    return run


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        prog="python -m tools.migrate",
        description=(
            "Polymarket Intelligence Platform "
            "migration and audit runner."
        ),
    )

    parser.add_argument(
        "operation",
        help=(
            "Operation module name, such as "
            "runtime_audit or runtime_v06."
        ),
    )

    return parser


def main() -> int:
    """Run the requested migration or audit."""

    parser = build_parser()
    arguments = parser.parse_args()

    try:
        project_root = discover_project_root()
        module = load_operation(arguments.operation)
        run = operation_runner(module)

        result = run(project_root)

        if result is None:
            return 0

        return int(result)

    except KeyboardInterrupt:
        print()
        print("Operation cancelled by user.")
        return 130

    except Exception as exc:
        print()
        print("OPERATION FAILED")
        print("----------------")
        print(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
