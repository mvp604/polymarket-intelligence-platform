from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from database import save_consensus_history


DATABASE_PATH = Path("database/polymarket.db")

MINIMUM_WALLETS = 2
MINIMUM_POSITION_VALUE = 500.0


def connect_database() -> sqlite3.Connection:
    """Open the local Polymarket SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}. "
            "Run the wallet scanner first."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def safe_float(value: Any) -> float:
    """Convert a value into a float without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def get_latest_positions() -> list[dict[str, Any]]:
    """
    Retrieve qualifying positions from only the newest stored scan
    for every tracked wallet.
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
                p.market_id,
                p.title,
                p.outcome,
                p.wallet,
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


def group_consensus_positions(
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Group positions by exact market ID and normalized outcome.

    Matching by market ID and outcome is safer than matching
    by title alone.
    """

    grouped: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for position in positions:
        market_id = str(
            position.get("market_id") or ""
        ).strip()

        outcome = str(
            position.get("outcome") or ""
        ).strip()

        if not market_id or not outcome:
            continue

        normalized_outcome = outcome.lower()

        grouped[
            (
                market_id,
                normalized_outcome,
            )
        ].append(position)

    consensus_results: list[dict[str, Any]] = []

    for (
        market_id,
        _normalized_outcome,
    ), group in grouped.items():

        unique_wallets = {
            str(
                position.get("wallet") or ""
            ).strip().lower()
            for position in group
            if position.get("wallet")
        }

        if len(unique_wallets) < MINIMUM_WALLETS:
            continue

        total_shares = sum(
            safe_float(position.get("shares"))
            for position in group
        )

        combined_value = sum(
            safe_float(position.get("current_value"))
            for position in group
        )

        combined_pnl = sum(
            safe_float(position.get("cash_pnl"))
            for position in group
        )

        weighted_entry_total = sum(
            safe_float(position.get("average_price"))
            * safe_float(position.get("shares"))
            for position in group
        )

        weighted_current_total = sum(
            safe_float(position.get("current_price"))
            * safe_float(position.get("shares"))
            for position in group
        )

        average_entry_price = (
            weighted_entry_total / total_shares
            if total_shares > 0
            else 0.0
        )

        average_current_price = (
            weighted_current_total / total_shares
            if total_shares > 0
            else 0.0
        )

        price_move = (
            average_current_price
            - average_entry_price
        )

        consensus_results.append(
            {
                "market_id": market_id,
                "title": (
                    group[0].get("title")
                    or "Unknown market"
                ),
                "outcome": (
                    group[0].get("outcome")
                    or "Unknown"
                ),
                "wallets": sorted(unique_wallets),
                "wallet_count": len(unique_wallets),
                "combined_shares": total_shares,
                "combined_value": combined_value,
                "combined_pnl": combined_pnl,
                "average_entry_price": average_entry_price,
                "average_current_price": average_current_price,
                "price_move": price_move,
            }
        )

    return consensus_results


