from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


st.set_page_config(
    page_title="Market Intelligence Timeline",
    page_icon="📈",
    layout="wide",
)


def connect_database() -> sqlite3.Connection:
    """Open the platform SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def table_exists(table_name: str) -> bool:
    """Check whether a database table exists."""

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
    """Run a SQLite query and return a DataFrame."""

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
    """Convert a value to float safely."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value to integer safely."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def format_money(value: Any) -> str:
    """Format a value as currency."""

    return f"${safe_float(value):,.2f}"


def load_available_markets() -> pd.DataFrame:
    """Load every market/outcome with stored consensus history."""

    if not table_exists("consensus_history"):
        return pd.DataFrame()

    return safe_query(
        """
        SELECT
            market_id,
            title,
            outcome,
            COUNT(*) AS snapshot_count,
            MIN(scanned_at) AS first_seen,
            MAX(scanned_at) AS last_seen
        FROM consensus_history
        GROUP BY
            market_id,
            title,
            LOWER(TRIM(outcome))
        ORDER BY
            last_seen DESC,
            title ASC
        """
    )


def load_market_timeline(
    market_id: str,
    outcome: str,
) -> pd.DataFrame:
    """Load every stored consensus snapshot for one signal."""

    return safe_query(
        """
        SELECT
            id,
            scanned_at,
            wallet_count,
            combined_shares,
            combined_value,
            combined_pnl,
            conviction_score,
            conviction_grade,
            average_entry_price,
            average_current_price,
            observed_price_move
        FROM consensus_history
        WHERE market_id = ?
          AND LOWER(TRIM(outcome)) = LOWER(TRIM(?))
        ORDER BY
            scanned_at ASC,
            id ASC
        """,
        (
            market_id,
            outcome,
        ),
    )


def load_supporting_wallets(
    market_id: str,
    outcome: str,
) -> pd.DataFrame:
    """Load wallets currently supporting the selected signal."""

    if not table_exists("positions"):
        return pd.DataFrame()

    return safe_query(
        """
        WITH latest_scans AS (
            SELECT
                wallet,
                MAX(id) AS latest_scan_id
            FROM wallet_scans
            GROUP BY wallet
        )
        SELECT
            positions.wallet,
            positions.shares,
            positions.average_price,
            positions.current_price,
            positions.current_value,
            positions.cash_pnl,
            positions.percent_pnl
        FROM positions
        INNER JOIN latest_scans
            ON positions.wallet = latest_scans.wallet
           AND positions.scan_id = latest_scans.latest_scan_id
        WHERE positions.market_id = ?
          AND LOWER(TRIM(positions.outcome)) = LOWER(TRIM(?))
        ORDER BY
            positions.current_value DESC
        """,
        (
            market_id,
            outcome,
        ),
    )


def shorten_wallet(wallet: str) -> str:
    """Shorten a wallet address for display."""

    wallet = str(wallet or "")

    if len(wallet) <= 20:
        return wallet

    return f"{wallet[:10]}...{wallet[-8:]}"


def calculate_changes(
    timeline: pd.DataFrame,
) -> dict[str, float]:
    """Calculate changes from the first to latest snapshot."""

    if timeline.empty:
        return {
            "wallet_change": 0,
            "value_change": 0.0,
            "pnl_change": 0.0,
            "conviction_change": 0.0,
            "price_change": 0.0,
        }

    first = timeline.iloc[0]
    latest = timeline.iloc[-1]

    return {
        "wallet_change": (
            safe_int(latest["wallet_count"])
            - safe_int(first["wallet_count"])
        ),
        "value_change": (
            safe_float(latest["combined_value"])
            - safe_float(first["combined_value"])
        ),
        "pnl_change": (
            safe_float(latest["combined_pnl"])
            - safe_float(first["combined_pnl"])
        ),
        "conviction_change": (
            safe_float(latest["conviction_score"])
            - safe_float(first["conviction_score"])
        ),
        "price_change": (
            safe_float(latest["average_current_price"])
            - safe_float(first["average_current_price"])
        ),
    }


