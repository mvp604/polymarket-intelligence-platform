"""
Polymarket Decision Price Attribution Engine v1.1

Attributes a historical market price to every institutional decision while
strictly preventing look-ahead bias.

Source priority
---------------
1. closing_line_history
2. market_price_history
3. official_wallet_trades
4. official_wallet_activity
5. backtest_results

Only prices observed at or before the institutional decision timestamp are
eligible.

Dry-run mode is the default. Use --apply to persist attribution records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import argparse
import hashlib
import math
import sqlite3
import statistics
import time
import uuid


ENGINE_VERSION = "1.1"

ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = (
    ROOT
    / "database"
    / "polymarket.db"
)

DEFAULT_STAKE = 100.0

DEFAULT_MAX_PRICE_AGE_HOURS = 48.0

TRADE_WINDOW_SECONDS = 1800

EXACT_SOURCE_PRIORITY = {
    "CLOSING_LINE_HISTORY": 1,
    "MARKET_PRICE_HISTORY": 2,
    "OFFICIAL_WALLET_TRADES": 3,
    "OFFICIAL_WALLET_ACTIVITY": 4,
    "BACKTEST_RESULTS": 5,
}


@dataclass(frozen=True)
class DecisionRecord:
    history_id: int
    run_id: str
    opportunity_key: str
    market_id: str
    title: str
    outcome: str
    decision_action: str
    decision_grade: str
    decision_score: float
    confidence: float
    observed_at: str
    observed_epoch: float
    methodology_version: str


@dataclass(frozen=True)
class PriceCandidate:
    source_name: str
    source_row_key: str
    market_id: str
    outcome: str
    price: float
    price_at: str
    price_epoch: float
    match_method: str
    source_priority: int
    sample_count: int
    price_dispersion: float | None


@dataclass(frozen=True)
class AttributionRecord:
    attribution_key: str
    source_history_id: int
    source_run_id: str
    opportunity_key: str
    market_id: str
    title: str
    selected_outcome: str
    decision_action: str
    decision_grade: str
    decision_score: float
    decision_confidence: float
    methodology_version: str
    decision_at: str

    attributed_price: float | None
    price_at: str
    price_age_seconds: float | None
    price_age_hours: float | None
    price_source: str
    source_row_key: str
    match_method: str
    source_priority: int | None
    source_sample_count: int
    price_dispersion: float | None

    attribution_status: str
    attribution_quality: str
    lookahead_safe: int
    stale_price: int

    resolved: int
    actual_result: int | None
    winning_outcome: str
    settlement_price: float | None

    hypothetical_stake: float
    hypothetical_shares: float | None
    hypothetical_settlement_value: float | None
    hypothetical_profit: float | None
    hypothetical_roi: float | None

    avoided_loss_amount: float | None
    avoided_loss_roi: float | None

    calculated_at: str


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def normalize_text(value: Any) -> str:
    return " ".join(
        clean_text(value)
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(result):
        return default

    return result


def optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def valid_price(
    value: Any,
) -> float | None:
    price = optional_float(value)

    if price is None:
        return None

    if not 0 < price < 1:
        return None

    return price


def parse_datetime(
    value: Any,
) -> datetime | None:
    text = clean_text(value)

    if not text:
        return None

    if text.endswith("Z"):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            text
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def datetime_epoch(
    value: Any,
) -> float | None:
    parsed = parse_datetime(value)

    if parsed is None:
        return None

    return parsed.timestamp()


def unix_epoch(
    value: Any,
) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if result <= 0:
        return None

    return result


def stable_key(
    *parts: Any,
) -> str:
    payload = "|".join(
        clean_text(part)
        for part in parts
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def quote_identifier(
    value: str,
) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def require_source_table(
    connection: sqlite3.Connection,
) -> None:
    if not table_exists(
        connection,
        "institutional_decision_history",
    ):
        raise RuntimeError(
            "institutional_decision_history "
            "does not exist."
        )


def create_tables(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS
        decision_price_attributions (
            attribution_key TEXT PRIMARY KEY,

            source_history_id INTEGER NOT NULL,
            source_run_id TEXT NOT NULL,

            opportunity_key TEXT NOT NULL,
            market_id TEXT NOT NULL,
            title TEXT NOT NULL,
            selected_outcome TEXT NOT NULL,

            decision_action TEXT NOT NULL,
            decision_grade TEXT NOT NULL,
            decision_score REAL NOT NULL,
            decision_confidence REAL NOT NULL,
            methodology_version TEXT NOT NULL,
            decision_at TEXT NOT NULL,

            attributed_price REAL,
            price_at TEXT,
            price_age_seconds REAL,
            price_age_hours REAL,

            price_source TEXT
                NOT NULL DEFAULT 'NONE',

            source_row_key TEXT,
            match_method TEXT,

            source_priority INTEGER,
            source_sample_count INTEGER
                NOT NULL DEFAULT 0,

            price_dispersion REAL,

            attribution_status TEXT
                NOT NULL,

            attribution_quality TEXT
                NOT NULL,

            lookahead_safe INTEGER
                NOT NULL DEFAULT 1,

            stale_price INTEGER
                NOT NULL DEFAULT 0,

            resolved INTEGER
                NOT NULL DEFAULT 0,

            actual_result INTEGER,
            winning_outcome TEXT,
            settlement_price REAL,

            hypothetical_stake REAL
                NOT NULL DEFAULT 0,

            hypothetical_shares REAL,
            hypothetical_settlement_value REAL,
            hypothetical_profit REAL,
            hypothetical_roi REAL,

            avoided_loss_amount REAL,
            avoided_loss_roi REAL,

            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                source_history_id,
                methodology_version
            )
        );

        CREATE INDEX IF NOT EXISTS
        idx_decision_price_market
        ON decision_price_attributions(
            market_id,
            selected_outcome,
            decision_at
        );

        CREATE INDEX IF NOT EXISTS
        idx_decision_price_source
        ON decision_price_attributions(
            price_source,
            attribution_status
        );

        CREATE INDEX IF NOT EXISTS
        idx_decision_price_quality
        ON decision_price_attributions(
            attribution_quality,
            stale_price
        );

        CREATE TABLE IF NOT EXISTS
        decision_price_attribution_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            decisions_loaded INTEGER
                NOT NULL DEFAULT 0,

            attributed_decisions INTEGER
                NOT NULL DEFAULT 0,

            unattributed_decisions INTEGER
                NOT NULL DEFAULT 0,

            fresh_attributions INTEGER
                NOT NULL DEFAULT 0,

            stale_attributions INTEGER
                NOT NULL DEFAULT 0,

            resolved_buy_records INTEGER
                NOT NULL DEFAULT 0,

            resolved_avoid_records INTEGER
                NOT NULL DEFAULT 0,

            rows_saved INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,
            status TEXT NOT NULL,
            error_message TEXT
        );
        """
    )


