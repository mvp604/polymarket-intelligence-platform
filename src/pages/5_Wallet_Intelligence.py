from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


st.set_page_config(
    page_title="Wallet Intelligence",
    page_icon="🧬",
    layout="wide",
)


# =============================================================================
# DATABASE HELPERS
# =============================================================================


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
    """Convert a value into a float safely."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value into an integer safely."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def format_money(value: Any) -> str:
    """Format a value as currency."""

    return f"${safe_float(value):,.2f}"


def format_signed_money(value: Any) -> str:
    """Format a signed currency value."""

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


# =============================================================================
# DATA LOADERS
# =============================================================================


def load_wallet_profiles() -> pd.DataFrame:
    """Load current Wallet DNA profiles."""

    if not table_exists("wallet_profiles"):
        return pd.DataFrame()

    return safe_query(
        """
        SELECT
            wallet,
            wallet_score,
            wallet_grade,
            scan_count,
            active_position_count,
            meaningful_position_count,
            total_current_value,
            total_open_pnl,
            open_pnl_ratio,
            profitable_position_rate,
            average_position_value,
            median_position_value,
            largest_position_value,
            concentration_ratio,
            average_entry_price,
            average_current_price,
            average_observed_move,
            sports_exposure,
            politics_exposure,
            crypto_exposure,
            macro_exposure,
            entertainment_exposure,
            other_exposure,
            favorite_category,
            activity_style,
            risk_profile,
            leader_score,
            activity_score,
            specialization_score,
            dna_score,
            dna_grade,
            first_observed_at,
            latest_observed_at,
            calculated_at
        FROM wallet_profiles
        ORDER BY
            dna_score DESC,
            wallet_score DESC,
            total_current_value DESC
        """
    )


def load_wallet_profile_history(
    wallet: str,
) -> pd.DataFrame:
    """Load historical DNA snapshots for one wallet."""

    if not table_exists("wallet_profile_history"):
        return pd.DataFrame()

    return safe_query(
        """
        SELECT
            id,
            wallet_score,
            wallet_grade,
            total_current_value,
            total_open_pnl,
            open_pnl_ratio,
            active_position_count,
            meaningful_position_count,
            profitable_position_rate,
            concentration_ratio,
            favorite_category,
            activity_style,
            risk_profile,
            leader_score,
            activity_score,
            specialization_score,
            dna_score,
            dna_grade,
            calculated_at
        FROM wallet_profile_history
        WHERE LOWER(wallet) = LOWER(?)
        ORDER BY calculated_at ASC, id ASC
        """,
        (wallet,),
    )


def load_wallet_activity(
    wallet: str,
    limit: int = 100,
) -> pd.DataFrame:
    """Load recent normalized activity for one wallet."""

    if not table_exists("wallet_activity"):
        return pd.DataFrame()

    return safe_query(
        """
        SELECT
            id,
            scan_id,
            previous_scan_id,
            market_id,
            title,
            outcome,
            activity_type,
            previous_shares,
            current_shares,
            share_change,
            previous_value,
            current_value,
            value_change,
            previous_price,
            current_price,
            price_change,
            detected_at
        FROM wallet_activity
        WHERE LOWER(wallet) = LOWER(?)
        ORDER BY detected_at DESC, id DESC
        LIMIT ?
        """,
        (
            wallet,
            limit,
        ),
    )


def load_latest_positions(
    wallet: str,
) -> pd.DataFrame:
    """Load positions from the wallet's latest scan."""

    if not table_exists("positions"):
        return pd.DataFrame()

    return safe_query(
        """
        WITH latest_scan AS (
            SELECT
                MAX(id) AS scan_id
            FROM wallet_scans
            WHERE LOWER(wallet) = LOWER(?)
        )
        SELECT
            positions.market_id,
            positions.title,
            positions.outcome,
            positions.shares,
            positions.average_price,
            positions.current_price,
            positions.current_value,
            positions.cash_pnl,
            positions.percent_pnl
        FROM positions
        INNER JOIN latest_scan
            ON positions.scan_id = latest_scan.scan_id
        WHERE LOWER(positions.wallet) = LOWER(?)
        ORDER BY
            positions.current_value DESC,
            positions.cash_pnl DESC
        """,
        (
            wallet,
            wallet,
        ),
    )


