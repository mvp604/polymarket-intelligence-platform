from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = PROJECT_ROOT / "src"
RUNTIME_DIRECTORY = PROJECT_ROOT / "runtime"

BACKGROUND_RUNNER = SRC_DIRECTORY / "background_job.py"
STATUS_PATH = RUNTIME_DIRECTORY / "platform_job_status.json"
OUTPUT_PATH = RUNTIME_DIRECTORY / "platform_job_output.log"

MAX_OUTPUT_CHARACTERS = 30_000


def load_status() -> dict[str, Any]:
    """Load the latest background-job status."""

    if not STATUS_PATH.exists():
        return {
            "job_type": "",
            "title": "None",
            "status": "NEVER RUN",
            "started_at": "",
            "finished_at": "",
            "return_code": None,
            "message": (
                "No dashboard job has been started yet."
            ),
        }

    try:
        return json.loads(
            STATUS_PATH.read_text(
                encoding="utf-8",
            )
        )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {
            "job_type": "",
            "title": "Unknown",
            "status": "STATUS ERROR",
            "started_at": "",
            "finished_at": "",
            "return_code": None,
            "message": (
                "The background status file could not be read."
            ),
        }


def load_output() -> str:
    """Load the newest background-job console output."""

    if not OUTPUT_PATH.exists():
        return ""

    try:
        output = OUTPUT_PATH.read_text(
            encoding="utf-8",
            errors="replace",
        )

    except OSError as error:
        return f"Could not read output log: {error}"

    return output[-MAX_OUTPUT_CHARACTERS:]


def launch_background_job(
    job_type: str,
) -> tuple[bool, str]:
    """
    Launch a job independently from the Streamlit page process.

    The process remains alive if the browser refreshes or disconnects.
    """

    if not BACKGROUND_RUNNER.exists():
        return (
            False,
            f"Missing runner: {BACKGROUND_RUNNER}",
        )

    RUNTIME_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        sys.executable,
        str(BACKGROUND_RUNNER),
        job_type,
    ]

    creation_flags = 0

    if os.name == "nt":
        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
        )

    try:
        subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            close_fds=True,
        )

    except Exception as error:
        return (
            False,
            f"Could not launch background job: {error}",
        )

    return (
        True,
        "The job was launched successfully.",
    )


def display_job_status(
    status: dict[str, Any],
) -> None:
    """Display current or most recent job status."""

    st.subheader("Platform Job Status")

    status_name = str(
        status.get("status") or "UNKNOWN"
    )

    column_1, column_2, column_3 = st.columns(3)

    column_1.metric(
        "Job",
        str(status.get("title") or "None"),
    )

    column_2.metric(
        "Status",
        status_name,
    )

    finished_at = (
        status.get("finished_at")
        or status.get("started_at")
        or "Not yet"
    )

    column_3.metric(
        "Last Updated",
        str(finished_at),
    )

    message = str(
        status.get("message") or ""
    )

    if status_name == "RUNNING":
        st.info(message)

    elif status_name == "COMPLETED":
        st.success(message)

    elif status_name in {
        "FAILED",
        "STATUS ERROR",
    }:
        st.error(message)

    else:
        st.caption(message)


def display_console_output() -> None:
    """Display the latest background console output."""

    output = load_output()

    if not output:
        st.caption(
            "No dashboard job output is available yet."
        )
        return

    with st.expander(
        "View live platform console",
        expanded=True,
    ):
        st.code(
            output,
            language="text",
        )


@st.fragment(run_every="3s")
def render_live_job_monitor() -> None:
    """
    Refresh only the status area every three seconds.

    This does not rerun the complete dashboard.
    """

    status = load_status()

    display_job_status(status)
    display_console_output()

    if status.get("status") == "RUNNING":
        st.caption(
            "This panel refreshes automatically every "
            "three seconds."
        )
    else:
        if st.button(
            "Refresh Dashboard Data",
            width="stretch",
            key="refresh_dashboard_after_job",
        ):
            st.rerun()


def render_platform_controls() -> None:
    """Render separate local-pipeline and AI-report buttons."""

    status = load_status()
    job_running = (
        status.get("status") == "RUNNING"
    )

    st.subheader("Platform Controls")

    st.caption(
        "The local platform pipeline and paid AI report "
        "are intentionally separate."
    )

    local_column, ai_column = st.columns(2)

    with local_column:
        with st.container(border=True):
            st.markdown("### ▶ Run Full Platform")

            st.write(
                "Runs every required local engine in order:"
            )

            st.markdown(
                """
- Wallet scanner
- Wallet rating engine
- Conviction engine
- Weighted consensus
- Alert engine
- Backtesting engine
- ML ranking engine
"""
            )

            st.success(
                "This does not use OpenAI API credits."
            )

            local_clicked = st.button(
                "▶ Run Full Platform",
                type="primary",
                width="stretch",
                disabled=job_running,
                key="launch_full_platform",
            )

    with ai_column:
        with st.container(border=True):
            st.markdown("### ✨ Generate AI Report")

            st.write(
                "Runs only the OpenAI-powered research engine."
            )

            st.markdown(
                """
- Reads the newest completed platform data
- Creates a fresh research brief
- Saves it in the reports folder
- Updates the AI Command Center
"""
            )

            st.warning(
                "This action uses OpenAI API credits."
            )

            ai_clicked = st.button(
                "✨ Generate AI Report",
                width="stretch",
                disabled=job_running,
                key="launch_ai_report",
            )

    if local_clicked:
        launched, message = launch_background_job(
            "full_platform"
        )

        if launched:
            st.success(message)
            st.info(
                "The full pipeline is now running in the "
                "background. You may change tabs or refresh."
            )
            st.rerun()

        else:
            st.error(message)

    if ai_clicked:
        launched, message = launch_background_job(
            "ai_report"
        )

        if launched:
            st.success(message)
            st.warning(
                "The AI report is running and may consume "
                "OpenAI credits."
            )
            st.rerun()

        else:
            st.error(message)

    st.divider()

    render_live_job_monitor()