def load_decisions(
    connection: sqlite3.Connection,
    limit: int | None,
) -> list[DecisionRecord]:
    sql = """
        SELECT
            id,
            run_id,
            opportunity_key,
            market_id,
            title,
            outcome,
            decision_action,
            decision_grade,
            decision_score,
            confidence,
            observed_at,
            methodology_version
        FROM institutional_decision_history
        ORDER BY observed_at, id
    """

    parameters: tuple[Any, ...] = ()

    if limit is not None:
        sql += "\nLIMIT ?"
        parameters = (limit,)

    rows = connection.execute(
        sql,
        parameters,
    ).fetchall()

    decisions: list[
        DecisionRecord
    ] = []

    for row in rows:
        epoch = datetime_epoch(
            row["observed_at"]
        )

        if epoch is None:
            continue

        decisions.append(
            DecisionRecord(
                history_id=safe_int(
                    row["id"]
                ),
                run_id=clean_text(
                    row["run_id"]
                ),
                opportunity_key=clean_text(
                    row["opportunity_key"]
                ),
                market_id=clean_text(
                    row["market_id"]
                ),
                title=clean_text(
                    row["title"]
                ),
                outcome=clean_text(
                    row["outcome"]
                ),
                decision_action=clean_text(
                    row["decision_action"]
                ).upper(),
                decision_grade=clean_text(
                    row["decision_grade"]
                ),
                decision_score=safe_float(
                    row["decision_score"]
                ),
                confidence=safe_float(
                    row["confidence"]
                ),
                observed_at=clean_text(
                    row["observed_at"]
                ),
                observed_epoch=epoch,
                methodology_version=clean_text(
                    row["methodology_version"]
                ),
            )
        )

    return decisions


def load_closing_line_candidates(
    connection: sqlite3.Connection,
) -> list[PriceCandidate]:
    if not table_exists(
        connection,
        "closing_line_history",
    ):
        return []

    rows = connection.execute(
        """
        SELECT
            id,
            opportunity_key,
            market_id,
            outcome,
            current_price,
            observed_at
        FROM closing_line_history
        WHERE current_price > 0
          AND current_price < 1
        """
    ).fetchall()

    candidates: list[
        PriceCandidate
    ] = []

    for row in rows:
        epoch = datetime_epoch(
            row["observed_at"]
        )

        price = valid_price(
            row["current_price"]
        )

        if epoch is None or price is None:
            continue

        candidates.append(
            PriceCandidate(
                source_name=(
                    "CLOSING_LINE_HISTORY"
                ),
                source_row_key=(
                    f"closing_line_history:"
                    f"{row['id']}"
                ),
                market_id=clean_text(
                    row["market_id"]
                ),
                outcome=clean_text(
                    row["outcome"]
                ),
                price=price,
                price_at=clean_text(
                    row["observed_at"]
                ),
                price_epoch=epoch,
                match_method=(
                    "OPPORTUNITY_KEY_EXACT"
                ),
                source_priority=1,
                sample_count=1,
                price_dispersion=None,
            )
        )

    return candidates


