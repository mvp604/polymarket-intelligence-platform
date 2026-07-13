from __future__ import annotations

import math
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("database/polymarket.db")

MINIMUM_MEANINGFUL_POSITION_VALUE = 500.0


def connect_database() -> sqlite3.Connection:
    """Open the local SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH.resolve()}. "
            "Run the watchlist scanner first."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def safe_float(value: Any) -> float:
    """Convert a value into a float without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value into an integer without crashing."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def create_wallet_rating_table() -> None:
    """Create storage for historical wallet-rating snapshots."""

    connection = connect_database()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS wallet_rating_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                scan_count INTEGER NOT NULL,
                position_count INTEGER NOT NULL,
                meaningful_position_count INTEGER NOT NULL,
                profitable_position_count INTEGER NOT NULL,
                profitable_position_rate REAL NOT NULL,
                total_current_value REAL NOT NULL,
                total_open_pnl REAL NOT NULL,
                open_pnl_ratio REAL NOT NULL,
                largest_position_value REAL NOT NULL,
                concentration_ratio REAL NOT NULL,
                median_position_value REAL NOT NULL,
                wallet_score REAL NOT NULL,
                wallet_grade TEXT NOT NULL,
                rated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_wallet_rating_history_wallet
            ON wallet_rating_history(wallet)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_wallet_rating_history_rated_at
            ON wallet_rating_history(rated_at)
            """
        )

        connection.commit()

    finally:
        connection.close()


def fetch_latest_wallet_positions() -> list[dict[str, Any]]:
    """
    Retrieve the latest stored position snapshot for every wallet.

    Historical scans are excluded from the current rating calculation.
    """

    connection = connect_database()

    try:
        query = """
            WITH latest_scans AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_scan_id,
                    COUNT(*) AS scan_count
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT
                latest.wallet,
                latest.scan_count,
                latest.latest_scan_id,
                p.market_id,
                p.title,
                p.outcome,
                p.shares,
                p.average_price,
                p.current_price,
                p.current_value,
                p.cash_pnl,
                p.percent_pnl
            FROM latest_scans AS latest
            LEFT JOIN positions AS p
                ON p.scan_id = latest.latest_scan_id
               AND p.wallet = latest.wallet
            ORDER BY latest.wallet
        """

        rows = connection.execute(query).fetchall()
        return [dict(row) for row in rows]

    finally:
        connection.close()


def group_positions_by_wallet(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Group latest positions under their wallet addresses."""

    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        wallet = str(row.get("wallet") or "").strip().lower()

        if not wallet:
            continue

        if wallet not in grouped:
            grouped[wallet] = {
                "wallet": wallet,
                "scan_count": safe_int(row.get("scan_count")),
                "positions": [],
            }

        if row.get("market_id") is not None:
            grouped[wallet]["positions"].append(row)

    return grouped


def calculate_wallet_metrics(
    wallet_data: dict[str, Any],
) -> dict[str, Any]:
    """Calculate transparent research metrics for one wallet."""

    wallet = str(wallet_data["wallet"])
    scan_count = safe_int(wallet_data["scan_count"])
    positions = list(wallet_data["positions"])

    meaningful_positions = [
        position
        for position in positions
        if safe_float(position.get("current_value"))
        >= MINIMUM_MEANINGFUL_POSITION_VALUE
    ]

    current_values = [
        safe_float(position.get("current_value"))
        for position in meaningful_positions
    ]

    open_pnls = [
        safe_float(position.get("cash_pnl"))
        for position in meaningful_positions
    ]

    profitable_positions = [
        position
        for position in meaningful_positions
        if safe_float(position.get("cash_pnl")) > 0
    ]

    total_current_value = sum(current_values)
    total_open_pnl = sum(open_pnls)

    profitable_position_rate = (
        len(profitable_positions) / len(meaningful_positions)
        if meaningful_positions
        else 0.0
    )

    open_pnl_ratio = (
        total_open_pnl / total_current_value
        if total_current_value > 0
        else 0.0
    )

    largest_position_value = max(current_values, default=0.0)

    concentration_ratio = (
        largest_position_value / total_current_value
        if total_current_value > 0
        else 1.0
    )

    median_position_value = (
        statistics.median(current_values)
        if current_values
        else 0.0
    )

    return {
        "wallet": wallet,
        "scan_count": scan_count,
        "position_count": len(positions),
        "meaningful_position_count": len(meaningful_positions),
        "profitable_position_count": len(profitable_positions),
        "profitable_position_rate": profitable_position_rate,
        "total_current_value": total_current_value,
        "total_open_pnl": total_open_pnl,
        "open_pnl_ratio": open_pnl_ratio,
        "largest_position_value": largest_position_value,
        "concentration_ratio": concentration_ratio,
        "median_position_value": median_position_value,
    }


