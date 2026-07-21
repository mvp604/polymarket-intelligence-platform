from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from data_access import DATABASE_PATH
except ImportError:
    from src.data_access import DATABASE_PATH


LOGGER = logging.getLogger(__name__)

DATA_API_BASE = "https://data-api.polymarket.com"

RUNS_TABLE = "wallet_profile_collection_runs"
PROFILES_TABLE = "wallet_profiles_raw"
CURRENT_TABLE = "wallet_current_position_snapshots"
CLOSED_TABLE = "wallet_closed_position_snapshots"
TRADES_TABLE = "wallet_trade_snapshots"
ACTIVITY_TABLE = "wallet_activity_snapshots"

DISCOVERED_TABLE = "discovered_wallets"

WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
CONDITION_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRIES = 3
DEFAULT_PAUSE_SECONDS = 0.10
DEFAULT_CANDIDATE_LIMIT = 10
DEFAULT_MIN_ELITE_SCORE = 50.0
DEFAULT_PAGE_SIZE = 50
DEFAULT_MAX_CLOSED_POSITIONS = 500
DEFAULT_MAX_TRADES = 500
DEFAULT_MAX_ACTIVITY = 500


def configure_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any) -> float:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else 0.0
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def safe_bool_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(bool(value))
    return int(clean_text(value).lower() in {"1", "true", "yes", "y"})


def normalize_wallet(value: Any) -> str:
    wallet = clean_text(value).lower()
    return wallet if WALLET_RE.fullmatch(wallet) else ""


def normalize_condition_id(value: Any) -> str:
    condition_id = clean_text(value).lower()
    return condition_id if CONDITION_RE.fullmatch(condition_id) else ""


@dataclass(slots=True)
class CandidateWallet:
    wallet: str
    username: str
    elite_score: float
    elite_grade: str
    primary_category: str
    active_watchlist: int
    manually_approved: int


@dataclass(slots=True)
class WalletCollection:
    candidate: CandidateWallet
    position_value: float
    total_markets_traded: int
    current_positions: list[dict[str, Any]]
    closed_positions: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    activity: list[dict[str, Any]]
    API_queries: int
    errors: list[str]

    @property
    def current_position_count(self) -> int:
        return len(self.current_positions)

    @property
    def closed_position_count(self) -> int:
        return len(self.closed_positions)

    @property
    def trade_count(self) -> int:
        return len(self.trades)

    @property
    def activity_count(self) -> int:
        return len(self.activity)


class PublicDataAPIClient:
    def __init__(
        self,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        retries: int = DEFAULT_RETRIES,
        pause_seconds: float = DEFAULT_PAUSE_SECONDS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.pause_seconds = pause_seconds

    def get_json(self, path: str, params: dict[str, Any]) -> Any:
        filtered_params = {
            key: value
            for key, value in params.items()
            if value is not None and value != ""
        }
        query = urllib.parse.urlencode(filtered_params, doseq=True)
        url = f"{DATA_API_BASE}{path}"
        if query:
            url = f"{url}?{query}"

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Polymarket-Intelligence-Platform/1.0",
            },
            method="GET",
        )

        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout_seconds,
                ) as response:
                    payload = response.read().decode("utf-8")
                    parsed = json.loads(payload)
                    time.sleep(self.pause_seconds)
                    return parsed
            except Exception as exc:
                last_error = exc
                if attempt >= self.retries:
                    break

                delay = min(2 ** (attempt - 1), 5)
                LOGGER.warning(
                    "Request failed (%s/%s) for %s: %s. Retrying in %ss.",
                    attempt,
                    self.retries,
                    path,
                    exc,
                    delay,
                )
                time.sleep(delay)

        raise RuntimeError(f"Request failed for {path}: {last_error}")

    def fetch_paginated_list(
        self,
        path: str,
        *,
        params: dict[str, Any],
        page_size: int,
        max_rows: int,
        offset_limit: int = 10000,
    ) -> tuple[list[dict[str, Any]], int]:
        rows: list[dict[str, Any]] = []
        offset = 0
        query_count = 0

        while len(rows) < max_rows and offset <= offset_limit:
            limit = min(page_size, max_rows - len(rows))
            payload = self.get_json(
                path,
                {
                    **params,
                    "limit": limit,
                    "offset": offset,
                },
            )
            query_count += 1

            if not isinstance(payload, list):
                raise RuntimeError(
                    f"Unexpected response from {path}: "
                    f"{type(payload).__name__}"
                )

            page = [row for row in payload if isinstance(row, dict)]
            rows.extend(page)

            if len(page) < limit:
                break

            offset += limit

        return rows, query_count


