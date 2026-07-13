from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("database/polymarket.db")
MAX_SNAPSHOTS_PER_MARKET = 5


def connect_database() -> sqlite3.Connection:
    """
    Open the Polymarket SQLite database.

    sqlite3.Row allows us to access columns by name:
    row["title"] instead of row[0].
    """
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at: {DATABASE_PATH.resolve()}"
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def fetch_consensus_history(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    """
    Retrieve all stored consensus snapshots.

    Results are sorted by market, outcome, and scan time.
    """
    query = """
        SELECT
            id,
            market_id,
            title,
            outcome,
            wallet_count,
            combined_shares,
            combined_value,
            combined_pnl,
            conviction_score,
            conviction_grade,
            average_entry_price,
            average_current_price,
            observed_price_move,
            scanned_at
        FROM consensus_history
        ORDER BY market_id, outcome, scanned_at ASC
    """

    cursor = connection.execute(query)
    return cursor.fetchall()


def group_history(
    rows: list[sqlite3.Row],
) -> dict[tuple[str, str], list[sqlite3.Row]]:
    """
    Group snapshots by market_id and outcome.

    A YES position and a NO position are treated as separate signals.
    """
    grouped: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)

    for row in rows:
        market_id = str(row["market_id"])
        outcome = str(row["outcome"])
        grouped[(market_id, outcome)].append(row)

    return grouped


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def direction_symbol(old_value: float, new_value: float) -> str:
    """
    Return a simple direction arrow.
    """
    if new_value > old_value:
        return "↑"
    if new_value < old_value:
        return "↓"
    return "→"


def classify_trend(history: list[sqlite3.Row]) -> str:
    """
    Classify the signal based on its earliest and latest snapshots.
    """
    if len(history) == 1:
        return "NEW"

    first = history[0]
    latest = history[-1]

    first_wallets = safe_int(first["wallet_count"])
    latest_wallets = safe_int(latest["wallet_count"])

    first_score = safe_float(first["conviction_score"])
    latest_score = safe_float(latest["conviction_score"])

    first_value = safe_float(first["combined_value"])
    latest_value = safe_float(latest["combined_value"])

    improving_metrics = 0
    weakening_metrics = 0

    if latest_wallets > first_wallets:
        improving_metrics += 1
    elif latest_wallets < first_wallets:
        weakening_metrics += 1

    if latest_score > first_score:
        improving_metrics += 1
    elif latest_score < first_score:
        weakening_metrics += 1

    if latest_value > first_value:
        improving_metrics += 1
    elif latest_value < first_value:
        weakening_metrics += 1

    if improving_metrics >= 2:
        return "BUILDING"

    if weakening_metrics >= 2:
        return "WEAKENING"

    return "STABLE"


def format_money(value: Any) -> str:
    return f"${safe_float(value):,.2f}"


def format_price(value: Any) -> str:
    return f"{safe_float(value):.4f}"


def display_market_history(
    market_key: tuple[str, str],
    history: list[sqlite3.Row],
) -> None:
    market_id, outcome = market_key
    latest = history[-1]
    trend = classify_trend(history)

    print()
    print("=" * 100)
    print(str(latest["title"]))
    print("=" * 100)
    print(f"Market ID: {market_id}")
    print(f"Outcome: {outcome}")
    print(f"Trend: {trend}")
    print(f"Snapshots stored: {len(history)}")
    print(f"First seen: {history[0]['scanned_at']}")
    print(f"Latest seen: {latest['scanned_at']}")
    print()

    recent_history = history[-MAX_SNAPSHOTS_PER_MARKET:]

    print(
        f"{'SCANNED AT':25}"
        f"{'WALLETS':>10}"
        f"{'SCORE':>10}"
        f"{'GRADE':>10}"
        f"{'VALUE':>16}"
        f"{'PRICE':>12}"
    )
    print("-" * 100)

    for row in recent_history:
        print(
            f"{str(row['scanned_at'])[:24]:25}"
            f"{safe_int(row['wallet_count']):>10}"
            f"{safe_float(row['conviction_score']):>10.1f}"
            f"{str(row['conviction_grade'] or '-'):>10}"
            f"{format_money(row['combined_value']):>16}"
            f"{format_price(row['average_current_price']):>12}"
        )

    if len(history) >= 2:
        previous = history[-2]

        wallet_arrow = direction_symbol(
            safe_int(previous["wallet_count"]),
            safe_int(latest["wallet_count"]),
        )

        score_arrow = direction_symbol(
            safe_float(previous["conviction_score"]),
            safe_float(latest["conviction_score"]),
        )

        value_arrow = direction_symbol(
            safe_float(previous["combined_value"]),
            safe_float(latest["combined_value"]),
        )

        price_arrow = direction_symbol(
            safe_float(previous["average_current_price"]),
            safe_float(latest["average_current_price"]),
        )

        print()
        print("LATEST CHANGE")
        print("-" * 100)
        print(
            f"Wallets: "
            f"{safe_int(previous['wallet_count'])} "
            f"{wallet_arrow} "
            f"{safe_int(latest['wallet_count'])}"
        )
        print(
            f"Conviction: "
            f"{safe_float(previous['conviction_score']):.1f} "
            f"{score_arrow} "
            f"{safe_float(latest['conviction_score']):.1f}"
        )
        print(
            f"Combined value: "
            f"{format_money(previous['combined_value'])} "
            f"{value_arrow} "
            f"{format_money(latest['combined_value'])}"
        )
        print(
            f"Current price: "
            f"{format_price(previous['average_current_price'])} "
            f"{price_arrow} "
            f"{format_price(latest['average_current_price'])}"
        )


def main() -> None:
    print()
    print("=" * 100)
    print("POLYMARKET CONSENSUS HISTORY ANALYTICS V1")
    print("=" * 100)

    try:
        connection = connect_database()

        try:
            rows = fetch_consensus_history(connection)
        finally:
            connection.close()

        if not rows:
            print()
            print("No consensus history has been stored yet.")
            print("Run the consensus or conviction engine several times first.")
            return

        grouped = group_history(rows)

        print()
        print(f"Consensus snapshots found: {len(rows)}")
        print(f"Unique market outcomes found: {len(grouped)}")

        sorted_groups = sorted(
            grouped.items(),
            key=lambda item: (
                safe_float(item[1][-1]["conviction_score"]),
                safe_int(item[1][-1]["wallet_count"]),
                safe_float(item[1][-1]["combined_value"]),
            ),
            reverse=True,
        )

        for market_key, history in sorted_groups:
            display_market_history(market_key, history)

        print()
        print("=" * 100)
        print("ANALYSIS COMPLETE")
        print("=" * 100)

    except sqlite3.OperationalError as error:
        print()
        print("Database error:")
        print(error)
        print()
        print(
            "This usually means a table or column name in the code "
            "does not exactly match your SQLite database."
        )

    except Exception as error:
        print()
        print(f"Unexpected error: {error}")


if __name__ == "__main__":
    main()