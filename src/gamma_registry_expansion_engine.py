from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"
GAMMA_API = "https://gamma-api.polymarket.com"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_PAGE_LIMIT = 100
DEFAULT_MAX_PAGES = 500
DEFAULT_REQUEST_DELAY = 0.10
DEFAULT_TIMEOUT = 30
DEFAULT_DISPLAY_LIMIT = 30
DEFAULT_TARGET_BATCH_SIZE = 25
MAX_RETRIES = 5


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


def normalize_identifier(value: Any) -> str:
    return clean_text(value).lower()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def parse_json_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (list, dict, int, float, bool)):
        return value

    raw = clean_text(value)

    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def chunked(
    values: list[str],
    size: int,
) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(f"Database not found: {DB}")

    connection = sqlite3.connect(DB, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
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
            WHERE type='table'
              AND name=?
            """,
            (table_name,),
        ).fetchone()
        is not None
    )


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not table_exists(connection, table_name):
        return set()

    return {
        clean_text(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def first_existing(
    columns: set[str],
    candidates: tuple[str, ...],
) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


def require_table(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    if not table_exists(connection, table_name):
        raise RuntimeError(
            f"Required table is missing: {table_name}"
        )


# =============================================================================
# ENGINE TABLES
# =============================================================================


def create_engine_tables() -> None:
    connection = connect_database()

    try:
        require_table(connection, "gamma_markets")
        require_table(connection, "gamma_market_outcomes")

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS gamma_registry_expansion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                active_keyset_pages INTEGER NOT NULL DEFAULT 0,
                active_markets_received INTEGER NOT NULL DEFAULT 0,

                targeted_condition_ids INTEGER NOT NULL DEFAULT 0,
                targeted_batches INTEGER NOT NULL DEFAULT 0,
                targeted_markets_received INTEGER NOT NULL DEFAULT 0,

                unique_markets_received INTEGER NOT NULL DEFAULT 0,
                markets_inserted INTEGER NOT NULL DEFAULT 0,
                markets_updated INTEGER NOT NULL DEFAULT 0,
                outcomes_inserted INTEGER NOT NULL DEFAULT 0,
                outcomes_updated INTEGER NOT NULL DEFAULT 0,

                unresolved_before INTEGER NOT NULL DEFAULT 0,
                unresolved_after INTEGER NOT NULL DEFAULT 0,
                recovered_condition_ids INTEGER NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS gamma_registry_expansion_checkpoints (
                checkpoint_name TEXT PRIMARY KEY,

                next_cursor TEXT,
                last_market_updated_at TEXT,
                last_success_at TEXT,
                last_error_at TEXT,
                last_error_message TEXT,
                metadata_json TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gamma_registry_expansion_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                run_id INTEGER,
                stage TEXT NOT NULL,
                request_url TEXT,
                condition_ids_json TEXT,
                http_status INTEGER,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                response_body_preview TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_gamma_registry_expansion_errors_run
            ON gamma_registry_expansion_errors(
                run_id,
                created_at DESC
            );

            CREATE TABLE IF NOT EXISTS gamma_registry_expansion_recovery (
                condition_id TEXT PRIMARY KEY,

                first_requested_at TEXT NOT NULL,
                last_requested_at TEXT NOT NULL,

                recovered INTEGER NOT NULL DEFAULT 0,
                gamma_market_id TEXT,
                market_slug TEXT,
                event_slug TEXT,

                recovery_method TEXT,
                recovered_at TEXT,

                request_count INTEGER NOT NULL DEFAULT 0,
                last_error_message TEXT,
                metadata_json TEXT
            );
            """
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# HTTP
# =============================================================================


def build_url(
    path: str,
    params: dict[str, Any],
) -> str:
    query = urllib.parse.urlencode(
        params,
        doseq=True,
    )

    return (
        f"{GAMMA_API}{path}"
        + (
            f"?{query}"
            if query
            else ""
        )
    )


def request_json_once(
    url: str,
    timeout: int,
) -> tuple[Any, int, str]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "PolymarketIntelligencePlatform/"
                "gamma-registry-expansion-v1"
            ),
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            body = response.read().decode(
                "utf-8",
                errors="replace",
            )

            return (
                json.loads(body),
                response.status,
                body[:2000],
            )

    except urllib.error.HTTPError as error:
        body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        wrapped = RuntimeError(
            f"HTTP {error.code}: {error.reason}"
            + (
                f" | body={body[:1000]}"
                if body
                else ""
            )
        )

        setattr(wrapped, "http_status", error.code)
        setattr(wrapped, "response_body", body[:2000])
        setattr(wrapped, "request_url", url)

        raise wrapped from error


def request_json(
    url: str,
    timeout: int,
) -> Any:
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            payload, _, _ = request_json_once(
                url=url,
                timeout=timeout,
            )

            return payload

        except Exception as error:
            last_error = error

            status = safe_int(
                getattr(
                    error,
                    "http_status",
                    0,
                )
            )

            retryable = (
                status in {
                    0,
                    425,
                    429,
                    500,
                    502,
                    503,
                    504,
                }
            )

            if not retryable:
                break

            if attempt < MAX_RETRIES - 1:
                time.sleep(
                    min(
                        2 ** attempt,
                        16,
                    )
                )

    assert last_error is not None
    raise last_error


# =============================================================================
# GAMMA FETCHING
# =============================================================================


def fetch_active_markets_keyset(
    page_limit: int,
    max_pages: int,
    timeout: int,
    request_delay: float,
) -> tuple[list[dict[str, Any]], int]:
    """
    Stable keyset crawl of current active markets.

    Gamma's keyset endpoint returns:
      {
        "markets": [...],
        "next_cursor": "..."
      }
    """
    all_markets: list[dict[str, Any]] = []
    cursor = ""
    pages = 0

    while pages < max_pages:
        params: dict[str, Any] = {
            "limit": page_limit,
            "ascending": "true",
            "active": "true",
            "closed": "false",
        }

        if cursor:
            params["after_cursor"] = cursor

        url = build_url(
            "/markets/keyset",
            params,
        )

        payload = request_json(
            url=url,
            timeout=timeout,
        )

        if not isinstance(payload, dict):
            raise RuntimeError(
                "Unexpected /markets/keyset response type: "
                f"{type(payload).__name__}"
            )

        markets = payload.get(
            "markets",
            [],
        )

        if not isinstance(markets, list):
            raise RuntimeError(
                "Keyset response did not contain a markets list."
            )

        pages += 1

        page_markets = [
            item
            for item in markets
            if isinstance(item, dict)
        ]

        all_markets.extend(
            page_markets
        )

        print(
            f"Active keyset page {pages}: "
            f"{len(page_markets)} markets "
            f"(total {len(all_markets):,})"
        )

        next_cursor = clean_text(
            payload.get(
                "next_cursor"
            )
            or payload.get(
                "nextCursor"
            )
        )

        if (
            not page_markets
            or not next_cursor
            or next_cursor == cursor
        ):
            break

        cursor = next_cursor

        if request_delay > 0:
            time.sleep(request_delay)

    return all_markets, pages


