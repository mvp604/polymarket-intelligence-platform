from __future__ import annotations

import requests


DATA_API_URL = "https://data-api.polymarket.com"
REQUEST_TIMEOUT = 20


def shorten_wallet(wallet: str) -> str:
    """Display a wallet address in a shorter, easier-to-read format."""
    if len(wallet) < 14:
        return wallet

    return f"{wallet[:8]}...{wallet[-6:]}"


def fetch_positions(wallet: str, limit: int = 20) -> list[dict]:
    """Retrieve a wallet's current Polymarket positions."""

    response = requests.get(
        f"{DATA_API_URL}/positions",
        params={
            "user": wallet,
            "limit": limit,
            "sortBy": "CURRENT",
            "sortDirection": "DESC",
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    positions = response.json()

    if not isinstance(positions, list):
        raise ValueError("Polymarket returned an unexpected response.")

    return positions


def safe_number(value: object) -> float:
    """Convert API values to numbers without crashing."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def display_positions(wallet: str, positions: list[dict]) -> None:
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


def main() -> None:
    wallet = input("Paste a Polymarket wallet address: ").strip()

    if not wallet:
        print("No wallet address was entered.")
        return

    try:
        positions = fetch_positions(wallet)
        display_positions(wallet, positions)

    except requests.RequestException as error:
        print()
        print("Could not retrieve the wallet positions.")
        print(f"Error: {error}")

    except ValueError as error:
        print()
        print(f"Data error: {error}")


if __name__ == "__main__":
    main()