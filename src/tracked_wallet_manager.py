from __future__ import annotations

import argparse
import re
import sqlite3
from typing import Any

from database import (
    add_tracked_wallet,
    create_tables,
    get_tracked_wallets,
    remove_tracked_wallet,
    set_tracked_wallet_active,
)


WALLET_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def validate_wallet(wallet: str) -> str:
    """Validate and normalize an EVM-compatible wallet address."""

    normalized = str(wallet or "").strip().lower()

    if not WALLET_PATTERN.fullmatch(normalized):
        raise argparse.ArgumentTypeError(
            "Wallet must start with 0x and contain exactly 40 hexadecimal characters."
        )

    return normalized


def shorten_wallet(wallet: str) -> str:
    if len(wallet) < 14:
        return wallet
    return f"{wallet[:8]}...{wallet[-6:]}"


def print_wallets(wallets: list[dict[str, Any]]) -> None:
    """Print tracked-wallet records in a compact terminal table."""

    if not wallets:
        print("No tracked wallets found.")
        return

    print()
    print("=" * 122)
    print(
        f"{'ID':>4}  {'ACTIVE':<6}  {'WALLET':<19}  "
        f"{'NICKNAME':<24}  {'CATEGORY':<16}  {'LAST STATUS':<12}"
    )
    print("=" * 122)

    for record in wallets:
        print(
            f"{int(record['id']):>4}  "
            f"{'YES' if int(record['active']) == 1 else 'NO':<6}  "
            f"{shorten_wallet(str(record['wallet'])):<19}  "
            f"{str(record.get('nickname') or '-')[:24]:<24}  "
            f"{str(record.get('category') or '-')[:16]:<16}  "
            f"{str(record.get('last_scan_status') or '-')[:12]:<12}"
        )

    print("=" * 122)
    print(f"Total: {len(wallets)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage wallets scanned by the automated wallet pipeline."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add or update a tracked wallet.")
    add_parser.add_argument("wallet", type=validate_wallet)
    add_parser.add_argument("--nickname")
    add_parser.add_argument("--category")
    add_parser.add_argument("--notes")
    add_parser.add_argument(
        "--inactive",
        action="store_true",
        help="Save the wallet but leave automated scanning disabled.",
    )

    list_parser = subparsers.add_parser("list", help="List tracked wallets.")
    list_parser.add_argument(
        "--active-only",
        action="store_true",
        help="Show only wallets enabled for automated scanning.",
    )

    enable_parser = subparsers.add_parser("enable", help="Enable one wallet.")
    enable_parser.add_argument("wallet", type=validate_wallet)

    disable_parser = subparsers.add_parser("disable", help="Disable one wallet.")
    disable_parser.add_argument("wallet", type=validate_wallet)

    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove one wallet from tracking while preserving scan history.",
    )
    remove_parser.add_argument("wallet", type=validate_wallet)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        create_tables()

        if args.command == "add":
            wallet_id = add_tracked_wallet(
                wallet=args.wallet,
                nickname=args.nickname,
                category=args.category,
                notes=args.notes,
                active=not args.inactive,
            )
            print(f"Tracked wallet saved successfully. ID: {wallet_id}")
            return 0

        if args.command == "list":
            print_wallets(
                get_tracked_wallets(active_only=args.active_only)
            )
            return 0

        if args.command == "enable":
            changed = set_tracked_wallet_active(args.wallet, True)
            print("Wallet enabled." if changed else "Wallet was not found.")
            return 0 if changed else 1

        if args.command == "disable":
            changed = set_tracked_wallet_active(args.wallet, False)
            print("Wallet disabled." if changed else "Wallet was not found.")
            return 0 if changed else 1

        if args.command == "remove":
            changed = remove_tracked_wallet(args.wallet)
            print(
                "Wallet removed from tracking; history was preserved."
                if changed
                else "Wallet was not found."
            )
            return 0 if changed else 1

        parser.error("Unsupported command.")
        return 2

    except (ValueError, RuntimeError, sqlite3.Error) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())