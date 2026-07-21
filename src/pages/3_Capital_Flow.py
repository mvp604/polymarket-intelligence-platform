from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


st.set_page_config(
    page_title="Capital Flow",
    page_icon="💰",
    layout="wide",
)


def connect_database() -> sqlite3.Connection:
    """Open the local SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(table_name: str) -> bool:
    """Return True if a SQLite table exists."""

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


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """Keep a number inside a defined range."""

    return max(
        minimum,
        min(value, maximum),
    )


def format_money(value: Any) -> str:
    """Format currency safely."""

    return f"${safe_float(value):,.2f}"


def format_signed_money(value: Any) -> str:
    """Format signed currency safely."""

    number = safe_float(value)

    if number > 0:
        return f"+${number:,.2f}"

    if number < 0:
        return f"-${abs(number):,.2f}"

    return "$0.00"


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp into UTC."""

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


def load_consensus_history() -> pd.DataFrame:
    """Load all consensus snapshots."""

    if not table_exists("consensus_history"):
        return pd.DataFrame()

    frame = safe_query(
        """
        SELECT
            id,
            market_id,
            title,
            outcome,
            wallet_count,
            combined_shares,
            combined_value,
            combined_pnl,
            conviction_score,
            conviction_grade,
            average_entry_price,
            average_current_price,
            observed_price_move,
            scanned_at
        FROM consensus_history
        ORDER BY
            market_id,
            LOWER(TRIM(outcome)),
            scanned_at ASC,
            id ASC
        """
    )

    if not frame.empty:
        frame["parsed_time"] = pd.to_datetime(
            frame["scanned_at"],
            errors="coerce",
            utc=True,
        )

    return frame


def calculate_recent_baseline(
    group: pd.DataFrame,
    hours: int,
) -> pd.Series:
    """
    Return the snapshot closest to the selected lookback period.

    Falls back to the first snapshot when insufficient history exists.
    """

    latest = group.iloc[-1]
    latest_time = latest["parsed_time"]

    if pd.isna(latest_time):
        return group.iloc[0]

    cutoff = latest_time - pd.Timedelta(
        hours=hours
    )

    earlier = group[
        group["parsed_time"] <= cutoff
    ]

    if earlier.empty:
        return group.iloc[0]

    return earlier.iloc[-1]


def classify_flow_state(
    capital_change: float,
    wallet_change: int,
    conviction_change: float,
    share_change: float,
) -> str:
    """Classify the latest capital-flow behavior."""

    positive = 0
    negative = 0

    if capital_change > 0:
        positive += 1
    elif capital_change < 0:
        negative += 1

    if wallet_change > 0:
        positive += 1
    elif wallet_change < 0:
        negative += 1

    if conviction_change > 0:
        positive += 1
    elif conviction_change < 0:
        negative += 1

    if share_change > 0:
        positive += 1
    elif share_change < 0:
        negative += 1

    if positive >= 3:
        return "STRONG ACCUMULATION"

    if positive >= 2:
        return "ACCUMULATION"

    if negative >= 3:
        return "STRONG DISTRIBUTION"

    if negative >= 2:
        return "DISTRIBUTION"

    if capital_change > 0:
        return "ADDING"

    if capital_change < 0:
        return "REDUCING"

    return "STABLE"


def calculate_flow_score(
    capital_change: float,
    wallet_change: int,
    conviction_change: float,
    share_change: float,
    current_value: float,
    current_wallets: int,
    price_change: float,
) -> float:
    """
    Calculate a transparent capital-flow score.

    Positive values indicate accumulation.
    Negative values indicate distribution.
    """

    if current_value > 0:
        capital_ratio = (
            capital_change
            / max(
                current_value - capital_change,
                1,
            )
        )
    else:
        capital_ratio = 0.0

    if share_change != 0:
        share_direction = (
            1.0
            if share_change > 0
            else -1.0
        )
    else:
        share_direction = 0.0

    capital_points = clamp(
        capital_ratio / 0.25,
        -1,
        1,
    ) * 35

    wallet_points = clamp(
        wallet_change / 3,
        -1,
        1,
    ) * 20

    conviction_points = clamp(
        conviction_change / 15,
        -1,
        1,
    ) * 20

    share_points = share_direction * min(
        abs(share_change) / 100_000,
        1,
    ) * 10

    participation_points = clamp(
        current_wallets / 5,
        0,
        1,
    ) * 10

    if capital_change > 0 and price_change <= 0.05:
        timing_points = 5.0
    elif capital_change > 0 and price_change > 0.10:
        timing_points = -5.0
    elif capital_change < 0 and price_change < 0:
        timing_points = -3.0
    else:
        timing_points = 0.0

    return round(
        clamp(
            capital_points
            + wallet_points
            + conviction_points
            + share_points
            + participation_points
            + timing_points,
            -100,
            100,
        ),
        1,
    )