def load_market_price_candidates(
    connection: sqlite3.Connection,
) -> list[PriceCandidate]:
    if not table_exists(
        connection,
        "market_price_history",
    ):
        return []

    rows = connection.execute(
        """
        SELECT
            id,
            market_id,
            outcome,
            current_price,
            observed_at
        FROM market_price_history
        WHERE current_price > 0
          AND current_price < 1
        """
    ).fetchall()

    candidates: list[
        PriceCandidate
    ] = []

    for row in rows:
        epoch = datetime_epoch(
            row["observed_at"]
        )

        price = valid_price(
            row["current_price"]
        )

        if epoch is None or price is None:
            continue

        candidates.append(
            PriceCandidate(
                source_name=(
                    "MARKET_PRICE_HISTORY"
                ),
                source_row_key=(
                    f"market_price_history:"
                    f"{row['id']}"
                ),
                market_id=clean_text(
                    row["market_id"]
                ),
                outcome=clean_text(
                    row["outcome"]
                ),
                price=price,
                price_at=clean_text(
                    row["observed_at"]
                ),
                price_epoch=epoch,
                match_method=(
                    "MARKET_OUTCOME_EXACT"
                ),
                source_priority=2,
                sample_count=1,
                price_dispersion=None,
            )
        )

    return candidates


def trade_time(
    row: sqlite3.Row,
) -> tuple[str, float] | None:
    raw_timestamp = unix_epoch(
        row["timestamp"]
    )

    if raw_timestamp is not None:
        text = datetime.fromtimestamp(
            raw_timestamp,
            tz=timezone.utc,
        ).isoformat()

        return text, raw_timestamp

    observed_at = clean_text(
        row["observed_at"]
    )

    epoch = datetime_epoch(
        observed_at
    )

    if epoch is None:
        return None

    return observed_at, epoch


