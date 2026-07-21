from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = PROJECT_ROOT / "src"
RUNTIME_DIRECTORY = PROJECT_ROOT / "runtime"
STATUS_PATH = RUNTIME_DIRECTORY / "platform_job_status.json"
OUTPUT_PATH = RUNTIME_DIRECTORY / "platform_job_output.log"


def utc_now() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def write_status(data: dict[str, Any]) -> None:
    """Safely write the current background-job status."""

    RUNTIME_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = STATUS_PATH.with_suffix(".tmp")

    temporary_path.write_text(
        json.dumps(
            data,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(STATUS_PATH)


def parse_arguments() -> argparse.Namespace:
    """Read the requested job type."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "job_type",
        choices=[
            "full_platform",
            "ai_report",
        ],
    )

    return parser.parse_args()


def main() -> None:
    """Run one dashboard-requested job independently."""

    arguments = parse_arguments()

    if arguments.job_type == "full_platform":
        title = "Full Platform"
        command = [
            sys.executable,
            str(SRC_DIRECTORY / "run_platform.py"),
        ]

    else:
        title = "AI Research Report"
        command = [
            sys.executable,
            str(SRC_DIRECTORY / "ai_research_engine.py"),
        ]

    started_at = utc_now()

    status: dict[str, Any] = {
        "job_type": arguments.job_type,
        "title": title,
        "status": "RUNNING",
        "started_at": started_at,
        "finished_at": "",
        "return_code": None,
        "message": f"{title} is running.",
        "output_path": str(OUTPUT_PATH),
    }

    write_status(status)

    RUNTIME_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with OUTPUT_PATH.open(
            "w",
            encoding="utf-8",
        ) as output_file:
            output_file.write(
                f"{title}\n"
                f"Started: {started_at}\n"
                f"Python: {sys.executable}\n"
                f"Project: {PROJECT_ROOT}\n\n"
            )
            output_file.flush()

            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

        return_code = completed.returncode
        finished_at = utc_now()

        if return_code == 0:
            status.update(
                {
                    "status": "COMPLETED",
                    "finished_at": finished_at,
                    "return_code": return_code,
                    "message": (
                        f"{title} completed successfully."
                    ),
                }
            )

        else:
            status.update(
                {
                    "status": "FAILED",
                    "finished_at": finished_at,
                    "return_code": return_code,
                    "message": (
                        f"{title} failed with exit code "
                        f"{return_code}."
                    ),
                }
            )

        write_status(status)

    except Exception as error:
        status.update(
            {
                "status": "FAILED",
                "finished_at": utc_now(),
                "return_code": -1,
                "message": (
                    f"{title} could not be completed: {error}"
                ),
            }
        )

        write_status(status)

        with OUTPUT_PATH.open(
            "a",
            encoding="utf-8",
        ) as output_file:
            output_file.write(
                "\nBACKGROUND JOB ERROR\n"
                f"{type(error).__name__}: {error}\n"
            )

        raise


if __name__ == "__main__":
    main()