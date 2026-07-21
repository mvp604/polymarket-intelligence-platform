from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# =============================================================================
# PROJECT CONFIGURATION
# =============================================================================


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
LOG_DIR = PROJECT_ROOT / "logs"
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

DEFAULT_FULL_INTERVAL_SECONDS = 3_600
DEFAULT_STATUS_INTERVAL_SECONDS = 300
DEFAULT_TEST_SECONDS = 0

BUSY_TIMEOUT_MS = 30_000

PIPELINE_VERSION = "1.1"


# =============================================================================
# STEP DEFINITIONS
# =============================================================================


@dataclass(frozen=True)
class PipelineStep:
    name: str
    key: str
    candidates: tuple[str, ...]
    required: bool = True
    stage: str = "CORE"
    arguments: tuple[str, ...] = ()
    timeout_seconds: int = 1_800


PIPELINE_STEPS: tuple[PipelineStep, ...] = (
    PipelineStep(
        name="Wallet Scanner",
        key="wallet_scanner",
        candidates=(
            "wallet_tracker.py",
            "wallet_scanner.py",
        ),
        required=True,
        stage="WALLET",
        timeout_seconds=1_800,
    ),
    PipelineStep(
        name="Wallet Ratings",
        key="wallet_ratings",
        candidates=(
            "wallet_ratings.py",
            "wallet_rating_engine.py",
        ),
        required=True,
        stage="WALLET",
    ),
    PipelineStep(
        name="Wallet Intelligence",
        key="wallet_intelligence",
        candidates=(
            "wallet_intelligence.py",
            "wallet_intelligence_engine.py",
        ),
        required=True,
        stage="WALLET",
    ),
    PipelineStep(
        name="Portfolio Overlap",
        key="portfolio_overlap",
        candidates=(
            "portfolio_overlap_engine.py",
            "portfolio_overlap.py",
        ),
        required=True,
        stage="WALLET",
    ),
    PipelineStep(
        name="Conviction Engine",
        key="conviction_engine",
        candidates=(
            "conviction_engine.py",
        ),
        required=True,
        stage="CONSENSUS",
    ),
    PipelineStep(
        name="Weighted Consensus",
        key="weighted_consensus",
        candidates=(
            "weighted_consensus.py",
            "weighted_consensus_engine.py",
        ),
        required=True,
        stage="CONSENSUS",
    ),
    PipelineStep(
        name="Alert Engine",
        key="alert_engine",
        candidates=(
            "alert_engine.py",
        ),
        required=False,
        stage="CONSENSUS",
    ),
    PipelineStep(
        name="Backtesting Engine",
        key="backtesting_engine",
        candidates=(
            "backtesting_engine.py",
            "backtest_engine.py",
        ),
        required=False,
        stage="MODEL",
        timeout_seconds=2_700,
    ),
    PipelineStep(
        name="ML Ranking Engine",
        key="ml_ranking_engine",
        candidates=(
            "ml_ranking_engine.py",
            "ml_rank_engine.py",
        ),
        required=False,
        stage="MODEL",
        timeout_seconds=2_700,
    ),
    PipelineStep(
        name="Canonical Market Identity",
        key="canonical_market_identity_engine",
        candidates=(
            "canonical_market_identity_engine.py",
        ),
        required=True,
        stage="IDENTITY",
        timeout_seconds=2_700,
    ),
    PipelineStep(
        name="Market Status and T-Minus",
        key="market_status_engine",
        candidates=(
            "market_status_engine.py",
        ),
        required=True,
        stage="MARKET",
        timeout_seconds=1_800,
    ),
    PipelineStep(
        name="Price History",
        key="price_history_engine",
        candidates=(
            "price_history_engine.py",
        ),
        required=True,
        stage="MARKET",
    ),
    PipelineStep(
        name="Closing Line Intelligence",
        key="closing_line_engine",
        candidates=(
            "closing_line_engine.py",
        ),
        required=True,
        stage="INTELLIGENCE",
    ),
    PipelineStep(
        name="Institutional Consensus",
        key="institutional_consensus_engine",
        candidates=(
            "institutional_consensus_engine.py",
        ),
        required=True,
        stage="INTELLIGENCE",
    ),
    PipelineStep(
        name="Position Evolution",
        key="position_evolution_engine",
        candidates=(
            "position_evolution_engine.py",
        ),
        required=True,
        stage="INTELLIGENCE",
    ),
    PipelineStep(
        name="Opportunity Engine",
        key="opportunity_engine",
        candidates=(
            "opportunity_engine.py",
        ),
        required=True,
        stage="RANKING",
    ),
    PipelineStep(
        name="Master Opportunity Engine",
        key="master_opportunity_engine",
        candidates=(
            "master_opportunity_engine.py",
        ),
        required=True,
        stage="RANKING",
    ),
)


