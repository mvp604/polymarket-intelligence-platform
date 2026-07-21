from __future__ import annotations

import math
import sqlite3
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence_database import create_intelligence_tables


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

MINIMUM_MEANINGFUL_POSITION_VALUE = 500.0
MINIMUM_ACTIVITY_SHARE_CHANGE = 1.0
MINIMUM_ACTIVITY_VALUE_CHANGE = 25.0


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Sports": (
        "world cup",
        "nba",
        "nfl",
        "nhl",
        "mlb",
        "wnba",
        "soccer",
        "football",
        "basketball",
        "baseball",
        "tennis",
        "open:",
        "vs.",
        "spread:",
        "exact score",
        "both teams",
        "o/u",
        "win on",
        "leading at halftime",
        "championship",
        "premier league",
        "champions league",
        "ufc",
        "boxing",
        "formula 1",
        "f1",
    ),
    "Politics": (
        "president",
        "presidential",
        "democratic",
        "republican",
        "prime minister",
        "senate",
        "house",
        "congress",
        "election",
        "nomination",
        "governor",
        "cabinet",
        "parliament",
        "balance of power",
        "approval rating",
    ),
    "Crypto": (
        "bitcoin",
        "btc",
        "ethereum",
        "eth",
        "solana",
        "crypto",
        "token",
        "blockchain",
        "coinbase",
        "binance",
        "dogecoin",
        "xrp",
    ),
    "Macro": (
        "fed",
        "federal reserve",
        "interest rate",
        "inflation",
        "cpi",
        "gdp",
        "recession",
        "unemployment",
        "treasury",
        "tariff",
        "oil price",
        "gold price",
        "s&p",
        "nasdaq",
        "dow",
    ),
    "Entertainment": (
        "oscar",
        "academy award",
        "grammy",
        "emmy",
        "movie",
        "film",
        "box office",
        "album",
        "song",
        "celebrity",
        "television",
        "tv show",
        "netflix",
        "youtube",
    ),
}


def connect_database() -> sqlite3.Connection:
    """Open the main SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}. "
            "Run the scanner first."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


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
    """Keep a numerical value inside a defined range."""

    return max(minimum, min(value, maximum))


def utc_now() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: Any) -> str:
    """Normalize text for matching."""

    return str(value or "").strip().casefold()


def weighted_average(
    values_and_weights: list[tuple[float, float]],
) -> float:
    """Calculate a safe weighted average."""

    total_weight = sum(
        max(weight, 0.0)
        for _, weight in values_and_weights
    )

    if total_weight <= 0:
        return 0.0

    weighted_total = sum(
        value * max(weight, 0.0)
        for value, weight in values_and_weights
    )

    return weighted_total / total_weight


def classify_category(title: str) -> str:
    """Classify a market title into a broad category."""

    normalized_title = normalize_text(title)

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(
            keyword.casefold() in normalized_title
            for keyword in keywords
        ):
            return category

    return "Other"


def load_latest_wallet_ratings() -> dict[str, dict[str, Any]]:
    """Load the newest wallet rating record per wallet."""

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            WITH latest_ratings AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_id
                FROM wallet_rating_history
                GROUP BY wallet
            )
            SELECT
                rating.*
            FROM wallet_rating_history AS rating
            INNER JOIN latest_ratings AS latest
                ON rating.id = latest.latest_id
            """
        ).fetchall()

        return {
            normalize_text(row["wallet"]): dict(row)
            for row in rows
        }

    finally:
        connection.close()