def calculate_wallet_score(
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate a provisional wallet-research score out of 100.

    This is not yet a true lifetime skill score because resolved-market
    outcomes have not been incorporated.
    """

    scan_count = safe_int(metrics["scan_count"])
    position_count = safe_int(metrics["meaningful_position_count"])
    total_value = safe_float(metrics["total_current_value"])
    pnl_ratio = safe_float(metrics["open_pnl_ratio"])
    profitable_rate = safe_float(metrics["profitable_position_rate"])
    concentration = safe_float(metrics["concentration_ratio"])

    # 1. Historical observation depth: maximum 10 points.
    scan_score = min(scan_count / 5, 1.0) * 10

    # 2. Meaningful sample size: maximum 15 points.
    sample_score = min(position_count / 15, 1.0) * 15

    # 3. Capital deployed: maximum 15 points.
    if total_value > 0:
        capital_score = min(
            math.log10(max(total_value, 1))
            / math.log10(500_000),
            1.0,
        ) * 15
    else:
        capital_score = 0.0

    # 4. Open PnL ratio: maximum 25 points.
    # Full points at +20%; zero points at -10% or worse.
    pnl_score = min(
        max((pnl_ratio + 0.10) / 0.30, 0.0),
        1.0,
    ) * 25

    # 5. Positive-position consistency: maximum 20 points.
    consistency_score = profitable_rate * 20

    # 6. Diversification: maximum 15 points.
    # Heavy concentration lowers the score.
    diversification_score = max(
        0.0,
        1.0 - concentration,
    ) * 15

    total_score = round(
        scan_score
        + sample_score
        + capital_score
        + pnl_score
        + consistency_score
        + diversification_score,
        1,
    )

    # Restrict wallets with little usable evidence.
    if position_count == 0:
        grade = "INSUFFICIENT DATA"

    elif position_count < 3 or scan_count < 2:
        grade = "WATCHLIST"

    elif total_score >= 85:
        grade = "PROVISIONAL S+"

    elif total_score >= 75:
        grade = "PROVISIONAL S"

    elif total_score >= 65:
        grade = "PROVISIONAL A+"

    elif total_score >= 55:
        grade = "PROVISIONAL A"

    elif total_score >= 40:
        grade = "WATCHLIST"

    else:
        grade = "PASS"

    scored = dict(metrics)

    scored.update(
        {
            "wallet_score": total_score,
            "wallet_grade": grade,
            "scan_score": round(scan_score, 1),
            "sample_score": round(sample_score, 1),
            "capital_score": round(capital_score, 1),
            "pnl_score": round(pnl_score, 1),
            "consistency_score": round(consistency_score, 1),
            "diversification_score": round(
                diversification_score,
                1,
            ),
        }
    )

    return scored


def save_wallet_ratings(
    results: list[dict[str, Any]],
) -> int:
    """Save the current rating snapshot for every wallet."""

    if not results:
        return 0

    create_wallet_rating_table()

    connection = connect_database()
    rated_at = datetime.now(timezone.utc).isoformat()

    try:
        for result in results:
            connection.execute(
                """
                INSERT INTO wallet_rating_history (
                    wallet,
                    scan_count,
                    position_count,
                    meaningful_position_count,
                    profitable_position_count,
                    profitable_position_rate,
                    total_current_value,
                    total_open_pnl,
                    open_pnl_ratio,
                    largest_position_value,
                    concentration_ratio,
                    median_position_value,
                    wallet_score,
                    wallet_grade,
                    rated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["wallet"],
                    result["scan_count"],
                    result["position_count"],
                    result["meaningful_position_count"],
                    result["profitable_position_count"],
                    result["profitable_position_rate"],
                    result["total_current_value"],
                    result["total_open_pnl"],
                    result["open_pnl_ratio"],
                    result["largest_position_value"],
                    result["concentration_ratio"],
                    result["median_position_value"],
                    result["wallet_score"],
                    result["wallet_grade"],
                    rated_at,
                ),
            )

        connection.commit()
        return len(results)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def shorten_wallet(wallet: str) -> str:
    """Shorten a wallet address for terminal display."""

    if len(wallet) <= 16:
        return wallet

    return f"{wallet[:10]}...{wallet[-8:]}"


