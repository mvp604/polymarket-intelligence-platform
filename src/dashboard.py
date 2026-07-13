from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from command_center import render_command_center


DATABASE_PATH = Path("database/polymarket.db")


st.set_page_config(
    page_title="Polymarket Intelligence Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def connect_database() -> sqlite3.Connection:
    """Open the local SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH.resolve()}."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Check whether a database table exists."""

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
    """Run a query and return a dataframe."""

    connection = connect_database()

    try:
        return pd.read_sql_query(
            query,
            connection,
            params=parameters,
        )

    finally:
        connection.close()


def get_table_count(table_name: str) -> int:
    """Return the number of rows in a table."""

    connection = connect_database()

    try:
        if not table_exists(connection, table_name):
            return 0

        row = connection.execute(
            f"SELECT COUNT(*) AS total FROM {table_name}"
        ).fetchone()

        return int(row["total"]) if row else 0

    finally:
        connection.close()


def format_money(value: Any) -> str:
    """Format money values safely."""

    try:
        return f"${float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def load_latest_consensus() -> pd.DataFrame:
    """Load the latest consensus snapshot for every market and outcome."""

    connection = connect_database()

    try:
        if not table_exists(connection, "consensus_history"):
            return pd.DataFrame()

    finally:
        connection.close()

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
            history.scanned_at,
            history.market_id
        FROM consensus_history AS history
        INNER JOIN latest_history AS latest
            ON history.id = latest.latest_id
        ORDER BY
            history.conviction_score DESC,
            history.wallet_count DESC,
            history.combined_value DESC
        """
    )


def load_latest_wallet_ratings() -> pd.DataFrame:
    """Load the newest rating for every wallet."""

    connection = connect_database()

    try:
        if not table_exists(connection, "wallet_rating_history"):
            return pd.DataFrame()

    finally:
        connection.close()

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
            rating.scan_count,
            rating.meaningful_position_count,
            rating.profitable_position_rate,
            rating.total_current_value,
            rating.total_open_pnl,
            rating.open_pnl_ratio,
            rating.concentration_ratio,
            rating.rated_at
        FROM wallet_rating_history AS rating
        INNER JOIN latest_ratings AS latest
            ON rating.id = latest.latest_id
        ORDER BY
            rating.wallet_score DESC,
            rating.total_current_value DESC
        """
    )


