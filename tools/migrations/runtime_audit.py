"""Audit the runtime package before API migration."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from tools.framework import MigrationSession


PATTERNS: dict[str, re.Pattern[str]] = {
    "PlatformContext": re.compile(
        r"\bPlatformContext\b"
    ),
    "execute method definitions": re.compile(
        r"\bdef\s+execute\s*\("
    ),
    "execute method calls": re.compile(
        r"\.execute\s*\("
    ),
    "set_shared": re.compile(
        r"\bset_shared\b"
    ),
    "get_shared": re.compile(
        r"\bget_shared\b"
    ),
}


def collect_python_files(
    *directories: Path,
) -> list[Path]:
    """Collect Python files in deterministic order."""

    files: list[Path] = []

    for directory in directories:
        if directory.exists():
            files.extend(
                directory.rglob("*.py")
            )

    return sorted(
        set(files),
        key=lambda path: str(path).lower(),
    )


def run(project_root: Path) -> int:
    """Run the runtime migration audit."""

    operation_name = "runtime_migration"

    with MigrationSession(
        project_root,
        operation_name,
    ) as session:
        runtime_directory = (
            project_root / "src" / "runtime"
        )

        test_directory = (
            project_root / "tests" / "runtime"
        )

        session.require_paths(
            [
                "src/runtime",
                "tests/runtime",
                "src/runtime/__init__.py",
                "src/runtime/context.py",
                "src/runtime/engine.py",
                "src/runtime/protocol.py",
                "src/runtime/registry.py",
                "src/runtime/planner.py",
                "src/runtime/runner.py",
            ]
        )

        report_lines: list[str] = []

        def record(text: str = "") -> None:
            report_lines.append(text)
            print(text)

        record("==========================================")
        record(" Polymarket Runtime Python Audit")
        record("==========================================")
        record()
        record(
            f"Generated: "
            f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        )
        record(f"Project: {project_root}")
        record(f"Python: {sys.executable}")
        record()

        record("PREREQUISITE CHECK")
        record("------------------")

        required_paths = [
            "src/runtime",
            "tests/runtime",
            "src/runtime/__init__.py",
            "src/runtime/context.py",
            "src/runtime/engine.py",
            "src/runtime/protocol.py",
            "src/runtime/registry.py",
            "src/runtime/planner.py",
            "src/runtime/runner.py",
        ]

        for relative_path in required_paths:
            record(f"[OK] {relative_path}")

        files = collect_python_files(
            runtime_directory,
            test_directory,
        )

        record()
        record("LEGACY SYMBOL SCAN")
        record("------------------")

        total_matches = 0

        for label, pattern in PATTERNS.items():
            record()
            record(f"Pattern: {label}")

            matches: list[
                tuple[Path, int, str]
            ] = []

            for path in files:
                content = path.read_text(
                    encoding="utf-8-sig"
                )

                for line_number, line in enumerate(
                    content.splitlines(),
                    start=1,
                ):
                    if pattern.search(line):
                        matches.append(
                            (
                                path.relative_to(
                                    project_root
                                ),
                                line_number,
                                line.strip(),
                            )
                        )

            if not matches:
                record("No matches found.")
                continue

            total_matches += len(matches)

            for relative, line_number, text in matches:
                record(
                    f"{relative}:{line_number}: {text}"
                )

        record()
        record("PUBLIC RUNTIME IMPORT")
        record("---------------------")

        import_result = session.run_python(
            "-c",
            (
                "import src.runtime as runtime; "
                "print('src.runtime imported successfully'); "
                "print('Public names:'); "
                "print('\\n'.join("
                "'  ' + name for name in sorted("
                "name for name in dir(runtime) "
                "if not name.startswith('_'))"
                "))"
            ),
        )

        if import_result.stdout.strip():
            record(import_result.stdout.rstrip())

        if import_result.stderr.strip():
            record(import_result.stderr.rstrip())

        record(
            f"Import exit code: "
            f"{import_result.return_code}"
        )

        record()
        record("RUNTIME TEST SUITE")
        record("------------------")

        test_result = session.run_python(
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests/runtime",
            "-p",
            "test_*.py",
            "-v",
        )

        if test_result.stdout.strip():
            record(test_result.stdout.rstrip())

        if test_result.stderr.strip():
            record(test_result.stderr.rstrip())

        record()
        record("AUDIT SUMMARY")
        record("-------------")
        record(f"Python files scanned: {len(files)}")
        record(f"Legacy matches: {total_matches}")
        record(
            f"Import exit code: "
            f"{import_result.return_code}"
        )
        record(
            f"Runtime tests exit code: "
            f"{test_result.return_code}"
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        report_path = session.save_report(
            f"runtime_python_audit_{timestamp}.txt",
            report_lines,
        )

        relative_report = report_path.relative_to(
            project_root
        )

        record(f"Report: {relative_report}")

        import_succeeded = (
            import_result.return_code == 0
        )

        tests_succeeded = (
            test_result.return_code == 0
        )

        if import_succeeded and tests_succeeded:
            record(
                "Status: Runtime imports and all "
                "runtime tests pass."
            )
        else:
            record(
                "Status: Runtime migration work remains."
            )

        # Audit operations do not modify project source files.
        session.commit()

        # A failing audit is a valid diagnostic result.
        # Return zero so PowerShell remains usable and the
        # report can be reviewed before migration.
        return 0