def classify_signal(
    timeline: pd.DataFrame,
) -> str:
    """Classify whether a signal is building, stable or weakening."""

    if timeline.empty:
        return "NO DATA"

    if len(timeline) == 1:
        return "NEW SIGNAL"

    changes = calculate_changes(timeline)

    positive_factors = 0
    negative_factors = 0

    if changes["wallet_change"] > 0:
        positive_factors += 1
    elif changes["wallet_change"] < 0:
        negative_factors += 1

    if changes["value_change"] > 0:
        positive_factors += 1
    elif changes["value_change"] < 0:
        negative_factors += 1

    if changes["conviction_change"] > 0:
        positive_factors += 1
    elif changes["conviction_change"] < 0:
        negative_factors += 1

    if positive_factors >= 2:
        return "BUILDING"

    if negative_factors >= 2:
        return "WEAKENING"

    return "STABLE"


def display_market_summary(
    timeline: pd.DataFrame,
) -> None:
    """Display latest market metrics and changes."""

    latest = timeline.iloc[-1]
    changes = calculate_changes(timeline)
    signal_state = classify_signal(timeline)

    st.subheader("Current Intelligence Snapshot")

    column_1, column_2, column_3, column_4, column_5 = st.columns(5)

    column_1.metric(
        "Signal State",
        signal_state,
    )

    column_2.metric(
        "Conviction",
        f"{safe_float(latest['conviction_score']):.1f}",
        delta=f"{changes['conviction_change']:+.1f}",
    )

    column_3.metric(
        "Agreeing Wallets",
        safe_int(latest["wallet_count"]),
        delta=f"{changes['wallet_change']:+d}",
    )

    column_4.metric(
        "Combined Value",
        format_money(latest["combined_value"]),
        delta=format_money(changes["value_change"]),
    )

    column_5.metric(
        "Current Price",
        f"{safe_float(latest['average_current_price']):.3f}",
        delta=f"{changes['price_change']:+.3f}",
    )

    st.caption(
        f"Current grade: {latest['conviction_grade']} · "
        f"Snapshots stored: {len(timeline)} · "
        f"Latest scan: {latest['scanned_at']}"
    )


def display_charts(
    timeline: pd.DataFrame,
) -> None:
    """Display historical signal charts."""

    chart_data = timeline.copy()

    chart_data["scanned_at"] = pd.to_datetime(
        chart_data["scanned_at"],
        errors="coerce",
    )

    chart_data = chart_data.dropna(
        subset=["scanned_at"]
    ).set_index("scanned_at")

    st.subheader("Signal Evolution")

    row_1_left, row_1_right = st.columns(2)

    with row_1_left:
        st.caption("Conviction Score")
        st.line_chart(
            chart_data[["conviction_score"]],
            width="stretch",
        )

    with row_1_right:
        st.caption("Agreeing Wallets")
        st.line_chart(
            chart_data[["wallet_count"]],
            width="stretch",
        )

    row_2_left, row_2_right = st.columns(2)

    with row_2_left:
        st.caption("Combined Smart-Money Value")
        st.line_chart(
            chart_data[["combined_value"]],
            width="stretch",
        )

    with row_2_right:
        st.caption("Market Price")
        st.line_chart(
            chart_data[["average_current_price"]],
            width="stretch",
        )

    row_3_left, row_3_right = st.columns(2)

    with row_3_left:
        st.caption("Combined Open PnL")
        st.line_chart(
            chart_data[["combined_pnl"]],
            width="stretch",
        )

    with row_3_right:
        st.caption("Observed Price Move")
        st.line_chart(
            chart_data[["observed_price_move"]],
            width="stretch",
        )