def fetch_markets_by_condition_ids(
    condition_ids: list[str],
    batch_size: int,
    timeout: int,
    request_delay: float,
    continue_on_batch_failure: bool,
    run_id: int,
) -> tuple[
    list[dict[str, Any]],
    int,
]:
    all_markets: list[dict[str, Any]] = []
    batch_count = 0

    for batch_index, batch in enumerate(
        chunked(
            condition_ids,
            batch_size,
        ),
        start=1,
    ):
        batch_count += 1

        params = {
            "condition_ids": batch,
            "limit": max(
                len(batch),
                1,
            ),
            "offset": 0,
        }

        url = build_url(
            "/markets",
            params,
        )

        try:
            payload = request_json(
                url=url,
                timeout=timeout,
            )

            if not isinstance(payload, list):
                raise RuntimeError(
                    "Unexpected targeted /markets response type: "
                    f"{type(payload).__name__}"
                )

            page_markets = [
                item
                for item in payload
                if isinstance(item, dict)
            ]

            all_markets.extend(
                page_markets
            )

            print(
                f"Targeted condition batch "
                f"{batch_index}: "
                f"{len(batch)} requested, "
                f"{len(page_markets)} returned"
            )

        except Exception as error:
            log_error(
                run_id=run_id,
                stage="TARGETED_CONDITION_LOOKUP",
                request_url=url,
                condition_ids=batch,
                error=error,
            )

            print(
                f"Targeted condition batch "
                f"{batch_index} failed: "
                f"{type(error).__name__}: {error}"
            )

            if not continue_on_batch_failure:
                raise

        if request_delay > 0:
            time.sleep(request_delay)

    return all_markets, batch_count


# =============================================================================
# MISSING CONDITION DISCOVERY
# =============================================================================


def load_unresolved_condition_ids() -> list[str]:
    """
    Prioritize unresolved identities from prediction/flow/memory enrichment.
    Fall back to the registry's unmapped table when enrichment is unavailable.
    """
    connection = connect_database()

    try:
        values: set[str] = set()

        if table_exists(
            connection,
            "market_identity_enrichments",
        ):
            rows = connection.execute(
                """
                SELECT DISTINCT source_condition_id
                FROM market_identity_enrichments
                WHERE enrichment_status='UNRESOLVED'
                  AND source_condition_id IS NOT NULL
                  AND TRIM(source_condition_id) <> ''
                """
            ).fetchall()

            values.update(
                normalize_identifier(
                    row["source_condition_id"]
                )
                for row in rows
                if normalize_identifier(
                    row["source_condition_id"]
                )
            )

        if table_exists(
            connection,
            "market_identifier_unmapped",
        ):
            rows = connection.execute(
                """
                SELECT DISTINCT source_condition_id
                FROM market_identifier_unmapped
                WHERE source_condition_id IS NOT NULL
                  AND TRIM(source_condition_id) <> ''
                """
            ).fetchall()

            values.update(
                normalize_identifier(
                    row["source_condition_id"]
                )
                for row in rows
                if normalize_identifier(
                    row["source_condition_id"]
                )
            )

        return sorted(values)

    finally:
        connection.close()


def load_existing_gamma_condition_ids() -> set[str]:
    connection = connect_database()

    try:
        columns = table_columns(
            connection,
            "gamma_markets",
        )

        condition_column = first_existing(
            columns,
            (
                "condition_id",
                "conditionId",
                "conditionid",
            ),
        )

        if condition_column is None:
            raise RuntimeError(
                "gamma_markets has no recognizable condition-ID column."
            )

        rows = connection.execute(
            f"""
            SELECT "{condition_column}" AS condition_id
            FROM gamma_markets
            WHERE "{condition_column}" IS NOT NULL
              AND TRIM("{condition_column}") <> ''
            """
        ).fetchall()

        return {
            normalize_identifier(
                row["condition_id"]
            )
            for row in rows
            if normalize_identifier(
                row["condition_id"]
            )
        }

    finally:
        connection.close()


# =============================================================================
# ADAPTIVE UPSERT
# =============================================================================



EVENT_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "gamma_event_id": (
        "gamma_event_id",
        "event_id",
        "id",
    ),
    "slug": (
        "slug",
        "event_slug",
    ),
    "ticker": (
        "ticker",
    ),
    "title": (
        "title",
        "name",
    ),
    "description": (
        "description",
    ),
    "category": (
        "category",
    ),
    "subcategory": (
        "subcategory",
        "subCategory",
    ),
    "active": (
        "active",
        "is_active",
    ),
    "closed": (
        "closed",
        "is_closed",
    ),
    "archived": (
        "archived",
        "is_archived",
    ),
    "restricted": (
        "restricted",
        "is_restricted",
    ),
    "featured": (
        "featured",
        "is_featured",
    ),
    "start_time": (
        "start_time",
        "start_date",
        "startDate",
        "start_at",
    ),
    "end_time": (
        "end_time",
        "end_date",
        "endDate",
        "end_at",
    ),
    "created_at_gamma": (
        "created_at_gamma",
        "createdAt",
        "created_at",
    ),
    "updated_at_gamma": (
        "updated_at_gamma",
        "updatedAt",
        "updated_at",
    ),
    "liquidity": (
        "liquidity",
        "liquidity_num",
        "liquidityNum",
    ),
    "volume": (
        "volume",
        "volume_num",
        "volumeNum",
    ),
    "volume_24h": (
        "volume_24h",
        "volume24hr",
        "volume24h",
    ),
    "open_interest": (
        "open_interest",
        "openInterest",
    ),
    "market_count": (
        "market_count",
    ),
    "tags_json": (
        "tags_json",
    ),
    "series_json": (
        "series_json",
    ),
    "image_url": (
        "image_url",
        "image",
    ),
    "icon_url": (
        "icon_url",
        "icon",
    ),
    "raw_payload_json": (
        "raw_payload_json",
        "raw_json",
    ),
    "first_seen_at": (
        "first_seen_at",
    ),
    "last_seen_at": (
        "last_seen_at",
    ),
    "refreshed_at": (
        "refreshed_at",
    ),
}


