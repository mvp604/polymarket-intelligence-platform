from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"
DATA_API = "https://data-api.polymarket.com"

DEFAULT_WALLET_LIMIT = 10
DEFAULT_ACTIVITY_PAGE_LIMIT = 500
DEFAULT_TRADE_PAGE_LIMIT = 500
DEFAULT_MAX_ACTIVITY_RECORDS = 20_000
DEFAULT_MAX_TRADE_RECORDS = 10_000
DEFAULT_DELAY = 0.10
DEFAULT_DISPLAY_LIMIT = 20

MAX_RETRIES = 5
DOCUMENTED_MAX_OFFSET = 10_000
OBSERVED_SAFE_OFFSET = 3_000


# =============================================================================
# HELPERS
# =============================================================================


def configure_utf8() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def wallet_text(value: Any) -> str:
    return text(value).lower()


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def valid_wallet(wallet: str) -> bool:
    if len(wallet) != 42 or not wallet.startswith("0x"):
        return False

    try:
        int(wallet[2:], 16)
        return True
    except ValueError:
        return False


def observed_at_from_epoch(timestamp: int) -> str:
    if timestamp <= 0:
        return ""

    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    ).isoformat()


def canonical_key(
    prefix: str,
    wallet: str,
    row: dict[str, Any],
) -> str:
    identity = "|".join(
        [
            prefix,
            wallet,
            text(row.get("transactionHash")).lower(),
            str(integer(row.get("timestamp"))),
            text(row.get("conditionId")).lower(),
            text(row.get("asset")),
            text(row.get("side")).upper(),
            text(row.get("type")).upper(),
            f"{number(row.get('size')):.12f}",
            f"{number(row.get('price')):.12f}",
            text(row.get("outcome")),
        ]
    )

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()


# =============================================================================
# DATABASE
# =============================================================================