def build_flow_records(
    history: pd.DataFrame,
    lookback_hours: int,
) -> list[dict[str, Any]]:
    """Build one capital-flow record per market and outcome."""

    if history.empty:
        return []

    grouped = history.groupby(
        [
            "market_id",
            history["outcome"]
            .astype(str)
            .str.strip()
            .str.casefold(),
        ],
        sort=False,
    )

    records: list[dict[str, Any]] = []

    for (
        market_id,
        _normalized_outcome,
    ), group in grouped:

        group = group.sort_values(
            [
                "parsed_time",
                "id",
            ]
        ).reset_index(drop=True)

        if group.empty:
            continue

        latest = group.iloc[-1]

        previous = (
            group.iloc[-2]
            if len(group) >= 2
            else group.iloc[0]
        )

        baseline = calculate_recent_baseline(
            group=group,
            hours=lookback_hours,
        )

        latest_value = safe_float(
            latest["combined_value"]
        )

        latest_wallets = safe_int(
            latest["wallet_count"]
        )

        recent_capital_change = (
            latest_value
            - safe_float(
                previous["combined_value"]
            )
        )

        recent_wallet_change = (
            latest_wallets
            - safe_int(
                previous["wallet_count"]
            )
        )

        recent_conviction_change = (
            safe_float(
                latest["conviction_score"]
            )
            - safe_float(
                previous["conviction_score"]
            )
        )

        recent_share_change = (
            safe_float(
                latest["combined_shares"]
            )
            - safe_float(
                previous["combined_shares"]
            )
        )

        lookback_capital_change = (
            latest_value
            - safe_float(
                baseline["combined_value"]
            )
        )

        lookback_wallet_change = (
            latest_wallets
            - safe_int(
                baseline["wallet_count"]
            )
        )

        lookback_conviction_change = (
            safe_float(
                latest["conviction_score"]
            )
            - safe_float(
                baseline["conviction_score"]
            )
        )

        lookback_share_change = (
            safe_float(
                latest["combined_shares"]
            )
            - safe_float(
                baseline["combined_shares"]
            )
        )

        price_change = (
            safe_float(
                latest["average_current_price"]
            )
            - safe_float(
                baseline["average_current_price"]
            )
        )

        flow_state = classify_flow_state(
            capital_change=lookback_capital_change,
            wallet_change=lookback_wallet_change,
            conviction_change=lookback_conviction_change,
            share_change=lookback_share_change,
        )

        flow_score = calculate_flow_score(
            capital_change=lookback_capital_change,
            wallet_change=lookback_wallet_change,
            conviction_change=lookback_conviction_change,
            share_change=lookback_share_change,
            current_value=latest_value,
            current_wallets=latest_wallets,
            price_change=price_change,
        )

        first = group.iloc[0]

        records.append(
            {
                "market_id": str(market_id),
                "title": str(
                    latest["title"]
                    or "Unknown market"
                ),
                "outcome": str(
                    latest["outcome"]
                    or "Unknown"
                ),
                "flow_state": flow_state,
                "flow_score": flow_score,
                "snapshot_count": len(group),
                "wallet_count": latest_wallets,
                "combined_value": latest_value,
                "combined_shares": safe_float(
                    latest["combined_shares"]
                ),
                "combined_pnl": safe_float(
                    latest["combined_pnl"]
                ),
                "conviction_score": safe_float(
                    latest["conviction_score"]
                ),
                "conviction_grade": str(
                    latest["conviction_grade"]
                    or "UNRATED"
                ),
                "average_entry_price": safe_float(
                    latest["average_entry_price"]
                ),
                "current_price": safe_float(
                    latest["average_current_price"]
                ),
                "observed_price_move": safe_float(
                    latest["observed_price_move"]
                ),
                "recent_capital_change": (
                    recent_capital_change
                ),
                "recent_wallet_change": (
                    recent_wallet_change
                ),
                "recent_conviction_change": (
                    recent_conviction_change
                ),
                "recent_share_change": (
                    recent_share_change
                ),
                "lookback_capital_change": (
                    lookback_capital_change
                ),
                "lookback_wallet_change": (
                    lookback_wallet_change
                ),
                "lookback_conviction_change": (
                    lookback_conviction_change
                ),
                "lookback_share_change": (
                    lookback_share_change
                ),
                "lookback_price_change": (
                    price_change
                ),
                "all_time_capital_change": (
                    latest_value
                    - safe_float(
                        first["combined_value"]
                    )
                ),
                "all_time_wallet_change": (
                    latest_wallets
                    - safe_int(
                        first["wallet_count"]
                    )
                ),
                "all_time_conviction_change": (
                    safe_float(
                        latest["conviction_score"]
                    )
                    - safe_float(
                        first["conviction_score"]
                    )
                ),
                "latest_scan": str(
                    latest["scanned_at"]
                ),
                "baseline_scan": str(
                    baseline["scanned_at"]
                ),
                "chase_risk": (
                    abs(
                        safe_float(
                            latest[
                                "observed_price_move"
                            ]
                        )
                    )
                    >= 0.10
                ),
            }
        )

    records.sort(
        key=lambda item: (
            abs(
                item["lookback_capital_change"]
            ),
            abs(item["flow_score"]),
            item["combined_value"],
        ),
        reverse=True,
    )

    return records


