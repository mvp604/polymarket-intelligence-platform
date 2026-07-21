from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = PROJECT_ROOT / "src"
LOG_DIRECTORY = PROJECT_ROOT / "logs"


DEFAULT_STEPS = [
    ("Wallet Scanner", "watchlist_scanner.py"),
    ("Wallet Ratings", "wallet_rating_engine.py"),
    ("Wallet Intelligence", "wallet_intelligence_engine.py"),
    ("Portfolio Overlap", "portfolio_overlap_engine.py"),
    ("Conviction Engine", "conviction_engine.py"),
    ("Weighted Consensus", "weighted_consensus_engine.py"),
    ("Alert Engine", "alert_engine.py"),
    ("Backtesting Engine", "backtesting_engine.py"),
    ("ML Ranking Engine", "ml_ranking_engine.py"),
]


AI_STEP = (
    "AI Research Engine",
    "ai_research_engine.py",
)


def configure_utf8_output() -> None:
    """Force UTF-8 terminal output when supported."""

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


def safe_console_write(text: str) -> None:
    """Write console output without Unicode encoding crashes."""

    try:
        sys.stdout.write(text)
        sys.stdout.flush()

    except UnicodeEncodeError:
        encoding = (
            getattr(
                sys.stdout,
                "encoding",
                None,
            )
            or "utf-8"
        )

        safe_text = text.encode(
            encoding,
            errors="replace",
        ).decode(
            encoding,
            errors="replace",
        )

        sys.stdout.write(safe_text)
        sys.stdout.flush()


def build_environment() -> dict[str, str]:
    """Build a UTF-8 subprocess environment."""

    environment = dict(os.environ)

    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"

    return environment


def run_script(
    step_number: int,
    total_steps: int,
    title: str,
    filename: str,
    log_file: TextIO,
) -> bool:
    """Run one platform engine and stream its output."""

    script_path = SRC_DIRECTORY / filename

    print()
    print("=" * 100)
    print(
        f"STEP {step_number} OF "
        f"{total_steps}: {title}"
    )
    print("=" * 100)

    log_file.write("\n")
    log_file.write("=" * 100 + "\n")
    log_file.write(
        f"STEP {step_number} OF "
        f"{total_steps}: {title}\n"
    )
    log_file.write("=" * 100 + "\n")
    log_file.flush()

    if not script_path.exists():
        message = (
            f"Missing script: {script_path}"
        )

        print(message)
        log_file.write(message + "\n")
        log_file.flush()

        return False

    started_at = time.perf_counter()

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                str(script_path),
            ],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=build_environment(),
        )

    except Exception as error:
        elapsed = (
            time.perf_counter()
            - started_at
        )

        message = (
            f"FAILED: Could not start "
            f"{title}: {error}"
        )

        print(message)

        log_file.write(
            message + "\n"
        )
        log_file.flush()

        print(
            f"Elapsed: {elapsed:.1f} seconds"
        )

        return False

    if process.stdout is not None:
        for line in process.stdout:
            safe_console_write(line)

            log_file.write(line)
            log_file.flush()

    return_code = process.wait()

    elapsed = (
        time.perf_counter()
        - started_at
    )

    if return_code == 0:
        result = (
            f"\nCOMPLETED: {title} "
            f"in {elapsed:.1f} seconds."
        )

        print(result)

        log_file.write(
            result + "\n"
        )
        log_file.flush()

        return True

    result = (
        f"\nFAILED: {title} returned "
        f"exit code {return_code} "
        f"after {elapsed:.1f} seconds."
    )

    print(result)

    log_file.write(
        result + "\n"
    )
    log_file.flush()

    return False


