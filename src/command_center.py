from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from platform_controls import render_platform_controls
from platform_health import render_platform_health


DATABASE_PATH = Path("database/polymarket.db")
REPORTS_PATH = Path("reports")


def connect_database() -> sqlite3.Connection:
    """Connect to the local SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH.resolve()}."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def table_exists(table_name: str) -> bool:
    """Return True when a SQLite table exists."""

    connection = connect_database()

    try:
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

    finally:
        connection.close()


def safe_query(
    query: str,
    parameters: tuple[Any, ...] = (),
) -> pd.DataFrame:
    """Run a SQLite query and return a pandas DataFrame."""

    connection = connect_database()

    try:
        return pd.read_sql_query(
            query,
            connection,
            params=parameters,
        )

    finally:
        connection.close()


def safe_float(value: Any) -> float:
    """Convert a value to float without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value to integer without crashing."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def format_money(value: Any) -> str:
    """Format a value as currency."""

    return f"${safe_float(value):,.2f}"


def load_top_signals(limit: int = 5) -> pd.DataFrame:
    """Load the strongest current consensus signals."""

    if not table_exists("consensus_history"):
        return pd.DataFrame()

    return safe_query(
        """
        WITH latest_history AS (
            SELECT
                market_id,
                LOWER(TRIM(outcome)) AS normalized_outcome,
                MAX(id) AS latest_id
            FROM consensus_history
            GROUP BY
                market_id,
                LOWER(TRIM(outcome))
        )
        SELECT
            history.market_id,
            history.title,
            history.outcome,
            history.wallet_count,
            history.combined_value,
            history.combined_pnl,
            history.conviction_score,
            history.conviction_grade,
            history.average_entry_price,
            history.average_current_price,
            history.observed_price_move,
            history.scanned_at
        FROM consensus_history AS history
        INNER JOIN latest_history AS latest
            ON history.id = latest.latest_id
        ORDER BY
            history.conviction_score DESC,
            history.wallet_count DESC,
            history.combined_value DESC
        LIMIT ?
        """,
        (limit,),
    )


def load_recent_alerts(limit: int = 5) -> pd.DataFrame:
    """Load the newest alerts."""

    if not table_exists("alerts"):
        return pd.DataFrame()

    return safe_query(
        """
        SELECT
            severity,
            alert_type,
            title,
            outcome,
            message,
            wallet_count,
            combined_value,
            conviction_score,
            observed_price_move,
            created_at
        FROM alerts
        ORDER BY
            created_at DESC,
            id DESC
        LIMIT ?
        """,
        (limit,),
    )


def load_top_wallets(limit: int = 5) -> pd.DataFrame:
    """Load the newest rating for each top wallet."""

    if not table_exists("wallet_rating_history"):
        return pd.DataFrame()

    return safe_query(
        """
        WITH latest_ratings AS (
            SELECT
                wallet,
                MAX(id) AS latest_id
            FROM wallet_rating_history
            GROUP BY wallet
        )
        SELECT
            rating.wallet,
            rating.wallet_score,
            rating.wallet_grade,
            rating.meaningful_position_count,
            rating.profitable_position_rate,
            rating.total_current_value,
            rating.total_open_pnl,
            rating.open_pnl_ratio,
            rating.concentration_ratio
        FROM wallet_rating_history AS rating
        INNER JOIN latest_ratings AS latest
            ON rating.id = latest.latest_id
        ORDER BY
            rating.wallet_score DESC,
            rating.total_current_value DESC
        LIMIT ?
        """,
        (limit,),
    )


def load_backtest_summary() -> dict[str, Any]:
    """Load a compact summary of stored backtest records."""

    empty_summary = {
        "total": 0,
        "pending": 0,
        "wins": 0,
        "losses": 0,
        "market_not_found": 0,
        "profit": 0.0,
    }

    if not table_exists("backtest_results"):
        return empty_summary

    frame = safe_query(
        """
        SELECT
            result_status,
            hypothetical_profit
        FROM backtest_results
        """
    )

    if frame.empty:
        return empty_summary

    return {
        "total": len(frame),
        "pending": int(
            (frame["result_status"] == "PENDING").sum()
        ),
        "wins": int(
            (frame["result_status"] == "WIN").sum()
        ),
        "losses": int(
            (frame["result_status"] == "LOSS").sum()
        ),
        "market_not_found": int(
            (
                frame["result_status"]
                == "MARKET_NOT_FOUND"
            ).sum()
        ),
        "profit": safe_float(
            frame["hypothetical_profit"]
            .fillna(0)
            .sum()
        ),
    }


