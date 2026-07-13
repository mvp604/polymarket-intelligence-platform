from __future__ import annotations

import json
import sqlite3
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DATABASE_PATH = Path("database/polymarket.db")

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"

HYPOTHETICAL_STAKE = 100.0
RESOLUTION_WIN_THRESHOLD = 0.99
REQUEST_TIMEOUT_SECONDS = 30
DELAY_BETWEEN_REQUESTS = 0.20


def connect_database() -> sqlite3.Connection:
    """Open the local SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH.resolve()}."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def safe_float(value: Any) -> float:
    """Convert a value to float without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value to integer without crashing."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_json_list(value: Any) -> list[Any]:
    """
    Parse Gamma API fields such as outcomes and outcomePrices.

    They may arrive as JSON strings or ordinary Python lists.
    """

    if isinstance(value, list):
        return value

    if value is None:
        return []

    if isinstance(value, str):
        try:
            parsed = json.loads(value)

            if isinstance(parsed, list):
                return parsed

        except json.JSONDecodeError:
            return []

    return []


def parse_datetime(value: Any) -> datetime | None:
    """Parse ISO timestamps and normalize them to UTC."""

    if not value:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except ValueError:
        return None


def create_backtest_table() -> None:
    """Create persistent storage for resolved backtest results."""

    connection = connect_database()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                selected_outcome TEXT NOT NULL,
                winning_outcome TEXT,
                first_signal_at TEXT NOT NULL,
                market_closed_at TEXT,
                entry_price REAL NOT NULL,
                conviction_score REAL NOT NULL,
                conviction_grade TEXT NOT NULL,
                wallet_count INTEGER NOT NULL,
                hypothetical_stake REAL NOT NULL,
                hypothetical_profit REAL,
                hypothetical_return_pct REAL,
                result_status TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                UNIQUE (
                    market_id,
                    selected_outcome,
                    first_signal_at
                )
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_backtest_results_status
            ON backtest_results(result_status)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_backtest_results_score
            ON backtest_results(conviction_score)
            """
        )

        connection.commit()

    finally:
        connection.close()


def fetch_first_consensus_signals() -> list[dict[str, Any]]:
    """
    Retrieve the earliest stored consensus signal for each market/outcome.

    Using the first observation helps prevent cherry-picking a later,
    more favorable snapshot.
    """

    connection = connect_database()

    try:
        query = """
            WITH first_signals AS (
                SELECT
                    market_id,
                    LOWER(TRIM(outcome)) AS normalized_outcome,
                    MIN(id) AS first_id
                FROM consensus_history
                GROUP BY
                    market_id,
                    LOWER(TRIM(outcome))
            )
            SELECT
                history.id,
                history.market_id,
                history.title,
                history.outcome,
                history.wallet_count,
                history.conviction_score,
                history.conviction_grade,
                history.average_current_price,
                history.scanned_at
            FROM consensus_history AS history
            INNER JOIN first_signals AS first_signal
                ON history.id = first_signal.first_id
            ORDER BY history.scanned_at ASC
        """

        rows = connection.execute(query).fetchall()
        return [dict(row) for row in rows]

    finally:
        connection.close()


def fetch_market_by_condition_id(
    condition_id: str,
) -> dict[str, Any] | None:
    """Retrieve one Gamma market by its Polymarket condition ID."""

    response = requests.get(
        GAMMA_MARKETS_URL,
        params={
            "condition_ids": condition_id,
            "limit": 5,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={
            "User-Agent": "polymarket-intelligence-platform/1.0",
        },
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list):
        return None

    normalized_condition = condition_id.lower()

    for market in payload:
        returned_condition = str(
            market.get("conditionId") or ""
        ).lower()

        if returned_condition == normalized_condition:
            return market

    return None


def determine_winning_outcome(
    market: dict[str, Any],
) -> str | None:
    """
    Determine the winning outcome from final outcome prices.

    A resolved winner should have a price very close to 1.0.
    """

    outcomes = parse_json_list(market.get("outcomes"))
    prices = parse_json_list(market.get("outcomePrices"))

    if not outcomes or len(outcomes) != len(prices):
        return None

    converted_prices = [
        safe_float(price)
        for price in prices
    ]

    if not converted_prices:
        return None

    highest_price = max(converted_prices)
    winning_index = converted_prices.index(highest_price)

    if highest_price < RESOLUTION_WIN_THRESHOLD:
        return None

    return str(outcomes[winning_index])


def calculate_hypothetical_result(
    selected_outcome: str,
    winning_outcome: str,
    entry_price: float,
) -> tuple[float, float, str]:
    """
    Calculate profit from a hypothetical fixed stake.

    If the selected outcome wins:
        payout = stake / entry price
        profit = payout - stake

    If it loses:
        profit = -stake
    """

    if entry_price <= 0 or entry_price >= 1:
        return 0.0, 0.0, "INVALID_ENTRY_PRICE"

    selected_normalized = selected_outcome.strip().casefold()
    winning_normalized = winning_outcome.strip().casefold()

    if selected_normalized == winning_normalized:
        payout = HYPOTHETICAL_STAKE / entry_price
        profit = payout - HYPOTHETICAL_STAKE
        return_pct = profit / HYPOTHETICAL_STAKE

        return profit, return_pct, "WIN"

    return (
        -HYPOTHETICAL_STAKE,
        -1.0,
        "LOSS",
    )


def save_backtest_result(
    result: dict[str, Any],
) -> None:
    """Insert or update one backtest record."""

    connection = connect_database()

    try:
        connection.execute(
            """
            INSERT INTO backtest_results (
                market_id,
                title,
                selected_outcome,
                winning_outcome,
                first_signal_at,
                market_closed_at,
                entry_price,
                conviction_score,
                conviction_grade,
                wallet_count,
                hypothetical_stake,
                hypothetical_profit,
                hypothetical_return_pct,
                result_status,
                evaluated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (
                market_id,
                selected_outcome,
                first_signal_at
            )
            DO UPDATE SET
                title = excluded.title,
                winning_outcome = excluded.winning_outcome,
                market_closed_at = excluded.market_closed_at,
                entry_price = excluded.entry_price,
                conviction_score = excluded.conviction_score,
                conviction_grade = excluded.conviction_grade,
                wallet_count = excluded.wallet_count,
                hypothetical_stake = excluded.hypothetical_stake,
                hypothetical_profit = excluded.hypothetical_profit,
                hypothetical_return_pct =
                    excluded.hypothetical_return_pct,
                result_status = excluded.result_status,
                evaluated_at = excluded.evaluated_at
            """,
            (
                result["market_id"],
                result["title"],
                result["selected_outcome"],
                result.get("winning_outcome"),
                result["first_signal_at"],
                result.get("market_closed_at"),
                result["entry_price"],
                result["conviction_score"],
                result["conviction_grade"],
                result["wallet_count"],
                result["hypothetical_stake"],
                result.get("hypothetical_profit"),
                result.get("hypothetical_return_pct"),
                result["result_status"],
                result["evaluated_at"],
            ),
        )

        connection.commit()

    finally:
        connection.close()


def evaluate_signal(
    signal: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one historical consensus signal."""

    market_id = str(signal.get("market_id") or "").strip()
    title = str(signal.get("title") or "Unknown market")
    selected_outcome = str(signal.get("outcome") or "Unknown")
    first_signal_at = str(signal.get("scanned_at") or "")
    entry_price = safe_float(
        signal.get("average_current_price")
    )

    base_result = {
        "market_id": market_id,
        "title": title,
        "selected_outcome": selected_outcome,
        "winning_outcome": None,
        "first_signal_at": first_signal_at,
        "market_closed_at": None,
        "entry_price": entry_price,
        "conviction_score": safe_float(
            signal.get("conviction_score")
        ),
        "conviction_grade": str(
            signal.get("conviction_grade")
            or "UNRATED"
        ),
        "wallet_count": safe_int(
            signal.get("wallet_count")
        ),
        "hypothetical_stake": HYPOTHETICAL_STAKE,
        "hypothetical_profit": None,
        "hypothetical_return_pct": None,
        "result_status": "UNKNOWN",
        "evaluated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    market = fetch_market_by_condition_id(market_id)

    if market is None:
        base_result["result_status"] = "MARKET_NOT_FOUND"
        return base_result

    is_closed = bool(market.get("closed"))

    closed_at_value = (
        market.get("closedTime")
        or market.get("endDate")
    )

    base_result["market_closed_at"] = (
        str(closed_at_value)
        if closed_at_value
        else None
    )

    if not is_closed:
        base_result["result_status"] = "PENDING"
        return base_result

    signal_time = parse_datetime(first_signal_at)
    closed_time = parse_datetime(closed_at_value)

    # Reject signals first observed after market closure.
    # This prevents look-ahead bias from stale wallet positions.
    if (
        signal_time is not None
        and closed_time is not None
        and signal_time >= closed_time
    ):
        base_result["result_status"] = "LATE_SIGNAL_EXCLUDED"
        return base_result

    winning_outcome = determine_winning_outcome(market)

    if winning_outcome is None:
        base_result["result_status"] = "CLOSED_UNRESOLVED"
        return base_result

    base_result["winning_outcome"] = winning_outcome

    profit, return_pct, status = (
        calculate_hypothetical_result(
            selected_outcome=selected_outcome,
            winning_outcome=winning_outcome,
            entry_price=entry_price,
        )
    )

    base_result["hypothetical_profit"] = profit
    base_result["hypothetical_return_pct"] = return_pct
    base_result["result_status"] = status

    return base_result


def display_signal_result(
    number: int,
    result: dict[str, Any],
) -> None:
    """Display one backtest evaluation."""

    print()
    print("-" * 100)
    print(f"{number}. {result['title']}")
    print("-" * 100)

    print(
        f"Selected outcome:         "
        f"{result['selected_outcome']}"
    )
    print(
        f"Winning outcome:          "
        f"{result.get('winning_outcome') or '-'}"
    )
    print(
        f"First signal price:       "
        f"{result['entry_price']:.4f}"
    )
    print(
        f"Conviction score:         "
        f"{result['conviction_score']:.1f}"
    )
    print(
        f"Conviction grade:         "
        f"{result['conviction_grade']}"
    )
    print(
        f"Agreeing wallets:         "
        f"{result['wallet_count']}"
    )
    print(
        f"Status:                   "
        f"{result['result_status']}"
    )

    if result["hypothetical_profit"] is not None:
        print(
            f"Hypothetical stake:       "
            f"${result['hypothetical_stake']:,.2f}"
        )
        print(
            f"Hypothetical profit:      "
            f"${result['hypothetical_profit']:,.2f}"
        )
        print(
            f"Hypothetical return:      "
            f"{result['hypothetical_return_pct']:.1%}"
        )


def summarize_resolved_results(
    results: list[dict[str, Any]],
) -> None:
    """Print overall and grade-level performance."""

    resolved = [
        result
        for result in results
        if result["result_status"] in {"WIN", "LOSS"}
    ]

    print()
    print("=" * 100)
    print("BACKTEST SUMMARY")
    print("=" * 100)

    status_counts: dict[str, int] = defaultdict(int)

    for result in results:
        status_counts[result["result_status"]] += 1

    print(f"Signals evaluated:             {len(results)}")

    for status, count in sorted(status_counts.items()):
        print(f"{status:30} {count}")

    if not resolved:
        print()
        print("No valid resolved signals are available yet.")
        print(
            "This is expected while most stored markets remain open "
            "or when signals were first captured after closure."
        )
        return

    wins = [
        result
        for result in resolved
        if result["result_status"] == "WIN"
    ]

    total_staked = (
        len(resolved)
        * HYPOTHETICAL_STAKE
    )

    total_profit = sum(
        safe_float(result["hypothetical_profit"])
        for result in resolved
    )

    roi = (
        total_profit / total_staked
        if total_staked > 0
        else 0.0
    )

    returns = [
        safe_float(
            result["hypothetical_return_pct"]
        )
        for result in resolved
    ]

    print()
    print(f"Valid resolved signals:        {len(resolved)}")
    print(f"Wins:                          {len(wins)}")
    print(
        f"Win rate:                      "
        f"{len(wins) / len(resolved):.1%}"
    )
    print(f"Total hypothetical stake:      ${total_staked:,.2f}")
    print(f"Total hypothetical profit:     ${total_profit:,.2f}")
    print(f"Portfolio ROI:                 {roi:.1%}")
    print(
        f"Median signal return:          "
        f"{statistics.median(returns):.1%}"
    )

    grouped_by_grade: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for result in resolved:
        grouped_by_grade[
            result["conviction_grade"]
        ].append(result)

    print()
    print("RESULTS BY CONVICTION GRADE")
    print("-" * 100)

    for grade, grade_results in sorted(
        grouped_by_grade.items()
    ):
        grade_wins = sum(
            1
            for result in grade_results
            if result["result_status"] == "WIN"
        )

        grade_profit = sum(
            safe_float(result["hypothetical_profit"])
            for result in grade_results
        )

        grade_stake = (
            len(grade_results)
            * HYPOTHETICAL_STAKE
        )

        grade_roi = (
            grade_profit / grade_stake
            if grade_stake > 0
            else 0.0
        )

        print()
        print(f"{grade}")
        print(f"  Signals:      {len(grade_results)}")
        print(
            f"  Win rate:     "
            f"{grade_wins / len(grade_results):.1%}"
        )
        print(f"  Profit:       ${grade_profit:,.2f}")
        print(f"  ROI:          {grade_roi:.1%}")


def main() -> None:
    """Run the historical signal backtester."""

    print()
    print("=" * 100)
    print("POLYMARKET HISTORICAL BACKTESTING ENGINE v1")
    print("=" * 100)
    print(
        f"Hypothetical fixed stake per signal: "
        f"${HYPOTHETICAL_STAKE:,.2f}"
    )

    create_backtest_table()

    signals = fetch_first_consensus_signals()

    print(f"First-observed signals found: {len(signals)}")

    if not signals:
        print("No consensus signals are available to evaluate.")
        return

    results: list[dict[str, Any]] = []

    for number, signal in enumerate(
        signals,
        start=1,
    ):
        print()
        print(
            f"Evaluating signal "
            f"{number} of {len(signals)}..."
        )

        try:
            result = evaluate_signal(signal)

        except requests.RequestException as error:
            result = {
                "market_id": signal["market_id"],
                "title": signal["title"],
                "selected_outcome": signal["outcome"],
                "winning_outcome": None,
                "first_signal_at": signal["scanned_at"],
                "market_closed_at": None,
                "entry_price": safe_float(
                    signal["average_current_price"]
                ),
                "conviction_score": safe_float(
                    signal["conviction_score"]
                ),
                "conviction_grade": signal[
                    "conviction_grade"
                ],
                "wallet_count": safe_int(
                    signal["wallet_count"]
                ),
                "hypothetical_stake": HYPOTHETICAL_STAKE,
                "hypothetical_profit": None,
                "hypothetical_return_pct": None,
                "result_status": "API_ERROR",
                "evaluated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            print(f"API error: {error}")

        save_backtest_result(result)
        results.append(result)

        display_signal_result(number, result)

        if number < len(signals):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    summarize_resolved_results(results)

    print()
    print("=" * 100)
    print("IMPORTANT")
    print("=" * 100)
    print(
        "Backtests are hypothetical and do not include slippage, "
        "fees, liquidity constraints or partial fills."
    )
    print(
        "Signals first observed after market closure are excluded "
        "to reduce look-ahead bias."
    )
    print(
        "A useful evaluation requires a much larger sample of "
        "independently resolved signals."
    )
    print("=" * 100)


if __name__ == "__main__":
    main()