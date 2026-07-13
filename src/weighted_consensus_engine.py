from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("database/polymarket.db")

MINIMUM_WALLETS = 2
MINIMUM_POSITION_VALUE = 500.0


def connect_database() -> sqlite3.Connection:
    """Connect to the local Polymarket SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH.resolve()}. "
            "Run the watchlist scanner first."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


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


def normalize_wallet(wallet: Any) -> str:
    """Normalize a wallet address for matching."""

    return str(wallet or "").strip().lower()


def wallet_quality_multiplier(score: float) -> float:
    """
    Convert a provisional wallet score into a research multiplier.

    Score 100 -> 1.50
    Score 80  -> 1.30
    Score 60  -> 1.10
    Score 40  -> 0.90
    Score 20  -> 0.70
    Score 0   -> 0.50
    """

    bounded_score = min(max(score, 0.0), 100.0)
    return 0.50 + (bounded_score / 100.0)


def fetch_latest_wallet_ratings() -> dict[str, dict[str, Any]]:
    """
    Retrieve only the latest stored rating for each wallet.
    """

    connection = connect_database()

    try:
        query = """
            WITH latest_ratings AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_rating_id
                FROM wallet_rating_history
                GROUP BY wallet
            )
            SELECT
                rating.wallet,
                rating.wallet_score,
                rating.wallet_grade,
                rating.meaningful_position_count,
                rating.profitable_position_rate,
                rating.open_pnl_ratio,
                rating.concentration_ratio,
                rating.rated_at
            FROM wallet_rating_history AS rating
            INNER JOIN latest_ratings AS latest
                ON rating.id = latest.latest_rating_id
        """

        rows = connection.execute(query).fetchall()

        ratings: dict[str, dict[str, Any]] = {}

        for row in rows:
            wallet = normalize_wallet(row["wallet"])

            if not wallet:
                continue

            ratings[wallet] = dict(row)

        return ratings

    finally:
        connection.close()


def fetch_latest_qualifying_positions() -> list[dict[str, Any]]:
    """
    Retrieve qualifying positions from the latest scan of each wallet.
    """

    connection = connect_database()

    try:
        query = """
            WITH latest_scans AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_scan_id
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT
                p.wallet,
                p.market_id,
                p.title,
                p.outcome,
                p.shares,
                p.average_price,
                p.current_price,
                p.current_value,
                p.cash_pnl,
                p.percent_pnl
            FROM positions AS p
            INNER JOIN latest_scans AS latest
                ON p.wallet = latest.wallet
               AND p.scan_id = latest.latest_scan_id
            WHERE
                p.market_id IS NOT NULL
                AND TRIM(p.market_id) != ''
                AND p.outcome IS NOT NULL
                AND TRIM(p.outcome) != ''
                AND COALESCE(p.current_value, 0) >= ?
        """

        rows = connection.execute(
            query,
            (MINIMUM_POSITION_VALUE,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def group_weighted_consensus(
    positions: list[dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Group positions by exact market ID and outcome.

    Wallet quality affects weighted support, but raw wallet count
    is still shown separately.
    """

    grouped: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for position in positions:
        market_id = str(position.get("market_id") or "").strip()
        outcome = str(position.get("outcome") or "").strip()

        if not market_id or not outcome:
            continue

        grouped[
            (
                market_id,
                outcome.lower(),
            )
        ].append(position)

    results: list[dict[str, Any]] = []

    for (market_id, _), group in grouped.items():
        wallet_positions: dict[str, dict[str, Any]] = {}

        # Keep only one position per wallet for each market/outcome group.
        for position in group:
            wallet = normalize_wallet(position.get("wallet"))

            if not wallet:
                continue

            wallet_positions[wallet] = position

        if len(wallet_positions) < MINIMUM_WALLETS:
            continue

        wallet_details: list[dict[str, Any]] = []

        combined_shares = 0.0
        combined_value = 0.0
        combined_pnl = 0.0

        weighted_support = 0.0
        weighted_capital = 0.0

        weighted_entry_total = 0.0
        weighted_current_total = 0.0

        total_rating_score = 0.0
        rated_wallets = 0

        for wallet, position in wallet_positions.items():
            rating = ratings.get(wallet)

            if rating:
                wallet_score = safe_float(rating.get("wallet_score"))
                wallet_grade = str(
                    rating.get("wallet_grade") or "UNRATED"
                )
                rated_wallets += 1
                total_rating_score += wallet_score
            else:
                # Neutral fallback when a rating is unavailable.
                wallet_score = 50.0
                wallet_grade = "UNRATED"

            multiplier = wallet_quality_multiplier(wallet_score)

            shares = safe_float(position.get("shares"))
            current_value = safe_float(position.get("current_value"))
            cash_pnl = safe_float(position.get("cash_pnl"))
            average_price = safe_float(position.get("average_price"))
            current_price = safe_float(position.get("current_price"))

            combined_shares += shares
            combined_value += current_value
            combined_pnl += cash_pnl

            weighted_support += multiplier
            weighted_capital += current_value * multiplier

            weighted_entry_total += average_price * shares
            weighted_current_total += current_price * shares

            wallet_details.append(
                {
                    "wallet": wallet,
                    "wallet_score": wallet_score,
                    "wallet_grade": wallet_grade,
                    "multiplier": multiplier,
                    "current_value": current_value,
                    "cash_pnl": cash_pnl,
                    "shares": shares,
                }
            )

        average_entry_price = (
            weighted_entry_total / combined_shares
            if combined_shares > 0
            else 0.0
        )

        average_current_price = (
            weighted_current_total / combined_shares
            if combined_shares > 0
            else 0.0
        )

        price_move = average_current_price - average_entry_price

        average_wallet_score = (
            total_rating_score / rated_wallets
            if rated_wallets > 0
            else 50.0
        )

        results.append(
            {
                "market_id": market_id,
                "title": group[0].get("title") or "Unknown market",
                "outcome": group[0].get("outcome") or "Unknown",
                "wallet_count": len(wallet_positions),
                "rated_wallet_count": rated_wallets,
                "average_wallet_score": average_wallet_score,
                "weighted_support": weighted_support,
                "combined_shares": combined_shares,
                "combined_value": combined_value,
                "weighted_capital": weighted_capital,
                "combined_pnl": combined_pnl,
                "average_entry_price": average_entry_price,
                "average_current_price": average_current_price,
                "price_move": price_move,
                "wallet_details": wallet_details,
            }
        )

    return results


def calculate_weighted_score(
    consensus: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate a weighted research score out of 100.
    """

    wallet_count = safe_int(consensus["wallet_count"])
    weighted_support = safe_float(consensus["weighted_support"])
    average_wallet_score = safe_float(
        consensus["average_wallet_score"]
    )
    weighted_capital = safe_float(consensus["weighted_capital"])
    combined_value = safe_float(consensus["combined_value"])
    combined_pnl = safe_float(consensus["combined_pnl"])
    price_move = safe_float(consensus["price_move"])
    current_price = safe_float(
        consensus["average_current_price"]
    )

    # 1. Weighted wallet support: maximum 30 points.
    support_score = min(weighted_support / 6.5, 1.0) * 30

    # 2. Average wallet quality: maximum 20 points.
    quality_score = min(
        max(average_wallet_score / 100.0, 0.0),
        1.0,
    ) * 20

    # 3. Capital commitment: maximum 20 points.
    capital_score = min(
        math.log10(max(weighted_capital, 1))
        / math.log10(500_000),
        1.0,
    ) * 20

    # 4. Open PnL confirmation: maximum 10 points.
    pnl_ratio = (
        combined_pnl / combined_value
        if combined_value > 0
        else 0.0
    )

    pnl_score = min(
        max((pnl_ratio + 0.05) / 0.15, 0.0),
        1.0,
    ) * 10

    # 5. Entry timing: maximum 10 points.
    absolute_move = abs(price_move)

    if absolute_move <= 0.02:
        timing_score = 10.0
        chase_warning = False
    elif absolute_move <= 0.05:
        timing_score = 8.0
        chase_warning = False
    elif absolute_move <= 0.10:
        timing_score = 5.0
        chase_warning = True
    else:
        timing_score = 1.0
        chase_warning = True

    # 6. Remaining price room: maximum 10 points.
    if 0.20 <= current_price <= 0.70:
        price_room_score = 10.0
    elif 0.10 <= current_price < 0.20:
        price_room_score = 7.0
    elif 0.70 < current_price <= 0.85:
        price_room_score = 6.0
    elif current_price > 0.95:
        price_room_score = 1.0
    else:
        price_room_score = 4.0

    total_score = round(
        support_score
        + quality_score
        + capital_score
        + pnl_score
        + timing_score
        + price_room_score,
        1,
    )

    # Require raw agreement regardless of weighted score.
    if wallet_count < MINIMUM_WALLETS:
        grade = "INSUFFICIENT CONSENSUS"
    elif total_score >= 85:
        grade = "ELITE WEIGHTED RESEARCH"
    elif total_score >= 75:
        grade = "STRONG WEIGHTED RESEARCH"
    elif total_score >= 65:
        grade = "MODERATE WEIGHTED RESEARCH"
    elif total_score >= 50:
        grade = "WEIGHTED WATCH"
    else:
        grade = "LOW PRIORITY"

    result = dict(consensus)

    result.update(
        {
            "weighted_score": total_score,
            "weighted_grade": grade,
            "support_score": round(support_score, 1),
            "quality_score": round(quality_score, 1),
            "capital_score": round(capital_score, 1),
            "pnl_score": round(pnl_score, 1),
            "timing_score": round(timing_score, 1),
            "price_room_score": round(price_room_score, 1),
            "chase_warning": chase_warning,
        }
    )

    return result


def shorten_wallet(wallet: str) -> str:
    """Shorten wallet address for display."""

    if len(wallet) <= 16:
        return wallet

    return f"{wallet[:10]}...{wallet[-8:]}"


def display_result(
    number: int,
    result: dict[str, Any],
) -> None:
    """Display one weighted consensus result."""

    print()
    print("-" * 100)
    print(f"{number}. {result['title']}")
    print("-" * 100)

    print(f"Outcome:                    {result['outcome']}")
    print(
        f"Weighted research score:    "
        f"{result['weighted_score']:.1f}/100"
    )
    print(
        f"Weighted research grade:    "
        f"{result['weighted_grade']}"
    )
    print(
        f"Raw agreeing wallets:       "
        f"{result['wallet_count']}"
    )
    print(
        f"Rated wallets:              "
        f"{result['rated_wallet_count']}"
    )
    print(
        f"Average wallet score:       "
        f"{result['average_wallet_score']:.1f}/100"
    )
    print(
        f"Weighted wallet support:    "
        f"{result['weighted_support']:.2f}"
    )
    print(
        f"Combined current value:     "
        f"${result['combined_value']:,.2f}"
    )
    print(
        f"Quality-weighted capital:   "
        f"${result['weighted_capital']:,.2f}"
    )
    print(
        f"Combined open PnL:          "
        f"${result['combined_pnl']:,.2f}"
    )
    print(
        f"Average entry price:        "
        f"{result['average_entry_price']:.3f}"
    )
    print(
        f"Average current price:      "
        f"{result['average_current_price']:.3f}"
    )
    print(
        f"Observed price move:        "
        f"{result['price_move']:+.3f}"
    )

    print()
    print("Score breakdown:")
    print(
        f"  Weighted support:         "
        f"{result['support_score']}/30"
    )
    print(
        f"  Wallet quality:           "
        f"{result['quality_score']}/20"
    )
    print(
        f"  Weighted capital:         "
        f"{result['capital_score']}/20"
    )
    print(
        f"  Open PnL confirmation:    "
        f"{result['pnl_score']}/10"
    )
    print(
        f"  Entry timing:             "
        f"{result['timing_score']}/10"
    )
    print(
        f"  Remaining price room:     "
        f"{result['price_room_score']}/10"
    )

    if result["chase_warning"]:
        print()
        print(
            "WARNING: Price has moved materially from the "
            "observed average entry."
        )
        print("Do not blindly chase the existing wallet positions.")

    print()
    print("Supporting wallets:")

    wallet_details = sorted(
        result["wallet_details"],
        key=lambda item: (
            item["wallet_score"],
            item["current_value"],
        ),
        reverse=True,
    )

    for wallet in wallet_details:
        print(
            f"  - {shorten_wallet(wallet['wallet'])}"
            f" | score {wallet['wallet_score']:.1f}"
            f" | {wallet['wallet_grade']}"
            f" | weight {wallet['multiplier']:.2f}"
            f" | value ${wallet['current_value']:,.2f}"
        )


def main() -> None:
    """Run the weighted research consensus engine."""

    print()
    print("=" * 100)
    print("POLYMARKET WEIGHTED RESEARCH CONSENSUS ENGINE v1")
    print("=" * 100)

    ratings = fetch_latest_wallet_ratings()
    positions = fetch_latest_qualifying_positions()

    consensus_groups = group_weighted_consensus(
        positions=positions,
        ratings=ratings,
    )

    results = [
        calculate_weighted_score(consensus)
        for consensus in consensus_groups
    ]

    results.sort(
        key=lambda result: (
            result["weighted_score"],
            result["weighted_support"],
            result["combined_value"],
        ),
        reverse=True,
    )

    print()
    print("ENGINE DIAGNOSTICS")
    print("-" * 100)
    print(f"Latest wallet ratings loaded:   {len(ratings)}")
    print(f"Latest qualifying positions:    {len(positions)}")
    print(f"Weighted consensus groups:      {len(results)}")
    print(f"Minimum agreeing wallets:       {MINIMUM_WALLETS}")
    print(
        f"Minimum position value:         "
        f"${MINIMUM_POSITION_VALUE:,.2f}"
    )

    if not results:
        print()
        print("No weighted consensus signals currently qualify.")
        return

    for number, result in enumerate(results, start=1):
        display_result(number, result)

    print()
    print("=" * 100)
    print("IMPORTANT")
    print("=" * 100)
    print(
        "Wallet ratings are provisional and currently rely on "
        "observable open-position evidence."
    )
    print(
        "Weighted consensus ranks research priority only; it does "
        "not prove positive expected value."
    )
    print(
        "Resolved-market performance will later replace provisional "
        "ratings with stronger evidence."
    )
    print("=" * 100)


if __name__ == "__main__":
    main()