def extract_embedded_events(
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Extract unique embedded Gamma event objects from market payloads.

    Gamma market responses commonly include an `events` list. These parent
    events must be inserted before child gamma_markets rows because the local
    database enforces:
        gamma_markets.gamma_event_id -> gamma_events.gamma_event_id
    """
    events_by_id: dict[str, dict[str, Any]] = {}

    for market in markets:
        embedded_events = market.get("events")

        if not isinstance(embedded_events, list):
            continue

        for event in embedded_events:
            if not isinstance(event, dict):
                continue

            event_id = clean_text(
                event.get("id")
                or event.get("eventId")
                or event.get("event_id")
            )

            if not event_id:
                continue

            events_by_id[event_id] = event

    return list(events_by_id.values())


def canonical_event_values(
    event: dict[str, Any],
) -> dict[str, Any]:
    now_iso = utc_now_iso()

    markets = event.get("markets")
    market_count = (
        len(markets)
        if isinstance(markets, list)
        else safe_int(
            event.get("marketCount"),
            0,
        )
    )

    tags = event.get("tags")
    series = event.get("series")

    return {
        "gamma_event_id": clean_text(
            event.get("id")
            or event.get("eventId")
            or event.get("event_id")
        ),
        "slug": clean_text(
            event.get("slug")
        ),
        "ticker": clean_text(
            event.get("ticker")
        ),
        "title": (
            clean_text(event.get("title"))
            or clean_text(event.get("name"))
            or "Untitled Gamma event"
        ),
        "description": clean_text(
            event.get("description")
        ),
        "category": clean_text(
            event.get("category")
        ),
        "subcategory": clean_text(
            event.get("subcategory")
            or event.get("subCategory")
        ),
        "active": int(
            bool(event.get("active"))
        ),
        "closed": int(
            bool(event.get("closed"))
        ),
        "archived": int(
            bool(event.get("archived"))
        ),
        "restricted": int(
            bool(event.get("restricted"))
        ),
        "featured": int(
            bool(event.get("featured"))
        ),
        "start_time": clean_text(
            event.get("startDate")
            or event.get("startTime")
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
        "tags_json": stable_json(
            tags if isinstance(tags, list) else []
        ),
        "series_json": stable_json(
            series if isinstance(series, list) else []
        ),
        "image_url": clean_text(
            event.get("image")
        ),
        "icon_url": clean_text(
            event.get("icon")
        ),
        "raw_payload_json": stable_json(event),
        "first_seen_at": now_iso,
        "last_seen_at": now_iso,
        "refreshed_at": now_iso,
    }


def upsert_gamma_events(
    events: list[dict[str, Any]],
) -> tuple[int, int]:
    if not events:
        return 0, 0

    column_map = resolve_existing_columns(
        "gamma_events",
        EVENT_FIELD_CANDIDATES,
    )

    event_id_column = column_map.get(
        "gamma_event_id"
    )

    if not event_id_column:
        raise RuntimeError(
            "Unable to find gamma event-ID column in gamma_events."
        )

    connection = connect_database()
    inserted = 0
    updated = 0

    try:
        connection.execute("BEGIN IMMEDIATE")

        for raw_event in events:
            values = canonical_event_values(
                raw_event
            )

            event_id = values[
                "gamma_event_id"
            ]

            if not event_id:
                continue

            existing = connection.execute(
                f"""
                SELECT 1
                FROM gamma_events
                WHERE TRIM("{event_id_column}")=?
                LIMIT 1
                """,
                (event_id,),
            ).fetchone()

            available_values = {
                column_map[logical]: value
                for logical, value in values.items()
                if logical in column_map
            }

            if existing:
                first_seen_column = column_map.get(
                    "first_seen_at"
                )

                update_columns = [
                    column
                    for column in available_values
                    if (
                        column != event_id_column
                        and column != first_seen_column
                    )
                ]

                assignments = ", ".join(
                    f'"{column}"=?'
                    for column in update_columns
                )

                parameters = [
                    available_values[column]
                    for column in update_columns
                ]

                if assignments:
                    connection.execute(
                        f"""
                        UPDATE gamma_events
                        SET {assignments}
                        WHERE TRIM("{event_id_column}")=?
                        """,
                        (
                            *parameters,
                            event_id,
                        ),
                    )

                updated += 1

            else:
                columns = list(
                    available_values
                )

                placeholders = ", ".join(
                    "?"
                    for _ in columns
                )

                connection.execute(
                    f"""
                    INSERT INTO gamma_events (
                        {", ".join(f'"{column}"' for column in columns)}
                    )
                    VALUES ({placeholders})
                    """,
                    tuple(
                        available_values[column]
                        for column in columns
                    ),
                )

                inserted += 1

        connection.commit()

        return inserted, updated

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


MARKET_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "condition_id": (
        "condition_id",
        "conditionId",
        "conditionid",
    ),
    "gamma_market_id": (
        "gamma_market_id",
        "market_id",
        "id",
    ),
    "gamma_event_id": (
        "gamma_event_id",
        "event_id",
    ),
    "question": (
        "question",
        "title",
    ),
    "question_id": (
        "question_id",
        "questionId",
    ),
    "description": (
        "description",
    ),
    "market_type": (
        "market_type",
        "marketType",
    ),
    "slug": (
        "slug",
        "market_slug",
    ),
    "event_slug": (
        "event_slug",
        "eventSlug",
    ),
    "category": (
        "category",
    ),
    "start_date": (
        "start_date",
        "startDate",
        "start_at",
        "start_time",
    ),
    "end_date": (
        "end_date",
        "endDate",
        "end_at",
        "end_time",
    ),
    "game_start_time": (
        "game_start_time",
        "gameStartTime",
    ),
    "active": (
        "active",
        "is_active",
    ),
    "resolved": (
        "resolved",
        "is_resolved",
    ),
    "restricted": (
        "restricted",
        "is_restricted",
    ),
    "neg_risk": (
        "neg_risk",
        "negRisk",
    ),
    "closed": (
        "closed",
        "is_closed",
    ),
    "archived": (
        "archived",
        "is_archived",
    ),
    "accepting_orders": (
        "accepting_orders",
        "acceptingOrders",
    ),
    "enable_order_book": (
        "enable_order_book",
        "enableOrderBook",
    ),
    "volume": (
        "volume",
        "volume_num",
        "volumeNum",
    ),
    "volume_24h": (
        "volume_24h",
        "volume24hr",
        "volume24h",
    ),
    "liquidity": (
        "liquidity",
        "liquidity_num",
        "liquidityNum",
    ),
    "open_interest": (
        "open_interest",
        "openInterest",
    ),
    "spread": (
        "spread",
    ),
    "outcomes": (
        "outcomes",
        "outcomes_json",
    ),
    "outcome_prices": (
        "outcome_prices",
        "outcomePrices",
        "outcome_prices_json",
    ),
    "clob_token_ids": (
        "clob_token_ids",
        "clobTokenIds",
        "clob_token_ids_json",
    ),
    "outcome_count": (
        "outcome_count",
    ),
    "updated_at": (
        "updated_at",
        "updatedAt",
        "updated_at_gamma",
    ),
    "created_at": (
        "created_at",
        "createdAt",
        "created_at_gamma",
    ),
    "raw_json": (
        "raw_json",
        "raw_payload_json",
    ),
    "first_seen_at": (
        "first_seen_at",
    ),
    "last_seen_at": (
        "last_seen_at",
    ),
    "refreshed_at": (
        "refreshed_at",
    ),
}


def market_event_identity(
    market: dict[str, Any],
) -> tuple[str, str]:
    events = market.get("events")

    if isinstance(events, list) and events:
        first_event = events[0]

        if isinstance(first_event, dict):
            return (
                clean_text(
                    first_event.get("id")
                ),
                clean_text(
                    first_event.get("slug")
                ),
            )

    return (
        clean_text(
            market.get("eventId")
            or market.get("event_id")
        ),
        clean_text(
            market.get("eventSlug")
            or market.get("event_slug")
        ),
    )



def load_existing_gamma_event_ids() -> set[str]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT gamma_event_id
            FROM gamma_events
            WHERE gamma_event_id IS NOT NULL
              AND TRIM(gamma_event_id) <> ''
            """
        ).fetchall()

        return {
            clean_text(row["gamma_event_id"])
            for row in rows
            if clean_text(row["gamma_event_id"])
        }

    finally:
        connection.close()


