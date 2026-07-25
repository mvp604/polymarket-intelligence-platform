"""Automated test execution utilities."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TestResult:
    """Result returned by a test process."""

    successful: bool
    exit_code: int
    command: tuple[str, ...]


def run_command(
    project_root: Path,
    command: list[str],
) -> TestResult:
    """Run a command from the project root."""

    completed = subprocess.run(
        command,
        cwd=project_root,
        check=False,
    )

    return TestResult(
        successful=completed.returncode == 0,
        exit_code=completed.returncode,
        command=tuple(command),
    )


def run_tests(
    project_root: Path,
    start_directory: str = "tests",
    pattern: str = "test*.py",
) -> TestResult:
    """Run the complete unittest discovery suite."""

    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        start_directory,
        "-p",
        pattern,
        "-v",
    ]

    return run_command(
        project_root,
        command,
    )


def run_test_module(
    project_root: Path,
    module_name: str,
) -> TestResult:
    """Run a specific unittest module."""

    command = [
        sys.executable,
        "-m",
        "unittest",
        module_name,
        "-v",
    ]

    return run_command(
        project_root,
        command,
    )
