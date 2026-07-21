from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

DATABASE_BUSY_TIMEOUT_MS = 30_000
DEFAULT_RETENTION_DAYS = 90
DEFAULT_DISPLAY_LIMIT = 30

LOOKBACK_WINDOWS = {
    "move_5m": 5 * 60,
    "move_15m": 15 * 60,
    "move_1h": 60 * 60,
    "move_6h": 6 * 60 * 60,
    "move_24h": 24 * 60 * 60,
}

INACTIVE_STATUSES = {
    "resolved",
    "closed",
    "ended",
    "ended_unconfirmed",
}


# =============================================================================
# BASIC HELPERS
# =============================================================================


def configure_utf8_output() -> None:
    """Configure Windows terminal output safely."""

    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except (AttributeError, OSError):
        pass

    try:
        sys.stderr.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except (AttributeError, OSError):
        pass


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC timestamp as ISO text."""

    return utc_now().isoformat()


def parse_datetime(value: Any) -> datetime | None:
    """Parse ISO-style datetime text safely."""

    text = str(value or "").strip()

    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(timezone.utc)


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Convert a value into a float safely."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Convert a value into an integer safely."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clean_text(value: Any) -> str:
    """Return trimmed text."""

    return str(value or "").strip()


def normalize_text(value: Any) -> str:
    """Normalize text for matching."""

    return clean_text(value).casefold()


def normalize_market_id(value: Any) -> str:
    """Normalize a Polymarket condition ID."""

    return clean_text(value).lower()


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """Restrict a value to a fixed range."""

    return max(
        minimum,
        min(value, maximum),
    )


def format_price(value: Any) -> str:
    """Format a probability price."""

    return f"{safe_float(value):.4f}"


def format_signed_move(value: Any) -> str:
    """Format a signed probability-point movement."""

    return f"{safe_float(value):+.4f}"


def format_percentage(value: Any) -> str:
    """Format a decimal ratio as a percentage."""

    return f"{safe_float(value):+.1%}"


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
    """Open the main platform database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        f"PRAGMA busy_timeout = "
        f"{DATABASE_BUSY_TIMEOUT_MS}"
    )

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Return True when a table exists."""

    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def table_row_count(
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    """Return a table row count."""

    if not table_exists(
        connection,
        table_name,
    ):
        return 0

    row = connection.execute(
        f'SELECT COUNT(*) AS total '
        f'FROM "{table_name}"'
    ).fetchone()

    return safe_int(
        row["total"] if row else 0
    )


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_price_history_tables() -> None:
    """Create price snapshot, metric and run tables."""

    connection = connect_database()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT,
                market_type TEXT,
                category TEXT,
                sport TEXT,
                league TEXT,

                current_price REAL NOT NULL,
                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                source_updated_at TEXT,
                observed_at TEXT NOT NULL,

                UNIQUE(
                    market_id,
                    observed_at
                )
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_market_price_history_market_time
            ON market_price_history(
                market_id,
                observed_at DESC
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_market_price_history_observed
            ON market_price_history(
                observed_at DESC
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_price_metrics (
                market_id TEXT PRIMARY KEY,

                title TEXT NOT NULL,
                outcome TEXT,
                current_price REAL NOT NULL,

                price_5m_ago REAL,
                price_15m_ago REAL,
                price_1h_ago REAL,
                price_6h_ago REAL,
                price_24h_ago REAL,

                move_5m REAL,
                move_15m REAL,
                move_1h REAL,
                move_6h REAL,
                move_24h REAL,

                move_5m_pct REAL,
                move_15m_pct REAL,
                move_1h_pct REAL,
                move_6h_pct REAL,
                move_24h_pct REAL,

                high_24h REAL,
                low_24h REAL,
                range_24h REAL,

                snapshot_count_24h INTEGER
                    NOT NULL DEFAULT 0,

                steam_score REAL
                    NOT NULL DEFAULT 0,

                reversal_score REAL
                    NOT NULL DEFAULT 0,

                volatility_score REAL
                    NOT NULL DEFAULT 0,

                move_status TEXT
                    NOT NULL DEFAULT 'INSUFFICIENT_DATA',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                latest_observed_at TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_market_price_metrics_steam
            ON market_price_metrics(
                steam_score DESC
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_market_price_metrics_status
            ON market_price_metrics(
                move_status,
                steam_score DESC
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                markets_seen INTEGER
                    NOT NULL DEFAULT 0,

                snapshots_inserted INTEGER
                    NOT NULL DEFAULT 0,

                snapshots_skipped INTEGER
                    NOT NULL DEFAULT 0,

                metrics_updated INTEGER
                    NOT NULL DEFAULT 0,

                rows_deleted INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
            """
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# MARKET LOADING
# =============================================================================


