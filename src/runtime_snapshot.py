#!/usr/bin/env python3
"""
Polymarket Intelligence Platform Runtime Snapshot Exporter.

Run from the project root:

    python runtime_snapshot.py

This script does not modify src/, tests/, or tools/.
"""

from __future__ import annotations

import compileall
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import traceback
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


REQUESTED_FILES: tuple[str, ...] = (
    "src/runtime/__init__.py",
    "src/runtime/context.py",
    "src/runtime/dependency_graph.py",
    "src/runtime/engine.py",
    "src/runtime/planner.py",
    "src/runtime/registry.py",
    "src/runtime/runner.py",
    "src/runtime/state.py",

    "tests/runtime/__init__.py",
    "tests/runtime/test_context.py",
    "tests/runtime/test_dependency_graph.py",
    "tests/runtime/test_engine.py",
    "tests/runtime/test_planner.py",
    "tests/runtime/test_registry.py",
    "tests/runtime/test_runner.py",
    "tests/runtime/test_state.py",

    "tools/__init__.py",
    "tools/framework.py",
    "tools/migrate.py",
    "tools/migrations/__init__.py",
    "tools/migrations/runtime_audit.py",
)


SCAN_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "PlatformContext",
        r"\bPlatformContext\b",
    ),
    (
        "RuntimeContext",
        r"\bRuntimeContext\b",
    ),
    (
        "execute method definitions",
        r"\bdef\s+execute\s*\(",
    ),
    (
        "execute method calls",
        r"\.execute\s*\(",
    ),
    (
        "run method definitions",
        r"\bdef\s+run\s*\(",
    ),
    (
        "run method calls",
        r"\.run\s*\(",
    ),
    (
        "set_shared",
        r"\bset_shared\b",
    ),
    (
        "get_shared",
        r"\bget_shared\b",
    ),
)


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: list[str]
    return_code: int
    stdout: str
    stderr: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp() -> str:
    return datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


