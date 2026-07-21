from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


st.set_page_config(
    page_title="Market Leadership",
    page_icon="🏆",
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


def format_signed_money(value: Any) -> str:
    """Format signed currency."""

    number = safe_float(value)

    if number > 0:
        return f"+${number:,.2f}"

    if number < 0:
        return f"-${abs(number):,.2f}"

    return "$0.00"


def shorten_wallet(wallet: str) -> str:
    """Shorten a wallet address for display."""

    wallet = str(wallet or "")

    if len(wallet) <= 20:
        return wallet

    return f"{wallet[:10]}...{wallet[-8:]}"


def load_available_markets() -> pd.DataFrame:
    """Load markets currently represented by latest wallet positions."""

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
            positions.market_id,
            positions.title,
            positions.outcome,
            COUNT(DISTINCT positions.wallet) AS wallet_count,
            SUM(COALESCE(positions.current_value, 0)) AS combined_value
        FROM positions
        INNER JOIN latest_scans
            ON positions.wallet = latest_scans.wallet
           AND positions.scan_id = latest_scans.latest_scan_id
        WHERE positions.market_id IS NOT NULL
          AND TRIM(positions.market_id) != ''
          AND positions.outcome IS NOT NULL
          AND TRIM(positions.outcome) != ''
          AND COALESCE(positions.current_value, 0) >= 500
        GROUP BY
            positions.market_id,
            positions.title,
            LOWER(TRIM(positions.outcome))
        HAVING COUNT(DISTINCT positions.wallet) >= 1
        ORDER BY
            wallet_count DESC,
            combined_value DESC
        """
    )


def load_latest_wallet_ratings() -> pd.DataFrame:
    """Load the newest stored rating for every wallet."""

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
            rating.profitable_position_rate,
            rating.total_current_value,
            rating.total_open_pnl,
            rating.open_pnl_ratio,
            rating.concentration_ratio
        FROM wallet_rating_history AS rating
        INNER JOIN latest_ratings AS latest
            ON rating.id = latest.latest_id
        """
    )


def load_market_wallet_history(
    market_id: str,
    outcome: str,
) -> pd.DataFrame:
    """Load every historical wallet position for one market and outcome."""

    return safe_query(
        """
        SELECT
            positions.wallet,
            positions.scan_id,
            wallet_scans.scanned_at,
            positions.shares,
            positions.average_price,
            positions.current_price,
            positions.current_value,
            positions.cash_pnl,
            positions.percent_pnl
        FROM positions
        INNER JOIN wallet_scans
            ON positions.scan_id = wallet_scans.id
        WHERE positions.market_id = ?
          AND LOWER(TRIM(positions.outcome)) = LOWER(TRIM(?))
        ORDER BY
            positions.wallet,
            wallet_scans.scanned_at ASC,
            positions.scan_id ASC
        """,
        (
            market_id,
            outcome,
        ),
    )