def classify_market_type(
    title: str,
) -> str:
    """Classify a market from its title."""

    normalized = normalize_text(title)

    if "exact score" in normalized:
        return "EXACT_SCORE"

    if "corners" in normalized:
        return "CORNERS"

    if (
        "o/u" in normalized
        or "over/under" in normalized
    ):
        return "TOTAL"

    if (
        "both teams to score"
        in normalized
    ):
        return "BTTS"

    if "spread:" in normalized:
        return "SPREAD"

    if "team to advance" in normalized:
        return "ADVANCE"

    if "halftime" in normalized:
        return "HALFTIME"

    if (
        "world cup" in normalized
        and "win the" in normalized
    ):
        return "FUTURE"

    if (
        normalized.startswith("will ")
        and " win on " in normalized
    ):
        return "MONEYLINE"

    if " vs." in normalized or " vs " in normalized:
        return "MATCH"

    return "OTHER"


def extract_price_from_json(
    outcome_prices_json: Any,
    outcome: str,
) -> float | None:
    """Extract an outcome price from stored JSON when possible."""

    text = clean_text(
        outcome_prices_json
    )

    if not text:
        return None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    normalized_outcome = normalize_text(
        outcome
    )

    if isinstance(payload, dict):
        for key, value in payload.items():
            if normalize_text(key) == normalized_outcome:
                price = safe_float(
                    value,
                    default=-1,
                )

                if 0 <= price <= 1:
                    return price

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue

            item_outcome = normalize_text(
                item.get("outcome")
                or item.get("name")
                or item.get("label")
            )

            if item_outcome != normalized_outcome:
                continue

            price = safe_float(
                item.get("price")
                or item.get("value"),
                default=-1,
            )

            if 0 <= price <= 1:
                return price

    return None


def load_current_markets() -> list[dict[str, Any]]:
    """Load markets with valid current prices."""

    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "market_metadata",
        ):
            raise RuntimeError(
                "market_metadata table does not exist."
            )

        rows = connection.execute(
            """
            SELECT *
            FROM market_metadata
            ORDER BY title
            """
        ).fetchall()

    finally:
        connection.close()

    markets: list[dict[str, Any]] = []

    for row in rows:
        record = dict(row)

        market_id = normalize_market_id(
            record.get("market_id")
        )

        title = clean_text(
            record.get("title")
        )

        outcome = clean_text(
            record.get("outcome")
        )

        if not market_id or not title:
            continue

        lifecycle_status = clean_text(
            record.get(
                "lifecycle_status"
            )
        )

        if normalize_text(
            lifecycle_status
        ) in INACTIVE_STATUSES:
            continue

        current_price = safe_float(
            record.get("current_price"),
            default=-1,
        )

        if not 0 <= current_price <= 1:
            extracted = extract_price_from_json(
                record.get(
                    "outcome_prices_json"
                ),
                outcome,
            )

            if extracted is None:
                continue

            current_price = extracted

        markets.append(
            {
                "market_id": market_id,
                "title": title,
                "outcome": outcome,
                "market_type": (
                    classify_market_type(
                        title
                    )
                ),
                "category": clean_text(
                    record.get("category")
                ),
                "sport": clean_text(
                    record.get("sport")
                ),
                "league": clean_text(
                    record.get("league")
                ),
                "current_price": (
                    current_price
                ),
                "lifecycle_status": (
                    lifecycle_status
                ),
                "seconds_to_start": (
                    record.get(
                        "seconds_to_start"
                    )
                ),
                "source_updated_at": (
                    clean_text(
                        record.get(
                            "source_updated_at"
                        )
                    )
                ),
            }
        )

    return markets