def display_snapshot_history(
    timeline: pd.DataFrame,
) -> None:
    """Display the raw historical snapshots."""

    st.subheader("Snapshot History")

    display_frame = timeline[
        [
            "scanned_at",
            "wallet_count",
            "conviction_score",
            "conviction_grade",
            "combined_value",
            "combined_pnl",
            "average_entry_price",
            "average_current_price",
            "observed_price_move",
        ]
    ].copy()

    display_frame = display_frame.rename(
        columns={
            "scanned_at": "Scanned At",
            "wallet_count": "Wallets",
            "conviction_score": "Conviction",
            "conviction_grade": "Grade",
            "combined_value": "Combined Value",
            "combined_pnl": "Open PnL",
            "average_entry_price": "Average Entry",
            "average_current_price": "Current Price",
            "observed_price_move": "Price Move",
        }
    )

    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Conviction": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Combined Value": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Open PnL": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Average Entry": st.column_config.NumberColumn(
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


def display_supporting_wallets(
    wallets: pd.DataFrame,
) -> None:
    """Display wallets currently supporting the selected signal."""

    st.subheader("Supporting Wallets")

    if wallets.empty:
        st.info(
            "No wallets from the latest stored scans currently "
            "support this exact market and outcome."
        )
        return

    display_frame = wallets.copy()

    display_frame["wallet"] = display_frame["wallet"].apply(
        shorten_wallet
    )

    display_frame["percent_pnl"] = (
        display_frame["percent_pnl"]
        .fillna(0)
    )

    display_frame = display_frame.rename(
        columns={
            "wallet": "Wallet",
            "shares": "Shares",
            "average_price": "Average Entry",
            "current_price": "Current Price",
            "current_value": "Current Value",
            "cash_pnl": "Open PnL",
            "percent_pnl": "PnL %",
        }
    )

    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Shares": st.column_config.NumberColumn(
                format="%.2f",
            ),
            "Average Entry": st.column_config.NumberColumn(
                format="%.3f",
            ),
            "Current Price": st.column_config.NumberColumn(
                format="%.3f",
            ),
            "Current Value": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Open PnL": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "PnL %": st.column_config.NumberColumn(
                format="%.2f%%",
            ),
        },
    )


def main() -> None:
    """Render the market intelligence timeline page."""

    st.title("📈 Market Intelligence Timeline")

    st.caption(
        "Track when smart money entered, how conviction changed, "
        "whether capital increased and how price reacted."
    )

    if not DATABASE_PATH.exists():
        st.error(
            f"The database could not be found at {DATABASE_PATH}."
        )
        st.stop()

    markets = load_available_markets()

    if markets.empty:
        st.info(
            "No consensus history is stored yet. "
            "Run the conviction engine several times first."
        )
        st.stop()

    market_options = {
        (
            row["market_id"],
            row["outcome"],
        ): (
            f"{row['title']} — {row['outcome']} "
            f"({safe_int(row['snapshot_count'])} snapshots)"
        )
        for _, row in markets.iterrows()
    }

    selected_market = st.selectbox(
        "Choose a market and outcome",
        options=list(market_options.keys()),
        format_func=lambda key: market_options[key],
    )

    timeline = load_market_timeline(
        market_id=selected_market[0],
        outcome=selected_market[1],
    )

    if timeline.empty:
        st.warning(
            "No timeline data was returned for this signal."
        )
        st.stop()

    selected_row = markets[
        (
            markets["market_id"]
            == selected_market[0]
        )
        & (
            markets["outcome"]
            == selected_market[1]
        )
    ].iloc[0]

    st.markdown(
        f"## {selected_row['title']} — "
        f"{selected_row['outcome']}"
    )

    display_market_summary(timeline)

    st.divider()

    display_charts(timeline)

    st.divider()

    supporting_wallets = load_supporting_wallets(
        market_id=selected_market[0],
        outcome=selected_market[1],
    )

    left_column, right_column = st.columns(
        [1.15, 1],
    )

    with left_column:
        display_supporting_wallets(
            supporting_wallets
        )

    with right_column:
        latest = timeline.iloc[-1]

        st.subheader("Latest Position Summary")

        st.metric(
            "Combined Shares",
            f"{safe_float(latest['combined_shares']):,.2f}",
        )

        st.metric(
            "Combined Open PnL",
            format_money(latest["combined_pnl"]),
        )

        st.metric(
            "Average Entry",
            f"{safe_float(latest['average_entry_price']):.3f}",
        )

        st.metric(
            "Observed Price Move",
            f"{safe_float(latest['observed_price_move']):+.3f}",
        )

    st.divider()

    display_snapshot_history(timeline)

    st.sidebar.header("Timeline Information")

    st.sidebar.write(
        f"First seen: {selected_row['first_seen']}"
    )

    st.sidebar.write(
        f"Last seen: {selected_row['last_seen']}"
    )

    st.sidebar.write(
        f"Stored snapshots: "
        f"{safe_int(selected_row['snapshot_count'])}"
    )

    st.sidebar.divider()

    st.sidebar.caption(
        "A building signal is not automatically a good entry. "
        "Always compare current price with average smart-money entry."
    )


if __name__ == "__main__":
    main()