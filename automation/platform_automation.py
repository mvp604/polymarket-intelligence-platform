from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


AUTOMATION_VERSION = "1.0.0"
DEFAULT_CONFIG = Path("automation/platform_automation.json")


@dataclass(slots=True)
class StepResult:
    name: str
    module: str
    status: str
    return_code: int
    runtime_seconds: float
    log_path: str
    message: str = ""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root() / path
    return path.resolve()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def module_exists(module_name: str) -> bool:
    relative = Path(*module_name.split(".")).with_suffix(".py")
    return (project_root() / relative).exists()


def compile_module(module_name: str) -> tuple[bool, str]:
    relative = Path(*module_name.split(".")).with_suffix(".py")
    module_path = project_root() / relative

    if not module_path.exists():
        return False, f"Module file not found: {module_path}"

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(module_path)],
        cwd=project_root(),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()

    return True, "Compilation passed."


def database_integrity_check(database_path: Path) -> tuple[bool, str]:
    if not database_path.exists():
        return False, f"Database not found: {database_path}"

    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        result = str(row[0]) if row else "unknown"
        return result.lower() == "ok", result
    finally:
        connection.close()


def run_process(
    command: list[str],
    log_path: Path,
    timeout_seconds: int | None,
) -> tuple[int, float, str]:
    ensure_directory(log_path.parent)
    started = time.perf_counter()

    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n\n")
        log.flush()

        try:
            process = subprocess.Popen(
                command,
                cwd=project_root(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="")
                log.write(line)

            return_code = process.wait(timeout=timeout_seconds)
            runtime = time.perf_counter() - started
            return return_code, runtime, ""

        except subprocess.TimeoutExpired:
            process.kill()
            runtime = time.perf_counter() - started
            message = f"Timed out after {timeout_seconds} seconds."
            log.write("\n" + message + "\n")
            return 124, runtime, message


def acquire_lock(lock_path: Path) -> None:
    ensure_directory(lock_path.parent)

    if lock_path.exists():
        try:
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
            existing_pid = payload.get("pid")
            existing_started = payload.get("started_at")
        except Exception:
            existing_pid = None
            existing_started = None

        raise RuntimeError(
            "Automation lock already exists. "
            f"PID={existing_pid}, started_at={existing_started}. "
            f"Delete {lock_path} only if no platform run is active."
        )

    write_json(
        lock_path,
        {
            "pid": os.getpid(),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


def release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass


def run_migrations(
    config: dict[str, Any],
    run_log_dir: Path,
) -> StepResult:
    migration_runner = resolve_path(
        config.get(
            "migration_runner",
            "database/migration_runner.py",
        )
    )

    if not migration_runner.exists():
        return StepResult(
            name="database_migrations",
            module=str(migration_runner),
            status="FAILED",
            return_code=2,
            runtime_seconds=0.0,
            log_path="",
            message="Migration runner is missing.",
        )

    log_path = run_log_dir / "00_database_migrations.log"
    command = [sys.executable, str(migration_runner)]

    return_code, runtime, message = run_process(
        command,
        log_path,
        config.get("migration_timeout_seconds", 300),
    )

    return StepResult(
        name="database_migrations",
        module=str(migration_runner),
        status="SUCCESS" if return_code == 0 else "FAILED",
        return_code=return_code,
        runtime_seconds=runtime,
        log_path=str(log_path),
        message=message,
    )


def run_step(
    index: int,
    step: dict[str, Any],
    run_log_dir: Path,
) -> StepResult:
    name = str(step["name"])
    module = str(step["module"])
    required = bool(step.get("required", True))
    enabled = bool(step.get("enabled", True))
    arguments = [str(item) for item in step.get("arguments", [])]
    timeout = step.get("timeout_seconds")

    if not enabled:
        return StepResult(
            name=name,
            module=module,
            status="DISABLED",
            return_code=0,
            runtime_seconds=0.0,
            log_path="",
            message="Disabled in configuration.",
        )

    if not module_exists(module):
        status = "FAILED" if required else "SKIPPED"
        return StepResult(
            name=name,
            module=module,
            status=status,
            return_code=2,
            runtime_seconds=0.0,
            log_path="",
            message=f"Module not found: {module}",
        )

    compiled, compile_message = compile_module(module)
    if not compiled:
        return StepResult(
            name=name,
            module=module,
            status="FAILED",
            return_code=3,
            runtime_seconds=0.0,
            log_path="",
            message=compile_message,
        )

    log_path = run_log_dir / f"{index:02d}_{name}.log"
    command = [sys.executable, "-m", module, *arguments]

    return_code, runtime, message = run_process(
        command,
        log_path,
        timeout,
    )

    return StepResult(
        name=name,
        module=module,
        status="SUCCESS" if return_code == 0 else "FAILED",
        return_code=return_code,
        runtime_seconds=runtime,
        log_path=str(log_path),
        message=message,
    )


def print_result(result: StepResult) -> None:
    print(
        f"{result.name:<30} "
        f"{result.status:<10} "
        f"{result.runtime_seconds:>8.2f}s"
    )
    if result.message:
        print(f"  {result.message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One-command Polymarket platform automation."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Automation configuration path.",
    )
    parser.add_argument(
        "--from-step",
        help="Start from a named engine step.",
    )
    parser.add_argument(
        "--only",
        help="Run only one named engine step.",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config_path = resolve_path(args.config)
    config = load_config(config_path)

    database_path = resolve_path(
        config.get("database", "database/polymarket.db")
    )
    logs_root = resolve_path(
        config.get("logs_directory", "logs/automation")
    )
    lock_path = resolve_path(
        config.get("lock_file", "logs/automation/platform.lock")
    )

    run_id = f"automation_{utc_stamp()}"
    run_log_dir = logs_root / run_id
    ensure_directory(run_log_dir)

    manifest_path = run_log_dir / "manifest.json"
    results: list[StepResult] = []

    print("=" * 112)
    print(f"POLYMARKET PLATFORM AUTOMATION v{AUTOMATION_VERSION}")
    print("=" * 112)
    print(f"Project:  {project_root()}")
    print(f"Database: {database_path}")
    print(f"Config:   {config_path}")
    print(f"Logs:     {run_log_dir}")

    if args.dry_run:
        print("\nDRY RUN Ã¢â‚¬â€ no processes will execute.")
        for step in config.get("steps", []):
            print(
                f"{step['name']:<30} "
                f"{step['module']:<50} "
                f"required={step.get('required', True)}"
            )
        return 0

    acquire_lock(lock_path)

    overall_status = "SUCCESS"

    try:
        integrity_ok, integrity_message = database_integrity_check(
            database_path
        )
        if not integrity_ok:
            raise RuntimeError(
                f"Database integrity check failed: {integrity_message}"
            )
        print(f"Database integrity: {integrity_message}")

        if not args.skip_migrations:
            migration_result = run_migrations(config, run_log_dir)
            results.append(migration_result)
            print_result(migration_result)

            if migration_result.status == "FAILED":
                overall_status = "FAILED"
                raise RuntimeError(
                    "Database migration failed. Engine execution stopped."
                )

        steps = list(config.get("steps", []))

        if args.only:
            steps = [
                step
                for step in steps
                if step.get("name") == args.only
            ]
            if not steps:
                raise RuntimeError(f"Unknown step: {args.only}")

        elif args.from_step:
            names = [str(step.get("name")) for step in steps]
            if args.from_step not in names:
                raise RuntimeError(
                    f"Unknown starting step: {args.from_step}"
                )
            steps = steps[names.index(args.from_step):]

        for index, step in enumerate(steps, start=1):
            print()
            print("-" * 112)
            print(
                f"[{index}/{len(steps)}] "
                f"{step['name']} ({step['module']})"
            )
            print("-" * 112)

            result = run_step(index, step, run_log_dir)
            results.append(result)
            print_result(result)

            if result.status == "FAILED":
                overall_status = "PARTIAL_FAILURE"

                required = bool(step.get("required", True))
                stop_on_error = bool(
                    config.get("stop_on_required_error", True)
                )

                if (
                    required
                    and stop_on_error
                    and not args.continue_on_error
                ):
                    print(
                        "Stopping because a required step failed."
                    )
                    break

        if any(result.status == "FAILED" for result in results):
            overall_status = "PARTIAL_FAILURE"

    except Exception as error:
        overall_status = "FAILED"
        print(f"\nAutomation failed: {error}", file=sys.stderr)
        traceback.print_exc()

    finally:
        manifest = {
            "automation_version": AUTOMATION_VERSION,
            "run_id": run_id,
            "status": overall_status,
            "project_root": str(project_root()),
            "database": str(database_path),
            "config": str(config_path),
            "started_at": run_id.removeprefix("automation_"),
            "completed_at": datetime.now().isoformat(timespec="seconds"),
            "results": [
                {
                    "name": result.name,
                    "module": result.module,
                    "status": result.status,
                    "return_code": result.return_code,
                    "runtime_seconds": round(
                        result.runtime_seconds,
                        3,
                    ),
                    "log_path": result.log_path,
                    "message": result.message,
                }
                for result in results
            ],
        }
        write_json(manifest_path, manifest)
        release_lock(lock_path)

    print()
    print("=" * 112)
    print("AUTOMATION SUMMARY")
    print("=" * 112)
    print(f"Status:   {overall_status}")
    print(f"Manifest: {manifest_path}")

    for result in results:
        print_result(result)

    return 0 if overall_status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