def build_wallet_leadership(
    history: pd.DataFrame,
    ratings: pd.DataFrame,
) -> pd.DataFrame:
    """Build one leadership record for each supporting wallet."""

    if history.empty:
        return pd.DataFrame()

    rating_lookup: dict[str, dict[str, Any]] = {}

    if not ratings.empty:
        for _, row in ratings.iterrows():
            rating_lookup[
                str(row["wallet"]).strip().lower()
            ] = dict(row)

    records: list[dict[str, Any]] = []

    for wallet, group in history.groupby("wallet"):
        group = group.sort_values(
            [
                "scanned_at",
                "scan_id",
            ]
        ).reset_index(drop=True)

        first = group.iloc[0]
        latest = group.iloc[-1]

        previous = (
            group.iloc[-2]
            if len(group) >= 2
            else first
        )

        wallet_key = str(wallet).strip().lower()
        rating = rating_lookup.get(wallet_key, {})

        latest_value = safe_float(
            latest["current_value"]
        )

        previous_value = safe_float(
            previous["current_value"]
        )

        latest_shares = safe_float(
            latest["shares"]
        )

        previous_shares = safe_float(
            previous["shares"]
        )

        records.append(
            {
                "wallet": str(wallet),
                "first_seen": str(first["scanned_at"]),
                "latest_seen": str(latest["scanned_at"]),
                "scan_count": len(group),
                "shares": latest_shares,
                "share_change": (
                    latest_shares - previous_shares
                ),
                "average_price": safe_float(
                    latest["average_price"]
                ),
                "current_price": safe_float(
                    latest["current_price"]
                ),
                "current_value": latest_value,
                "value_change": (
                    latest_value - previous_value
                ),
                "cash_pnl": safe_float(
                    latest["cash_pnl"]
                ),
                "percent_pnl": safe_float(
                    latest["percent_pnl"]
                ),
                "wallet_score": safe_float(
                    rating.get("wallet_score")
                ),
                "wallet_grade": str(
                    rating.get("wallet_grade")
                    or "UNRATED"
                ),
                "profitable_position_rate": safe_float(
                    rating.get(
                        "profitable_position_rate"
                    )
                ),
                "wallet_total_value": safe_float(
                    rating.get(
                        "total_current_value"
                    )
                ),
                "wallet_total_pnl": safe_float(
                    rating.get(
                        "total_open_pnl"
                    )
                ),
                "wallet_concentration": safe_float(
                    rating.get(
                        "concentration_ratio"
                    )
                ),
            }
        )

    frame = pd.DataFrame(records)

    if frame.empty:
        return frame

    total_value = frame["current_value"].sum()

    if total_value > 0:
        frame["capital_share"] = (
            frame["current_value"] / total_value
        )
    else:
        frame["capital_share"] = 0.0

    frame["leadership_score"] = (
        frame["capital_share"].clip(0, 1) * 45
        + (frame["wallet_score"] / 100).clip(0, 1) * 30
        + (
            frame["value_change"]
            .clip(lower=0)
            / max(
                frame["value_change"]
                .clip(lower=0)
                .max(),
                1,
            )
        ) * 15
        + (
            frame["cash_pnl"]
            .clip(lower=0)
            / max(
                frame["cash_pnl"]
                .clip(lower=0)
                .max(),
                1,
            )
        ) * 10
    ).round(1)

    return frame.sort_values(
        [
            "leadership_score",
            "current_value",
        ],
        ascending=False,
    ).reset_index(drop=True)


def leadership_grade(score: float) -> str:
    """Convert a leadership score into a label."""

    if score >= 75:
        return "DOMINANT LEADER"

    if score >= 55:
        return "MAJOR LEADER"

    if score >= 35:
        return "CORE SUPPORTER"

    if score >= 20:
        return "SECONDARY SUPPORTER"

    return "MINOR SUPPORTER"


def display_market_summary(
    leadership: pd.DataFrame,
) -> None:
    """Display leadership-level market statistics."""

    total_capital = safe_float(
        leadership["current_value"].sum()
    )

    total_pnl = safe_float(
        leadership["cash_pnl"].sum()
    )

    recent_flow = safe_float(
        leadership["value_change"].sum()
    )

    largest_holder = leadership.iloc[0]

    top_holder_share = safe_float(
        largest_holder["capital_share"]
    )

    columns = st.columns(5)

    columns[0].metric(
        "Supporting Wallets",
        len(leadership),
    )

    columns[1].metric(
        "Tracked Capital",
        format_money(total_capital),
    )

    columns[2].metric(
        "Combined Open PnL",
        format_money(total_pnl),
    )

    columns[3].metric(
        "Recent Capital Flow",
        format_signed_money(recent_flow),
    )

    columns[4].metric(
        "Largest Holder Share",
        f"{top_holder_share:.1%}",
    )

    if top_holder_share >= 0.60:
        st.error(
            "CONCENTRATION RISK: One wallet controls at least "
            "60% of the tracked capital in this signal."
        )

    elif top_holder_share >= 0.40:
        st.warning(
            "This signal is meaningfully concentrated in its "
            "largest supporting wallet."
        )

    else:
        st.success(
            "Capital support is relatively distributed across wallets."
        )