def load_wallet_scan_metadata() -> dict[str, dict[str, Any]]:
    """Load scan counts and first/latest observation times."""

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT
                wallet,
                COUNT(*) AS scan_count,
                MIN(scanned_at) AS first_observed_at,
                MAX(scanned_at) AS latest_observed_at,
                MAX(id) AS latest_scan_id
            FROM wallet_scans
            GROUP BY wallet
            """
        ).fetchall()

        return {
            normalize_text(row["wallet"]): dict(row)
            for row in rows
        }

    finally:
        connection.close()


def load_latest_positions() -> dict[str, list[dict[str, Any]]]:
    """Load positions from each wallet's newest scan."""

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            WITH latest_scans AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_scan_id
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT
                positions.*
            FROM positions
            INNER JOIN latest_scans
                ON positions.wallet = latest_scans.wallet
               AND positions.scan_id = latest_scans.latest_scan_id
            ORDER BY
                positions.wallet,
                positions.current_value DESC
            """
        ).fetchall()

    finally:
        connection.close()

    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        wallet = normalize_text(row["wallet"])

        grouped.setdefault(wallet, []).append(
            dict(row)
        )

    return grouped


def load_latest_two_scans(
    wallet: str,
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    """Load current and previous scan metadata for a wallet."""

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                wallet,
                scanned_at
            FROM wallet_scans
            WHERE LOWER(wallet) = LOWER(?)
            ORDER BY id DESC
            LIMIT 2
            """,
            (wallet,),
        ).fetchall()

    finally:
        connection.close()

    current = dict(rows[0]) if len(rows) >= 1 else None
    previous = dict(rows[1]) if len(rows) >= 2 else None

    return current, previous


def load_positions_for_scan(
    scan_id: int,
) -> list[dict[str, Any]]:
    """Load positions connected to one scan."""

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT
                market_id,
                title,
                outcome,
                shares,
                average_price,
                current_price,
                current_value,
                cash_pnl,
                percent_pnl
            FROM positions
            WHERE scan_id = ?
            """,
            (scan_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def position_key(
    position: dict[str, Any],
) -> tuple[str, str]:
    """Create a stable market and outcome key."""

    market_id = normalize_text(
        position.get("market_id")
    )

    if not market_id:
        market_id = normalize_text(
            position.get("title")
        )

    outcome = normalize_text(
        position.get("outcome")
    )

    return market_id, outcome


def determine_activity_type(
    previous_shares: float,
    current_shares: float,
    previous_value: float,
    current_value: float,
) -> str | None:
    """Classify a position change."""

    if previous_shares <= 0 and current_shares > 0:
        return "NEW"

    if previous_shares > 0 and current_shares <= 0:
        return "CLOSED"

    share_change = current_shares - previous_shares
    value_change = current_value - previous_value

    meaningful_share_change = (
        abs(share_change)
        >= MINIMUM_ACTIVITY_SHARE_CHANGE
    )

    meaningful_value_change = (
        abs(value_change)
        >= MINIMUM_ACTIVITY_VALUE_CHANGE
    )

    if not (
        meaningful_share_change
        or meaningful_value_change
    ):
        return None

    if share_change > 0:
        return "INCREASED"

    if share_change < 0:
        return "REDUCED"

    if value_change > 0:
        return "VALUE_INCREASED"

    if value_change < 0:
        return "VALUE_DECREASED"

    return None


def build_wallet_activity(
    wallet: str,
) -> list[dict[str, Any]]:
    """Compare the wallet's latest two scans."""

    current_scan, previous_scan = (
        load_latest_two_scans(wallet)
    )

    if current_scan is None or previous_scan is None:
        return []

    current_positions = load_positions_for_scan(
        safe_int(current_scan["id"])
    )

    previous_positions = load_positions_for_scan(
        safe_int(previous_scan["id"])
    )

    current_lookup = {
        position_key(position): position
        for position in current_positions
    }

    previous_lookup = {
        position_key(position): position
        for position in previous_positions
    }

    all_keys = set(current_lookup) | set(previous_lookup)

    activities: list[dict[str, Any]] = []

    for key in all_keys:
        current = current_lookup.get(key, {})
        previous = previous_lookup.get(key, {})

        previous_shares = safe_float(
            previous.get("shares")
        )
        current_shares = safe_float(
            current.get("shares")
        )

        previous_value = safe_float(
            previous.get("current_value")
        )
        current_value = safe_float(
            current.get("current_value")
        )

        activity_type = determine_activity_type(
            previous_shares=previous_shares,
            current_shares=current_shares,
            previous_value=previous_value,
            current_value=current_value,
        )

        if activity_type is None:
            continue

        source = current or previous

        previous_price = safe_float(
            previous.get("current_price")
        )
        current_price = safe_float(
            current.get("current_price")
        )

        activities.append(
            {
                "wallet": wallet,
                "scan_id": safe_int(
                    current_scan["id"]
                ),
                "previous_scan_id": safe_int(
                    previous_scan["id"]
                ),
                "market_id": str(
                    source.get("market_id") or ""
                ),
                "title": str(
                    source.get("title")
                    or "Unknown market"
                ),
                "outcome": str(
                    source.get("outcome")
                    or "Unknown"
                ),
                "activity_type": activity_type,
                "previous_shares": previous_shares,
                "current_shares": current_shares,
                "share_change": (
                    current_shares - previous_shares
                ),
                "previous_value": previous_value,
                "current_value": current_value,
                "value_change": (
                    current_value - previous_value
                ),
                "previous_price": previous_price,
                "current_price": current_price,
                "price_change": (
                    current_price - previous_price
                ),
                "detected_at": str(
                    current_scan["scanned_at"]
                ),
            }
        )

    return activities