def load_wallet_scan_history(
    wallet: str,
) -> pd.DataFrame:
    """Load scan history for one wallet."""

    if not table_exists("wallet_scans"):
        return pd.DataFrame()

    return safe_query(
        """
        SELECT
            id AS scan_id,
            scanned_at
        FROM wallet_scans
        WHERE LOWER(wallet) = LOWER(?)
        ORDER BY scanned_at ASC, id ASC
        """,
        (wallet,),
    )


# =============================================================================
# PROFILE HELPERS
# =============================================================================


def get_selected_profile(
    profiles: pd.DataFrame,
    wallet: str,
) -> pd.Series:
    """Return one selected wallet profile."""

    matching = profiles[
        profiles["wallet"]
        .astype(str)
        .str.casefold()
        == str(wallet).casefold()
    ]

    if matching.empty:
        raise ValueError(
            "The selected wallet profile could not be found."
        )

    return matching.iloc[0]


def activity_summary(
    activity: pd.DataFrame,
) -> dict[str, int]:
    """Count activity records by activity type."""

    summary = {
        "NEW": 0,
        "INCREASED": 0,
        "REDUCED": 0,
        "CLOSED": 0,
        "VALUE_INCREASED": 0,
        "VALUE_DECREASED": 0,
    }

    if activity.empty:
        return summary

    counts = (
        activity["activity_type"]
        .fillna("UNKNOWN")
        .astype(str)
        .value_counts()
        .to_dict()
    )

    for key in summary:
        summary[key] = safe_int(
            counts.get(key, 0)
        )

    return summary


def dna_description(profile: pd.Series) -> str:
    """Build a transparent Wallet DNA interpretation."""

    dna_score = safe_float(
        profile["dna_score"]
    )

    wallet_score = safe_float(
        profile["wallet_score"]
    )

    leader_score = safe_float(
        profile["leader_score"]
    )

    activity_score = safe_float(
        profile["activity_score"]
    )

    specialization_score = safe_float(
        profile["specialization_score"]
    )

    favorite_category = str(
        profile["favorite_category"]
        or "Unknown"
    )

    activity_style = str(
        profile["activity_style"]
        or "Unknown"
    )

    risk_profile = str(
        profile["risk_profile"]
        or "Unknown"
    )

    concentration = safe_float(
        profile["concentration_ratio"]
    )

    observations: list[str] = []

    if dna_score >= 75:
        observations.append(
            "This wallet currently ranks as a high-priority "
            "research wallet within the tracked dataset."
        )
    elif dna_score >= 55:
        observations.append(
            "This wallet has a developing intelligence profile "
            "but still requires continued observation."
        )
    else:
        observations.append(
            "This wallet currently has limited or mixed evidence."
        )

    observations.append(
        f"Its strongest observed market specialization is "
        f"{favorite_category}."
    )

    observations.append(
        f"The current activity style is classified as "
        f"{activity_style}, with a {risk_profile.lower()} "
        f"risk profile."
    )

    if concentration >= 0.70:
        observations.append(
            "The portfolio is highly concentrated, meaning one "
            "position can strongly influence the wallet's results."
        )
    elif concentration >= 0.45:
        observations.append(
            "The portfolio has meaningful concentration risk."
        )
    else:
        observations.append(
            "Capital is relatively distributed across positions."
        )

    if leader_score >= 75:
        observations.append(
            "The wallet shows strong observed leadership characteristics."
        )
    elif leader_score >= 55:
        observations.append(
            "The wallet has moderate market-leadership evidence."
        )

    if activity_score < 25:
        observations.append(
            "Recorded activity remains limited, so behavior labels "
            "may change as additional scans are collected."
        )

    if specialization_score >= 80:
        observations.append(
            "The wallet is highly specialized rather than broadly diversified."
        )

    observations.append(
        f"Current component scores are wallet quality "
        f"{wallet_score:.1f}, leadership {leader_score:.1f}, "
        f"activity {activity_score:.1f}, and specialization "
        f"{specialization_score:.1f}."
    )

    return " ".join(observations)