def display_leadership_cards(
    leadership: pd.DataFrame,
) -> None:
    """Display ranked wallet leadership cards."""

    st.subheader("Market Leadership Rankings")

    for index, wallet in leadership.iterrows():
        rank = index + 1
        score = safe_float(
            wallet["leadership_score"]
        )

        grade = leadership_grade(score)

        with st.container(border=True):
            st.markdown(
                f"### {rank}. "
                f"{shorten_wallet(wallet['wallet'])}"
            )

            st.caption(
                f"{grade} · "
                f"{wallet['wallet_grade']}"
            )

            columns = st.columns(5)

            columns[0].metric(
                "Leadership Score",
                f"{score:.1f}",
            )

            columns[1].metric(
                "Position Value",
                format_money(
                    wallet["current_value"]
                ),
                delta=format_signed_money(
                    wallet["value_change"]
                ),
            )

            columns[2].metric(
                "Capital Share",
                f"{safe_float(wallet['capital_share']):.1%}",
            )

            columns[3].metric(
                "Wallet Rating",
                f"{safe_float(wallet['wallet_score']):.1f}",
            )

            columns[4].metric(
                "Open PnL",
                format_money(
                    wallet["cash_pnl"]
                ),
            )

            if safe_float(wallet["value_change"]) > 0:
                st.success(
                    "This wallet increased its exposure in the "
                    "latest stored scan."
                )

            elif safe_float(wallet["value_change"]) < 0:
                st.warning(
                    "This wallet reduced its exposure in the "
                    "latest stored scan."
                )

            else:
                st.info(
                    "No meaningful capital change was detected "
                    "in the latest scan."
                )

            st.caption(
                f"First observed: {wallet['first_seen']} · "
                f"Average entry: "
                f"{safe_float(wallet['average_price']):.3f} · "
                f"Current price: "
                f"{safe_float(wallet['current_price']):.3f} · "
                f"Shares: "
                f"{safe_float(wallet['shares']):,.2f}"
            )


def display_leadership_table(
    leadership: pd.DataFrame,
) -> None:
    """Display the complete leadership board."""

    st.subheader("Complete Leadership Board")

    frame = leadership.copy()

    frame.insert(
        0,
        "Rank",
        range(1, len(frame) + 1),
    )

    frame["wallet"] = frame["wallet"].apply(
        shorten_wallet
    )

    frame["Leadership Grade"] = frame[
        "leadership_score"
    ].apply(leadership_grade)

    frame["capital_share"] = (
        frame["capital_share"] * 100
    )

    frame["profitable_position_rate"] = (
        frame["profitable_position_rate"] * 100
    )

    frame = frame[
        [
            "Rank",
            "wallet",
            "Leadership Grade",
            "leadership_score",
            "wallet_score",
            "wallet_grade",
            "current_value",
            "value_change",
            "capital_share",
            "shares",
            "share_change",
            "average_price",
            "current_price",
            "cash_pnl",
            "percent_pnl",
            "first_seen",
            "latest_seen",
        ]
    ]

    frame = frame.rename(
        columns={
            "wallet": "Wallet",
            "leadership_score": "Leadership Score",
            "wallet_score": "Wallet Score",
            "wallet_grade": "Wallet Grade",
            "current_value": "Position Value",
            "value_change": "Recent Value Change",
            "capital_share": "Capital Share %",
            "shares": "Shares",
            "share_change": "Recent Share Change",
            "average_price": "Average Entry",
            "current_price": "Current Price",
            "cash_pnl": "Open PnL",
            "percent_pnl": "PnL %",
            "first_seen": "First Seen",
            "latest_seen": "Latest Seen",
        }
    )

    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Leadership Score":
                st.column_config.NumberColumn(
                    format="%.1f",
                ),
            "Wallet Score":
                st.column_config.NumberColumn(
                    format="%.1f",
                ),
            "Position Value":
                st.column_config.NumberColumn(
                    format="$%.2f",
                ),
            "Recent Value Change":
                st.column_config.NumberColumn(
                    format="%+.2f",
                ),
            "Capital Share %":
                st.column_config.NumberColumn(
                    format="%.1f%%",
                ),
            "Shares":
                st.column_config.NumberColumn(
                    format="%.2f",
                ),
            "Recent Share Change":
                st.column_config.NumberColumn(
                    format="%+.2f",
                ),
            "Average Entry":
                st.column_config.NumberColumn(
                    format="%.3f",
                ),
            "Current Price":
                st.column_config.NumberColumn(
                    format="%.3f",
                ),
            "Open PnL":
                st.column_config.NumberColumn(
                    format="$%.2f",
                ),
            "PnL %":
                st.column_config.NumberColumn(
                    format="%.2f%%",
                ),
        },
    )


def display_capital_distribution(
    leadership: pd.DataFrame,
) -> None:
    """Display capital share by supporting wallet."""

    st.subheader("Capital Distribution")

    chart = leadership[
        [
            "wallet",
            "current_value",
        ]
    ].copy()

    chart["wallet"] = chart["wallet"].apply(
        shorten_wallet
    )

    chart = chart.set_index("wallet")

    st.bar_chart(
        chart,
        width="stretch",
    )