def section(title: str) -> str:
    bar = "=" * 78

    return (
        f"{bar}\n"
        f"{title}\n"
        f"{bar}\n"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest().upper()


def run_command(
    name: str,
    command: Sequence[str],
    cwd: Path,
) -> CommandResult:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

        return CommandResult(
            name=name,
            command=list(command),
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    except Exception as error:
        return CommandResult(
            name=name,
            command=list(command),
            return_code=-1,
            stdout="",
            stderr=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )


def format_command_result(
    result: CommandResult,
) -> str:
    command_text = " ".join(
        result.command
    )

    return "\n".join(
        [
            section(
                f"COMMAND: {result.name}"
            ),
            f"Invocation: {command_text}",
            "",
            "STDOUT:",
            (
                result.stdout.rstrip()
                or "<no stdout>"
            ),
            "",
            "STDERR:",
            (
                result.stderr.rstrip()
                or "<no stderr>"
            ),
            "",
            (
                "Exit code: "
                f"{result.return_code}"
            ),
            "",
        ]
    )


def validate_project_root(
    project_root: Path,
) -> None:
    runtime_directory = (
        project_root
        / "src"
        / "runtime"
    )

    if not runtime_directory.is_dir():
        raise RuntimeError(
            "src/runtime was not found.\n\n"
            "Run this script from:\n"
            "C:\\Users\\mitch\\OneDrive\\Desktop\\"
            "Polymarket Intelligence Platform"
        )


def copy_requested_files(
    project_root: Path,
    snapshot_root: Path,
) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    missing: list[str] = []

    for relative_path in REQUESTED_FILES:
        source_path = (
            project_root
            / relative_path
        )

        destination_path = (
            snapshot_root
            / relative_path
        )

        if source_path.is_file():
            destination_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                source_path,
                destination_path,
            )

            copied.append(
                relative_path
            )

            print(
                f"[COPIED]  {relative_path}"
            )

        else:
            missing.append(
                relative_path
            )

            print(
                f"[MISSING] {relative_path}"
            )

    return copied, missing


def collect_git_metadata(
    project_root: Path,
) -> dict[str, object]:
    commands = {
        "branch": [
            "git",
            "branch",
            "--show-current",
        ],
        "head": [
            "git",
            "rev-parse",
            "HEAD",
        ],
        "status": [
            "git",
            "status",
            "--short",
        ],
    }

    metadata: dict[str, object] = {}

    for key, command in commands.items():
        result = run_command(
            name=f"git {key}",
            command=command,
            cwd=project_root,
        )

        if result.return_code == 0:
            metadata[key] = (
                result.stdout.strip()
            )
        else:
            metadata[key] = (
                "Unavailable"
            )

    return metadata


def collect_environment_metadata(
    project_root: Path,
    copied_files: list[str],
    missing_files: list[str],
) -> dict[str, object]:
    return {
        "generated_at_utc": (
            utc_now_iso()
        ),
        "project_root": str(
            project_root
        ),
        "python_version": (
            sys.version
        ),
        "python_executable": (
            sys.executable
        ),
        "platform": (
            platform.platform()
        ),
        "machine": (
            platform.machine()
        ),
        "processor": (
            platform.processor()
        ),
        "working_directory": (
            os.getcwd()
        ),
        "copied_files": (
            copied_files
        ),
        "missing_files": (
            missing_files
        ),
        "git": collect_git_metadata(
            project_root
        ),
    }


def compile_runtime(
    project_root: Path,
) -> tuple[bool, str]:
    report: list[str] = [
        section(
            "PYTHON COMPILATION"
        )
    ]

    targets = (
        project_root
        / "src"
        / "runtime",

        project_root
        / "tests"
        / "runtime",
    )

    success = True

    for target in targets:
        relative_target = (
            target.relative_to(
                project_root
            )
        )

        if not target.exists():
            report.append(
                f"[MISSING] {relative_target}"
            )

            success = False
            continue

        target_passed = (
            compileall.compile_dir(
                str(target),
                quiet=1,
                force=True,
            )
        )

        status = (
            "PASS"
            if target_passed
            else "FAIL"
        )

        report.append(
            f"[{status}] {relative_target}"
        )

        success = (
            success
            and target_passed
        )

    report.append("")

    return (
        success,
        "\n".join(report),
    )


def scan_python_files(
    project_root: Path,
) -> str:
    report: list[str] = [
        section(
            "LEGACY RUNTIME API SCAN"
        )
    ]

    scan_roots = (
        project_root
        / "src"
        / "runtime",

        project_root
        / "tests"
        / "runtime",
    )

    python_files: list[Path] = []

    for scan_root in scan_roots:
        if scan_root.exists():
            python_files.extend(
                sorted(
                    scan_root.rglob(
                        "*.py"
                    )
                )
            )

    for label, raw_pattern in SCAN_PATTERNS:
        pattern = re.compile(
            raw_pattern
        )

        report.append(
            f"Pattern: {label}"
        )

        report.append(
            f"Regex:   {raw_pattern}"
        )

        report.append(
            "-" * 78
        )

        match_count = 0

        for path in python_files:
            lines = path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()

            for line_number, line in enumerate(
                lines,
                start=1,
            ):
                if not pattern.search(line):
                    continue

                relative_path = (
                    path.relative_to(
                        project_root
                    )
                )

                report.append(
                    f"{relative_path}:"
                    f"{line_number}: "
                    f"{line.strip()}"
                )

                match_count += 1

        if match_count == 0:
            report.append(
                "No matches."
            )

        report.append("")

    return "\n".join(report)


def file_hash_report(
    project_root: Path,
    copied_files: Iterable[str],
) -> str:
    report: list[str] = [
        section(
            "RUNTIME FILE HASHES"
        )
    ]

    for relative_path in copied_files:
        source_path = (
            project_root
            / relative_path
        )

        if not source_path.is_file():
            continue

        report.append(
            f"{relative_path} = "
            f"{sha256_file(source_path)}"
        )

    report.append("")

    return "\n".join(report)


def write_zip(
    source_root: Path,
    archive_path: Path,
) -> None:
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=(
            zipfile.ZIP_DEFLATED
        ),
        compresslevel=9,
    ) as archive:
        for path in sorted(
            source_root.rglob("*")
        ):
            if not path.is_file():
                continue

            archive.write(
                path,
                arcname=(
                    path.relative_to(
                        source_root
                    )
                ),
            )


