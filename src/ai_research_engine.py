from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


DATABASE_PATH = Path("database/polymarket.db")
REPORTS_DIRECTORY = Path("reports")

MAX_SIGNALS = 10
MAX_WALLETS_PER_SIGNAL = 8


def connect_database() -> sqlite3.Connection:
    """Open the local Polymarket SQLite database."""

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


def shorten_wallet(wallet: str) -> str:
    """Shorten a wallet address for reports."""

    if len(wallet) <= 16:
        return wallet

    return f"{wallet[:10]}...{wallet[-8:]}"


def fetch_latest_consensus_signals() -> list[dict[str, Any]]:
    """
    Retrieve the newest consensus snapshot for every market/outcome.

    Older snapshots remain in SQLite for trend analysis but are excluded
    from the current AI report.
    """

    connection = connect_database()

    try:
        query = """
            WITH latest_history AS (
                SELECT
                    market_id,
                    LOWER(TRIM(outcome)) AS normalized_outcome,
                    MAX(id) AS latest_id
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
                history.combined_shares,
                history.combined_value,
                history.combined_pnl,
                history.conviction_score,
                history.conviction_grade,
                history.average_entry_price,
                history.average_current_price,
                history.observed_price_move,
                history.scanned_at
            FROM consensus_history AS history
            INNER JOIN latest_history AS latest
                ON history.id = latest.latest_id
            ORDER BY
                history.conviction_score DESC,
                history.wallet_count DESC,
                history.combined_value DESC
            LIMIT ?
        """

        rows = connection.execute(
            query,
            (MAX_SIGNALS,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def fetch_latest_wallet_ratings() -> dict[str, dict[str, Any]]:
    """Retrieve the latest rating snapshot for each wallet."""

    connection = connect_database()

    try:
        query = """
            WITH latest_ratings AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_id
                FROM wallet_rating_history
                GROUP BY wallet
            )
            SELECT
                rating.wallet,
                rating.wallet_score,
                rating.wallet_grade,
                rating.meaningful_position_count,
                rating.profitable_position_rate,
                rating.total_current_value,
                rating.total_open_pnl,
                rating.open_pnl_ratio,
                rating.concentration_ratio,
                rating.rated_at
            FROM wallet_rating_history AS rating
            INNER JOIN latest_ratings AS latest
                ON rating.id = latest.latest_id
        """

        rows = connection.execute(query).fetchall()

        ratings: dict[str, dict[str, Any]] = {}

        for row in rows:
            wallet = str(row["wallet"] or "").strip().lower()

            if wallet:
                ratings[wallet] = dict(row)

        return ratings

    finally:
        connection.close()


def fetch_latest_positions_for_signal(
    market_id: str,
    outcome: str,
) -> list[dict[str, Any]]:
    """Retrieve supporting latest wallet positions for one signal."""

    connection = connect_database()

    try:
        query = """
            WITH latest_scans AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_scan_id
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT
                position.wallet,
                position.shares,
                position.average_price,
                position.current_price,
                position.current_value,
                position.cash_pnl,
                position.percent_pnl
            FROM positions AS position
            INNER JOIN latest_scans AS latest
                ON position.wallet = latest.wallet
               AND position.scan_id = latest.latest_scan_id
            WHERE
                position.market_id = ?
                AND LOWER(TRIM(position.outcome)) =
                    LOWER(TRIM(?))
            ORDER BY position.current_value DESC
            LIMIT ?
        """

        rows = connection.execute(
            query,
            (
                market_id,
                outcome,
                MAX_WALLETS_PER_SIGNAL,
            ),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def fetch_backtest_status(
    market_id: str,
    outcome: str,
) -> dict[str, Any] | None:
    """Retrieve the newest backtest status for one signal."""

    connection = connect_database()

    try:
        row = connection.execute(
            """
            SELECT
                winning_outcome,
                entry_price,
                hypothetical_profit,
                hypothetical_return_pct,
                result_status,
                evaluated_at
            FROM backtest_results
            WHERE
                market_id = ?
                AND LOWER(TRIM(selected_outcome)) =
                    LOWER(TRIM(?))
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                market_id,
                outcome,
            ),
        ).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def fetch_history_summary(
    market_id: str,
    outcome: str,
) -> dict[str, Any]:
    """Summarize historical consensus development for one signal."""

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT
                wallet_count,
                combined_value,
                combined_pnl,
                conviction_score,
                average_current_price,
                scanned_at
            FROM consensus_history
            WHERE
                market_id = ?
                AND LOWER(TRIM(outcome)) =
                    LOWER(TRIM(?))
            ORDER BY id ASC
            """,
            (
                market_id,
                outcome,
            ),
        ).fetchall()

    finally:
        connection.close()

    if not rows:
        return {
            "snapshot_count": 0,
            "trend": "NO HISTORY",
        }

    first = rows[0]
    latest = rows[-1]

    score_change = (
        safe_float(latest["conviction_score"])
        - safe_float(first["conviction_score"])
    )

    wallet_change = (
        safe_int(latest["wallet_count"])
        - safe_int(first["wallet_count"])
    )

    value_change = (
        safe_float(latest["combined_value"])
        - safe_float(first["combined_value"])
    )

    if len(rows) == 1:
        trend = "NEW"
    elif score_change >= 5 or wallet_change > 0 or value_change > 50_000:
        trend = "BUILDING"
    elif score_change <= -5 or wallet_change < 0 or value_change < -50_000:
        trend = "WEAKENING"
    else:
        trend = "STABLE"

    return {
        "snapshot_count": len(rows),
        "trend": trend,
        "first_score": safe_float(first["conviction_score"]),
        "latest_score": safe_float(latest["conviction_score"]),
        "score_change": score_change,
        "first_wallet_count": safe_int(first["wallet_count"]),
        "latest_wallet_count": safe_int(latest["wallet_count"]),
        "wallet_change": wallet_change,
        "first_combined_value": safe_float(first["combined_value"]),
        "latest_combined_value": safe_float(latest["combined_value"]),
        "combined_value_change": value_change,
        "first_price": safe_float(first["average_current_price"]),
        "latest_price": safe_float(latest["average_current_price"]),
        "first_scanned_at": str(first["scanned_at"]),
        "latest_scanned_at": str(latest["scanned_at"]),
    }


def build_signal_package(
    signals: list[dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Combine consensus, history, wallets and backtest evidence."""

    packages: list[dict[str, Any]] = []

    for rank, signal in enumerate(signals, start=1):
        market_id = str(signal["market_id"])
        outcome = str(signal["outcome"])

        supporting_positions = fetch_latest_positions_for_signal(
            market_id=market_id,
            outcome=outcome,
        )

        supporting_wallets: list[dict[str, Any]] = []

        for position in supporting_positions:
            wallet = str(position["wallet"] or "").strip().lower()
            rating = ratings.get(wallet, {})

            supporting_wallets.append(
                {
                    "wallet": shorten_wallet(wallet),
                    "wallet_score": safe_float(
                        rating.get("wallet_score")
                    ),
                    "wallet_grade": str(
                        rating.get("wallet_grade")
                        or "UNRATED"
                    ),
                    "meaningful_position_count": safe_int(
                        rating.get("meaningful_position_count")
                    ),
                    "profitable_position_rate": safe_float(
                        rating.get("profitable_position_rate")
                    ),
                    "wallet_open_pnl_ratio": safe_float(
                        rating.get("open_pnl_ratio")
                    ),
                    "position_value": safe_float(
                        position.get("current_value")
                    ),
                    "position_cash_pnl": safe_float(
                        position.get("cash_pnl")
                    ),
                    "average_entry_price": safe_float(
                        position.get("average_price")
                    ),
                    "current_price": safe_float(
                        position.get("current_price")
                    ),
                }
            )

        rated_scores = [
            wallet["wallet_score"]
            for wallet in supporting_wallets
            if wallet["wallet_score"] > 0
        ]

        average_wallet_score = (
            sum(rated_scores) / len(rated_scores)
            if rated_scores
            else 0.0
        )

        history = fetch_history_summary(
            market_id=market_id,
            outcome=outcome,
        )

        backtest = fetch_backtest_status(
            market_id=market_id,
            outcome=outcome,
        )

        current_price = safe_float(
            signal.get("average_current_price")
        )

        price_move = safe_float(
            signal.get("observed_price_move")
        )

        chase_risk = (
            "HIGH"
            if abs(price_move) >= 0.10 or current_price >= 0.90
            else "MEDIUM"
            if abs(price_move) >= 0.05 or current_price >= 0.75
            else "LOW"
        )

        packages.append(
            {
                "rank": rank,
                "market_id": market_id,
                "title": signal["title"],
                "outcome": outcome,
                "wallet_count": safe_int(signal["wallet_count"]),
                "combined_shares": safe_float(
                    signal["combined_shares"]
                ),
                "combined_value": safe_float(
                    signal["combined_value"]
                ),
                "combined_pnl": safe_float(
                    signal["combined_pnl"]
                ),
                "conviction_score": safe_float(
                    signal["conviction_score"]
                ),
                "conviction_grade": signal["conviction_grade"],
                "average_entry_price": safe_float(
                    signal["average_entry_price"]
                ),
                "average_current_price": current_price,
                "observed_price_move": price_move,
                "average_wallet_score": average_wallet_score,
                "chase_risk": chase_risk,
                "history": history,
                "backtest": backtest,
                "supporting_wallets": supporting_wallets,
            }
        )

    return packages


def build_prompt(
    signal_packages: list[dict[str, Any]],
) -> str:
    """Create the evidence-grounded AI research prompt."""

    evidence_json = json.dumps(
        signal_packages,
        indent=2,
    )

    return f"""
You are the senior research analyst for a Polymarket smart-money
intelligence platform.

Analyze only the supplied evidence. Do not invent news, injuries,
lineups, election facts, schedules, market rules, or external context.

The deterministic engines already calculated the numbers. Your role is
to explain, compare, prioritize and identify risk. Do not override the
database evidence with unsupported assumptions.

Core principles:

1. Consensus is confirmation, not automatic value.
2. A high current price may mean the edge is already gone.
3. Open PnL is not the same as proven lifetime skill.
4. Wallet ratings are provisional until resolved-market performance
   becomes available.
5. Pending backtests provide no proof of predictive accuracy.
6. Clearly distinguish current evidence from historical validation.
7. Recommend PASS or MONITOR when evidence is insufficient.
8. Never promise a win or guaranteed return.
9. Do not tell the user how much money to wager.
10. Treat signals near 1.00 as potentially stale, resolved or too late.

Produce a professional report with exactly these sections:

# Executive Summary

State:
- number of signals reviewed;
- strongest current research candidate;
- whether the board is strong, mixed, weak or unvalidated;
- the most important limitation.

# Ranked Research Board

For every signal, include:

## Rank. Market title — Selected outcome

- Research classification:
  RESEARCH / MONITOR / TOO LATE / INSUFFICIENT EVIDENCE / PASS
- Conviction score and grade
- Wallet agreement
- Average supporting-wallet score
- Capital committed
- Current price
- Price movement
- Trend
- Backtest status
- Chase risk
- Why it ranks here
- Key risk
- Evidence needed before acting

Do not call something RESEARCH merely because its conviction score is
high. Penalize stale pricing, weak wallet evidence, pending backtests,
single-snapshot history and concentrated support.

# Cross-Signal Comparison

Compare the strongest three signals. Explain which has:
- best wallet breadth;
- best wallet quality;
- most capital;
- best entry timing;
- greatest chase risk;
- strongest historical confirmation.

# Risk Flags

List material issues such as:
- price near 1.00;
- only two agreeing wallets;
- provisional wallet scores;
- no resolved backtest sample;
- weakening conviction;
- large price movement;
- market lookup failure;
- stale or potentially resolved sports markets.

# Final Research Classification

Create five lists:

- Research Now
- Monitor
- Too Late
- Insufficient Evidence
- Pass

Use only the supplied signals.

# Data Limitations

State clearly that this is research support, not financial advice,
and that current backtesting evidence may be insufficient.

Here is the database evidence:

{evidence_json}
""".strip()


def call_openai(
    prompt: str,
) -> str:
    """Send the evidence package to OpenAI."""

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY was not found in .env."
        )

    if not model:
        raise RuntimeError(
            "OPENAI_MODEL was not found in .env."
        )

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        instructions=(
            "Write a disciplined, evidence-grounded Polymarket "
            "research report. Never invent missing facts."
        ),
        input=prompt,
    )

    report = response.output_text.strip()

    if not report:
        raise RuntimeError(
            "OpenAI returned an empty report."
        )

    return report


def save_report(
    report: str,
    signal_packages: list[dict[str, Any]],
) -> Path:
    """Save the AI report and its supporting evidence."""

    REPORTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    report_path = REPORTS_DIRECTORY / (
        f"ai_research_report_{timestamp}.md"
    )

    evidence_path = REPORTS_DIRECTORY / (
        f"ai_research_evidence_{timestamp}.json"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    evidence_path.write_text(
        json.dumps(signal_packages, indent=2),
        encoding="utf-8",
    )

    return report_path


def main() -> None:
    """Generate the AI smart-money research report."""

    print()
    print("=" * 100)
    print("POLYMARKET AI RESEARCH ENGINE v1")
    print("=" * 100)

    load_dotenv()

    model = os.getenv("OPENAI_MODEL", "").strip()

    print(f"OpenAI model: {model or 'NOT CONFIGURED'}")

    signals = fetch_latest_consensus_signals()
    ratings = fetch_latest_wallet_ratings()

    print(f"Latest consensus signals loaded: {len(signals)}")
    print(f"Latest wallet ratings loaded:    {len(ratings)}")

    if not signals:
        print()
        print("No consensus signals are available.")
        print(
            "Run the conviction engine before generating "
            "an AI report."
        )
        return

    signal_packages = build_signal_package(
        signals=signals,
        ratings=ratings,
    )

    print(
        f"Evidence packages prepared:      "
        f"{len(signal_packages)}"
    )

    prompt = build_prompt(signal_packages)

    print()
    print("Sending evidence to OpenAI...")

    try:
        report = call_openai(prompt)

    except Exception as error:
        print()
        print("AI research report generation failed.")
        print(f"Error type: {type(error).__name__}")
        print(f"Details: {error}")
        return

    report_path = save_report(
        report=report,
        signal_packages=signal_packages,
    )

    print()
    print("=" * 100)
    print("AI RESEARCH REPORT")
    print("=" * 100)
    print()
    print(report)

    print()
    print("=" * 100)
    print("REPORT SAVED")
    print("=" * 100)
    print(f"Location: {report_path}")
    print("=" * 100)


if __name__ == "__main__":
    main()