def display_leadership_insights(
    leadership: pd.DataFrame,
) -> None:
    """Display key wallet leadership findings."""

    st.subheader("Leadership Intelligence")

    largest_holder = leadership.iloc[
        leadership["current_value"].idxmax()
    ]

    largest_buyer = leadership.iloc[
        leadership["value_change"].idxmax()
    ]

    largest_seller = leadership.iloc[
        leadership["value_change"].idxmin()
    ]

    earliest = leadership.sort_values(
        "first_seen"
    ).iloc[0]

    highest_quality = leadership.iloc[
        leadership["wallet_score"].idxmax()
    ]

    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            st.markdown("### Largest Current Holder")
            st.write(
                shorten_wallet(
                    largest_holder["wallet"]
                )
            )
            st.metric(
                "Position Value",
                format_money(
                    largest_holder[
                        "current_value"
                    ]
                ),
            )

        with st.container(border=True):
            st.markdown("### Earliest Observed Supporter")
            st.write(
                shorten_wallet(
                    earliest["wallet"]
                )
            )
            st.caption(
                f"First seen: {earliest['first_seen']}"
            )

        with st.container(border=True):
            st.markdown("### Highest-Rated Wallet")
            st.write(
                shorten_wallet(
                    highest_quality["wallet"]
                )
            )
            st.metric(
                "Wallet Score",
                f"{safe_float(highest_quality['wallet_score']):.1f}",
            )

    with right:
        with st.container(border=True):
            st.markdown("### Largest Recent Buyer")
            st.write(
                shorten_wallet(
                    largest_buyer["wallet"]
                )
            )
            st.metric(
                "Capital Change",
                format_signed_money(
                    largest_buyer[
                        "value_change"
                    ]
                ),
            )

        with st.container(border=True):
            st.markdown("### Largest Recent Seller")
            st.write(
                shorten_wallet(
                    largest_seller["wallet"]
                )
            )
            st.metric(
                "Capital Change",
                format_signed_money(
                    largest_seller[
                        "value_change"
                    ]
                ),
            )


def main() -> None:
    """Render the Market Leadership page."""

    st.title("🏆 Market Leadership")

    st.caption(
        "Identify which wallets lead each market, who entered "
        "early, who controls the most capital and who is adding "
        "or reducing exposure."
    )

    if not DATABASE_PATH.exists():
        st.error(
            f"Database not found at {DATABASE_PATH}."
        )
        st.stop()

    markets = load_available_markets()

    if markets.empty:
        st.info(
            "No qualifying markets are currently stored. "
            "Run the full platform first."
        )
        st.stop()

    market_options = {
        (
            row["market_id"],
            row["outcome"],
        ): (
            f"{row['title']} — {row['outcome']} "
            f"({safe_int(row['wallet_count'])} wallets, "
            f"{format_money(row['combined_value'])})"
        )
        for _, row in markets.iterrows()
    }

    selected_market = st.selectbox(
        "Choose a market and outcome",
        options=list(market_options.keys()),
        format_func=lambda key: market_options[key],
    )

    selected_row = markets[
        (
            markets["market_id"]
            == selected_market[0]
        )
        & (
            markets["outcome"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == str(selected_market[1])
            .strip()
            .casefold()
        )
    ].iloc[0]

    history = load_market_wallet_history(
        market_id=selected_market[0],
        outcome=selected_market[1],
    )

    ratings = load_latest_wallet_ratings()

    leadership = build_wallet_leadership(
        history=history,
        ratings=ratings,
    )

    if leadership.empty:
        st.warning(
            "No wallet leadership records were returned."
        )
        st.stop()

    st.markdown(
        f"## {selected_row['title']} — "
        f"{selected_row['outcome']}"
    )

    display_market_summary(leadership)

    st.divider()

    insights_tab, rankings_tab, table_tab = st.tabs(
        [
            "Leadership Intelligence",
            "Wallet Rankings",
            "Complete Board",
        ]
    )

    with insights_tab:
        display_leadership_insights(
            leadership
        )

        st.divider()

        display_capital_distribution(
            leadership
        )

    with rankings_tab:
        display_leadership_cards(
            leadership
        )

    with table_tab:
        display_leadership_table(
            leadership
        )

    st.sidebar.header("Leadership Notes")

    st.sidebar.write(
        f"Selected wallets: {len(leadership)}"
    )

    st.sidebar.write(
        "Total tracked capital: "
        f"{format_money(leadership['current_value'].sum())}"
    )

    st.sidebar.divider()

    st.sidebar.caption(
        "Leadership measures current observed influence. "
        "A large wallet may still be wrong, overexposed or late."
    )


if __name__ == "__main__":
    main()