STATUS_ONLY_STEPS = {
    "canonical_market_identity_engine",
    "market_status_engine",
    "price_history_engine",
    "closing_line_engine",
    "institutional_consensus_engine",
    "position_evolution_engine",
    "opportunity_engine",
    "master_opportunity_engine",
}


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class StepResult:
    name: str
    key: str
    stage: str
    script_path: str
    required: bool

    status: str
    return_code: int | None

    started_at: str
    finished_at: str
    elapsed_seconds: float

    log_path: str

    error_message: str = ""


@dataclass
class PipelineRunResult:
    run_id: int
    mode: str

    started_at: str
    finished_at: str
    elapsed_seconds: float

    successful_steps: int
    failed_steps: int
    skipped_steps: int

    required_failures: int
    optional_failures: int

    status: str

    summary_log_path: str
    step_results: list[StepResult] = field(
        default_factory=list
    )


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8_output() -> None:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except (AttributeError, OSError):
        pass

    try:
        sys.stderr.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except (AttributeError, OSError):
        pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_duration(
    seconds: float,
) -> str:
    total = max(
        int(seconds),
        0,
    )

    days, remainder = divmod(
        total,
        86_400,
    )

    hours, remainder = divmod(
        remainder,
        3_600,
    )

    minutes, seconds_left = divmod(
        remainder,
        60,
    )

    if days > 0:
        return (
            f"{days}d "
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds_left:02d}"
        )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds_left:02d}"
    )


def timestamp_for_filename(
    value: datetime | None = None,
) -> str:
    current = value or utc_now()

    return current.strftime(
        "%Y%m%d_%H%M%S"
    )


def ensure_directories() -> None:
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def resolve_step_script(
    step: PipelineStep,
) -> Path | None:
    for candidate in step.candidates:
        path = SRC_DIR / candidate

        if path.exists():
            return path

    return None


def print_banner(
    title: str,
    width: int = 108,
) -> None:
    print()
    print("=" * width)
    print(title)
    print("=" * width)


# =============================================================================
# DATABASE TABLES
# =============================================================================


def connect_database() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA journal_mode = WAL"
    )
    connection.execute(
        f"PRAGMA busy_timeout = "
        f"{BUSY_TIMEOUT_MS}"
    )

    return connection


def create_pipeline_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS master_pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                mode TEXT NOT NULL,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                successful_steps INTEGER
                    NOT NULL DEFAULT 0,

                failed_steps INTEGER
                    NOT NULL DEFAULT 0,

                skipped_steps INTEGER
                    NOT NULL DEFAULT 0,

                required_failures INTEGER
                    NOT NULL DEFAULT 0,

                optional_failures INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,

                summary_log_path TEXT,
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS
            idx_master_pipeline_runs_started
            ON master_pipeline_runs(
                started_at DESC
            );

            CREATE TABLE IF NOT EXISTS master_pipeline_step_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                pipeline_run_id INTEGER NOT NULL,

                step_name TEXT NOT NULL,
                step_key TEXT NOT NULL,
                stage TEXT NOT NULL,

                script_path TEXT,
                required INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                return_code INTEGER,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                log_path TEXT,
                error_message TEXT,

                FOREIGN KEY(
                    pipeline_run_id
                )
                REFERENCES master_pipeline_runs(id)
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_master_pipeline_step_runs_parent
            ON master_pipeline_step_runs(
                pipeline_run_id,
                id
            );
            """
        )

        connection.commit()

    finally:
        connection.close()


def start_pipeline_run(
    mode: str,
    summary_log_path: Path,
) -> tuple[int, datetime]:
    started = utc_now()

    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO master_pipeline_runs (
                mode,
                started_at,
                status,
                summary_log_path
            )
            VALUES (
                ?, ?, 'RUNNING', ?
            )
            """,
            (
                mode,
                started.isoformat(),
                str(summary_log_path),
            ),
        )

        connection.commit()

        return cursor.lastrowid, started

    finally:
        connection.close()


