from __future__ import annotations

import requests

LEADERBOARD_URL = "https://data-api.polymarket.com/v1/leaderboard"


def fetch_top_traders(
    category: str = "SPORTS",
    time_period: str = "MONTH",
    order_by: str = "PNL",
    limit: int = 20,
) -> list[dict]:
    """
    Retrieve Polymarket leaderboard traders.

    category examples:
        OVERALL, SPORTS, POLITICS, CRYPTO

    time_period examples:
        DAY, WEEK, MONTH, ALL

    order_by examples:
        PNL, VOL
    """

    parameters = {
        "category": category,
        "timePeriod": time_period,
        "orderBy": order_by,
        "limit": limit,
        "offset": 0,
    }

    try:
        response = requests.get(
            LEADERBOARD_URL,
            params=parameters,
            timeout=30,
        )

        response.raise_for_status()
        traders = response.json()

        if not isinstance(traders, list):
            raise ValueError("Polymarket returned an unexpected response.")

        return traders

    except requests.RequestException as error:
        print(f"Unable to retrieve the leaderboard: {error}")
        return []

    except ValueError as error:
        print(f"Unable to read the leaderboard data: {error}")
        return []


def safe_number(value) -> float:
    """Convert a value into a number without crashing."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def shorten_wallet(wallet: str) -> str:
    """Display a public wallet in a shorter readable format."""
    if len(wallet) < 14:
        return wallet

    return f"{wallet[:8]}...{wallet[-6:]}"


def display_traders(traders: list[dict]) -> None:
    print()
    print("=" * 76)
    print("POLYMARKET TOP SPORTS TRADERS — MONTHLY PNL")
    print("=" * 76)

    if not traders:
        print("No traders were returned.")
        return

    for trader in traders:
        rank = trader.get("rank", "N/A")
        username = trader.get("userName") or "Anonymous"
        wallet = trader.get("proxyWallet") or "Unknown"
        pnl = safe_number(trader.get("pnl"))
        volume = safe_number(trader.get("vol"))

        print()
        print(f"Rank:      {rank}")
        print(f"Trader:    {username}")
        print(f"Wallet:    {shorten_wallet(wallet)}")
        print(f"PnL:       ${pnl:,.2f}")
        print(f"Volume:    ${volume:,.2f}")
        print("-" * 76)


def main() -> None:
    traders = fetch_top_traders(
        category="SPORTS",
        time_period="MONTH",
        order_by="PNL",
        limit=20,
    )

    display_traders(traders)


if __name__ == "__main__":
    main()