def flow_icon(state: str) -> str:
    """Return an icon for the flow classification."""

    icons = {
        "STRONG ACCUMULATION": "🔥",
        "ACCUMULATION": "📈",
        "ADDING": "➕",
        "STABLE": "➡️",
        "REDUCING": "➖",
        "DISTRIBUTION": "📉",
        "STRONG DISTRIBUTION": "🚨",
    }

    return icons.get(
        state,
        "•",
    )


def display_summary(
    records: list[dict[str, Any]],
) -> None:
    """Display high-level capital-flow statistics."""

    total_inflow = sum(
        max(
            record["lookback_capital_change"],
            0,
        )
        for record in records
    )

    total_outflow = sum(
        min(
            record["lookback_capital_change"],
            0,
        )
        for record in records
    )

    accumulating = sum(
        1
        for record in records
        if record["flow_state"]
        in {
            "STRONG ACCUMULATION",
            "ACCUMULATION",
            "ADDING",
        }
    )

    distributing = sum(
        1
        for record in records
        if record["flow_state"]
        in {
            "STRONG DISTRIBUTION",
            "DISTRIBUTION",
            "REDUCING",
        }
    )

    net_flow = total_inflow + total_outflow

    (
        column_1,
        column_2,
        column_3,
        column_4,
        column_5,
    ) = st.columns(5)

    column_1.metric(
        "Tracked Signals",
        len(records),
    )

    column_2.metric(
        "Gross Inflow",
        format_money(total_inflow),
    )

    column_3.metric(
        "Gross Outflow",
        format_money(total_outflow),
    )

    column_4.metric(
        "Net Capital Flow",
        format_signed_money(net_flow),
    )

    column_5.metric(
        "Accumulating / Distributing",
        f"{accumulating} / {distributing}",
    )


def display_flow_card(
    rank: int,
    record: dict[str, Any],
    lookback_hours: int,
) -> None:
    """Display one market capital-flow card."""

    with st.container(border=True):
        st.markdown(
            f"## {rank}. "
            f"{flow_icon(record['flow_state'])} "
            f"{record['title']} — "
            f"{record['outcome']}"
        )

        st.caption(
            f"{record['flow_state']} · "
            f"Flow score: "
            f"{record['flow_score']:+.1f} · "
            f"{record['snapshot_count']} snapshots"
        )

        (
            metric_1,
            metric_2,
            metric_3,
            metric_4,
            metric_5,
        ) = st.columns(5)

        metric_1.metric(
            f"{lookback_hours}h Capital Flow",
            format_signed_money(
                record[
                    "lookback_capital_change"
                ]
            ),
        )

        metric_2.metric(
            "Agreeing Wallets",
            record["wallet_count"],
            delta=(
                f"{record['lookback_wallet_change']:+d}"
            ),
        )

        metric_3.metric(
            "Conviction",
            f"{record['conviction_score']:.1f}",
            delta=(
                f"{record['lookback_conviction_change']:+.1f}"
            ),
        )

        metric_4.metric(
            "Current Capital",
            format_money(
                record["combined_value"]
            ),
        )

        metric_5.metric(
            "Current Price",
            f"{record['current_price']:.3f}",
            delta=(
                f"{record['lookback_price_change']:+.3f}"
            ),
        )

        if record["flow_state"] in {
            "STRONG ACCUMULATION",
            "ACCUMULATION",
        }:
            st.success(
                "Smart money is adding capital while participation "
                "or conviction is strengthening."
            )

        elif record["flow_state"] in {
            "STRONG DISTRIBUTION",
            "DISTRIBUTION",
        }:
            st.error(
                "Smart money is reducing exposure while participation "
                "or conviction is weakening."
            )

        elif record["flow_state"] == "ADDING":
            st.info(
                "Capital increased, but broader confirmation is limited."
            )

        elif record["flow_state"] == "REDUCING":
            st.warning(
                "Capital declined, but full distribution confirmation "
                "is not yet present."
            )

        else:
            st.info(
                "Capital and participation are currently stable."
            )

        if record["chase_risk"]:
            st.warning(
                "CHASE RISK: The current market price has moved "
                "materially from smart-money average entry."
            )

        st.caption(
            f"Shares change: "
            f"{record['lookback_share_change']:+,.2f} · "
            f"Open PnL: "
            f"{format_money(record['combined_pnl'])} · "
            f"Average entry: "
            f"{record['average_entry_price']:.3f}"
        )