def load_trade_rows(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    if not table_exists(
        connection,
        table_name,
    ):
        return []

    key_column = (
        "trade_key"
        if table_name
        == "official_wallet_trades"
        else "activity_key"
    )

    rows = connection.execute(
        f"""
        SELECT
            {quote_identifier(key_column)}
                AS source_key,
            condition_id,
            outcome,
            price,
            timestamp,
            observed_at
        FROM {quote_identifier(table_name)}
        WHERE condition_id IS NOT NULL
          AND outcome IS NOT NULL
          AND price > 0
          AND price < 1
        """
    ).fetchall()

    records: list[
        dict[str, Any]
    ] = []

    for row in rows:
        parsed_time = trade_time(row)

        price = valid_price(
            row["price"]
        )

        if (
            parsed_time is None
            or price is None
        ):
            continue

        records.append(
            {
                "source_key": clean_text(
                    row["source_key"]
                ),
                "market_id": clean_text(
                    row["condition_id"]
                ),
                "outcome": clean_text(
                    row["outcome"]
                ),
                "price": price,
                "price_at": parsed_time[0],
                "price_epoch": parsed_time[1],
            }
        )

    return records


def load_backtest_candidates(
    connection: sqlite3.Connection,
) -> list[PriceCandidate]:
    if not table_exists(
        connection,
        "backtest_results",
    ):
        return []

    rows = connection.execute(
        """
        SELECT
            id,
            market_id,
            selected_outcome,
            entry_price,
            first_signal_at
        FROM backtest_results
        WHERE entry_price > 0
          AND entry_price < 1
        """
    ).fetchall()

    candidates: list[
        PriceCandidate
    ] = []

    for row in rows:
        epoch = datetime_epoch(
            row["first_signal_at"]
        )

        price = valid_price(
            row["entry_price"]
        )

        if epoch is None or price is None:
            continue

        candidates.append(
            PriceCandidate(
                source_name=(
                    "BACKTEST_RESULTS"
                ),
                source_row_key=(
                    f"backtest_results:"
                    f"{row['id']}"
                ),
                market_id=clean_text(
                    row["market_id"]
                ),
                outcome=clean_text(
                    row["selected_outcome"]
                ),
                price=price,
                price_at=clean_text(
                    row["first_signal_at"]
                ),
                price_epoch=epoch,
                match_method=(
                    "LEGACY_BACKTEST_SIGNAL"
                ),
                source_priority=5,
                sample_count=1,
                price_dispersion=None,
            )
        )

    return candidates


def index_candidates(
    candidates: Iterable[
        PriceCandidate
    ],
) -> dict[
    tuple[str, str],
    list[PriceCandidate],
]:
    lookup: dict[
        tuple[str, str],
        list[PriceCandidate],
    ] = {}

    for candidate in candidates:
        key = (
            normalize_text(
                candidate.market_id
            ),
            normalize_text(
                candidate.outcome
            ),
        )

        if not all(key):
            continue

        lookup.setdefault(
            key,
            [],
        ).append(candidate)

    for rows in lookup.values():
        rows.sort(
            key=lambda row: (
                row.price_epoch,
                -row.source_priority,
            )
        )

    return lookup


def group_trade_candidates(
    records: list[dict[str, Any]],
    source_name: str,
    source_priority: int,
) -> dict[
    tuple[str, str],
    list[dict[str, Any]],
]:
    lookup: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = {}

    for record in records:
        key = (
            normalize_text(
                record["market_id"]
            ),
            normalize_text(
                record["outcome"]
            ),
        )

        if not all(key):
            continue

        lookup.setdefault(
            key,
            [],
        ).append(record)

    for rows in lookup.values():
        rows.sort(
            key=lambda row: row[
                "price_epoch"
            ]
        )

    return lookup


def choose_exact_candidate(
    decision: DecisionRecord,
    candidates: list[
        PriceCandidate
    ],
) -> PriceCandidate | None:
    eligible = [
        candidate
        for candidate in candidates
        if (
            candidate.price_epoch
            <= decision.observed_epoch
        )
    ]

    if not eligible:
        return None

    return max(
        eligible,
        key=lambda candidate: (
            candidate.price_epoch,
            -candidate.source_priority,
        ),
    )


def choose_trade_candidate(
    decision: DecisionRecord,
    records: list[dict[str, Any]],
    source_name: str,
    source_priority: int,
) -> PriceCandidate | None:
    eligible = [
        record
        for record in records
        if (
            record["price_epoch"]
            <= decision.observed_epoch
        )
    ]

    if not eligible:
        return None

    latest_epoch = max(
        record["price_epoch"]
        for record in eligible
    )

    window_start = (
        latest_epoch
        - TRADE_WINDOW_SECONDS
    )

    window = [
        record
        for record in eligible
        if (
            record["price_epoch"]
            >= window_start
        )
    ]

    prices = [
        record["price"]
        for record in window
    ]

    median_price = statistics.median(
        prices
    )

    dispersion = (
        statistics.pstdev(prices)
        if len(prices) > 1
        else 0.0
    )

    latest_record = max(
        window,
        key=lambda row: row[
            "price_epoch"
        ],
    )

    source_keys = sorted(
        {
            record["source_key"]
            for record in window
        }
    )

    return PriceCandidate(
        source_name=source_name,
        source_row_key=(
            ",".join(source_keys[:10])
        ),
        market_id=decision.market_id,
        outcome=decision.outcome,
        price=median_price,
        price_at=latest_record[
            "price_at"
        ],
        price_epoch=latest_epoch,
        match_method=(
            "PRE_DECISION_TRADE_MEDIAN_30M"
        ),
        source_priority=source_priority,
        sample_count=len(window),
        price_dispersion=dispersion,
    )


def load_resolution_lookup(
    connection: sqlite3.Connection,
) -> dict[
    tuple[str, str],
    dict[str, Any],
]:
    if not table_exists(
        connection,
        "mapped_market_results",
    ):
        return {}

    rows = connection.execute(
        """
        SELECT
            source_market_id,
            source_outcome,
            resolution_status,
            winning_outcome_name,
            source_outcome_won,
            source_outcome_lost,
            settlement_price,
            match_confidence,
            updated_at
        FROM mapped_market_results
        """
    ).fetchall()

    lookup: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for row in rows:
        key = (
            normalize_text(
                row["source_market_id"]
            ),
            normalize_text(
                row["source_outcome"]
            ),
        )

        if not all(key):
            continue

        won = (
            safe_int(
                row["source_outcome_won"],
                -1,
            )
        )

        lost = (
            safe_int(
                row["source_outcome_lost"],
                -1,
            )
        )

        if won not in {0, 1}:
            if lost in {0, 1}:
                won = 1 - lost
            else:
                continue

        record = {
            "actual_result": won,
            "winning_outcome": clean_text(
                row["winning_outcome_name"]
            ),
            "settlement_price": (
                optional_float(
                    row["settlement_price"]
                )
            ),
            "match_confidence": safe_float(
                row["match_confidence"]
            ),
            "updated_at": clean_text(
                row["updated_at"]
            ),
        }

        existing = lookup.get(key)

        if existing is None:
            lookup[key] = record
            continue

        if (
            record["match_confidence"]
            >= existing[
                "match_confidence"
            ]
        ):
            lookup[key] = record

    return lookup


def attribution_quality(
    candidate: PriceCandidate | None,
    age_hours: float | None,
    max_age_hours: float,
) -> tuple[str, str, int]:
    if candidate is None:
        return (
            "NO_HISTORICAL_PRICE",
            "NONE",
            0,
        )

    if age_hours is None:
        return (
            "INVALID_PRICE_TIME",
            "NONE",
            0,
        )

    if age_hours < 0:
        return (
            "LOOKAHEAD_REJECTED",
            "REJECTED",
            0,
        )

    stale = int(
        age_hours > max_age_hours
    )

    if stale:
        return (
            "ATTRIBUTED_STALE",
            "LOW",
            1,
        )

    if age_hours <= 6:
        if candidate.source_priority <= 2:
            return (
                "ATTRIBUTED",
                "HIGH",
                1,
            )

        if (
            candidate.source_priority
            in {3, 4}
            and candidate.sample_count >= 3
        ):
            return (
                "ATTRIBUTED",
                "HIGH",
                1,
            )

        return (
            "ATTRIBUTED",
            "MEDIUM",
            1,
        )

    if age_hours <= 24:
        if candidate.source_priority <= 2:
            return (
                "ATTRIBUTED",
                "MEDIUM",
                1,
            )

        if (
            candidate.source_priority
            in {3, 4}
            and candidate.sample_count >= 3
        ):
            return (
                "ATTRIBUTED",
                "MEDIUM",
                1,
            )

        return (
            "ATTRIBUTED",
            "LOW",
            1,
        )

    if age_hours <= max_age_hours:
        return (
            "ATTRIBUTED",
            "LOW",
            1,
        )

    return (
        "ATTRIBUTED_STALE",
        "STALE",
        1,
    )


def calculate_financials(
    action: str,
    price: float | None,
    actual_result: int | None,
    stake: float,
) -> dict[str, float | None]:
    result = {
        "shares": None,
        "settlement_value": None,
        "profit": None,
        "roi": None,
        "avoided_loss_amount": None,
        "avoided_loss_roi": None,
    }

    if (
        price is None
        or actual_result is None
        or stake <= 0
    ):
        return result

    shares = stake / price

    settlement_value = (
        shares
        if actual_result == 1
        else 0.0
    )

    profit = (
        settlement_value
        - stake
    )

    roi = (
        profit / stake
        * 100.0
    )

    if action == "BUY":
        result.update(
            {
                "shares": shares,
                "settlement_value": (
                    settlement_value
                ),
                "profit": profit,
                "roi": roi,
            }
        )

    elif action == "AVOID":
        avoided_loss_amount = (
            -profit
            if profit < 0
            else 0.0
        )

        avoided_loss_roi = (
            avoided_loss_amount
            / stake
            * 100.0
        )

        result.update(
            {
                "avoided_loss_amount": (
                    avoided_loss_amount
                ),
                "avoided_loss_roi": (
                    avoided_loss_roi
                ),
            }
        )

    return result


def build_attributions(
    decisions: list[DecisionRecord],
    closing_lookup: dict[
        tuple[str, str],
        list[PriceCandidate],
    ],
    market_price_lookup: dict[
        tuple[str, str],
        list[PriceCandidate],
    ],
    backtest_lookup: dict[
        tuple[str, str],
        list[PriceCandidate],
    ],
    trade_lookup: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ],
    activity_lookup: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ],
    resolution_lookup: dict[
        tuple[str, str],
        dict[str, Any],
    ],
    max_age_hours: float,
    stake: float,
) -> tuple[
    list[AttributionRecord],
    dict[str, int],
]:
    calculated_at = utc_now()

    results: list[
        AttributionRecord
    ] = []

    counts = {
        "attributed": 0,
        "unattributed": 0,
        "fresh": 0,
        "stale": 0,
        "resolved_buy": 0,
        "resolved_avoid": 0,
    }

    for decision in decisions:
        key = (
            normalize_text(
                decision.market_id
            ),
            normalize_text(
                decision.outcome
            ),
        )

        candidate = choose_exact_candidate(
            decision,
            closing_lookup.get(
                key,
                [],
            ),
        )

        if candidate is None:
            candidate = choose_exact_candidate(
                decision,
                market_price_lookup.get(
                    key,
                    [],
                ),
            )

        if candidate is None:
            candidate = choose_trade_candidate(
                decision=decision,
                records=trade_lookup.get(
                    key,
                    [],
                ),
                source_name=(
                    "OFFICIAL_WALLET_TRADES"
                ),
                source_priority=3,
            )

        if candidate is None:
            candidate = choose_trade_candidate(
                decision=decision,
                records=activity_lookup.get(
                    key,
                    [],
                ),
                source_name=(
                    "OFFICIAL_WALLET_ACTIVITY"
                ),
                source_priority=4,
            )

        if candidate is None:
            candidate = choose_exact_candidate(
                decision,
                backtest_lookup.get(
                    key,
                    [],
                ),
            )

        attributed_price: float | None = None
        price_at = ""
        price_age_seconds: float | None = None
        price_age_hours: float | None = None
        price_source = "NONE"
        source_row_key = ""
        match_method = ""
        source_priority: int | None = None
        source_sample_count = 0
        price_dispersion: float | None = None

        if candidate is not None:
            attributed_price = (
                candidate.price
            )

            price_at = candidate.price_at

            price_age_seconds = (
                decision.observed_epoch
                - candidate.price_epoch
            )

            price_age_hours = (
                price_age_seconds
                / 3600.0
            )

            price_source = (
                candidate.source_name
            )

            source_row_key = (
                candidate.source_row_key
            )

            match_method = (
                candidate.match_method
            )

            source_priority = (
                candidate.source_priority
            )

            source_sample_count = (
                candidate.sample_count
            )

            price_dispersion = (
                candidate.price_dispersion
            )

        (
            status,
            quality,
            lookahead_safe,
        ) = attribution_quality(
            candidate=candidate,
            age_hours=price_age_hours,
            max_age_hours=max_age_hours,
        )

        stale_price = int(
            status == "ATTRIBUTED_STALE"
        )

        if candidate is None:
            counts["unattributed"] += 1
        else:
            counts["attributed"] += 1

            if stale_price:
                counts["stale"] += 1
            else:
                counts["fresh"] += 1

        resolution = (
            resolution_lookup.get(key)
        )

        actual_result: int | None = None
        winning_outcome = ""
        settlement_price: float | None = None

        if resolution is not None:
            actual_result = safe_int(
                resolution[
                    "actual_result"
                ]
            )

            winning_outcome = clean_text(
                resolution[
                    "winning_outcome"
                ]
            )

            settlement_price = (
                optional_float(
                    resolution[
                        "settlement_price"
                    ]
                )
            )

        resolved = int(
            actual_result in {0, 1}
        )

        financials = calculate_financials(
            action=decision.decision_action,
            price=attributed_price,
            actual_result=actual_result,
            stake=stake,
        )

        if (
            resolved
            and decision.decision_action
            == "BUY"
        ):
            counts["resolved_buy"] += 1

        if (
            resolved
            and decision.decision_action
            == "AVOID"
        ):
            counts["resolved_avoid"] += 1

        attribution_key = stable_key(
            "decision-price-attribution-v1",
            decision.history_id,
            decision.methodology_version,
        )

        results.append(
            AttributionRecord(
                attribution_key=(
                    attribution_key
                ),
                source_history_id=(
                    decision.history_id
                ),
                source_run_id=(
                    decision.run_id
                ),
                opportunity_key=(
                    decision.opportunity_key
                ),
                market_id=(
                    decision.market_id
                ),
                title=decision.title,
                selected_outcome=(
                    decision.outcome
                ),
                decision_action=(
                    decision.decision_action
                ),
                decision_grade=(
                    decision.decision_grade
                ),
                decision_score=(
                    decision.decision_score
                ),
                decision_confidence=(
                    decision.confidence
                ),
                methodology_version=(
                    decision.methodology_version
                ),
                decision_at=(
                    decision.observed_at
                ),
                attributed_price=(
                    attributed_price
                ),
                price_at=price_at,
                price_age_seconds=(
                    price_age_seconds
                ),
                price_age_hours=(
                    price_age_hours
                ),
                price_source=(
                    price_source
                ),
                source_row_key=(
                    source_row_key
                ),
                match_method=(
                    match_method
                ),
                source_priority=(
                    source_priority
                ),
                source_sample_count=(
                    source_sample_count
                ),
                price_dispersion=(
                    price_dispersion
                ),
                attribution_status=(
                    status
                ),
                attribution_quality=(
                    quality
                ),
                lookahead_safe=(
                    lookahead_safe
                ),
                stale_price=stale_price,
                resolved=resolved,
                actual_result=(
                    actual_result
                ),
                winning_outcome=(
                    winning_outcome
                ),
                settlement_price=(
                    settlement_price
                ),
                hypothetical_stake=stake,
                hypothetical_shares=(
                    financials["shares"]
                ),
                hypothetical_settlement_value=(
                    financials[
                        "settlement_value"
                    ]
                ),
                hypothetical_profit=(
                    financials["profit"]
                ),
                hypothetical_roi=(
                    financials["roi"]
                ),
                avoided_loss_amount=(
                    financials[
                        "avoided_loss_amount"
                    ]
                ),
                avoided_loss_roi=(
                    financials[
                        "avoided_loss_roi"
                    ]
                ),
                calculated_at=(
                    calculated_at
                ),
            )
        )

    return results, counts