def parse_arguments() -> argparse.Namespace:
    """Read optional command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Run the Polymarket Intelligence "
            "Platform pipeline in strict order."
        )
    )

    parser.add_argument(
        "--include-ai",
        action="store_true",
        help=(
            "Run the OpenAI-powered AI Research "
            "Engine after all local engines. "
            "This may use paid API credits."
        ),
    )

    return parser.parse_args()


def display_run_header(
    started_at: datetime,
    log_path: Path,
    step_count: int,
    include_ai: bool,
) -> None:
    """Display full-run metadata."""

    print()
    print("=" * 100)
    print(
        "POLYMARKET INTELLIGENCE "
        "PLATFORM - FULL RUN"
    )
    print("=" * 100)

    print(
        f"Started: "
        f"{started_at.isoformat()}"
    )

    print(
        f"Python: {sys.executable}"
    )

    print(
        f"Project: {PROJECT_ROOT}"
    )

    print(
        f"Log: {log_path}"
    )

    print(
        f"Steps scheduled: {step_count}"
    )

    print(
        "AI research: "
        + (
            "ENABLED"
            if include_ai
            else "DISABLED"
        )
    )

    print("=" * 100)


def write_log_header(
    log_file: TextIO,
    started_at: datetime,
    include_ai: bool,
) -> None:
    """Write run metadata into the log."""

    log_file.write(
        "POLYMARKET INTELLIGENCE "
        "PLATFORM - FULL RUN\n"
    )

    log_file.write(
        f"Started: "
        f"{started_at.isoformat()}\n"
    )

    log_file.write(
        f"Python: {sys.executable}\n"
    )

    log_file.write(
        f"Project: {PROJECT_ROOT}\n"
    )

    log_file.write(
        "AI research: "
        + (
            "ENABLED"
            if include_ai
            else "DISABLED"
        )
        + "\n"
    )

    log_file.flush()


def display_run_summary(
    finished_at: datetime,
    elapsed_seconds: float,
    successful_steps: list[str],
    failed_steps: list[str],
    log_path: Path,
) -> None:
    """Display the final pipeline summary."""

    print()
    print("=" * 100)
    print("PLATFORM RUN SUMMARY")
    print("=" * 100)

    print(
        f"Finished: "
        f"{finished_at.isoformat()}"
    )

    print(
        f"Elapsed: "
        f"{elapsed_seconds:.1f} seconds"
    )

    print(
        f"Successful steps: "
        f"{len(successful_steps)}"
    )

    print(
        f"Failed steps: "
        f"{len(failed_steps)}"
    )

    if successful_steps:
        print()
        print("Completed:")

        for title in successful_steps:
            print(
                f"  [OK] {title}"
            )

    if failed_steps:
        print()
        print("Failed:")

        for title in failed_steps:
            print(
                f"  [FAILED] {title}"
            )

    print()
    print(
        f"Full log saved to: "
        f"{log_path}"
    )

    print("=" * 100)


def write_run_summary(
    log_file: TextIO,
    finished_at: datetime,
    elapsed_seconds: float,
    successful_steps: list[str],
    failed_steps: list[str],
) -> None:
    """Write the final summary into the run log."""

    log_file.write("\n")
    log_file.write("=" * 100 + "\n")
    log_file.write(
        "PLATFORM RUN SUMMARY\n"
    )
    log_file.write("=" * 100 + "\n")

    log_file.write(
        f"Finished: "
        f"{finished_at.isoformat()}\n"
    )

    log_file.write(
        f"Elapsed: "
        f"{elapsed_seconds:.1f} seconds\n"
    )

    log_file.write(
        f"Successful steps: "
        f"{len(successful_steps)}\n"
    )

    log_file.write(
        f"Failed steps: "
        f"{len(failed_steps)}\n"
    )

    if successful_steps:
        log_file.write("\nCompleted:\n")

        for title in successful_steps:
            log_file.write(
                f"  [OK] {title}\n"
            )

    if failed_steps:
        log_file.write("\nFailed:\n")

        for title in failed_steps:
            log_file.write(
                f"  [FAILED] {title}\n"
            )

    log_file.flush()


def main() -> None:
    """Run the strict intelligence-platform pipeline."""

    configure_utf8_output()

    arguments = parse_arguments()

    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_started_at = datetime.now(
        timezone.utc
    )

    log_name = (
        "platform_run_"
        + run_started_at.strftime(
            "%Y%m%d_%H%M%S"
        )
        + ".log"
    )

    log_path = (
        LOG_DIRECTORY / log_name
    )

    steps = list(DEFAULT_STEPS)

    if arguments.include_ai:
        steps.append(AI_STEP)

    display_run_header(
        started_at=run_started_at,
        log_path=log_path,
        step_count=len(steps),
        include_ai=arguments.include_ai,
    )

    successful_steps: list[str] = []
    failed_steps: list[str] = []

    with log_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as log_file:

        write_log_header(
            log_file=log_file,
            started_at=run_started_at,
            include_ai=arguments.include_ai,
        )

        for number, (
            title,
            filename,
        ) in enumerate(
            steps,
            start=1,
        ):
            succeeded = run_script(
                step_number=number,
                total_steps=len(steps),
                title=title,
                filename=filename,
                log_file=log_file,
            )

            if succeeded:
                successful_steps.append(
                    title
                )

            else:
                failed_steps.append(
                    title
                )

                print()
                print(
                    "Pipeline stopped because "
                    "a required engine failed."
                )

                print(
                    "Fix the failed engine, then "
                    "rerun the full platform."
                )

                break

        finished_at = datetime.now(
            timezone.utc
        )

        elapsed_seconds = (
            finished_at
            - run_started_at
        ).total_seconds()

        display_run_summary(
            finished_at=finished_at,
            elapsed_seconds=elapsed_seconds,
            successful_steps=successful_steps,
            failed_steps=failed_steps,
            log_path=log_path,
        )

        write_run_summary(
            log_file=log_file,
            finished_at=finished_at,
            elapsed_seconds=elapsed_seconds,
            successful_steps=successful_steps,
            failed_steps=failed_steps,
        )

    if failed_steps:
        raise SystemExit(1)


if __name__ == "__main__":
    main()