def find_latest_report() -> Path | None:
    """Return the newest AI report from the reports folder."""

    REPORTS_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_files = [
        path
        for path in REPORTS_PATH.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".txt", ".md"}
    ]

    if not report_files:
        return None

    return max(
        report_files,
        key=lambda path: path.stat().st_mtime,
    )


def load_latest_report() -> tuple[str, str]:
    """Return the newest report filename and text."""

    report_path = find_latest_report()

    if report_path is None:
        return "", ""

    try:
        report_text = report_path.read_text(
            encoding="utf-8",
        )

    except UnicodeDecodeError:
        report_text = report_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    return report_path.name, report_text


def research_label(
    score: float,
    price_move: float,
) -> str:
    """Assign a practical research label."""

    if abs(price_move) >= 0.10:
        return "TOO LATE / CHASE RISK"

    if score >= 85:
        return "RESEARCH NOW"

    if score >= 75:
        return "HIGH-PRIORITY MONITOR"

    if score >= 65:
        return "MONITOR"

    return "LOW PRIORITY"


def shorten_wallet(wallet: str) -> str:
    """Shorten a wallet address for display."""

    wallet = str(wallet or "")

    if len(wallet) <= 18:
        return wallet

    return f"{wallet[:10]}...{wallet[-8:]}"


def display_summary_metrics(
    signals: pd.DataFrame,
    alerts: pd.DataFrame,
    wallets: pd.DataFrame,
    backtests: dict[str, Any],
) -> None:
    """Display top-level command-center metrics."""

    elite_signals = 0

    if not signals.empty:
        elite_signals = int(
            (
                signals["conviction_score"]
                >= 85
            ).sum()
        )

    high_alerts = 0

    if not alerts.empty:
        high_alerts = int(
            alerts["severity"]
            .isin(["CRITICAL", "HIGH"])
            .sum()
        )

    (
        column_1,
        column_2,
        column_3,
        column_4,
        column_5,
    ) = st.columns(5)

    column_1.metric(
        "Top Signals",
        len(signals),
    )

    column_2.metric(
        "Elite Signals",
        elite_signals,
    )

    column_3.metric(
        "Top Wallets",
        len(wallets),
    )

    column_4.metric(
        "High Alerts",
        high_alerts,
    )

    column_5.metric(
        "Resolved Backtests",
        backtests["wins"] + backtests["losses"],
    )


def display_top_signals(signals: pd.DataFrame) -> None:
    """Display the current highest-priority signals."""

    st.subheader("Top Smart-Money Signals")

    if signals.empty:
        st.info(
            "No consensus signals are stored yet. "
            "Run the full platform first."
        )
        return

    for position, (_, signal) in enumerate(
        signals.iterrows(),
        start=1,
    ):
        score = safe_float(
            signal["conviction_score"]
        )

        price_move = safe_float(
            signal["observed_price_move"]
        )

        label = research_label(
            score=score,
            price_move=price_move,
        )

        with st.container(border=True):
            st.markdown(
                f"### {position}. "
                f"{signal['title']} — "
                f"{signal['outcome']}"
            )

            (
                metric_1,
                metric_2,
                metric_3,
                metric_4,
            ) = st.columns(4)

            metric_1.metric(
                "Conviction",
                f"{score:.1f}/100",
            )

            metric_2.metric(
                "Wallets",
                safe_int(
                    signal["wallet_count"]
                ),
            )

            metric_3.metric(
                "Combined Value",
                format_money(
                    signal["combined_value"]
                ),
            )

            metric_4.metric(
                "Price Move",
                f"{price_move:+.3f}",
            )

            if label == "RESEARCH NOW":
                st.success(label)

            elif label == "HIGH-PRIORITY MONITOR":
                st.warning(label)

            elif label == "TOO LATE / CHASE RISK":
                st.error(label)

            elif label == "MONITOR":
                st.info(label)

            else:
                st.caption(label)

            st.caption(
                f"Grade: "
                f"{signal['conviction_grade']} · "
                f"Average entry: "
                f"{safe_float(signal['average_entry_price']):.3f} · "
                f"Current price: "
                f"{safe_float(signal['average_current_price']):.3f}"
            )