def save_wallet_activity(
    activities: list[dict[str, Any]],
) -> int:
    """Save newly detected wallet activity."""

    if not activities:
        return 0

    connection = connect_database()
    rows_created = 0

    try:
        for activity in activities:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO wallet_activity (
                    wallet,
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
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    activity["wallet"],
                    activity["scan_id"],
                    activity["previous_scan_id"],
                    activity["market_id"],
                    activity["title"],
                    activity["outcome"],
                    activity["activity_type"],
                    activity["previous_shares"],
                    activity["current_shares"],
                    activity["share_change"],
                    activity["previous_value"],
                    activity["current_value"],
                    activity["value_change"],
                    activity["previous_price"],
                    activity["current_price"],
                    activity["price_change"],
                    activity["detected_at"],
                ),
            )

            rows_created += max(
                cursor.rowcount,
                0,
            )

        connection.commit()
        return rows_created

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def load_activity_counts(
    wallet: str,
) -> dict[str, int]:
    """Count stored activity types for one wallet."""

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT
                activity_type,
                COUNT(*) AS total
            FROM wallet_activity
            WHERE LOWER(wallet) = LOWER(?)
            GROUP BY activity_type
            """,
            (wallet,),
        ).fetchall()

        return {
            str(row["activity_type"]): safe_int(
                row["total"]
            )
            for row in rows
        }

    finally:
        connection.close()


def calculate_category_exposure(
    positions: list[dict[str, Any]],
) -> dict[str, float]:
    """Calculate portfolio value by category."""

    category_values = {
        "Sports": 0.0,
        "Politics": 0.0,
        "Crypto": 0.0,
        "Macro": 0.0,
        "Entertainment": 0.0,
        "Other": 0.0,
    }

    for position in positions:
        value = max(
            safe_float(
                position.get("current_value")
            ),
            0.0,
        )

        category = classify_category(
            str(position.get("title") or "")
        )

        category_values[category] += value

    total_value = sum(
        category_values.values()
    )

    if total_value <= 0:
        return {
            category: 0.0
            for category in category_values
        }

    return {
        category: value / total_value
        for category, value
        in category_values.items()
    }


def classify_activity_style(
    activity_counts: dict[str, int],
    concentration_ratio: float,
    active_position_count: int,
) -> str:
    """Classify the wallet's observed activity style."""

    new_count = activity_counts.get("NEW", 0)
    increased_count = activity_counts.get(
        "INCREASED",
        0,
    )

    reduced_count = activity_counts.get(
        "REDUCED",
        0,
    )

    closed_count = activity_counts.get(
        "CLOSED",
        0,
    )

    additions = new_count + increased_count
    reductions = reduced_count + closed_count
    total_actions = additions + reductions

    if total_actions == 0:
        if concentration_ratio >= 0.70:
            return "Concentrated Holder"

        if active_position_count >= 15:
            return "Diversified Holder"

        return "Low Activity"

    turnover_ratio = (
        reductions / total_actions
        if total_actions > 0
        else 0.0
    )

    if total_actions >= 20 and turnover_ratio >= 0.40:
        return "High Turnover"

    if additions >= reductions * 2:
        return "Accumulator"

    if reductions >= additions * 2:
        return "Distributor"

    if concentration_ratio >= 0.70:
        return "Concentrated Conviction"

    if active_position_count >= 15:
        return "Diversified Active"

    return "Balanced Active"