# =============================================================================
# DISPLAY COMPONENTS
# =============================================================================


def display_platform_summary(
    profiles: pd.DataFrame,
) -> None:
    """Display Wallet Intelligence platform summary."""

    elite_wallets = int(
        (
            profiles["dna_score"] >= 75
        ).sum()
    )

    high_risk_wallets = int(
        profiles["risk_profile"]
        .astype(str)
        .isin(
            [
                "High",
                "Very High",
            ]
        )
        .sum()
    )

    total_capital = safe_float(
        profiles["total_current_value"].sum()
    )

    categories = int(
        profiles["favorite_category"]
        .dropna()
        .nunique()
    )

    columns = st.columns(5)

    columns[0].metric(
        "Wallet Profiles",
        len(profiles),
    )

    columns[1].metric(
        "DNA S / S+",
        elite_wallets,
    )

    columns[2].metric(
        "Tracked Capital",
        format_money(total_capital),
    )

    columns[3].metric(
        "High-Risk Profiles",
        high_risk_wallets,
    )

    columns[4].metric(
        "Specializations",
        categories,
    )


def display_profile_header(
    profile: pd.Series,
) -> None:
    """Display top wallet-profile metrics."""

    wallet = str(profile["wallet"])

    st.markdown(
        f"## 🧬 {shorten_wallet(wallet)}"
    )

    st.code(
        wallet,
        language="text",
    )

    st.caption(
        f"DNA grade: {profile['dna_grade']} · "
        f"Wallet grade: {profile['wallet_grade']} · "
        f"Calculated: {profile['calculated_at']}"
    )

    columns = st.columns(6)

    columns[0].metric(
        "DNA Score",
        f"{safe_float(profile['dna_score']):.1f}/100",
    )

    columns[1].metric(
        "Wallet Score",
        f"{safe_float(profile['wallet_score']):.1f}",
    )

    columns[2].metric(
        "Leader Score",
        f"{safe_float(profile['leader_score']):.1f}",
    )

    columns[3].metric(
        "Activity Score",
        f"{safe_float(profile['activity_score']):.1f}",
    )

    columns[4].metric(
        "Specialization",
        f"{safe_float(profile['specialization_score']):.1f}",
    )

    columns[5].metric(
        "Risk Profile",
        str(profile["risk_profile"]),
    )


def display_capital_metrics(
    profile: pd.Series,
) -> None:
    """Display wallet capital and performance metrics."""

    st.subheader("Capital and Portfolio Profile")

    row_1 = st.columns(5)

    row_1[0].metric(
        "Current Value",
        format_money(
            profile["total_current_value"]
        ),
    )

    row_1[1].metric(
        "Open PnL",
        format_money(
            profile["total_open_pnl"]
        ),
    )

    row_1[2].metric(
        "Open PnL Ratio",
        f"{safe_float(profile['open_pnl_ratio']):.1%}",
    )

    row_1[3].metric(
        "Profitable Positions",
        f"{safe_float(profile['profitable_position_rate']):.1%}",
    )

    row_1[4].metric(
        "Largest Position Share",
        f"{safe_float(profile['concentration_ratio']):.1%}",
    )

    row_2 = st.columns(5)

    row_2[0].metric(
        "Active Positions",
        safe_int(
            profile["active_position_count"]
        ),
    )

    row_2[1].metric(
        "Positions $500+",
        safe_int(
            profile["meaningful_position_count"]
        ),
    )

    row_2[2].metric(
        "Average Position",
        format_money(
            profile["average_position_value"]
        ),
    )

    row_2[3].metric(
        "Median Position",
        format_money(
            profile["median_position_value"]
        ),
    )

    row_2[4].metric(
        "Largest Position",
        format_money(
            profile["largest_position_value"]
        ),
    )

    st.caption(
        f"Weighted average entry: "
        f"{safe_float(profile['average_entry_price']):.3f} · "
        f"Weighted current price: "
        f"{safe_float(profile['average_current_price']):.3f} · "
        f"Observed move: "
        f"{safe_float(profile['average_observed_move']):+.3f}"
    )