def display_recent_alerts(
    alerts: pd.DataFrame,
) -> None:
    """Display the newest stored alerts."""

    st.subheader("Latest Alerts")

    if alerts.empty:
        st.info(
            "No alerts are stored yet. "
            "Run the full platform first."
        )
        return

    for _, alert in alerts.iterrows():
        severity = str(
            alert["severity"] or "INFO"
        )

        with st.container(border=True):
            st.markdown(
                f"**[{severity}] "
                f"{alert['alert_type']}**"
            )

            st.markdown(
                f"**{alert['title']} — "
                f"{alert['outcome']}**"
            )

            st.write(
                str(alert["message"])
            )

            metric_1, metric_2 = st.columns(2)

            metric_1.metric(
                "Conviction",
                f"{safe_float(alert['conviction_score']):.1f}",
            )

            metric_2.metric(
                "Value",
                format_money(
                    alert["combined_value"]
                ),
            )

            st.caption(
                f"Created: {alert['created_at']}"
            )


def display_top_wallets(
    wallets: pd.DataFrame,
) -> None:
    """Display the highest-rated tracked wallets."""

    st.subheader("Top Wallets")

    if wallets.empty:
        st.info(
            "No wallet ratings are stored yet."
        )
        return

    for position, (_, wallet) in enumerate(
        wallets.iterrows(),
        start=1,
    ):
        with st.container(border=True):
            st.markdown(
                f"**{position}. "
                f"{shorten_wallet(wallet['wallet'])}**"
            )

            score_column, value_column = st.columns(2)

            score_column.metric(
                "Wallet Score",
                f"{safe_float(wallet['wallet_score']):.1f}",
            )

            value_column.metric(
                "Current Value",
                format_money(
                    wallet["total_current_value"]
                ),
            )

            st.caption(
                f"{wallet['wallet_grade']} · "
                f"{safe_int(wallet['meaningful_position_count'])} "
                f"positions worth $500+ · "
                f"{safe_float(wallet['profitable_position_rate']):.1%} "
                f"currently profitable"
            )


def display_ai_report() -> None:
    """Display the newest stored AI research report."""

    st.subheader("Latest AI Research Brief")

    filename, report_text = load_latest_report()

    if not report_text:
        st.info(
            "No AI report was found in the reports folder. "
            "Use the Generate AI Report button above."
        )
        return

    st.caption(
        f"Loaded report: {filename}"
    )

    with st.container(border=True):
        st.markdown(report_text)


def display_backtest_status(
    backtests: dict[str, Any],
) -> None:
    """Display a compact backtesting status panel."""

    st.subheader("Backtesting Status")

    metric_1, metric_2, metric_3 = st.columns(3)

    metric_1.metric(
        "Pending",
        backtests["pending"],
    )

    metric_2.metric(
        "Wins",
        backtests["wins"],
    )

    metric_3.metric(
        "Losses",
        backtests["losses"],
    )

    st.caption(
        f"Total records: {backtests['total']} · "
        f"Markets not found: "
        f"{backtests['market_not_found']} · "
        f"Hypothetical resolved profit: "
        f"{format_money(backtests['profit'])}"
    )


def render_command_center() -> None:
    """Render the complete AI Command Center."""

    st.title("🧠 AI Command Center")

    st.caption(
        "Executive briefing for smart-money consensus, "
        "wallet quality, alerts and historical evaluation."
    )

    render_platform_controls()

    st.divider()

    signals = load_top_signals(limit=5)
    alerts = load_recent_alerts(limit=5)
    wallets = load_top_wallets(limit=5)
    backtests = load_backtest_summary()

    display_summary_metrics(
        signals=signals,
        alerts=alerts,
        wallets=wallets,
        backtests=backtests,
    )

    st.divider()

    display_top_signals(signals)

    st.divider()

    left_column, right_column = st.columns(
        [1.3, 1],
    )

    with left_column:
        display_ai_report()

    with right_column:
        display_recent_alerts(alerts)

    st.divider()

    wallet_column, backtest_column = st.columns(
        [1.2, 1],
    )

    with wallet_column:
        display_top_wallets(wallets)

    with backtest_column:
        display_backtest_status(backtests)

    st.divider()

    render_platform_health()