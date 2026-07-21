from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests

from change_detector import compare_positions, display_changes
from database import (
    add_tracked_wallet,
    count_wallet_scans,
    create_tables,
    get_active_wallets,
    get_positions_for_scan,
    get_previous_scan_id,
    save_wallet_scan,
    update_tracked_wallet_scan_status,
)


DATA_API_URL = "https://data-api.polymarket.com"
REQUEST_TIMEOUT = 20
DEFAULT_POSITION_LIMIT = 500
DEFAULT_REQUEST_RETRIES = 3
WALLET_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


@dataclass(slots=True)
class ScanResult:
    """Outcome of one wallet scan."""

    wallet: str
    success: bool
    scan_id: int | None = None
    positions_found: int = 0
    error_message: str | None = None


def shorten_wallet(wallet: str) -> str:
    """Display a wallet address in a shorter, easier-to-read format."""

    if len(wallet) < 14:
        return wallet

    return f"{wallet[:8]}...{wallet[-6:]}"


def normalize_wallet(wallet: str) -> str:
    """Normalize a wallet address for API and database usage."""

    return str(wallet or "").strip().lower()


def validate_wallet(wallet: str) -> str:
    """Validate and normalize an EVM-compatible Polymarket wallet address."""

    normalized = normalize_wallet(wallet)

    if not normalized:
        raise ValueError("No wallet address was entered.")

    if not WALLET_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Wallet must start with 0x and contain exactly 40 hexadecimal characters."
        )

    return normalized


def safe_number(value: object) -> float:
    """Convert API values to numbers without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def fetch_positions(
    wallet: str,
    *,
    limit: int = DEFAULT_POSITION_LIMIT,
    retries: int = DEFAULT_REQUEST_RETRIES,
) -> list[dict[str, Any]]:
    """Retrieve a wallet's current Polymarket positions with retry handling."""

    validated_wallet = validate_wallet(wallet)
    last_error: requests.RequestException | None = None

    for attempt in range(1, max(1, retries) + 1):
        try:
            response = requests.get(
                f"{DATA_API_URL}/positions",
                params={
                    "user": validated_wallet,
                    "limit": max(1, int(limit)),
                    "sortBy": "CURRENT",
                    "sortDirection": "DESC",
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            positions = response.json()

            if not isinstance(positions, list):
                raise ValueError("Polymarket returned an unexpected response.")

            return [position for position in positions if isinstance(position, dict)]

        except requests.RequestException as error:
            last_error = error

            if attempt >= max(1, retries):
                break

            wait_seconds = min(2 ** (attempt - 1), 8)
            print(
                f"Request failed for {shorten_wallet(validated_wallet)} "
                f"(attempt {attempt}/{retries}). Retrying in {wait_seconds}s..."
            )
            time.sleep(wait_seconds)

    if last_error is not None:
        raise last_error

    raise RuntimeError("Wallet position request failed without an error message.")


def display_positions(wallet: str, positions: list[dict[str, Any]]) -> None:
    """Print wallet positions in a readable format."""

    print()
    print("=" * 76)
    print("POLYMARKET WALLET TRACKER")
    print("=" * 76)
    print(f"Wallet: {shorten_wallet(wallet)}")
    print(f"Open positions found: {len(positions)}")
    print("=" * 76)

    if not positions:
        print("No open positions were found for this wallet.")
        return

    total_value = 0.0
    total_cash_pnl = 0.0

    for number, position in enumerate(positions, start=1):
        title = position.get("title") or "Unknown market"
        outcome = position.get("outcome") or "Unknown"
        size = safe_number(position.get("size"))
        average_price = safe_number(position.get("avgPrice"))
        current_price = safe_number(position.get("curPrice"))
        current_value = safe_number(position.get("currentValue"))
        cash_pnl = safe_number(position.get("cashPnl"))
        percent_pnl = safe_number(position.get("percentPnl"))

        total_value += current_value
        total_cash_pnl += cash_pnl

        print()
        print(f"{number}. {title}")
        print(f"   Outcome:       {outcome}")
        print(f"   Shares:        {size:,.2f}")
        print(f"   Average price: {average_price:.3f}")
        print(f"   Current price: {current_price:.3f}")
        print(f"   Current value: ${current_value:,.2f}")
        print(f"   Cash PnL:      ${cash_pnl:,.2f}")
        print(f"   Percent PnL:   {percent_pnl:,.2f}%")

    print()
    print("=" * 76)
    print(f"Total current value: ${total_value:,.2f}")
    print(f"Total open PnL:      ${total_cash_pnl:,.2f}")
    print("=" * 76)


def display_change_analysis(wallet: str, scan_id: int) -> None:
    """Compare the latest scan with the immediately preceding scan."""

    previous_scan_id = get_previous_scan_id(wallet, scan_id)

    if previous_scan_id is None:
        print()
        print("=" * 76)
        print("CHANGE DETECTOR")
        print("=" * 76)
        print("This is the first stored scan for this wallet.")
        print("Run the wallet tracker again later to detect changes.")
        print("=" * 76)
        return

    previous_positions = get_positions_for_scan(previous_scan_id)
    current_positions = get_positions_for_scan(scan_id)

    changes = compare_positions(
        previous_positions=previous_positions,
        current_positions=current_positions,
    )
    display_changes(changes)


def scan_wallet(
    wallet: str,
    *,
    display_details: bool,
    position_limit: int,
    track_wallet: bool,
) -> ScanResult:
    """Fetch, store, and compare one wallet without terminating the full run."""

    try:
        validated_wallet = validate_wallet(wallet)

        if track_wallet:
            add_tracked_wallet(validated_wallet, active=True)

        positions = fetch_positions(
            validated_wallet,
            limit=position_limit,
        )
        scan_id = save_wallet_scan(validated_wallet, positions)
        total_scans = count_wallet_scans(validated_wallet)

        if display_details:
            display_positions(validated_wallet, positions)
            display_change_analysis(validated_wallet, scan_id)

            print()
            print("DATABASE SAVE COMPLETE")
            print(f"Scan ID: {scan_id}")
            print(f"Stored scans for this wallet: {total_scans}")
            print(f"Positions saved: {len(positions)}")

        update_tracked_wallet_scan_status(
            validated_wallet,
            status="SUCCESS",
            error_message=None,
        )

        return ScanResult(
            wallet=validated_wallet,
            success=True,
            scan_id=scan_id,
            positions_found=len(positions),
        )

    except (
        requests.RequestException,
        ValueError,
        RuntimeError,
        sqlite3.Error,
    ) as error:
        normalized_wallet = normalize_wallet(wallet)
        error_message = str(error)

        try:
            update_tracked_wallet_scan_status(
                normalized_wallet,
                status="FAILED",
                error_message=error_message,
            )
        except sqlite3.Error:
            pass

        if display_details:
            print()
            print(f"Wallet scan failed for {shorten_wallet(normalized_wallet)}.")
            print(f"Error: {error_message}")

        return ScanResult(
            wallet=normalized_wallet,
            success=False,
            error_message=error_message,
        )


def run_interactive(position_limit: int) -> int:
    """Run the original one-wallet interactive workflow."""

    wallet = input("Paste a Polymarket wallet address: ").strip()

    result = scan_wallet(
        wallet,
        display_details=True,
        position_limit=position_limit,
        track_wallet=True,
    )

    return 0 if result.success else 1


def run_single_wallet(wallet: str, position_limit: int) -> int:
    """Scan one wallet supplied on the command line."""

    result = scan_wallet(
        wallet,
        display_details=True,
        position_limit=position_limit,
        track_wallet=True,
    )

    return 0 if result.success else 1


def run_pipeline(position_limit: int, display_details: bool) -> int:
    """Scan every active tracked wallet without requesting keyboard input."""

    create_tables()
    tracked_wallets = get_active_wallets()

    print()
    print("=" * 100)
    print("POLYMARKET WALLET TRACKER - PIPELINE MODE")
    print("=" * 100)
    print(f"Active tracked wallets: {len(tracked_wallets)}")
    print(f"Position limit/wallet:  {position_limit}")
    print("=" * 100)

    if not tracked_wallets:
        print()
        print("No active tracked wallets were found.")
        print("The pipeline will continue without a wallet refresh.")
        print()
        print("Add one with:")
        print(
            'python .\\src\\tracked_wallet_manager.py add '
            '0xYOUR_WALLET --nickname "Name"'
        )
        return 0

    results: list[ScanResult] = []

    for index, tracked in enumerate(tracked_wallets, start=1):
        wallet = str(tracked.get("wallet") or "")
        nickname = str(tracked.get("nickname") or "").strip()
        label = nickname or shorten_wallet(wallet)

        print()
        print("-" * 100)
        print(f"[{index}/{len(tracked_wallets)}] Scanning: {label}")
        print(f"Wallet: {wallet}")
        print("-" * 100)

        result = scan_wallet(
            wallet,
            display_details=display_details,
            position_limit=position_limit,
            track_wallet=False,
        )
        results.append(result)

        if result.success:
            print(
                f"SUCCESS: {shorten_wallet(result.wallet)} | "
                f"scan_id={result.scan_id} | "
                f"positions={result.positions_found}"
            )
        else:
            print(
                f"FAILED:  {shorten_wallet(result.wallet)} | "
                f"{result.error_message}"
            )

    successful = sum(1 for result in results if result.success)
    failed = len(results) - successful
    positions_saved = sum(
        result.positions_found for result in results if result.success
    )

    print()
    print("=" * 100)
    print("WALLET PIPELINE SUMMARY")
    print("=" * 100)
    print(f"Wallets attempted: {len(results)}")
    print(f"Successful:        {successful}")
    print(f"Failed:            {failed}")
    print(f"Positions saved:   {positions_saved}")
    print("=" * 100)

    # A required pipeline step should fail only when every configured wallet fails.
    if results and successful == 0:
        return 1

    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    """Build command-line arguments for interactive and pipeline operation."""

    parser = argparse.ArgumentParser(
        description=(
            "Scan one Polymarket wallet interactively or scan every active "
            "tracked wallet in automated pipeline mode."
        )
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--pipeline",
        action="store_true",
        help="Scan all active wallets from tracked_wallets without prompting.",
    )
    mode.add_argument(
        "--wallet",
        help="Scan one wallet supplied directly on the command line.",
    )
    mode.add_argument(
        "--interactive",
        action="store_true",
        help="Force the interactive wallet prompt.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_POSITION_LIMIT,
        help=f"Maximum positions requested per wallet (default: {DEFAULT_POSITION_LIMIT}).",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Show full positions and change details during pipeline mode.",
    )

    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be greater than zero.")

    if args.pipeline:
        return run_pipeline(
            position_limit=args.limit,
            display_details=args.details,
        )

    if args.wallet:
        return run_single_wallet(
            wallet=args.wallet,
            position_limit=args.limit,
        )

    if args.interactive:
        return run_interactive(position_limit=args.limit)

    # Direct terminal use remains interactive. When stdout is redirected to the
    # master-pipeline log, automatically choose non-interactive pipeline mode.
    if sys.stdout.isatty():
        return run_interactive(position_limit=args.limit)

    return run_pipeline(
        position_limit=args.limit,
        display_details=args.details,
    )


if __name__ == "__main__":
    raise SystemExit(main())