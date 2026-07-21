from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict
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
LEADERBOARD_ENDPOINT = "/v1/leaderboard"

DEFAULT_CATEGORIES = (
    "OVERALL",
    "SPORTS",
    "ESPORTS",
    "POLITICS",
    "CRYPTO",
    "WEATHER",
    "ECONOMICS",
    "TECH",
    "FINANCE",
    "CULTURE",
)

DEFAULT_PERIODS = ("DAY", "WEEK", "MONTH", "ALL")
DEFAULT_ORDER_BY = "PNL"
DEFAULT_LIMIT = 50
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRIES = 3

RUNS_TABLE = "wallet_discovery_runs"
SNAPSHOTS_TABLE = "wallet_leaderboard_snapshots"
WALLETS_TABLE = "discovered_wallets"
SPECIALTIES_TABLE = "wallet_category_specialties"

WALLET_RE = __import__("re").compile(r"^0x[a-fA-F0-9]{40}$")


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


@dataclass(slots=True)
class LeaderboardEntry:
    wallet: str
    username: str
    rank: int
    volume: float
    pnl: float
    category: str
    time_period: str
    order_by: str
    verified_badge: int
    x_username: str
    profile_image: str

    @property
    def roi_proxy(self) -> float:
        if self.volume <= 0:
            return 0.0
        return self.pnl / self.volume


@dataclass(slots=True)
class WalletAggregate:
    wallet: str
    username: str = ""
    x_username: str = ""
    profile_image: str = ""
    verified_badge: int = 0
    appearances: int = 0
    categories_seen: int = 0
    periods_seen: int = 0
    best_rank: int = 0
    total_pnl_signal: float = 0.0
    total_volume_signal: float = 0.0
    average_rank_score: float = 0.0
    elite_score: float = 0.0
    elite_grade: str = ""
    primary_category: str = ""
    discovery_reason: str = ""


