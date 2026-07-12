from __future__ import annotations

import time

from change_detector import compare_positions, display_changes
from database import (
    count_wallet_scans,
    get_positions_for_scan,
    get_previous_scan_id,
    save_wallet_scan,
)
from traders import fetch_top_traders
from wallet_tracker import fetch_positions


WATCHLIST_SIZE = 5
DELAY_BETWEEN_WALLETS = 1.0


def scan_wallet(wallet: str, username: str) -> None:
    """Scan one wallet, save its positions and detect changes."""

    print()
    print("=" * 76)
    print(f"SCANNING TRADER: {username}")
    print(f"WALLET: {wallet}")
    print("=" * 76)

    try:
        positions = fetch_positions(wallet)

        if not positions:
            print("No open positions found.")
            return

        scan_id = save_wallet_scan(wallet, positions)
        total_scans = count_wallet_scans(wallet)

        previous_scan_id = get_previous_scan_id(wallet, scan_id)

        print(f"Open positions: {len(positions)}")
        print(f"Database scan ID: {scan_id}")
        print(f"Stored scans for wallet: {total_scans}")

        if previous_scan_id is None:
            print()
            print("FIRST STORED SCAN")
            print("No previous scan exists for comparison.")
            return

        previous_positions = get_positions_for_scan(previous_scan_id)
        current_positions = get_positions_for_scan(scan_id)

        changes = compare_positions(
            previous_positions=previous_positions,
            current_positions=current_positions,
        )

        display_changes(changes)

    except Exception as error:
        print(f"Could not scan wallet: {error}")


def main() -> None:
    print("=" * 76)
    print("POLYMARKET SMART-MONEY WATCHLIST SCANNER")
    print("=" * 76)

    traders = fetch_top_traders(
        category="SPORTS",
        time_period="MONTH",
        order_by="PNL",
        limit=WATCHLIST_SIZE,
    )

    if not traders:
        print("No traders were returned by the leaderboard.")
        return

    valid_traders = []

    for trader in traders:
        wallet = trader.get("proxyWallet")
        username = trader.get("userName") or "Anonymous"

        if wallet:
            valid_traders.append(
                {
                    "wallet": wallet,
                    "username": username,
                }
            )

    if not valid_traders:
        print("No valid wallet addresses were found.")
        return

    print(f"Qualified wallets to scan: {len(valid_traders)}")

    for number, trader in enumerate(valid_traders, start=1):
        print()
        print(f"WALLET {number} OF {len(valid_traders)}")

        scan_wallet(
            wallet=trader["wallet"],
            username=trader["username"],
        )

        if number < len(valid_traders):
            time.sleep(DELAY_BETWEEN_WALLETS)

    print()
    print("=" * 76)
    print("WATCHLIST SCAN COMPLETE")
    print("=" * 76)


if __name__ == "__main__":
    main()