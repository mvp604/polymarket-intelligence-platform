from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
RUNTIME_DIRECTORY = PROJECT_ROOT / "runtime"
STATUS_PATH = RUNTIME_DIRECTORY / "platform_job_status.json"
REPORTS_PATH = PROJECT_ROOT / "reports"


def connect_database() -> sqlite3.Connection:
    """Open the local SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Check whether a SQLite table exists."""

    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def safe_query(
    query: str,
    parameters: tuple[Any, ...] = (),
) -> pd.DataFrame:
    """Run a query and return a DataFrame."""

    connection = connect_database()

    try:
        return pd.read_sql_query(
            query,
            connection,
            params=parameters,
        )

    finally:
        connection.close()


def safe_int(value: Any) -> int:
    """Convert a value into an integer safely."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_datetime(value: Any) -> datetime | None:
    """Parse a stored ISO timestamp."""

    if not value:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)

    except ValueError:
        return None


def format_timestamp(value: Any) -> str:
    """Format an ISO timestamp for dashboard display."""

    parsed = parse_datetime(value)

    if parsed is None:
        return "No data"

    return parsed.strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def age_label(value: Any) -> str:
    """Describe how old a timestamp is."""

    parsed = parse_datetime(value)

    if parsed is None:
        return "Unknown"

    age_seconds = max(
        (
            datetime.now(timezone.utc) - parsed
        ).total_seconds(),
        0,
    )

    if age_seconds < 60:
        return "Just now"

    if age_seconds < 3600:
        minutes = int(age_seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    if age_seconds < 86400:
        hours = int(age_seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = int(age_seconds // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def freshness_state(value: Any) -> str:
    """Classify data freshness."""

    parsed = parse_datetime(value)

    if parsed is None:
        return "NO DATA"

    age_hours = (
        datetime.now(timezone.utc) - parsed
    ).total_seconds() / 3600

    if age_hours <= 1:
        return "FRESH"

    if age_hours <= 6:
        return "RECENT"

    if age_hours <= 24:
        return "AGING"

    return "STALE"


def load_latest_timestamp(
    table_name: str,
    column_name: str,
) -> str:
    """Load the newest timestamp from one table."""

    connection = connect_database()

    try:
        if not table_exists(
            connection,
            table_name,
        ):
            return ""

        row = connection.execute(
            f"""
            SELECT MAX({column_name}) AS latest
            FROM {table_name}
            """
        ).fetchone()

        if row is None:
            return ""

        return str(row["latest"] or "")

    finally:
        connection.close()


def load_table_count(table_name: str) -> int:
    """Return the number of rows in one table."""

    connection = connect_database()

    try:
        if not table_exists(
            connection,
            table_name,
        ):
            return 0

        row = connection.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM {table_name}
            """
        ).fetchone()

        return safe_int(
            row["total"] if row else 0
        )

    finally:
        connection.close()


def load_background_status() -> dict[str, Any]:
    """Load the newest dashboard job status."""

    if not STATUS_PATH.exists():
        return {
            "title": "None",
            "status": "NEVER RUN",
            "started_at": "",
            "finished_at": "",
            "message": (
                "No dashboard-triggered job has run yet."
            ),
            "return_code": None,
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
            "title": "Unknown",
            "status": "STATUS ERROR",
            "started_at": "",
            "finished_at": "",
            "message": (
                "The runtime status file could not be read."
            ),
            "return_code": None,
        }