def save_attributions(
    connection: sqlite3.Connection,
    records: list[AttributionRecord],
) -> int:
    updated_at = utc_now()

    sql = """
        INSERT INTO
        decision_price_attributions (
            attribution_key,
            source_history_id,
            source_run_id,
            opportunity_key,
            market_id,
            title,
            selected_outcome,
            decision_action,
            decision_grade,
            decision_score,
            decision_confidence,
            methodology_version,
            decision_at,
            attributed_price,
            price_at,
            price_age_seconds,
            price_age_hours,
            price_source,
            source_row_key,
            match_method,
            source_priority,
            source_sample_count,
            price_dispersion,
            attribution_status,
            attribution_quality,
            lookahead_safe,
            stale_price,
            resolved,
            actual_result,
            winning_outcome,
            settlement_price,
            hypothetical_stake,
            hypothetical_shares,
            hypothetical_settlement_value,
            hypothetical_profit,
            hypothetical_roi,
            avoided_loss_amount,
            avoided_loss_roi,
            calculated_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(attribution_key)
        DO UPDATE SET
            attributed_price =
                excluded.attributed_price,
            price_at =
                excluded.price_at,
            price_age_seconds =
                excluded.price_age_seconds,
            price_age_hours =
                excluded.price_age_hours,
            price_source =
                excluded.price_source,
            source_row_key =
                excluded.source_row_key,
            match_method =
                excluded.match_method,
            source_priority =
                excluded.source_priority,
            source_sample_count =
                excluded.source_sample_count,
            price_dispersion =
                excluded.price_dispersion,
            attribution_status =
                excluded.attribution_status,
            attribution_quality =
                excluded.attribution_quality,
            lookahead_safe =
                excluded.lookahead_safe,
            stale_price =
                excluded.stale_price,
            resolved =
                excluded.resolved,
            actual_result =
                excluded.actual_result,
            winning_outcome =
                excluded.winning_outcome,
            settlement_price =
                excluded.settlement_price,
            hypothetical_shares =
                excluded.hypothetical_shares,
            hypothetical_settlement_value =
                excluded.hypothetical_settlement_value,
            hypothetical_profit =
                excluded.hypothetical_profit,
            hypothetical_roi =
                excluded.hypothetical_roi,
            avoided_loss_amount =
                excluded.avoided_loss_amount,
            avoided_loss_roi =
                excluded.avoided_loss_roi,
            calculated_at =
                excluded.calculated_at,
            updated_at =
                excluded.updated_at
    """

    values = [
        (
            row.attribution_key,
            row.source_history_id,
            row.source_run_id,
            row.opportunity_key,
            row.market_id,
            row.title,
            row.selected_outcome,
            row.decision_action,
            row.decision_grade,
            row.decision_score,
            row.decision_confidence,
            row.methodology_version,
            row.decision_at,
            row.attributed_price,
            row.price_at,
            row.price_age_seconds,
            row.price_age_hours,
            row.price_source,
            row.source_row_key,
            row.match_method,
            row.source_priority,
            row.source_sample_count,
            row.price_dispersion,
            row.attribution_status,
            row.attribution_quality,
            row.lookahead_safe,
            row.stale_price,
            row.resolved,
            row.actual_result,
            row.winning_outcome,
            row.settlement_price,
            row.hypothetical_stake,
            row.hypothetical_shares,
            row.hypothetical_settlement_value,
            row.hypothetical_profit,
            row.hypothetical_roi,
            row.avoided_loss_amount,
            row.avoided_loss_roi,
            row.calculated_at,
            updated_at,
        )
        for row in records
    ]

    connection.executemany(
        sql,
        values,
    )

    return len(values)