def display_wallet_rating(
    number: int,
    result: dict[str, Any],
) -> None:
    """Display one wallet's provisional rating."""

    print()
    print("-" * 96)
    print(f"{number}. {shorten_wallet(result['wallet'])}")
    print("-" * 96)

    print(f"Provisional score:        {result['wallet_score']:.1f}/100")
    print(f"Provisional grade:        {result['wallet_grade']}")
    print(f"Stored scans:             {result['scan_count']}")
    print(f"Latest open positions:    {result['position_count']}")
    print(
        f"Positions worth $500+:    "
        f"{result['meaningful_position_count']}"
    )
    print(
        f"Profitable positions:     "
        f"{result['profitable_position_count']}"
    )
    print(
        f"Positive-position rate:   "
        f"{result['profitable_position_rate']:.1%}"
    )
    print(
        f"Total current value:      "
        f"${result['total_current_value']:,.2f}"
    )
    print(
        f"Total open PnL:           "
        f"${result['total_open_pnl']:,.2f}"
    )
    print(
        f"Open PnL ratio:           "
        f"{result['open_pnl_ratio']:.1%}"
    )
    print(
        f"Largest-position share:   "
        f"{result['concentration_ratio']:.1%}"
    )
    print(
        f"Median position value:    "
        f"${result['median_position_value']:,.2f}"
    )

    print()
    print("Score breakdown:")
    print(f"  Observation depth:      {result['scan_score']}/10")
    print(f"  Meaningful sample:      {result['sample_score']}/15")
    print(f"  Capital deployed:       {result['capital_score']}/15")
    print(f"  Open PnL evidence:      {result['pnl_score']}/25")
    print(f"  Position consistency:   {result['consistency_score']}/20")
    print(
        f"  Diversification:        "
        f"{result['diversification_score']}/15"
    )


def main() -> None:
    """Calculate, rank, display and store wallet ratings."""

    print()
    print("=" * 96)
    print("POLYMARKET PROVISIONAL WALLET RATING ENGINE v1")
    print("=" * 96)

    create_wallet_rating_table()

    rows = fetch_latest_wallet_positions()
    grouped_wallets = group_positions_by_wallet(rows)

    results = []

    for wallet_data in grouped_wallets.values():
        metrics = calculate_wallet_metrics(wallet_data)
        scored = calculate_wallet_score(metrics)
        results.append(scored)

    results.sort(
        key=lambda result: (
            result["wallet_score"],
            result["meaningful_position_count"],
            result["total_current_value"],
        ),
        reverse=True,
    )

    rows_saved = save_wallet_ratings(results)

    print()
    print(f"Distinct wallets rated: {len(results)}")
    print(f"Rating snapshots saved: {rows_saved}")
    print(
        f"Meaningful position threshold: "
        f"${MINIMUM_MEANINGFUL_POSITION_VALUE:,.2f}"
    )

    for number, result in enumerate(results, start=1):
        display_wallet_rating(number, result)

    print()
    print("=" * 96)
    print("IMPORTANT")
    print("=" * 96)
    print(
        "These are provisional research ratings based on currently "
        "observable open positions."
    )
    print(
        "They are not yet resolved-market accuracy ratings or proof "
        "of repeatable future skill."
    )
    print(
        "The later performance backtester will upgrade these ratings "
        "using resolved outcomes."
    )
    print("=" * 96)


if __name__ == "__main__":
    main()