def display_behavior_profile(
    profile: pd.Series,
) -> None:
    """Display behavioral Wallet DNA labels."""

    st.subheader("Behavioral DNA")

    columns = st.columns(4)

    columns[0].metric(
        "Activity Style",
        str(profile["activity_style"]),
    )

    columns[1].metric(
        "Favorite Category",
        str(profile["favorite_category"]),
    )

    columns[2].metric(
        "Risk Profile",
        str(profile["risk_profile"]),
    )

    columns[3].metric(
        "Stored Scans",
        safe_int(profile["scan_count"]),
    )

    with st.container(border=True):
        st.markdown("### Wallet DNA Interpretation")
        st.write(
            dna_description(profile)
        )

        st.caption(
            "This interpretation is based on observed open "
            "positions and stored scan history. It is not yet "
            "a resolved-market skill assessment."
        )


def display_category_exposure(
    profile: pd.Series,
) -> None:
    """Display category exposure percentages."""

    st.subheader("Market Specialization")

    exposure_rows = [
        {
            "Category": "Sports",
            "Exposure": safe_float(
                profile["sports_exposure"]
            ),
        },
        {
            "Category": "Politics",
            "Exposure": safe_float(
                profile["politics_exposure"]
            ),
        },
        {
            "Category": "Crypto",
            "Exposure": safe_float(
                profile["crypto_exposure"]
            ),
        },
        {
            "Category": "Macro",
            "Exposure": safe_float(
                profile["macro_exposure"]
            ),
        },
        {
            "Category": "Entertainment",
            "Exposure": safe_float(
                profile["entertainment_exposure"]
            ),
        },
        {
            "Category": "Other",
            "Exposure": safe_float(
                profile["other_exposure"]
            ),
        },
    ]

    exposure_frame = pd.DataFrame(
        exposure_rows
    ).sort_values(
        "Exposure",
        ascending=False,
    )

    chart_frame = exposure_frame.copy()
    chart_frame = chart_frame.set_index(
        "Category"
    )

    st.bar_chart(
        chart_frame,
        width="stretch",
    )

    display_frame = exposure_frame.copy()

    display_frame["Exposure"] = (
        display_frame["Exposure"] * 100
    )

    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Exposure": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
        },
    )


def display_activity_summary(
    activity: pd.DataFrame,
) -> None:
    """Display summarized wallet activity."""

    st.subheader("Activity Intelligence")

    counts = activity_summary(activity)

    row_1 = st.columns(4)

    row_1[0].metric(
        "New Positions",
        counts["NEW"],
    )

    row_1[1].metric(
        "Increased",
        counts["INCREASED"],
    )

    row_1[2].metric(
        "Reduced",
        counts["REDUCED"],
    )

    row_1[3].metric(
        "Closed",
        counts["CLOSED"],
    )

    if activity.empty:
        st.info(
            "No normalized wallet-activity records are available yet. "
            "Run the Wallet Intelligence Engine after at least two "
            "wallet scans."
        )
        return

    activity_by_type = (
        activity["activity_type"]
        .astype(str)
        .value_counts()
        .rename_axis("Activity Type")
        .reset_index(name="Count")
    )

    st.bar_chart(
        activity_by_type.set_index(
            "Activity Type"
        ),
        width="stretch",
    )


