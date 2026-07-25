"""Bootstrap the Polymarket Intelligence Platform Developer Kit.

Run this file from the project root:

    python bootstrap_devkit.py

This script will:

1. Verify the project root.
2. Create the Developer Kit folders.
3. Back up existing files before overwriting them.
4. Create tools/dev.py.
5. Create supporting Developer Kit modules.
6. Create unit tests.
7. Compile the generated files.
8. Run Developer Kit tests.
9. Run the complete project test suite.

After installation, use:

    python tools/dev.py validate
    python tools/dev.py compile
    python tools/dev.py test
    python tools/dev.py all
"""

from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

TOOLS_DIR = PROJECT_ROOT / "tools"
DEVKIT_DIR = TOOLS_DIR / "devkit"
TESTS_DIR = PROJECT_ROOT / "tests"
DEVKIT_TESTS_DIR = TESTS_DIR / "devkit"

BACKUP_ROOT = (
    PROJECT_ROOT
    / ".devkit_backups"
    / datetime.now().strftime("%Y%m%d_%H%M%S")
)


GENERATED_FILES: dict[str, str] = {
    "tools/__init__.py": '''"""Project development and automation tools."""
''',

    "tools/devkit/__init__.py": '''"""Developer Kit for the Polymarket Intelligence Platform."""

from tools.devkit.backup import backup_files
from tools.devkit.compiler import CompilationResult, compile_project
from tools.devkit.reporter import print_header, print_result
from tools.devkit.tester import TestResult, run_tests
from tools.devkit.validator import ValidationResult, validate_project

__all__ = [
    "CompilationResult",
    "TestResult",
    "ValidationResult",
    "backup_files",
    "compile_project",
    "print_header",
    "print_result",
    "run_tests",
    "validate_project",
]
''',

    "tools/devkit/backup.py": '''"""Backup utilities for automated project changes."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def backup_files(
    project_root: Path,
    paths: list[Path],
) -> Path | None:
    """Back up existing files while preserving project-relative paths."""

    existing_paths = [
        path
        for path in paths
        if path.exists() and path.is_file()
    ]

    if not existing_paths:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_root = (
        project_root
        / ".devkit_backups"
        / timestamp
    )

    backup_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    for source in existing_paths:
        relative_path = source.resolve().relative_to(
            project_root.resolve()
        )

        destination = backup_root / relative_path

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

    return backup_root
''',

    "tools/devkit/validator.py": '''"""Project structure and environment validation."""

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
''',

    "tools/devkit/compiler.py": '''"""Python source compilation utilities."""

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
''',

    "tools/devkit/tester.py": '''"""Automated test execution utilities."""

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
''',

    "tools/devkit/reporter.py": '''"""Console reporting utilities."""

from __future__ import annotations


LINE_WIDTH = 64


def print_header(title: str) -> None:
    """Print a consistent command section header."""

    print()
    print("=" * LINE_WIDTH)
    print(title)
    print("=" * LINE_WIDTH)


def print_result(
    label: str,
    successful: bool,
) -> None:
    """Print a standardized success or failure result."""

    status = "PASSED" if successful else "FAILED"
    print(f"{label}: {status}")
''',

    "tools/dev.py": '''"""Main developer automation command.

Usage:

    python tools/dev.py validate
    python tools/dev.py compile
    python tools/dev.py test
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
        "all": command_all,
    }

    return commands[arguments.command]()


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
''',

    "tests/devkit/__init__.py": '''"""Tests for the internal Developer Kit."""
''',

    "tests/devkit/test_validator.py": '''"""Tests for project validation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.devkit.validator import validate_project


class ValidationTests(unittest.TestCase):
    def test_valid_project_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            for folder_name in (
                "src",
                "tests",
                "tools",
            ):
                (
                    project_root
                    / folder_name
                ).mkdir()

            result = validate_project(
                project_root
            )

            self.assertTrue(result.valid)
            self.assertEqual(
                result.missing_paths,
                (),
            )
            self.assertEqual(
                result.errors,
                (),
            )

    def test_missing_directories_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            (
                project_root
                / "src"
            ).mkdir()

            result = validate_project(
                project_root
            )

            self.assertFalse(result.valid)

            self.assertIn(
                Path("tests"),
                result.missing_paths,
            )

            self.assertIn(
                Path("tools"),
                result.missing_paths,
            )


if __name__ == "__main__":
    unittest.main()
''',

    "tests/devkit/test_compiler.py": '''"""Tests for project compilation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.devkit.compiler import (
    compile_project,
    discover_python_files,
)


class CompilerTests(unittest.TestCase):
    def test_python_files_are_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            source_directory = project_root / "src"
            source_directory.mkdir()

            source_file = source_directory / "sample.py"

            source_file.write_text(
                "VALUE = 1\\n",
                encoding="utf-8",
            )

            files = discover_python_files(
                project_root
            )

            self.assertEqual(
                files,
                (source_file,),
            )

    def test_valid_python_file_compiles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            source_directory = project_root / "src"
            source_directory.mkdir()

            source_file = source_directory / "sample.py"

            source_file.write_text(
                "VALUE = 1\\n",
                encoding="utf-8",
            )

            result = compile_project(
                project_root
            )

            self.assertTrue(
                result.successful
            )

            self.assertIn(
                source_file,
                result.compiled_files,
            )

            self.assertEqual(
                result.errors,
                (),
            )

    def test_invalid_python_file_fails_compilation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            source_directory = project_root / "src"
            source_directory.mkdir()

            source_file = source_directory / "broken.py"

            source_file.write_text(
                "def broken(:\\n",
                encoding="utf-8",
            )

            result = compile_project(
                project_root
            )

            self.assertFalse(
                result.successful
            )

            self.assertTrue(
                result.errors
            )


if __name__ == "__main__":
    unittest.main()
''',

    "tests/devkit/test_backup.py": '''"""Tests for project backup utilities."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.devkit.backup import backup_files


class BackupTests(unittest.TestCase):
    def test_existing_file_is_backed_up(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            source_file = (
                project_root
                / "tools"
                / "sample.py"
            )

            source_file.parent.mkdir(
                parents=True
            )

            source_file.write_text(
                "VALUE = 1\\n",
                encoding="utf-8",
            )

            backup_root = backup_files(
                project_root,
                [source_file],
            )

            self.assertIsNotNone(
                backup_root
            )

            assert backup_root is not None

            backup_file = (
                backup_root
                / "tools"
                / "sample.py"
            )

            self.assertTrue(
                backup_file.exists()
            )

            self.assertEqual(
                backup_file.read_text(
                    encoding="utf-8"
                ),
                "VALUE = 1\\n",
            )

    def test_no_backup_for_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            backup_root = backup_files(
                project_root,
                [
                    project_root
                    / "missing.py"
                ],
            )

            self.assertIsNone(
                backup_root
            )


if __name__ == "__main__":
    unittest.main()
''',
}