def save_run_start(
    connection: sqlite3.Connection,
    run_id: str,
    mode: str,
    started_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO
        decision_price_attribution_runs (
            run_id,
            engine_version,
            mode,
            started_at,
            status
        )
        VALUES (?, ?, ?, ?, 'RUNNING')
        """,
        (
            run_id,
            ENGINE_VERSION,
            mode,
            started_at,
        ),
    )


def save_run_complete(
    connection: sqlite3.Connection,
    run_id: str,
    counts: dict[str, int],
    decisions_loaded: int,
    rows_saved: int,
    duration_seconds: float,
) -> None:
    connection.execute(
        """
        UPDATE
        decision_price_attribution_runs
        SET
            completed_at = ?,
            decisions_loaded = ?,
            attributed_decisions = ?,
            unattributed_decisions = ?,
            fresh_attributions = ?,
            stale_attributions = ?,
            resolved_buy_records = ?,
            resolved_avoid_records = ?,
            rows_saved = ?,
            duration_seconds = ?,
            status = 'COMPLETE'
        WHERE run_id = ?
        """,
        (
            utc_now(),
            decisions_loaded,
            counts["attributed"],
            counts["unattributed"],
            counts["fresh"],
            counts["stale"],
            counts["resolved_buy"],
            counts["resolved_avoid"],
            rows_saved,
            duration_seconds,
            run_id,
        ),
    )


def print_summary(
    mode: str,
    run_id: str,
    decisions: list[DecisionRecord],
    records: list[AttributionRecord],
    counts: dict[str, int],
    duration_seconds: float,
    display_limit: int,
) -> None:
    print()
    print("=" * 120)
    print(
        "POLYMARKET DECISION PRICE "
        "ATTRIBUTION ENGINE v1.1"
    )
    print("=" * 120)
    print(f"Database:                   {DATABASE_PATH}")
    print(f"Mode:                       {mode}")
    print(f"Run ID:                     {run_id}")
    print(f"Decisions loaded:           {len(decisions):,}")
    print(
        f"Attributed decisions:       "
        f"{counts['attributed']:,}"
    )
    print(
        f"Unattributed decisions:     "
        f"{counts['unattributed']:,}"
    )
    print(
        f"Fresh / stale:              "
        f"{counts['fresh']:,} / "
        f"{counts['stale']:,}"
    )
    print(
        f"Resolved BUY records:       "
        f"{counts['resolved_buy']:,}"
    )
    print(
        f"Resolved AVOID records:     "
        f"{counts['resolved_avoid']:,}"
    )
    print(
        f"Duration:                   "
        f"{duration_seconds:,.3f}s"
    )
    print("=" * 120)

    source_counts: dict[str, int] = {}

    for row in records:
        source_counts[
            row.price_source
        ] = (
            source_counts.get(
                row.price_source,
                0,
            )
            + 1
        )

    print()
    print("SOURCE COVERAGE")
    print("-" * 120)

    for source, count in sorted(
        source_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print(
            f"{source:<32} "
            f"{count:>6,}"
        )

    attributed = [
        row
        for row in records
        if row.attributed_price
        is not None
    ]

    if attributed:
        print()
        print("SAMPLE ATTRIBUTIONS")
        print("-" * 120)

        ordered = sorted(
            attributed,
            key=lambda row: (
                row.price_age_seconds
                if row.price_age_seconds
                is not None
                else float("inf"),
                row.title,
            ),
        )

        for index, row in enumerate(
            ordered[:display_limit],
            start=1,
        ):
            print(
                f"{index:>3}. "
                f"{row.decision_action:<6} "
                f"price={row.attributed_price:>7.4f} "
                f"age={row.price_age_hours:>8.2f}h "
                f"quality={row.attribution_quality:<6} "
                f"source={row.price_source}"
            )
            print(
                f"     {row.title} ? "
                f"{row.selected_outcome}"
            )
            print(
                f"     decision={row.decision_at} "
                f"price_at={row.price_at}"
            )

    print()
    print("=" * 120)

    if mode == "DRY RUN":
        print(
            "Dry run complete. No attribution "
            "records were saved."
        )
        print(
            "Review coverage and price ages "
            "before running --apply."
        )
    else:
        print(
            "Decision price attribution "
            "records were saved successfully."
        )

    print(
        "Every accepted price was timestamped "
        "at or before its decision."
    )
    print(
        "Stale prices remain explicitly flagged "
        "and should not be used for precise ROI."
    )
    print("=" * 120)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Attribute historical market prices "
            "to institutional decisions."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Save attribution records and "
            "run metadata."
        ),
    )

    parser.add_argument(
        "--decision-limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--max-price-age-hours",
        type=float,
        default=(
            DEFAULT_MAX_PRICE_AGE_HOURS
        ),
    )

    parser.add_argument(
        "--stake",
        type=float,
        default=DEFAULT_STAKE,
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=15,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if (
        args.decision_limit
        is not None
        and args.decision_limit <= 0
    ):
        raise SystemExit(
            "--decision-limit must be "
            "greater than zero."
        )

    if args.max_price_age_hours <= 0:
        raise SystemExit(
            "--max-price-age-hours must be "
            "greater than zero."
        )

    if args.stake <= 0:
        raise SystemExit(
            "--stake must be greater than zero."
        )

    if args.display_limit <= 0:
        raise SystemExit(
            "--display-limit must be "
            "greater than zero."
        )

    started_clock = time.perf_counter()
    started_at = utc_now()
    run_id = uuid.uuid4().hex

    mode = (
        "APPLY"
        if args.apply
        else "DRY RUN"
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        require_source_table(
            connection
        )

        if args.apply:
            create_tables(
                connection
            )

            save_run_start(
                connection,
                run_id,
                mode,
                started_at,
            )

            connection.commit()

        decisions = load_decisions(
            connection,
            args.decision_limit,
        )

        closing_lookup = index_candidates(
            load_closing_line_candidates(
                connection
            )
        )

        market_price_lookup = (
            index_candidates(
                load_market_price_candidates(
                    connection
                )
            )
        )

        backtest_lookup = index_candidates(
            load_backtest_candidates(
                connection
            )
        )

        trade_lookup = (
            group_trade_candidates(
                load_trade_rows(
                    connection,
                    "official_wallet_trades",
                ),
                "OFFICIAL_WALLET_TRADES",
                3,
            )
        )

        activity_lookup = (
            group_trade_candidates(
                load_trade_rows(
                    connection,
                    "official_wallet_activity",
                ),
                "OFFICIAL_WALLET_ACTIVITY",
                4,
            )
        )

        resolution_lookup = (
            load_resolution_lookup(
                connection
            )
        )

        records, counts = (
            build_attributions(
                decisions=decisions,
                closing_lookup=closing_lookup,
                market_price_lookup=(
                    market_price_lookup
                ),
                backtest_lookup=(
                    backtest_lookup
                ),
                trade_lookup=trade_lookup,
                activity_lookup=(
                    activity_lookup
                ),
                resolution_lookup=(
                    resolution_lookup
                ),
                max_age_hours=(
                    args.max_price_age_hours
                ),
                stake=args.stake,
            )
        )

        rows_saved = 0

        if args.apply:
            rows_saved = save_attributions(
                connection,
                records,
            )

            duration_seconds = (
                time.perf_counter()
                - started_clock
            )

            save_run_complete(
                connection=connection,
                run_id=run_id,
                counts=counts,
                decisions_loaded=(
                    len(decisions)
                ),
                rows_saved=rows_saved,
                duration_seconds=(
                    duration_seconds
                ),
            )

            connection.commit()
        else:
            duration_seconds = (
                time.perf_counter()
                - started_clock
            )

        print_summary(
            mode=mode,
            run_id=run_id,
            decisions=decisions,
            records=records,
            counts=counts,
            duration_seconds=(
                duration_seconds
            ),
            display_limit=(
                args.display_limit
            ),
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