def load_latest_alerts(limit: int = 50) -> pd.DataFrame:
    """Load recent alerts."""

    connection = connect_database()

    try:
        if not table_exists(connection, "alerts"):
            return pd.DataFrame()

    finally:
        connection.close()

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
            created_at,
            acknowledged
        FROM alerts
        ORDER BY
            created_at DESC,
            id DESC
        LIMIT ?
        """,
        (limit,),
    )


def load_backtest_results() -> pd.DataFrame:
    """Load historical backtest records."""

    connection = connect_database()

    try:
        if not table_exists(connection, "backtest_results"):
            return pd.DataFrame()

    finally:
        connection.close()

    return safe_query(
        """
        SELECT
            title,
            selected_outcome,
            winning_outcome,
            entry_price,
            conviction_score,
            conviction_grade,
            wallet_count,
            hypothetical_profit,
            hypothetical_return_pct,
            result_status,
            evaluated_at
        FROM backtest_results
        ORDER BY
            evaluated_at DESC,
            id DESC
        """
    )


def load_consensus_timeline(
    market_id: str,
    outcome: str,
) -> pd.DataFrame:
    """Load historical snapshots for one consensus signal."""

    return safe_query(
        """
        SELECT
            scanned_at,
            wallet_count,
            combined_value,
            combined_pnl,
            conviction_score,
            average_current_price
        FROM consensus_history
        WHERE market_id = ?
          AND LOWER(TRIM(outcome)) = LOWER(TRIM(?))
        ORDER BY scanned_at ASC, id ASC
        """,
        (
            market_id,
            outcome,
        ),
    )


def display_overview_metrics(
    consensus: pd.DataFrame,
    wallet_ratings: pd.DataFrame,
    alerts: pd.DataFrame,
    backtests: pd.DataFrame,
) -> None:
    """Display top-level platform statistics."""

    total_wallets = len(wallet_ratings)
    active_consensus = len(consensus)
    alert_count = len(alerts)

    resolved_backtests = 0

    if not backtests.empty:
        resolved_backtests = int(
            backtests["result_status"]
            .isin(["WIN", "LOSS"])
            .sum()
        )

    elite_signals = 0

    if not consensus.empty:
        elite_signals = int(
            (
                consensus["conviction_score"]
                >= 85
            ).sum()
        )

    column_1, column_2, column_3, column_4, column_5 = st.columns(5)

    column_1.metric(
        "Tracked Wallets",
        total_wallets,
    )

    column_2.metric(
        "Consensus Signals",
        active_consensus,
    )

    column_3.metric(
        "Elite Signals",
        elite_signals,
    )

    column_4.metric(
        "Stored Alerts",
        alert_count,
    )

    column_5.metric(
        "Resolved Backtests",
        resolved_backtests,
    )


def display_consensus_tab(consensus: pd.DataFrame) -> None:
    """Display consensus signals and history charts."""

    st.subheader("Smart-Money Consensus")

    if consensus.empty:
        st.info(
            "No consensus snapshots are stored yet. "
            "Run the conviction engine first."
        )
        return

    grade_options = sorted(
        consensus["conviction_grade"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_grades = st.multiselect(
        "Filter by conviction grade",
        grade_options,
        default=grade_options,
    )

    minimum_score = st.slider(
        "Minimum conviction score",
        min_value=0,
        max_value=100,
        value=50,
        step=1,
    )

    filtered = consensus[
        consensus["conviction_grade"].isin(selected_grades)
        & (
            consensus["conviction_score"]
            >= minimum_score
        )
    ].copy()

    if filtered.empty:
        st.warning(
            "No signals match the selected filters."
        )
        return

    display_frame = filtered[
        [
            "title",
            "outcome",
            "wallet_count",
            "conviction_score",
            "conviction_grade",
            "combined_value",
            "combined_pnl",
            "average_entry_price",
            "average_current_price",
            "observed_price_move",
            "scanned_at",
        ]
    ].copy()

    display_frame = display_frame.rename(
        columns={
            "title": "Market",
            "outcome": "Outcome",
            "wallet_count": "Wallets",
            "conviction_score": "Score",
            "conviction_grade": "Grade",
            "combined_value": "Combined Value",
            "combined_pnl": "Open PnL",
            "average_entry_price": "Avg Entry",
            "average_current_price": "Current Price",
            "observed_price_move": "Price Move",
            "scanned_at": "Last Snapshot",
        }
    )

    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Combined Value": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Open PnL": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Avg Entry": st.column_config.NumberColumn(
                format="%.3f",
            ),
            "Current Price": st.column_config.NumberColumn(
                format="%.3f",
            ),
            "Price Move": st.column_config.NumberColumn(
                format="%+.3f",
            ),
        },
    )

    st.divider()
    st.subheader("Consensus History")

    market_labels = {
        (
            row["market_id"],
            row["outcome"],
        ): (
            f"{row['title']} — {row['outcome']}"
        )
        for _, row in filtered.iterrows()
    }

    selected_key = st.selectbox(
        "Choose a market",
        options=list(market_labels.keys()),
        format_func=lambda key: market_labels[key],
    )

    timeline = load_consensus_timeline(
        market_id=selected_key[0],
        outcome=selected_key[1],
    )

    if timeline.empty:
        st.info(
            "No historical timeline is available."
        )
        return

    timeline["scanned_at"] = pd.to_datetime(
        timeline["scanned_at"],
        errors="coerce",
    )

    timeline = timeline.dropna(
        subset=["scanned_at"]
    ).set_index("scanned_at")

    chart_1, chart_2 = st.columns(2)

    with chart_1:
        st.caption("Conviction Score")
        st.line_chart(
            timeline[["conviction_score"]]
        )

    with chart_2:
        st.caption("Agreeing Wallets")
        st.line_chart(
            timeline[["wallet_count"]]
        )

    chart_3, chart_4 = st.columns(2)

    with chart_3:
        st.caption("Combined Smart-Money Value")
        st.line_chart(
            timeline[["combined_value"]]
        )

    with chart_4:
        st.caption("Market Price")
        st.line_chart(
            timeline[["average_current_price"]]
        )


def display_wallet_tab(
    wallet_ratings: pd.DataFrame,
) -> None:
    """Display latest wallet ratings."""

    st.subheader("Wallet Rankings")

    if wallet_ratings.empty:
        st.info(
            "No wallet ratings are stored yet. "
            "Run the wallet rating engine."
        )
        return

    minimum_wallet_score = st.slider(
        "Minimum wallet score",
        min_value=0,
        max_value=100,
        value=40,
        step=1,
    )

    filtered = wallet_ratings[
        wallet_ratings["wallet_score"]
        >= minimum_wallet_score
    ].copy()

    filtered["profitable_position_rate"] = (
        filtered["profitable_position_rate"]
        * 100
    )

    filtered["open_pnl_ratio"] = (
        filtered["open_pnl_ratio"]
        * 100
    )

    filtered["concentration_ratio"] = (
        filtered["concentration_ratio"]
        * 100
    )

    display_frame = filtered[
        [
            "wallet",
            "wallet_score",
            "wallet_grade",
            "scan_count",
            "meaningful_position_count",
            "profitable_position_rate",
            "total_current_value",
            "total_open_pnl",
            "open_pnl_ratio",
            "concentration_ratio",
        ]
    ].copy()

    display_frame = display_frame.rename(
        columns={
            "wallet": "Wallet",
            "wallet_score": "Score",
            "wallet_grade": "Grade",
            "scan_count": "Scans",
            "meaningful_position_count": "Positions $500+",
            "profitable_position_rate": "Profitable Positions %",
            "total_current_value": "Current Value",
            "total_open_pnl": "Open PnL",
            "open_pnl_ratio": "Open PnL %",
            "concentration_ratio": "Largest Position %",
        }
    )

    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Current Value": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Open PnL": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Profitable Positions %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
            "Open PnL %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
            "Largest Position %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
        },
    )


def display_alerts_tab(alerts: pd.DataFrame) -> None:
    """Display alerts."""

    st.subheader("Smart-Money Alert Feed")

    if alerts.empty:
        st.info(
            "No alerts are stored yet. "
            "Run the alert engine."
        )
        return

    severity_options = sorted(
        alerts["severity"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_severities = st.multiselect(
        "Filter by severity",
        severity_options,
        default=severity_options,
    )

    filtered = alerts[
        alerts["severity"].isin(
            selected_severities
        )
    ]

    for _, alert in filtered.iterrows():
        severity = str(alert["severity"])

        if severity == "CRITICAL":
            display_method = st.error
        elif severity == "HIGH":
            display_method = st.warning
        elif severity == "WARNING":
            display_method = st.info
        else:
            display_method = st.success

        with st.container(border=True):
            st.markdown(
                f"### [{severity}] {alert['alert_type']}"
            )

            st.markdown(
                f"**{alert['title']} — {alert['outcome']}**"
            )

            metric_1, metric_2, metric_3 = st.columns(3)

            metric_1.metric(
                "Wallets",
                int(alert["wallet_count"]),
            )

            metric_2.metric(
                "Conviction",
                f"{float(alert['conviction_score']):.1f}",
            )

            metric_3.metric(
                "Combined Value",
                format_money(
                    alert["combined_value"]
                ),
            )

            display_method(
                str(alert["message"])
            )

            st.caption(
                f"Created: {alert['created_at']}"
            )


def display_backtest_tab(
    backtests: pd.DataFrame,
) -> None:
    """Display historical backtesting results."""

    st.subheader("Historical Backtesting")

    if backtests.empty:
        st.info(
            "No backtest results are stored yet."
        )
        return

    status_counts = (
        backtests["result_status"]
        .value_counts()
        .to_dict()
    )

    summary_columns = st.columns(
        max(len(status_counts), 1)
    )

    for column, (
        status,
        count,
    ) in zip(
        summary_columns,
        status_counts.items(),
    ):
        column.metric(
            status,
            int(count),
        )

    resolved = backtests[
        backtests["result_status"]
        .isin(["WIN", "LOSS"])
    ].copy()

    if resolved.empty:
        st.info(
            "No valid resolved signals are available yet. "
            "Pending results will update when markets resolve."
        )

    else:
        wins = int(
            (
                resolved["result_status"]
                == "WIN"
            ).sum()
        )

        win_rate = wins / len(resolved)

        total_profit = resolved[
            "hypothetical_profit"
        ].fillna(0).sum()

        metric_1, metric_2, metric_3 = st.columns(3)

        metric_1.metric(
            "Resolved Signals",
            len(resolved),
        )

        metric_2.metric(
            "Win Rate",
            f"{win_rate:.1%}",
        )

        metric_3.metric(
            "Hypothetical Profit",
            format_money(total_profit),
        )

    display_frame = backtests.copy()

    display_frame[
        "hypothetical_return_pct"
    ] = (
        display_frame[
            "hypothetical_return_pct"
        ]
        * 100
    )

    display_frame = display_frame.rename(
        columns={
            "title": "Market",
            "selected_outcome": "Selected Outcome",
            "winning_outcome": "Winning Outcome",
            "entry_price": "Entry Price",
            "conviction_score": "Score",
            "conviction_grade": "Grade",
            "wallet_count": "Wallets",
            "hypothetical_profit": "Profit",
            "hypothetical_return_pct": "Return %",
            "result_status": "Status",
            "evaluated_at": "Evaluated At",
        }
    )

    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Entry Price": st.column_config.NumberColumn(
                format="%.3f",
            ),
            "Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Profit": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Return %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
        },
    )


def main() -> None:
    """Render the dashboard."""

    st.title("📊 Polymarket Intelligence Platform")

    st.caption(
        "Smart-money tracking, wallet intelligence, "
        "consensus research and historical evaluation."
    )

    if not DATABASE_PATH.exists():
        st.error(
            "The SQLite database was not found. "
            "Run the scanner and database setup first."
        )
        st.stop()

    consensus = load_latest_consensus()
    wallet_ratings = load_latest_wallet_ratings()
    alerts = load_latest_alerts()
    backtests = load_backtest_results()

    display_overview_metrics(
        consensus=consensus,
        wallet_ratings=wallet_ratings,
        alerts=alerts,
        backtests=backtests,
    )

    st.divider()

    (
        command_center_tab,
        consensus_tab,
        wallets_tab,
        alerts_tab,
        backtests_tab,
    ) = st.tabs(
        [
            "AI Command Center",
            "Consensus",
            "Wallet Rankings",
            "Alerts",
            "Backtesting",
        ]
    )

    with command_center_tab:
        render_command_center()

    with consensus_tab:
        display_consensus_tab(consensus)

    with wallets_tab:
        display_wallet_tab(wallet_ratings)

    with alerts_tab:
        display_alerts_tab(alerts)

    with backtests_tab:
        display_backtest_tab(backtests)

    st.sidebar.header("Platform Status")

    st.sidebar.write(
        f"Wallet scans: "
        f"{get_table_count('wallet_scans')}"
    )

    st.sidebar.write(
        f"Stored positions: "
        f"{get_table_count('positions')}"
    )

    st.sidebar.write(
        f"Consensus snapshots: "
        f"{get_table_count('consensus_history')}"
    )

    st.sidebar.write(
        f"Wallet rating snapshots: "
        f"{get_table_count('wallet_rating_history')}"
    )

    st.sidebar.write(
        f"Alerts: "
        f"{get_table_count('alerts')}"
    )

    st.sidebar.write(
        f"Backtest records: "
        f"{get_table_count('backtest_results')}"
    )

    st.sidebar.divider()

    st.sidebar.caption(
        "Research support only. "
        "No signal guarantees a winning trade."
    )


if __name__ == "__main__":
    main()