def print_header(title: str) -> None:
    """Print a visible bootstrap section header."""

    print()
    print("=" * 68)
    print(title)
    print("=" * 68)


def validate_bootstrap_location() -> None:
    """Confirm the script is running from the project root."""

    if not (PROJECT_ROOT / "src").exists():
        raise RuntimeError(
            "The src folder was not found. "
            "Place bootstrap_devkit.py in the main project folder."
        )

    if not (PROJECT_ROOT / "tests").exists():
        raise RuntimeError(
            "The tests folder was not found. "
            "Place bootstrap_devkit.py in the main project folder."
        )


def get_destination_paths() -> list[Path]:
    """Return all files that will be generated."""

    return [
        PROJECT_ROOT / relative_path
        for relative_path in GENERATED_FILES
    ]


def create_backup() -> Path | None:
    """Back up existing generated files."""

    existing_files = [
        path
        for path in get_destination_paths()
        if path.exists() and path.is_file()
    ]

    if not existing_files:
        return None

    BACKUP_ROOT.mkdir(
        parents=True,
        exist_ok=False,
    )

    for source in existing_files:
        relative_path = source.relative_to(
            PROJECT_ROOT
        )

        destination = (
            BACKUP_ROOT
            / relative_path
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

    return BACKUP_ROOT


def write_generated_files() -> None:
    """Create the Developer Kit files."""

    for relative_path, content in GENERATED_FILES.items():
        destination = (
            PROJECT_ROOT
            / relative_path
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination.write_text(
            content.rstrip() + "\n",
            encoding="utf-8",
            newline="\n",
        )

        print(
            f"Created: {relative_path}"
        )


def compile_generated_files() -> None:
    """Compile all generated Python files."""

    for relative_path in GENERATED_FILES:
        if not relative_path.endswith(".py"):
            continue

        path = PROJECT_ROOT / relative_path

        py_compile.compile(
            str(path),
            doraise=True,
        )

        print(
            f"Compiled: {relative_path}"
        )


def run_command(
    command: list[str],
    description: str,
) -> None:
    """Run a command and raise an error if it fails."""

    print_header(description)

    print(
        "Command:"
    )

    print(
        "  " + " ".join(command)
    )

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"{description} failed with "
            f"exit code {completed.returncode}."
        )


def main() -> int:
    """Install and verify the Developer Kit."""

    print_header(
        "POLYMARKET INTELLIGENCE PLATFORM "
        "DEVELOPER KIT BOOTSTRAP"
    )

    print(
        f"Project root: {PROJECT_ROOT}"
    )

    try:
        validate_bootstrap_location()

        print_header(
            "BACKING UP EXISTING FILES"
        )

        backup_path = create_backup()

        if backup_path is None:
            print(
                "No existing Developer Kit files required backup."
            )
        else:
            print(
                f"Backup created: {backup_path}"
            )

        print_header(
            "CREATING DEVELOPER KIT"
        )

        write_generated_files()

        print_header(
            "COMPILING GENERATED FILES"
        )

        compile_generated_files()

        run_command(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests/devkit",
                "-p",
                "test*.py",
                "-v",
            ],
            "RUNNING DEVELOPER KIT TESTS",
        )

        run_command(
            [
                sys.executable,
                "tools/dev.py",
                "all",
            ],
            "RUNNING COMPLETE DEVELOPMENT PIPELINE",
        )

    except Exception as error:
        print_header(
            "BOOTSTRAP FAILED"
        )

        print(
            str(error)
        )

        return 1

    print_header(
        "DEVELOPER KIT INSTALLED SUCCESSFULLY"
    )

    print(
        "Permanent development commands:"
    )

    print()
    print(
        "  python tools/dev.py validate"
    )
    print(
        "  python tools/dev.py compile"
    )
    print(
        "  python tools/dev.py test"
    )
    print(
        "  python tools/dev.py all"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )