import json

import requests


API_URL = "https://gamma-api.polymarket.com/markets"


def get_active_markets(limit=10):
    parameters = {
        "active": "true",
        "closed": "false",
        "limit": limit,
    }

    try:
        response = requests.get(
            API_URL,
            params=parameters,
            timeout=20,
        )

        response.raise_for_status()

        markets = response.json()

        if not isinstance(markets, list):
            print("Unexpected response from Polymarket.")
            return []

        return markets

    except requests.RequestException as error:
        print(f"Could not connect to Polymarket: {error}")
        return []


def display_markets(markets):
    print("=" * 70)
    print("ACTIVE POLYMARKET MARKETS")
    print("=" * 70)

    if not markets:
        print("No markets were retrieved.")
        return

    for number, market in enumerate(markets, start=1):
        question = market.get("question", "Question unavailable")
        volume = market.get("volume", 0)
        liquidity = market.get("liquidity", 0)
        outcomes = market.get("outcomes", "[]")
        prices = market.get("outcomePrices", "[]")

        try:
            outcomes = json.loads(outcomes)
        except (TypeError, json.JSONDecodeError):
            outcomes = []

        try:
            prices = json.loads(prices)
        except (TypeError, json.JSONDecodeError):
            prices = []

        print()
        print(f"{number}. {question}")
        print(f"   Volume: ${float(volume or 0):,.2f}")
        print(f"   Liquidity: ${float(liquidity or 0):,.2f}")

        if outcomes and prices:
            for outcome, price in zip(outcomes, prices):
                probability = float(price) * 100
                print(f"   {outcome}: {probability:.1f}%")


def main():
    markets = get_active_markets(limit=10)
    display_markets(markets)


if __name__ == "__main__":
    main()