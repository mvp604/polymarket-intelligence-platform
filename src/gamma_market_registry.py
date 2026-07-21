from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
DEFAULT_LIMIT = 100
DEFAULT_MAX_PAGES = 20
REQUEST_TIMEOUT_SECONDS = 45
BUSY_TIMEOUT_MS = 30_000


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8_output() -> None:
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


def parse_json_value(value: Any) -> Any:
    if isinstance(
        value,
        (list, dict),
    ):
        return value

    text = clean_text(value)

    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def normalize_list(value: Any) -> list[Any]:
    parsed = parse_json_value(value)

    if isinstance(parsed, list):
        return parsed

    if isinstance(value, list):
        return value

    return []


def truthy(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)

    text = clean_text(value).casefold()

    return int(
        text in {
            "1",
            "true",
            "yes",
            "y",
        }
    )


# =============================================================================
# DATABASE
# =============================================================================


def connect_database() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
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
        f"{BUSY_TIMEOUT_MS}"
    )

    return connection


def create_registry_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS gamma_events (
                gamma_event_id TEXT PRIMARY KEY,

                slug TEXT,
                ticker TEXT,

                title TEXT NOT NULL,
                description TEXT,

                category TEXT,
                subcategory TEXT,

                active INTEGER
                    NOT NULL DEFAULT 0,

                closed INTEGER
                    NOT NULL DEFAULT 0,

                archived INTEGER
                    NOT NULL DEFAULT 0,

                restricted INTEGER
                    NOT NULL DEFAULT 0,

                featured INTEGER
                    NOT NULL DEFAULT 0,

                start_time TEXT,
                end_time TEXT,
                created_at_gamma TEXT,
                updated_at_gamma TEXT,

                liquidity REAL
                    NOT NULL DEFAULT 0,

                volume REAL
                    NOT NULL DEFAULT 0,

                volume_24h REAL
                    NOT NULL DEFAULT 0,

                open_interest REAL
                    NOT NULL DEFAULT 0,

                market_count INTEGER
                    NOT NULL DEFAULT 0,

                tags_json TEXT,
                series_json TEXT,
                image_url TEXT,
                icon_url TEXT,

                raw_payload_json TEXT NOT NULL,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                refreshed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_gamma_events_active
            ON gamma_events(
                active,
                closed,
                end_time
            );

            CREATE INDEX IF NOT EXISTS
            idx_gamma_events_slug
            ON gamma_events(
                slug
            );

            CREATE TABLE IF NOT EXISTS gamma_markets (
                gamma_market_id TEXT PRIMARY KEY,

                gamma_event_id TEXT,

                condition_id TEXT,
                question_id TEXT,

                slug TEXT,
                question TEXT NOT NULL,
                description TEXT,

                market_type TEXT,
                category TEXT,

                active INTEGER
                    NOT NULL DEFAULT 0,

                closed INTEGER
                    NOT NULL DEFAULT 0,

                archived INTEGER
                    NOT NULL DEFAULT 0,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                restricted INTEGER
                    NOT NULL DEFAULT 0,

                accepting_orders INTEGER
                    NOT NULL DEFAULT 0,

                neg_risk INTEGER
                    NOT NULL DEFAULT 0,

                start_time TEXT,
                end_time TEXT,
                game_start_time TEXT,

                created_at_gamma TEXT,
                updated_at_gamma TEXT,

                liquidity REAL
                    NOT NULL DEFAULT 0,

                volume REAL
                    NOT NULL DEFAULT 0,

                volume_24h REAL
                    NOT NULL DEFAULT 0,

                open_interest REAL
                    NOT NULL DEFAULT 0,

                spread REAL,
                last_trade_price REAL,
                best_bid REAL,
                best_ask REAL,

                outcome_count INTEGER
                    NOT NULL DEFAULT 0,

                clob_token_ids_json TEXT,
                outcomes_json TEXT,
                outcome_prices_json TEXT,

                resolution_source TEXT,
                resolved_by TEXT,

                image_url TEXT,
                icon_url TEXT,

                raw_payload_json TEXT NOT NULL,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                refreshed_at TEXT NOT NULL,

                FOREIGN KEY(
                    gamma_event_id
                )
                REFERENCES gamma_events(
                    gamma_event_id
                )
                ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_gamma_markets_condition
            ON gamma_markets(
                condition_id
            );

            CREATE INDEX IF NOT EXISTS
            idx_gamma_markets_event
            ON gamma_markets(
                gamma_event_id
            );

            CREATE INDEX IF NOT EXISTS
            idx_gamma_markets_active
            ON gamma_markets(
                active,
                closed,
                end_time
            );

            CREATE INDEX IF NOT EXISTS
            idx_gamma_markets_slug
            ON gamma_markets(
                slug
            );

            CREATE TABLE IF NOT EXISTS gamma_market_outcomes (
                outcome_key TEXT PRIMARY KEY,

                gamma_market_id TEXT NOT NULL,
                gamma_event_id TEXT,

                condition_id TEXT,

                outcome_index INTEGER
                    NOT NULL,

                outcome_name TEXT NOT NULL,
                token_id TEXT,

                implied_price REAL,
                winner INTEGER
                    NOT NULL DEFAULT 0,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                refreshed_at TEXT NOT NULL,

                FOREIGN KEY(
                    gamma_market_id
                )
                REFERENCES gamma_markets(
                    gamma_market_id
                )
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_gamma_outcomes_market
            ON gamma_market_outcomes(
                gamma_market_id,
                outcome_index
            );

            CREATE INDEX IF NOT EXISTS
            idx_gamma_outcomes_token
            ON gamma_market_outcomes(
                token_id
            );

            CREATE TABLE IF NOT EXISTS gamma_registry_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                events_fetched INTEGER
                    NOT NULL DEFAULT 0,

                markets_fetched INTEGER
                    NOT NULL DEFAULT 0,

                events_saved INTEGER
                    NOT NULL DEFAULT 0,

                markets_saved INTEGER
                    NOT NULL DEFAULT 0,

                outcomes_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# HTTP
# =============================================================================


def http_get_json(
    path: str,
    parameters: dict[str, Any],
) -> Any:
    query = urllib.parse.urlencode(
        {
            key: value
            for key, value
            in parameters.items()
            if value is not None
        },
        doseq=True,
    )

    url = (
        f"{GAMMA_BASE_URL}{path}"
        + (
            f"?{query}"
            if query
            else ""
        )
    )

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Polymarket-Intelligence-Platform/"
                "Gamma-Registry-1.0"
            ),
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as response:
        return json.load(response)


def fetch_active_events(
    limit: int,
    max_pages: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    offset = 0

    for page_number in range(
        1,
        max_pages + 1,
    ):
        payload = http_get_json(
            "/events",
            {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": offset,
            },
        )

        if not isinstance(
            payload,
            list,
        ):
            break

        batch = [
            item
            for item in payload
            if isinstance(
                item,
                dict,
            )
        ]

        if not batch:
            break

        events.extend(batch)

        print(
            f"Fetched event page "
            f"{page_number}: "
            f"{len(batch)} events"
        )

        if len(batch) < limit:
            break

        offset += limit
        time.sleep(0.10)

    return events


def fetch_markets_direct(
    limit: int,
    max_pages: int,
) -> list[dict[str, Any]]:
    markets: list[dict[str, Any]] = []
    offset = 0

    for page_number in range(
        1,
        max_pages + 1,
    ):
        payload = http_get_json(
            "/markets",
            {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": offset,
            },
        )

        if not isinstance(
            payload,
            list,
        ):
            break

        batch = [
            item
            for item in payload
            if isinstance(
                item,
                dict,
            )
        ]

        if not batch:
            break

        markets.extend(batch)

        print(
            f"Fetched market page "
            f"{page_number}: "
            f"{len(batch)} markets"
        )

        if len(batch) < limit:
            break

        offset += limit
        time.sleep(0.10)

    return markets


# =============================================================================
# NORMALIZATION
# =============================================================================


def event_id_from_market(
    market: dict[str, Any],
) -> str:
    event_id = clean_text(
        market.get("eventId")
        or market.get("event_id")
    )

    if event_id:
        return event_id

    events = market.get("events")

    if isinstance(events, list) and events:
        first = events[0]

        if isinstance(first, dict):
            return clean_text(
                first.get("id")
            )

    return clean_text(
        market.get("_event_id")
    )


def event_record(
    event: dict[str, Any],
) -> dict[str, Any]:
    markets = event.get("markets")

    market_count = (
        len(markets)
        if isinstance(
            markets,
            list,
        )
        else 0
    )

    return {
        "gamma_event_id": clean_text(
            event.get("id")
        ),
        "slug": clean_text(
            event.get("slug")
        ),
        "ticker": clean_text(
            event.get("ticker")
        ),
        "title": clean_text(
            event.get("title")
            or event.get("question")
            or "Untitled event"
        ),
        "description": clean_text(
            event.get("description")
        ),
        "category": clean_text(
            event.get("category")
        ),
        "subcategory": clean_text(
            event.get("subcategory")
        ),
        "active": truthy(
            event.get("active")
        ),
        "closed": truthy(
            event.get("closed")
        ),
        "archived": truthy(
            event.get("archived")
        ),
        "restricted": truthy(
            event.get("restricted")
        ),
        "featured": truthy(
            event.get("featured")
        ),
        "start_time": clean_text(
            event.get("startDate")
            or event.get("startTime")
            or event.get("gameStartTime")
        ),
        "end_time": clean_text(
            event.get("endDate")
            or event.get("endTime")
        ),
        "created_at_gamma": clean_text(
            event.get("createdAt")
        ),
        "updated_at_gamma": clean_text(
            event.get("updatedAt")
        ),
        "liquidity": safe_float(
            event.get("liquidity")
            or event.get("liquidityNum")
        ),
        "volume": safe_float(
            event.get("volume")
            or event.get("volumeNum")
        ),
        "volume_24h": safe_float(
            event.get("volume24hr")
            or event.get("volume24h")
        ),
        "open_interest": safe_float(
            event.get("openInterest")
        ),
        "market_count": market_count,
        "tags_json": json.dumps(
            event.get("tags") or [],
            ensure_ascii=False,
            default=str,
        ),
        "series_json": json.dumps(
            event.get("series") or [],
            ensure_ascii=False,
            default=str,
        ),
        "image_url": clean_text(
            event.get("image")
        ),
        "icon_url": clean_text(
            event.get("icon")
        ),
        "raw_payload_json": json.dumps(
            event,
            ensure_ascii=False,
            default=str,
        ),
    }


def market_record(
    market: dict[str, Any],
) -> dict[str, Any]:
    clob_token_ids = normalize_list(
        market.get("clobTokenIds")
        or market.get("clob_token_ids")
    )

    outcomes = normalize_list(
        market.get("outcomes")
    )

    outcome_prices = normalize_list(
        market.get("outcomePrices")
        or market.get("outcome_prices")
    )

    return {
        "gamma_market_id": clean_text(
            market.get("id")
        ),
        "gamma_event_id": (
            event_id_from_market(
                market
            )
        ),
        "condition_id": clean_text(
            market.get("conditionId")
            or market.get("condition_id")
        ).lower(),
        "question_id": clean_text(
            market.get("questionID")
            or market.get("questionId")
            or market.get("question_id")
        ),
        "slug": clean_text(
            market.get("slug")
        ),
        "question": clean_text(
            market.get("question")
            or market.get("title")
            or "Untitled market"
        ),
        "description": clean_text(
            market.get("description")
        ),
        "market_type": clean_text(
            market.get("marketType")
            or market.get("type")
        ),
        "category": clean_text(
            market.get("category")
        ),
        "active": truthy(
            market.get("active")
        ),
        "closed": truthy(
            market.get("closed")
        ),
        "archived": truthy(
            market.get("archived")
        ),
        "resolved": truthy(
            market.get("resolved")
        ),
        "restricted": truthy(
            market.get("restricted")
        ),
        "accepting_orders": truthy(
            market.get("acceptingOrders")
        ),
        "neg_risk": truthy(
            market.get("negRisk")
        ),
        "start_time": clean_text(
            market.get("startDate")
            or market.get("startTime")
        ),
        "end_time": clean_text(
            market.get("endDate")
            or market.get("endTime")
        ),
        "game_start_time": clean_text(
            market.get("gameStartTime")
        ),
        "created_at_gamma": clean_text(
            market.get("createdAt")
        ),
        "updated_at_gamma": clean_text(
            market.get("updatedAt")
        ),
        "liquidity": safe_float(
            market.get("liquidity")
            or market.get("liquidityNum")
        ),
        "volume": safe_float(
            market.get("volume")
            or market.get("volumeNum")
        ),
        "volume_24h": safe_float(
            market.get("volume24hr")
            or market.get("volume24h")
        ),
        "open_interest": safe_float(
            market.get("openInterest")
        ),
        "spread": (
            safe_float(
                market.get("spread")
            )
            if market.get("spread")
            is not None
            else None
        ),
        "last_trade_price": (
            safe_float(
                market.get("lastTradePrice")
            )
            if market.get("lastTradePrice")
            is not None
            else None
        ),
        "best_bid": (
            safe_float(
                market.get("bestBid")
            )
            if market.get("bestBid")
            is not None
            else None
        ),
        "best_ask": (
            safe_float(
                market.get("bestAsk")
            )
            if market.get("bestAsk")
            is not None
            else None
        ),
        "outcome_count": len(outcomes),
        "clob_token_ids_json": json.dumps(
            clob_token_ids,
            ensure_ascii=False,
            default=str,
        ),
        "outcomes_json": json.dumps(
            outcomes,
            ensure_ascii=False,
            default=str,
        ),
        "outcome_prices_json": json.dumps(
            outcome_prices,
            ensure_ascii=False,
            default=str,
        ),
        "resolution_source": clean_text(
            market.get("resolutionSource")
        ),
        "resolved_by": clean_text(
            market.get("resolvedBy")
        ),
        "image_url": clean_text(
            market.get("image")
        ),
        "icon_url": clean_text(
            market.get("icon")
        ),
        "raw_payload_json": json.dumps(
            market,
            ensure_ascii=False,
            default=str,
        ),
        "_outcomes": outcomes,
        "_token_ids": clob_token_ids,
        "_outcome_prices": outcome_prices,
    }


def flatten_event_markets(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for event in events:
        event_id = clean_text(
            event.get("id")
        )

        event_markets = event.get(
            "markets"
        )

        if not isinstance(
            event_markets,
            list,
        ):
            continue

        for market in event_markets:
            if not isinstance(
                market,
                dict,
            ):
                continue

            item = dict(market)
            item["_event_id"] = event_id
            output.append(item)

    return output


def deduplicate_markets(
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: dict[
        str,
        dict[str, Any],
    ] = {}

    for market in markets:
        market_id = clean_text(
            market.get("id")
        )

        condition_id = clean_text(
            market.get("conditionId")
            or market.get("condition_id")
        ).lower()

        key = (
            market_id
            or condition_id
        )

        if not key:
            continue

        prior = output.get(key)

        if prior is None:
            output[key] = market
            continue

        prior_score = len(
            json.dumps(
                prior,
                default=str,
            )
        )

        current_score = len(
            json.dumps(
                market,
                default=str,
            )
        )

        if current_score > prior_score:
            output[key] = market

    return list(
        output.values()
    )


# =============================================================================
# SAVING
# =============================================================================


def save_registry(
    events: list[dict[str, Any]],
    markets: list[dict[str, Any]],
) -> tuple[int, int, int]:
    connection = connect_database()
    refreshed_at = utc_now_iso()

    events_saved = 0
    markets_saved = 0
    outcomes_saved = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for raw_event in events:
            record = event_record(
                raw_event
            )

            if not record[
                "gamma_event_id"
            ]:
                continue

            connection.execute(
                """
                INSERT INTO gamma_events (
                    gamma_event_id,
                    slug,
                    ticker,
                    title,
                    description,
                    category,
                    subcategory,
                    active,
                    closed,
                    archived,
                    restricted,
                    featured,
                    start_time,
                    end_time,
                    created_at_gamma,
                    updated_at_gamma,
                    liquidity,
                    volume,
                    volume_24h,
                    open_interest,
                    market_count,
                    tags_json,
                    series_json,
                    image_url,
                    icon_url,
                    raw_payload_json,
                    first_seen_at,
                    last_seen_at,
                    refreshed_at
                )
                VALUES (
                    :gamma_event_id,
                    :slug,
                    :ticker,
                    :title,
                    :description,
                    :category,
                    :subcategory,
                    :active,
                    :closed,
                    :archived,
                    :restricted,
                    :featured,
                    :start_time,
                    :end_time,
                    :created_at_gamma,
                    :updated_at_gamma,
                    :liquidity,
                    :volume,
                    :volume_24h,
                    :open_interest,
                    :market_count,
                    :tags_json,
                    :series_json,
                    :image_url,
                    :icon_url,
                    :raw_payload_json,
                    :refreshed_at,
                    :refreshed_at,
                    :refreshed_at
                )
                ON CONFLICT(gamma_event_id)
                DO UPDATE SET
                    slug=excluded.slug,
                    ticker=excluded.ticker,
                    title=excluded.title,
                    description=excluded.description,
                    category=excluded.category,
                    subcategory=excluded.subcategory,
                    active=excluded.active,
                    closed=excluded.closed,
                    archived=excluded.archived,
                    restricted=excluded.restricted,
                    featured=excluded.featured,
                    start_time=excluded.start_time,
                    end_time=excluded.end_time,
                    created_at_gamma=excluded.created_at_gamma,
                    updated_at_gamma=excluded.updated_at_gamma,
                    liquidity=excluded.liquidity,
                    volume=excluded.volume,
                    volume_24h=excluded.volume_24h,
                    open_interest=excluded.open_interest,
                    market_count=excluded.market_count,
                    tags_json=excluded.tags_json,
                    series_json=excluded.series_json,
                    image_url=excluded.image_url,
                    icon_url=excluded.icon_url,
                    raw_payload_json=excluded.raw_payload_json,
                    last_seen_at=excluded.last_seen_at,
                    refreshed_at=excluded.refreshed_at
                """,
                {
                    **record,
                    "refreshed_at": (
                        refreshed_at
                    ),
                },
            )

            events_saved += 1

        for raw_market in markets:
            record = market_record(
                raw_market
            )

            market_id = record[
                "gamma_market_id"
            ]

            if not market_id:
                continue

            event_id = record[
                "gamma_event_id"
            ]

            if event_id:
                exists = connection.execute(
                    """
                    SELECT 1
                    FROM gamma_events
                    WHERE gamma_event_id = ?
                    """,
                    (event_id,),
                ).fetchone()

                if exists is None:
                    event_id = None

            record[
                "gamma_event_id"
            ] = event_id

            database_record = {
                key: value
                for key, value
                in record.items()
                if not key.startswith("_")
            }

            connection.execute(
                """
                INSERT INTO gamma_markets (
                    gamma_market_id,
                    gamma_event_id,
                    condition_id,
                    question_id,
                    slug,
                    question,
                    description,
                    market_type,
                    category,
                    active,
                    closed,
                    archived,
                    resolved,
                    restricted,
                    accepting_orders,
                    neg_risk,
                    start_time,
                    end_time,
                    game_start_time,
                    created_at_gamma,
                    updated_at_gamma,
                    liquidity,
                    volume,
                    volume_24h,
                    open_interest,
                    spread,
                    last_trade_price,
                    best_bid,
                    best_ask,
                    outcome_count,
                    clob_token_ids_json,
                    outcomes_json,
                    outcome_prices_json,
                    resolution_source,
                    resolved_by,
                    image_url,
                    icon_url,
                    raw_payload_json,
                    first_seen_at,
                    last_seen_at,
                    refreshed_at
                )
                VALUES (
                    :gamma_market_id,
                    :gamma_event_id,
                    :condition_id,
                    :question_id,
                    :slug,
                    :question,
                    :description,
                    :market_type,
                    :category,
                    :active,
                    :closed,
                    :archived,
                    :resolved,
                    :restricted,
                    :accepting_orders,
                    :neg_risk,
                    :start_time,
                    :end_time,
                    :game_start_time,
                    :created_at_gamma,
                    :updated_at_gamma,
                    :liquidity,
                    :volume,
                    :volume_24h,
                    :open_interest,
                    :spread,
                    :last_trade_price,
                    :best_bid,
                    :best_ask,
                    :outcome_count,
                    :clob_token_ids_json,
                    :outcomes_json,
                    :outcome_prices_json,
                    :resolution_source,
                    :resolved_by,
                    :image_url,
                    :icon_url,
                    :raw_payload_json,
                    :refreshed_at,
                    :refreshed_at,
                    :refreshed_at
                )
                ON CONFLICT(gamma_market_id)
                DO UPDATE SET
                    gamma_event_id=excluded.gamma_event_id,
                    condition_id=excluded.condition_id,
                    question_id=excluded.question_id,
                    slug=excluded.slug,
                    question=excluded.question,
                    description=excluded.description,
                    market_type=excluded.market_type,
                    category=excluded.category,
                    active=excluded.active,
                    closed=excluded.closed,
                    archived=excluded.archived,
                    resolved=excluded.resolved,
                    restricted=excluded.restricted,
                    accepting_orders=excluded.accepting_orders,
                    neg_risk=excluded.neg_risk,
                    start_time=excluded.start_time,
                    end_time=excluded.end_time,
                    game_start_time=excluded.game_start_time,
                    created_at_gamma=excluded.created_at_gamma,
                    updated_at_gamma=excluded.updated_at_gamma,
                    liquidity=excluded.liquidity,
                    volume=excluded.volume,
                    volume_24h=excluded.volume_24h,
                    open_interest=excluded.open_interest,
                    spread=excluded.spread,
                    last_trade_price=excluded.last_trade_price,
                    best_bid=excluded.best_bid,
                    best_ask=excluded.best_ask,
                    outcome_count=excluded.outcome_count,
                    clob_token_ids_json=excluded.clob_token_ids_json,
                    outcomes_json=excluded.outcomes_json,
                    outcome_prices_json=excluded.outcome_prices_json,
                    resolution_source=excluded.resolution_source,
                    resolved_by=excluded.resolved_by,
                    image_url=excluded.image_url,
                    icon_url=excluded.icon_url,
                    raw_payload_json=excluded.raw_payload_json,
                    last_seen_at=excluded.last_seen_at,
                    refreshed_at=excluded.refreshed_at
                """,
                {
                    **database_record,
                    "refreshed_at": (
                        refreshed_at
                    ),
                },
            )

            markets_saved += 1

            outcomes = record[
                "_outcomes"
            ]

            token_ids = record[
                "_token_ids"
            ]

            outcome_prices = record[
                "_outcome_prices"
            ]

            for index, outcome_name in enumerate(
                outcomes
            ):
                token_id = (
                    clean_text(
                        token_ids[index]
                    )
                    if index
                    < len(token_ids)
                    else ""
                )

                implied_price = (
                    safe_float(
                        outcome_prices[index]
                    )
                    if index
                    < len(outcome_prices)
                    else None
                )

                winner = 0

                winners = raw_market.get(
                    "winner"
                )

                if isinstance(
                    winners,
                    list,
                ) and index < len(winners):
                    winner = truthy(
                        winners[index]
                    )

                outcome_key = (
                    f"{market_id}:{index}"
                )

                connection.execute(
                    """
                    INSERT INTO gamma_market_outcomes (
                        outcome_key,
                        gamma_market_id,
                        gamma_event_id,
                        condition_id,
                        outcome_index,
                        outcome_name,
                        token_id,
                        implied_price,
                        winner,
                        first_seen_at,
                        last_seen_at,
                        refreshed_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    ON CONFLICT(outcome_key)
                    DO UPDATE SET
                        gamma_event_id=excluded.gamma_event_id,
                        condition_id=excluded.condition_id,
                        outcome_name=excluded.outcome_name,
                        token_id=excluded.token_id,
                        implied_price=excluded.implied_price,
                        winner=excluded.winner,
                        last_seen_at=excluded.last_seen_at,
                        refreshed_at=excluded.refreshed_at
                    """,
                    (
                        outcome_key,
                        market_id,
                        event_id,
                        record[
                            "condition_id"
                        ],
                        index,
                        clean_text(
                            outcome_name
                        ),
                        token_id,
                        implied_price,
                        winner,
                        refreshed_at,
                        refreshed_at,
                        refreshed_at,
                    ),
                )

                outcomes_saved += 1

        connection.commit()

        return (
            events_saved,
            markets_saved,
            outcomes_saved,
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run() -> tuple[int, datetime]:
    started = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO gamma_registry_runs (
                started_at,
                status
            )
            VALUES (
                ?,
                'RUNNING'
            )
            """,
            (started.isoformat(),),
        )

        connection.commit()

        return (
            cursor.lastrowid,
            started,
        )

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started_at: datetime,
    status: str,
    events_fetched: int,
    markets_fetched: int,
    events_saved: int,
    markets_saved: int,
    outcomes_saved: int,
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE gamma_registry_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                events_fetched = ?,
                markets_fetched = ?,
                events_saved = ?,
                markets_saved = ?,
                outcomes_saved = ?,
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
                events_fetched,
                markets_fetched,
                events_saved,
                markets_saved,
                outcomes_saved,
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
    events_fetched: int,
    markets_fetched: int,
    events_saved: int,
    markets_saved: int,
    outcomes_saved: int,
) -> None:
    connection = connect_database()

    try:
        active_events = safe_int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM gamma_events
                WHERE active = 1
                  AND closed = 0
                """
            ).fetchone()[0]
        )

        active_markets = safe_int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM gamma_markets
                WHERE active = 1
                  AND closed = 0
                """
            ).fetchone()[0]
        )

        token_rows = safe_int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM gamma_market_outcomes
                WHERE token_id IS NOT NULL
                  AND token_id != ''
                """
            ).fetchone()[0]
        )

    finally:
        connection.close()

    print()
    print("=" * 108)
    print("GAMMA MARKET REGISTRY SUMMARY")
    print("=" * 108)

    print(
        f"Events fetched:                 "
        f"{events_fetched}"
    )

    print(
        f"Markets fetched:                "
        f"{markets_fetched}"
    )

    print(
        f"Events saved:                   "
        f"{events_saved}"
    )

    print(
        f"Markets saved:                  "
        f"{markets_saved}"
    )

    print(
        f"Outcome rows saved:             "
        f"{outcomes_saved}"
    )

    print(
        f"Active registry events:         "
        f"{active_events}"
    )

    print(
        f"Active registry markets:        "
        f"{active_markets}"
    )

    print(
        f"Outcome rows with token IDs:    "
        f"{token_rows}"
    )

    print("=" * 108)


# =============================================================================
# ARGUMENTS AND MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Mirror active Polymarket Gamma events, "
            "markets and outcome token IDs into SQLite."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
    )

    parser.add_argument(
        "--events-only",
        action="store_true",
        help=(
            "Use only markets embedded inside the "
            "events response."
        ),
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8_output()
    arguments = parse_arguments()

    limit = max(
        arguments.limit,
        1,
    )

    max_pages = max(
        arguments.max_pages,
        1,
    )

    print()
    print("=" * 108)
    print("POLYMARKET GAMMA MARKET REGISTRY v1")
    print("=" * 108)

    print(
        f"Database: {DATABASE_PATH}"
    )

    print(
        f"Gamma:    {GAMMA_BASE_URL}"
    )

    print(
        f"Page limit: {limit}"
    )

    print(
        f"Maximum pages: {max_pages}"
    )

    create_registry_tables()
    run_id, started_at = start_run()

    events: list[dict[str, Any]] = []
    direct_markets: list[
        dict[str, Any]
    ] = []

    markets: list[dict[str, Any]] = []

    events_saved = 0
    markets_saved = 0
    outcomes_saved = 0

    try:
        events = fetch_active_events(
            limit=limit,
            max_pages=max_pages,
        )

        embedded_markets = (
            flatten_event_markets(
                events
            )
        )

        if not arguments.events_only:
            direct_markets = (
                fetch_markets_direct(
                    limit=limit,
                    max_pages=max_pages,
                )
            )

        markets = deduplicate_markets(
            embedded_markets
            + direct_markets
        )

        (
            events_saved,
            markets_saved,
            outcomes_saved,
        ) = save_registry(
            events=events,
            markets=markets,
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            events_fetched=len(events),
            markets_fetched=len(
                markets
            ),
            events_saved=events_saved,
            markets_saved=markets_saved,
            outcomes_saved=outcomes_saved,
        )

        display_summary(
            events_fetched=len(events),
            markets_fetched=len(
                markets
            ),
            events_saved=events_saved,
            markets_saved=markets_saved,
            outcomes_saved=outcomes_saved,
        )

        print()
        print("=" * 108)
        print("GAMMA MARKET REGISTRY COMPLETE")
        print("=" * 108)

        print(
            "Events were stored in gamma_events."
        )

        print(
            "Markets were stored in gamma_markets."
        )

        print(
            "Outcome and token mappings were stored in "
            "gamma_market_outcomes."
        )

        print(
            "The registry mirrors Gamma identifiers and "
            "does not infer title-based matches."
        )

        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            events_fetched=len(events),
            markets_fetched=len(
                markets
            ),
            events_saved=events_saved,
            markets_saved=markets_saved,
            outcomes_saved=outcomes_saved,
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()