def display_inflow_board(
    records: list[dict[str, Any]],
    lookback_hours: int,
) -> None:
    """Display the largest capital inflows."""

    st.subheader("Largest Capital Inflows")

    inflows = [
        record
        for record in records
        if record["lookback_capital_change"] > 0
    ]

    inflows.sort(
        key=lambda item: (
            item["lookback_capital_change"],
            item["flow_score"],
        ),
        reverse=True,
    )

    if not inflows:
        st.info(
            "No positive capital inflows were detected "
            "for the selected lookback."
        )
        return

    for rank, record in enumerate(
        inflows[:10],
        start=1,
    ):
        display_flow_card(
            rank=rank,
            record=record,
            lookback_hours=lookback_hours,
        )


def display_outflow_board(
    records: list[dict[str, Any]],
    lookback_hours: int,
) -> None:
    """Display the largest capital outflows."""

    st.subheader("Largest Capital Outflows")

    outflows = [
        record
        for record in records
        if record["lookback_capital_change"] < 0
    ]

    outflows.sort(
        key=lambda item: (
            item["lookback_capital_change"],
            item["flow_score"],
        )
    )

    if not outflows:
        st.info(
            "No negative capital outflows were detected "
            "for the selected lookback."
        )
        return

    for rank, record in enumerate(
        outflows[:10],
        start=1,
    ):
        display_flow_card(
            rank=rank,
            record=record,
            lookback_hours=lookback_hours,
        )


def display_flow_table(
    records: list[dict[str, Any]],
    lookback_hours: int,
) -> None:
    """Display the complete capital-flow board."""

    st.subheader("Complete Capital Flow Board")

    rows: list[dict[str, Any]] = []

    for record in records:
        rows.append(
            {
                "Market": record["title"],
                "Outcome": record["outcome"],
                "Flow State": (
                    record["flow_state"]
                ),
                "Flow Score": (
                    record["flow_score"]
                ),
                f"{lookback_hours}h Capital Flow": (
                    record[
                        "lookback_capital_change"
                    ]
                ),
                "Current Capital": (
                    record["combined_value"]
                ),
                "Wallets": (
                    record["wallet_count"]
                ),
                "Wallet Change": (
                    record[
                        "lookback_wallet_change"
                    ]
                ),
                "Conviction": (
                    record["conviction_score"]
                ),
                "Conviction Change": (
                    record[
                        "lookback_conviction_change"
                    ]
                ),
                "Share Change": (
                    record[
                        "lookback_share_change"
                    ]
                ),
                "Current Price": (
                    record["current_price"]
                ),
                "Price Change": (
                    record[
                        "lookback_price_change"
                    ]
                ),
                "Chase Risk": (
                    "YES"
                    if record["chase_risk"]
                    else "NO"
                ),
            }
        )

    frame = pd.DataFrame(rows)

    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Flow Score":
                st.column_config.NumberColumn(
                    format="%+.1f",
                ),
            f"{lookback_hours}h Capital Flow":
                st.column_config.NumberColumn(
                    format="%+.2f",
                ),
            "Current Capital":
                st.column_config.NumberColumn(
                    format="$%.2f",
                ),
            "Conviction":
                st.column_config.NumberColumn(
                    format="%.1f",
                ),
            "Conviction Change":
                st.column_config.NumberColumn(
                    format="%+.1f",
                ),
            "Share Change":
                st.column_config.NumberColumn(
                    format="%+.2f",
                ),
            "Current Price":
                st.column_config.NumberColumn(
                    format="%.3f",
                ),
            "Price Change":
                st.column_config.NumberColumn(
                    format="%+.3f",
                ),
        },
    )