def display_recent_activity(
    activity: pd.DataFrame,
) -> None:
    """Display recent wallet activity records."""

    st.subheader("Recent Wallet Activity")

    if activity.empty:
        st.info(
            "No recorded activity is available for this wallet."
        )
        return

    display_frame = activity[
        [
            "detected_at",
            "activity_type",
            "title",
            "outcome",
            "previous_value",
            "current_value",
            "value_change",
            "previous_shares",
            "current_shares",
            "share_change",
            "previous_price",
            "current_price",
            "price_change",
        ]
    ].copy()

    display_frame = display_frame.rename(
        columns={
            "detected_at": "Detected At",
            "activity_type": "Activity",
            "title": "Market",
            "outcome": "Outcome",
            "previous_value": "Previous Value",
            "current_value": "Current Value",
            "value_change": "Value Change",
            "previous_shares": "Previous Shares",
            "current_shares": "Current Shares",
            "share_change": "Share Change",
            "previous_price": "Previous Price",
            "current_price": "Current Price",
            "price_change": "Price Change",
        }
    )

    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Previous Value": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Current Value": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Value Change": st.column_config.NumberColumn(
                format="%+.2f",
            ),
            "Previous Shares": st.column_config.NumberColumn(
                format="%.2f",
            ),
            "Current Shares": st.column_config.NumberColumn(
                format="%.2f",
            ),
            "Share Change": st.column_config.NumberColumn(
                format="%+.2f",
            ),
            "Previous Price": st.column_config.NumberColumn(
                format="%.3f",
            ),
            "Current Price": st.column_config.NumberColumn(
                format="%.3f",
            ),
            "Price Change": st.column_config.NumberColumn(
                format="%+.3f",
            ),
        },
    )


def display_current_positions(
    positions: pd.DataFrame,
) -> None:
    """Display positions from the latest wallet scan."""

    st.subheader("Current Portfolio")

    if positions.empty:
        st.info(
            "No positions were found in the wallet's latest scan."
        )
        return

    display_frame = positions[
        [
            "title",
            "outcome",
            "shares",
            "average_price",
            "current_price",
            "current_value",
            "cash_pnl",
            "percent_pnl",
        ]
    ].copy()

    display_frame = display_frame.rename(
        columns={
            "title": "Market",
            "outcome": "Outcome",
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


def display_profile_history(
    history: pd.DataFrame,
) -> None:
    """Display historical Wallet DNA development."""

    st.subheader("Wallet DNA Timeline")

    if history.empty:
        st.info(
            "No Wallet DNA history has been stored yet."
        )
        return

    chart_data = history.copy()

    chart_data["calculated_at"] = pd.to_datetime(
        chart_data["calculated_at"],
        errors="coerce",
        utc=True,
    )

    chart_data = chart_data.dropna(
        subset=["calculated_at"]
    ).set_index("calculated_at")

    if chart_data.empty:
        st.info(
            "Historical timestamps could not be parsed."
        )
        return

    row_1_left, row_1_right = st.columns(2)

    with row_1_left:
        st.caption("DNA and Wallet Scores")

        st.line_chart(
            chart_data[
                [
                    "dna_score",
                    "wallet_score",
                ]
            ],
            width="stretch",
        )

    with row_1_right:
        st.caption("Leadership and Activity Scores")

        st.line_chart(
            chart_data[
                [
                    "leader_score",
                    "activity_score",
                ]
            ],
            width="stretch",
        )

    row_2_left, row_2_right = st.columns(2)

    with row_2_left:
        st.caption("Total Current Value")

        st.line_chart(
            chart_data[
                ["total_current_value"]
            ],
            width="stretch",
        )

    with row_2_right:
        st.caption("Open PnL")

        st.line_chart(
            chart_data[
                ["total_open_pnl"]
            ],
            width="stretch",
        )

    display_frame = history.copy()

    display_frame["open_pnl_ratio"] = (
        display_frame["open_pnl_ratio"] * 100
    )

    display_frame["profitable_position_rate"] = (
        display_frame[
            "profitable_position_rate"
        ]
        * 100
    )

    display_frame["concentration_ratio"] = (
        display_frame[
            "concentration_ratio"
        ]
        * 100
    )

    display_frame = display_frame.rename(
        columns={
            "calculated_at": "Calculated At",
            "dna_score": "DNA Score",
            "dna_grade": "DNA Grade",
            "wallet_score": "Wallet Score",
            "wallet_grade": "Wallet Grade",
            "leader_score": "Leader Score",
            "activity_score": "Activity Score",
            "specialization_score": "Specialization",
            "total_current_value": "Current Value",
            "total_open_pnl": "Open PnL",
            "open_pnl_ratio": "Open PnL %",
            "active_position_count": "Active Positions",
            "meaningful_position_count": "Positions $500+",
            "profitable_position_rate": "Profitable Positions %",
            "concentration_ratio": "Concentration %",
            "favorite_category": "Favorite Category",
            "activity_style": "Activity Style",
            "risk_profile": "Risk Profile",
        }
    )

    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "DNA Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Wallet Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Leader Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Activity Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Specialization": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Current Value": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Open PnL": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Open PnL %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
            "Profitable Positions %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
            "Concentration %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
        },
    )


