from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


st.set_page_config(
    page_title="Smart Money Radar",
    page_icon="📡",
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
    """Run a query and return a pandas DataFrame."""

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
    """Keep a value inside a numerical range."""

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

    if number >= 0:
        return f"+${number:,.2f}"

    return f"-${abs(number):,.2f}"


def load_consensus_history() -> pd.DataFrame:
    """Load all stored consensus snapshots."""

    if not table_exists("consensus_history"):
        return pd.DataFrame()

    return safe_query(
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


def load_latest_wallet_scores() -> dict[str, float]:
    """Load the latest stored score for every wallet."""

    if not table_exists("wallet_rating_history"):
        return {}

    frame = safe_query(
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
            rating.wallet_score
        FROM wallet_rating_history AS rating
        INNER JOIN latest_ratings AS latest
            ON rating.id = latest.latest_id
        """
    )

    if frame.empty:
        return {}

    return {
        str(row["wallet"]).strip().lower():
            safe_float(row["wallet_score"])
        for _, row in frame.iterrows()
    }


def load_latest_supporting_wallets() -> pd.DataFrame:
    """Load qualifying positions from the latest scan of each wallet."""

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
            positions.market_id,
            positions.outcome,
            positions.current_value
        FROM positions
        INNER JOIN latest_scans
            ON positions.wallet = latest_scans.wallet
           AND positions.scan_id = latest_scans.latest_scan_id
        WHERE positions.market_id IS NOT NULL
          AND TRIM(positions.market_id) != ''
          AND positions.outcome IS NOT NULL
          AND TRIM(positions.outcome) != ''
          AND COALESCE(positions.current_value, 0) >= 500
        """
    )


def calculate_wallet_quality(
    market_id: str,
    outcome: str,
    positions: pd.DataFrame,
    wallet_scores: dict[str, float],
) -> float:
    """Calculate average quality of wallets supporting a signal."""

    if positions.empty:
        return 50.0

    matching = positions[
        (
            positions["market_id"]
            == market_id
        )
        & (
            positions["outcome"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == str(outcome).strip().casefold()
        )
    ]

    if matching.empty:
        return 50.0

    scores: list[float] = []

    for wallet in matching["wallet"].dropna():
        normalized_wallet = str(wallet).strip().lower()

        if normalized_wallet in wallet_scores:
            scores.append(
                wallet_scores[normalized_wallet]
            )

    if not scores:
        return 50.0

    return sum(scores) / len(scores)


def calculate_velocity(
    series: pd.Series,
) -> float:
    """Calculate the recent average change per snapshot."""

    values = [
        safe_float(value)
        for value in series.tolist()
    ]

    if len(values) < 2:
        return 0.0

    differences = [
        values[index] - values[index - 1]
        for index in range(1, len(values))
    ]

    recent_differences = differences[-3:]

    return sum(recent_differences) / len(
        recent_differences
    )


def classify_signal_state(
    snapshot_count: int,
    wallet_change: int,
    value_change: float,
    conviction_change: float,
    recent_conviction_velocity: float,
) -> str:
    """Classify signal momentum."""

    if snapshot_count <= 1:
        return "NEW"

    positive_factors = 0
    negative_factors = 0

    if wallet_change > 0:
        positive_factors += 1
    elif wallet_change < 0:
        negative_factors += 1

    if value_change > 0:
        positive_factors += 1
    elif value_change < 0:
        negative_factors += 1

    if conviction_change > 0:
        positive_factors += 1
    elif conviction_change < 0:
        negative_factors += 1

    if recent_conviction_velocity >= 3:
        positive_factors += 1
    elif recent_conviction_velocity <= -3:
        negative_factors += 1

    if positive_factors >= 3:
        return "BUILDING FAST"

    if positive_factors >= 2:
        return "BUILDING"

    if negative_factors >= 2:
        return "WEAKENING"

    return "STABLE"


def calculate_radar_score(
    latest_score: float,
    latest_wallets: int,
    latest_value: float,
    wallet_quality: float,
    wallet_change: int,
    value_change: float,
    conviction_change: float,
    conviction_velocity: float,
    price_move: float,
    current_price: float,
) -> tuple[float, dict[str, float]]:
    """Calculate a transparent radar score out of 100."""

    conviction_points = clamp(
        latest_score / 100,
        0,
        1,
    ) * 25

    wallet_points = clamp(
        latest_wallets / 5,
        0,
        1,
    ) * 15

    if latest_value <= 0:
        capital_points = 0.0
    elif latest_value >= 500_000:
        capital_points = 15.0
    elif latest_value >= 250_000:
        capital_points = 13.0
    elif latest_value >= 100_000:
        capital_points = 10.0
    elif latest_value >= 25_000:
        capital_points = 7.0
    elif latest_value >= 5_000:
        capital_points = 4.0
    else:
        capital_points = 2.0

    quality_points = clamp(
        wallet_quality / 100,
        0,
        1,
    ) * 15

    wallet_growth_points = clamp(
        wallet_change / 3,
        -1,
        1,
    ) * 5

    if latest_value > 0:
        value_growth_ratio = (
            value_change
            / max(
                latest_value - value_change,
                1,
            )
        )
    else:
        value_growth_ratio = 0.0

    capital_flow_points = clamp(
        value_growth_ratio / 0.25,
        -1,
        1,
    ) * 8

    conviction_growth_points = clamp(
        conviction_change / 15,
        -1,
        1,
    ) * 6

    velocity_points = clamp(
        conviction_velocity / 5,
        -1,
        1,
    ) * 4

    absolute_price_move = abs(price_move)

    if absolute_price_move <= 0.02:
        timing_points = 7.0
    elif absolute_price_move <= 0.05:
        timing_points = 5.0
    elif absolute_price_move <= 0.10:
        timing_points = 2.0
    else:
        timing_points = -5.0

    if 0.10 <= current_price <= 0.75:
        price_room_points = 5.0
    elif 0.75 < current_price <= 0.90:
        price_room_points = 2.0
    elif current_price > 0.95:
        price_room_points = -3.0
    else:
        price_room_points = 1.0

    total_score = (
        conviction_points
        + wallet_points
        + capital_points
        + quality_points
        + wallet_growth_points
        + capital_flow_points
        + conviction_growth_points
        + velocity_points
        + timing_points
        + price_room_points
    )

    total_score = clamp(
        total_score,
        0,
        100,
    )

    breakdown = {
        "Conviction": round(
            conviction_points,
            1,
        ),
        "Wallet Agreement": round(
            wallet_points,
            1,
        ),
        "Capital": round(
            capital_points,
            1,
        ),
        "Wallet Quality": round(
            quality_points,
            1,
        ),
        "Wallet Growth": round(
            wallet_growth_points,
            1,
        ),
        "Capital Flow": round(
            capital_flow_points,
            1,
        ),
        "Conviction Growth": round(
            conviction_growth_points,
            1,
        ),
        "Velocity": round(
            velocity_points,
            1,
        ),
        "Entry Timing": round(
            timing_points,
            1,
        ),
        "Price Room": round(
            price_room_points,
            1,
        ),
    }

    return round(total_score, 1), breakdown


def radar_grade(score: float) -> str:
    """Convert radar score into a research tier."""

    if score >= 85:
        return "S+ RADAR"

    if score >= 78:
        return "S RADAR"

    if score >= 70:
        return "A RADAR"

    if score >= 60:
        return "MONITOR"

    return "LOW PRIORITY"


def build_radar_signals(
    history: pd.DataFrame,
    positions: pd.DataFrame,
    wallet_scores: dict[str, float],
) -> list[dict[str, Any]]:
    """Build one radar record for each market and outcome."""

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

    signals: list[dict[str, Any]] = []

    for (
        market_id,
        _normalized_outcome,
    ), group in grouped:

        group = group.sort_values(
            [
                "scanned_at",
                "id",
            ]
        ).reset_index(drop=True)

        first = group.iloc[0]
        latest = group.iloc[-1]

        previous = (
            group.iloc[-2]
            if len(group) >= 2
            else first
        )

        latest_wallets = safe_int(
            latest["wallet_count"]
        )

        latest_value = safe_float(
            latest["combined_value"]
        )

        latest_score = safe_float(
            latest["conviction_score"]
        )

        current_price = safe_float(
            latest["average_current_price"]
        )

        price_move = safe_float(
            latest["observed_price_move"]
        )

        total_wallet_change = (
            latest_wallets
            - safe_int(first["wallet_count"])
        )

        total_value_change = (
            latest_value
            - safe_float(first["combined_value"])
        )

        total_conviction_change = (
            latest_score
            - safe_float(first["conviction_score"])
        )

        recent_wallet_change = (
            latest_wallets
            - safe_int(previous["wallet_count"])
        )

        recent_value_change = (
            latest_value
            - safe_float(previous["combined_value"])
        )

        recent_conviction_change = (
            latest_score
            - safe_float(
                previous["conviction_score"]
            )
        )

        conviction_velocity = calculate_velocity(
            group["conviction_score"]
        )

        value_velocity = calculate_velocity(
            group["combined_value"]
        )

        wallet_quality = calculate_wallet_quality(
            market_id=str(market_id),
            outcome=str(latest["outcome"]),
            positions=positions,
            wallet_scores=wallet_scores,
        )

        signal_state = classify_signal_state(
            snapshot_count=len(group),
            wallet_change=recent_wallet_change,
            value_change=recent_value_change,
            conviction_change=(
                recent_conviction_change
            ),
            recent_conviction_velocity=(
                conviction_velocity
            ),
        )

        radar_score, score_breakdown = (
            calculate_radar_score(
                latest_score=latest_score,
                latest_wallets=latest_wallets,
                latest_value=latest_value,
                wallet_quality=wallet_quality,
                wallet_change=recent_wallet_change,
                value_change=recent_value_change,
                conviction_change=(
                    recent_conviction_change
                ),
                conviction_velocity=(
                    conviction_velocity
                ),
                price_move=price_move,
                current_price=current_price,
            )
        )

        chase_risk = abs(price_move) >= 0.10

        signal = {
            "market_id": str(market_id),
            "title": str(
                latest["title"]
                or "Unknown market"
            ),
            "outcome": str(
                latest["outcome"]
                or "Unknown"
            ),
            "snapshot_count": len(group),
            "radar_score": radar_score,
            "radar_grade": radar_grade(
                radar_score
            ),
            "signal_state": signal_state,
            "conviction_score": latest_score,
            "conviction_grade": str(
                latest["conviction_grade"]
                or "UNRATED"
            ),
            "wallet_count": latest_wallets,
            "wallet_quality": wallet_quality,
            "combined_value": latest_value,
            "combined_pnl": safe_float(
                latest["combined_pnl"]
            ),
            "average_entry_price": safe_float(
                latest["average_entry_price"]
            ),
            "current_price": current_price,
            "price_move": price_move,
            "recent_wallet_change": (
                recent_wallet_change
            ),
            "recent_value_change": (
                recent_value_change
            ),
            "recent_conviction_change": (
                recent_conviction_change
            ),
            "total_wallet_change": (
                total_wallet_change
            ),
            "total_value_change": (
                total_value_change
            ),
            "total_conviction_change": (
                total_conviction_change
            ),
            "conviction_velocity": (
                conviction_velocity
            ),
            "value_velocity": value_velocity,
            "chase_risk": chase_risk,
            "latest_scan": str(
                latest["scanned_at"]
            ),
            "score_breakdown": (
                score_breakdown
            ),
        }

        signals.append(signal)

    signals.sort(
        key=lambda item: (
            item["radar_score"],
            item["conviction_score"],
            item["wallet_count"],
            item["combined_value"],
        ),
        reverse=True,
    )

    return signals


def state_icon(state: str) -> str:
    """Return a visual label for each signal state."""

    icons = {
        "BUILDING FAST": "🔥",
        "BUILDING": "📈",
        "STABLE": "➡️",
        "WEAKENING": "📉",
        "NEW": "🆕",
    }

    return icons.get(
        state,
        "•",
    )


def display_radar_summary(
    signals: list[dict[str, Any]],
) -> None:
    """Display radar overview metrics."""

    total_signals = len(signals)

    building = sum(
        1
        for signal in signals
        if signal["signal_state"]
        in {
            "BUILDING",
            "BUILDING FAST",
        }
    )

    weakening = sum(
        1
        for signal in signals
        if signal["signal_state"]
        == "WEAKENING"
    )

    elite = sum(
        1
        for signal in signals
        if signal["radar_score"] >= 78
    )

    chase_risk = sum(
        1
        for signal in signals
        if signal["chase_risk"]
    )

    (
        column_1,
        column_2,
        column_3,
        column_4,
        column_5,
    ) = st.columns(5)

    column_1.metric(
        "Radar Signals",
        total_signals,
    )

    column_2.metric(
        "Building",
        building,
    )

    column_3.metric(
        "Elite Radar",
        elite,
    )

    column_4.metric(
        "Weakening",
        weakening,
    )

    column_5.metric(
        "Chase Risk",
        chase_risk,
    )


def display_signal_card(
    rank: int,
    signal: dict[str, Any],
) -> None:
    """Display one radar signal card."""

    with st.container(border=True):
        st.markdown(
            f"## {rank}. "
            f"{state_icon(signal['signal_state'])} "
            f"{signal['title']} — "
            f"{signal['outcome']}"
        )

        st.caption(
            f"{signal['radar_grade']} · "
            f"{signal['signal_state']} · "
            f"{signal['snapshot_count']} snapshots"
        )

        (
            metric_1,
            metric_2,
            metric_3,
            metric_4,
            metric_5,
        ) = st.columns(5)

        metric_1.metric(
            "Radar Score",
            f"{signal['radar_score']:.1f}",
        )

        metric_2.metric(
            "Conviction",
            f"{signal['conviction_score']:.1f}",
            delta=(
                f"{signal['recent_conviction_change']:+.1f}"
            ),
        )

        metric_3.metric(
            "Wallets",
            signal["wallet_count"],
            delta=(
                f"{signal['recent_wallet_change']:+d}"
            ),
        )

        metric_4.metric(
            "Smart-Money Value",
            format_money(
                signal["combined_value"]
            ),
            delta=format_signed_money(
                signal["recent_value_change"]
            ),
        )

        metric_5.metric(
            "Current Price",
            f"{signal['current_price']:.3f}",
            delta=f"{signal['price_move']:+.3f}",
        )

        if signal["signal_state"] == "BUILDING FAST":
            st.success(
                "Smart-money participation and conviction "
                "are accelerating."
            )

        elif signal["signal_state"] == "BUILDING":
            st.success(
                "The signal is strengthening across recent snapshots."
            )

        elif signal["signal_state"] == "WEAKENING":
            st.warning(
                "Wallet participation, capital, or conviction "
                "is declining."
            )

        elif signal["signal_state"] == "NEW":
            st.info(
                "This is a newly detected consensus signal."
            )

        else:
            st.info(
                "The signal is currently stable."
            )

        if signal["chase_risk"]:
            st.error(
                "CHASE RISK: Current price has moved materially "
                "from the observed smart-money entry."
            )

        st.caption(
            f"Average wallet quality: "
            f"{signal['wallet_quality']:.1f}/100 · "
            f"Average entry: "
            f"{signal['average_entry_price']:.3f} · "
            f"Open PnL: "
            f"{format_money(signal['combined_pnl'])}"
        )

        with st.expander(
            "View radar score breakdown"
        ):
            breakdown_frame = pd.DataFrame(
                [
                    {
                        "Factor": factor,
                        "Points": points,
                    }
                    for factor, points
                    in signal[
                        "score_breakdown"
                    ].items()
                ]
            )

            st.dataframe(
                breakdown_frame,
                width="stretch",
                hide_index=True,
            )


def display_radar_table(
    signals: list[dict[str, Any]],
) -> None:
    """Display all radar signals in one table."""

    st.subheader("Complete Radar Board")

    rows = []

    for rank, signal in enumerate(
        signals,
        start=1,
    ):
        rows.append(
            {
                "Rank": rank,
                "Market": signal["title"],
                "Outcome": signal["outcome"],
                "State": signal["signal_state"],
                "Radar Score": (
                    signal["radar_score"]
                ),
                "Radar Grade": (
                    signal["radar_grade"]
                ),
                "Conviction": (
                    signal["conviction_score"]
                ),
                "Wallets": (
                    signal["wallet_count"]
                ),
                "Wallet Change": (
                    signal[
                        "recent_wallet_change"
                    ]
                ),
                "Combined Value": (
                    signal["combined_value"]
                ),
                "Capital Change": (
                    signal[
                        "recent_value_change"
                    ]
                ),
                "Wallet Quality": (
                    signal["wallet_quality"]
                ),
                "Current Price": (
                    signal["current_price"]
                ),
                "Price Move": (
                    signal["price_move"]
                ),
                "Chase Risk": (
                    "YES"
                    if signal["chase_risk"]
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
            "Radar Score":
                st.column_config.NumberColumn(
                    format="%.1f",
                ),
            "Conviction":
                st.column_config.NumberColumn(
                    format="%.1f",
                ),
            "Wallet Quality":
                st.column_config.NumberColumn(
                    format="%.1f",
                ),
            "Combined Value":
                st.column_config.NumberColumn(
                    format="$%.2f",
                ),
            "Capital Change":
                st.column_config.NumberColumn(
                    format="%+.2f",
                ),
            "Current Price":
                st.column_config.NumberColumn(
                    format="%.3f",
                ),
            "Price Move":
                st.column_config.NumberColumn(
                    format="%+.3f",
                ),
        },
    )


def main() -> None:
    """Render the Smart Money Radar page."""

    st.title("📡 Smart Money Radar")

    st.caption(
        "Automatically detect markets where wallet participation, "
        "capital and conviction are strengthening or weakening."
    )

    if not DATABASE_PATH.exists():
        st.error(
            f"Database not found at {DATABASE_PATH}."
        )
        st.stop()

    history = load_consensus_history()

    if history.empty:
        st.info(
            "No consensus history exists yet. "
            "Run the full platform several times first."
        )
        st.stop()

    positions = load_latest_supporting_wallets()
    wallet_scores = load_latest_wallet_scores()

    signals = build_radar_signals(
        history=history,
        positions=positions,
        wallet_scores=wallet_scores,
    )

    if not signals:
        st.info(
            "No radar signals could be generated."
        )
        st.stop()

    display_radar_summary(signals)

    st.divider()

    st.sidebar.header("Radar Filters")

    state_options = sorted(
        {
            signal["signal_state"]
            for signal in signals
        }
    )

    selected_states = st.sidebar.multiselect(
        "Signal state",
        options=state_options,
        default=state_options,
    )

    minimum_radar_score = st.sidebar.slider(
        "Minimum radar score",
        min_value=0,
        max_value=100,
        value=50,
        step=1,
    )

    minimum_wallets = st.sidebar.slider(
        "Minimum agreeing wallets",
        min_value=1,
        max_value=10,
        value=2,
        step=1,
    )

    exclude_chase_risk = st.sidebar.checkbox(
        "Exclude chase-risk signals",
        value=False,
    )

    filtered_signals = [
        signal
        for signal in signals
        if (
            signal["signal_state"]
            in selected_states
        )
        and (
            signal["radar_score"]
            >= minimum_radar_score
        )
        and (
            signal["wallet_count"]
            >= minimum_wallets
        )
        and (
            not exclude_chase_risk
            or not signal["chase_risk"]
        )
    ]

    st.subheader("Highest-Priority Radar Signals")

    if not filtered_signals:
        st.warning(
            "No signals match the current radar filters."
        )
        st.stop()

    top_limit = st.selectbox(
        "Number of signal cards to display",
        options=[
            3,
            5,
            10,
            20,
        ],
        index=1,
    )

    for rank, signal in enumerate(
        filtered_signals[:top_limit],
        start=1,
    ):
        display_signal_card(
            rank=rank,
            signal=signal,
        )

    st.divider()

    display_radar_table(
        filtered_signals
    )

    st.sidebar.divider()

    st.sidebar.caption(
        "Radar scores rank research priority only. "
        "They are not calibrated win probabilities."
    )


if __name__ == "__main__":
    main()