class WalletProfileCollector:
    def __init__(
        self,
        database_path: Path | str = DATABASE_PATH,
        *,
        candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
        min_elite_score: float = DEFAULT_MIN_ELITE_SCORE,
        include_watchlist_only: bool = False,
        max_closed_positions: int = DEFAULT_MAX_CLOSED_POSITIONS,
        max_trades: int = DEFAULT_MAX_TRADES,
        max_activity: int = DEFAULT_MAX_ACTIVITY,
    ) -> None:
        self.database_path = Path(database_path)
        self.candidate_limit = max(1, int(candidate_limit))
        self.min_elite_score = float(min_elite_score)
        self.include_watchlist_only = include_watchlist_only
        self.max_closed_positions = max(1, int(max_closed_positions))
        self.max_trades = max(1, int(max_trades))
        self.max_activity = max(1, int(max_activity))
        self.client = PublicDataAPIClient()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def table_exists(
        self,
        connection: sqlite3.Connection,
        table_name: str,
    ) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name=?
            LIMIT 1
            """,
            (table_name,),
        ).fetchone()
        return row is not None

    def validate_dependencies(self) -> None:
        connection = self.connect()
        try:
            if not self.table_exists(connection, DISCOVERED_TABLE):
                raise RuntimeError(
                    "discovered_wallets does not exist. Run the Elite Wallet "
                    "Discovery Engine in --apply mode first."
                )

            columns = {
                str(row["name"])
                for row in connection.execute(
                    f"PRAGMA table_info({quote_identifier(DISCOVERED_TABLE)})"
                )
            }
            required = {
                "wallet",
                "username",
                "elite_score",
                "elite_grade",
                "primary_category",
                "active_watchlist",
                "manually_approved",
            }
            missing = required - columns
            if missing:
                raise RuntimeError(
                    "discovered_wallets is missing required columns: "
                    + ", ".join(sorted(missing))
                )
        finally:
            connection.close()

    def create_tables(self) -> None:
        connection = self.connect()
        try:
            connection.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_identifier(RUNS_TABLE)} (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    candidate_limit INTEGER NOT NULL,
                    min_elite_score REAL NOT NULL,
                    wallets_selected INTEGER NOT NULL DEFAULT 0,
                    wallets_completed INTEGER NOT NULL DEFAULT 0,
                    wallets_failed INTEGER NOT NULL DEFAULT 0,
                    API_queries INTEGER NOT NULL DEFAULT 0,
                    current_positions_collected INTEGER NOT NULL DEFAULT 0,
                    closed_positions_collected INTEGER NOT NULL DEFAULT 0,
                    trades_collected INTEGER NOT NULL DEFAULT 0,
                    activity_rows_collected INTEGER NOT NULL DEFAULT 0,
                    profile_rows_upserted INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(PROFILES_TABLE)} (
                    wallet TEXT PRIMARY KEY,
                    username TEXT,
                    source_elite_score REAL NOT NULL DEFAULT 0,
                    source_elite_grade TEXT,
                    primary_category TEXT,
                    first_profiled_at TEXT NOT NULL,
                    last_profiled_at TEXT NOT NULL,
                    profile_scan_count INTEGER NOT NULL DEFAULT 1,
                    position_value REAL NOT NULL DEFAULT 0,
                    total_markets_traded INTEGER NOT NULL DEFAULT 0,
                    current_position_count INTEGER NOT NULL DEFAULT 0,
                    closed_position_count INTEGER NOT NULL DEFAULT 0,
                    trade_sample_count INTEGER NOT NULL DEFAULT 0,
                    activity_sample_count INTEGER NOT NULL DEFAULT 0,
                    latest_collection_status TEXT NOT NULL,
                    latest_error_message TEXT,
                    last_run_id TEXT NOT NULL,
                    FOREIGN KEY(last_run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(CURRENT_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    asset TEXT,
                    condition_id TEXT,
                    size REAL NOT NULL DEFAULT 0,
                    avg_price REAL NOT NULL DEFAULT 0,
                    initial_value REAL NOT NULL DEFAULT 0,
                    current_value REAL NOT NULL DEFAULT 0,
                    cash_pnl REAL NOT NULL DEFAULT 0,
                    percent_pnl REAL NOT NULL DEFAULT 0,
                    total_bought REAL NOT NULL DEFAULT 0,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    percent_realized_pnl REAL NOT NULL DEFAULT 0,
                    current_price REAL NOT NULL DEFAULT 0,
                    redeemable INTEGER NOT NULL DEFAULT 0,
                    mergeable INTEGER NOT NULL DEFAULT 0,
                    title TEXT,
                    slug TEXT,
                    event_slug TEXT,
                    outcome TEXT,
                    outcome_index INTEGER,
                    opposite_outcome TEXT,
                    opposite_asset TEXT,
                    end_date TEXT,
                    negative_risk INTEGER NOT NULL DEFAULT 0,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(CLOSED_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    asset TEXT,
                    condition_id TEXT,
                    avg_price REAL NOT NULL DEFAULT 0,
                    total_bought REAL NOT NULL DEFAULT 0,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    current_price REAL NOT NULL DEFAULT 0,
                    closed_timestamp INTEGER,
                    title TEXT,
                    slug TEXT,
                    event_slug TEXT,
                    outcome TEXT,
                    outcome_index INTEGER,
                    opposite_outcome TEXT,
                    opposite_asset TEXT,
                    end_date TEXT,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(TRADES_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    side TEXT,
                    asset TEXT,
                    condition_id TEXT,
                    size REAL NOT NULL DEFAULT 0,
                    price REAL NOT NULL DEFAULT 0,
                    trade_timestamp INTEGER,
                    title TEXT,
                    slug TEXT,
                    event_slug TEXT,
                    outcome TEXT,
                    outcome_index INTEGER,
                    transaction_hash TEXT,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(ACTIVITY_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    activity_timestamp INTEGER,
                    condition_id TEXT,
                    activity_type TEXT,
                    size REAL NOT NULL DEFAULT 0,
                    usdc_size REAL NOT NULL DEFAULT 0,
                    transaction_hash TEXT,
                    price REAL NOT NULL DEFAULT 0,
                    asset TEXT,
                    side TEXT,
                    outcome_index INTEGER,
                    title TEXT,
                    slug TEXT,
                    event_slug TEXT,
                    outcome TEXT,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_wallet_profiles_score
                    ON {quote_identifier(PROFILES_TABLE)}(
                        source_elite_score DESC,
                        total_markets_traded DESC
                    );

                CREATE INDEX IF NOT EXISTS idx_current_positions_wallet
                    ON {quote_identifier(CURRENT_TABLE)}(
                        wallet,
                        observed_at DESC
                    );

                CREATE INDEX IF NOT EXISTS idx_closed_positions_wallet
                    ON {quote_identifier(CLOSED_TABLE)}(
                        wallet,
                        closed_timestamp DESC
                    );

                CREATE INDEX IF NOT EXISTS idx_trade_snapshots_wallet
                    ON {quote_identifier(TRADES_TABLE)}(
                        wallet,
                        trade_timestamp DESC
                    );

                CREATE INDEX IF NOT EXISTS idx_activity_snapshots_wallet
                    ON {quote_identifier(ACTIVITY_TABLE)}(
                        wallet,
                        activity_timestamp DESC
                    );
                """
            )
            connection.commit()
        finally:
            connection.close()

    def select_candidates(self) -> list[CandidateWallet]:
        connection = self.connect()
        try:
            where_parts = ["elite_score >= ?"]
            params: list[Any] = [self.min_elite_score]

            if self.include_watchlist_only:
                where_parts.append(
                    "(active_watchlist = 1 OR manually_approved = 1)"
                )

            rows = connection.execute(
                f"""
                SELECT
                    wallet,
                    COALESCE(username, '') AS username,
                    COALESCE(elite_score, 0) AS elite_score,
                    COALESCE(elite_grade, '') AS elite_grade,
                    COALESCE(primary_category, '') AS primary_category,
                    COALESCE(active_watchlist, 0) AS active_watchlist,
                    COALESCE(manually_approved, 0) AS manually_approved
                FROM {quote_identifier(DISCOVERED_TABLE)}
                WHERE {' AND '.join(where_parts)}
                ORDER BY
                    manually_approved DESC,
                    active_watchlist DESC,
                    elite_score DESC,
                    CASE
                        WHEN best_rank IS NULL OR best_rank = 0 THEN 999999
                        ELSE best_rank
                    END ASC,
                    wallet ASC
                LIMIT ?
                """,
                (*params, self.candidate_limit),
            ).fetchall()

            candidates: list[CandidateWallet] = []
            for row in rows:
                wallet = normalize_wallet(row["wallet"])
                if not wallet:
                    LOGGER.warning(
                        "Skipping malformed discovered wallet: %r",
                        row["wallet"],
                    )
                    continue

                candidates.append(
                    CandidateWallet(
                        wallet=wallet,
                        username=clean_text(row["username"]),
                        elite_score=safe_float(row["elite_score"]),
                        elite_grade=clean_text(row["elite_grade"]),
                        primary_category=clean_text(
                            row["primary_category"]
                        ),
                        active_watchlist=safe_int(
                            row["active_watchlist"]
                        ),
                        manually_approved=safe_int(
                            row["manually_approved"]
                        ),
                    )
                )

            return candidates
        finally:
            connection.close()

    def fetch_value(self, wallet: str) -> tuple[float, int]:
        payload = self.client.get_json("/value", {"user": wallet})
        if not isinstance(payload, list):
            raise RuntimeError(
                f"Unexpected /value response: {type(payload).__name__}"
            )

        value = 0.0
        for row in payload:
            if isinstance(row, dict):
                value += safe_float(row.get("value"))

        return value, 1

    def fetch_traded(self, wallet: str) -> tuple[int, int]:
        payload = self.client.get_json("/traded", {"user": wallet})
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"Unexpected /traded response: {type(payload).__name__}"
            )
        return safe_int(payload.get("traded")), 1

    def fetch_current_positions(
        self,
        wallet: str,
    ) -> tuple[list[dict[str, Any]], int]:
        return self.client.fetch_paginated_list(
            "/positions",
            params={
                "user": wallet,
                "sortBy": "CURRENT",
                "sortDirection": "DESC",
            },
            page_size=DEFAULT_PAGE_SIZE,
            max_rows=1000,
            offset_limit=100000,
        )

    def fetch_closed_positions(
        self,
        wallet: str,
    ) -> tuple[list[dict[str, Any]], int]:
        return self.client.fetch_paginated_list(
            "/closed-positions",
            params={
                "user": wallet,
                "sortBy": "TIMESTAMP",
                "sortDirection": "DESC",
            },
            page_size=DEFAULT_PAGE_SIZE,
            max_rows=self.max_closed_positions,
            offset_limit=100000,
        )

    def fetch_trades(
        self,
        wallet: str,
    ) -> tuple[list[dict[str, Any]], int]:
        return self.client.fetch_paginated_list(
            "/trades",
            params={
                "user": wallet,
                "takerOnly": "false",
            },
            page_size=min(1000, self.max_trades),
            max_rows=self.max_trades,
            offset_limit=10000,
        )

    def fetch_activity(
        self,
        wallet: str,
    ) -> tuple[list[dict[str, Any]], int]:
        return self.client.fetch_paginated_list(
            "/activity",
            params={
                "user": wallet,
                "sortDirection": "DESC",
            },
            page_size=min(500, self.max_activity),
            max_rows=self.max_activity,
            offset_limit=10000,
        )

    def collect_wallet(
        self,
        candidate: CandidateWallet,
    ) -> WalletCollection:
        LOGGER.info(
            "Collecting wallet=%s score=%.2f grade=%s",
            candidate.wallet,
            candidate.elite_score,
            candidate.elite_grade or "-",
        )

        position_value = 0.0
        total_markets_traded = 0
        current_positions: list[dict[str, Any]] = []
        closed_positions: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []
        activity: list[dict[str, Any]] = []
        query_count = 0
        errors: list[str] = []

        collectors = (
            (
                "value",
                lambda: self.fetch_value(candidate.wallet),
            ),
            (
                "traded",
                lambda: self.fetch_traded(candidate.wallet),
            ),
            (
                "current_positions",
                lambda: self.fetch_current_positions(candidate.wallet),
            ),
            (
                "closed_positions",
                lambda: self.fetch_closed_positions(candidate.wallet),
            ),
            (
                "trades",
                lambda: self.fetch_trades(candidate.wallet),
            ),
            (
                "activity",
                lambda: self.fetch_activity(candidate.wallet),
            ),
        )

        for label, collector in collectors:
            try:
                result, used_queries = collector()
                query_count += used_queries

                if label == "value":
                    position_value = safe_float(result)
                elif label == "traded":
                    total_markets_traded = safe_int(result)
                elif label == "current_positions":
                    current_positions = list(result)
                elif label == "closed_positions":
                    closed_positions = list(result)
                elif label == "trades":
                    trades = list(result)
                elif label == "activity":
                    activity = list(result)

            except Exception as exc:
                message = f"{label}: {exc}"
                errors.append(message)
                LOGGER.error(
                    "Wallet %s collection error: %s",
                    candidate.wallet,
                    message,
                )

        return WalletCollection(
            candidate=candidate,
            position_value=position_value,
            total_markets_traded=total_markets_traded,
            current_positions=current_positions,
            closed_positions=closed_positions,
            trades=trades,
            activity=activity,
            API_queries=query_count,
            errors=errors,
        )

    def persist_collection(
        self,
        *,
        run_id: str,
        observed_at: str,
        collection: WalletCollection,
    ) -> None:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            candidate = collection.candidate
            status = "SUCCESS" if not collection.errors else "PARTIAL"
            error_message = "; ".join(collection.errors) or None

            connection.execute(
                f"""
                INSERT INTO {quote_identifier(PROFILES_TABLE)} (
                    wallet,
                    username,
                    source_elite_score,
                    source_elite_grade,
                    primary_category,
                    first_profiled_at,
                    last_profiled_at,
                    profile_scan_count,
                    position_value,
                    total_markets_traded,
                    current_position_count,
                    closed_position_count,
                    trade_sample_count,
                    activity_sample_count,
                    latest_collection_status,
                    latest_error_message,
                    last_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(wallet) DO UPDATE SET
                    username=CASE
                        WHEN excluded.username <> '' THEN excluded.username
                        ELSE {quote_identifier(PROFILES_TABLE)}.username
                    END,
                    source_elite_score=excluded.source_elite_score,
                    source_elite_grade=excluded.source_elite_grade,
                    primary_category=excluded.primary_category,
                    last_profiled_at=excluded.last_profiled_at,
                    profile_scan_count=
                        {quote_identifier(PROFILES_TABLE)}.profile_scan_count + 1,
                    position_value=excluded.position_value,
                    total_markets_traded=excluded.total_markets_traded,
                    current_position_count=excluded.current_position_count,
                    closed_position_count=excluded.closed_position_count,
                    trade_sample_count=excluded.trade_sample_count,
                    activity_sample_count=excluded.activity_sample_count,
                    latest_collection_status=
                        excluded.latest_collection_status,
                    latest_error_message=excluded.latest_error_message,
                    last_run_id=excluded.last_run_id
                """,
                (
                    candidate.wallet,
                    candidate.username,
                    candidate.elite_score,
                    candidate.elite_grade,
                    candidate.primary_category,
                    observed_at,
                    observed_at,
                    collection.position_value,
                    collection.total_markets_traded,
                    collection.current_position_count,
                    collection.closed_position_count,
                    collection.trade_count,
                    collection.activity_count,
                    status,
                    error_message,
                    run_id,
                ),
            )

            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(CURRENT_TABLE)} (
                    run_id,
                    wallet,
                    asset,
                    condition_id,
                    size,
                    avg_price,
                    initial_value,
                    current_value,
                    cash_pnl,
                    percent_pnl,
                    total_bought,
                    realized_pnl,
                    percent_realized_pnl,
                    current_price,
                    redeemable,
                    mergeable,
                    title,
                    slug,
                    event_slug,
                    outcome,
                    outcome_index,
                    opposite_outcome,
                    opposite_asset,
                    end_date,
                    negative_risk,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    (
                        run_id,
                        candidate.wallet,
                        clean_text(row.get("asset")),
                        normalize_condition_id(row.get("conditionId")),
                        safe_float(row.get("size")),
                        safe_float(row.get("avgPrice")),
                        safe_float(row.get("initialValue")),
                        safe_float(row.get("currentValue")),
                        safe_float(row.get("cashPnl")),
                        safe_float(row.get("percentPnl")),
                        safe_float(row.get("totalBought")),
                        safe_float(row.get("realizedPnl")),
                        safe_float(row.get("percentRealizedPnl")),
                        safe_float(row.get("curPrice")),
                        safe_bool_int(row.get("redeemable")),
                        safe_bool_int(row.get("mergeable")),
                        clean_text(row.get("title")),
                        clean_text(row.get("slug")),
                        clean_text(row.get("eventSlug")),
                        clean_text(row.get("outcome")),
                        safe_int(row.get("outcomeIndex")),
                        clean_text(row.get("oppositeOutcome")),
                        clean_text(row.get("oppositeAsset")),
                        clean_text(row.get("endDate")),
                        safe_bool_int(row.get("negativeRisk")),
                        observed_at,
                    )
                    for row in collection.current_positions
                ],
            )

            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(CLOSED_TABLE)} (
                    run_id,
                    wallet,
                    asset,
                    condition_id,
                    avg_price,
                    total_bought,
                    realized_pnl,
                    current_price,
                    closed_timestamp,
                    title,
                    slug,
                    event_slug,
                    outcome,
                    outcome_index,
                    opposite_outcome,
                    opposite_asset,
                    end_date,
                    observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        candidate.wallet,
                        clean_text(row.get("asset")),
                        normalize_condition_id(row.get("conditionId")),
                        safe_float(row.get("avgPrice")),
                        safe_float(row.get("totalBought")),
                        safe_float(row.get("realizedPnl")),
                        safe_float(row.get("curPrice")),
                        safe_int(row.get("timestamp")),
                        clean_text(row.get("title")),
                        clean_text(row.get("slug")),
                        clean_text(row.get("eventSlug")),
                        clean_text(row.get("outcome")),
                        safe_int(row.get("outcomeIndex")),
                        clean_text(row.get("oppositeOutcome")),
                        clean_text(row.get("oppositeAsset")),
                        clean_text(row.get("endDate")),
                        observed_at,
                    )
                    for row in collection.closed_positions
                ],
            )

            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(TRADES_TABLE)} (
                    run_id,
                    wallet,
                    side,
                    asset,
                    condition_id,
                    size,
                    price,
                    trade_timestamp,
                    title,
                    slug,
                    event_slug,
                    outcome,
                    outcome_index,
                    transaction_hash,
                    observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        candidate.wallet,
                        clean_text(row.get("side")).upper(),
                        clean_text(row.get("asset")),
                        normalize_condition_id(row.get("conditionId")),
                        safe_float(row.get("size")),
                        safe_float(row.get("price")),
                        safe_int(row.get("timestamp")),
                        clean_text(row.get("title")),
                        clean_text(row.get("slug")),
                        clean_text(row.get("eventSlug")),
                        clean_text(row.get("outcome")),
                        safe_int(row.get("outcomeIndex")),
                        clean_text(row.get("transactionHash")),
                        observed_at,
                    )
                    for row in collection.trades
                ],
            )

            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(ACTIVITY_TABLE)} (
                    run_id,
                    wallet,
                    activity_timestamp,
                    condition_id,
                    activity_type,
                    size,
                    usdc_size,
                    transaction_hash,
                    price,
                    asset,
                    side,
                    outcome_index,
                    title,
                    slug,
                    event_slug,
                    outcome,
                    observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        candidate.wallet,
                        safe_int(row.get("timestamp")),
                        normalize_condition_id(row.get("conditionId")),
                        clean_text(row.get("type")).upper(),
                        safe_float(row.get("size")),
                        safe_float(row.get("usdcSize")),
                        clean_text(row.get("transactionHash")),
                        safe_float(row.get("price")),
                        clean_text(row.get("asset")),
                        clean_text(row.get("side")).upper(),
                        safe_int(row.get("outcomeIndex")),
                        clean_text(row.get("title")),
                        clean_text(row.get("slug")),
                        clean_text(row.get("eventSlug")),
                        clean_text(row.get("outcome")),
                        observed_at,
                    )
                    for row in collection.activity
                ],
            )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def run(self, *, apply: bool = False) -> dict[str, Any]:
        self.validate_dependencies()
        self.create_tables()

        run_id = uuid.uuid4().hex
        started_at = utc_now()
        observed_at = started_at.isoformat()
        mode = "APPLY" if apply else "DRY RUN"

        candidates = self.select_candidates()

        connection = self.connect()
        try:
            connection.execute(
                f"""
                INSERT INTO {quote_identifier(RUNS_TABLE)} (
                    run_id,
                    started_at,
                    mode,
                    candidate_limit,
                    min_elite_score,
                    wallets_selected,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    observed_at,
                    mode,
                    self.candidate_limit,
                    self.min_elite_score,
                    len(candidates),
                    "RUNNING",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        collections: list[WalletCollection] = []
        total_queries = 0
        completed = 0
        failed = 0
        current_count = 0
        closed_count = 0
        trade_count = 0
        activity_count = 0
        profile_rows_upserted = 0
        status = "SUCCESS"
        error_message = ""

        try:
            for candidate in candidates:
                collection = self.collect_wallet(candidate)
                collections.append(collection)
                total_queries += collection.API_queries
                current_count += collection.current_position_count
                closed_count += collection.closed_position_count
                trade_count += collection.trade_count
                activity_count += collection.activity_count

                if collection.errors:
                    failed += 1
                else:
                    completed += 1

                if apply:
                    self.persist_collection(
                        run_id=run_id,
                        observed_at=observed_at,
                        collection=collection,
                    )
                    profile_rows_upserted += 1

            if failed and completed:
                status = "PARTIAL"
            elif failed and not completed:
                status = "FAILED"

        except Exception as exc:
            status = "FAILED"
            error_message = str(exc)
            raise

        finally:
            finished_at = utc_now()
            connection = self.connect()
            try:
                connection.execute(
                    f"""
                    UPDATE {quote_identifier(RUNS_TABLE)}
                    SET
                        finished_at=?,
                        wallets_completed=?,
                        wallets_failed=?,
                        API_queries=?,
                        current_positions_collected=?,
                        closed_positions_collected=?,
                        trades_collected=?,
                        activity_rows_collected=?,
                        profile_rows_upserted=?,
                        status=?,
                        error_message=?
                    WHERE run_id=?
                    """,
                    (
                        finished_at.isoformat(),
                        completed,
                        failed,
                        total_queries,
                        current_count,
                        closed_count,
                        trade_count,
                        activity_count,
                        profile_rows_upserted,
                        status,
                        error_message or None,
                        run_id,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

        return {
            "run_id": run_id,
            "database_path": str(self.database_path),
            "mode": mode,
            "candidate_limit": self.candidate_limit,
            "min_elite_score": self.min_elite_score,
            "wallets_selected": len(candidates),
            "wallets_completed": completed,
            "wallets_failed": failed,
            "API_queries": total_queries,
            "current_positions_collected": current_count,
            "closed_positions_collected": closed_count,
            "trades_collected": trade_count,
            "activity_rows_collected": activity_count,
            "profile_rows_upserted": profile_rows_upserted,
            "collections": collections,
            "status": status,
            "duration_seconds": (finished_at - started_at).total_seconds(),
        }


def print_report(report: dict[str, Any]) -> None:
    print()
    print("=" * 118)
    print("WALLET PROFILE COLLECTOR")
    print("=" * 118)
    print(f"{'Database:':38} {report['database_path']}")
    print(f"{'Mode:':38} {report['mode']}")
    print(f"{'Run ID:':38} {report['run_id']}")
    print(f"{'Candidate limit:':38} {report['candidate_limit']}")
    print(f"{'Minimum elite score:':38} {report['min_elite_score']:.2f}")
    print(f"{'Wallets selected:':38} {report['wallets_selected']}")
    print(f"{'Wallets completed:':38} {report['wallets_completed']}")
    print(f"{'Wallets with collection errors:':38} {report['wallets_failed']}")
    print(f"{'API queries:':38} {report['API_queries']}")
    print(
        f"{'Current positions collected:':38} "
        f"{report['current_positions_collected']}"
    )
    print(
        f"{'Closed positions collected:':38} "
        f"{report['closed_positions_collected']}"
    )
    print(f"{'Trades collected:':38} {report['trades_collected']}")
    print(
        f"{'Activity rows collected:':38} "
        f"{report['activity_rows_collected']}"
    )
    print(
        f"{'Profile rows upserted:':38} "
        f"{report['profile_rows_upserted']}"
    )
    print(f"{'Duration:':38} {report['duration_seconds']:.3f}s")
    print(f"{'Status:':38} {report['status']}")

    print()
    print("WALLET COLLECTION SUMMARY")
    print("-" * 118)

    collections: list[WalletCollection] = report["collections"]
    if not collections:
        print(
            "No candidates selected. Run the discovery engine with --apply "
            "or lower --min-elite-score."
        )
    else:
        for index, collection in enumerate(collections, start=1):
            candidate = collection.candidate
            collection_status = (
                "SUCCESS" if not collection.errors else "PARTIAL"
            )
            print(
                f"{index:>3}. {candidate.elite_grade or '-':<6} "
                f"score={candidate.elite_score:>6.2f} "
                f"status={collection_status:<7} "
                f"{candidate.username or 'anonymous'}"
            )
            print(f"     {candidate.wallet}")
            print(
                "     "
                f"value=${collection.position_value:,.2f} | "
                f"markets={collection.total_markets_traded} | "
                f"open={collection.current_position_count} | "
                f"closed={collection.closed_position_count} | "
                f"trades={collection.trade_count} | "
                f"activity={collection.activity_count}"
            )
            for error in collection.errors:
                print(f"     ERROR: {error}")

    print("=" * 118)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect raw public Polymarket profile, position, trade, and "
            "activity data for elite wallet-discovery candidates."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist collected wallet profiles and raw snapshot rows.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=DEFAULT_CANDIDATE_LIMIT,
        help="Maximum number of discovered wallets to collect.",
    )
    parser.add_argument(
        "--min-elite-score",
        type=float,
        default=DEFAULT_MIN_ELITE_SCORE,
        help="Minimum discovery score required for candidate selection.",
    )
    parser.add_argument(
        "--watchlist-only",
        action="store_true",
        help=(
            "Only select wallets whose active_watchlist or "
            "manually_approved flag is enabled."
        ),
    )
    parser.add_argument(
        "--max-closed-positions",
        type=int,
        default=DEFAULT_MAX_CLOSED_POSITIONS,
        help="Maximum recent closed positions collected per wallet.",
    )
    parser.add_argument(
        "--max-trades",
        type=int,
        default=DEFAULT_MAX_TRADES,
        help="Maximum recent trades collected per wallet.",
    )
    parser.add_argument(
        "--max-activity",
        type=int,
        default=DEFAULT_MAX_ACTIVITY,
        help="Maximum recent activity rows collected per wallet.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed logging.",
    )
    return parser.parse_args()


def main() -> None:
    configure_utf8()
    args = parse_args()
    configure_logging(args.verbose)

    collector = WalletProfileCollector(
        candidate_limit=args.candidate_limit,
        min_elite_score=args.min_elite_score,
        include_watchlist_only=args.watchlist_only,
        max_closed_positions=args.max_closed_positions,
        max_trades=args.max_trades,
        max_activity=args.max_activity,
    )
    report = collector.run(apply=args.apply)
    print_report(report)


if __name__ == "__main__":
    main()