def connect() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(
            f"Database not found: {DB}"
        )

    connection = sqlite3.connect(
        DB,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")

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
        text(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    if column_name in table_columns(
        connection,
        table_name,
    ):
        return

    connection.execute(
        f'ALTER TABLE "{table_name}" '
        f'ADD COLUMN "{column_name}" {definition}'
    )


def create_or_migrate_tables() -> None:
    connection = connect()

    try:
        if not table_exists(
            connection,
            "wallet_registry",
        ):
            raise RuntimeError(
                "wallet_registry is missing. "
                "Run weekly_wallet_discovery.py first."
            )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS official_wallet_activity (
                activity_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                timestamp INTEGER NOT NULL DEFAULT 0,
                observed_at TEXT,
                condition_id TEXT,
                activity_type TEXT,
                side TEXT,
                asset TEXT,
                outcome TEXT,
                outcome_index INTEGER,
                size REAL NOT NULL DEFAULT 0,
                usdc_size REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                transaction_hash TEXT,
                title TEXT,
                slug TEXT,
                event_slug TEXT,
                name TEXT,
                pseudonym TEXT,
                is_combo INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL,
                first_ingested_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_official_activity_wallet_time
            ON official_wallet_activity(
                wallet,
                timestamp DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_official_activity_market
            ON official_wallet_activity(
                condition_id,
                timestamp DESC
            );

            CREATE TABLE IF NOT EXISTS official_wallet_trades (
                trade_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                timestamp INTEGER NOT NULL DEFAULT 0,
                observed_at TEXT,
                condition_id TEXT,
                side TEXT,
                asset TEXT,
                outcome TEXT,
                outcome_index INTEGER,
                size REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                notional REAL NOT NULL DEFAULT 0,
                transaction_hash TEXT,
                title TEXT,
                slug TEXT,
                event_slug TEXT,
                trade_source TEXT NOT NULL DEFAULT 'TRADES_ENDPOINT',
                raw_json TEXT NOT NULL,
                first_ingested_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_official_trades_wallet_time
            ON official_wallet_trades(
                wallet,
                timestamp DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_official_trades_market
            ON official_wallet_trades(
                condition_id,
                timestamp DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_activity_checkpoints (
                wallet TEXT PRIMARY KEY,
                last_activity_timestamp INTEGER NOT NULL DEFAULT 0,
                oldest_activity_timestamp INTEGER NOT NULL DEFAULT 0,
                last_trade_timestamp INTEGER NOT NULL DEFAULT 0,
                oldest_trade_timestamp INTEGER NOT NULL DEFAULT 0,
                activity_records INTEGER NOT NULL DEFAULT 0,
                trade_records INTEGER NOT NULL DEFAULT 0,
                activity_complete INTEGER NOT NULL DEFAULT 0,
                trades_complete INTEGER NOT NULL DEFAULT 0,
                activity_truncated INTEGER NOT NULL DEFAULT 0,
                trades_truncated INTEGER NOT NULL DEFAULT 0,
                activity_windows INTEGER NOT NULL DEFAULT 0,
                activity_pages INTEGER NOT NULL DEFAULT 0,
                trade_pages INTEGER NOT NULL DEFAULT 0,
                last_success_at TEXT,
                last_error_at TEXT,
                last_error_message TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallet_activity_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                wallet TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                requested_offset INTEGER,
                requested_start INTEGER,
                requested_end INTEGER,
                http_status INTEGER,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                response_body_preview TEXT,
                terminal_page INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_activity_errors_wallet
            ON wallet_activity_errors(
                wallet,
                created_at DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_activity_ingestion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                engine_version TEXT NOT NULL DEFAULT '2.0',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                wallets_selected INTEGER NOT NULL DEFAULT 0,
                wallets_succeeded INTEGER NOT NULL DEFAULT 0,
                wallets_failed INTEGER NOT NULL DEFAULT 0,
                activity_rows_received INTEGER NOT NULL DEFAULT 0,
                activity_rows_inserted INTEGER NOT NULL DEFAULT 0,
                trade_rows_received INTEGER NOT NULL DEFAULT 0,
                trade_rows_inserted INTEGER NOT NULL DEFAULT 0,
                activity_terminal_400s INTEGER NOT NULL DEFAULT 0,
                trade_terminal_400s INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )

        migrations = {
            "official_wallet_activity": {
                "is_combo": "INTEGER NOT NULL DEFAULT 0",
            },
            "official_wallet_trades": {
                "trade_source": (
                    "TEXT NOT NULL DEFAULT 'TRADES_ENDPOINT'"
                ),
            },
            "wallet_activity_checkpoints": {
                "oldest_activity_timestamp": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "oldest_trade_timestamp": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "activity_complete": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "trades_complete": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "activity_truncated": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "trades_truncated": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "activity_windows": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "activity_pages": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "trade_pages": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
            },
            "wallet_activity_errors": {
                "requested_offset": "INTEGER",
                "requested_start": "INTEGER",
                "requested_end": "INTEGER",
                "http_status": "INTEGER",
                "response_body_preview": "TEXT",
                "terminal_page": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
            },
            "wallet_activity_ingestion_runs": {
                "engine_version": (
                    "TEXT NOT NULL DEFAULT '2.0'"
                ),
                "activity_terminal_400s": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "trade_terminal_400s": (
                    "INTEGER NOT NULL DEFAULT 0"
                ),
            },
        }

        for table_name, definitions in migrations.items():
            for column_name, definition in definitions.items():
                ensure_column(
                    connection,
                    table_name,
                    column_name,
                    definition,
                )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# HTTP
# =============================================================================


def build_url(
    endpoint: str,
    wallet: str,
    params: dict[str, Any],
) -> str:
    query = urllib.parse.urlencode(
        {
            "user": wallet,
            **params,
        },
        doseq=True,
    )

    return (
        f"{DATA_API}{endpoint}?{query}"
    )


def decode_error_body(
    raw_body: bytes,
) -> str:
    return raw_body.decode(
        "utf-8",
        errors="replace",
    )[:2000]


def fetch_page(
    endpoint: str,
    wallet: str,
    params: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    int,
    str,
]:
    url = build_url(
        endpoint,
        wallet,
        params,
    )

    last_error: Exception | None = None
    last_status = 0
    last_body = ""

    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "PolymarketIntelligencePlatform/"
                    "official-wallet-activity-v2"
                ),
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:
                payload = json.loads(
                    response.read().decode(
                        "utf-8",
                        errors="replace",
                    )
                )

                if not isinstance(payload, list):
                    raise RuntimeError(
                        f"Unexpected {endpoint} response: "
                        f"{type(payload).__name__}"
                    )

                return (
                    [
                        item
                        for item in payload
                        if isinstance(item, dict)
                    ],
                    response.status,
                    "",
                )

        except urllib.error.HTTPError as error:
            last_error = error
            last_status = error.code
            last_body = decode_error_body(
                error.read()
            )

            if error.code not in {
                425,
                429,
                500,
                502,
                503,
                504,
            }:
                break

        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as error:
            last_error = error

        if attempt < MAX_RETRIES - 1:
            delay = min(
                2 ** attempt,
                16,
            )

            time.sleep(delay)

    message = (
        f"{type(last_error).__name__}: "
        f"{last_error}"
    )

    if last_body:
        message += (
            f" | body={last_body}"
        )

    error = RuntimeError(message)
    setattr(error, "http_status", last_status)
    setattr(error, "response_body", last_body)
    setattr(error, "request_url", url)

    raise error


# =============================================================================
# PAGINATION
# =============================================================================


def deduplicate_rows(
    prefix: str,
    wallet: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unique: dict[
        str,
        dict[str, Any],
    ] = {}

    for row in rows:
        unique[
            canonical_key(
                prefix,
                wallet,
                row,
            )
        ] = row

    return sorted(
        unique.values(),
        key=lambda row: integer(
            row.get("timestamp")
        ),
        reverse=True,
    )


def fetch_activity_adaptive(
    wallet: str,
    page_limit: int,
    max_records: int,
    delay: float,
    full_history: bool,
) -> dict[str, Any]:
    all_rows: list[
        dict[str, Any]
    ] = []

    seen_keys: set[str] = set()

    start_timestamp = (
        1
        if full_history
        else 0
    )

    end_timestamp = integer(
        utc_now().timestamp()
    )

    windows = 0
    pages = 0
    terminal_400s = 0
    complete = False
    truncated = False

    while (
        len(all_rows) < max_records
        and end_timestamp > start_timestamp
    ):
        windows += 1
        offset = 0
        window_oldest: int | None = None
        rows_added_in_window = 0

        while (
            offset <= DOCUMENTED_MAX_OFFSET
            and len(all_rows) < max_records
        ):
            params = {
                "limit": page_limit,
                "offset": offset,
                "start": start_timestamp,
                "end": end_timestamp,
                "sortBy": "TIMESTAMP",
                "sortDirection": "DESC",
            }

            try:
                page, _, _ = fetch_page(
                    endpoint="/activity",
                    wallet=wallet,
                    params=params,
                )

            except RuntimeError as error:
                status = integer(
                    getattr(
                        error,
                        "http_status",
                        0,
                    )
                )

                if (
                    status == 400
                    and offset > 0
                    and window_oldest is not None
                ):
                    terminal_400s += 1
                    break

                raise

            pages += 1

            if not page:
                complete = True
                break

            for row in page:
                row_key = canonical_key(
                    "ACTIVITY",
                    wallet,
                    row,
                )

                if row_key in seen_keys:
                    continue

                seen_keys.add(row_key)
                all_rows.append(row)
                rows_added_in_window += 1

                row_timestamp = integer(
                    row.get("timestamp")
                )

                if row_timestamp > 0:
                    window_oldest = (
                        row_timestamp
                        if window_oldest is None
                        else min(
                            window_oldest,
                            row_timestamp,
                        )
                    )

                if len(all_rows) >= max_records:
                    truncated = True
                    break

            if len(page) < page_limit:
                complete = True
                break

            offset += page_limit

            if (
                offset > OBSERVED_SAFE_OFFSET
                and window_oldest is not None
            ):
                break

            if delay > 0:
                time.sleep(delay)

        if complete or truncated:
            break

        if (
            window_oldest is None
            or rows_added_in_window == 0
        ):
            complete = True
            break

        next_end = window_oldest - 1

        if next_end >= end_timestamp:
            truncated = True
            break

        end_timestamp = next_end

        if delay > 0:
            time.sleep(delay)

    if len(all_rows) >= max_records:
        truncated = True

    return {
        "rows": deduplicate_rows(
            "ACTIVITY",
            wallet,
            all_rows,
        ),
        "windows": windows,
        "pages": pages,
        "terminal_400s": terminal_400s,
        "complete": int(
            complete
            and not truncated
        ),
        "truncated": int(truncated),
    }


def fetch_trades_adaptive(
    wallet: str,
    page_limit: int,
    max_records: int,
    delay: float,
) -> dict[str, Any]:
    rows: list[
        dict[str, Any]
    ] = []

    offset = 0
    pages = 0
    terminal_400s = 0
    complete = False
    truncated = False

    while (
        offset <= DOCUMENTED_MAX_OFFSET
        and len(rows) < max_records
    ):
        params = {
            "limit": min(
                page_limit,
                max_records - len(rows),
            ),
            "offset": offset,
        }

        try:
            page, _, _ = fetch_page(
                endpoint="/trades",
                wallet=wallet,
                params=params,
            )

        except RuntimeError as error:
            status = integer(
                getattr(
                    error,
                    "http_status",
                    0,
                )
            )

            if status == 400 and offset > 0:
                terminal_400s += 1
                complete = True
                break

            raise

        pages += 1
        rows.extend(page)

        if len(page) < params["limit"]:
            complete = True
            break

        offset += params["limit"]

        if delay > 0:
            time.sleep(delay)

    if len(rows) >= max_records:
        truncated = True

    return {
        "rows": deduplicate_rows(
            "TRADE",
            wallet,
            rows,
        ),
        "pages": pages,
        "terminal_400s": terminal_400s,
        "complete": int(
            complete
            and not truncated
        ),
        "truncated": int(truncated),
    }


def activity_trade_rows(
    activity_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        row
        for row in activity_rows
        if text(
            row.get("type")
        ).upper()
        == "TRADE"
    ]


# =============================================================================
# SELECTION
# =============================================================================


def select_wallets(
    statuses: list[str],
    wallet_limit: int,
    only_scan_required: bool,
    failed_only: bool,
) -> list[dict[str, Any]]:
    connection = connect()

    try:
        placeholders = ", ".join(
            "?"
            for _ in statuses
        )

        has_evaluations = table_exists(
            connection,
            "candidate_wallet_evaluations",
        )

        evaluation_join = (
            """
            LEFT JOIN candidate_wallet_evaluations cwe
              ON cwe.wallet = wr.wallet
            """
            if has_evaluations
            else ""
        )

        evaluation_fields = (
            """
            COALESCE(cwe.needs_position_scan, 0)
                AS needs_position_scan,
            COALESCE(cwe.needs_history_scan, 0)
                AS needs_history_scan,
            COALESCE(cwe.evaluation_score, 0)
                AS evaluation_score
            """
            if has_evaluations
            else
            """
            0 AS needs_position_scan,
            0 AS needs_history_scan,
            0 AS evaluation_score
            """
        )

        sql = f"""
            SELECT
                wr.wallet,
                wr.status,
                wr.qualification_eligible,
                wr.leaderboard_appearance_count,
                wr.best_rank,
                wr.best_observed_pnl,
                {evaluation_fields},
                COALESCE(wac.last_success_at, '')
                    AS last_success_at,
                COALESCE(wac.last_error_message, '')
                    AS last_error_message
            FROM wallet_registry wr
            {evaluation_join}
            LEFT JOIN wallet_activity_checkpoints wac
              ON wac.wallet = wr.wallet
            WHERE wr.status IN ({placeholders})
        """

        parameters: list[Any] = list(
            statuses
        )

        if only_scan_required and has_evaluations:
            sql += """
                AND (
                    COALESCE(cwe.needs_position_scan, 0) = 1
                    OR COALESCE(cwe.needs_history_scan, 0) = 1
                )
            """

        if failed_only:
            sql += """
                AND COALESCE(wac.last_error_message, '') <> ''
            """

        sql += """
            ORDER BY
                CASE
                    WHEN COALESCE(wac.last_error_message, '') <> ''
                    THEN 0
                    ELSE 1
                END,
                CASE wr.status
                    WHEN 'ELITE' THEN 1
                    WHEN 'QUALIFIED' THEN 2
                    WHEN 'WATCHLIST' THEN 3
                    ELSE 4
                END,
                evaluation_score DESC,
                wr.leaderboard_appearance_count DESC,
                wr.best_rank ASC,
                wr.best_observed_pnl DESC
        """

        if wallet_limit > 0:
            sql += " LIMIT ?"
            parameters.append(
                wallet_limit
            )

        return [
            dict(row)
            for row in connection.execute(
                sql,
                tuple(parameters),
            ).fetchall()
        ]

    finally:
        connection.close()


# =============================================================================
# STORAGE
# =============================================================================


def save_activity_rows(
    wallet: str,
    rows: list[dict[str, Any]],
    ingested_at: str,
) -> int:
    connection = connect()
    inserted = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for row in rows:
            key = canonical_key(
                "ACTIVITY",
                wallet,
                row,
            )

            exists = connection.execute(
                """
                SELECT 1
                FROM official_wallet_activity
                WHERE activity_key=?
                """,
                (key,),
            ).fetchone()

            connection.execute(
                """
                INSERT INTO official_wallet_activity (
                    activity_key,
                    wallet,
                    timestamp,
                    observed_at,
                    condition_id,
                    activity_type,
                    side,
                    asset,
                    outcome,
                    outcome_index,
                    size,
                    usdc_size,
                    price,
                    transaction_hash,
                    title,
                    slug,
                    event_slug,
                    name,
                    pseudonym,
                    is_combo,
                    raw_json,
                    first_ingested_at,
                    last_seen_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(activity_key) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,
                    raw_json=excluded.raw_json
                """,
                (
                    key,
                    wallet,
                    integer(
                        row.get("timestamp")
                    ),
                    observed_at_from_epoch(
                        integer(
                            row.get("timestamp")
                        )
                    ),
                    text(
                        row.get("conditionId")
                    ).lower(),
                    text(
                        row.get("type")
                    ).upper(),
                    text(
                        row.get("side")
                    ).upper(),
                    text(
                        row.get("asset")
                    ),
                    text(
                        row.get("outcome")
                    ),
                    integer(
                        row.get("outcomeIndex")
                    ),
                    number(
                        row.get("size")
                    ),
                    number(
                        row.get("usdcSize")
                    ),
                    number(
                        row.get("price")
                    ),
                    text(
                        row.get("transactionHash")
                    ).lower(),
                    text(row.get("title")),
                    text(row.get("slug")),
                    text(row.get("eventSlug")),
                    text(row.get("name")),
                    text(row.get("pseudonym")),
                    int(
                        bool(
                            row.get("isCombo")
                        )
                    ),
                    stable_json(row),
                    ingested_at,
                    ingested_at,
                ),
            )

            if exists is None:
                inserted += 1

        connection.commit()
        return inserted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_trade_rows(
    wallet: str,
    endpoint_rows: list[dict[str, Any]],
    activity_rows: list[dict[str, Any]],
    ingested_at: str,
) -> int:
    combined: list[
        tuple[
            dict[str, Any],
            str,
        ]
    ] = [
        (
            row,
            "TRADES_ENDPOINT",
        )
        for row in endpoint_rows
    ]

    combined.extend(
        (
            row,
            "ACTIVITY_ENDPOINT",
        )
        for row in activity_trade_rows(
            activity_rows
        )
    )

    connection = connect()
    inserted = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for row, source in combined:
            key = canonical_key(
                "TRADE",
                wallet,
                row,
            )

            exists = connection.execute(
                """
                SELECT 1
                FROM official_wallet_trades
                WHERE trade_key=?
                """,
                (key,),
            ).fetchone()

            size = number(
                row.get("size")
            )

            price = number(
                row.get("price")
            )

            connection.execute(
                """
                INSERT INTO official_wallet_trades (
                    trade_key,
                    wallet,
                    timestamp,
                    observed_at,
                    condition_id,
                    side,
                    asset,
                    outcome,
                    outcome_index,
                    size,
                    price,
                    notional,
                    transaction_hash,
                    title,
                    slug,
                    event_slug,
                    trade_source,
                    raw_json,
                    first_ingested_at,
                    last_seen_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(trade_key) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,
                    raw_json=excluded.raw_json,
                    trade_source=
                        CASE
                            WHEN official_wallet_trades.trade_source =
                                 'TRADES_ENDPOINT'
                            THEN official_wallet_trades.trade_source
                            ELSE excluded.trade_source
                        END
                """,
                (
                    key,
                    wallet,
                    integer(
                        row.get("timestamp")
                    ),
                    observed_at_from_epoch(
                        integer(
                            row.get("timestamp")
                        )
                    ),
                    text(
                        row.get("conditionId")
                    ).lower(),
                    text(
                        row.get("side")
                    ).upper(),
                    text(
                        row.get("asset")
                    ),
                    text(
                        row.get("outcome")
                    ),
                    integer(
                        row.get("outcomeIndex")
                    ),
                    size,
                    price,
                    size * price,
                    text(
                        row.get("transactionHash")
                    ).lower(),
                    text(row.get("title")),
                    text(row.get("slug")),
                    text(row.get("eventSlug")),
                    source,
                    stable_json(row),
                    ingested_at,
                    ingested_at,
                ),
            )

            if exists is None:
                inserted += 1

        connection.commit()
        return inserted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def update_checkpoint(
    wallet: str,
    activity_result: dict[str, Any],
    trade_result: dict[str, Any],
    success: bool,
    error_message: str = "",
) -> None:
    activity_rows = activity_result.get(
        "rows",
        [],
    )

    trade_rows = trade_result.get(
        "rows",
        [],
    )

    activity_timestamps = [
        integer(
            row.get("timestamp")
        )
        for row in activity_rows
        if integer(
            row.get("timestamp")
        )
        > 0
    ]

    trade_timestamps = [
        integer(
            row.get("timestamp")
        )
        for row in trade_rows
        if integer(
            row.get("timestamp")
        )
        > 0
    ]

    timestamp = utc_now_iso()
    connection = connect()

    try:
        connection.execute(
            """
            INSERT INTO wallet_activity_checkpoints (
                wallet,
                last_activity_timestamp,
                oldest_activity_timestamp,
                last_trade_timestamp,
                oldest_trade_timestamp,
                activity_records,
                trade_records,
                activity_complete,
                trades_complete,
                activity_truncated,
                trades_truncated,
                activity_windows,
                activity_pages,
                trade_pages,
                last_success_at,
                last_error_at,
                last_error_message,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(wallet) DO UPDATE SET
                last_activity_timestamp=
                    MAX(
                        last_activity_timestamp,
                        excluded.last_activity_timestamp
                    ),
                oldest_activity_timestamp=
                    CASE
                        WHEN oldest_activity_timestamp = 0
                        THEN excluded.oldest_activity_timestamp
                        WHEN excluded.oldest_activity_timestamp = 0
                        THEN oldest_activity_timestamp
                        ELSE MIN(
                            oldest_activity_timestamp,
                            excluded.oldest_activity_timestamp
                        )
                    END,
                last_trade_timestamp=
                    MAX(
                        last_trade_timestamp,
                        excluded.last_trade_timestamp
                    ),
                oldest_trade_timestamp=
                    CASE
                        WHEN oldest_trade_timestamp = 0
                        THEN excluded.oldest_trade_timestamp
                        WHEN excluded.oldest_trade_timestamp = 0
                        THEN oldest_trade_timestamp
                        ELSE MIN(
                            oldest_trade_timestamp,
                            excluded.oldest_trade_timestamp
                        )
                    END,
                activity_records=
                    excluded.activity_records,
                trade_records=
                    excluded.trade_records,
                activity_complete=
                    excluded.activity_complete,
                trades_complete=
                    excluded.trades_complete,
                activity_truncated=
                    excluded.activity_truncated,
                trades_truncated=
                    excluded.trades_truncated,
                activity_windows=
                    excluded.activity_windows,
                activity_pages=
                    excluded.activity_pages,
                trade_pages=
                    excluded.trade_pages,
                last_success_at=
                    excluded.last_success_at,
                last_error_at=
                    excluded.last_error_at,
                last_error_message=
                    excluded.last_error_message,
                updated_at=
                    excluded.updated_at
            """,
            (
                wallet,
                max(
                    activity_timestamps,
                    default=0,
                ),
                min(
                    activity_timestamps,
                    default=0,
                ),
                max(
                    trade_timestamps,
                    default=0,
                ),
                min(
                    trade_timestamps,
                    default=0,
                ),
                len(activity_rows),
                len(trade_rows),
                integer(
                    activity_result.get(
                        "complete"
                    )
                ),
                integer(
                    trade_result.get(
                        "complete"
                    )
                ),
                integer(
                    activity_result.get(
                        "truncated"
                    )
                ),
                integer(
                    trade_result.get(
                        "truncated"
                    )
                ),
                integer(
                    activity_result.get(
                        "windows"
                    )
                ),
                integer(
                    activity_result.get(
                        "pages"
                    )
                ),
                integer(
                    trade_result.get(
                        "pages"
                    )
                ),
                (
                    timestamp
                    if success
                    else None
                ),
                (
                    None
                    if success
                    else timestamp
                ),
                (
                    ""
                    if success
                    else error_message
                ),
                timestamp,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def log_error(
    run_id: int,
    wallet: str,
    endpoint: str,
    error: Exception,
    terminal_page: bool = False,
) -> None:
    connection = connect()

    try:
        connection.execute(
            """
            INSERT INTO wallet_activity_errors (
                run_id,
                wallet,
                endpoint,
                http_status,
                error_type,
                error_message,
                response_body_preview,
                terminal_page,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                run_id,
                wallet,
                endpoint,
                integer(
                    getattr(
                        error,
                        "http_status",
                        0,
                    )
                ),
                type(error).__name__,
                str(error),
                text(
                    getattr(
                        error,
                        "response_body",
                        "",
                    )
                ),
                int(terminal_page),
                utc_now_iso(),
            ),
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING / DISPLAY
# =============================================================================


def start_run(
    wallet_count: int,
) -> tuple[int, datetime]:
    started = utc_now()
    connection = connect()

    try:
        cursor = connection.execute(
            """
            INSERT INTO wallet_activity_ingestion_runs (
                engine_version,
                started_at,
                wallets_selected,
                status
            )
            VALUES (
                '2.0',
                ?,
                ?,
                'RUNNING'
            )
            """,
            (
                started.isoformat(),
                wallet_count,
            ),
        )

        connection.commit()

        return cursor.lastrowid, started

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started: datetime,
    status: str,
    succeeded: int,
    failed: int,
    activity_received: int,
    activity_inserted: int,
    trade_received: int,
    trade_inserted: int,
    activity_terminal_400s: int,
    trade_terminal_400s: int,
    error_message: str = "",
) -> None:
    finished = utc_now()
    connection = connect()

    try:
        connection.execute(
            """
            UPDATE wallet_activity_ingestion_runs
            SET
                finished_at=?,
                elapsed_seconds=?,
                wallets_succeeded=?,
                wallets_failed=?,
                activity_rows_received=?,
                activity_rows_inserted=?,
                trade_rows_received=?,
                trade_rows_inserted=?,
                activity_terminal_400s=?,
                trade_terminal_400s=?,
                status=?,
                error_message=?
            WHERE id=?
            """,
            (
                finished.isoformat(),
                (
                    finished
                    - started
                ).total_seconds(),
                succeeded,
                failed,
                activity_received,
                activity_inserted,
                trade_received,
                trade_inserted,
                activity_terminal_400s,
                trade_terminal_400s,
                status,
                error_message,
                run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def show_summary(
    display_limit: int,
) -> None:
    connection = connect()

    try:
        activity_total = connection.execute(
            """
            SELECT COUNT(*)
            FROM official_wallet_activity
            """
        ).fetchone()[0]

        trade_total = connection.execute(
            """
            SELECT COUNT(*)
            FROM official_wallet_trades
            """
        ).fetchone()[0]

        rows = connection.execute(
            """
            SELECT
                wallet,
                activity_records,
                trade_records,
                activity_complete,
                trades_complete,
                activity_truncated,
                trades_truncated,
                activity_windows,
                activity_pages,
                trade_pages,
                last_success_at,
                last_error_message
            FROM wallet_activity_checkpoints
            ORDER BY
                last_success_at DESC,
                trade_records DESC,
                activity_records DESC
            LIMIT ?
            """,
            (
                max(
                    display_limit,
                    1,
                ),
            ),
        ).fetchall()

    finally:
        connection.close()

    print()
    print("=" * 112)
    print("OFFICIAL WALLET ACTIVITY v2 SUMMARY")
    print("=" * 112)

    print(
        f"Stored official activity rows:  "
        f"{activity_total}"
    )

    print(
        f"Stored official trade rows:     "
        f"{trade_total}"
    )

    print("=" * 112)

    for index, row in enumerate(
        rows,
        start=1,
    ):
        print(
            f"{index:>3}. {row['wallet']} | "
            f"activity {row['activity_records']:>6} "
            f"({'complete' if row['activity_complete'] else 'partial'}) | "
            f"trades {row['trade_records']:>6} "
            f"({'complete' if row['trades_complete'] else 'partial'}) | "
            f"windows {row['activity_windows']:>2} | "
            f"pages {row['activity_pages']:>3}/"
            f"{row['trade_pages']:>3}"
        )


# =============================================================================
# MAIN
# =============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest official Polymarket wallet activity and trades "
            "with adaptive timestamp-window pagination and graceful "
            "handling of terminal HTTP 400 pagination responses."
        )
    )

    parser.add_argument(
        "--status",
        action="append",
        choices=[
            "CANDIDATE",
            "WATCHLIST",
            "QUALIFIED",
            "ELITE",
        ],
        help=(
            "Registry status to ingest. May be repeated. "
            "Default: WATCHLIST, QUALIFIED, ELITE."
        ),
    )

    parser.add_argument(
        "--wallet-limit",
        type=int,
        default=DEFAULT_WALLET_LIMIT,
    )

    parser.add_argument(
        "--activity-page-limit",
        type=int,
        default=DEFAULT_ACTIVITY_PAGE_LIMIT,
    )

    parser.add_argument(
        "--trade-page-limit",
        type=int,
        default=DEFAULT_TRADE_PAGE_LIMIT,
    )

    parser.add_argument(
        "--max-activity-records",
        type=int,
        default=DEFAULT_MAX_ACTIVITY_RECORDS,
    )

    parser.add_argument(
        "--max-trade-records",
        type=int,
        default=DEFAULT_MAX_TRADE_RECORDS,
    )

    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_DELAY,
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    parser.add_argument(
        "--only-scan-required",
        action="store_true",
    )

    parser.add_argument(
        "--failed-only",
        action="store_true",
        help=(
            "Select only wallets whose current checkpoint contains "
            "an ingestion error."
        ),
    )

    parser.add_argument(
        "--recent-window-only",
        action="store_true",
        help=(
            "Omit start=1 and use the API's default recent activity "
            "window rather than requesting full history."
        ),
    )

    parser.add_argument(
        "--continue-on-wallet-failure",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8()
    args = parse_args()

    statuses = args.status or [
        "WATCHLIST",
        "QUALIFIED",
        "ELITE",
    ]

    wallet_limit = max(
        args.wallet_limit,
        0,
    )

    activity_page_limit = min(
        max(
            args.activity_page_limit,
            1,
        ),
        500,
    )

    trade_page_limit = min(
        max(
            args.trade_page_limit,
            1,
        ),
        10_000,
    )

    max_activity_records = max(
        args.max_activity_records,
        1,
    )

    max_trade_records = max(
        args.max_trade_records,
        1,
    )

    delay = max(
        args.request_delay,
        0.0,
    )

    print()
    print("=" * 112)
    print("POLYMARKET OFFICIAL WALLET ACTIVITY ENGINE v2")
    print("=" * 112)

    print(f"Database:                    {DB}")
    print(f"Data API:                    {DATA_API}")
    print(f"Statuses:                    {', '.join(statuses)}")
    print(f"Wallet limit:                {wallet_limit or 'ALL'}")
    print(f"Activity page limit:         {activity_page_limit}")
    print(f"Trade page limit:            {trade_page_limit}")
    print(f"Maximum activity records:    {max_activity_records}")
    print(f"Maximum trade records:       {max_trade_records}")
    print(
        f"Full activity history:       "
        f"{not args.recent_window_only}"
    )
    print(
        f"Failed wallets only:         "
        f"{args.failed_only}"
    )

    print("=" * 112)

    create_or_migrate_tables()

    wallets = select_wallets(
        statuses=statuses,
        wallet_limit=wallet_limit,
        only_scan_required=(
            args.only_scan_required
        ),
        failed_only=args.failed_only,
    )

    if not wallets:
        raise RuntimeError(
            "No registry wallets matched the selected filters."
        )

    run_id, started = start_run(
        len(wallets)
    )

    succeeded = 0
    failed = 0
    activity_received = 0
    activity_inserted = 0
    trade_received = 0
    trade_inserted = 0
    activity_terminal_400s = 0
    trade_terminal_400s = 0
    errors: list[str] = []

    try:
        for index, registry in enumerate(
            wallets,
            start=1,
        ):
            wallet = wallet_text(
                registry["wallet"]
            )

            if not valid_wallet(wallet):
                continue

            print()
            print("-" * 112)

            print(
                f"WALLET {index}/{len(wallets)}: "
                f"{wallet} [{registry['status']}]"
            )

            print("-" * 112)

            activity_result: dict[str, Any] = {
                "rows": [],
            }

            trade_result: dict[str, Any] = {
                "rows": [],
            }

            try:
                activity_result = (
                    fetch_activity_adaptive(
                        wallet=wallet,
                        page_limit=(
                            activity_page_limit
                        ),
                        max_records=(
                            max_activity_records
                        ),
                        delay=delay,
                        full_history=(
                            not args.recent_window_only
                        ),
                    )
                )

                trade_result = (
                    fetch_trades_adaptive(
                        wallet=wallet,
                        page_limit=(
                            trade_page_limit
                        ),
                        max_records=(
                            max_trade_records
                        ),
                        delay=delay,
                    )
                )

                ingested_at = utc_now_iso()

                new_activity = save_activity_rows(
                    wallet=wallet,
                    rows=activity_result[
                        "rows"
                    ],
                    ingested_at=ingested_at,
                )

                new_trades = save_trade_rows(
                    wallet=wallet,
                    endpoint_rows=trade_result[
                        "rows"
                    ],
                    activity_rows=activity_result[
                        "rows"
                    ],
                    ingested_at=ingested_at,
                )

                update_checkpoint(
                    wallet=wallet,
                    activity_result=(
                        activity_result
                    ),
                    trade_result=(
                        trade_result
                    ),
                    success=True,
                )

                activity_count = len(
                    activity_result["rows"]
                )

                trade_count = len(
                    trade_result["rows"]
                )

                activity_received += (
                    activity_count
                )

                activity_inserted += (
                    new_activity
                )

                trade_received += trade_count
                trade_inserted += new_trades

                activity_terminal_400s += (
                    integer(
                        activity_result.get(
                            "terminal_400s"
                        )
                    )
                )

                trade_terminal_400s += (
                    integer(
                        trade_result.get(
                            "terminal_400s"
                        )
                    )
                )

                succeeded += 1

                print(
                    f"Activity: {activity_count} received, "
                    f"{new_activity} new | "
                    f"{activity_result['windows']} windows, "
                    f"{activity_result['pages']} pages | "
                    f"{'complete' if activity_result['complete'] else 'partial'}"
                )

                print(
                    f"Trades:   {trade_count} endpoint rows, "
                    f"{new_trades} new after activity merge | "
                    f"{trade_result['pages']} pages | "
                    f"{'complete' if trade_result['complete'] else 'partial'}"
                )

            except Exception as error:
                failed += 1

                message = (
                    f"{wallet}: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                errors.append(message)

                update_checkpoint(
                    wallet=wallet,
                    activity_result=(
                        activity_result
                    ),
                    trade_result=(
                        trade_result
                    ),
                    success=False,
                    error_message=message,
                )

                log_error(
                    run_id=run_id,
                    wallet=wallet,
                    endpoint=(
                        "activity_or_trades"
                    ),
                    error=error,
                )

                print(f"FAILED: {message}")

                if not (
                    args
                    .continue_on_wallet_failure
                ):
                    raise

        final_status = (
            "SUCCESS"
            if failed == 0
            else "PARTIAL_SUCCESS"
        )

        finish_run(
            run_id=run_id,
            started=started,
            status=final_status,
            succeeded=succeeded,
            failed=failed,
            activity_received=(
                activity_received
            ),
            activity_inserted=(
                activity_inserted
            ),
            trade_received=trade_received,
            trade_inserted=trade_inserted,
            activity_terminal_400s=(
                activity_terminal_400s
            ),
            trade_terminal_400s=(
                trade_terminal_400s
            ),
            error_message="\n".join(
                errors
            ),
        )

        print()
        print("=" * 112)
        print("OFFICIAL WALLET ACTIVITY v2 COMPLETE")
        print("=" * 112)

        print(f"Wallets succeeded:             {succeeded}")
        print(f"Wallets failed:                {failed}")

        print(
            f"Activity received/new:         "
            f"{activity_received} / "
            f"{activity_inserted}"
        )

        print(
            f"Trade endpoint received/new:   "
            f"{trade_received} / "
            f"{trade_inserted}"
        )

        print(
            f"Activity terminal HTTP 400s:   "
            f"{activity_terminal_400s}"
        )

        print(
            f"Trade terminal HTTP 400s:      "
            f"{trade_terminal_400s}"
        )

        print("=" * 112)

        show_summary(
            args.display_limit
        )

    except Exception as error:
        finish_run(
            run_id=run_id,
            started=started,
            status="FAILED",
            succeeded=succeeded,
            failed=max(
                failed,
                1,
            ),
            activity_received=(
                activity_received
            ),
            activity_inserted=(
                activity_inserted
            ),
            trade_received=trade_received,
            trade_inserted=trade_inserted,
            activity_terminal_400s=(
                activity_terminal_400s
            ),
            trade_terminal_400s=(
                trade_terminal_400s
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()