def canonical_market_values(
    market: dict[str, Any],
) -> dict[str, Any]:
    event_id, event_slug = market_event_identity(
        market
    )

    now_iso = utc_now_iso()

    outcomes = parse_json_value(
        market.get("outcomes")
    )

    if not isinstance(outcomes, list):
        outcomes = []

    return {
        "condition_id": normalize_identifier(
            market.get(
                "conditionId"
            )
            or market.get(
                "condition_id"
            )
        ),
        "gamma_market_id": clean_text(
            market.get("id")
        ),
        "gamma_event_id": event_id,
        "question_id": clean_text(
            market.get("questionID")
            or market.get("questionId")
            or market.get("question_id")
        ),
        "question": (
            clean_text(
                market.get("question")
            )
            or clean_text(
                market.get("title")
            )
            or "Untitled Gamma market"
        ),
        "description": clean_text(
            market.get("description")
        ),
        "market_type": clean_text(
            market.get("marketType")
            or market.get("market_type")
        ),
        "slug": clean_text(
            market.get("slug")
        ),
        "event_slug": event_slug,
        "category": clean_text(
            market.get("category")
        ),
        "start_date": clean_text(
            market.get("startDate")
            or market.get("startDateIso")
        ),
        "end_date": clean_text(
            market.get("endDate")
            or market.get("endDateIso")
        ),
        "game_start_time": clean_text(
            market.get("gameStartTime")
        ),
        "active": int(
            bool(
                market.get("active")
            )
        ),
        "closed": int(
            bool(
                market.get("closed")
            )
        ),
        "archived": int(
            bool(
                market.get("archived")
            )
        ),
        "resolved": int(
            bool(
                market.get("resolved")
            )
        ),
        "restricted": int(
            bool(
                market.get("restricted")
            )
        ),
        "accepting_orders": int(
            bool(
                market.get("acceptingOrders")
            )
        ),
        "neg_risk": int(
            bool(
                market.get("negRisk")
            )
        ),
        "enable_order_book": int(
            bool(
                market.get("enableOrderBook")
            )
        ),
        "volume": safe_float(
            market.get("volumeNum")
            or market.get("volume")
        ),
        "volume_24h": safe_float(
            market.get("volume24hr")
            or market.get("volume24h")
        ),
        "liquidity": safe_float(
            market.get("liquidityNum")
            or market.get("liquidity")
        ),
        "open_interest": safe_float(
            market.get("openInterest")
        ),
        "spread": (
            safe_float(
                market.get("spread")
            )
            if market.get("spread") is not None
            else None
        ),
        "outcomes": stable_json(outcomes),
        "outcome_prices": stable_json(
            parse_json_value(
                market.get("outcomePrices")
            )
            or []
        ),
        "clob_token_ids": stable_json(
            parse_json_value(
                market.get("clobTokenIds")
            )
            or []
        ),
        "outcome_count": len(outcomes),
        "updated_at": clean_text(
            market.get("updatedAt")
        ),
        "created_at": clean_text(
            market.get("createdAt")
        ),
        "raw_json": stable_json(market),
        "first_seen_at": now_iso,
        "last_seen_at": now_iso,
        "refreshed_at": now_iso,
    }


