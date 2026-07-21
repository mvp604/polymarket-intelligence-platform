from __future__ import annotations

import argparse
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TextIO

from market_monitor_database import create_market_monitor_tables


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = PROJECT_ROOT / "src"
LOG_DIRECTORY = PROJECT_ROOT / "logs"
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

MARKET_STATUS_SCRIPT = SRC_DIRECTORY / "market_status_engine.py"
FULL_PLATFORM_SCRIPT = SRC_DIRECTORY / "run_platform.py"
SPORTS_LISTENER_SCRIPT = SRC_DIRECTORY / "sports_live_listener.py"

LOCK_NAME = "continuous_monitor"
LOCK_EXPIRY_SECONDS = 300
LOCK_HEARTBEAT_SECONDS = 60

DEFAULT_STATUS_INTERVAL_SECONDS = 180
DEFAULT_FULL_PIPELINE_INTERVAL_SECONDS = 3600
DEFAULT_LISTENER_RESTART_DELAY_SECONDS = 5

LOOP_SLEEP_SECONDS = 1

STOP_REQUESTED = threading.Event()

ACTIVE_ENGINE_PROCESS: subprocess.Popen[str] | None = None
SPORTS_LISTENER_PROCESS: subprocess.Popen[str] | None = None
SPORTS_LISTENER_LOG: TextIO | None = None

PROCESS_LOCK = threading.Lock()


# =============================================================================
# OUTPUT AND TIME HELPERS
# =============================================================================


def configure_utf8_output() -> None:
    """Configure terminal output safely on Windows."""

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
    """Return the current timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC time as ISO text."""

    return utc_now().isoformat()


def parse_datetime(value: Any) -> datetime | None:
    """Parse stored ISO datetime text."""

    text = str(value or "").strip()

    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(timezone.utc)


def format_duration(seconds: float) -> str:
    """Format a duration as HH:MM:SS."""

    seconds = max(int(seconds), 0)

    hours, remainder = divmod(
        seconds,
        3600,
    )

    minutes, seconds_left = divmod(
        remainder,
        60,
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds_left:02d}"
    )


def format_countdown(
    target_time: datetime | None,
) -> str:
    """Format time remaining until a scheduled action."""

    if target_time is None:
        return "not scheduled"

    remaining = (
        target_time - utc_now()
    ).total_seconds()

    if remaining <= 0:
        return "due now"

    return format_duration(remaining)


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Convert a value into an integer safely."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# =============================================================================
# DATABASE
# =============================================================================