def find_latest_ai_report() -> Path | None:
    """Find the newest saved AI report."""

    REPORTS_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    candidates = [
        path
        for path in REPORTS_PATH.iterdir()
        if path.is_file()
        and path.suffix.lower() in {
            ".txt",
            ".md",
        }
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


def load_health_rows() -> list[dict[str, Any]]:
    """Load the latest timestamp and count for each system area."""

    rows = [
        {
            "component": "Wallet Scanner",
            "table": "wallet_scans",
            "timestamp_column": "scanned_at",
        },
        {
            "component": "Positions",
            "table": "positions",
            "timestamp_column": "",
        },
        {
            "component": "Consensus Engine",
            "table": "consensus_history",
            "timestamp_column": "scanned_at",
        },
        {
            "component": "Wallet Ratings",
            "table": "wallet_rating_history",
            "timestamp_column": "rated_at",
        },
        {
            "component": "Alert Engine",
            "table": "alerts",
            "timestamp_column": "created_at",
        },
        {
            "component": "Backtesting",
            "table": "backtest_results",
            "timestamp_column": "evaluated_at",
        },
    ]

    results: list[dict[str, Any]] = []

    wallet_scan_time = load_latest_timestamp(
        "wallet_scans",
        "scanned_at",
    )

    for row in rows:
        timestamp_column = row[
            "timestamp_column"
        ]

        if timestamp_column:
            latest = load_latest_timestamp(
                row["table"],
                timestamp_column,
            )
        else:
            latest = wallet_scan_time

        results.append(
            {
                "Component": row["component"],
                "Records": load_table_count(
                    row["table"]
                ),
                "Latest Update": format_timestamp(
                    latest
                ),
                "Age": age_label(latest),
                "Freshness": freshness_state(
                    latest
                ),
            }
        )

    latest_report = find_latest_ai_report()

    if latest_report is None:
        report_timestamp = ""
        report_name = "No report"
    else:
        report_timestamp = datetime.fromtimestamp(
            latest_report.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()

        report_name = latest_report.name

    results.append(
        {
            "Component": "AI Research Report",
            "Records": (
                len(
                    [
                        path
                        for path in REPORTS_PATH.iterdir()
                        if path.is_file()
                        and path.suffix.lower()
                        in {".txt", ".md"}
                    ]
                )
                if REPORTS_PATH.exists()
                else 0
            ),
            "Latest Update": (
                format_timestamp(
                    report_timestamp
                )
                if report_timestamp
                else report_name
            ),
            "Age": age_label(
                report_timestamp
            ),
            "Freshness": freshness_state(
                report_timestamp
            ),
        }
    )

    return results


def display_job_health() -> None:
    """Display the most recent full-platform job."""

    status = load_background_status()

    st.subheader("Latest Platform Run")

    column_1, column_2, column_3, column_4 = st.columns(4)

    column_1.metric(
        "Job",
        str(status.get("title") or "None"),
    )

    column_2.metric(
        "Status",
        str(status.get("status") or "UNKNOWN"),
    )

    column_3.metric(
        "Started",
        format_timestamp(
            status.get("started_at")
        ),
    )

    column_4.metric(
        "Finished",
        format_timestamp(
            status.get("finished_at")
        ),
    )

    status_name = str(
        status.get("status") or "UNKNOWN"
    )

    message = str(
        status.get("message") or ""
    )

    if status_name == "COMPLETED":
        st.success(message)

    elif status_name == "RUNNING":
        st.info(message)

    elif status_name in {
        "FAILED",
        "STATUS ERROR",
    }:
        st.error(message)

    else:
        st.caption(message)


def display_component_health() -> None:
    """Display freshness and row counts for platform components."""

    st.subheader("Data Freshness")

    health_rows = load_health_rows()
    frame = pd.DataFrame(health_rows)

    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Records": st.column_config.NumberColumn(
                format="%d",
            ),
        },
    )

    stale_components = frame[
        frame["Freshness"].isin(
            [
                "STALE",
                "NO DATA",
            ]
        )
    ]

    if stale_components.empty:
        st.success(
            "All tracked components contain current or recent data."
        )

    else:
        names = ", ".join(
            stale_components[
                "Component"
            ].tolist()
        )

        st.warning(
            f"Components requiring attention: {names}"
        )


def display_database_summary() -> None:
    """Display high-level database totals."""

    st.subheader("Database Summary")

    wallet_count = 0

    connection = connect_database()

    try:
        if table_exists(
            connection,
            "wallet_scans",
        ):
            row = connection.execute(
                """
                SELECT COUNT(DISTINCT wallet) AS total
                FROM wallet_scans
                """
            ).fetchone()

            wallet_count = safe_int(
                row["total"] if row else 0
            )

    finally:
        connection.close()

    column_1, column_2, column_3, column_4 = st.columns(4)

    column_1.metric(
        "Distinct Wallets",
        wallet_count,
    )

    column_2.metric(
        "Stored Positions",
        load_table_count("positions"),
    )

    column_3.metric(
        "Consensus Snapshots",
        load_table_count(
            "consensus_history"
        ),
    )

    column_4.metric(
        "Stored Alerts",
        load_table_count("alerts"),
    )


def render_platform_health() -> None:
    """Render the complete platform-health panel."""

    st.subheader("Platform Health")

    st.caption(
        "Confirm that every engine and dataset is current "
        "before relying on platform research."
    )

    display_job_health()

    st.divider()

    display_database_summary()

    st.divider()

    display_component_health()