def calculate_conviction_score(
    consensus: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate an explainable research-priority score out of 100.

    This is a ranking model. It is not a guarantee that a
    market position will win.
    """

    wallet_count = int(
        consensus["wallet_count"]
    )

    combined_value = safe_float(
        consensus["combined_value"]
    )

    combined_pnl = safe_float(
        consensus["combined_pnl"]
    )

    price_move = safe_float(
        consensus["price_move"]
    )

    current_price = safe_float(
        consensus["average_current_price"]
    )

    # 1. Wallet agreement: maximum 40 points.
    wallet_score = min(
        wallet_count / 5,
        1.0,
    ) * 40

    # 2. Combined capital: maximum 25 points.
    # Log scaling prevents one huge position from dominating.
    value_score = min(
        math.log10(
            max(combined_value, 1)
        )
        / math.log10(250_000),
        1.0,
    ) * 25

    # 3. Open PnL confirmation: maximum 15 points.
    if combined_value > 0:
        pnl_ratio = (
            combined_pnl
            / combined_value
        )
    else:
        pnl_ratio = 0.0

    pnl_score = min(
        max(
            (pnl_ratio + 0.05)
            / 0.15,
            0.0,
        ),
        1.0,
    ) * 15

    # 4. Entry timing: maximum 10 points.
    # Very large moves may indicate the edge is already gone.
    absolute_move = abs(price_move)

    if absolute_move <= 0.02:
        timing_score = 10
        chase_warning = False

    elif absolute_move <= 0.05:
        timing_score = 8
        chase_warning = False

    elif absolute_move <= 0.10:
        timing_score = 5
        chase_warning = True

    else:
        timing_score = 1
        chase_warning = True

    # 5. Remaining price room: maximum 10 points.
    if 0.20 <= current_price <= 0.70:
        price_room_score = 10

    elif 0.10 <= current_price < 0.20:
        price_room_score = 7

    elif 0.70 < current_price <= 0.85:
        price_room_score = 6

    elif current_price > 0.95:
        price_room_score = 1

    else:
        price_room_score = 4

    total_score = round(
        wallet_score
        + value_score
        + pnl_score
        + timing_score
        + price_room_score,
        1,
    )

    if total_score >= 85:
        grade = "ELITE RESEARCH"

    elif total_score >= 75:
        grade = "STRONG RESEARCH"

    elif total_score >= 65:
        grade = "MODERATE RESEARCH"

    elif total_score >= 50:
        grade = "WATCH"

    else:
        grade = "LOW PRIORITY"

    result = dict(consensus)

    result.update(
        {
            "conviction_score": total_score,
            "grade": grade,
            "wallet_score": round(
                wallet_score,
                1,
            ),
            "value_score": round(
                value_score,
                1,
            ),
            "pnl_score": round(
                pnl_score,
                1,
            ),
            "timing_score": round(
                timing_score,
                1,
            ),
            "price_room_score": round(
                price_room_score,
                1,
            ),
            "chase_warning": chase_warning,
        }
    )

    return result


def shorten_wallet(wallet: str) -> str:
    """Display a public wallet address in shortened form."""

    if len(wallet) <= 14:
        return wallet

    return (
        f"{wallet[:8]}"
        f"..."
        f"{wallet[-6:]}"
    )


def display_results(
    results: list[dict[str, Any]],
) -> None:
    """Display scored consensus results in the terminal."""

    print()
    print("=" * 82)
    print(
        "POLYMARKET SMART-MONEY "
        "CONVICTION ENGINE v1"
    )
    print("=" * 82)

    if not results:
        print()
        print(
            "No positions met the minimum "
            "consensus requirements."
        )
        print(
            f"Minimum agreeing wallets: "
            f"{MINIMUM_WALLETS}"
        )
        return

    print()
    print(
        f"Ranked consensus positions found: "
        f"{len(results)}"
    )

    for number, result in enumerate(
        results,
        start=1,
    ):
        print()
        print("-" * 82)
        print(
            f"{number}. "
            f"{result['title']}"
        )
        print(
            f"Outcome:                 "
            f"{result['outcome']}"
        )
        print(
            f"Research score:          "
            f"{result['conviction_score']}/100"
        )
        print(
            f"Research grade:          "
            f"{result['grade']}"
        )
        print(
            f"Qualified wallets:       "
            f"{result['wallet_count']}"
        )
        print(
            f"Combined shares:         "
            f"{result['combined_shares']:,.2f}"
        )
        print(
            f"Combined current value:  "
            f"${result['combined_value']:,.2f}"
        )
        print(
            f"Combined open PnL:       "
            f"${result['combined_pnl']:,.2f}"
        )
        print(
            f"Average entry price:     "
            f"{result['average_entry_price']:.3f}"
        )
        print(
            f"Average current price:   "
            f"{result['average_current_price']:.3f}"
        )
        print(
            f"Observed price move:     "
            f"{result['price_move']:+.3f}"
        )

        print()
        print("Score breakdown:")

        print(
            f"  Wallet agreement:      "
            f"{result['wallet_score']}/40"
        )
        print(
            f"  Combined capital:      "
            f"{result['value_score']}/25"
        )
        print(
            f"  Open PnL confirmation: "
            f"{result['pnl_score']}/15"
        )
        print(
            f"  Entry timing:          "
            f"{result['timing_score']}/10"
        )
        print(
            f"  Remaining price room:  "
            f"{result['price_room_score']}/10"
        )

        if result["chase_warning"]:
            print()
            print(
                "WARNING: The price has moved "
                "materially since the"
            )
            print(
                "observed average entry. "
                "Do not blindly chase."
            )

        print()
        print("Wallets:")

        for wallet in result["wallets"]:
            print(
                f"  - "
                f"{shorten_wallet(wallet)}"
            )

    print()
    print("=" * 82)
    print("IMPORTANT:")
    print(
        "This score ranks research priority only."
    )
    print(
        "It does not prove positive expected value "
        "or guarantee a win."
    )
    print("=" * 82)


def main() -> None:
    """Run conviction scoring and save historical snapshots."""

    positions = get_latest_positions()

    consensus_positions = (
        group_consensus_positions(
            positions
        )
    )

    scored_results = [
        calculate_conviction_score(position)
        for position in consensus_positions
    ]

    scored_results.sort(
        key=lambda result: (
            result["conviction_score"],
            result["wallet_count"],
            result["combined_value"],
        ),
        reverse=True,
    )

    print()
    print("=" * 82)
    print("ENGINE DIAGNOSTICS")
    print("=" * 82)
    print(
        f"Latest qualifying position rows: "
        f"{len(positions)}"
    )
    print(
        f"Consensus groups meeting threshold: "
        f"{len(consensus_positions)}"
    )
    print(
        f"Scored results produced: "
        f"{len(scored_results)}"
    )
    print(
        f"Minimum agreeing wallets: "
        f"{MINIMUM_WALLETS}"
    )
    print(
        f"Minimum individual position value: "
        f"${MINIMUM_POSITION_VALUE:,.2f}"
    )
    print("=" * 82)

    try:
        rows_saved = save_consensus_history(
            scored_results
        )

        print()
        print("=" * 82)
        print("CONSENSUS HISTORY SAVE")
        print("=" * 82)
        print(
            f"Consensus snapshots saved: "
            f"{rows_saved}"
        )
        print("=" * 82)

    except Exception as error:
        print()
        print("=" * 82)
        print("CONSENSUS HISTORY SAVE FAILED")
        print("=" * 82)
        print(f"Error: {error}")
        print("=" * 82)

    display_results(scored_results)


if __name__ == "__main__":
    main()