def display_all_wallet_rankings(
    profiles: pd.DataFrame,
) -> None:
    """Display complete Wallet DNA rankings."""

    st.subheader("Complete Wallet DNA Rankings")

    frame = profiles.copy()

    frame.insert(
        0,
        "Rank",
        range(1, len(frame) + 1),
    )

    frame["wallet"] = frame["wallet"].apply(
        shorten_wallet
    )

    frame["open_pnl_ratio"] = (
        frame["open_pnl_ratio"] * 100
    )

    frame["profitable_position_rate"] = (
        frame["profitable_position_rate"]
        * 100
    )

    frame["concentration_ratio"] = (
        frame["concentration_ratio"] * 100
    )

    frame = frame[
        [
            "Rank",
            "wallet",
            "dna_score",
            "dna_grade",
            "wallet_score",
            "wallet_grade",
            "leader_score",
            "activity_score",
            "specialization_score",
            "favorite_category",
            "activity_style",
            "risk_profile",
            "scan_count",
            "active_position_count",
            "meaningful_position_count",
            "total_current_value",
            "total_open_pnl",
            "open_pnl_ratio",
            "profitable_position_rate",
            "concentration_ratio",
            "latest_observed_at",
            "calculated_at",
        ]
    ]

    frame = frame.rename(
        columns={
            "wallet": "Wallet",
            "dna_score": "DNA Score",
            "dna_grade": "DNA Grade",
            "wallet_score": "Wallet Score",
            "wallet_grade": "Wallet Grade",
            "leader_score": "Leader Score",
            "activity_score": "Activity Score",
            "specialization_score": "Specialization",
            "favorite_category": "Favorite Category",
            "activity_style": "Activity Style",
            "risk_profile": "Risk Profile",
            "scan_count": "Scans",
            "active_position_count": "Active Positions",
            "meaningful_position_count": "Positions $500+",
            "total_current_value": "Current Value",
            "total_open_pnl": "Open PnL",
            "open_pnl_ratio": "Open PnL %",
            "profitable_position_rate": "Profitable Positions %",
            "concentration_ratio": "Concentration %",
            "latest_observed_at": "Latest Observed",
            "calculated_at": "DNA Calculated",
        }
    )

    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "DNA Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Wallet Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Leader Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Activity Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Specialization": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Current Value": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Open PnL": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Open PnL %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
            "Profitable Positions %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
            "Concentration %": st.column_config.NumberColumn(
                format="%.1f%%",
            ),
        },
    )


# =============================================================================
# MAIN PAGE
# =============================================================================


