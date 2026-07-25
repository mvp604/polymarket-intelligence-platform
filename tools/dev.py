"""Main developer automation command.

Usage:

    python tools/dev.py validate
    python tools/dev.py compile
    python tools/dev.py test
    python tools/dev.py audit
    python tools/dev.py all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from tools.devkit.auditor import (
    audit_repository,
    format_audit_report,
    write_audit_report,
)
from tools.devkit.compiler import compile_project
from tools.devkit.reporter import print_header, print_result
from tools.devkit.tester import run_tests
from tools.devkit.validator import validate_project


def command_validate() -> int:
    """Validate the project structure."""

    print_header("PROJECT VALIDATION")

    result = validate_project(
        PROJECT_ROOT
    )

    if result.missing_paths:
        print("Missing required paths:")

        for path in result.missing_paths:
            print(f"  - {path}")

    if result.errors:
        print("Validation errors:")

        for error in result.errors:
            print(f"  - {error}")

    print_result(
        "Project validation",
        result.valid,
    )

    return 0 if result.valid else 1


def command_compile() -> int:
    """Compile project Python files."""

    print_header("PYTHON COMPILATION")

    result = compile_project(
        PROJECT_ROOT
    )

    print(
        f"Compiled files: "
        f"{len(result.compiled_files)}"
    )

    if result.errors:
        print("Compilation errors:")

        for error in result.errors:
            print(f"  - {error}")

    print_result(
        "Python compilation",
        result.successful,
    )

    return 0 if result.successful else 1


def command_test() -> int:
    """Run the complete project test suite."""

    print_header("PROJECT TEST SUITE")

    result = run_tests(
        PROJECT_ROOT
    )

    print_result(
        "Project tests",
        result.successful,
    )

    return result.exit_code


def command_audit() -> int:
    """Generate the repository architecture audit."""

    print_header("REPOSITORY AUDIT")

    try:
        audit = audit_repository(
            PROJECT_ROOT
        )

        output_path = (
            PROJECT_ROOT
            / "reports"
            / "repository_audit.txt"
        )

        written_path = write_audit_report(
            audit,
            output_path,
        )

    except Exception as error:
        print(
            f"Repository audit failed: {error}"
        )

        print_result(
            "Repository audit",
            False,
        )

        return 1

    print(
        format_audit_report(audit)
    )

    print(
        f"Audit report written to: "
        f"{written_path.relative_to(PROJECT_ROOT)}"
    )

    print_result(
        "Repository audit",
        True,
    )

    return 0


def command_all() -> int:
    """Run validation, compilation, and tests."""

    commands = (
        command_validate,
        command_compile,
        command_test,
    )

    for command in commands:
        exit_code = command()

        if exit_code != 0:
            print_header("DEVELOPMENT CHECKS FAILED")
            return exit_code

    print_header("ALL DEVELOPMENT CHECKS PASSED")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Polymarket Intelligence Platform "
            "Developer Kit"
        )
    )

    parser.add_argument(
        "command",
        choices=(
            "validate",
            "compile",
            "test",
            "audit",
            "all",
        ),
        help="Developer operation to run.",
    )

    return parser


def main() -> int:
    """Execute the requested developer command."""

    parser = build_parser()
    arguments = parser.parse_args()

    commands = {
        "validate": command_validate,
        "compile": command_compile,
        "test": command_test,
        "audit": command_audit,
        "all": command_all,
    }

    return commands[arguments.command]()


if __name__ == "__main__":
    raise SystemExit(
        main()
    )