def main() -> int:
    print()
    print("=" * 78)
    print(
        "Polymarket Runtime "
        "Snapshot Exporter"
    )
    print("=" * 78)
    print()

    project_root = (
        Path.cwd().resolve()
    )

    validate_project_root(
        project_root
    )

    artifacts_directory = (
        project_root
        / "artifacts"
    )

    artifacts_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_timestamp = timestamp()

    snapshot_root = (
        artifacts_directory
        / (
            "runtime_snapshot_"
            f"{run_timestamp}"
        )
    )

    archive_path = (
        artifacts_directory
        / (
            "runtime_snapshot_"
            f"{run_timestamp}.zip"
        )
    )

    archive_hash_path = (
        artifacts_directory
        / (
            "runtime_snapshot_"
            f"{run_timestamp}"
            ".zip.sha256.txt"
        )
    )

    snapshot_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    print(
        f"[OK] Project root: "
        f"{project_root}"
    )

    print(
        f"[OK] Snapshot folder: "
        f"{snapshot_root}"
    )

    print()

    copied_files, missing_files = (
        copy_requested_files(
            project_root=project_root,
            snapshot_root=snapshot_root,
        )
    )

    metadata = (
        collect_environment_metadata(
            project_root=project_root,
            copied_files=copied_files,
            missing_files=missing_files,
        )
    )

    metadata_path = (
        snapshot_root
        / "snapshot_metadata.json"
    )

    metadata_path.write_text(
        (
            json.dumps(
                metadata,
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        ),
        encoding="utf-8",
    )

    report_parts: list[str] = [
        section(
            "POLYMARKET RUNTIME "
            "SNAPSHOT VALIDATION"
        ),
        (
            f"Generated: "
            f"{utc_now_iso()}\n"
        ),
        (
            f"Project: "
            f"{project_root}\n\n"
        ),
    ]

    compilation_passed, compilation_report = (
        compile_runtime(
            project_root
        )
    )

    report_parts.append(
        compilation_report
    )

    import_validation_code = (
        "import src.runtime; "
        "print('src.runtime import passed'); "
        "print("
        "'Runtime module:', "
        "src.runtime.__file__"
        "); "
        "print("
        "'Runtime exports:', "
        "sorted("
        "name "
        "for name in dir(src.runtime) "
        "if not name.startswith('_')"
        ")"
        ")"
    )

    commands: tuple[
        tuple[str, list[str]],
        ...,
    ] = (
        (
            "Python version",
            [
                sys.executable,
                "--version",
            ],
        ),
        (
            "Import src.runtime",
            [
                sys.executable,
                "-c",
                import_validation_code,
            ],
        ),
        (
            "Runtime unit tests",
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests/runtime",
                "-p",
                "test_*.py",
                "-v",
            ],
        ),
    )

    command_results: list[
        CommandResult
    ] = []

    for name, command in commands:
        print(
            f"[RUN] {name}"
        )

        result = run_command(
            name=name,
            command=command,
            cwd=project_root,
        )

        command_results.append(
            result
        )

        report_parts.append(
            format_command_result(
                result
            )
        )

        status = (
            "OK"
            if result.return_code == 0
            else "DIAGNOSTIC"
        )

        print(
            f"[{status}] {name}: "
            f"exit code "
            f"{result.return_code}"
        )

    report_parts.append(
        scan_python_files(
            project_root
        )
    )

    report_parts.append(
        file_hash_report(
            project_root=project_root,
            copied_files=copied_files,
        )
    )

    validation_summary = {
        "generated_at_utc": (
            utc_now_iso()
        ),
        "compilation_passed": (
            compilation_passed
        ),
        "commands": [
            asdict(result)
            for result in command_results
        ],
    }

    validation_summary_path = (
        snapshot_root
        / "validation_summary.json"
    )

    validation_summary_path.write_text(
        (
            json.dumps(
                validation_summary,
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        ),
        encoding="utf-8",
    )

    report_path = (
        snapshot_root
        / "runtime_validation_report.txt"
    )

    report_path.write_text(
        "".join(report_parts),
        encoding="utf-8",
    )

    write_zip(
        source_root=snapshot_root,
        archive_path=archive_path,
    )

    archive_hash = sha256_file(
        archive_path
    )

    archive_hash_path.write_text(
        (
            f"File: {archive_path}\n"
            f"SHA256: {archive_hash}\n"
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 78)
    print(
        "Runtime snapshot completed"
    )
    print("=" * 78)
    print(
        f"ZIP:    {archive_path}"
    )
    print(
        f"SHA256: {archive_hash}"
    )
    print()
    print(
        "Upload the ZIP file shown above."
    )
    print(
        "No project source files "
        "were modified."
    )
    print()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )

    except KeyboardInterrupt:
        print()
        print("Cancelled.")

        raise SystemExit(130)

    except Exception as error:
        print()
        print("=" * 78)
        print(
            "Runtime snapshot failed"
        )
        print("=" * 78)

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        print()

        traceback.print_exc()

        print()
        print(
            "No project source files "
            "were modified."
        )

        raise SystemExit(1)