class PolymarketLeaderboardClient:
    def __init__(
        self,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        retries: int = DEFAULT_RETRIES,
        pause_seconds: float = 0.15,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.pause_seconds = pause_seconds

    def get_json(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{DATA_API_BASE}{path}?{urllib.parse.urlencode(params)}"
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
                    return json.loads(payload)
            except Exception as exc:
                last_error = exc
                if attempt == self.retries:
                    break
                sleep_seconds = min(2 ** (attempt - 1), 5)
                LOGGER.warning(
                    "Request failed (%s/%s): %s. Retrying in %ss.",
                    attempt,
                    self.retries,
                    exc,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)

        raise RuntimeError(f"Leaderboard request failed: {last_error}")

    def fetch_leaderboard(
        self,
        *,
        category: str,
        time_period: str,
        order_by: str,
        limit: int,
        offset: int = 0,
    ) -> list[LeaderboardEntry]:
        payload = self.get_json(
            LEADERBOARD_ENDPOINT,
            {
                "category": category,
                "timePeriod": time_period,
                "orderBy": order_by,
                "limit": limit,
                "offset": offset,
            },
        )

        if not isinstance(payload, list):
            raise RuntimeError(
                f"Unexpected leaderboard response for {category}/{time_period}: "
                f"{type(payload).__name__}"
            )

        entries: list[LeaderboardEntry] = []
        for row in payload:
            if not isinstance(row, dict):
                continue

            wallet = clean_text(row.get("proxyWallet")).lower()
            if not WALLET_RE.fullmatch(wallet):
                LOGGER.debug("Skipping invalid wallet: %r", wallet)
                continue

            entries.append(
                LeaderboardEntry(
                    wallet=wallet,
                    username=clean_text(row.get("userName")),
                    rank=safe_int(row.get("rank")),
                    volume=safe_float(row.get("vol")),
                    pnl=safe_float(row.get("pnl")),
                    category=category,
                    time_period=time_period,
                    order_by=order_by,
                    verified_badge=int(bool(row.get("verifiedBadge"))),
                    x_username=clean_text(row.get("xUsername")),
                    profile_image=clean_text(row.get("profileImage")),
                )
            )

        time.sleep(self.pause_seconds)
        return entries


class EliteWalletDiscoveryEngine:
    def __init__(
        self,
        database_path: Path | str = DATABASE_PATH,
        *,
        categories: Sequence[str] = DEFAULT_CATEGORIES,
        periods: Sequence[str] = DEFAULT_PERIODS,
        order_by: str = DEFAULT_ORDER_BY,
        leaderboard_limit: int = DEFAULT_LIMIT,
    ) -> None:
        self.database_path = Path(database_path)
        self.categories = tuple(dict.fromkeys(category.upper() for category in categories))
        self.periods = tuple(dict.fromkeys(period.upper() for period in periods))
        self.order_by = order_by.upper()
        self.leaderboard_limit = max(1, min(int(leaderboard_limit), 50))
        self.client = PolymarketLeaderboardClient()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

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
                    categories_scanned INTEGER NOT NULL DEFAULT 0,
                    periods_scanned INTEGER NOT NULL DEFAULT 0,
                    API_queries INTEGER NOT NULL DEFAULT 0,
                    leaderboard_rows INTEGER NOT NULL DEFAULT 0,
                    unique_wallets INTEGER NOT NULL DEFAULT 0,
                    wallet_rows_upserted INTEGER NOT NULL DEFAULT 0,
                    snapshot_rows_inserted INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(SNAPSHOTS_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    username TEXT,
                    category TEXT NOT NULL,
                    time_period TEXT NOT NULL,
                    order_by TEXT NOT NULL,
                    leaderboard_rank INTEGER,
                    pnl REAL NOT NULL DEFAULT 0,
                    volume REAL NOT NULL DEFAULT 0,
                    roi_proxy REAL NOT NULL DEFAULT 0,
                    verified_badge INTEGER NOT NULL DEFAULT 0,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(WALLETS_TABLE)} (
                    wallet TEXT PRIMARY KEY,
                    username TEXT,
                    x_username TEXT,
                    profile_image TEXT,
                    verified_badge INTEGER NOT NULL DEFAULT 0,
                    first_discovered_at TEXT NOT NULL,
                    last_discovered_at TEXT NOT NULL,
                    discovery_count INTEGER NOT NULL DEFAULT 1,
                    leaderboard_appearances INTEGER NOT NULL DEFAULT 0,
                    categories_seen INTEGER NOT NULL DEFAULT 0,
                    periods_seen INTEGER NOT NULL DEFAULT 0,
                    best_rank INTEGER,
                    total_pnl_signal REAL NOT NULL DEFAULT 0,
                    total_volume_signal REAL NOT NULL DEFAULT 0,
                    elite_score REAL NOT NULL DEFAULT 0,
                    elite_grade TEXT,
                    primary_category TEXT,
                    discovery_reason TEXT,
                    active_watchlist INTEGER NOT NULL DEFAULT 0,
                    manually_approved INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(SPECIALTIES_TABLE)} (
                    wallet TEXT NOT NULL,
                    category TEXT NOT NULL,
                    appearances INTEGER NOT NULL DEFAULT 0,
                    best_rank INTEGER,
                    pnl_signal REAL NOT NULL DEFAULT 0,
                    volume_signal REAL NOT NULL DEFAULT 0,
                    specialty_score REAL NOT NULL DEFAULT 0,
                    specialty_grade TEXT,
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY(wallet, category),
                    FOREIGN KEY(wallet)
                        REFERENCES {quote_identifier(WALLETS_TABLE)}(wallet)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_wallet_time
                    ON {quote_identifier(SNAPSHOTS_TABLE)}(
                        wallet,
                        observed_at DESC
                    );

                CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_category_period
                    ON {quote_identifier(SNAPSHOTS_TABLE)}(
                        category,
                        time_period,
                        leaderboard_rank
                    );

                CREATE INDEX IF NOT EXISTS idx_discovered_wallets_elite
                    ON {quote_identifier(WALLETS_TABLE)}(
                        elite_score DESC,
                        best_rank ASC
                    );

                CREATE INDEX IF NOT EXISTS idx_wallet_specialties_category
                    ON {quote_identifier(SPECIALTIES_TABLE)}(
                        category,
                        specialty_score DESC
                    );
                """
            )
            connection.commit()
        finally:
            connection.close()

    def collect(self) -> tuple[list[LeaderboardEntry], int]:
        entries: list[LeaderboardEntry] = []
        query_count = 0

        for category in self.categories:
            for period in self.periods:
                LOGGER.info(
                    "Fetching leaderboard category=%s period=%s order=%s",
                    category,
                    period,
                    self.order_by,
                )
                batch = self.client.fetch_leaderboard(
                    category=category,
                    time_period=period,
                    order_by=self.order_by,
                    limit=self.leaderboard_limit,
                )
                entries.extend(batch)
                query_count += 1

        return entries, query_count

    @staticmethod
    def grade(score: float) -> str:
        if score >= 90:
            return "S+"
        if score >= 82:
            return "S"
        if score >= 74:
            return "A+"
        if score >= 66:
            return "A"
        if score >= 58:
            return "B+"
        if score >= 50:
            return "B"
        if score >= 40:
            return "C"
        return "WATCH"

    def aggregate(
        self,
        entries: Sequence[LeaderboardEntry],
    ) -> tuple[list[WalletAggregate], dict[tuple[str, str], dict[str, Any]]]:
        by_wallet: dict[str, list[LeaderboardEntry]] = defaultdict(list)
        for entry in entries:
            by_wallet[entry.wallet].append(entry)

        wallet_results: list[WalletAggregate] = []
        specialty_results: dict[tuple[str, str], dict[str, Any]] = {}

        total_boards = max(1, len(self.categories) * len(self.periods))

        for wallet, wallet_entries in by_wallet.items():
            categories = {entry.category for entry in wallet_entries}
            periods = {entry.time_period for entry in wallet_entries}
            positive_entries = [entry for entry in wallet_entries if entry.pnl > 0]

            best_rank = min(
                (entry.rank for entry in wallet_entries if entry.rank > 0),
                default=0,
            )

            rank_scores = [
                max(0.0, 1.0 - ((entry.rank - 1) / max(1, self.leaderboard_limit)))
                for entry in wallet_entries
                if entry.rank > 0
            ]
            average_rank_score = (
                sum(rank_scores) / len(rank_scores) if rank_scores else 0.0
            )

            recurrence_score = min(1.0, len(wallet_entries) / total_boards)
            positive_rate = len(positive_entries) / max(1, len(wallet_entries))
            breadth_score = min(1.0, len(categories) / 4.0)
            period_score = min(1.0, len(periods) / max(1, len(self.periods)))
            verification_score = 1.0 if any(e.verified_badge for e in wallet_entries) else 0.0

            pnl_signal = sum(max(0.0, entry.pnl) for entry in wallet_entries)
            volume_signal = sum(max(0.0, entry.volume) for entry in wallet_entries)
            efficiency_values = [
                max(-1.0, min(1.0, entry.roi_proxy))
                for entry in wallet_entries
                if entry.volume > 0
            ]
            efficiency_score = (
                max(0.0, sum(efficiency_values) / len(efficiency_values))
                if efficiency_values
                else 0.0
            )

            elite_score = 100.0 * (
                0.30 * average_rank_score
                + 0.20 * recurrence_score
                + 0.18 * positive_rate
                + 0.12 * period_score
                + 0.08 * breadth_score
                + 0.07 * efficiency_score
                + 0.05 * verification_score
            )

            category_groups: dict[str, list[LeaderboardEntry]] = defaultdict(list)
            for entry in wallet_entries:
                category_groups[entry.category].append(entry)

            category_scores: dict[str, float] = {}
            for category, category_entries in category_groups.items():
                category_rank_scores = [
                    max(
                        0.0,
                        1.0 - (
                            (entry.rank - 1)
                            / max(1, self.leaderboard_limit)
                        ),
                    )
                    for entry in category_entries
                    if entry.rank > 0
                ]
                category_rank_score = (
                    sum(category_rank_scores) / len(category_rank_scores)
                    if category_rank_scores
                    else 0.0
                )
                category_positive_rate = (
                    sum(1 for entry in category_entries if entry.pnl > 0)
                    / max(1, len(category_entries))
                )
                category_period_coverage = min(
                    1.0,
                    len({entry.time_period for entry in category_entries})
                    / max(1, len(self.periods)),
                )
                category_efficiency_values = [
                    max(-1.0, min(1.0, entry.roi_proxy))
                    for entry in category_entries
                    if entry.volume > 0
                ]
                category_efficiency = (
                    max(
                        0.0,
                        sum(category_efficiency_values)
                        / len(category_efficiency_values),
                    )
                    if category_efficiency_values
                    else 0.0
                )

                specialty_score = 100.0 * (
                    0.45 * category_rank_score
                    + 0.25 * category_positive_rate
                    + 0.20 * category_period_coverage
                    + 0.10 * category_efficiency
                )
                category_scores[category] = specialty_score

                specialty_results[(wallet, category)] = {
                    "wallet": wallet,
                    "category": category,
                    "appearances": len(category_entries),
                    "best_rank": min(
                        (
                            entry.rank
                            for entry in category_entries
                            if entry.rank > 0
                        ),
                        default=0,
                    ),
                    "pnl_signal": sum(entry.pnl for entry in category_entries),
                    "volume_signal": sum(
                        entry.volume for entry in category_entries
                    ),
                    "specialty_score": specialty_score,
                    "specialty_grade": self.grade(specialty_score),
                }

            primary_category = max(
                category_scores,
                key=category_scores.get,
                default="OVERALL",
            )
            representative = sorted(
                wallet_entries,
                key=lambda entry: (
                    entry.rank if entry.rank > 0 else 999999,
                    -entry.pnl,
                ),
            )[0]

            reason_parts = [
                f"{len(wallet_entries)} leaderboard appearances",
                f"{len(categories)} categories",
                f"{len(periods)} periods",
            ]
            if best_rank:
                reason_parts.append(f"best rank #{best_rank}")
            if positive_rate >= 0.75:
                reason_parts.append("high positive-PnL recurrence")

            wallet_results.append(
                WalletAggregate(
                    wallet=wallet,
                    username=representative.username,
                    x_username=representative.x_username,
                    profile_image=representative.profile_image,
                    verified_badge=int(
                        any(entry.verified_badge for entry in wallet_entries)
                    ),
                    appearances=len(wallet_entries),
                    categories_seen=len(categories),
                    periods_seen=len(periods),
                    best_rank=best_rank,
                    total_pnl_signal=sum(entry.pnl for entry in wallet_entries),
                    total_volume_signal=sum(
                        entry.volume for entry in wallet_entries
                    ),
                    average_rank_score=average_rank_score,
                    elite_score=elite_score,
                    elite_grade=self.grade(elite_score),
                    primary_category=primary_category,
                    discovery_reason="; ".join(reason_parts),
                )
            )

        wallet_results.sort(
            key=lambda wallet: (
                -wallet.elite_score,
                wallet.best_rank if wallet.best_rank > 0 else 999999,
                wallet.wallet,
            )
        )
        return wallet_results, specialty_results

    def persist(
        self,
        *,
        run_id: str,
        observed_at: str,
        entries: Sequence[LeaderboardEntry],
        wallets: Sequence[WalletAggregate],
        specialties: dict[tuple[str, str], dict[str, Any]],
    ) -> tuple[int, int]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")

            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(SNAPSHOTS_TABLE)} (
                    run_id,
                    wallet,
                    username,
                    category,
                    time_period,
                    order_by,
                    leaderboard_rank,
                    pnl,
                    volume,
                    roi_proxy,
                    verified_badge,
                    observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        entry.wallet,
                        entry.username,
                        entry.category,
                        entry.time_period,
                        entry.order_by,
                        entry.rank,
                        entry.pnl,
                        entry.volume,
                        entry.roi_proxy,
                        entry.verified_badge,
                        observed_at,
                    )
                    for entry in entries
                ],
            )

            for wallet in wallets:
                connection.execute(
                    f"""
                    INSERT INTO {quote_identifier(WALLETS_TABLE)} (
                        wallet,
                        username,
                        x_username,
                        profile_image,
                        verified_badge,
                        first_discovered_at,
                        last_discovered_at,
                        discovery_count,
                        leaderboard_appearances,
                        categories_seen,
                        periods_seen,
                        best_rank,
                        total_pnl_signal,
                        total_volume_signal,
                        elite_score,
                        elite_grade,
                        primary_category,
                        discovery_reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(wallet) DO UPDATE SET
                        username=CASE
                            WHEN excluded.username <> '' THEN excluded.username
                            ELSE {quote_identifier(WALLETS_TABLE)}.username
                        END,
                        x_username=CASE
                            WHEN excluded.x_username <> '' THEN excluded.x_username
                            ELSE {quote_identifier(WALLETS_TABLE)}.x_username
                        END,
                        profile_image=CASE
                            WHEN excluded.profile_image <> '' THEN excluded.profile_image
                            ELSE {quote_identifier(WALLETS_TABLE)}.profile_image
                        END,
                        verified_badge=MAX(
                            {quote_identifier(WALLETS_TABLE)}.verified_badge,
                            excluded.verified_badge
                        ),
                        last_discovered_at=excluded.last_discovered_at,
                        discovery_count=
                            {quote_identifier(WALLETS_TABLE)}.discovery_count + 1,
                        leaderboard_appearances=excluded.leaderboard_appearances,
                        categories_seen=excluded.categories_seen,
                        periods_seen=excluded.periods_seen,
                        best_rank=CASE
                            WHEN {quote_identifier(WALLETS_TABLE)}.best_rank IS NULL
                                OR {quote_identifier(WALLETS_TABLE)}.best_rank = 0
                                THEN excluded.best_rank
                            WHEN excluded.best_rank = 0
                                THEN {quote_identifier(WALLETS_TABLE)}.best_rank
                            ELSE MIN(
                                {quote_identifier(WALLETS_TABLE)}.best_rank,
                                excluded.best_rank
                            )
                        END,
                        total_pnl_signal=excluded.total_pnl_signal,
                        total_volume_signal=excluded.total_volume_signal,
                        elite_score=excluded.elite_score,
                        elite_grade=excluded.elite_grade,
                        primary_category=excluded.primary_category,
                        discovery_reason=excluded.discovery_reason
                    """,
                    (
                        wallet.wallet,
                        wallet.username,
                        wallet.x_username,
                        wallet.profile_image,
                        wallet.verified_badge,
                        observed_at,
                        observed_at,
                        wallet.appearances,
                        wallet.categories_seen,
                        wallet.periods_seen,
                        wallet.best_rank,
                        wallet.total_pnl_signal,
                        wallet.total_volume_signal,
                        wallet.elite_score,
                        wallet.elite_grade,
                        wallet.primary_category,
                        wallet.discovery_reason,
                    ),
                )

            for specialty in specialties.values():
                connection.execute(
                    f"""
                    INSERT INTO {quote_identifier(SPECIALTIES_TABLE)} (
                        wallet,
                        category,
                        appearances,
                        best_rank,
                        pnl_signal,
                        volume_signal,
                        specialty_score,
                        specialty_grade,
                        last_seen_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(wallet, category) DO UPDATE SET
                        appearances=excluded.appearances,
                        best_rank=CASE
                            WHEN {quote_identifier(SPECIALTIES_TABLE)}.best_rank IS NULL
                                OR {quote_identifier(SPECIALTIES_TABLE)}.best_rank = 0
                                THEN excluded.best_rank
                            WHEN excluded.best_rank = 0
                                THEN {quote_identifier(SPECIALTIES_TABLE)}.best_rank
                            ELSE MIN(
                                {quote_identifier(SPECIALTIES_TABLE)}.best_rank,
                                excluded.best_rank
                            )
                        END,
                        pnl_signal=excluded.pnl_signal,
                        volume_signal=excluded.volume_signal,
                        specialty_score=excluded.specialty_score,
                        specialty_grade=excluded.specialty_grade,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        specialty["wallet"],
                        specialty["category"],
                        specialty["appearances"],
                        specialty["best_rank"],
                        specialty["pnl_signal"],
                        specialty["volume_signal"],
                        specialty["specialty_score"],
                        specialty["specialty_grade"],
                        observed_at,
                    ),
                )

            connection.commit()
            return len(entries), len(wallets)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def run(self, *, apply: bool = False) -> dict[str, Any]:
        self.create_tables()

        run_id = uuid.uuid4().hex
        started_at = utc_now()
        observed_at = started_at.isoformat()
        mode = "APPLY" if apply else "DRY RUN"

        connection = self.connect()
        try:
            connection.execute(
                f"""
                INSERT INTO {quote_identifier(RUNS_TABLE)} (
                    run_id,
                    started_at,
                    mode,
                    categories_scanned,
                    periods_scanned,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    observed_at,
                    mode,
                    len(self.categories),
                    len(self.periods),
                    "RUNNING",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        status = "SUCCESS"
        error_message = ""
        entries: list[LeaderboardEntry] = []
        wallets: list[WalletAggregate] = []
        specialties: dict[tuple[str, str], dict[str, Any]] = {}
        query_count = 0
        snapshot_rows_inserted = 0
        wallet_rows_upserted = 0

        try:
            entries, query_count = self.collect()
            wallets, specialties = self.aggregate(entries)

            if apply:
                (
                    snapshot_rows_inserted,
                    wallet_rows_upserted,
                ) = self.persist(
                    run_id=run_id,
                    observed_at=observed_at,
                    entries=entries,
                    wallets=wallets,
                    specialties=specialties,
                )

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
                        API_queries=?,
                        leaderboard_rows=?,
                        unique_wallets=?,
                        wallet_rows_upserted=?,
                        snapshot_rows_inserted=?,
                        status=?,
                        error_message=?
                    WHERE run_id=?
                    """,
                    (
                        finished_at.isoformat(),
                        query_count,
                        len(entries),
                        len(wallets),
                        wallet_rows_upserted,
                        snapshot_rows_inserted,
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
            "categories": self.categories,
            "periods": self.periods,
            "order_by": self.order_by,
            "API_queries": query_count,
            "leaderboard_rows": len(entries),
            "unique_wallets": len(wallets),
            "wallet_rows_upserted": wallet_rows_upserted,
            "snapshot_rows_inserted": snapshot_rows_inserted,
            "wallets": wallets,
            "status": status,
            "duration_seconds": (finished_at - started_at).total_seconds(),
        }


def print_report(report: dict[str, Any], preview_limit: int) -> None:
    print()
    print("=" * 118)
    print("ELITE WALLET DISCOVERY ENGINE")
    print("=" * 118)
    print(f"{'Database:':36} {report['database_path']}")
    print(f"{'Mode:':36} {report['mode']}")
    print(f"{'Run ID:':36} {report['run_id']}")
    print(f"{'Categories scanned:':36} {len(report['categories'])}")
    print(f"{'Periods scanned:':36} {len(report['periods'])}")
    print(f"{'API queries:':36} {report['API_queries']}")
    print(f"{'Leaderboard rows:':36} {report['leaderboard_rows']}")
    print(f"{'Unique wallets:':36} {report['unique_wallets']}")
    print(f"{'Snapshots inserted:':36} {report['snapshot_rows_inserted']}")
    print(f"{'Wallets upserted:':36} {report['wallet_rows_upserted']}")
    print(f"{'Duration:':36} {report['duration_seconds']:.3f}s")
    print(f"{'Status:':36} {report['status']}")

    print()
    print("TOP DISCOVERED WALLETS")
    print("-" * 118)
    wallets: list[WalletAggregate] = report["wallets"]
    if not wallets:
        print("No valid wallets were returned by the leaderboard API.")
    else:
        for index, wallet in enumerate(wallets[:preview_limit], start=1):
            name = wallet.username or "anonymous"
            print(
                f"{index:>3}. {wallet.elite_grade:<6} "
                f"score={wallet.elite_score:>6.2f} "
                f"best_rank={wallet.best_rank or '-':>4} "
                f"category={wallet.primary_category:<10} "
                f"{name}"
            )
            print(f"     {wallet.wallet}")
            print(f"     {wallet.discovery_reason}")

    print("=" * 118)


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(
        token.strip().upper()
        for token in value.split(",")
        if token.strip()
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover elite Polymarket wallets across official leaderboard "
            "categories and time periods."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist leaderboard snapshots and discovered-wallet scores.",
    )
    parser.add_argument(
        "--categories",
        type=parse_csv,
        default=DEFAULT_CATEGORIES,
        help=(
            "Comma-separated leaderboard categories. "
            "Default includes overall, sports, esports, politics, crypto, "
            "weather, economics, tech, finance, and culture."
        ),
    )
    parser.add_argument(
        "--periods",
        type=parse_csv,
        default=DEFAULT_PERIODS,
        help="Comma-separated periods: DAY,WEEK,MONTH,ALL.",
    )
    parser.add_argument(
        "--order-by",
        choices=("PNL", "VOL"),
        default=DEFAULT_ORDER_BY,
        help="Leaderboard ordering criterion. Default: PNL.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Leaderboard rows per category/period query. Range 1-50.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=25,
        help="Number of top discovered wallets to print.",
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

    engine = EliteWalletDiscoveryEngine(
        categories=args.categories,
        periods=args.periods,
        order_by=args.order_by,
        leaderboard_limit=args.limit,
    )
    report = engine.run(apply=args.apply)
    print_report(report, max(1, args.preview_limit))


if __name__ == "__main__":
    main()