def classify_risk_profile(
    concentration_ratio: float,
    average_entry_price: float,
    position_count: int,
    open_pnl_ratio: float,
) -> str:
    """Classify observed portfolio risk."""

    risk_points = 0

    if concentration_ratio >= 0.75:
        risk_points += 3
    elif concentration_ratio >= 0.50:
        risk_points += 2
    elif concentration_ratio >= 0.35:
        risk_points += 1

    if average_entry_price <= 0.15:
        risk_points += 2
    elif average_entry_price <= 0.30:
        risk_points += 1

    if position_count <= 3:
        risk_points += 2
    elif position_count <= 7:
        risk_points += 1

    if open_pnl_ratio <= -0.10:
        risk_points += 2
    elif open_pnl_ratio <= -0.03:
        risk_points += 1

    if risk_points >= 6:
        return "Very High"

    if risk_points >= 4:
        return "High"

    if risk_points >= 2:
        return "Moderate"

    return "Conservative"


def calculate_leader_score(
    positions: list[dict[str, Any]],
    wallet_score: float,
    total_current_value: float,
    activity_counts: dict[str, int],
) -> float:
    """Estimate observed market-leadership strength."""

    meaningful_positions = [
        position
        for position in positions
        if safe_float(
            position.get("current_value")
        ) >= MINIMUM_MEANINGFUL_POSITION_VALUE
    ]

    new_and_increased = (
        activity_counts.get("NEW", 0)
        + activity_counts.get("INCREASED", 0)
    )

    if total_current_value > 0:
        capital_points = clamp(
            math.log10(
                max(total_current_value, 1)
            )
            / math.log10(1_000_000),
            0,
            1,
        ) * 40
    else:
        capital_points = 0.0

    wallet_quality_points = clamp(
        wallet_score / 100,
        0,
        1,
    ) * 30

    breadth_points = clamp(
        len(meaningful_positions) / 15,
        0,
        1,
    ) * 15

    activity_points = clamp(
        new_and_increased / 10,
        0,
        1,
    ) * 15

    return round(
        capital_points
        + wallet_quality_points
        + breadth_points
        + activity_points,
        1,
    )


def calculate_activity_score(
    activity_counts: dict[str, int],
    scan_count: int,
) -> float:
    """Calculate an activity score out of 100."""

    total_activity = sum(
        activity_counts.values()
    )

    depth_points = clamp(
        scan_count / 10,
        0,
        1,
    ) * 30

    action_points = clamp(
        total_activity / 30,
        0,
        1,
    ) * 50

    directional_actions = (
        activity_counts.get("NEW", 0)
        + activity_counts.get("INCREASED", 0)
        + activity_counts.get("REDUCED", 0)
        + activity_counts.get("CLOSED", 0)
    )

    directional_points = clamp(
        directional_actions / 15,
        0,
        1,
    ) * 20

    return round(
        depth_points
        + action_points
        + directional_points,
        1,
    )


def calculate_specialization_score(
    category_exposure: dict[str, float],
) -> float:
    """Calculate portfolio specialization out of 100."""

    largest_exposure = max(
        category_exposure.values(),
        default=0.0,
    )

    return round(
        clamp(
            largest_exposure,
            0,
            1,
        ) * 100,
        1,
    )


def dna_grade(score: float) -> str:
    """Convert DNA score into a provisional grade."""

    if score >= 85:
        return "DNA S+"

    if score >= 75:
        return "DNA S"

    if score >= 65:
        return "DNA A+"

    if score >= 55:
        return "DNA A"

    if score >= 40:
        return "DNA WATCH"

    return "DNA INSUFFICIENT"


