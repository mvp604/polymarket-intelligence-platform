"""Developer CLI for automated project workflows."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from tools.pdk.sprint_builder import (
    SprintAlreadyExistsError,
    SprintBuilder,
    SprintBuilderError,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Create, install, and validate "
            "Polymarket Intelligence Platform sprints."
        )
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    create_parser = commands.add_parser(
        "create",
        help="Create a new sprint package.",
    )

    create_parser.add_argument(
        "component_type",
        choices=("runtime",),
        help="Type of component to generate.",
    )

    create_parser.add_argument(
        "module_name",
        help="Module name, such as scheduler.",
    )

    create_parser.add_argument(
        "--version",
        required=True,
        help="Semantic version, such as 0.13.0.",
    )

    create_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing generated sprint.",
    )

    install_parser = commands.add_parser(
        "install",
        help="Install a sprint transactionally.",
    )

    install_parser.add_argument(
        "manifest",
        type=Path,
        help="Path to the sprint manifest.",
    )

    commands.add_parser(
        "validate",
        help="Compile and test the repository.",
    )

    return parser


def create_runtime_sprint(
    repository_root: Path,
    module_name: str,
    version: str,
    overwrite: bool,
) -> int:
    """Create a runtime sprint package."""

    builder = SprintBuilder(repository_root)

    try:
        paths = builder.create_runtime_module(
            module_name,
            version=version,
            overwrite=overwrite,
        )

    except (
        SprintAlreadyExistsError,
        SprintBuilderError,
        TypeError,
        ValueError,
    ) as error:
        print(
            f"Sprint creation failed: {error}",
            file=sys.stderr,
        )

        return 1

    print("")
    print("Sprint created successfully:")
    print(f"  Root:     {paths.root}")
    print(f"  Manifest: {paths.manifest}")
    print(f"  Source:   {paths.source}")
    print(f"  Test:     {paths.test}")
    print(f"  README:   {paths.readme}")
    print("")
    print(
        "Review the generated implementation "
        "before installation."
    )

    return 0


def install_sprint(
    repository_root: Path,
    manifest: Path,
) -> int:
    """Install a sprint through the existing Sprint Runner."""

    resolved_manifest = manifest

    if not resolved_manifest.is_absolute():
        resolved_manifest = (
            repository_root
            / resolved_manifest
        )

    resolved_manifest = resolved_manifest.resolve()

    if not resolved_manifest.is_file():
        print(
            "Manifest does not exist: "
            f"{resolved_manifest}",
            file=sys.stderr,
        )

        return 1

    command = (
        sys.executable,
        "-m",
        "tools.pdk.sprint_runner",
        str(resolved_manifest),
    )

    print("")
    print(
        "Running transactional installation:"
    )

    print(
        "  "
        + " ".join(command)
    )

    completed = subprocess.run(
        command,
        cwd=repository_root,
        check=False,
    )

    if completed.returncode != 0:
        print(
            "",
            file=sys.stderr,
        )

        print(
            "Sprint installation failed.",
            file=sys.stderr,
        )

        print(
            "The Sprint Runner should have "
            "rolled back changed files.",
            file=sys.stderr,
        )

        return completed.returncode

    print("")
    print("Sprint installation completed.")

    return 0


def validate_repository(
    repository_root: Path,
) -> int:
    """Compile the repository and run all tests."""

    builder = SprintBuilder(repository_root)

    for command in builder.validation_commands():
        print("")
        print(
            "Running: "
            + " ".join(command)
        )

        completed = subprocess.run(
            command,
            cwd=repository_root,
            check=False,
        )

        if completed.returncode != 0:
            print(
                "",
                file=sys.stderr,
            )

            print(
                "Repository validation failed.",
                file=sys.stderr,
            )

            return completed.returncode

    print("")
    print("Repository validation passed.")

    return 0


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Run the developer command-line interface."""

    arguments = build_parser().parse_args(
        argv
    )

    repository_root = Path.cwd().resolve()

    if arguments.command == "create":
        return create_runtime_sprint(
            repository_root,
            arguments.module_name,
            arguments.version,
            arguments.overwrite,
        )

    if arguments.command == "install":
        return install_sprint(
            repository_root,
            arguments.manifest,
        )

    if arguments.command == "validate":
        return validate_repository(
            repository_root
        )

    print(
        f"Unsupported command: {arguments.command}",
        file=sys.stderr,
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())