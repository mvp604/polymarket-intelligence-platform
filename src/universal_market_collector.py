from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import requests

ENGINE_VERSION = "1.1.0"
GAMMA_API_URL = "https://gamma-api.polymarket.com"
DEFAULT_DATABASE_PATH = Path("database/polymarket.db")
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_EVENTS = 5000
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 4


@dataclass(slots=True)
class Config:
    database_path: Path
    page_size: int
    max_events: int
    include_closed: bool
    active_only: bool
    save_snapshots: bool
    timeout: int
    retries: int
    display_limit: int


@dataclass(slots=True)
class Stats:
    run_id: str
    started_at: str
    api_requests: int = 0
    api_failures: int = 0
    pages_fetched: int = 0
    events_fetched: int = 0
    events_inserted: int = 0
    events_updated: int = 0
    markets_seen: int = 0
    markets_inserted: int = 0
    markets_updated: int = 0
    markets_unchanged: int = 0
    snapshots_inserted: int = 0
    links_written: int = 0
    tags_written: int = 0
    malformed_events: int = 0
    malformed_markets: int = 0
    pagination_exhausted: int = 0
    last_successful_offset: int = 0
    pagination_warning: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"market_collector:{stamp}:{uuid.uuid4().hex[:8]}"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root() / path
    return path.resolve()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def text(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def optional_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def boolean(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value != 0)
    return int(text(value).lower() in {"1", "true", "yes", "y", "on"})


def first(data: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [part.strip() for part in stripped.split(",") if part.strip()]
        return parsed if isinstance(parsed, list) else [parsed]
    return []


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS universal_market_collector_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            database_path TEXT NOT NULL,
            include_closed INTEGER NOT NULL DEFAULT 0,
            active_only INTEGER NOT NULL DEFAULT 1,
            page_size INTEGER NOT NULL,
            max_events INTEGER NOT NULL,
            api_requests INTEGER NOT NULL DEFAULT 0,
            api_failures INTEGER NOT NULL DEFAULT 0,
            pages_fetched INTEGER NOT NULL DEFAULT 0,
            events_fetched INTEGER NOT NULL DEFAULT 0,
            events_inserted INTEGER NOT NULL DEFAULT 0,
            events_updated INTEGER NOT NULL DEFAULT 0,
            markets_seen INTEGER NOT NULL DEFAULT 0,
            markets_inserted INTEGER NOT NULL DEFAULT 0,
            markets_updated INTEGER NOT NULL DEFAULT 0,
            markets_unchanged INTEGER NOT NULL DEFAULT 0,
            snapshots_inserted INTEGER NOT NULL DEFAULT 0,
            links_written INTEGER NOT NULL DEFAULT 0,
            tags_written INTEGER NOT NULL DEFAULT 0,
            malformed_events INTEGER NOT NULL DEFAULT 0,
            malformed_markets INTEGER NOT NULL DEFAULT 0,
            pagination_exhausted INTEGER NOT NULL DEFAULT 0,
            last_successful_offset INTEGER NOT NULL DEFAULT 0,
            pagination_warning TEXT NOT NULL DEFAULT '',
            runtime_seconds REAL NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS event_catalog (
            gamma_event_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL DEFAULT '',
            slug TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            subtitle TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            resolution_source TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            subcategory TEXT NOT NULL DEFAULT '',
            start_time TEXT NOT NULL DEFAULT '',
            end_time TEXT NOT NULL DEFAULT '',
            creation_time TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 0,
            closed INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            featured INTEGER NOT NULL DEFAULT 0,
            restricted INTEGER NOT NULL DEFAULT 0,
            liquidity REAL NOT NULL DEFAULT 0,
            volume REAL NOT NULL DEFAULT 0,
            volume_24h REAL NOT NULL DEFAULT 0,
            open_interest REAL NOT NULL DEFAULT 0,
            polymarket_url TEXT NOT NULL DEFAULT '',
            image_url TEXT NOT NULL DEFAULT '',
            icon_url TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_event_catalog_slug ON event_catalog(slug);
        CREATE INDEX IF NOT EXISTS idx_event_catalog_status ON event_catalog(active, closed, archived);
        CREATE INDEX IF NOT EXISTS idx_event_catalog_end_time ON event_catalog(end_time);

        CREATE TABLE IF NOT EXISTS market_catalog (
            condition_id TEXT PRIMARY KEY,
            gamma_market_id TEXT NOT NULL DEFAULT '',
            question_id TEXT NOT NULL DEFAULT '',
            slug TEXT NOT NULL DEFAULT '',
            question TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            resolution_source TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            market_type TEXT NOT NULL DEFAULT '',
            format_type TEXT NOT NULL DEFAULT '',
            group_item_title TEXT NOT NULL DEFAULT '',
            group_item_threshold TEXT NOT NULL DEFAULT '',
            sports_market_type TEXT NOT NULL DEFAULT '',
            game_id TEXT NOT NULL DEFAULT '',
            start_time TEXT NOT NULL DEFAULT '',
            end_time TEXT NOT NULL DEFAULT '',
            game_start_time TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 0,
            closed INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            restricted INTEGER NOT NULL DEFAULT 0,
            accepting_orders INTEGER NOT NULL DEFAULT 0,
            enable_order_book INTEGER NOT NULL DEFAULT 0,
            resolved INTEGER NOT NULL DEFAULT 0,
            resolution_status TEXT NOT NULL DEFAULT '',
            outcomes_json TEXT NOT NULL DEFAULT '[]',
            outcome_prices_json TEXT NOT NULL DEFAULT '[]',
            clob_token_ids_json TEXT NOT NULL DEFAULT '[]',
            yes_token_id TEXT NOT NULL DEFAULT '',
            no_token_id TEXT NOT NULL DEFAULT '',
            yes_price REAL,
            no_price REAL,
            best_bid REAL,
            best_ask REAL,
            spread REAL,
            last_trade_price REAL,
            liquidity REAL NOT NULL DEFAULT 0,
            volume REAL NOT NULL DEFAULT 0,
            volume_24h REAL NOT NULL DEFAULT 0,
            volume_1w REAL NOT NULL DEFAULT 0,
            volume_1m REAL NOT NULL DEFAULT 0,
            open_interest REAL NOT NULL DEFAULT 0,
            minimum_tick_size REAL,
            minimum_order_size REAL,
            neg_risk INTEGER NOT NULL DEFAULT 0,
            fees_enabled INTEGER NOT NULL DEFAULT 0,
            polymarket_url TEXT NOT NULL DEFAULT '',
            image_url TEXT NOT NULL DEFAULT '',
            icon_url TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_market_catalog_gamma_id
            ON market_catalog(gamma_market_id) WHERE gamma_market_id <> '';
        CREATE INDEX IF NOT EXISTS idx_market_catalog_slug ON market_catalog(slug);
        CREATE INDEX IF NOT EXISTS idx_market_catalog_status ON market_catalog(active, closed, resolved);
        CREATE INDEX IF NOT EXISTS idx_market_catalog_end_time ON market_catalog(end_time);
        CREATE INDEX IF NOT EXISTS idx_market_catalog_volume ON market_catalog(volume DESC);
        CREATE INDEX IF NOT EXISTS idx_market_catalog_liquidity ON market_catalog(liquidity DESC);

        CREATE TABLE IF NOT EXISTS event_market_map (
            gamma_event_id TEXT NOT NULL,
            condition_id TEXT NOT NULL,
            relationship_order INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            PRIMARY KEY(gamma_event_id, condition_id),
            FOREIGN KEY(gamma_event_id) REFERENCES event_catalog(gamma_event_id) ON DELETE CASCADE,
            FOREIGN KEY(condition_id) REFERENCES market_catalog(condition_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS market_tags (
            condition_id TEXT NOT NULL,
            tag_id TEXT NOT NULL DEFAULT '',
            tag_slug TEXT NOT NULL DEFAULT '',
            tag_label TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            PRIMARY KEY(condition_id, tag_id, tag_slug),
            FOREIGN KEY(condition_id) REFERENCES market_catalog(condition_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_market_tags_slug ON market_tags(tag_slug);

        CREATE TABLE IF NOT EXISTS market_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            condition_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            active INTEGER NOT NULL,
            closed INTEGER NOT NULL,
            resolved INTEGER NOT NULL,
            accepting_orders INTEGER NOT NULL,
            yes_price REAL,
            no_price REAL,
            best_bid REAL,
            best_ask REAL,
            spread REAL,
            last_trade_price REAL,
            liquidity REAL NOT NULL DEFAULT 0,
            volume REAL NOT NULL DEFAULT 0,
            volume_24h REAL NOT NULL DEFAULT 0,
            volume_1w REAL NOT NULL DEFAULT 0,
            volume_1m REAL NOT NULL DEFAULT 0,
            open_interest REAL NOT NULL DEFAULT 0,
            outcome_prices_json TEXT NOT NULL DEFAULT '[]',
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(run_id, condition_id),
            FOREIGN KEY(run_id) REFERENCES universal_market_collector_runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY(condition_id) REFERENCES market_catalog(condition_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_market_snapshots_condition_time
            ON market_snapshots(condition_id, observed_at DESC);
        """
    )
    # Backward-compatible schema migration for databases created by v1.0.0.
    existing_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(universal_market_collector_runs)"
        ).fetchall()
    }
    migrations = {
        "pagination_exhausted": (
            "ALTER TABLE universal_market_collector_runs "
            "ADD COLUMN pagination_exhausted INTEGER NOT NULL DEFAULT 0"
        ),
        "last_successful_offset": (
            "ALTER TABLE universal_market_collector_runs "
            "ADD COLUMN last_successful_offset INTEGER NOT NULL DEFAULT 0"
        ),
        "pagination_warning": (
            "ALTER TABLE universal_market_collector_runs "
            "ADD COLUMN pagination_warning TEXT NOT NULL DEFAULT ''"
        ),
    }
    for column_name, statement in migrations.items():
        if column_name not in existing_columns:
            connection.execute(statement)

    connection.commit()


class GammaClient:
    def __init__(self, config: Config, stats: Stats) -> None:
        self.config = config
        self.stats = stats
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", f"User-Agent": "Polymarket-Intelligence-Platform/{ENGINE_VERSION}"})

    def get_json(self, path: str, params: Mapping[str, Any]) -> Any:
        error: Exception | None = None
        for attempt in range(1, self.config.retries + 1):
            self.stats.api_requests += 1
            try:
                response = self.session.get(f"{GAMMA_API_URL}{path}", params=params, timeout=self.config.timeout)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                error = exc
                self.stats.api_failures += 1
                if attempt < self.config.retries:
                    time.sleep(min(2 ** (attempt - 1), 12))
        raise RuntimeError(f"Gamma request failed: {error}")

    def events(self) -> Iterable[Mapping[str, Any]]:
        offset = 0
        yielded = 0

        while yielded < self.config.max_events:
            limit = min(
                self.config.page_size,
                self.config.max_events - yielded,
            )
            params: dict[str, Any] = {
                "limit": limit,
                "offset": offset,
                "order": "volume",
                "ascending": "false",
            }
            if self.config.active_only:
                params["active"] = "true"
            if not self.config.include_closed:
                params["closed"] = "false"

            try:
                payload = self.get_json("/events", params)
            except RuntimeError as error:
                message = str(error)

                # Gamma currently rejects sufficiently deep offset pages with
                # HTTP 422 instead of returning an empty list. Once at least
                # one page has completed, this is a pagination boundary rather
                # than a failed collection run.
                if (
                    offset > 0
                    and yielded > 0
                    and (
                        "422 Client Error" in message
                        or "Unprocessable Entity" in message
                    )
                ):
                    self.stats.pagination_exhausted = 1
                    self.stats.last_successful_offset = max(
                        offset - self.config.page_size,
                        0,
                    )
                    self.stats.pagination_warning = (
                        "Gamma pagination boundary reached at "
                        f"offset={offset}; collection completed using "
                        f"{self.stats.pages_fetched} successful pages."
                    )
                    break

                raise

            if not isinstance(payload, list):
                raise RuntimeError(
                    "Unexpected /events payload: "
                    f"{type(payload).__name__}"
                )

            self.stats.pages_fetched += 1
            self.stats.last_successful_offset = offset

            if not payload:
                break

            page_identity = tuple(
                text(item.get("id"))
                for item in payload
                if isinstance(item, Mapping)
            )
            if not page_identity:
                self.stats.pagination_warning = (
                    f"Gamma returned no valid events at offset={offset}."
                )
                break

            for item in payload:
                if isinstance(item, Mapping):
                    yield item
                    yielded += 1
                else:
                    self.stats.malformed_events += 1

                if yielded >= self.config.max_events:
                    break

            if len(payload) < limit:
                break

            offset += len(payload)


def event_record(event: Mapping[str, Any]) -> dict[str, Any] | None:
    event_id = text(event.get("id"))
    if not event_id:
        return None
    slug = text(event.get("slug"))
    return {
        "gamma_event_id": event_id,
        "ticker": text(event.get("ticker")),
        "slug": slug,
        "title": text(event.get("title")),
        "subtitle": text(event.get("subtitle")),
        "description": text(event.get("description")),
        "resolution_source": text(event.get("resolutionSource")),
        "category": text(event.get("category")),
        "subcategory": text(event.get("subcategory")),
        "start_time": text(first(event, "startDate", "startDateIso")),
        "end_time": text(first(event, "endDate", "endDateIso")),
        "creation_time": text(first(event, "creationDate", "createdAt")),
        "active": boolean(event.get("active")),
        "closed": boolean(event.get("closed")),
        "archived": boolean(event.get("archived")),
        "featured": boolean(event.get("featured")),
        "restricted": boolean(event.get("restricted")),
        "liquidity": number(event.get("liquidity")),
        "volume": number(event.get("volume")),
        "volume_24h": number(first(event, "volume24hr", "volume24h")),
        "open_interest": number(event.get("openInterest")),
        "polymarket_url": f"https://polymarket.com/event/{slug}" if slug else "",
        "image_url": text(event.get("image")),
        "icon_url": text(event.get("icon")),
        "source_hash": digest(event),
        "raw_json": stable_json(event),
    }


def outcome_data(market: Mapping[str, Any]) -> tuple[str, str, str, str, str, float | None, float | None]:
    outcomes = as_list(market.get("outcomes"))
    prices = as_list(market.get("outcomePrices"))
    tokens = as_list(market.get("clobTokenIds"))
    normalized = [text(item).lower() for item in outcomes]
    yes_index = normalized.index("yes") if "yes" in normalized else 0
    no_index = normalized.index("no") if "no" in normalized else 1
    yes_token = text(tokens[yes_index]) if yes_index < len(tokens) else ""
    no_token = text(tokens[no_index]) if no_index < len(tokens) else ""
    yes_price = optional_number(prices[yes_index]) if yes_index < len(prices) else None
    no_price = optional_number(prices[no_index]) if no_index < len(prices) else None
    return stable_json(outcomes), stable_json(prices), stable_json(tokens), yes_token, no_token, yes_price, no_price


def resolved(market: Mapping[str, Any]) -> int:
    status = text(first(market, "umaResolutionStatus", "umaResolutionStatuses", "resolutionStatus")).lower()
    if status in {"resolved", "finalized", "settled"}:
        return 1
    if boolean(market.get("closed")):
        prices = [optional_number(value) for value in as_list(market.get("outcomePrices"))]
        return int(any(value is not None and value >= 0.999 for value in prices))
    return 0


def market_record(market: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any] | None:
    condition_id = text(first(market, "conditionId", "condition_id"))
    if not condition_id:
        return None
    outcomes_json, prices_json, tokens_json, yes_token, no_token, yes_price, no_price = outcome_data(market)
    event_slug = text(event.get("slug"))
    slug = text(market.get("slug"))
    best_bid = optional_number(market.get("bestBid"))
    best_ask = optional_number(market.get("bestAsk"))
    spread = optional_number(market.get("spread"))
    if spread is None and best_bid is not None and best_ask is not None:
        spread = max(best_ask - best_bid, 0.0)
    return {
        "condition_id": condition_id,
        "gamma_market_id": text(market.get("id")),
        "question_id": text(first(market, "questionID", "questionId")),
        "slug": slug,
        "question": text(market.get("question")),
        "description": text(market.get("description")),
        "resolution_source": text(market.get("resolutionSource")),
        "category": text(first(market, "category", default=event.get("category"))),
        "market_type": text(first(market, "marketType", "market_type")),
        "format_type": text(market.get("formatType")),
        "group_item_title": text(market.get("groupItemTitle")),
        "group_item_threshold": text(market.get("groupItemThreshold")),
        "sports_market_type": text(first(market, "sportsMarketType", "sports_market_type")),
        "game_id": text(first(market, "gameId", "game_id")),
        "start_time": text(first(market, "startDate", "startDateIso")),
        "end_time": text(first(market, "endDate", "endDateIso")),
        "game_start_time": text(first(market, "gameStartTime", "eventStartTime")),
        "active": boolean(market.get("active")),
        "closed": boolean(market.get("closed")),
        "archived": boolean(market.get("archived")),
        "restricted": boolean(market.get("restricted")),
        "accepting_orders": boolean(first(market, "acceptingOrders", "accepting_orders")),
        "enable_order_book": boolean(market.get("enableOrderBook")),
        "resolved": resolved(market),
        "resolution_status": text(first(market, "umaResolutionStatus", "umaResolutionStatuses", "resolutionStatus")),
        "outcomes_json": outcomes_json,
        "outcome_prices_json": prices_json,
        "clob_token_ids_json": tokens_json,
        "yes_token_id": yes_token,
        "no_token_id": no_token,
        "yes_price": yes_price,
        "no_price": no_price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "last_trade_price": optional_number(market.get("lastTradePrice")),
        "liquidity": number(first(market, "liquidityNum", "liquidity")),
        "volume": number(first(market, "volumeNum", "volume")),
        "volume_24h": number(first(market, "volume24hr", "volume24h")),
        "volume_1w": number(first(market, "volume1wk", "volume1w")),
        "volume_1m": number(first(market, "volume1mo", "volume1m")),
        "open_interest": number(market.get("openInterest")),
        "minimum_tick_size": optional_number(market.get("orderPriceMinTickSize")),
        "minimum_order_size": optional_number(market.get("orderMinSize")),
        "neg_risk": boolean(first(market, "negRisk", "neg_risk")),
        "fees_enabled": boolean(first(market, "feesEnabled", "fees_enabled")),
        "polymarket_url": f"https://polymarket.com/event/{event_slug or slug}" if (event_slug or slug) else "",
        "image_url": text(market.get("image")),
        "icon_url": text(market.get("icon")),
        "source_hash": digest(market),
        "raw_json": stable_json(market),
    }


def upsert(connection: sqlite3.Connection, table: str, key: str, record: Mapping[str, Any], observed_at: str) -> str:
    existing = connection.execute(f"SELECT source_hash FROM {table} WHERE {key} = ?", (record[key],)).fetchone()
    if existing is None:
        columns = list(record)
        names = ",".join(columns + ["first_seen_at", "last_seen_at", "created_at", "updated_at"])
        marks = ",".join("?" for _ in range(len(columns) + 4))
        connection.execute(
            f"INSERT INTO {table} ({names}) VALUES ({marks})",
            tuple(record[column] for column in columns) + (observed_at, observed_at, observed_at, observed_at),
        )
        return "INSERTED"
    changed = existing["source_hash"] != record["source_hash"]
    columns = [column for column in record if column != key]
    assignments = ",".join(f"{column} = ?" for column in columns)
    connection.execute(
        f"UPDATE {table} SET {assignments}, last_seen_at = ?, updated_at = ? WHERE {key} = ?",
        tuple(record[column] for column in columns) + (observed_at, observed_at, record[key]),
    )
    return "UPDATED" if changed else "UNCHANGED"


def write_link(connection: sqlite3.Connection, event_id: str, condition_id: str, order: int, observed_at: str) -> None:
    connection.execute(
        """
        INSERT INTO event_market_map (gamma_event_id, condition_id, relationship_order, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(gamma_event_id, condition_id) DO UPDATE SET
            relationship_order = excluded.relationship_order,
            last_seen_at = excluded.last_seen_at
        """,
        (event_id, condition_id, order, observed_at, observed_at),
    )


def iter_tags(event: Mapping[str, Any], market: Mapping[str, Any]) -> Iterable[tuple[str, str, str]]:
    seen: set[tuple[str, str, str]] = set()
    for source in (event.get("tags"), market.get("tags")):
        for raw in as_list(source):
            mapping = as_mapping(raw)
            item = (
                text(mapping.get("id")) if mapping else "",
                text(mapping.get("slug")) if mapping else text(raw),
                text(first(mapping, "label", "name")) if mapping else text(raw),
            )
            if item != ("", "", "") and item not in seen:
                seen.add(item)
                yield item


def write_tag(connection: sqlite3.Connection, condition_id: str, item: tuple[str, str, str], observed_at: str) -> None:
    connection.execute(
        """
        INSERT INTO market_tags (condition_id, tag_id, tag_slug, tag_label, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(condition_id, tag_id, tag_slug) DO UPDATE SET
            tag_label = excluded.tag_label,
            last_seen_at = excluded.last_seen_at
        """,
        (condition_id, *item, observed_at, observed_at),
    )


def write_snapshot(connection: sqlite3.Connection, run: str, record: Mapping[str, Any], observed_at: str) -> bool:
    before = connection.total_changes
    connection.execute(
        """
        INSERT OR IGNORE INTO market_snapshots (
            run_id, condition_id, observed_at, active, closed, resolved, accepting_orders,
            yes_price, no_price, best_bid, best_ask, spread, last_trade_price,
            liquidity, volume, volume_24h, volume_1w, volume_1m, open_interest,
            outcome_prices_json, raw_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run,
            record["condition_id"],
            observed_at,
            record["active"],
            record["closed"],
            record["resolved"],
            record["accepting_orders"],
            record["yes_price"],
            record["no_price"],
            record["best_bid"],
            record["best_ask"],
            record["spread"],
            record["last_trade_price"],
            record["liquidity"],
            record["volume"],
            record["volume_24h"],
            record["volume_1w"],
            record["volume_1m"],
            record["open_interest"],
            record["outcome_prices_json"],
            record["raw_json"],
            observed_at,
        ),
    )
    return connection.total_changes > before


def start_run(connection: sqlite3.Connection, config: Config, stats: Stats) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO universal_market_collector_runs (
            run_id, started_at, status, engine_version, database_path,
            include_closed, active_only, page_size, max_events, created_at, updated_at
        ) VALUES (?, ?, 'RUNNING', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stats.run_id,
            stats.started_at,
            ENGINE_VERSION,
            str(config.database_path),
            int(config.include_closed),
            int(config.active_only),
            config.page_size,
            config.max_events,
            now,
            now,
        ),
    )
    connection.commit()


def finish_run(connection: sqlite3.Connection, stats: Stats, status: str, runtime: float, error: str) -> None:
    connection.execute(
        """
        UPDATE universal_market_collector_runs SET
            completed_at=?, status=?, api_requests=?, api_failures=?, pages_fetched=?,
            events_fetched=?, events_inserted=?, events_updated=?, markets_seen=?,
            markets_inserted=?, markets_updated=?, markets_unchanged=?, snapshots_inserted=?,
            links_written=?, tags_written=?, malformed_events=?, malformed_markets=?,
            pagination_exhausted=?, last_successful_offset=?, pagination_warning=?,
            runtime_seconds=?, error_message=?, updated_at=?
        WHERE run_id=?
        """,
        (
            utc_now(), status, stats.api_requests, stats.api_failures, stats.pages_fetched,
            stats.events_fetched, stats.events_inserted, stats.events_updated, stats.markets_seen,
            stats.markets_inserted, stats.markets_updated, stats.markets_unchanged,
            stats.snapshots_inserted, stats.links_written, stats.tags_written,
            stats.malformed_events, stats.malformed_markets,
            stats.pagination_exhausted, stats.last_successful_offset,
            stats.pagination_warning, runtime, error, utc_now(), stats.run_id,
        ),
    )
    connection.commit()


def collect(connection: sqlite3.Connection, client: GammaClient, config: Config, stats: Stats) -> list[dict[str, Any]]:
    observed_at = utc_now()
    samples: list[dict[str, Any]] = []
    for event in client.events():
        stats.events_fetched += 1
        normalized_event = event_record(event)
        if normalized_event is None:
            stats.malformed_events += 1
            continue
        state = upsert(connection, "event_catalog", "gamma_event_id", normalized_event, observed_at)
        stats.events_inserted += int(state == "INSERTED")
        stats.events_updated += int(state == "UPDATED")

        for index, raw_market in enumerate(as_list(event.get("markets"))):
            market = as_mapping(raw_market)
            if not market:
                stats.malformed_markets += 1
                continue
            normalized_market = market_record(market, event)
            if normalized_market is None:
                stats.malformed_markets += 1
                continue
            stats.markets_seen += 1
            market_state = upsert(connection, "market_catalog", "condition_id", normalized_market, observed_at)
            stats.markets_inserted += int(market_state == "INSERTED")
            stats.markets_updated += int(market_state == "UPDATED")
            stats.markets_unchanged += int(market_state == "UNCHANGED")
            write_link(connection, normalized_event["gamma_event_id"], normalized_market["condition_id"], index, observed_at)
            stats.links_written += 1
            for item in iter_tags(event, market):
                write_tag(connection, normalized_market["condition_id"], item, observed_at)
                stats.tags_written += 1
            if config.save_snapshots and write_snapshot(connection, stats.run_id, normalized_market, observed_at):
                stats.snapshots_inserted += 1
            if len(samples) < config.display_limit:
                samples.append(normalized_market)
        connection.commit()
    return samples


def print_line(title: str) -> None:
    print("=" * 118)
    print(title)
    print("=" * 118)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Polymarket events and markets from the public Gamma API.")
    parser.add_argument("--database", default=os.getenv("POLYMARKET_DATABASE_PATH", str(DEFAULT_DATABASE_PATH)))
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    parser.add_argument("--include-closed", action="store_true")
    parser.add_argument("--all-statuses", action="store_true")
    parser.add_argument("--no-snapshots", action="store_true")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--display-limit", type=int, default=10)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not 1 <= args.page_size <= 500:
        parser.error("--page-size must be between 1 and 500")
    if args.max_events <= 0 or args.timeout <= 0 or args.retries <= 0 or args.display_limit < 0:
        parser.error("numeric arguments must be positive; --display-limit may be zero")

    config = Config(
        database_path=resolve_path(args.database),
        page_size=args.page_size,
        max_events=args.max_events,
        include_closed=bool(args.include_closed),
        active_only=not bool(args.all_statuses),
        save_snapshots=not bool(args.no_snapshots),
        timeout=args.timeout,
        retries=args.retries,
        display_limit=args.display_limit,
    )
    stats = Stats(run_id=run_id(), started_at=utc_now())

    print_line(f"UNIVERSAL MARKET COLLECTOR v{ENGINE_VERSION}")
    print(f"Run ID:          {stats.run_id}")
    print(f"Database:        {config.database_path}")
    print(f"Active only:     {config.active_only}")
    print(f"Include closed:  {config.include_closed}")
    print(f"Save snapshots:  {config.save_snapshots}")
    print(f"Maximum events:  {config.max_events}")

    connection = connect(config.database_path)
    ensure_schema(connection)
    start_run(connection, config, stats)
    started = time.perf_counter()
    status = "SUCCESS"
    error = ""
    samples: list[dict[str, Any]] = []

    try:
        samples = collect(connection, GammaClient(config, stats), config, stats)
        if stats.events_fetched == 0:
            status = "NO_DATA"
        elif stats.markets_seen == 0:
            status = "NO_MARKETS"
    except KeyboardInterrupt:
        status = "INTERRUPTED"
        error = "Collector interrupted by user"
    except Exception as exc:
        status = "FAILED"
        error = str(exc)
        print(f"Collector failed: {error}", file=sys.stderr)
    finally:
        runtime = time.perf_counter() - started
        finish_run(connection, stats, status, runtime, error)
        connection.close()

    if samples:
        print()
        print_line("SAMPLE COLLECTED MARKETS")
        for index, row in enumerate(samples, 1):
            yes = "-" if row["yes_price"] is None else f"{row['yes_price']:.3f}"
            state = "CLOSED" if row["closed"] else "OPEN"
            print(f"{index:>3}. {state:<6} YES={yes:<7} Vol=${row['volume']:>12,.0f} Liq=${row['liquidity']:>10,.0f} | {row['question'][:68]}")

    print()
    print_line("UNIVERSAL MARKET COLLECTOR HEALTH SUMMARY")
    print(f"Status:                     {status}")
    print(f"Events fetched:             {stats.events_fetched:,}")
    print(f"Events inserted/updated:    {stats.events_inserted:,}/{stats.events_updated:,}")
    print(f"Markets seen:               {stats.markets_seen:,}")
    print(f"Markets new/updated/same:   {stats.markets_inserted:,}/{stats.markets_updated:,}/{stats.markets_unchanged:,}")
    print(f"Snapshots inserted:         {stats.snapshots_inserted:,}")
    print(f"Event-market links:         {stats.links_written:,}")
    print(f"Tag links:                  {stats.tags_written:,}")
    print(f"API requests/failures:      {stats.api_requests:,}/{stats.api_failures:,}")
    print(f"Pages fetched:              {stats.pages_fetched:,}")
    print(f"Malformed events/markets:   {stats.malformed_events:,}/{stats.malformed_markets:,}")
    print(f"Pagination exhausted:       {bool(stats.pagination_exhausted)}")
    print(f"Last successful offset:     {stats.last_successful_offset:,}")
    print(f"Runtime:                    {runtime:.2f}s")
    if stats.pagination_warning:
        print(f"Warning:                    {stats.pagination_warning}")
    if error:
        print(f"Error:                      {error}")

    return 0 if status in {"SUCCESS", "NO_DATA", "NO_MARKETS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())