def display_flow_chart(
    records: list[dict[str, Any]],
    lookback_hours: int,
) -> None:
    """Display a bar chart of the largest flows."""

    st.subheader("Capital Flow Comparison")

    top_records = sorted(
        records,
        key=lambda item: abs(
            item["lookback_capital_change"]
        ),
        reverse=True,
    )[:20]

    chart_frame = pd.DataFrame(
        [
            {
                "Signal": (
                    f"{record['title']} — "
                    f"{record['outcome']}"
                ),
                "Capital Flow": (
                    record[
                        "lookback_capital_change"
                    ]
                ),
            }
            for record in top_records
        ]
    )

    if chart_frame.empty:
        st.info(
            "No capital-flow chart data is available."
        )
        return

    chart_frame = chart_frame.set_index(
        "Signal"
    )

    st.caption(
        f"Largest absolute capital changes over "
        f"the selected {lookback_hours}-hour lookback."
    )

    st.bar_chart(
        chart_frame,
        width="stretch",
    )


def main() -> None:
    """Render the Capital Flow dashboard page."""

    st.title("💰 Capital Flow")

    st.caption(
        "Track where smart-money capital is entering, leaving, "
        "accumulating or distributing across markets."
    )

    if not DATABASE_PATH.exists():
        st.error(
            f"Database not found at {DATABASE_PATH}."
        )
        st.stop()

    history = load_consensus_history()

    if history.empty:
        st.info(
            "No consensus history is available. "
            "Run the full platform several times first."
        )
        st.stop()

    st.sidebar.header("Capital Flow Filters")

    lookback_hours = st.sidebar.selectbox(
        "Lookback period",
        options=[
            1,
            6,
            12,
            24,
            48,
            72,
            168,
        ],
        index=3,
        format_func=lambda hours: (
            f"{hours} hour"
            if hours == 1
            else (
                f"{hours // 24} days"
                if hours >= 24
                else f"{hours} hours"
            )
        ),
    )

    records = build_flow_records(
        history=history,
        lookback_hours=lookback_hours,
    )

    if not records:
        st.info(
            "No capital-flow records could be generated."
        )
        st.stop()

    state_options = sorted(
        {
            record["flow_state"]
            for record in records
        }
    )

    selected_states = st.sidebar.multiselect(
        "Flow states",
        options=state_options,
        default=state_options,
    )

    minimum_wallets = st.sidebar.slider(
        "Minimum agreeing wallets",
        min_value=1,
        max_value=10,
        value=2,
        step=1,
    )

    minimum_absolute_flow = st.sidebar.number_input(
        "Minimum absolute capital flow",
        min_value=0.0,
        value=0.0,
        step=1000.0,
    )

    exclude_chase_risk = st.sidebar.checkbox(
        "Exclude chase-risk signals",
        value=False,
    )

    filtered_records = [
        record
        for record in records
        if record["flow_state"]
        in selected_states
        and record["wallet_count"]
        >= minimum_wallets
        and abs(
            record["lookback_capital_change"]
        )
        >= minimum_absolute_flow
        and (
            not exclude_chase_risk
            or not record["chase_risk"]
        )
    ]

    if not filtered_records:
        st.warning(
            "No capital-flow signals match the current filters."
        )
        st.stop()

    display_summary(
        filtered_records
    )

    st.divider()

    display_flow_chart(
        records=filtered_records,
        lookback_hours=lookback_hours,
    )

    st.divider()

    inflow_tab, outflow_tab, board_tab = st.tabs(
        [
            "Capital Inflows",
            "Capital Outflows",
            "Complete Flow Board",
        ]
    )

    with inflow_tab:
        display_inflow_board(
            records=filtered_records,
            lookback_hours=lookback_hours,
        )

    with outflow_tab:
        display_outflow_board(
            records=filtered_records,
            lookback_hours=lookback_hours,
        )

    with board_tab:
        display_flow_table(
            records=filtered_records,
            lookback_hours=lookback_hours,
        )

    st.sidebar.divider()

    st.sidebar.caption(
        "Capital flow is calculated from stored consensus snapshots. "
        "A positive flow is not automatically a good entry."
    )


if __name__ == "__main__":
    main()