def connect_database() -> sqlite3.Connection:
    """Open the platform SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}."
        )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )
    connection.execute(
        "PRAGMA journal_mode = WAL"
    )
    connection.execute(
        "PRAGMA busy_timeout = 30000"
    )

    return connection


def load_setting(
    key: str,
    default: str,
) -> str:
    """Load one monitor setting."""

    connection = connect_database()

    try:
        row = connection.execute(
            """
            SELECT setting_value
            FROM monitor_settings
            WHERE setting_key = ?
            """,
            (key,),
        ).fetchone()

        if row is None:
            return default

        value = str(
            row["setting_value"]
            or ""
        ).strip()

        return value or default

    finally:
        connection.close()


def update_setting(
    key: str,
    value: str,
    description: str = "",
) -> None:
    """Insert or update one monitor setting."""

    connection = connect_database()

    try:
        connection.execute(
            """
            INSERT INTO monitor_settings (
                setting_key,
                setting_value,
                description,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value =
                    excluded.setting_value,
                description =
                    CASE
                        WHEN excluded.description != ''
                        THEN excluded.description
                        ELSE monitor_settings.description
                    END,
                updated_at =
                    excluded.updated_at
            """,
            (
                key,
                value,
                description,
                utc_now_iso(),
            ),
        )

        connection.commit()

    finally:
        connection.close()


def acquire_monitor_lock() -> bool:
    """
    Acquire the single-instance monitor lock.

    Expired locks are replaced automatically.
    """

    connection = connect_database()

    now = utc_now()
    expires_at = now + timedelta(
        seconds=LOCK_EXPIRY_SECONDS
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            """
            SELECT
                process_id,
                acquired_at,
                expires_at
            FROM monitor_locks
            WHERE lock_name = ?
            """,
            (LOCK_NAME,),
        ).fetchone()

        if existing is not None:
            existing_expiry = parse_datetime(
                existing["expires_at"]
            )

            if (
                existing_expiry is not None
                and existing_expiry > now
            ):
                connection.rollback()

                print()
                print(
                    "Another continuous monitor "
                    "appears to be running."
                )

                print(
                    f"Process ID: "
                    f"{existing['process_id']}"
                )

                print(
                    f"Lock expires: "
                    f"{existing['expires_at']}"
                )

                return False

            connection.execute(
                """
                DELETE FROM monitor_locks
                WHERE lock_name = ?
                """,
                (LOCK_NAME,),
            )

        connection.execute(
            """
            INSERT INTO monitor_locks (
                lock_name,
                process_id,
                acquired_at,
                expires_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                LOCK_NAME,
                os.getpid(),
                now.isoformat(),
                expires_at.isoformat(),
            ),
        )

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def refresh_monitor_lock() -> None:
    """Extend the active monitor lock."""

    now = utc_now()
    expires_at = now + timedelta(
        seconds=LOCK_EXPIRY_SECONDS
    )

    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            UPDATE monitor_locks
            SET
                process_id = ?,
                acquired_at = ?,
                expires_at = ?
            WHERE lock_name = ?
            """,
            (
                os.getpid(),
                now.isoformat(),
                expires_at.isoformat(),
                LOCK_NAME,
            ),
        )

        if cursor.rowcount == 0:
            raise RuntimeError(
                "The continuous-monitor lock was lost."
            )

        connection.commit()

    finally:
        connection.close()


def release_monitor_lock() -> None:
    """Release the continuous-monitor lock."""

    connection = connect_database()

    try:
        connection.execute(
            """
            DELETE FROM monitor_locks
            WHERE lock_name = ?
              AND process_id = ?
            """,
            (
                LOCK_NAME,
                os.getpid(),
            ),
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# LOGGING
# =============================================================================


def create_log_path(
    prefix: str,
) -> Path:
    """Create a timestamped log path."""

    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = utc_now().strftime(
        "%Y%m%d_%H%M%S"
    )

    return (
        LOG_DIRECTORY
        / f"{prefix}_{timestamp}.log"
    )


def build_subprocess_environment() -> dict[str, str]:
    """Build a UTF-8 subprocess environment."""

    environment = dict(os.environ)

    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"

    return environment


def windows_creation_flags() -> int:
    """Return safe subprocess flags for Windows."""

    if os.name != "nt":
        return 0

    return getattr(
        subprocess,
        "CREATE_NEW_PROCESS_GROUP",
        0,
    )


# =============================================================================
# PROCESS CONTROL
# =============================================================================


def set_active_engine_process(
    process: subprocess.Popen[str] | None,
) -> None:
    """Store the currently running scheduled engine."""

    global ACTIVE_ENGINE_PROCESS

    with PROCESS_LOCK:
        ACTIVE_ENGINE_PROCESS = process


def set_listener_process(
    process: subprocess.Popen[str] | None,
) -> None:
    """Store the sports-listener process."""

    global SPORTS_LISTENER_PROCESS

    with PROCESS_LOCK:
        SPORTS_LISTENER_PROCESS = process


def terminate_process(
    process: subprocess.Popen[str] | None,
    title: str,
    timeout_seconds: int = 8,
) -> None:
    """Terminate a child process safely."""

    if process is None:
        return

    if process.poll() is not None:
        return

    print(
        f"Stopping {title}..."
    )

    try:
        process.terminate()
        process.wait(
            timeout=timeout_seconds
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


def stop_all_child_processes() -> None:
    """Stop active scheduled and listener processes."""

    with PROCESS_LOCK:
        engine_process = (
            ACTIVE_ENGINE_PROCESS
        )

        listener_process = (
            SPORTS_LISTENER_PROCESS
        )

    terminate_process(
        engine_process,
        "active engine",
    )

    terminate_process(
        listener_process,
        "sports listener",
    )


# =============================================================================
# SPORTS LISTENER
# =============================================================================


def close_listener_log() -> None:
    """Close the listener log handle."""

    global SPORTS_LISTENER_LOG

    if SPORTS_LISTENER_LOG is None:
        return

    try:
        SPORTS_LISTENER_LOG.flush()
        SPORTS_LISTENER_LOG.close()
    except Exception:
        pass

    SPORTS_LISTENER_LOG = None


def start_sports_listener() -> bool:
    """Start the continuous sports WebSocket listener."""

    global SPORTS_LISTENER_LOG

    if not SPORTS_LISTENER_SCRIPT.exists():
        print(
            f"Missing listener: "
            f"{SPORTS_LISTENER_SCRIPT}"
        )
        return False

    close_listener_log()

    log_path = create_log_path(
        "sports_listener"
    )

    SPORTS_LISTENER_LOG = log_path.open(
        "a",
        encoding="utf-8",
        errors="replace",
    )

    command = [
        sys.executable,
        "-u",
        str(SPORTS_LISTENER_SCRIPT),
    ]

    try:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=SPORTS_LISTENER_LOG,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=build_subprocess_environment(),
            creationflags=(
                windows_creation_flags()
            ),
        )

    except Exception as error:
        close_listener_log()

        print(
            f"Could not start sports listener: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return False

    set_listener_process(
        process
    )

    print(
        f"Sports listener started "
        f"with PID {process.pid}."
    )

    print(
        f"Sports listener log: "
        f"{log_path}"
    )

    return True


def listener_is_running() -> bool:
    """Return True when the listener process is alive."""

    with PROCESS_LOCK:
        process = SPORTS_LISTENER_PROCESS

    return (
        process is not None
        and process.poll() is None
    )


def check_and_restart_listener(
    listener_enabled: bool,
    next_restart_at: datetime | None,
) -> datetime | None:
    """Restart the listener if it exited."""

    if not listener_enabled:
        return None

    if listener_is_running():
        return None

    now = utc_now()

    if (
        next_restart_at is not None
        and now < next_restart_at
    ):
        return next_restart_at

    with PROCESS_LOCK:
        old_process = (
            SPORTS_LISTENER_PROCESS
        )

    if old_process is not None:
        return_code = old_process.poll()

        print(
            f"Sports listener stopped "
            f"with exit code {return_code}."
        )

    close_listener_log()
    set_listener_process(None)

    started = start_sports_listener()

    if started:
        return None

    return now + timedelta(
        seconds=(
            DEFAULT_LISTENER_RESTART_DELAY_SECONDS
        )
    )


# =============================================================================
# SCHEDULED ENGINE RUNNER
# =============================================================================


def run_engine(
    title: str,
    script_path: Path,
    log_prefix: str,
) -> bool:
    """Run one scheduled engine and wait for completion."""

    if not script_path.exists():
        print(
            f"Missing script: {script_path}"
        )
        return False

    log_path = create_log_path(
        log_prefix
    )

    print()
    print("=" * 92)
    print(f"STARTING: {title}")
    print("=" * 92)
    print(f"Started: {utc_now_iso()}")
    print(f"Log: {log_path}")

    started_at = time.perf_counter()

    with log_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as log_file:

        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    str(script_path),
                ],
                cwd=PROJECT_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=(
                    build_subprocess_environment()
                ),
                creationflags=(
                    windows_creation_flags()
                ),
            )

        except Exception as error:
            print(
                f"Could not start {title}: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return False

        set_active_engine_process(
            process
        )

        try:
            while process.poll() is None:
                if STOP_REQUESTED.wait(
                    timeout=0.5
                ):
                    terminate_process(
                        process,
                        title,
                    )
                    break

        finally:
            set_active_engine_process(None)

    elapsed = (
        time.perf_counter()
        - started_at
    )

    return_code = process.poll()

    if return_code == 0:
        print(
            f"COMPLETED: {title} "
            f"in {elapsed:.1f} seconds."
        )
        return True

    if STOP_REQUESTED.is_set():
        print(
            f"STOPPED: {title} "
            f"during monitor shutdown."
        )
        return False

    print(
        f"FAILED: {title} returned "
        f"exit code {return_code} "
        f"after {elapsed:.1f} seconds."
    )

    print(
        f"Review log: {log_path}"
    )

    return False


# =============================================================================
# SIGNAL HANDLING
# =============================================================================


def request_shutdown(
    reason: str,
) -> None:
    """Request a clean monitor shutdown."""

    if STOP_REQUESTED.is_set():
        return

    STOP_REQUESTED.set()

    print()
    print(reason)
    print(
        "Stopping continuous monitoring..."
    )

    stop_all_child_processes()


def signal_handler(
    signal_number: int,
    frame: Any,
) -> None:
    """Handle Ctrl+C and termination signals."""

    del signal_number
    del frame

    request_shutdown(
        "Shutdown requested by Ctrl+C."
    )


def install_signal_handlers() -> None:
    """Install shutdown signal handlers."""

    signal.signal(
        signal.SIGINT,
        signal_handler,
    )

    if hasattr(signal, "SIGTERM"):
        signal.signal(
            signal.SIGTERM,
            signal_handler,
        )


# =============================================================================
# ARGUMENTS
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    """Read command-line options."""

    parser = argparse.ArgumentParser(
        description=(
            "Run continuous Polymarket monitoring, "
            "live sports updates and scheduled "
            "platform refreshes."
        )
    )

    parser.add_argument(
        "--seconds",
        type=int,
        default=0,
        help=(
            "Optional test duration. "
            "Use 0 to run continuously."
        ),
    )

    parser.add_argument(
        "--status-interval",
        type=int,
        default=0,
        help=(
            "Override the market-status refresh "
            "interval in seconds."
        ),
    )

    parser.add_argument(
        "--full-interval",
        type=int,
        default=0,
        help=(
            "Override the full-platform refresh "
            "interval in seconds."
        ),
    )

    parser.add_argument(
        "--run-full-now",
        action="store_true",
        help=(
            "Run the complete nine-engine pipeline "
            "immediately at startup."
        ),
    )

    parser.add_argument(
        "--no-listener",
        action="store_true",
        help=(
            "Disable the live sports WebSocket "
            "listener for this run."
        ),
    )

    parser.add_argument(
        "--status-only",
        action="store_true",
        help=(
            "Run recurring market-status refreshes "
            "without the full platform pipeline."
        ),
    )

    return parser.parse_args()


# =============================================================================
# MONITOR STATUS
# =============================================================================


def display_monitor_header(
    status_interval: int,
    full_interval: int,
    listener_enabled: bool,
    run_full_now: bool,
    maximum_seconds: int,
) -> None:
    """Display monitor startup information."""

    print()
    print("=" * 92)
    print(
        "POLYMARKET CONTINUOUS "
        "MONITOR v1.1"
    )
    print("=" * 92)

    print(
        f"Process ID:               "
        f"{os.getpid()}"
    )

    print(
        f"Project:                  "
        f"{PROJECT_ROOT}"
    )

    print(
        f"Python:                   "
        f"{sys.executable}"
    )

    print(
        f"Status refresh interval:  "
        f"{status_interval} seconds"
    )

    print(
        f"Full pipeline interval:   "
        f"{full_interval} seconds"
    )

    print(
        f"Sports listener:          "
        f"{'ENABLED' if listener_enabled else 'DISABLED'}"
    )

    print(
        f"Run full immediately:     "
        f"{run_full_now}"
    )

    if maximum_seconds > 0:
        print(
            f"Test duration:            "
            f"{maximum_seconds} seconds"
        )
    else:
        print(
            "Run mode:                 "
            "continuous until Ctrl+C"
        )

    print(
        "AI Research Engine:        "
        "EXCLUDED"
    )

    print("=" * 92)


def display_heartbeat(
    next_status_run: datetime,
    next_full_run: datetime | None,
    listener_enabled: bool,
) -> None:
    """Display a compact monitor heartbeat."""

    listener_status = (
        "RUNNING"
        if listener_enabled
        and listener_is_running()
        else (
            "DISABLED"
            if not listener_enabled
            else "RESTARTING"
        )
    )

    print()
    print(
        f"[MONITOR] "
        f"{utc_now_iso()} | "
        f"Listener: {listener_status} | "
        f"Status refresh: "
        f"{format_countdown(next_status_run)} | "
        f"Full pipeline: "
        f"{format_countdown(next_full_run)}"
    )


# =============================================================================
# MAIN MONITOR LOOP
# =============================================================================


def main() -> None:
    """Run continuous monitoring services."""

    configure_utf8_output()
    install_signal_handlers()

    arguments = parse_arguments()

    create_market_monitor_tables()

    if not acquire_monitor_lock():
        raise SystemExit(1)

    update_setting(
        "continuous_monitor_enabled",
        "1",
        (
            "Master continuous-monitor switch. "
            "Updated automatically while the "
            "monitor is running."
        ),
    )

    status_interval = (
        arguments.status_interval
        if arguments.status_interval > 0
        else safe_int(
            load_setting(
                "fast_monitor_interval_seconds",
                str(
                    DEFAULT_STATUS_INTERVAL_SECONDS
                ),
            ),
            DEFAULT_STATUS_INTERVAL_SECONDS,
        )
    )

    full_interval = (
        arguments.full_interval
        if arguments.full_interval > 0
        else safe_int(
            load_setting(
                "full_pipeline_interval_seconds",
                str(
                    DEFAULT_FULL_PIPELINE_INTERVAL_SECONDS
                ),
            ),
            (
                DEFAULT_FULL_PIPELINE_INTERVAL_SECONDS
            ),
        )
    )

    status_interval = max(
        status_interval,
        30,
    )

    full_interval = max(
        full_interval,
        300,
    )

    listener_enabled = (
        not arguments.no_listener
    )

    full_pipeline_enabled = (
        not arguments.status_only
    )

    maximum_seconds = max(
        arguments.seconds,
        0,
    )

    display_monitor_header(
        status_interval=status_interval,
        full_interval=full_interval,
        listener_enabled=listener_enabled,
        run_full_now=(
            arguments.run_full_now
        ),
        maximum_seconds=maximum_seconds,
    )

    monitor_started_at = utc_now()

    next_status_run = utc_now()

    if (
        full_pipeline_enabled
        and arguments.run_full_now
    ):
        next_full_run: datetime | None = (
            utc_now()
        )
    elif full_pipeline_enabled:
        next_full_run = (
            utc_now()
            + timedelta(
                seconds=full_interval
            )
        )
    else:
        next_full_run = None

    next_lock_refresh = (
        utc_now()
        + timedelta(
            seconds=LOCK_HEARTBEAT_SECONDS
        )
    )

    next_listener_restart: (
        datetime | None
    ) = None

    next_heartbeat = utc_now()

    try:
        if listener_enabled:
            if not start_sports_listener():
                next_listener_restart = (
                    utc_now()
                    + timedelta(
                        seconds=(
                            DEFAULT_LISTENER_RESTART_DELAY_SECONDS
                        )
                    )
                )

        while not STOP_REQUESTED.is_set():
            now = utc_now()

            if (
                maximum_seconds > 0
                and (
                    now
                    - monitor_started_at
                ).total_seconds()
                >= maximum_seconds
            ):
                request_shutdown(
                    "Configured continuous-monitor "
                    "test duration has completed."
                )
                break

            if now >= next_lock_refresh:
                refresh_monitor_lock()

                next_lock_refresh = (
                    now
                    + timedelta(
                        seconds=(
                            LOCK_HEARTBEAT_SECONDS
                        )
                    )
                )

            restart_result = (
                check_and_restart_listener(
                    listener_enabled=(
                        listener_enabled
                    ),
                    next_restart_at=(
                        next_listener_restart
                    ),
                )
            )

            if listener_is_running():
                next_listener_restart = None
            else:
                next_listener_restart = (
                    restart_result
                )

            if (
                next_full_run is not None
                and now >= next_full_run
            ):
                run_engine(
                    title=(
                        "Full Intelligence Platform"
                    ),
                    script_path=(
                        FULL_PLATFORM_SCRIPT
                    ),
                    log_prefix=(
                        "continuous_full_platform"
                    ),
                )

                next_full_run = (
                    utc_now()
                    + timedelta(
                        seconds=full_interval
                    )
                )

                next_status_run = (
                    utc_now()
                    + timedelta(
                        seconds=status_interval
                    )
                )

            elif now >= next_status_run:
                run_engine(
                    title=(
                        "Market Status and T-Minus"
                    ),
                    script_path=(
                        MARKET_STATUS_SCRIPT
                    ),
                    log_prefix=(
                        "continuous_market_status"
                    ),
                )

                next_status_run = (
                    utc_now()
                    + timedelta(
                        seconds=status_interval
                    )
                )

            if now >= next_heartbeat:
                display_heartbeat(
                    next_status_run=(
                        next_status_run
                    ),
                    next_full_run=(
                        next_full_run
                    ),
                    listener_enabled=(
                        listener_enabled
                    ),
                )

                next_heartbeat = (
                    now
                    + timedelta(seconds=60)
                )

            STOP_REQUESTED.wait(
                LOOP_SLEEP_SECONDS
            )

    except Exception as error:
        print()
        print("=" * 92)
        print("CONTINUOUS MONITOR FAILED")
        print("=" * 92)

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        print("=" * 92)

        raise

    finally:
        STOP_REQUESTED.set()

        stop_all_child_processes()
        close_listener_log()

        try:
            update_setting(
                "continuous_monitor_enabled",
                "0",
            )
        except Exception:
            pass

        try:
            release_monitor_lock()
        except Exception:
            pass

    elapsed = (
        utc_now()
        - monitor_started_at
    ).total_seconds()

    print()
    print("=" * 92)
    print("CONTINUOUS MONITOR STOPPED")
    print("=" * 92)

    print(
        f"Total runtime: "
        f"{format_duration(elapsed)}"
    )

    print(
        "Sports listener, status refreshes "
        "and full-pipeline scheduling have stopped."
    )

    print("=" * 92)


if __name__ == "__main__":
    main()