def build_wallet_profile(
    wallet: str,
    scan_metadata: dict[str, Any],
    positions: list[dict[str, Any]],
    rating: dict[str, Any],
    activity_counts: dict[str, int],
) -> dict[str, Any]:
    """Build the complete Wallet DNA profile."""

    meaningful_positions = [
        position
        for position in positions
        if safe_float(
            position.get("current_value")
        ) >= MINIMUM_MEANINGFUL_POSITION_VALUE
    ]

    position_values = [
        safe_float(
            position.get("current_value")
        )
        for position in meaningful_positions
    ]

    total_current_value = sum(
        position_values
    )

    total_open_pnl = sum(
        safe_float(
            position.get("cash_pnl")
        )
        for position in meaningful_positions
    )

    profitable_positions = sum(
        1
        for position in meaningful_positions
        if safe_float(
            position.get("cash_pnl")
        ) > 0
    )

    profitable_position_rate = (
        profitable_positions
        / len(meaningful_positions)
        if meaningful_positions
        else 0.0
    )

    open_pnl_ratio = (
        total_open_pnl / total_current_value
        if total_current_value > 0
        else 0.0
    )

    average_position_value = (
        statistics.mean(position_values)
        if position_values
        else 0.0
    )

    median_position_value = (
        statistics.median(position_values)
        if position_values
        else 0.0
    )

    largest_position_value = max(
        position_values,
        default=0.0,
    )

    concentration_ratio = (
        largest_position_value
        / total_current_value
        if total_current_value > 0
        else 1.0
    )

    weighted_entries = [
        (
            safe_float(
                position.get("average_price")
            ),
            safe_float(
                position.get("current_value")
            ),
        )
        for position in meaningful_positions
    ]

    weighted_current_prices = [
        (
            safe_float(
                position.get("current_price")
            ),
            safe_float(
                position.get("current_value")
            ),
        )
        for position in meaningful_positions
    ]

    average_entry_price = weighted_average(
        weighted_entries
    )

    average_current_price = weighted_average(
        weighted_current_prices
    )

    average_observed_move = (
        average_current_price
        - average_entry_price
    )

    category_exposure = calculate_category_exposure(
        meaningful_positions
    )

    favorite_category = max(
        category_exposure,
        key=category_exposure.get,
        default="Other",
    )

    wallet_score = safe_float(
        rating.get("wallet_score")
    )

    wallet_grade = str(
        rating.get("wallet_grade")
        or "UNRATED"
    )

    scan_count = safe_int(
        scan_metadata.get("scan_count")
    )

    activity_style = classify_activity_style(
        activity_counts=activity_counts,
        concentration_ratio=concentration_ratio,
        active_position_count=len(positions),
    )

    risk_profile = classify_risk_profile(
        concentration_ratio=concentration_ratio,
        average_entry_price=average_entry_price,
        position_count=len(meaningful_positions),
        open_pnl_ratio=open_pnl_ratio,
    )

    leader_score = calculate_leader_score(
        positions=positions,
        wallet_score=wallet_score,
        total_current_value=total_current_value,
        activity_counts=activity_counts,
    )

    activity_score = calculate_activity_score(
        activity_counts=activity_counts,
        scan_count=scan_count,
    )

    specialization_score = (
        calculate_specialization_score(
            category_exposure
        )
    )

    dna_score = round(
        wallet_score * 0.40
        + leader_score * 0.25
        + activity_score * 0.20
        + specialization_score * 0.15,
        1,
    )

    return {
        "wallet": wallet,
        "wallet_score": wallet_score,
        "wallet_grade": wallet_grade,
        "scan_count": scan_count,
        "active_position_count": len(
            positions
        ),
        "meaningful_position_count": len(
            meaningful_positions
        ),
        "total_current_value": (
            total_current_value
        ),
        "total_open_pnl": total_open_pnl,
        "open_pnl_ratio": open_pnl_ratio,
        "profitable_position_rate": (
            profitable_position_rate
        ),
        "average_position_value": (
            average_position_value
        ),
        "median_position_value": (
            median_position_value
        ),
        "largest_position_value": (
            largest_position_value
        ),
        "concentration_ratio": (
            concentration_ratio
        ),
        "average_entry_price": (
            average_entry_price
        ),
        "average_current_price": (
            average_current_price
        ),
        "average_observed_move": (
            average_observed_move
        ),
        "sports_exposure": (
            category_exposure["Sports"]
        ),
        "politics_exposure": (
            category_exposure["Politics"]
        ),
        "crypto_exposure": (
            category_exposure["Crypto"]
        ),
        "macro_exposure": (
            category_exposure["Macro"]
        ),
        "entertainment_exposure": (
            category_exposure[
                "Entertainment"
            ]
        ),
        "other_exposure": (
            category_exposure["Other"]
        ),
        "favorite_category": favorite_category,
        "activity_style": activity_style,
        "risk_profile": risk_profile,
        "leader_score": leader_score,
        "activity_score": activity_score,
        "specialization_score": (
            specialization_score
        ),
        "dna_score": dna_score,
        "dna_grade": dna_grade(dna_score),
        "first_observed_at": str(
            scan_metadata.get(
                "first_observed_at"
            )
            or ""
        ),
        "latest_observed_at": str(
            scan_metadata.get(
                "latest_observed_at"
            )
            or ""
        ),
        "calculated_at": utc_now(),
    }