def resolve_existing_columns(
    table_name: str,
    candidates: dict[str, tuple[str, ...]],
) -> dict[str, str]:
    connection = connect_database()

    try:
        columns = table_columns(
            connection,
            table_name,
        )

        output: dict[str, str] = {}

        for logical_name, names in candidates.items():
            column = first_existing(
                columns,
                names,
            )

            if column:
                output[
                    logical_name
                ] = column

        return output

    finally:
        connection.close()


def upsert_gamma_markets(
    markets: list[dict[str, Any]],
) -> tuple[int, int]:
    column_map = resolve_existing_columns(
        "gamma_markets",
        MARKET_FIELD_CANDIDATES,
    )

    condition_column = column_map.get(
        "condition_id"
    )

    if not condition_column:
        raise RuntimeError(
            "Unable to find condition-ID column in gamma_markets."
        )

    connection = connect_database()
    inserted = 0
    updated = 0

    known_event_ids = load_existing_gamma_event_ids()

    try:
        connection.execute("BEGIN IMMEDIATE")

        for raw_market in markets:
            values = canonical_market_values(
                raw_market
            )

            # Preserve referential integrity. If Gamma did not embed enough
            # parent-event data to create the referenced event, store NULL
            # temporarily rather than creating an orphan or failing the run.
            gamma_event_id = clean_text(
                values.get(
                    "gamma_event_id"
                )
            )

            if (
                gamma_event_id
                and gamma_event_id not in known_event_ids
            ):
                values[
                    "gamma_event_id"
                ] = None

            condition_id = values[
                "condition_id"
            ]

            if not condition_id:
                continue

            existing = connection.execute(
                f"""
                SELECT 1
                FROM gamma_markets
                WHERE LOWER(TRIM("{condition_column}"))=?
                LIMIT 1
                """,
                (condition_id,),
            ).fetchone()

            available_values = {
                column_map[logical]: value
                for logical, value in values.items()
                if logical in column_map
            }

            if existing:
                first_seen_column = column_map.get(
                    "first_seen_at"
                )

                update_columns = [
                    column
                    for column in available_values
                    if (
                        column != condition_column
                        and column != first_seen_column
                    )
                ]

                assignments = ", ".join(
                    f'"{column}"=?'
                    for column in update_columns
                )

                parameters = [
                    available_values[column]
                    for column in update_columns
                ]

                if assignments:
                    connection.execute(
                        f"""
                        UPDATE gamma_markets
                        SET {assignments}
                        WHERE LOWER(TRIM("{condition_column}"))=?
                        """,
                        (
                            *parameters,
                            condition_id,
                        ),
                    )

                updated += 1

            else:
                columns = list(
                    available_values
                )

                placeholders = ", ".join(
                    "?"
                    for _ in columns
                )

                connection.execute(
                    f"""
                    INSERT INTO gamma_markets (
                        {", ".join(f'"{column}"' for column in columns)}
                    )
                    VALUES ({placeholders})
                    """,
                    tuple(
                        available_values[
                            column
                        ]
                        for column in columns
                    ),
                )

                inserted += 1

        connection.commit()

        return inserted, updated

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


OUTCOME_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "outcome_key": (
        "outcome_key",
    ),
    "condition_id": (
        "condition_id",
        "conditionId",
    ),
    "gamma_market_id": (
        "gamma_market_id",
        "market_id",
    ),
    "gamma_event_id": (
        "gamma_event_id",
        "event_id",
    ),
    "outcome": (
        "outcome",
        "outcome_name",
    ),
    "outcome_index": (
        "outcome_index",
        "outcomeIndex",
    ),
    "token_id": (
        "token_id",
        "clob_token_id",
        "asset_id",
        "asset",
    ),
    "price": (
        "price",
        "outcome_price",
        "implied_price",
    ),
    "winner": (
        "winner",
        "is_winner",
    ),
    "first_seen_at": (
        "first_seen_at",
    ),
    "last_seen_at": (
        "last_seen_at",
    ),
    "refreshed_at": (
        "refreshed_at",
    ),
    "raw_json": (
        "raw_json",
        "raw_payload_json",
    ),
}


def market_outcome_rows(
    market: dict[str, Any],
) -> list[dict[str, Any]]:
    condition_id = normalize_identifier(
        market.get("conditionId")
        or market.get("condition_id")
    )

    gamma_market_id = clean_text(
        market.get("id")
    )

    gamma_event_id, _ = market_event_identity(
        market
    )

    outcomes = parse_json_value(
        market.get("outcomes")
    )

    token_ids = parse_json_value(
        market.get("clobTokenIds")
    )

    prices = parse_json_value(
        market.get("outcomePrices")
    )

    winners = parse_json_value(
        market.get("winningOutcomes")
        or market.get("winners")
    )

    if not isinstance(outcomes, list):
        outcomes = []

    if not isinstance(token_ids, list):
        token_ids = []

    if not isinstance(prices, list):
        prices = []

    winner_indexes: set[int] = set()

    if isinstance(winners, list):
        for item in winners:
            try:
                winner_indexes.add(
                    int(item)
                )
            except (TypeError, ValueError):
                pass

    now_iso = utc_now_iso()
    rows: list[dict[str, Any]] = []

    for index, outcome in enumerate(outcomes):
        token_id = (
            clean_text(token_ids[index])
            if index < len(token_ids)
            else ""
        )

        outcome_name = (
            clean_text(outcome)
            or f"Outcome {index}"
        )

        implied_price = (
            safe_float(prices[index])
            if index < len(prices)
            else None
        )

        outcome_key = (
            f"{gamma_market_id}:"
            f"{index}:"
            f"{token_id or normalize_identifier(outcome_name)}"
        )

        rows.append(
            {
                "outcome_key": outcome_key,
                "condition_id": condition_id,
                "gamma_market_id": gamma_market_id,
                "gamma_event_id": gamma_event_id,
                "outcome": outcome_name,
                "outcome_index": index,
                "token_id": token_id,
                "price": implied_price,
                "winner": int(
                    index in winner_indexes
                ),
                "first_seen_at": now_iso,
                "last_seen_at": now_iso,
                "refreshed_at": now_iso,
                "raw_json": stable_json(
                    {
                        "outcome_key": outcome_key,
                        "condition_id": condition_id,
                        "gamma_market_id": gamma_market_id,
                        "gamma_event_id": gamma_event_id,
                        "outcome": outcome_name,
                        "outcome_index": index,
                        "token_id": token_id,
                        "implied_price": implied_price,
                        "winner": int(
                            index in winner_indexes
                        ),
                    }
                ),
            }
        )

    return rows

