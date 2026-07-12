from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from database import connect_database


MINIMUM_WALLETS = 2
MINIMUM_COMBINED_VALUE = 500.0


@dataclass
class ConsensusPosition:
    market_id: str
    title: str
    outcome: str
    wallet_count: int
    wallets: list[str]
    combined_shares: float
    combined_value: float
    combined_pnl: float
    average_entry_price: float
    average_current_price: float


def safe_float(value: Any) -> float:
    """Convert a database value to float without crashing."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def shorten_wallet(wallet: str) -> str:
    """Display a wallet in a shorter, easier-to-read format."""
    if len(wallet) <= 14:
        return wallet

    return f"{wallet[:8]}...{wallet[-6:]}"


def get_latest_positions() -> list[dict[str, Any]]:
    """
    Retrieve positions from the newest stored scan for every tracked wallet.
    """

    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute(
        """
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
            p.percent_pnl,
            p.scan_id
        FROM positions AS p
        INNER JOIN (
            SELECT
                wallet,
                MAX(id) AS latest_scan_id
            FROM wallet_scans
            GROUP BY wallet
        ) AS latest
            ON p.wallet = latest.wallet
            AND p.scan_id = latest.latest_scan_id
        WHERE
            p.shares > 0
        ORDER BY
            p.wallet,
            p.current_value DESC
        """
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def build_consensus(
    positions: list[dict[str, Any]],
) -> list[ConsensusPosition]:
    """
    Group positions by market_id and outcome.

    Two wallets only count as agreeing when they hold the same market
    and the same outcome.
    """

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for position in positions:
        market_id = str(position.get("market_id") or "").strip()
        outcome = str(position.get("outcome") or "").strip()

        if not market_id or not outcome:
            continue

        grouped[(market_id, outcome)].append(position)

    consensus_results: list[ConsensusPosition] = []

    for (market_id, outcome), grouped_positions in grouped.items():
        unique_wallets = sorted(
            {
                str(position.get("wallet") or "")
                for position in grouped_positions
                if position.get("wallet")
            }
        )

        wallet_count = len(unique_wallets)

        if wallet_count < MINIMUM_WALLETS:
            continue

        combined_shares = sum(
            safe_float(position.get("shares"))
            for position in grouped_positions
        )

        combined_value = sum(
            safe_float(position.get("current_value"))
            for position in grouped_positions
        )

        if combined_value < MINIMUM_COMBINED_VALUE:
            continue

        combined_pnl = sum(
            safe_float(position.get("cash_pnl"))
            for position in grouped_positions
        )

        total_entry_weight = sum(
            safe_float(position.get("shares"))
            for position in grouped_positions
        )

        if total_entry_weight > 0:
            average_entry_price = sum(
                safe_float(position.get("average_price"))
                * safe_float(position.get("shares"))
                for position in grouped_positions
            ) / total_entry_weight

            average_current_price = sum(
                safe_float(position.get("current_price"))
                * safe_float(position.get("shares"))
                for position in grouped_positions
            ) / total_entry_weight
        else:
            average_entry_price = 0.0
            average_current_price = 0.0

        title = str(
            grouped_positions[0].get("title")
            or "Unknown market"
        )

        consensus_results.append(
            ConsensusPosition(
                market_id=market_id,
                title=title,
                outcome=outcome,
                wallet_count=wallet_count,
                wallets=unique_wallets,
                combined_shares=combined_shares,
                combined_value=combined_value,
                combined_pnl=combined_pnl,
                average_entry_price=average_entry_price,
                average_current_price=average_current_price,
            )
        )

    consensus_results.sort(
        key=lambda result: (
            result.wallet_count,
            result.combined_value,
        ),
        reverse=True,
    )

    return consensus_results


def consensus_grade(wallet_count: int) -> str:
    """Assign a preliminary strength label."""

    if wallet_count >= 5:
        return "VERY STRONG"

    if wallet_count >= 4:
        return "STRONG"

    if wallet_count >= 3:
        return "MODERATE"

    return "EARLY"


def display_consensus(
    results: list[ConsensusPosition],
) -> None:
    print()
    print("=" * 80)
    print("POLYMARKET SMART MONEY CONSENSUS")
    print("=" * 80)

    if not results:
        print()
        print("No qualifying consensus positions were found.")
        print(
            f"Current requirement: at least {MINIMUM_WALLETS} wallets "
            f"and ${MINIMUM_COMBINED_VALUE:,.2f} combined value."
        )
        return

    print()
    print(f"Consensus positions found: {len(results)}")

    for number, result in enumerate(results, start=1):
        price_move = (
            result.average_current_price
            - result.average_entry_price
        )

        print()
        print("-" * 80)
        print(f"{number}. {result.title}")
        print(f"Outcome:                {result.outcome}")
        print(f"Consensus grade:        {consensus_grade(result.wallet_count)}")
        print(f"Qualified wallets:      {result.wallet_count}")
        print(f"Combined shares:        {result.combined_shares:,.2f}")
        print(f"Combined current value: ${result.combined_value:,.2f}")
        print(f"Combined open PnL:      ${result.combined_pnl:,.2f}")
        print(f"Average entry price:    {result.average_entry_price:.3f}")
        print(f"Average current price:  {result.average_current_price:.3f}")
        print(f"Observed price move:    {price_move:+.3f}")

        print("Wallets:")

        for wallet in result.wallets:
            print(f"  - {shorten_wallet(wallet)}")

    print()
    print("=" * 80)
    print("Important: consensus is confirmation, not automatic value.")
    print("A position may already be overpriced after the wallets entered.")
    print("=" * 80)


def main() -> None:
    positions = get_latest_positions()
    results = build_consensus(positions)
    display_consensus(results)


if __name__ == "__main__":
    main()