def save_step_result(
    pipeline_run_id: int,
    result: StepResult,
) -> None:
    connection = connect_database()

    try:
        connection.execute(
            """
            INSERT INTO master_pipeline_step_runs (
                pipeline_run_id,
                step_name,
                step_key,
                stage,
                script_path,
                required,
                status,
                return_code,
                started_at,
                finished_at,
                elapsed_seconds,
                log_path,
                error_message
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                pipeline_run_id,
                result.name,
                result.key,
                result.stage,
                result.script_path,
                int(result.required),
                result.status,
                result.return_code,
                result.started_at,
                result.finished_at,
                result.elapsed_seconds,
                result.log_path,
                result.error_message,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def finish_pipeline_run(
    result: PipelineRunResult,
    error_message: str = "",
) -> None:
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE master_pipeline_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                successful_steps = ?,
                failed_steps = ?,
                skipped_steps = ?,
                required_failures = ?,
                optional_failures = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                result.finished_at,
                result.elapsed_seconds,
                result.successful_steps,
                result.failed_steps,
                result.skipped_steps,
                result.required_failures,
                result.optional_failures,
                result.status,
                error_message,
                result.run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# PIPELINE EXECUTION
# =============================================================================


class ShutdownController:
    def __init__(self) -> None:
        self.requested = False

    def request_shutdown(
        self,
        signum: int | None = None,
        frame: Any = None,
    ) -> None:
        del signum, frame

        if not self.requested:
            print()
            print(
                "Shutdown requested. "
                "The active step will be stopped."
            )

        self.requested = True


def run_step(
    step: PipelineStep,
    pipeline_run_id: int,
    run_timestamp: str,
    shutdown: ShutdownController,
    extra_arguments: tuple[str, ...] = (),
) -> StepResult:
    script_path = resolve_step_script(
        step
    )

    started = utc_now()

    log_path = (
        LOG_DIR
        / (
            f"master_pipeline_"
            f"{run_timestamp}_"
            f"{step.key}.log"
        )
    )

    if script_path is None:
        finished = utc_now()

        status = (
            "FAILED"
            if step.required
            else "SKIPPED"
        )

        error_message = (
            "No matching script was found. "
            f"Checked: {', '.join(step.candidates)}"
        )

        result = StepResult(
            name=step.name,
            key=step.key,
            stage=step.stage,
            script_path="",
            required=step.required,
            status=status,
            return_code=None,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            elapsed_seconds=(
                finished - started
            ).total_seconds(),
            log_path=str(log_path),
            error_message=error_message,
        )

        save_step_result(
            pipeline_run_id,
            result,
        )

        return result

    command = [
        sys.executable,
        "-u",
        str(script_path),
        *step.arguments,
        *extra_arguments,
    ]

    print_banner(
        f"STARTING: {step.name}"
    )

    print(
        f"Stage:      {step.stage}"
    )

    print(
        f"Required:   {step.required}"
    )

    print(
        f"Script:     {script_path}"
    )

    print(
        f"Started:    {started.isoformat()}"
    )

    print(
        f"Log:        {log_path}"
    )

    return_code: int | None = None
    error_message = ""

    with log_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as log_file:
        log_file.write(
            f"STEP: {step.name}\n"
        )

        log_file.write(
            f"SCRIPT: {script_path}\n"
        )

        log_file.write(
            f"COMMAND: {' '.join(command)}\n"
        )

        log_file.write(
            f"STARTED: {started.isoformat()}\n"
        )

        log_file.write(
            "=" * 108
            + "\n\n"
        )

        log_file.flush()

        process: subprocess.Popen[str] | None = None

        try:
            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                },
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if os.name == "nt"
                    else 0
                ),
            )

            deadline = (
                time.monotonic()
                + step.timeout_seconds
            )

            while process.poll() is None:
                if shutdown.requested:
                    error_message = (
                        "Shutdown requested by user."
                    )

                    terminate_process(
                        process
                    )

                    break

                if time.monotonic() >= deadline:
                    error_message = (
                        "Step timed out after "
                        f"{step.timeout_seconds} seconds."
                    )

                    terminate_process(
                        process
                    )

                    break

                time.sleep(0.5)

            return_code = process.poll()

        except Exception as error:
            error_message = (
                f"{type(error).__name__}: "
                f"{error}"
            )

            if process is not None:
                terminate_process(
                    process
                )

        finished = utc_now()

        log_file.write(
            "\n\n"
            + "=" * 108
            + "\n"
        )

        log_file.write(
            f"FINISHED: {finished.isoformat()}\n"
        )

        log_file.write(
            "ELAPSED: "
            f"{format_duration((finished - started).total_seconds())}\n"
        )

        log_file.write(
            f"RETURN CODE: {return_code}\n"
        )

        if error_message:
            log_file.write(
                f"ERROR: {error_message}\n"
            )

    if (
        return_code == 0
        and not error_message
    ):
        status = "SUCCESS"

    else:
        status = "FAILED"

        if not error_message:
            error_message = (
                "Process exited with "
                f"return code {return_code}."
            )

    result = StepResult(
        name=step.name,
        key=step.key,
        stage=step.stage,
        script_path=str(script_path),
        required=step.required,
        status=status,
        return_code=return_code,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        elapsed_seconds=(
            finished - started
        ).total_seconds(),
        log_path=str(log_path),
        error_message=error_message,
    )

    save_step_result(
        pipeline_run_id,
        result,
    )

    if status == "SUCCESS":
        print(
            f"COMPLETED: {step.name} "
            f"in "
            f"{format_duration(result.elapsed_seconds)}."
        )

    else:
        print(
            f"FAILED: {step.name} "
            f"in "
            f"{format_duration(result.elapsed_seconds)}."
        )

        print(
            f"Reason: {error_message}"
        )

    return result


def terminate_process(
    process: subprocess.Popen[str],
) -> None:
    if process.poll() is not None:
        return

    try:
        if os.name == "nt":
            process.send_signal(
                signal.CTRL_BREAK_EVENT
            )

            try:
                process.wait(
                    timeout=8
                )

                return
            except subprocess.TimeoutExpired:
                pass

        else:
            process.terminate()

            try:
                process.wait(
                    timeout=8
                )

                return
            except subprocess.TimeoutExpired:
                pass

    except Exception:
        pass

    try:
        process.kill()
        process.wait(
            timeout=5
        )

    except Exception:
        pass


def select_steps(
    status_only: bool,
    skip_wallet_refresh: bool,
) -> list[PipelineStep]:
    selected: list[PipelineStep] = []

    for step in PIPELINE_STEPS:
        if (
            status_only
            and step.key
            not in STATUS_ONLY_STEPS
        ):
            continue

        if (
            skip_wallet_refresh
            and step.stage == "WALLET"
        ):
            continue

        selected.append(step)

    return selected


def run_pipeline_once(
    mode: str,
    shutdown: ShutdownController,
    continue_on_required_failure: bool,
    status_only: bool,
    skip_wallet_refresh: bool,
    display_limit: int | None,
) -> PipelineRunResult:
    ensure_directories()
    create_pipeline_tables()

    run_started_wall = utc_now()
    run_timestamp = timestamp_for_filename(
        run_started_wall
    )

    summary_log_path = (
        LOG_DIR
        / (
            f"master_pipeline_summary_"
            f"{run_timestamp}.json"
        )
    )

    pipeline_run_id, started_at = (
        start_pipeline_run(
            mode=mode,
            summary_log_path=(
                summary_log_path
            ),
        )
    )

    selected_steps = select_steps(
        status_only=status_only,
        skip_wallet_refresh=(
            skip_wallet_refresh
        ),
    )

    results: list[StepResult] = []

    fatal_error = ""

    try:
        for step in selected_steps:
            if shutdown.requested:
                break

            extra_arguments: tuple[
                str,
                ...
            ] = ()

            if (
                display_limit is not None
                and step.key
                in {
                    "price_history_engine",
                    "closing_line_engine",
                    "institutional_consensus_engine",
                    "position_evolution_engine",
                    "opportunity_engine",
                    "master_opportunity_engine",
                }
            ):
                extra_arguments = (
                    "--display-limit",
                    str(display_limit),
                )

            result = run_step(
                step=step,
                pipeline_run_id=(
                    pipeline_run_id
                ),
                run_timestamp=(
                    run_timestamp
                ),
                shutdown=shutdown,
                extra_arguments=(
                    extra_arguments
                ),
            )

            results.append(result)

            if (
                result.status == "FAILED"
                and result.required
                and not continue_on_required_failure
            ):
                fatal_error = (
                    f"Required step failed: "
                    f"{step.name}"
                )

                break

    except Exception as error:
        fatal_error = (
            f"{type(error).__name__}: "
            f"{error}"
        )

        traceback.print_exc()

    finished_at = utc_now()

    successful_steps = sum(
        1
        for result in results
        if result.status == "SUCCESS"
    )

    failed_steps = sum(
        1
        for result in results
        if result.status == "FAILED"
    )

    skipped_steps = sum(
        1
        for result in results
        if result.status == "SKIPPED"
    )

    required_failures = sum(
        1
        for result in results
        if (
            result.status == "FAILED"
            and result.required
        )
    )

    optional_failures = sum(
        1
        for result in results
        if (
            result.status == "FAILED"
            and not result.required
        )
    )

    if shutdown.requested:
        status = "STOPPED"

    elif fatal_error or required_failures:
        status = "FAILED"

    elif optional_failures:
        status = (
            "SUCCESS_WITH_OPTIONAL_FAILURES"
        )

    else:
        status = "SUCCESS"

    pipeline_result = PipelineRunResult(
        run_id=pipeline_run_id,
        mode=mode,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        elapsed_seconds=(
            finished_at
            - started_at
        ).total_seconds(),
        successful_steps=successful_steps,
        failed_steps=failed_steps,
        skipped_steps=skipped_steps,
        required_failures=required_failures,
        optional_failures=optional_failures,
        status=status,
        summary_log_path=str(
            summary_log_path
        ),
        step_results=results,
    )

    summary_payload = {
        "pipeline_version": (
            PIPELINE_VERSION
        ),
        "run_id": pipeline_result.run_id,
        "mode": pipeline_result.mode,
        "status": pipeline_result.status,
        "started_at": (
            pipeline_result.started_at
        ),
        "finished_at": (
            pipeline_result.finished_at
        ),
        "elapsed_seconds": (
            pipeline_result.elapsed_seconds
        ),
        "successful_steps": (
            pipeline_result.successful_steps
        ),
        "failed_steps": (
            pipeline_result.failed_steps
        ),
        "skipped_steps": (
            pipeline_result.skipped_steps
        ),
        "required_failures": (
            pipeline_result.required_failures
        ),
        "optional_failures": (
            pipeline_result.optional_failures
        ),
        "fatal_error": fatal_error,
        "steps": [
            {
                "name": result.name,
                "key": result.key,
                "stage": result.stage,
                "required": result.required,
                "status": result.status,
                "return_code": (
                    result.return_code
                ),
                "elapsed_seconds": (
                    result.elapsed_seconds
                ),
                "script_path": (
                    result.script_path
                ),
                "log_path": result.log_path,
                "error_message": (
                    result.error_message
                ),
            }
            for result in results
        ],
    }

    summary_log_path.write_text(
        json.dumps(
            summary_payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    finish_pipeline_run(
        result=pipeline_result,
        error_message=fatal_error,
    )

    display_pipeline_summary(
        pipeline_result
    )

    return pipeline_result


# =============================================================================
# DISPLAY
# =============================================================================


def display_configuration(
    arguments: argparse.Namespace,
) -> None:
    print_banner(
        "POLYMARKET CONTINUOUS MASTER "
        f"PIPELINE v{PIPELINE_VERSION}"
    )

    print(
        f"Process ID:                 "
        f"{os.getpid()}"
    )

    print(
        f"Project:                    "
        f"{PROJECT_ROOT}"
    )

    print(
        f"Python:                     "
        f"{sys.executable}"
    )

    print(
        f"Mode:                       "
        f"{'CONTINUOUS' if arguments.continuous else 'ONE RUN'}"
    )

    print(
        f"Full pipeline interval:     "
        f"{arguments.interval} seconds"
    )

    print(
        f"Status interval:            "
        f"{arguments.status_interval} seconds"
    )

    print(
        f"Status-only mode:           "
        f"{arguments.status_only}"
    )

    print(
        f"Skip wallet refresh:        "
        f"{arguments.skip_wallet_refresh}"
    )

    print(
        f"Continue on req. failure:   "
        f"{arguments.continue_on_required_failure}"
    )

    print(
        f"Test duration:              "
        f"{arguments.seconds or 'Unlimited'}"
    )

    print(
        "AI Research Engine:        "
        "EXCLUDED"
    )

    print("=" * 108)


def display_pipeline_summary(
    result: PipelineRunResult,
) -> None:
    print_banner(
        "MASTER PIPELINE RUN SUMMARY"
    )

    print(
        f"Run ID:                    "
        f"{result.run_id}"
    )

    print(
        f"Status:                    "
        f"{result.status}"
    )

    print(
        f"Finished:                  "
        f"{result.finished_at}"
    )

    print(
        f"Elapsed:                   "
        f"{format_duration(result.elapsed_seconds)}"
    )

    print(
        f"Successful steps:          "
        f"{result.successful_steps}"
    )

    print(
        f"Failed steps:              "
        f"{result.failed_steps}"
    )

    print(
        f"Skipped steps:             "
        f"{result.skipped_steps}"
    )

    print(
        f"Required failures:         "
        f"{result.required_failures}"
    )

    print(
        f"Optional failures:         "
        f"{result.optional_failures}"
    )

    print()
    print("STEP RESULTS")

    for step in result.step_results:
        marker = {
            "SUCCESS": "[OK]",
            "FAILED": "[FAIL]",
            "SKIPPED": "[SKIP]",
        }.get(
            step.status,
            "[?]",
        )

        print(
            f"  {marker:<7}"
            f"{step.name:<38}"
            f"{format_duration(step.elapsed_seconds):>12}"
        )

    print()
    print(
        f"Summary saved to: "
        f"{result.summary_log_path}"
    )

    print("=" * 108)


# =============================================================================
# CONTINUOUS LOOP
# =============================================================================


def run_continuously(
    arguments: argparse.Namespace,
    shutdown: ShutdownController,
) -> None:
    process_started = time.monotonic()

    next_full_run = time.monotonic()

    last_status_print = 0.0

    run_number = 0

    while not shutdown.requested:
        now_monotonic = time.monotonic()

        if (
            arguments.seconds > 0
            and (
                now_monotonic
                - process_started
            )
            >= arguments.seconds
        ):
            print()
            print(
                "Configured continuous-pipeline "
                "test duration has completed."
            )

            break

        if now_monotonic >= next_full_run:
            run_number += 1

            mode = (
                "STATUS_ONLY"
                if arguments.status_only
                else "FULL"
            )

            print()
            print(
                f"[PIPELINE] Starting run "
                f"#{run_number} ({mode})"
            )

            result = run_pipeline_once(
                mode=mode,
                shutdown=shutdown,
                continue_on_required_failure=(
                    arguments.continue_on_required_failure
                ),
                status_only=(
                    arguments.status_only
                ),
                skip_wallet_refresh=(
                    arguments.skip_wallet_refresh
                ),
                display_limit=(
                    arguments.display_limit
                ),
            )

            if (
                result.required_failures > 0
                and not arguments.continue_on_required_failure
            ):
                print()
                print(
                    "Continuous mode stopped because "
                    "a required step failed."
                )

                break

            next_full_run = (
                time.monotonic()
                + arguments.interval
            )

        now_monotonic = time.monotonic()

        if (
            now_monotonic
            - last_status_print
            >= arguments.status_interval
        ):
            remaining = max(
                int(
                    next_full_run
                    - now_monotonic
                ),
                0,
            )

            print(
                f"[PIPELINE STATUS] "
                f"{utc_now_iso()} | "
                f"Next run: "
                f"{format_duration(remaining)} | "
                f"Completed runs: "
                f"{run_number}"
            )

            last_status_print = (
                now_monotonic
            )

        time.sleep(1.0)

    print()
    print_banner(
        "CONTINUOUS MASTER PIPELINE STOPPED"
    )

    print(
        f"Total runtime: "
        f"{format_duration(time.monotonic() - process_started)}"
    )

    print(
        "No additional pipeline runs will start."
    )

    print("=" * 108)


# =============================================================================
# ARGUMENTS AND MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete Polymarket intelligence "
            "stack once or continuously."
        )
    )

    parser.add_argument(
        "--continuous",
        action="store_true",
        help=(
            "Repeat the selected pipeline on a schedule."
        ),
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=(
            DEFAULT_FULL_INTERVAL_SECONDS
        ),
        help=(
            "Seconds between continuous pipeline runs."
        ),
    )

    parser.add_argument(
        "--status-interval",
        type=int,
        default=(
            DEFAULT_STATUS_INTERVAL_SECONDS
        ),
        help=(
            "Seconds between continuous status messages."
        ),
    )

    parser.add_argument(
        "--seconds",
        type=int,
        default=(
            DEFAULT_TEST_SECONDS
        ),
        help=(
            "Stop continuous mode after this many seconds. "
            "Use 0 for unlimited."
        ),
    )

    parser.add_argument(
        "--status-only",
        action="store_true",
        help=(
            "Run only market-status and downstream "
            "intelligence steps."
        ),
    )

    parser.add_argument(
        "--skip-wallet-refresh",
        action="store_true",
        help=(
            "Skip wallet scanner, ratings, intelligence "
            "and overlap steps."
        ),
    )

    parser.add_argument(
        "--continue-on-required-failure",
        action="store_true",
        help=(
            "Continue the run even if a required step fails."
        ),
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=10,
        help=(
            "Display limit passed to supported engines."
        ),
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8_output()

    arguments = parse_arguments()

    arguments.interval = max(
        arguments.interval,
        60,
    )

    arguments.status_interval = max(
        arguments.status_interval,
        5,
    )

    arguments.seconds = max(
        arguments.seconds,
        0,
    )

    arguments.display_limit = max(
        arguments.display_limit,
        1,
    )

    ensure_directories()
    create_pipeline_tables()

    shutdown = ShutdownController()

    signal.signal(
        signal.SIGINT,
        shutdown.request_shutdown,
    )

    try:
        signal.signal(
            signal.SIGTERM,
            shutdown.request_shutdown,
        )
    except (AttributeError, ValueError):
        pass

    display_configuration(
        arguments
    )

    if arguments.continuous:
        run_continuously(
            arguments=arguments,
            shutdown=shutdown,
        )

        return

    mode = (
        "STATUS_ONLY"
        if arguments.status_only
        else "FULL"
    )

    result = run_pipeline_once(
        mode=mode,
        shutdown=shutdown,
        continue_on_required_failure=(
            arguments.continue_on_required_failure
        ),
        status_only=(
            arguments.status_only
        ),
        skip_wallet_refresh=(
            arguments.skip_wallet_refresh
        ),
        display_limit=(
            arguments.display_limit
        ),
    )

    if result.status == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()