def upsert_gamma_outcomes(
    markets: list[dict[str, Any]],
) -> tuple[int, int]:
    column_map = resolve_existing_columns(
        "gamma_market_outcomes",
        OUTCOME_FIELD_CANDIDATES,
    )

    outcome_key_column = column_map.get(
        "outcome_key"
    )

    condition_column = column_map.get(
        "condition_id"
    )

    outcome_index_column = column_map.get(
        "outcome_index"
    )

    token_column = column_map.get(
        "token_id"
    )

    if not outcome_key_column:
        raise RuntimeError(
            "Unable to find outcome_key column in gamma_market_outcomes."
        )

    if not condition_column:
        raise RuntimeError(
            "Unable to find condition-ID column in gamma_market_outcomes."
        )

    connection = connect_database()
    inserted = 0
    updated = 0

    try:
        connection.execute("BEGIN IMMEDIATE")

        for market in markets:
            for values in market_outcome_rows(
                market
            ):
                if not values[
                    "condition_id"
                ]:
                    continue

                where_parts = [
                    f'TRIM("{outcome_key_column}")=?'
                ]

                where_params: list[Any] = [
                    values[
                        "outcome_key"
                    ]
                ]

                existing = connection.execute(
                    f"""
                    SELECT 1
                    FROM gamma_market_outcomes
                    WHERE {" AND ".join(where_parts)}
                    LIMIT 1
                    """,
                    tuple(where_params),
                ).fetchone()

                available_values = {
                    column_map[logical]: value
                    for logical, value in values.items()
                    if logical in column_map
                }

                if existing:
                    first_seen_column = column_map.get(
                        "first_seen_at"
                    )

                    update_columns = [
                        column
                        for column in available_values
                        if (
                            column != outcome_key_column
                            and column != first_seen_column
                        )
                    ]

                    assignments = ", ".join(
                        f'"{column}"=?'
                        for column in update_columns
                    )

                    parameters = [
                        available_values[column]
                        for column in update_columns
                    ]

                    if assignments:
                        connection.execute(
                            f"""
                            UPDATE gamma_market_outcomes
                            SET {assignments}
                            WHERE {" AND ".join(where_parts)}
                            """,
                            (
                                *parameters,
                                *where_params,
                            ),
                        )

                    updated += 1

                else:
                    columns = list(
                        available_values
                    )

                    placeholders = ", ".join(
                        "?"
                        for _ in columns
                    )

                    connection.execute(
                        f"""
                        INSERT INTO gamma_market_outcomes (
                            {", ".join(f'"{column}"' for column in columns)}
                        )
                        VALUES ({placeholders})
                        """,
                        tuple(
                            available_values[
                                column
                            ]
                            for column in columns
                        ),
                    )

                    inserted += 1

        connection.commit()

        return inserted, updated

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RECOVERY / LOGGING
# =============================================================================