def main() -> None:
    """Render the Wallet Intelligence page."""

    st.title("🧬 Wallet Intelligence")

    st.caption(
        "Inspect wallet quality, behavioral DNA, market "
        "specialization, capital deployment and observed activity."
    )

    if not DATABASE_PATH.exists():
        st.error(
            f"Database not found at {DATABASE_PATH}."
        )
        st.stop()

    profiles = load_wallet_profiles()

    if profiles.empty:
        st.info(
            "No Wallet DNA profiles have been generated yet."
        )

        st.code(
            "python src/wallet_intelligence_engine.py",
            language="powershell",
        )

        st.caption(
            "Run the Wallet Intelligence Engine, then refresh this page."
        )

        st.stop()

    display_platform_summary(profiles)

    st.divider()

    st.sidebar.header("Wallet Intelligence Filters")

    category_options = sorted(
        profiles["favorite_category"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_categories = st.sidebar.multiselect(
        "Favorite categories",
        options=category_options,
        default=category_options,
    )

    risk_options = sorted(
        profiles["risk_profile"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_risks = st.sidebar.multiselect(
        "Risk profiles",
        options=risk_options,
        default=risk_options,
    )

    minimum_dna_score = st.sidebar.slider(
        "Minimum DNA score",
        min_value=0,
        max_value=100,
        value=0,
        step=1,
    )

    filtered_profiles = profiles[
        profiles["favorite_category"].isin(
            selected_categories
        )
        & profiles["risk_profile"].isin(
            selected_risks
        )
        & (
            profiles["dna_score"]
            >= minimum_dna_score
        )
    ].copy()

    if filtered_profiles.empty:
        st.warning(
            "No wallet profiles match the current filters."
        )
        st.stop()

    wallet_options = (
        filtered_profiles["wallet"]
        .astype(str)
        .tolist()
    )

    selected_wallet = st.selectbox(
        "Choose a wallet",
        options=wallet_options,
        format_func=lambda wallet: (
            f"{shorten_wallet(wallet)} — "
            f"DNA {safe_float(get_selected_profile(filtered_profiles, wallet)['dna_score']):.1f} — "
            f"{get_selected_profile(filtered_profiles, wallet)['favorite_category']}"
        ),
    )

    profile = get_selected_profile(
        profiles,
        selected_wallet,
    )

    profile_history = load_wallet_profile_history(
        selected_wallet
    )

    activity = load_wallet_activity(
        selected_wallet,
        limit=200,
    )

    positions = load_latest_positions(
        selected_wallet
    )

    display_profile_header(profile)

    st.divider()

    overview_tab, activity_tab, portfolio_tab, history_tab, rankings_tab = (
        st.tabs(
            [
                "Wallet DNA Overview",
                "Activity Intelligence",
                "Current Portfolio",
                "DNA Timeline",
                "All Wallet Rankings",
            ]
        )
    )

    with overview_tab:
        display_capital_metrics(profile)

        st.divider()

        display_behavior_profile(profile)

        st.divider()

        display_category_exposure(profile)

    with activity_tab:
        display_activity_summary(activity)

        st.divider()

        display_recent_activity(activity)

    with portfolio_tab:
        display_current_positions(positions)

    with history_tab:
        display_profile_history(
            profile_history
        )

    with rankings_tab:
        display_all_wallet_rankings(
            filtered_profiles
        )

    st.sidebar.divider()

    st.sidebar.write(
        f"First observed: "
        f"{profile['first_observed_at']}"
    )

    st.sidebar.write(
        f"Latest observed: "
        f"{profile['latest_observed_at']}"
    )

    st.sidebar.write(
        f"DNA calculated: "
        f"{profile['calculated_at']}"
    )

    st.sidebar.caption(
        "Wallet DNA is provisional and based on observable "
        "open positions, scan history and current wallet ratings. "
        "Resolved-market performance will improve these profiles later."
    )


if __name__ == "__main__":
    main()