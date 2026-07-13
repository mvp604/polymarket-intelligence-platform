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


TARGET_USABLE_WALLETS = 20
MAX_CANDIDATES_TO_CHECK = 50
DELAY_BETWEEN_WALLETS = 1.0


def scan_wallet(wallet: str, username: str) -> str:
    """
    Scan one wallet, save its positions and detect changes.

    Returns:
        "stored" if the wallet had open positions and was saved
        "no_positions" if the wallet had no open positions
        "failed" if an error occurred
    """

    print()
    print("=" * 76)
    print(f"SCANNING TRADER: {username}")
    print(f"WALLET: {wallet}")
    print("=" * 76)

    try:
        positions = fetch_positions(wallet)

        if not positions:
            print("No open positions found.")
            return "no_positions"

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
            return "stored"

        previous_positions = get_positions_for_scan(previous_scan_id)
        current_positions = get_positions_for_scan(scan_id)

        changes = compare_positions(
            previous_positions=previous_positions,
            current_positions=current_positions,
        )

        display_changes(changes)

        return "stored"

    except Exception as error:
        print(f"Could not scan wallet: {error}")
        return "failed"


def main() -> None:
    print("=" * 76)
    print("POLYMARKET SMART-MONEY WATCHLIST SCANNER")
    print("=" * 76)

    print(f"Target usable wallets: {TARGET_USABLE_WALLETS}")
    print(f"Maximum candidates to check: {MAX_CANDIDATES_TO_CHECK}")

    traders = fetch_top_traders(
        category="SPORTS",
        time_period="MONTH",
        order_by="PNL",
        limit=MAX_CANDIDATES_TO_CHECK,
    )

    if not traders:
        print("No traders were returned by the leaderboard.")
        return

    unique_traders = []
    seen_wallets = set()

    duplicates_removed = 0
    invalid_wallets = 0

    for trader in traders:
        wallet = str(trader.get("proxyWallet") or "").strip()
        username = str(trader.get("userName") or "Anonymous").strip()

        if not wallet:
            invalid_wallets += 1
            continue

        normalized_wallet = wallet.lower()

        if normalized_wallet in seen_wallets:
            duplicates_removed += 1
            continue

        seen_wallets.add(normalized_wallet)

        unique_traders.append(
            {
                "wallet": wallet,
                "username": username,
            }
        )

    if not unique_traders:
        print("No valid unique wallet addresses were found.")
        return

    print()
    print(f"Leaderboard candidates returned: {len(traders)}")
    print(f"Unique valid wallets found: {len(unique_traders)}")
    print(f"Duplicate wallets removed: {duplicates_removed}")
    print(f"Missing wallet addresses: {invalid_wallets}")

    usable_wallets = 0
    candidates_checked = 0
    no_position_wallets = 0
    failed_wallets = 0

    for trader in unique_traders:
        if usable_wallets >= TARGET_USABLE_WALLETS:
            print()
            print(
                f"Usable-wallet target reached: "
                f"{usable_wallets}/{TARGET_USABLE_WALLETS}"
            )
            break

        candidates_checked += 1

        print()
        print(
            f"CANDIDATE {candidates_checked} "
            f"OF {len(unique_traders)}"
        )
        print(
            f"USABLE WALLETS FOUND: "
            f"{usable_wallets}/{TARGET_USABLE_WALLETS}"
        )

        result = scan_wallet(
            wallet=trader["wallet"],
            username=trader["username"],
        )

        if result == "stored":
            usable_wallets += 1

        elif result == "no_positions":
            no_position_wallets += 1

        elif result == "failed":
            failed_wallets += 1

        if (
            candidates_checked < len(unique_traders)
            and usable_wallets < TARGET_USABLE_WALLETS
        ):
            time.sleep(DELAY_BETWEEN_WALLETS)

    print()
    print("=" * 76)
    print("WATCHLIST SCAN COMPLETE")
    print("=" * 76)
    print(f"Leaderboard candidates returned: {len(traders)}")
    print(f"Unique valid wallets: {len(unique_traders)}")
    print(f"Candidates checked: {candidates_checked}")
    print(f"Usable wallets stored: {usable_wallets}")
    print(f"Wallets with no open positions: {no_position_wallets}")
    print(f"Failed wallet scans: {failed_wallets}")
    print(f"Duplicate wallets removed: {duplicates_removed}")
    print(f"Missing wallet addresses: {invalid_wallets}")

    if usable_wallets >= TARGET_USABLE_WALLETS:
        print(
            f"Target reached: "
            f"{usable_wallets}/{TARGET_USABLE_WALLETS}"
        )
    else:
        print(
            f"Target not reached: "
            f"{usable_wallets}/{TARGET_USABLE_WALLETS}"
        )
        print(
            "The leaderboard did not contain enough usable wallets "
            "within the candidate limit."
        )

    print("=" * 76)


if __name__ == "__main__":
    main()