# =============================================================================
# SNAPSHOTS
# =============================================================================


def insert_snapshots(
    markets: list[dict[str, Any]],
    observed_at: str,
) -> tuple[int, int]:
    """Insert one snapshot for every valid market."""

    connection = connect_database()

    inserted = 0
    skipped = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for market in markets:
            try:
                connection.execute(
                    """
                    INSERT INTO market_price_history (
                        market_id,
                        title,
                        outcome,
                        market_type,
                        category,
                        sport,
                        league,
                        current_price,
                        lifecycle_status,
                        seconds_to_start,
                        source_updated_at,
                        observed_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        market["market_id"],
                        market["title"],
                        market["outcome"],
                        market["market_type"],
                        market["category"],
                        market["sport"],
                        market["league"],
                        market["current_price"],
                        market[
                            "lifecycle_status"
                        ],
                        market[
                            "seconds_to_start"
                        ],
                        market[
                            "source_updated_at"
                        ],
                        observed_at,
                    ),
                )

                inserted += 1

            except sqlite3.IntegrityError:
                skipped += 1

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return inserted, skipped


# =============================================================================
# HISTORICAL PRICE LOOKUPS
# =============================================================================


def nearest_historical_price(
    connection: sqlite3.Connection,
    market_id: str,
    target_time: datetime,
    tolerance_seconds: int,
) -> tuple[float | None, str | None]:
    """
    Return the closest price at or before the target time.

    The tolerance prevents very old snapshots from being used as if
    they represented the requested lookback window.
    """

    row = connection.execute(
        """
        SELECT
            current_price,
            observed_at
        FROM market_price_history
        WHERE market_id = ?
          AND observed_at <= ?
        ORDER BY observed_at DESC
        LIMIT 1
        """,
        (
            market_id,
            target_time.isoformat(),
        ),
    ).fetchone()

    if row is None:
        return None, None

    observed = parse_datetime(
        row["observed_at"]
    )

    if observed is None:
        return None, None

    age_from_target = abs(
        (
            target_time - observed
        ).total_seconds()
    )

    if age_from_target > tolerance_seconds:
        return None, None

    return (
        safe_float(
            row["current_price"]
        ),
        clean_text(
            row["observed_at"]
        ),
    )


def percentage_move(
    current_price: float,
    historical_price: float | None,
) -> float | None:
    """Calculate relative percentage movement."""

    if (
        historical_price is None
        or historical_price <= 0
    ):
        return None

    return (
        current_price
        - historical_price
    ) / historical_price


# =============================================================================
# MOVEMENT SIGNALS
# =============================================================================


def calculate_steam_score(
    move_5m: float | None,
    move_15m: float | None,
    move_1h: float | None,
    move_6h: float | None,
) -> float:
    """Score directional upward market pressure."""

    score = 0.0

    windows = [
        (
            move_5m,
            0.015,
            20.0,
        ),
        (
            move_15m,
            0.025,
            25.0,
        ),
        (
            move_1h,
            0.050,
            30.0,
        ),
        (
            move_6h,
            0.100,
            25.0,
        ),
    ]

    for move, full_move, weight in windows:
        if move is None:
            continue

        if move <= 0:
            continue

        score += clamp(
            move / full_move,
            0.0,
            1.0,
        ) * weight

    return clamp(score)


def calculate_reversal_score(
    move_5m: float | None,
    move_15m: float | None,
    move_1h: float | None,
    move_6h: float | None,
) -> float:
    """Score short-term reversal against a longer move."""

    score = 0.0

    if (
        move_1h is not None
        and move_5m is not None
        and move_1h > 0.03
        and move_5m < -0.01
    ):
        score += 45.0

    if (
        move_6h is not None
        and move_15m is not None
        and move_6h > 0.06
        and move_15m < -0.02
    ):
        score += 35.0

    if (
        move_1h is not None
        and move_15m is not None
        and move_1h < -0.03
        and move_15m > 0.02
    ):
        score += 35.0

    return clamp(score)


def calculate_volatility_score(
    prices_24h: list[float],
) -> float:
    """Estimate volatility from observed prices."""

    if len(prices_24h) < 2:
        return 0.0

    average_price = sum(
        prices_24h
    ) / len(prices_24h)

    if average_price <= 0:
        return 0.0

    variance = sum(
        (
            price - average_price
        )
        ** 2
        for price in prices_24h
    ) / len(prices_24h)

    standard_deviation = math.sqrt(
        variance
    )

    coefficient = (
        standard_deviation
        / average_price
    )

    return clamp(
        coefficient
        / 0.15
        * 100.0
    )


def classify_move_status(
    snapshot_count: int,
    steam_score: float,
    reversal_score: float,
    move_1h: float | None,
    move_24h: float | None,
) -> str:
    """Classify current price behavior."""

    if snapshot_count < 2:
        return "INSUFFICIENT_DATA"

    if reversal_score >= 60:
        return "STRONG_REVERSAL"

    if reversal_score >= 35:
        return "REVERSAL_WATCH"

    if steam_score >= 75:
        return "STRONG_STEAM"

    if steam_score >= 50:
        return "STEAM"

    if (
        move_1h is not None
        and move_1h <= -0.05
    ):
        return "SHARP_DECLINE"

    if (
        move_24h is not None
        and move_24h <= -0.10
    ):
        return "BEARISH"

    if (
        move_1h is not None
        and abs(move_1h) <= 0.01
    ):
        return "STABLE"

    return "NORMAL"


# =============================================================================
# METRIC CALCULATION
# =============================================================================


@dataclass
class MetricResult:
    market_id: str
    title: str
    outcome: str
    current_price: float

    price_5m_ago: float | None
    price_15m_ago: float | None
    price_1h_ago: float | None
    price_6h_ago: float | None
    price_24h_ago: float | None

    move_5m: float | None
    move_15m: float | None
    move_1h: float | None
    move_6h: float | None
    move_24h: float | None

    move_5m_pct: float | None
    move_15m_pct: float | None
    move_1h_pct: float | None
    move_6h_pct: float | None
    move_24h_pct: float | None

    high_24h: float
    low_24h: float
    range_24h: float
    snapshot_count_24h: int

    steam_score: float
    reversal_score: float
    volatility_score: float
    move_status: str

    lifecycle_status: str
    seconds_to_start: int | None
    latest_observed_at: str
    calculated_at: str


def calculate_metric_for_market(
    connection: sqlite3.Connection,
    market: dict[str, Any],
    calculated_at: datetime,
) -> MetricResult:
    """Calculate all price metrics for one market."""

    market_id = market["market_id"]
    current_price = safe_float(
        market["current_price"]
    )

    historical_prices: dict[
        str,
        float | None,
    ] = {}

    tolerance_map = {
        "move_5m": 10 * 60,
        "move_15m": 20 * 60,
        "move_1h": 90 * 60,
        "move_6h": 8 * 60 * 60,
        "move_24h": 30 * 60 * 60,
    }

    for key, lookback_seconds in (
        LOOKBACK_WINDOWS.items()
    ):
        target = (
            calculated_at
            - timedelta(
                seconds=lookback_seconds
            )
        )

        price, _ = nearest_historical_price(
            connection=connection,
            market_id=market_id,
            target_time=target,
            tolerance_seconds=(
                tolerance_map[key]
            ),
        )

        historical_prices[key] = price

    price_5m_ago = historical_prices[
        "move_5m"
    ]

    price_15m_ago = historical_prices[
        "move_15m"
    ]

    price_1h_ago = historical_prices[
        "move_1h"
    ]

    price_6h_ago = historical_prices[
        "move_6h"
    ]

    price_24h_ago = historical_prices[
        "move_24h"
    ]

    move_5m = (
        current_price - price_5m_ago
        if price_5m_ago is not None
        else None
    )

    move_15m = (
        current_price - price_15m_ago
        if price_15m_ago is not None
        else None
    )

    move_1h = (
        current_price - price_1h_ago
        if price_1h_ago is not None
        else None
    )

    move_6h = (
        current_price - price_6h_ago
        if price_6h_ago is not None
        else None
    )

    move_24h = (
        current_price - price_24h_ago
        if price_24h_ago is not None
        else None
    )

    cutoff_24h = (
        calculated_at
        - timedelta(hours=24)
    ).isoformat()

    rows_24h = connection.execute(
        """
        SELECT current_price
        FROM market_price_history
        WHERE market_id = ?
          AND observed_at >= ?
        ORDER BY observed_at
        """,
        (
            market_id,
            cutoff_24h,
        ),
    ).fetchall()

    prices_24h = [
        safe_float(
            row["current_price"]
        )
        for row in rows_24h
    ]

    if not prices_24h:
        prices_24h = [
            current_price
        ]

    high_24h = max(
        prices_24h
    )

    low_24h = min(
        prices_24h
    )

    range_24h = (
        high_24h - low_24h
    )

    steam_score = (
        calculate_steam_score(
            move_5m=move_5m,
            move_15m=move_15m,
            move_1h=move_1h,
            move_6h=move_6h,
        )
    )

    reversal_score = (
        calculate_reversal_score(
            move_5m=move_5m,
            move_15m=move_15m,
            move_1h=move_1h,
            move_6h=move_6h,
        )
    )

    volatility_score = (
        calculate_volatility_score(
            prices_24h
        )
    )

    move_status = classify_move_status(
        snapshot_count=len(
            prices_24h
        ),
        steam_score=steam_score,
        reversal_score=(
            reversal_score
        ),
        move_1h=move_1h,
        move_24h=move_24h,
    )

    return MetricResult(
        market_id=market_id,
        title=market["title"],
        outcome=market["outcome"],
        current_price=current_price,

        price_5m_ago=price_5m_ago,
        price_15m_ago=price_15m_ago,
        price_1h_ago=price_1h_ago,
        price_6h_ago=price_6h_ago,
        price_24h_ago=price_24h_ago,

        move_5m=move_5m,
        move_15m=move_15m,
        move_1h=move_1h,
        move_6h=move_6h,
        move_24h=move_24h,

        move_5m_pct=percentage_move(
            current_price,
            price_5m_ago,
        ),
        move_15m_pct=percentage_move(
            current_price,
            price_15m_ago,
        ),
        move_1h_pct=percentage_move(
            current_price,
            price_1h_ago,
        ),
        move_6h_pct=percentage_move(
            current_price,
            price_6h_ago,
        ),
        move_24h_pct=percentage_move(
            current_price,
            price_24h_ago,
        ),

        high_24h=high_24h,
        low_24h=low_24h,
        range_24h=range_24h,
        snapshot_count_24h=len(
            prices_24h
        ),

        steam_score=steam_score,
        reversal_score=(
            reversal_score
        ),
        volatility_score=(
            volatility_score
        ),
        move_status=move_status,

        lifecycle_status=market[
            "lifecycle_status"
        ],
        seconds_to_start=(
            safe_int(
                market[
                    "seconds_to_start"
                ]
            )
            if market[
                "seconds_to_start"
            ]
            is not None
            else None
        ),
        latest_observed_at=(
            calculated_at.isoformat()
        ),
        calculated_at=(
            calculated_at.isoformat()
        ),
    )


def save_metrics(
    metrics: list[MetricResult],
) -> int:
    """Upsert current price metrics."""

    connection = connect_database()

    updated = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for metric in metrics:
            connection.execute(
                """
                INSERT INTO market_price_metrics (
                    market_id,
                    title,
                    outcome,
                    current_price,

                    price_5m_ago,
                    price_15m_ago,
                    price_1h_ago,
                    price_6h_ago,
                    price_24h_ago,

                    move_5m,
                    move_15m,
                    move_1h,
                    move_6h,
                    move_24h,

                    move_5m_pct,
                    move_15m_pct,
                    move_1h_pct,
                    move_6h_pct,
                    move_24h_pct,

                    high_24h,
                    low_24h,
                    range_24h,
                    snapshot_count_24h,

                    steam_score,
                    reversal_score,
                    volatility_score,
                    move_status,

                    lifecycle_status,
                    seconds_to_start,

                    latest_observed_at,
                    calculated_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?
                )
                ON CONFLICT(market_id)
                DO UPDATE SET
                    title =
                        excluded.title,
                    outcome =
                        excluded.outcome,
                    current_price =
                        excluded.current_price,

                    price_5m_ago =
                        excluded.price_5m_ago,
                    price_15m_ago =
                        excluded.price_15m_ago,
                    price_1h_ago =
                        excluded.price_1h_ago,
                    price_6h_ago =
                        excluded.price_6h_ago,
                    price_24h_ago =
                        excluded.price_24h_ago,

                    move_5m =
                        excluded.move_5m,
                    move_15m =
                        excluded.move_15m,
                    move_1h =
                        excluded.move_1h,
                    move_6h =
                        excluded.move_6h,
                    move_24h =
                        excluded.move_24h,

                    move_5m_pct =
                        excluded.move_5m_pct,
                    move_15m_pct =
                        excluded.move_15m_pct,
                    move_1h_pct =
                        excluded.move_1h_pct,
                    move_6h_pct =
                        excluded.move_6h_pct,
                    move_24h_pct =
                        excluded.move_24h_pct,

                    high_24h =
                        excluded.high_24h,
                    low_24h =
                        excluded.low_24h,
                    range_24h =
                        excluded.range_24h,
                    snapshot_count_24h =
                        excluded.snapshot_count_24h,

                    steam_score =
                        excluded.steam_score,
                    reversal_score =
                        excluded.reversal_score,
                    volatility_score =
                        excluded.volatility_score,
                    move_status =
                        excluded.move_status,

                    lifecycle_status =
                        excluded.lifecycle_status,
                    seconds_to_start =
                        excluded.seconds_to_start,

                    latest_observed_at =
                        excluded.latest_observed_at,
                    calculated_at =
                        excluded.calculated_at,
                    updated_at =
                        excluded.updated_at
                """,
                (
                    metric.market_id,
                    metric.title,
                    metric.outcome,
                    metric.current_price,

                    metric.price_5m_ago,
                    metric.price_15m_ago,
                    metric.price_1h_ago,
                    metric.price_6h_ago,
                    metric.price_24h_ago,

                    metric.move_5m,
                    metric.move_15m,
                    metric.move_1h,
                    metric.move_6h,
                    metric.move_24h,

                    metric.move_5m_pct,
                    metric.move_15m_pct,
                    metric.move_1h_pct,
                    metric.move_6h_pct,
                    metric.move_24h_pct,

                    metric.high_24h,
                    metric.low_24h,
                    metric.range_24h,
                    metric.snapshot_count_24h,

                    metric.steam_score,
                    metric.reversal_score,
                    metric.volatility_score,
                    metric.move_status,

                    metric.lifecycle_status,
                    metric.seconds_to_start,

                    metric.latest_observed_at,
                    metric.calculated_at,
                    metric.calculated_at,
                ),
            )

            updated += 1

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return updated


# =============================================================================
# RETENTION
# =============================================================================


def prune_old_history(
    retention_days: int,
) -> int:
    """Delete snapshots older than the retention period."""

    if retention_days <= 0:
        return 0

    cutoff = (
        utc_now()
        - timedelta(
            days=retention_days
        )
    ).isoformat()

    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            DELETE FROM market_price_history
            WHERE observed_at < ?
            """,
            (cutoff,),
        )

        deleted = cursor.rowcount

        connection.commit()

        return max(
            safe_int(deleted),
            0,
        )

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run() -> tuple[int, datetime]:
    """Create a price-history run record."""

    started = utc_now()

    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO price_history_runs (
                started_at,
                status
            )
            VALUES (?, ?)
            """,
            (
                started.isoformat(),
                "RUNNING",
            ),
        )

        connection.commit()

        return cursor.lastrowid, started

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started_at: datetime,
    status: str,
    markets_seen: int,
    snapshots_inserted: int,
    snapshots_skipped: int,
    metrics_updated: int,
    rows_deleted: int,
    error_message: str = "",
) -> None:
    """Finalize a run record."""

    finished = utc_now()

    elapsed = (
        finished - started_at
    ).total_seconds()

    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE price_history_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                markets_seen = ?,
                snapshots_inserted = ?,
                snapshots_skipped = ?,
                metrics_updated = ?,
                rows_deleted = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                finished.isoformat(),
                elapsed,
                markets_seen,
                snapshots_inserted,
                snapshots_skipped,
                metrics_updated,
                rows_deleted,
                status,
                error_message,
                run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# DISPLAY
# =============================================================================


def display_database_readiness() -> None:
    """Display relevant table row counts."""

    connection = connect_database()

    try:
        print()
        print("=" * 100)
        print("PRICE HISTORY DATA READINESS")
        print("=" * 100)

        for table_name in (
            "market_metadata",
            "market_price_history",
            "market_price_metrics",
            "price_history_runs",
        ):
            if table_exists(
                connection,
                table_name,
            ):
                print(
                    f"{table_name:<38}"
                    f"{table_row_count(connection, table_name):>12} rows"
                )
            else:
                print(
                    f"{table_name:<38}"
                    f"{'NOT FOUND':>12}"
                )

        print("=" * 100)

    finally:
        connection.close()


def display_top_metrics(
    metrics: list[MetricResult],
    limit: int,
) -> None:
    """Display the strongest current price signals."""

    ranked = sorted(
        metrics,
        key=lambda item: (
            item.steam_score,
            item.reversal_score,
            abs(
                item.move_1h
                or 0.0
            ),
        ),
        reverse=True,
    )

    print()
    print("=" * 100)
    print("TOP PRICE-MOVEMENT SIGNALS")
    print("=" * 100)

    if not ranked:
        print(
            "No price metrics were calculated."
        )

        print("=" * 100)
        return

    for rank, metric in enumerate(
        ranked[:limit],
        start=1,
    ):
        print()
        print(
            f"{rank}. {metric.title}"
        )

        print(
            f"   Outcome:      "
            f"{metric.outcome or '-'}"
        )

        print(
            f"   Price:        "
            f"{format_price(metric.current_price)}"
        )

        print(
            f"   5m / 15m:     "
            f"{format_signed_move(metric.move_5m) if metric.move_5m is not None else 'N/A'}"
            f" / "
            f"{format_signed_move(metric.move_15m) if metric.move_15m is not None else 'N/A'}"
        )

        print(
            f"   1h / 24h:     "
            f"{format_signed_move(metric.move_1h) if metric.move_1h is not None else 'N/A'}"
            f" / "
            f"{format_signed_move(metric.move_24h) if metric.move_24h is not None else 'N/A'}"
        )

        print(
            f"   Steam:        "
            f"{metric.steam_score:.1f}/100"
        )

        print(
            f"   Reversal:     "
            f"{metric.reversal_score:.1f}/100"
        )

        print(
            f"   Volatility:   "
            f"{metric.volatility_score:.1f}/100"
        )

        print(
            f"   Status:       "
            f"{metric.move_status}"
        )

        print(
            f"   24h samples:  "
            f"{metric.snapshot_count_24h}"
        )

    print()
    print("=" * 100)


def display_summary(
    markets_seen: int,
    snapshots_inserted: int,
    snapshots_skipped: int,
    metrics_updated: int,
    rows_deleted: int,
) -> None:
    """Display one engine-run summary."""

    print()
    print("=" * 100)
    print("PRICE HISTORY ENGINE SUMMARY")
    print("=" * 100)

    print(
        f"Markets seen:             "
        f"{markets_seen}"
    )

    print(
        f"Snapshots inserted:       "
        f"{snapshots_inserted}"
    )

    print(
        f"Snapshots skipped:        "
        f"{snapshots_skipped}"
    )

    print(
        f"Metrics updated:          "
        f"{metrics_updated}"
    )

    print(
        f"Old snapshots deleted:    "
        f"{rows_deleted}"
    )

    print("=" * 100)


# =============================================================================
# ARGUMENTS
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Snapshot Polymarket prices and calculate "
            "multi-window movement metrics."
        )
    )

    parser.add_argument(
        "--retention-days",
        type=int,
        default=(
            DEFAULT_RETENTION_DAYS
        ),
        help=(
            "Delete price snapshots older than this "
            "many days. Use 0 to disable pruning."
        ),
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=(
            DEFAULT_DISPLAY_LIMIT
        ),
        help=(
            "Maximum number of price signals to display."
        ),
    )

    return parser.parse_args()


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Run the Price History Engine."""

    configure_utf8_output()

    arguments = parse_arguments()

    print()
    print("=" * 100)
    print(
        "POLYMARKET PRICE HISTORY "
        "ENGINE v1"
    )
    print("=" * 100)

    print(
        f"Database: {DATABASE_PATH}"
    )

    create_price_history_tables()

    display_database_readiness()

    run_id, started_at = start_run()

    markets_seen = 0
    snapshots_inserted = 0
    snapshots_skipped = 0
    metrics_updated = 0
    rows_deleted = 0

    try:
        current_markets = (
            load_current_markets()
        )

        markets_seen = len(
            current_markets
        )

        observed_at = utc_now_iso()

        (
            snapshots_inserted,
            snapshots_skipped,
        ) = insert_snapshots(
            markets=current_markets,
            observed_at=observed_at,
        )

        calculated_at = utc_now()

        connection = connect_database()

        try:
            metrics = [
                calculate_metric_for_market(
                    connection=connection,
                    market=market,
                    calculated_at=(
                        calculated_at
                    ),
                )
                for market
                in current_markets
            ]

        finally:
            connection.close()

        metrics_updated = save_metrics(
            metrics
        )

        rows_deleted = prune_old_history(
            max(
                arguments.retention_days,
                0,
            )
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            markets_seen=markets_seen,
            snapshots_inserted=(
                snapshots_inserted
            ),
            snapshots_skipped=(
                snapshots_skipped
            ),
            metrics_updated=(
                metrics_updated
            ),
            rows_deleted=rows_deleted,
        )

        display_summary(
            markets_seen=markets_seen,
            snapshots_inserted=(
                snapshots_inserted
            ),
            snapshots_skipped=(
                snapshots_skipped
            ),
            metrics_updated=(
                metrics_updated
            ),
            rows_deleted=rows_deleted,
        )

        display_top_metrics(
            metrics=metrics,
            limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 100)
        print(
            "PRICE HISTORY ENGINE COMPLETE"
        )
        print("=" * 100)

        print(
            "Current snapshots were saved to "
            "market_price_history."
        )

        print(
            "Current movement metrics were saved to "
            "market_price_metrics."
        )

        print(
            "The first run will usually show "
            "INSUFFICIENT_DATA because historical "
            "snapshots do not exist yet."
        )

        print(
            "Repeated scheduled runs will populate "
            "5m, 15m, 1h, 6h and 24h movement."
        )

        print("=" * 100)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            markets_seen=markets_seen,
            snapshots_inserted=(
                snapshots_inserted
            ),
            snapshots_skipped=(
                snapshots_skipped
            ),
            metrics_updated=(
                metrics_updated
            ),
            rows_deleted=rows_deleted,
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()