def save_wallet_profile(
    profile: dict[str, Any],
) -> None:
    """Upsert the newest Wallet DNA profile."""

    connection = connect_database()

    try:
        connection.execute(
            """
            INSERT INTO wallet_profiles (
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
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            ON CONFLICT(wallet) DO UPDATE SET
                wallet_score = excluded.wallet_score,
                wallet_grade = excluded.wallet_grade,
                scan_count = excluded.scan_count,
                active_position_count = excluded.active_position_count,
                meaningful_position_count = excluded.meaningful_position_count,
                total_current_value = excluded.total_current_value,
                total_open_pnl = excluded.total_open_pnl,
                open_pnl_ratio = excluded.open_pnl_ratio,
                profitable_position_rate = excluded.profitable_position_rate,
                average_position_value = excluded.average_position_value,
                median_position_value = excluded.median_position_value,
                largest_position_value = excluded.largest_position_value,
                concentration_ratio = excluded.concentration_ratio,
                average_entry_price = excluded.average_entry_price,
                average_current_price = excluded.average_current_price,
                average_observed_move = excluded.average_observed_move,
                sports_exposure = excluded.sports_exposure,
                politics_exposure = excluded.politics_exposure,
                crypto_exposure = excluded.crypto_exposure,
                macro_exposure = excluded.macro_exposure,
                entertainment_exposure = excluded.entertainment_exposure,
                other_exposure = excluded.other_exposure,
                favorite_category = excluded.favorite_category,
                activity_style = excluded.activity_style,
                risk_profile = excluded.risk_profile,
                leader_score = excluded.leader_score,
                activity_score = excluded.activity_score,
                specialization_score = excluded.specialization_score,
                dna_score = excluded.dna_score,
                dna_grade = excluded.dna_grade,
                first_observed_at = excluded.first_observed_at,
                latest_observed_at = excluded.latest_observed_at,
                calculated_at = excluded.calculated_at
            """,
            tuple(profile.values()),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_wallet_profile_history(
    profile: dict[str, Any],
) -> None:
    """Save a historical Wallet DNA snapshot."""

    connection = connect_database()

    try:
        connection.execute(
            """
            INSERT INTO wallet_profile_history (
                wallet,
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
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                profile["wallet"],
                profile["wallet_score"],
                profile["wallet_grade"],
                profile["total_current_value"],
                profile["total_open_pnl"],
                profile["open_pnl_ratio"],
                profile["active_position_count"],
                profile[
                    "meaningful_position_count"
                ],
                profile[
                    "profitable_position_rate"
                ],
                profile["concentration_ratio"],
                profile["favorite_category"],
                profile["activity_style"],
                profile["risk_profile"],
                profile["leader_score"],
                profile["activity_score"],
                profile[
                    "specialization_score"
                ],
                profile["dna_score"],
                profile["dna_grade"],
                profile["calculated_at"],
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def shorten_wallet(wallet: str) -> str:
    """Shorten a wallet address for display."""

    if len(wallet) <= 20:
        return wallet

    return (
        f"{wallet[:10]}..."
        f"{wallet[-8:]}"
    )


def display_profile(
    number: int,
    profile: dict[str, Any],
) -> None:
    """Display one Wallet DNA profile."""

    print()
    print("-" * 100)
    print(
        f"{number}. "
        f"{shorten_wallet(profile['wallet'])}"
    )
    print("-" * 100)

    print(
        f"DNA score:               "
        f"{profile['dna_score']:.1f}/100"
    )

    print(
        f"DNA grade:               "
        f"{profile['dna_grade']}"
    )

    print(
        f"Wallet rating:           "
        f"{profile['wallet_score']:.1f} "
        f"({profile['wallet_grade']})"
    )

    print(
        f"Leader score:            "
        f"{profile['leader_score']:.1f}"
    )

    print(
        f"Activity score:          "
        f"{profile['activity_score']:.1f}"
    )

    print(
        f"Specialization score:    "
        f"{profile['specialization_score']:.1f}"
    )

    print(
        f"Favorite category:       "
        f"{profile['favorite_category']}"
    )

    print(
        f"Activity style:          "
        f"{profile['activity_style']}"
    )

    print(
        f"Risk profile:            "
        f"{profile['risk_profile']}"
    )

    print(
        f"Stored scans:            "
        f"{profile['scan_count']}"
    )

    print(
        f"Active positions:        "
        f"{profile['active_position_count']}"
    )

    print(
        f"Positions worth $500+:   "
        f"{profile['meaningful_position_count']}"
    )

    print(
        f"Total current value:     "
        f"${profile['total_current_value']:,.2f}"
    )

    print(
        f"Total open PnL:          "
        f"${profile['total_open_pnl']:,.2f}"
    )

    print(
        f"Open PnL ratio:          "
        f"{profile['open_pnl_ratio']:.1%}"
    )

    print(
        f"Profitable positions:    "
        f"{profile['profitable_position_rate']:.1%}"
    )

    print(
        f"Largest position share:  "
        f"{profile['concentration_ratio']:.1%}"
    )


def main() -> None:
    """Build and store Wallet Intelligence profiles."""

    print()
    print("=" * 100)
    print("POLYMARKET WALLET INTELLIGENCE ENGINE v1")
    print("=" * 100)

    create_intelligence_tables()

    ratings = load_latest_wallet_ratings()
    scan_metadata = load_wallet_scan_metadata()
    latest_positions = load_latest_positions()

    all_wallets = sorted(
        set(scan_metadata)
        | set(latest_positions)
        | set(ratings)
    )

    print(f"Wallets discovered: {len(all_wallets)}")

    profiles: list[dict[str, Any]] = []
    activity_rows_created = 0

    for wallet in all_wallets:
        activities = build_wallet_activity(
            wallet
        )

        activity_rows_created += (
            save_wallet_activity(activities)
        )

        activity_counts = load_activity_counts(
            wallet
        )

        profile = build_wallet_profile(
            wallet=wallet,
            scan_metadata=scan_metadata.get(
                wallet,
                {},
            ),
            positions=latest_positions.get(
                wallet,
                [],
            ),
            rating=ratings.get(
                wallet,
                {},
            ),
            activity_counts=activity_counts,
        )

        save_wallet_profile(profile)
        save_wallet_profile_history(profile)

        profiles.append(profile)

    profiles.sort(
        key=lambda profile: (
            profile["dna_score"],
            profile["wallet_score"],
            profile["total_current_value"],
        ),
        reverse=True,
    )

    print(
        f"Wallet profiles updated: "
        f"{len(profiles)}"
    )

    print(
        f"Activity records created: "
        f"{activity_rows_created}"
    )

    for number, profile in enumerate(
        profiles,
        start=1,
    ):
        display_profile(
            number,
            profile,
        )

    print()
    print("=" * 100)
    print("WALLET INTELLIGENCE COMPLETE")
    print("=" * 100)

    print(
        "Current profiles were written to: "
        "wallet_profiles"
    )

    print(
        "Historical snapshots were written to: "
        "wallet_profile_history"
    )

    print(
        "Detected position changes were written to: "
        "wallet_activity"
    )

    print()
    print(
        "Wallet DNA scores remain provisional until "
        "resolved-market performance is available."
    )

    print("=" * 100)


if __name__ == "__main__":
    main()