def log_error(
    run_id: int,
    stage: str,
    request_url: str,
    condition_ids: list[str],
    error: Exception,
) -> None:
    connection = connect_database()

    try:
        connection.execute(
            """
            INSERT INTO gamma_registry_expansion_errors (
                run_id,
                stage,
                request_url,
                condition_ids_json,
                http_status,
                error_type,
                error_message,
                response_body_preview,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                stage,
                request_url,
                stable_json(condition_ids),
                safe_int(
                    getattr(
                        error,
                        "http_status",
                        0,
                    )
                ),
                type(error).__name__,
                str(error),
                clean_text(
                    getattr(
                        error,
                        "response_body",
                        "",
                    )
                ),
                utc_now_iso(),
            ),
        )

        connection.commit()

    finally:
        connection.close()


def update_recovery_table(
    requested_condition_ids: list[str],
    returned_markets: list[dict[str, Any]],
) -> None:
    returned_lookup = {
        normalize_identifier(
            market.get("conditionId")
            or market.get("condition_id")
        ): market
        for market in returned_markets
        if normalize_identifier(
            market.get("conditionId")
            or market.get("condition_id")
        )
    }

    now_iso = utc_now_iso()
    connection = connect_database()

    try:
        connection.execute("BEGIN IMMEDIATE")

        for condition_id in requested_condition_ids:
            market = returned_lookup.get(
                condition_id
            )

            event_id, event_slug = (
                market_event_identity(market)
                if market
                else ("", "")
            )

            connection.execute(
                """
                INSERT INTO gamma_registry_expansion_recovery (
                    condition_id,
                    first_requested_at,
                    last_requested_at,
                    recovered,
                    gamma_market_id,
                    market_slug,
                    event_slug,
                    recovery_method,
                    recovered_at,
                    request_count,
                    last_error_message,
                    metadata_json
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?
                )
                ON CONFLICT(condition_id) DO UPDATE SET
                    last_requested_at=excluded.last_requested_at,
                    recovered=MAX(
                        gamma_registry_expansion_recovery.recovered,
                        excluded.recovered
                    ),
                    gamma_market_id=CASE
                        WHEN excluded.gamma_market_id <> ''
                        THEN excluded.gamma_market_id
                        ELSE gamma_registry_expansion_recovery.gamma_market_id
                    END,
                    market_slug=CASE
                        WHEN excluded.market_slug <> ''
                        THEN excluded.market_slug
                        ELSE gamma_registry_expansion_recovery.market_slug
                    END,
                    event_slug=CASE
                        WHEN excluded.event_slug <> ''
                        THEN excluded.event_slug
                        ELSE gamma_registry_expansion_recovery.event_slug
                    END,
                    recovery_method=CASE
                        WHEN excluded.recovered=1
                        THEN excluded.recovery_method
                        ELSE gamma_registry_expansion_recovery.recovery_method
                    END,
                    recovered_at=CASE
                        WHEN excluded.recovered=1
                        THEN excluded.recovered_at
                        ELSE gamma_registry_expansion_recovery.recovered_at
                    END,
                    request_count=
                        gamma_registry_expansion_recovery.request_count + 1,
                    last_error_message=excluded.last_error_message,
                    metadata_json=excluded.metadata_json
                """,
                (
                    condition_id,
                    now_iso,
                    now_iso,
                    int(market is not None),
                    clean_text(
                        market.get("id")
                        if market
                        else ""
                    ),
                    clean_text(
                        market.get("slug")
                        if market
                        else ""
                    ),
                    event_slug,
                    (
                        "EXACT_CONDITION_ID_GAMMA_LOOKUP"
                        if market
                        else "NOT_RETURNED_BY_GAMMA"
                    ),
                    (
                        now_iso
                        if market
                        else None
                    ),
                    (
                        ""
                        if market
                        else "Gamma returned no exact market for this condition ID."
                    ),
                    stable_json(
                        {
                            "event_id": event_id,
                        }
                    ),
                ),
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def start_run() -> tuple[int, datetime]:
    started_at = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO gamma_registry_expansion_runs (
                started_at,
                status
            )
            VALUES (?, 'RUNNING')
            """,
            (started_at.isoformat(),),
        )

        connection.commit()

        return cursor.lastrowid, started_at

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started_at: datetime,
    status: str,
    stats: dict[str, int],
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE gamma_registry_expansion_runs
            SET
                finished_at=?,
                elapsed_seconds=?,
                active_keyset_pages=?,
                active_markets_received=?,
                targeted_condition_ids=?,
                targeted_batches=?,
                targeted_markets_received=?,
                unique_markets_received=?,
                markets_inserted=?,
                markets_updated=?,
                outcomes_inserted=?,
                outcomes_updated=?,
                unresolved_before=?,
                unresolved_after=?,
                recovered_condition_ids=?,
                status=?,
                error_message=?
            WHERE id=?
            """,
            (
                finished_at.isoformat(),
                (
                    finished_at
                    - started_at
                ).total_seconds(),
                stats.get(
                    "active_keyset_pages",
                    0,
                ),
                stats.get(
                    "active_markets_received",
                    0,
                ),
                stats.get(
                    "targeted_condition_ids",
                    0,
                ),
                stats.get(
                    "targeted_batches",
                    0,
                ),
                stats.get(
                    "targeted_markets_received",
                    0,
                ),
                stats.get(
                    "unique_markets_received",
                    0,
                ),
                stats.get(
                    "markets_inserted",
                    0,
                ),
                stats.get(
                    "markets_updated",
                    0,
                ),
                stats.get(
                    "outcomes_inserted",
                    0,
                ),
                stats.get(
                    "outcomes_updated",
                    0,
                ),
                stats.get(
                    "unresolved_before",
                    0,
                ),
                stats.get(
                    "unresolved_after",
                    0,
                ),
                stats.get(
                    "recovered_condition_ids",
                    0,
                ),
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
    stats: dict[str, int],
    recovered_markets: list[dict[str, Any]],
    display_limit: int,
) -> None:
    print()
    print("=" * 120)
    print("GAMMA REGISTRY EXPANSION SUMMARY")
    print("=" * 120)

    print(
        f"Active keyset pages:            "
        f"{stats['active_keyset_pages']}"
    )

    print(
        f"Active markets received:        "
        f"{stats['active_markets_received']:,}"
    )

    print(
        f"Targeted condition IDs:         "
        f"{stats['targeted_condition_ids']:,}"
    )

    print(
        f"Targeted markets returned:      "
        f"{stats['targeted_markets_received']:,}"
    )

    print(
        f"Unique markets processed:       "
        f"{stats['unique_markets_received']:,}"
    )

    print(
        f"Events inserted / updated:      "
        f"{stats.get('events_inserted', 0):,} "
        f"/ {stats.get('events_updated', 0):,}"
    )

    print(
        f"Markets inserted / updated:     "
        f"{stats['markets_inserted']:,} "
        f"/ {stats['markets_updated']:,}"
    )

    print(
        f"Outcomes inserted / updated:    "
        f"{stats['outcomes_inserted']:,} "
        f"/ {stats['outcomes_updated']:,}"
    )

    print(
        f"Missing IDs before / after:     "
        f"{stats['unresolved_before']:,} "
        f"/ {stats['unresolved_after']:,}"
    )

    print(
        f"Condition IDs recovered:        "
        f"{stats['recovered_condition_ids']:,}"
    )

    print("=" * 120)

    if recovered_markets:
        print()
        print("RECOVERED TARGET MARKETS")

        for index, market in enumerate(
            recovered_markets[:display_limit],
            start=1,
        ):
            event_id, event_slug = market_event_identity(
                market
            )

            print()
            print("-" * 120)

            print(
                f"{index}. "
                f"{clean_text(market.get('question')) or '-'}"
            )

            print("-" * 120)

            print(
                f"Condition ID:                   "
                f"{normalize_identifier(market.get('conditionId'))}"
            )

            print(
                f"Gamma market ID:                "
                f"{clean_text(market.get('id'))}"
            )

            print(
                f"Market slug:                    "
                f"{clean_text(market.get('slug')) or '-'}"
            )

            print(
                f"Event ID / slug:                "
                f"{event_id or '-'} "
                f"/ {event_slug or '-'}"
            )

            print(
                f"Active / closed:                "
                f"{bool(market.get('active'))} "
                f"/ {bool(market.get('closed'))}"
            )


# =============================================================================
# MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Expand and refresh the local Gamma market registry using "
            "stable keyset pagination plus exact targeted lookups for "
            "currently unresolved condition IDs."
        )
    )

    parser.add_argument(
        "--page-limit",
        type=int,
        default=DEFAULT_PAGE_LIMIT,
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
    )

    parser.add_argument(
        "--target-batch-size",
        type=int,
        default=DEFAULT_TARGET_BATCH_SIZE,
    )

    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY,
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
    )

    parser.add_argument(
        "--skip-active-crawl",
        action="store_true",
        help=(
            "Skip the full active-market keyset crawl and run only "
            "targeted unresolved condition-ID lookups."
        ),
    )

    parser.add_argument(
        "--skip-targeted-recovery",
        action="store_true",
        help=(
            "Skip exact lookups for unresolved condition IDs."
        ),
    )

    parser.add_argument(
        "--continue-on-batch-failure",
        action="store_true",
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

    page_limit = min(
        max(arguments.page_limit, 1),
        500,
    )

    max_pages = max(
        arguments.max_pages,
        1,
    )

    target_batch_size = min(
        max(arguments.target_batch_size, 1),
        100,
    )

    request_delay = max(
        arguments.request_delay,
        0.0,
    )

    timeout = max(
        arguments.timeout,
        1,
    )

    print()
    print("=" * 120)
    print("POLYMARKET GAMMA REGISTRY EXPANSION ENGINE v1.3")
    print("=" * 120)

    print(f"Database:                    {DB}")
    print(f"Gamma API:                   {GAMMA_API}")
    print(f"Keyset page limit:           {page_limit}")
    print(f"Maximum keyset pages:        {max_pages}")
    print(f"Target batch size:           {target_batch_size}")
    print(
        f"Active crawl:                "
        f"{not arguments.skip_active_crawl}"
    )
    print(
        f"Targeted recovery:           "
        f"{not arguments.skip_targeted_recovery}"
    )
    print(
        "Method:                     "
        "ACTIVE KEYSET CRAWL + EXACT CONDITION-ID RECOVERY"
    )

    print("=" * 120)

    create_engine_tables()

    run_id, started_at = start_run()

    stats: dict[str, int] = {
        "active_keyset_pages": 0,
        "active_markets_received": 0,
        "targeted_condition_ids": 0,
        "targeted_batches": 0,
        "targeted_markets_received": 0,
        "unique_markets_received": 0,
        "events_inserted": 0,
        "events_updated": 0,
        "markets_inserted": 0,
        "markets_updated": 0,
        "outcomes_inserted": 0,
        "outcomes_updated": 0,
        "unresolved_before": 0,
        "unresolved_after": 0,
        "recovered_condition_ids": 0,
    }

    targeted_condition_ids: list[str] = []
    targeted_markets: list[dict[str, Any]] = []

    try:
        existing_before = load_existing_gamma_condition_ids()

        unresolved_ids = load_unresolved_condition_ids()

        targeted_condition_ids = [
            condition_id
            for condition_id in unresolved_ids
            if condition_id not in existing_before
        ]

        stats[
            "unresolved_before"
        ] = len(
            targeted_condition_ids
        )

        active_markets: list[
            dict[str, Any]
        ] = []

        if not arguments.skip_active_crawl:
            (
                active_markets,
                active_pages,
            ) = fetch_active_markets_keyset(
                page_limit=page_limit,
                max_pages=max_pages,
                timeout=timeout,
                request_delay=request_delay,
            )

            stats[
                "active_keyset_pages"
            ] = active_pages

            stats[
                "active_markets_received"
            ] = len(
                active_markets
            )

        if (
            targeted_condition_ids
            and not arguments.skip_targeted_recovery
        ):
            (
                targeted_markets,
                targeted_batches,
            ) = fetch_markets_by_condition_ids(
                condition_ids=(
                    targeted_condition_ids
                ),
                batch_size=(
                    target_batch_size
                ),
                timeout=timeout,
                request_delay=request_delay,
                continue_on_batch_failure=(
                    arguments
                    .continue_on_batch_failure
                ),
                run_id=run_id,
            )

            stats[
                "targeted_condition_ids"
            ] = len(
                targeted_condition_ids
            )

            stats[
                "targeted_batches"
            ] = targeted_batches

            stats[
                "targeted_markets_received"
            ] = len(
                targeted_markets
            )

            update_recovery_table(
                requested_condition_ids=(
                    targeted_condition_ids
                ),
                returned_markets=(
                    targeted_markets
                ),
            )

        unique_markets: dict[
            str,
            dict[str, Any],
        ] = {}

        for market in (
            active_markets
            + targeted_markets
        ):
            condition_id = normalize_identifier(
                market.get("conditionId")
                or market.get("condition_id")
            )

            if condition_id:
                unique_markets[
                    condition_id
                ] = market

        stats[
            "unique_markets_received"
        ] = len(
            unique_markets
        )

        market_values = list(
            unique_markets.values()
        )

        # Parent-before-child insertion order required by SQLite FKs:
        # gamma_events -> gamma_markets -> gamma_market_outcomes
        embedded_events = extract_embedded_events(
            market_values
        )

        (
            events_inserted,
            events_updated,
        ) = upsert_gamma_events(
            embedded_events
        )

        stats[
            "events_inserted"
        ] = events_inserted

        stats[
            "events_updated"
        ] = events_updated

        (
            markets_inserted,
            markets_updated,
        ) = upsert_gamma_markets(
            market_values
        )

        (
            outcomes_inserted,
            outcomes_updated,
        ) = upsert_gamma_outcomes(
            market_values
        )

        stats[
            "markets_inserted"
        ] = markets_inserted

        stats[
            "markets_updated"
        ] = markets_updated

        stats[
            "outcomes_inserted"
        ] = outcomes_inserted

        stats[
            "outcomes_updated"
        ] = outcomes_updated

        existing_after = load_existing_gamma_condition_ids()

        still_unresolved = [
            condition_id
            for condition_id in targeted_condition_ids
            if condition_id not in existing_after
        ]

        stats[
            "unresolved_after"
        ] = len(
            still_unresolved
        )

        stats[
            "recovered_condition_ids"
        ] = (
            stats[
                "unresolved_before"
            ]
            - stats[
                "unresolved_after"
            ]
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            stats=stats,
        )

        display_summary(
            stats=stats,
            recovered_markets=(
                targeted_markets
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 120)
        print("GAMMA REGISTRY EXPANSION COMPLETE")
        print("=" * 120)

        print(
            "Updated event registry:      "
            "gamma_events"
        )

        print(
            "Updated market registry:     "
            "gamma_markets"
        )

        print(
            "Updated outcome mappings:    "
            "gamma_market_outcomes"
        )

        print(
            "Recovery audit:              "
            "gamma_registry_expansion_recovery"
        )

        print(
            "Run history:                 "
            "gamma_registry_expansion_runs"
        )

        print()
        print(
            "Next required sequence: rerun "
            "market_identifier_registry_engine.py, then "
            "market_identity_enrichment_engine.py, then "
            "opportunity_ranking_engine.py."
        )

        print("=" * 120)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            stats=stats,
            error_message=(
                f"{type(error).__name__}: {error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()