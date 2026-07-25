from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


ENGINE_VERSION = "1.0.0"
DEFAULT_DATABASE_PATH = Path("database/polymarket.db")
DEFAULT_LOG_DIR = Path("logs/intelligence_runs")


@dataclass(frozen=True)
class StepDefinition:
    step_name: str
    module_name: str
    required: bool = False
    enabled_by_default: bool = True


@dataclass
class StepResult:
    step_name: str
    module_name: str
    status: str
    started_at: str
    completed_at: str
    runtime_seconds: float
    return_code: Optional[int]
    stdout_log: str
    stderr_log: str
    error_message: str = ""


# The orchestrator intentionally supports modules that may not exist yet.
# Missing optional modules are recorded as SKIPPED rather than treated as failures.
DEFAULT_STEPS: tuple[StepDefinition, ...] = (
    StepDefinition("wallet_discovery", "src.wallet_discovery_engine", required=False),
    StepDefinition("wallet_tracker", "src.wallet_tracker", required=False),
    StepDefinition("wallet_performance", "src.wallet_performance_engine", required=False),
    StepDefinition("universal_market_collector", "src.universal_market_collector", required=False),
    StepDefinition("consensus_intelligence", "src.consensus_intelligence_engine_v1_0_1", required=False),
    StepDefinition("resolution_warehouse", "src.resolution_warehouse_engine", required=True),
    StepDefinition("resolution_outcome", "src.resolution_outcome_engine", required=True),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def safe_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"intelligence_run:{timestamp}:{uuid.uuid4().hex[:8]}"


def connect_database(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS intelligence_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            database_path TEXT NOT NULL,
            requested_steps INTEGER NOT NULL DEFAULT 0,
            completed_steps INTEGER NOT NULL DEFAULT 0,
            skipped_steps INTEGER NOT NULL DEFAULT 0,
            failed_steps INTEGER NOT NULL DEFAULT 0,
            runtime_seconds REAL NOT NULL DEFAULT 0,
            markets_reviewed INTEGER NOT NULL DEFAULT 0,
            actionable_signals INTEGER NOT NULL DEFAULT 0,
            pending_signals INTEGER NOT NULL DEFAULT 0,
            resolved_signals INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            voids INTEGER NOT NULL DEFAULT 0,
            profit_loss_units REAL NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS intelligence_run_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            module_name TEXT NOT NULL,
            required INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            runtime_seconds REAL NOT NULL DEFAULT 0,
            return_code INTEGER,
            stdout_log TEXT NOT NULL DEFAULT '',
            stderr_log TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(run_id, step_order),
            FOREIGN KEY(run_id) REFERENCES intelligence_runs(run_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_intelligence_runs_started_at
            ON intelligence_runs(started_at DESC);

        CREATE INDEX IF NOT EXISTS idx_intelligence_run_steps_run_id
            ON intelligence_run_steps(run_id, step_order);
        """
    )
    connection.commit()


def module_exists(project_root: Path, module_name: str) -> bool:
    relative = Path(*module_name.split("."))
    return (
        (project_root / relative).with_suffix(".py").is_file()
        or (project_root / relative / "__init__.py").is_file()
    )


def select_steps(
    all_steps: Iterable[StepDefinition],
    requested_names: Optional[set[str]],
    skipped_names: set[str],
) -> list[StepDefinition]:
    selected: list[StepDefinition] = []
    for step in all_steps:
        if requested_names is not None and step.step_name not in requested_names:
            continue
        if step.step_name in skipped_names:
            continue
        if step.enabled_by_default or requested_names is not None:
            selected.append(step)
    return selected


def truncate_text(value: str, max_chars: int = 4000) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "\n...[truncated]..."


def execute_step(
    project_root: Path,
    log_dir: Path,
    run_id: str,
    step: StepDefinition,
    python_executable: str,
) -> StepResult:
    started_at = utc_now()
    started_monotonic = time.perf_counter()

    safe_step = step.step_name.replace("/", "_").replace("\\", "_")
    stdout_path = log_dir / f"{safe_step}.stdout.log"
    stderr_path = log_dir / f"{safe_step}.stderr.log"

    if not module_exists(project_root, step.module_name):
        completed_at = utc_now()
        runtime = time.perf_counter() - started_monotonic
        message = f"Module not found: {step.module_name}"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(message + "\n", encoding="utf-8")

        return StepResult(
            step_name=step.step_name,
            module_name=step.module_name,
            status="FAILED" if step.required else "SKIPPED",
            started_at=started_at,
            completed_at=completed_at,
            runtime_seconds=runtime,
            return_code=None,
            stdout_log=str(stdout_path),
            stderr_log=str(stderr_path),
            error_message=message,
        )

    command = [python_executable, "-m", step.module_name]
    environment = os.environ.copy()
    environment["POLYMARKET_ORCHESTRATOR_RUN_ID"] = run_id
    environment["PYTHONUNBUFFERED"] = "1"

    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            env=environment,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")

        status = "SUCCESS" if completed.returncode == 0 else "FAILED"
        error_message = ""
        if completed.returncode != 0:
            error_message = truncate_text(
                (completed.stderr or completed.stdout or "Unknown module failure").strip()
            )

        return StepResult(
            step_name=step.step_name,
            module_name=step.module_name,
            status=status,
            started_at=started_at,
            completed_at=utc_now(),
            runtime_seconds=time.perf_counter() - started_monotonic,
            return_code=completed.returncode,
            stdout_log=str(stdout_path),
            stderr_log=str(stderr_path),
            error_message=error_message,
        )

    except Exception as exc:
        error_text = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        stderr_path.write_text(error_text, encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")

        return StepResult(
            step_name=step.step_name,
            module_name=step.module_name,
            status="FAILED",
            started_at=started_at,
            completed_at=utc_now(),
            runtime_seconds=time.perf_counter() - started_monotonic,
            return_code=None,
            stdout_log=str(stdout_path),
            stderr_log=str(stderr_path),
            error_message=truncate_text(str(exc)),
        )


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def get_latest_daily_metrics(connection: sqlite3.Connection) -> dict[str, float | int]:
    defaults: dict[str, float | int] = {
        "markets_reviewed": 0,
        "actionable_signals": 0,
        "pending_signals": 0,
        "resolved_signals": 0,
        "wins": 0,
        "losses": 0,
        "voids": 0,
        "profit_loss_units": 0.0,
    }

    if not table_exists(connection, "daily_outcomes"):
        return defaults

    row = connection.execute(
        """
        SELECT
            markets_reviewed,
            actionable_signals,
            pending_signals,
            resolved_signals,
            wins,
            losses,
            voids,
            profit_loss_units
        FROM daily_outcomes
        ORDER BY outcome_date DESC
        LIMIT 1
        """
    ).fetchone()

    if row is None:
        return defaults

    for key in defaults:
        value = row[key]
        defaults[key] = 0 if value is None else value
    return defaults


def insert_run_start(
    connection: sqlite3.Connection,
    run_id: str,
    database_path: Path,
    requested_steps: int,
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO intelligence_runs (
            run_id,
            started_at,
            status,
            engine_version,
            database_path,
            requested_steps,
            created_at,
            updated_at
        )
        VALUES (?, ?, 'RUNNING', ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            now,
            ENGINE_VERSION,
            str(database_path.resolve()),
            requested_steps,
            now,
            now,
        ),
    )
    connection.commit()


def insert_step_result(
    connection: sqlite3.Connection,
    run_id: str,
    step_order: int,
    step: StepDefinition,
    result: StepResult,
) -> None:
    connection.execute(
        """
        INSERT INTO intelligence_run_steps (
            run_id,
            step_order,
            step_name,
            module_name,
            required,
            status,
            started_at,
            completed_at,
            runtime_seconds,
            return_code,
            stdout_log,
            stderr_log,
            error_message,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            step_order,
            result.step_name,
            result.module_name,
            int(step.required),
            result.status,
            result.started_at,
            result.completed_at,
            result.runtime_seconds,
            result.return_code,
            result.stdout_log,
            result.stderr_log,
            result.error_message,
            utc_now(),
        ),
    )
    connection.commit()


def finalize_run(
    connection: sqlite3.Connection,
    run_id: str,
    started_monotonic: float,
    results: list[StepResult],
    final_status: str,
    notes: str,
) -> dict[str, float | int]:
    metrics = get_latest_daily_metrics(connection)

    completed_steps = sum(result.status == "SUCCESS" for result in results)
    skipped_steps = sum(result.status == "SKIPPED" for result in results)
    failed_steps = sum(result.status == "FAILED" for result in results)

    connection.execute(
        """
        UPDATE intelligence_runs
        SET
            completed_at = ?,
            status = ?,
            completed_steps = ?,
            skipped_steps = ?,
            failed_steps = ?,
            runtime_seconds = ?,
            markets_reviewed = ?,
            actionable_signals = ?,
            pending_signals = ?,
            resolved_signals = ?,
            wins = ?,
            losses = ?,
            voids = ?,
            profit_loss_units = ?,
            notes = ?,
            updated_at = ?
        WHERE run_id = ?
        """,
        (
            utc_now(),
            final_status,
            completed_steps,
            skipped_steps,
            failed_steps,
            time.perf_counter() - started_monotonic,
            metrics["markets_reviewed"],
            metrics["actionable_signals"],
            metrics["pending_signals"],
            metrics["resolved_signals"],
            metrics["wins"],
            metrics["losses"],
            metrics["voids"],
            metrics["profit_loss_units"],
            notes,
            utc_now(),
            run_id,
        ),
    )
    connection.commit()
    return metrics


def print_header(title: str, width: int = 126) -> None:
    print("=" * width)
    print(title)
    print("=" * width)


def print_step_result(index: int, total: int, result: StepResult) -> None:
    runtime = f"{result.runtime_seconds:.2f}s"
    suffix = f" | {result.error_message}" if result.error_message else ""
    print(
        f"[{index:>2}/{total:<2}] "
        f"{result.step_name:<30} "
        f"{result.status:<8} "
        f"{runtime:>10}"
        f"{suffix}"
    )


def write_manifest(
    manifest_path: Path,
    run_id: str,
    final_status: str,
    results: list[StepResult],
    metrics: dict[str, float | int],
) -> None:
    payload = {
        "run_id": run_id,
        "status": final_status,
        "engine_version": ENGINE_VERSION,
        "created_at": utc_now(),
        "metrics": metrics,
        "steps": [asdict(result) for result in results],
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Polymarket Intelligence Platform as one auditable pipeline."
    )
    parser.add_argument(
        "--database",
        default=str(DEFAULT_DATABASE_PATH),
        help="SQLite database path. Default: database/polymarket.db",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Run only the named step(s). Example: --only resolution_warehouse resolution_outcome",
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        default=[],
        help="Skip named step(s).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue after a required step fails.",
    )
    parser.add_argument(
        "--list-steps",
        action="store_true",
        help="Print available orchestrator steps and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    database_path = (project_root / args.database).resolve()

    if args.list_steps:
        print_header("AVAILABLE INTELLIGENCE ORCHESTRATOR STEPS")
        for step in DEFAULT_STEPS:
            availability = "FOUND" if module_exists(project_root, step.module_name) else "MISSING"
            requirement = "REQUIRED" if step.required else "OPTIONAL"
            print(
                f"{step.step_name:<30} "
                f"{requirement:<10} "
                f"{availability:<8} "
                f"{step.module_name}"
            )
        return 0

    requested_names = set(args.only) if args.only else None
    skipped_names = set(args.skip)
    selected_steps = select_steps(DEFAULT_STEPS, requested_names, skipped_names)

    if not selected_steps:
        print("No orchestrator steps were selected.")
        return 2

    run_id = safe_run_id()
    run_log_dir = project_root / DEFAULT_LOG_DIR / run_id.replace(":", "_")
    run_log_dir.mkdir(parents=True, exist_ok=True)

    connection = connect_database(database_path)
    ensure_schema(connection)
    insert_run_start(connection, run_id, database_path, len(selected_steps))

    print_header("POLYMARKET INTELLIGENCE ORCHESTRATOR")
    print(f"Run ID: {run_id}")
    print(f"Database: {database_path}")
    print(f"Selected steps: {len(selected_steps)}")
    print(f"Log directory: {run_log_dir}")
    print()

    started_monotonic = time.perf_counter()
    results: list[StepResult] = []
    final_status = "SUCCESS"
    notes: list[str] = []

    try:
        for index, step in enumerate(selected_steps, start=1):
            result = execute_step(
                project_root=project_root,
                log_dir=run_log_dir,
                run_id=run_id,
                step=step,
                python_executable=sys.executable,
            )
            results.append(result)
            insert_step_result(connection, run_id, index, step, result)
            print_step_result(index, len(selected_steps), result)

            if result.status == "FAILED":
                final_status = "PARTIAL_FAILURE"
                notes.append(f"{step.step_name}: {result.error_message}")

                if step.required and not args.continue_on_error:
                    notes.append("Pipeline stopped because a required step failed.")
                    break

        if not results:
            final_status = "FAILED"
            notes.append("No steps executed.")
        elif any(
            result.status == "FAILED"
            and selected_steps[index].required
            for index, result in enumerate(results)
        ):
            final_status = "FAILED"
        elif any(result.status == "FAILED" for result in results):
            final_status = "PARTIAL_FAILURE"
        elif all(result.status == "SKIPPED" for result in results):
            final_status = "NO_OP"

    except KeyboardInterrupt:
        final_status = "INTERRUPTED"
        notes.append("Run interrupted by user.")
    except Exception as exc:
        final_status = "FAILED"
        notes.append(f"Unhandled orchestrator error: {exc}")
        traceback.print_exc()
    finally:
        metrics = finalize_run(
            connection=connection,
            run_id=run_id,
            started_monotonic=started_monotonic,
            results=results,
            final_status=final_status,
            notes=" | ".join(notes),
        )

        manifest_path = run_log_dir / "manifest.json"
        write_manifest(
            manifest_path=manifest_path,
            run_id=run_id,
            final_status=final_status,
            results=results,
            metrics=metrics,
        )
        connection.close()

    print()
    print_header("ORCHESTRATOR HEALTH SUMMARY")
    print(f"Status: {final_status}")
    print(f"Steps successful: {sum(r.status == 'SUCCESS' for r in results)}")
    print(f"Steps skipped:    {sum(r.status == 'SKIPPED' for r in results)}")
    print(f"Steps failed:     {sum(r.status == 'FAILED' for r in results)}")
    print(f"Markets reviewed: {metrics['markets_reviewed']}")
    print(f"Signals:          {metrics['actionable_signals']}")
    print(f"Pending:          {metrics['pending_signals']}")
    print(f"Resolved:         {metrics['resolved_signals']}")
    print(f"Wins/Losses:      {metrics['wins']}-{metrics['losses']}")
    print(f"Profit/Loss:      {float(metrics['profit_loss_units']):+.3f}u")
    print(f"Manifest:         {manifest_path}")

    return 0 if final_status in {"SUCCESS", "NO_OP"} else 1


if __name__ == "__main__":
    raise SystemExit(main())