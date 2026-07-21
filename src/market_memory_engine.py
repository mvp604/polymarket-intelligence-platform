from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"

DEFAULT_LOOKBACK_HOURS = 24
DEFAULT_DISPLAY_LIMIT = 25
BUSY_TIMEOUT_MS = 30_000


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)

        try:
            stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )
        except (AttributeError, OSError):
            pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_wallet(value: Any) -> str:
    return clean_text(value).lower()


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    if denominator == 0:
        return default

    return numerator / denominator


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(
            value,
            maximum,
        ),
    )


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def format_money(value: Any) -> str:
    amount = safe_float(value)

    if amount > 0:
        return f"+${amount:,.2f}"

    if amount < 0:
        return f"-${abs(amount):,.2f}"

    return "$0.00"


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(
            f"Database not found: {DB}"
        )

    connection = sqlite3.connect(
        DB,
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
        f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}"
    )

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
        ).fetchone()
        is not None
    )


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not table_exists(
        connection,
        table_name,
    ):
        return set()

    return {
        clean_text(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def first_existing_column(
    columns: set[str],
    candidates: tuple[str, ...],
) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_tables() -> None:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "official_wallet_trades",
        ):
            raise RuntimeError(
                "official_wallet_trades is missing. "
                "Run official_wallet_activity_engine_v2.py first."
            )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_memory_snapshots (
                snapshot_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,
                market_id TEXT,
                event_id TEXT,

                title TEXT,
                slug TEXT,
                event_slug TEXT,
                category TEXT,

                snapshot_at TEXT NOT NULL,
                lookback_hours INTEGER NOT NULL,

                current_price REAL,
                average_trade_price REAL,
                weighted_average_buy_price REAL,
                weighted_average_sell_price REAL,

                trade_count INTEGER NOT NULL DEFAULT 0,
                unique_wallet_count INTEGER NOT NULL DEFAULT 0,

                buy_trade_count INTEGER NOT NULL DEFAULT 0,
                sell_trade_count INTEGER NOT NULL DEFAULT 0,

                buy_notional REAL NOT NULL DEFAULT 0,
                sell_notional REAL NOT NULL DEFAULT 0,
                net_flow REAL NOT NULL DEFAULT 0,
                gross_flow REAL NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER NOT NULL DEFAULT 0,
                qualified_wallet_count INTEGER NOT NULL DEFAULT 0,
                watchlist_wallet_count INTEGER NOT NULL DEFAULT 0,
                candidate_wallet_count INTEGER NOT NULL DEFAULT 0,

                elite_buy_notional REAL NOT NULL DEFAULT 0,
                elite_sell_notional REAL NOT NULL DEFAULT 0,
                qualified_buy_notional REAL NOT NULL DEFAULT 0,
                qualified_sell_notional REAL NOT NULL DEFAULT 0,
                watchlist_buy_notional REAL NOT NULL DEFAULT 0,
                watchlist_sell_notional REAL NOT NULL DEFAULT 0,

                bullish_wallet_count INTEGER NOT NULL DEFAULT 0,
                bearish_wallet_count INTEGER NOT NULL DEFAULT 0,
                neutral_wallet_count INTEGER NOT NULL DEFAULT 0,

                bullish_wallet_share REAL NOT NULL DEFAULT 0,
                bearish_wallet_share REAL NOT NULL DEFAULT 0,

                largest_buyer_wallet TEXT,
                largest_buyer_notional REAL NOT NULL DEFAULT 0,

                largest_seller_wallet TEXT,
                largest_seller_notional REAL NOT NULL DEFAULT 0,

                strongest_wallet TEXT,
                strongest_wallet_weight REAL NOT NULL DEFAULT 0,

                smart_money_weight REAL NOT NULL DEFAULT 0,
                consensus_strength REAL NOT NULL DEFAULT 0,
                concentration_risk REAL NOT NULL DEFAULT 0,
                market_memory_score REAL NOT NULL DEFAULT 0,
                market_memory_grade TEXT NOT NULL DEFAULT 'PASS',

                resolved INTEGER NOT NULL DEFAULT 0,
                winning_outcome TEXT,

                metadata_json TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_memory_snapshots_condition
            ON market_memory_snapshots(
                condition_id,
                snapshot_at DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_memory_snapshots_score
            ON market_memory_snapshots(
                market_memory_score DESC,
                snapshot_at DESC
            );

            CREATE TABLE IF NOT EXISTS market_memory_wallet_flows (
                flow_key TEXT PRIMARY KEY,

                snapshot_key TEXT NOT NULL,
                condition_id TEXT NOT NULL,
                wallet TEXT NOT NULL,

                wallet_status TEXT,
                elite_tier TEXT,

                wallet_influence_score REAL NOT NULL DEFAULT 0,
                consensus_weight REAL NOT NULL DEFAULT 0,
                prediction_weight REAL NOT NULL DEFAULT 0,

                buy_trade_count INTEGER NOT NULL DEFAULT 0,
                sell_trade_count INTEGER NOT NULL DEFAULT 0,

                buy_notional REAL NOT NULL DEFAULT 0,
                sell_notional REAL NOT NULL DEFAULT 0,
                net_flow REAL NOT NULL DEFAULT 0,

                average_buy_price REAL,
                average_sell_price REAL,

                directional_label TEXT NOT NULL DEFAULT 'NEUTRAL',

                first_trade_timestamp INTEGER,
                last_trade_timestamp INTEGER,

                created_at TEXT NOT NULL,

                FOREIGN KEY(snapshot_key)
                    REFERENCES market_memory_snapshots(snapshot_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_memory_wallet_flows_market
            ON market_memory_wallet_flows(
                condition_id,
                net_flow DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_memory_wallet_flows_wallet
            ON market_memory_wallet_flows(
                wallet,
                condition_id
            );

            CREATE TABLE IF NOT EXISTS market_memory_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                lookback_hours INTEGER NOT NULL,

                trades_loaded INTEGER NOT NULL DEFAULT 0,
                markets_observed INTEGER NOT NULL DEFAULT 0,
                snapshots_saved INTEGER NOT NULL DEFAULT 0,
                wallet_flows_saved INTEGER NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# SOURCE LOADERS
# =============================================================================


def load_wallet_registry() -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "wallet_registry",
        ):
            return {}

        return {
            normalize_wallet(row["wallet"]): dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM wallet_registry
                """
            ).fetchall()
            if normalize_wallet(row["wallet"])
        }

    finally:
        connection.close()


def load_elite_rankings() -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "elite_wallet_rankings",
        ):
            return {}

        return {
            normalize_wallet(row["wallet"]): dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM elite_wallet_rankings
                """
            ).fetchall()
            if normalize_wallet(row["wallet"])
        }

    finally:
        connection.close()


def load_market_metadata() -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        output: dict[str, dict[str, Any]] = {}

        if not table_exists(
            connection,
            "gamma_markets",
        ):
            return output

        columns = table_columns(
            connection,
            "gamma_markets",
        )

        condition_column = first_existing_column(
            columns,
            (
                "condition_id",
                "conditionId",
                "conditionid",
            ),
        )

        if condition_column is None:
            return output

        select_columns = [
            condition_column,
        ]

        optional_candidates = {
            "market_id": (
                "market_id",
                "id",
                "gamma_market_id",
            ),
            "event_id": (
                "event_id",
                "gamma_event_id",
            ),
            "title": (
                "title",
                "question",
            ),
            "slug": (
                "slug",
                "market_slug",
            ),
            "event_slug": (
                "event_slug",
            ),
            "category": (
                "category",
            ),
            "current_price": (
                "current_price",
                "last_trade_price",
                "price",
            ),
            "resolved": (
                "resolved",
                "closed",
            ),
            "winning_outcome": (
                "winning_outcome",
                "resolution",
            ),
        }

        resolved_columns: dict[str, str] = {}

        for logical_name, candidates in optional_candidates.items():
            column = first_existing_column(
                columns,
                candidates,
            )

            if column is not None:
                select_columns.append(column)
                resolved_columns[
                    logical_name
                ] = column

        sql = (
            "SELECT "
            + ", ".join(
                f'"{column}"'
                for column in select_columns
            )
            + ' FROM "gamma_markets"'
        )

        for row in connection.execute(sql).fetchall():
            condition_id = clean_text(
                row[
                    condition_column
                ]
            ).lower()

            if not condition_id:
                continue

            metadata = {
                "condition_id": condition_id,
            }

            for logical_name, column in resolved_columns.items():
                metadata[
                    logical_name
                ] = row[column]

            output[
                condition_id
            ] = metadata

        return output

    finally:
        connection.close()


def load_recent_trades(
    cutoff_timestamp: int,
) -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        columns = table_columns(
            connection,
            "official_wallet_trades",
        )

        required = {
            "wallet",
            "timestamp",
            "condition_id",
            "side",
            "size",
            "price",
        }

        missing = required - columns

        if missing:
            raise RuntimeError(
                "official_wallet_trades is missing columns: "
                + ", ".join(
                    sorted(missing)
                )
            )

        rows = connection.execute(
            """
            SELECT *
            FROM official_wallet_trades
            WHERE timestamp >= ?
              AND condition_id IS NOT NULL
              AND TRIM(condition_id) <> ''
            ORDER BY timestamp ASC
            """,
            (
                cutoff_timestamp,
            ),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


# =============================================================================
# AGGREGATION
# =============================================================================


def grade_from_score(
    score: float,
) -> str:
    if score >= 85:
        return "S"

    if score >= 75:
        return "A+"

    if score >= 65:
        return "A"

    if score >= 55:
        return "B"

    if score >= 45:
        return "WATCH"

    return "PASS"


def directional_label(
    net_flow: float,
    gross_flow: float,
) -> str:
    if gross_flow <= 0:
        return "NEUTRAL"

    ratio = net_flow / gross_flow

    if ratio >= 0.10:
        return "BULLISH"

    if ratio <= -0.10:
        return "BEARISH"

    return "NEUTRAL"


def build_memory(
    lookback_hours: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
]:
    cutoff = utc_now() - timedelta(
        hours=lookback_hours
    )

    cutoff_timestamp = int(
        cutoff.timestamp()
    )

    trades = load_recent_trades(
        cutoff_timestamp
    )

    wallet_registry = load_wallet_registry()
    elite_rankings = load_elite_rankings()
    market_metadata = load_market_metadata()

    snapshot_at = utc_now_iso()

    wallet_market: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    market_prices: dict[
        str,
        list[tuple[float, float]],
    ] = defaultdict(list)

    market_titles: dict[
        str,
        dict[str, str],
    ] = {}

    for trade in trades:
        condition_id = clean_text(
            trade.get(
                "condition_id"
            )
        ).lower()

        wallet = normalize_wallet(
            trade.get(
                "wallet"
            )
        )

        if not condition_id or not wallet:
            continue

        side = clean_text(
            trade.get(
                "side"
            )
        ).upper()

        size = abs(
            safe_float(
                trade.get(
                    "size"
                )
            )
        )

        price = safe_float(
            trade.get(
                "price"
            )
        )

        notional = abs(
            safe_float(
                trade.get(
                    "notional"
                ),
                size * price,
            )
        )

        if notional == 0:
            notional = size * price

        timestamp = safe_int(
            trade.get(
                "timestamp"
            )
        )

        key = (
            condition_id,
            wallet,
        )

        aggregate = wallet_market.setdefault(
            key,
            {
                "condition_id": condition_id,
                "wallet": wallet,
                "buy_trade_count": 0,
                "sell_trade_count": 0,
                "buy_notional": 0.0,
                "sell_notional": 0.0,
                "buy_price_numerator": 0.0,
                "sell_price_numerator": 0.0,
                "buy_size": 0.0,
                "sell_size": 0.0,
                "first_trade_timestamp": (
                    timestamp
                    if timestamp > 0
                    else None
                ),
                "last_trade_timestamp": (
                    timestamp
                    if timestamp > 0
                    else None
                ),
            },
        )

        if side == "BUY":
            aggregate[
                "buy_trade_count"
            ] += 1

            aggregate[
                "buy_notional"
            ] += notional

            aggregate[
                "buy_price_numerator"
            ] += price * size

            aggregate[
                "buy_size"
            ] += size

        elif side == "SELL":
            aggregate[
                "sell_trade_count"
            ] += 1

            aggregate[
                "sell_notional"
            ] += notional

            aggregate[
                "sell_price_numerator"
            ] += price * size

            aggregate[
                "sell_size"
            ] += size

        if timestamp > 0:
            first_timestamp = aggregate.get(
                "first_trade_timestamp"
            )

            last_timestamp = aggregate.get(
                "last_trade_timestamp"
            )

            aggregate[
                "first_trade_timestamp"
            ] = (
                timestamp
                if first_timestamp is None
                else min(
                    first_timestamp,
                    timestamp,
                )
            )

            aggregate[
                "last_trade_timestamp"
            ] = (
                timestamp
                if last_timestamp is None
                else max(
                    last_timestamp,
                    timestamp,
                )
            )

        if price > 0 and size > 0:
            market_prices[
                condition_id
            ].append(
                (
                    price,
                    size,
                )
            )

        market_titles.setdefault(
            condition_id,
            {
                "title": clean_text(
                    trade.get(
                        "title"
                    )
                ),
                "slug": clean_text(
                    trade.get(
                        "slug"
                    )
                ),
                "event_slug": clean_text(
                    trade.get(
                        "event_slug"
                    )
                ),
            },
        )

    wallet_flows: list[
        dict[str, Any]
    ] = []

    market_wallet_rows: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for (
        condition_id,
        wallet,
    ), aggregate in wallet_market.items():
        registry = wallet_registry.get(
            wallet,
            {},
        )

        elite = elite_rankings.get(
            wallet,
            {},
        )

        wallet_status = (
            clean_text(
                registry.get(
                    "status"
                )
            ).upper()
            or "UNKNOWN"
        )

        buy_notional = safe_float(
            aggregate[
                "buy_notional"
            ]
        )

        sell_notional = safe_float(
            aggregate[
                "sell_notional"
            ]
        )

        net_flow = (
            buy_notional
            - sell_notional
        )

        gross_flow = (
            buy_notional
            + sell_notional
        )

        average_buy_price = divide(
            aggregate[
                "buy_price_numerator"
            ],
            aggregate[
                "buy_size"
            ],
            0.0,
        )

        average_sell_price = divide(
            aggregate[
                "sell_price_numerator"
            ],
            aggregate[
                "sell_size"
            ],
            0.0,
        )

        influence_score = safe_float(
            elite.get(
                "influence_score"
            )
        )

        consensus_weight = safe_float(
            elite.get(
                "consensus_weight"
            )
        )

        prediction_weight = safe_float(
            elite.get(
                "prediction_weight"
            )
        )

        snapshot_key = (
            f"{condition_id}:"
            f"{lookback_hours}:"
            f"{snapshot_at}"
        )

        flow = {
            "flow_key": (
                f"{snapshot_key}:"
                f"{wallet}"
            ),
            "snapshot_key": snapshot_key,
            "condition_id": condition_id,
            "wallet": wallet,
            "wallet_status": wallet_status,
            "elite_tier": clean_text(
                elite.get(
                    "elite_tier"
                )
            ),
            "wallet_influence_score": (
                influence_score
            ),
            "consensus_weight": (
                consensus_weight
            ),
            "prediction_weight": (
                prediction_weight
            ),
            "buy_trade_count": safe_int(
                aggregate[
                    "buy_trade_count"
                ]
            ),
            "sell_trade_count": safe_int(
                aggregate[
                    "sell_trade_count"
                ]
            ),
            "buy_notional": buy_notional,
            "sell_notional": sell_notional,
            "net_flow": net_flow,
            "average_buy_price": (
                average_buy_price
                if average_buy_price > 0
                else None
            ),
            "average_sell_price": (
                average_sell_price
                if average_sell_price > 0
                else None
            ),
            "directional_label": (
                directional_label(
                    net_flow,
                    gross_flow,
                )
            ),
            "first_trade_timestamp": (
                aggregate[
                    "first_trade_timestamp"
                ]
            ),
            "last_trade_timestamp": (
                aggregate[
                    "last_trade_timestamp"
                ]
            ),
            "created_at": snapshot_at,
        }

        wallet_flows.append(flow)

        market_wallet_rows[
            condition_id
        ].append(flow)

    snapshots: list[
        dict[str, Any]
    ] = []

    for condition_id, rows in market_wallet_rows.items():
        metadata = market_metadata.get(
            condition_id,
            {},
        )

        fallback_metadata = market_titles.get(
            condition_id,
            {},
        )

        buy_notional = sum(
            safe_float(
                row[
                    "buy_notional"
                ]
            )
            for row in rows
        )

        sell_notional = sum(
            safe_float(
                row[
                    "sell_notional"
                ]
            )
            for row in rows
        )

        gross_flow = (
            buy_notional
            + sell_notional
        )

        net_flow = (
            buy_notional
            - sell_notional
        )

        buy_trade_count = sum(
            safe_int(
                row[
                    "buy_trade_count"
                ]
            )
            for row in rows
        )

        sell_trade_count = sum(
            safe_int(
                row[
                    "sell_trade_count"
                ]
            )
            for row in rows
        )

        status_counts = defaultdict(int)

        for row in rows:
            status_counts[
                clean_text(
                    row[
                        "wallet_status"
                    ]
                ).upper()
            ] += 1

        bullish_wallets = [
            row
            for row in rows
            if row[
                "directional_label"
            ]
            == "BULLISH"
        ]

        bearish_wallets = [
            row
            for row in rows
            if row[
                "directional_label"
            ]
            == "BEARISH"
        ]

        neutral_wallets = [
            row
            for row in rows
            if row[
                "directional_label"
            ]
            == "NEUTRAL"
        ]

        largest_buyer = max(
            rows,
            key=lambda row: safe_float(
                row[
                    "buy_notional"
                ]
            ),
            default=None,
        )

        largest_seller = max(
            rows,
            key=lambda row: safe_float(
                row[
                    "sell_notional"
                ]
            ),
            default=None,
        )

        strongest_wallet = max(
            rows,
            key=lambda row: (
                safe_float(
                    row[
                        "consensus_weight"
                    ]
                ),
                abs(
                    safe_float(
                        row[
                            "net_flow"
                        ]
                    )
                ),
            ),
            default=None,
        )

        weighted_prices = market_prices.get(
            condition_id,
            [],
        )

        weighted_price_numerator = sum(
            price * size
            for price, size in weighted_prices
        )

        weighted_price_denominator = sum(
            size
            for _, size in weighted_prices
        )

        average_trade_price = divide(
            weighted_price_numerator,
            weighted_price_denominator,
            0.0,
        )

        weighted_buy_numerator = sum(
            safe_float(
                row[
                    "average_buy_price"
                ]
            )
            * safe_float(
                row[
                    "buy_notional"
                ]
            )
            for row in rows
            if row[
                "average_buy_price"
            ]
            is not None
        )

        weighted_sell_numerator = sum(
            safe_float(
                row[
                    "average_sell_price"
                ]
            )
            * safe_float(
                row[
                    "sell_notional"
                ]
            )
            for row in rows
            if row[
                "average_sell_price"
            ]
            is not None
        )

        weighted_average_buy_price = divide(
            weighted_buy_numerator,
            buy_notional,
            0.0,
        )

        weighted_average_sell_price = divide(
            weighted_sell_numerator,
            sell_notional,
            0.0,
        )

        smart_money_weight = sum(
            max(
                safe_float(
                    row[
                        "consensus_weight"
                    ]
                ),
                0.25,
            )
            * abs(
                safe_float(
                    row[
                        "net_flow"
                    ]
                )
            )
            for row in rows
            if clean_text(
                row[
                    "wallet_status"
                ]
            ).upper()
            in {
                "ELITE",
                "QUALIFIED",
                "WATCHLIST",
            }
        )

        directional_weight = sum(
            max(
                safe_float(
                    row[
                        "consensus_weight"
                    ]
                ),
                0.25,
            )
            * (
                1.0
                if row[
                    "directional_label"
                ]
                == "BULLISH"
                else (
                    -1.0
                    if row[
                        "directional_label"
                    ]
                    == "BEARISH"
                    else 0.0
                )
            )
            for row in rows
        )

        total_directional_weight = sum(
            max(
                safe_float(
                    row[
                        "consensus_weight"
                    ]
                ),
                0.25,
            )
            for row in rows
        )

        consensus_strength = clamp(
            abs(
                divide(
                    directional_weight,
                    total_directional_weight,
                    0.0,
                )
            )
            * 100.0
        )

        largest_absolute_flow = max(
            (
                abs(
                    safe_float(
                        row[
                            "net_flow"
                        ]
                    )
                )
                for row in rows
            ),
            default=0.0,
        )

        concentration_risk = clamp(
            divide(
                largest_absolute_flow,
                max(
                    gross_flow,
                    1.0,
                ),
                0.0,
            )
            * 100.0
        )

        wallet_breadth_score = clamp(
            len(rows)
            / 10.0
            * 100.0
        )

        trusted_wallet_score = clamp(
            (
                status_counts["ELITE"]
                * 30.0
                + status_counts["QUALIFIED"]
                * 20.0
                + status_counts["WATCHLIST"]
                * 8.0
            )
        )

        flow_strength_score = clamp(
            abs(
                divide(
                    net_flow,
                    max(
                        gross_flow,
                        1.0,
                    ),
                    0.0,
                )
            )
            * 100.0
        )

        market_memory_score = clamp(
            consensus_strength * 0.35
            + wallet_breadth_score * 0.20
            + trusted_wallet_score * 0.20
            + flow_strength_score * 0.15
            + min(
                smart_money_weight
                / 100_000.0
                * 100.0,
                100.0,
            )
            * 0.10
            - concentration_risk
            * 0.20
        )

        snapshot_key = (
            f"{condition_id}:"
            f"{lookback_hours}:"
            f"{snapshot_at}"
        )

        snapshot = {
            "snapshot_key": snapshot_key,
            "condition_id": condition_id,
            "market_id": clean_text(
                metadata.get(
                    "market_id"
                )
            ),
            "event_id": clean_text(
                metadata.get(
                    "event_id"
                )
            ),
            "title": (
                clean_text(
                    metadata.get(
                        "title"
                    )
                )
                or clean_text(
                    fallback_metadata.get(
                        "title"
                    )
                )
            ),
            "slug": (
                clean_text(
                    metadata.get(
                        "slug"
                    )
                )
                or clean_text(
                    fallback_metadata.get(
                        "slug"
                    )
                )
            ),
            "event_slug": (
                clean_text(
                    metadata.get(
                        "event_slug"
                    )
                )
                or clean_text(
                    fallback_metadata.get(
                        "event_slug"
                    )
                )
            ),
            "category": clean_text(
                metadata.get(
                    "category"
                )
            ),
            "snapshot_at": snapshot_at,
            "lookback_hours": (
                lookback_hours
            ),
            "current_price": (
                safe_float(
                    metadata.get(
                        "current_price"
                    )
                )
                if metadata.get(
                    "current_price"
                )
                is not None
                else None
            ),
            "average_trade_price": (
                average_trade_price
                if average_trade_price > 0
                else None
            ),
            "weighted_average_buy_price": (
                weighted_average_buy_price
                if weighted_average_buy_price > 0
                else None
            ),
            "weighted_average_sell_price": (
                weighted_average_sell_price
                if weighted_average_sell_price > 0
                else None
            ),
            "trade_count": (
                buy_trade_count
                + sell_trade_count
            ),
            "unique_wallet_count": len(
                rows
            ),
            "buy_trade_count": (
                buy_trade_count
            ),
            "sell_trade_count": (
                sell_trade_count
            ),
            "buy_notional": buy_notional,
            "sell_notional": (
                sell_notional
            ),
            "net_flow": net_flow,
            "gross_flow": gross_flow,
            "elite_wallet_count": (
                status_counts["ELITE"]
            ),
            "qualified_wallet_count": (
                status_counts[
                    "QUALIFIED"
                ]
            ),
            "watchlist_wallet_count": (
                status_counts[
                    "WATCHLIST"
                ]
            ),
            "candidate_wallet_count": (
                status_counts[
                    "CANDIDATE"
                ]
            ),
            "elite_buy_notional": sum(
                safe_float(
                    row[
                        "buy_notional"
                    ]
                )
                for row in rows
                if row[
                    "wallet_status"
                ]
                == "ELITE"
            ),
            "elite_sell_notional": sum(
                safe_float(
                    row[
                        "sell_notional"
                    ]
                )
                for row in rows
                if row[
                    "wallet_status"
                ]
                == "ELITE"
            ),
            "qualified_buy_notional": sum(
                safe_float(
                    row[
                        "buy_notional"
                    ]
                )
                for row in rows
                if row[
                    "wallet_status"
                ]
                == "QUALIFIED"
            ),
            "qualified_sell_notional": sum(
                safe_float(
                    row[
                        "sell_notional"
                    ]
                )
                for row in rows
                if row[
                    "wallet_status"
                ]
                == "QUALIFIED"
            ),
            "watchlist_buy_notional": sum(
                safe_float(
                    row[
                        "buy_notional"
                    ]
                )
                for row in rows
                if row[
                    "wallet_status"
                ]
                == "WATCHLIST"
            ),
            "watchlist_sell_notional": sum(
                safe_float(
                    row[
                        "sell_notional"
                    ]
                )
                for row in rows
                if row[
                    "wallet_status"
                ]
                == "WATCHLIST"
            ),
            "bullish_wallet_count": len(
                bullish_wallets
            ),
            "bearish_wallet_count": len(
                bearish_wallets
            ),
            "neutral_wallet_count": len(
                neutral_wallets
            ),
            "bullish_wallet_share": divide(
                len(
                    bullish_wallets
                ),
                len(rows),
                0.0,
            ),
            "bearish_wallet_share": divide(
                len(
                    bearish_wallets
                ),
                len(rows),
                0.0,
            ),
            "largest_buyer_wallet": (
                largest_buyer[
                    "wallet"
                ]
                if largest_buyer
                else ""
            ),
            "largest_buyer_notional": (
                safe_float(
                    largest_buyer[
                        "buy_notional"
                    ]
                )
                if largest_buyer
                else 0.0
            ),
            "largest_seller_wallet": (
                largest_seller[
                    "wallet"
                ]
                if largest_seller
                else ""
            ),
            "largest_seller_notional": (
                safe_float(
                    largest_seller[
                        "sell_notional"
                    ]
                )
                if largest_seller
                else 0.0
            ),
            "strongest_wallet": (
                strongest_wallet[
                    "wallet"
                ]
                if strongest_wallet
                else ""
            ),
            "strongest_wallet_weight": (
                safe_float(
                    strongest_wallet[
                        "consensus_weight"
                    ]
                )
                if strongest_wallet
                else 0.0
            ),
            "smart_money_weight": (
                smart_money_weight
            ),
            "consensus_strength": (
                consensus_strength
            ),
            "concentration_risk": (
                concentration_risk
            ),
            "market_memory_score": (
                market_memory_score
            ),
            "market_memory_grade": (
                grade_from_score(
                    market_memory_score
                )
            ),
            "resolved": int(
                bool(
                    metadata.get(
                        "resolved"
                    )
                )
            ),
            "winning_outcome": clean_text(
                metadata.get(
                    "winning_outcome"
                )
            ),
            "metadata_json": stable_json(
                {
                    "model_version": "1.0",
                    "cutoff_timestamp": (
                        cutoff_timestamp
                    ),
                    "directional_weight": (
                        directional_weight
                    ),
                    "total_directional_weight": (
                        total_directional_weight
                    ),
                    "wallet_breadth_score": (
                        wallet_breadth_score
                    ),
                    "trusted_wallet_score": (
                        trusted_wallet_score
                    ),
                    "flow_strength_score": (
                        flow_strength_score
                    ),
                }
            ),
            "created_at": snapshot_at,
            "updated_at": snapshot_at,
        }

        snapshots.append(snapshot)

    snapshots.sort(
        key=lambda row: (
            row[
                "market_memory_score"
            ],
            abs(
                row[
                    "net_flow"
                ]
            ),
            row[
                "unique_wallet_count"
            ],
        ),
        reverse=True,
    )

    return (
        snapshots,
        wallet_flows,
        len(trades),
    )


# =============================================================================
# SAVE
# =============================================================================


SNAPSHOT_COLUMNS = [
    "snapshot_key",
    "condition_id",
    "market_id",
    "event_id",
    "title",
    "slug",
    "event_slug",
    "category",
    "snapshot_at",
    "lookback_hours",
    "current_price",
    "average_trade_price",
    "weighted_average_buy_price",
    "weighted_average_sell_price",
    "trade_count",
    "unique_wallet_count",
    "buy_trade_count",
    "sell_trade_count",
    "buy_notional",
    "sell_notional",
    "net_flow",
    "gross_flow",
    "elite_wallet_count",
    "qualified_wallet_count",
    "watchlist_wallet_count",
    "candidate_wallet_count",
    "elite_buy_notional",
    "elite_sell_notional",
    "qualified_buy_notional",
    "qualified_sell_notional",
    "watchlist_buy_notional",
    "watchlist_sell_notional",
    "bullish_wallet_count",
    "bearish_wallet_count",
    "neutral_wallet_count",
    "bullish_wallet_share",
    "bearish_wallet_share",
    "largest_buyer_wallet",
    "largest_buyer_notional",
    "largest_seller_wallet",
    "largest_seller_notional",
    "strongest_wallet",
    "strongest_wallet_weight",
    "smart_money_weight",
    "consensus_strength",
    "concentration_risk",
    "market_memory_score",
    "market_memory_grade",
    "resolved",
    "winning_outcome",
    "metadata_json",
    "created_at",
    "updated_at",
]


FLOW_COLUMNS = [
    "flow_key",
    "snapshot_key",
    "condition_id",
    "wallet",
    "wallet_status",
    "elite_tier",
    "wallet_influence_score",
    "consensus_weight",
    "prediction_weight",
    "buy_trade_count",
    "sell_trade_count",
    "buy_notional",
    "sell_notional",
    "net_flow",
    "average_buy_price",
    "average_sell_price",
    "directional_label",
    "first_trade_timestamp",
    "last_trade_timestamp",
    "created_at",
]


def build_insert_query(
    table_name: str,
    columns: list[str],
) -> str:
    names = ", ".join(
        f'"{column}"'
        for column in columns
    )

    placeholders = ", ".join(
        "?"
        for _ in columns
    )

    return (
        f'INSERT INTO "{table_name}" '
        f'({names}) VALUES ({placeholders})'
    )


def save_memory(
    snapshots: list[dict[str, Any]],
    wallet_flows: list[dict[str, Any]],
) -> tuple[int, int]:
    connection = connect_database()

    snapshot_query = build_insert_query(
        "market_memory_snapshots",
        SNAPSHOT_COLUMNS,
    )

    flow_query = build_insert_query(
        "market_memory_wallet_flows",
        FLOW_COLUMNS,
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for row in snapshots:
            connection.execute(
                snapshot_query,
                tuple(
                    row[column]
                    for column in SNAPSHOT_COLUMNS
                ),
            )

        for row in wallet_flows:
            connection.execute(
                flow_query,
                tuple(
                    row[column]
                    for column in FLOW_COLUMNS
                ),
            )

        connection.commit()

        return (
            len(snapshots),
            len(wallet_flows),
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run(
    lookback_hours: int,
) -> tuple[int, datetime]:
    started_at = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO market_memory_runs (
                started_at,
                lookback_hours,
                status
            )
            VALUES (
                ?, ?, 'RUNNING'
            )
            """,
            (
                started_at.isoformat(),
                lookback_hours,
            ),
        )

        connection.commit()

        return (
            cursor.lastrowid,
            started_at,
        )

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started_at: datetime,
    status: str,
    trades_loaded: int,
    markets_observed: int,
    snapshots_saved: int,
    wallet_flows_saved: int,
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE market_memory_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                trades_loaded = ?,
                markets_observed = ?,
                snapshots_saved = ?,
                wallet_flows_saved = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                finished_at.isoformat(),
                (
                    finished_at
                    - started_at
                ).total_seconds(),
                trades_loaded,
                markets_observed,
                snapshots_saved,
                wallet_flows_saved,
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


def display_summary(
    snapshots: list[dict[str, Any]],
    wallet_flows: list[dict[str, Any]],
    trades_loaded: int,
    display_limit: int,
) -> None:
    print()
    print("=" * 112)
    print("MARKET MEMORY ENGINE SUMMARY")
    print("=" * 112)

    print(
        f"Official trades loaded:         "
        f"{trades_loaded}"
    )

    print(
        f"Markets observed:               "
        f"{len(snapshots)}"
    )

    print(
        f"Wallet-market flow rows:        "
        f"{len(wallet_flows)}"
    )

    print(
        f"Positive net-flow markets:      "
        f"{sum(1 for row in snapshots if row['net_flow'] > 0)}"
    )

    print(
        f"Negative net-flow markets:      "
        f"{sum(1 for row in snapshots if row['net_flow'] < 0)}"
    )

    print("=" * 112)

    print()
    print("TOP MARKET MEMORY SNAPSHOTS")

    for rank, row in enumerate(
        snapshots[:display_limit],
        start=1,
    ):
        print()
        print("-" * 112)

        print(
            f"{rank}. "
            f"{row['title'] or row['slug'] or row['condition_id']}"
        )

        print("-" * 112)

        print(
            f"Score / grade:                  "
            f"{row['market_memory_score']:.1f} "
            f"/ {row['market_memory_grade']}"
        )

        print(
            f"Condition ID:                   "
            f"{row['condition_id']}"
        )

        print(
            f"Wallets / trades:               "
            f"{row['unique_wallet_count']} "
            f"/ {row['trade_count']}"
        )

        print(
            f"Buy / sell notional:            "
            f"${row['buy_notional']:,.2f} "
            f"/ ${row['sell_notional']:,.2f}"
        )

        print(
            f"Net flow:                       "
            f"{format_money(row['net_flow'])}"
        )

        print(
            f"Bullish / bearish wallets:      "
            f"{row['bullish_wallet_count']} "
            f"/ {row['bearish_wallet_count']}"
        )

        print(
            f"Elite / qualified / watchlist:  "
            f"{row['elite_wallet_count']} "
            f"/ {row['qualified_wallet_count']} "
            f"/ {row['watchlist_wallet_count']}"
        )

        print(
            f"Consensus / concentration:      "
            f"{row['consensus_strength']:.1f} "
            f"/ {row['concentration_risk']:.1f}"
        )

        print(
            f"Largest buyer:                  "
            f"{row['largest_buyer_wallet'] or '-'} "
            f"(${row['largest_buyer_notional']:,.2f})"
        )

        print(
            f"Largest seller:                 "
            f"{row['largest_seller_wallet'] or '-'} "
            f"(${row['largest_seller_notional']:,.2f})"
        )


# =============================================================================
# MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create persistent market-level memory snapshots from "
            "official wallet trades, wallet classifications and "
            "elite influence weights."
        )
    )

    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=DEFAULT_LOOKBACK_HOURS,
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8()
    arguments = parse_arguments()

    lookback_hours = max(
        arguments.lookback_hours,
        1,
    )

    print()
    print("=" * 112)
    print("POLYMARKET MARKET MEMORY ENGINE v1")
    print("=" * 112)

    print(
        f"Database:                    {DB}"
    )

    print(
        f"Trade lookback:              "
        f"{lookback_hours} hours"
    )

    print(
        "Method:                     "
        "OFFICIAL TRADE FLOW + WALLET STATUS + ELITE WEIGHTS"
    )

    print("=" * 112)

    create_tables()

    run_id, started_at = start_run(
        lookback_hours
    )

    snapshots: list[
        dict[str, Any]
    ] = []

    wallet_flows: list[
        dict[str, Any]
    ] = []

    trades_loaded = 0
    snapshots_saved = 0
    flows_saved = 0

    try:
        (
            snapshots,
            wallet_flows,
            trades_loaded,
        ) = build_memory(
            lookback_hours
        )

        if not snapshots:
            raise RuntimeError(
                "No market activity was found within the selected "
                "lookback period. Try a larger --lookback-hours value."
            )

        (
            snapshots_saved,
            flows_saved,
        ) = save_memory(
            snapshots,
            wallet_flows,
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            trades_loaded=trades_loaded,
            markets_observed=len(
                snapshots
            ),
            snapshots_saved=(
                snapshots_saved
            ),
            wallet_flows_saved=(
                flows_saved
            ),
        )

        display_summary(
            snapshots=snapshots,
            wallet_flows=wallet_flows,
            trades_loaded=trades_loaded,
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 112)
        print("MARKET MEMORY ENGINE COMPLETE")
        print("=" * 112)

        print(
            "Market snapshots:            "
            "market_memory_snapshots"
        )

        print(
            "Wallet-market flows:         "
            "market_memory_wallet_flows"
        )

        print(
            "Run history:                 "
            "market_memory_runs"
        )

        print("=" * 112)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            trades_loaded=trades_loaded,
            markets_observed=len(
                snapshots
            ),
            snapshots_saved=(
                snapshots_saved
            ),
            wallet_flows_saved=(
                flows_saved
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()