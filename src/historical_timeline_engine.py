from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.1.0"

MARKET_SOURCE_PRIORITY = (
    "official_market_snapshots",
    "gamma_market_snapshots",
    "market_snapshots",
    "market_state_snapshots",
    "market_memory",
    "market_features",
    "markets",
    "gamma_markets",
    "official_markets",
)

SERVING_OR_DERIVED_NAMES = {
    "ranked_market_opportunities",
    "smart_money_clusters",
    "smart_money_action_board",
    "elite_wallet_intelligence",
    "elite_wallet_category_intelligence",
    "opportunity_scores",
}

DERIVED_PREFIXES = (
    "timeline_",
    "historical_",
    "market_event_",
    "wallet_entry_",
    "wallet_position_history",
    "cluster_evolution",
    "smart_money_",
    "elite_wallet_",
    "opportunity_",
    "consensus_",
)

WALLET_SOURCE_PRIORITY = (
    "wallet_current_position_snapshots",
    "positions",
    "official_wallet_trades",
    "official_wallet_activity",
)

MARKET_ALIASES = ("market_id", "condition_id", "token_id", "asset_id", "slug", "market")
TITLE_ALIASES = ("question", "title", "market_title", "market_question", "event_title")
OUTCOME_ALIASES = ("outcome", "selected_outcome", "side", "answer", "position")
PRICE_ALIASES = ("price", "current_price", "probability", "last_price", "mid_price", "average_price", "avg_price")
VOLUME_ALIASES = ("volume", "volume_24h", "total_volume", "market_volume")
LIQUIDITY_ALIASES = ("liquidity", "market_liquidity", "liquidity_num")
OPEN_INTEREST_ALIASES = ("open_interest", "oi", "market_open_interest")
SPREAD_ALIASES = ("spread", "bid_ask_spread")
TIMESTAMP_ALIASES = ("observed_at", "updated_at", "calculated_at", "scanned_at", "created_at", "timestamp", "trade_time", "event_time", "last_updated")
WALLET_ALIASES = ("wallet", "wallet_address", "proxy_wallet", "trader", "trader_address", "address", "owner")
SHARES_ALIASES = ("shares", "size", "quantity", "position_size")
VALUE_ALIASES = ("current_value", "position_value", "value", "amount", "notional", "capital", "capital_deployed")
PNL_ALIASES = ("cash_pnl", "pnl", "profit", "realized_pnl", "unrealized_pnl")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def normalize_timestamp(value: Any) -> str:
    if value is None or not str(value).strip():
        return utc_now()
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat(timespec="seconds")
    except ValueError:
        return utc_now()


def checksum(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def table_names(connection: sqlite3.Connection) -> list[str]:
    return [str(row[0]) for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]


def columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info({quote(table)})")]


def row_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {quote(table)}").fetchone()[0])


def find_column(available: Iterable[str], aliases: Iterable[str]) -> str | None:
    lookup = {name.lower(): name for name in available}
    for alias in aliases:
        if alias.lower() in lookup:
            return lookup[alias.lower()]
    return None


@dataclass
class Source:
    table: str
    rows: int
    mapping: dict[str, str | None]
    score: int


def excluded_table(table: str) -> bool:
    lowered = table.lower()
    return table in SERVING_OR_DERIVED_NAMES or lowered.startswith(DERIVED_PREFIXES)


def discover_market_source(connection: sqlite3.Connection) -> Source | None:
    candidates: list[Source] = []
    for table in table_names(connection):
        if excluded_table(table):
            continue

        available = columns(connection, table)
        market = find_column(available, MARKET_ALIASES)
        if not market:
            continue

        mapping = {
            "market": market,
            "title": find_column(available, TITLE_ALIASES),
            "outcome": find_column(available, OUTCOME_ALIASES),
            "price": find_column(available, PRICE_ALIASES),
            "volume": find_column(available, VOLUME_ALIASES),
            "liquidity": find_column(available, LIQUIDITY_ALIASES),
            "open_interest": find_column(available, OPEN_INTEREST_ALIASES),
            "spread": find_column(available, SPREAD_ALIASES),
            "timestamp": find_column(available, TIMESTAMP_ALIASES),
        }
        feature_hits = sum(v is not None for k, v in mapping.items() if k != "market")
        rows = row_count(connection, table)
        priority = 0
        if table in MARKET_SOURCE_PRIORITY:
            priority = (len(MARKET_SOURCE_PRIORITY) - MARKET_SOURCE_PRIORITY.index(table)) * 100
        raw_name_bonus = 120 if any(term in table.lower() for term in ("snapshot", "market", "gamma", "official")) else 0
        score = feature_hits * 100 + min(rows // 1000, 300) + priority + raw_name_bonus
        candidates.append(Source(table, rows, mapping, score))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item.score, item.rows), reverse=True)
    return candidates[0]


def discover_wallet_source(connection: sqlite3.Connection) -> Source | None:
    candidates: list[Source] = []
    for table in table_names(connection):
        if excluded_table(table):
            continue

        available = columns(connection, table)
        wallet = find_column(available, WALLET_ALIASES)
        market = find_column(available, MARKET_ALIASES)
        if not wallet or not market:
            continue

        mapping = {
            "wallet": wallet,
            "market": market,
            "title": find_column(available, TITLE_ALIASES),
            "outcome": find_column(available, OUTCOME_ALIASES),
            "price": find_column(available, PRICE_ALIASES),
            "shares": find_column(available, SHARES_ALIASES),
            "value": find_column(available, VALUE_ALIASES),
            "pnl": find_column(available, PNL_ALIASES),
            "timestamp": find_column(available, TIMESTAMP_ALIASES),
        }
        feature_hits = sum(v is not None for k, v in mapping.items() if k not in {"wallet", "market"})
        rows = row_count(connection, table)
        priority = 0
        if table in WALLET_SOURCE_PRIORITY:
            priority = (len(WALLET_SOURCE_PRIORITY) - WALLET_SOURCE_PRIORITY.index(table)) * 80
        score = feature_hits * 100 + min(rows // 1000, 200) + priority
        candidates.append(Source(table, rows, mapping, score))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item.score, item.rows), reverse=True)
    return candidates[0]


def select_rows(connection: sqlite3.Connection, source: Source, aliases: tuple[str, ...]) -> Iterable[sqlite3.Row]:
    selected = []
    for alias in aliases:
        column = source.mapping.get(alias)
        selected.append(f"{quote(column)} AS {quote(alias)}" if column else f"NULL AS {quote(alias)}")
    return connection.execute(f"SELECT {', '.join(selected)} FROM {quote(source.table)}")


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS historical_timeline_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            market_source TEXT,
            wallet_source TEXT,
            market_events_written INTEGER NOT NULL DEFAULT 0,
            wallet_events_written INTEGER NOT NULL DEFAULT 0,
            wallet_entries_created INTEGER NOT NULL DEFAULT 0,
            cluster_snapshots_written INTEGER NOT NULL DEFAULT 0,
            warnings_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS market_event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_key TEXT NOT NULL UNIQUE,
            market_id TEXT NOT NULL,
            outcome TEXT,
            title TEXT,
            observed_at TEXT NOT NULL,
            price REAL,
            volume REAL,
            liquidity REAL,
            open_interest REAL,
            spread REAL,
            source_table TEXT NOT NULL,
            payload_checksum TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_market_event_market_time
        ON market_event_log(market_id, observed_at);

        CREATE TABLE IF NOT EXISTS wallet_position_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_key TEXT NOT NULL UNIQUE,
            wallet TEXT NOT NULL,
            market_id TEXT NOT NULL,
            outcome TEXT,
            title TEXT,
            observed_at TEXT NOT NULL,
            price REAL,
            shares REAL,
            position_value REAL,
            pnl REAL,
            source_table TEXT NOT NULL,
            payload_checksum TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_wallet_position_history_wallet_market_time
        ON wallet_position_history(wallet, market_id, observed_at);

        CREATE TABLE IF NOT EXISTS wallet_entry_log (
            wallet TEXT NOT NULL,
            market_id TEXT NOT NULL,
            outcome TEXT NOT NULL DEFAULT 'UNKNOWN',
            first_observed_at TEXT NOT NULL,
            first_entry_price REAL,
            first_position_value REAL,
            first_shares REAL,
            source_table TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(wallet, market_id, outcome)
        );

        CREATE INDEX IF NOT EXISTS idx_wallet_entry_market_time
        ON wallet_entry_log(market_id, outcome, first_observed_at);

        CREATE TABLE IF NOT EXISTS cluster_evolution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            cluster_id TEXT NOT NULL,
            market_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            smart_money_score REAL NOT NULL,
            recommendation TEXT NOT NULL,
            signal_grade TEXT NOT NULL,
            wallet_count INTEGER NOT NULL,
            elite_wallet_count INTEGER NOT NULL,
            combined_capital REAL NOT NULL,
            entry_window_minutes REAL,
            timing_status TEXT,
            state_checksum TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(cluster_id, state_checksum)
        );

        CREATE INDEX IF NOT EXISTS idx_cluster_evolution_market_time
        ON cluster_evolution(market_id, outcome, observed_at);

        DROP VIEW IF EXISTS smart_money_timing_bridge;
        CREATE VIEW smart_money_timing_bridge AS
        SELECT
            market_id,
            outcome,
            COUNT(*) AS wallet_count_with_timing,
            MIN(first_observed_at) AS earliest_entry_at,
            MAX(first_observed_at) AS latest_entry_at,
            CASE
                WHEN COUNT(*) < 2 THEN NULL
                ELSE (
                    julianday(MAX(first_observed_at)) -
                    julianday(MIN(first_observed_at))
                ) * 1440.0
            END AS entry_window_minutes,
            CASE
                WHEN COUNT(*) < 2 THEN 'UNKNOWN'
                WHEN (
                    julianday(MAX(first_observed_at)) -
                    julianday(MIN(first_observed_at))
                ) * 1440.0 <= 15 THEN 'TIGHT'
                WHEN (
                    julianday(MAX(first_observed_at)) -
                    julianday(MIN(first_observed_at))
                ) * 1440.0 <= 120 THEN 'COORDINATED'
                WHEN (
                    julianday(MAX(first_observed_at)) -
                    julianday(MIN(first_observed_at))
                ) * 1440.0 <= 1440 THEN 'DISTRIBUTED'
                ELSE 'STALE'
            END AS timing_status
        FROM wallet_entry_log
        GROUP BY market_id, outcome;

        DROP VIEW IF EXISTS market_timeline_summary;
        CREATE VIEW market_timeline_summary AS
        SELECT
            market_id,
            COUNT(*) AS observation_count,
            MIN(observed_at) AS first_observed_at,
            MAX(observed_at) AS last_observed_at,
            MIN(price) AS min_price,
            MAX(price) AS max_price,
            AVG(price) AS average_price
        FROM market_event_log
        GROUP BY market_id;
        """
    )


def ingest_market_events(connection: sqlite3.Connection, source: Source | None) -> int:
    if source is None:
        return 0

    written = 0
    aliases = ("market", "title", "outcome", "price", "volume", "liquidity", "open_interest", "spread", "timestamp")
    for row in select_rows(connection, source, aliases):
        market_id = str(row["market"] or "").strip()
        if not market_id:
            continue

        observed_at = normalize_timestamp(row["timestamp"])
        payload = {
            "market_id": market_id,
            "title": str(row["title"] or market_id),
            "outcome": str(row["outcome"] or "UNKNOWN"),
            "price": safe_float(row["price"]),
            "volume": safe_float(row["volume"]),
            "liquidity": safe_float(row["liquidity"]),
            "open_interest": safe_float(row["open_interest"]),
            "spread": safe_float(row["spread"]),
            "observed_at": observed_at,
            "source_table": source.table,
        }
        digest = checksum(payload)
        event_key = hashlib.sha256(f"market|{market_id}|{observed_at}|{digest}".encode()).hexdigest()

        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO market_event_log (
                event_key, market_id, outcome, title, observed_at,
                price, volume, liquidity, open_interest, spread,
                source_table, payload_checksum, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_key, market_id, payload["outcome"], payload["title"], observed_at,
             payload["price"], payload["volume"], payload["liquidity"], payload["open_interest"],
             payload["spread"], source.table, digest, utc_now())
        )
        written += int(cursor.rowcount > 0)
    return written


def ingest_wallet_events(connection: sqlite3.Connection, source: Source | None) -> tuple[int, int]:
    if source is None:
        return 0, 0

    written = 0
    entry_changes = 0
    aliases = ("wallet", "market", "title", "outcome", "price", "shares", "value", "pnl", "timestamp")

    for row in select_rows(connection, source, aliases):
        wallet = str(row["wallet"] or "").strip()
        market_id = str(row["market"] or "").strip()
        if not wallet or not market_id:
            continue

        outcome = str(row["outcome"] or "UNKNOWN").strip() or "UNKNOWN"
        observed_at = normalize_timestamp(row["timestamp"])
        payload = {
            "wallet": wallet,
            "market_id": market_id,
            "title": str(row["title"] or market_id),
            "outcome": outcome,
            "price": safe_float(row["price"]),
            "shares": safe_float(row["shares"]),
            "position_value": safe_float(row["value"]),
            "pnl": safe_float(row["pnl"]),
            "observed_at": observed_at,
            "source_table": source.table,
        }
        digest = checksum(payload)
        event_key = hashlib.sha256(
            f"wallet|{wallet}|{market_id}|{outcome}|{observed_at}|{digest}".encode()
        ).hexdigest()

        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO wallet_position_history (
                event_key, wallet, market_id, outcome, title, observed_at,
                price, shares, position_value, pnl,
                source_table, payload_checksum, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_key, wallet, market_id, outcome, payload["title"], observed_at,
             payload["price"], payload["shares"], payload["position_value"], payload["pnl"],
             source.table, digest, utc_now())
        )
        inserted = int(cursor.rowcount > 0)
        written += inserted

        if inserted:
            old = connection.execute(
                """
                SELECT first_observed_at
                FROM wallet_entry_log
                WHERE wallet=? AND market_id=? AND outcome=?
                """,
                (wallet, market_id, outcome)
            ).fetchone()

            connection.execute(
                """
                INSERT INTO wallet_entry_log (
                    wallet, market_id, outcome,
                    first_observed_at, first_entry_price,
                    first_position_value, first_shares,
                    source_table, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(wallet, market_id, outcome) DO UPDATE SET
                    first_observed_at = CASE
                        WHEN excluded.first_observed_at < wallet_entry_log.first_observed_at
                        THEN excluded.first_observed_at ELSE wallet_entry_log.first_observed_at END,
                    first_entry_price = CASE
                        WHEN excluded.first_observed_at < wallet_entry_log.first_observed_at
                        THEN excluded.first_entry_price ELSE wallet_entry_log.first_entry_price END,
                    first_position_value = CASE
                        WHEN excluded.first_observed_at < wallet_entry_log.first_observed_at
                        THEN excluded.first_position_value ELSE wallet_entry_log.first_position_value END,
                    first_shares = CASE
                        WHEN excluded.first_observed_at < wallet_entry_log.first_observed_at
                        THEN excluded.first_shares ELSE wallet_entry_log.first_shares END,
                    updated_at = excluded.updated_at
                """,
                (wallet, market_id, outcome, observed_at, payload["price"],
                 payload["position_value"], payload["shares"], source.table, utc_now(), utc_now())
            )
            new = connection.execute(
                """
                SELECT first_observed_at
                FROM wallet_entry_log
                WHERE wallet=? AND market_id=? AND outcome=?
                """,
                (wallet, market_id, outcome)
            ).fetchone()

            if old is None or (new and old["first_observed_at"] != new["first_observed_at"]):
                entry_changes += 1

    return written, entry_changes


def capture_cluster_evolution(connection: sqlite3.Connection, run_id: str) -> int:
    if "smart_money_clusters" not in set(table_names(connection)):
        return 0

    observed_at = utc_now()
    written = 0
    for row in connection.execute(
        """
        SELECT
            cluster_id, market_id, outcome,
            smart_money_score, recommendation, signal_grade,
            wallet_count, elite_wallet_count, combined_capital,
            entry_window_minutes, timing_status
        FROM smart_money_clusters
        """
    ):
        state = {
            "smart_money_score": round(float(row["smart_money_score"]), 6),
            "recommendation": row["recommendation"],
            "signal_grade": row["signal_grade"],
            "wallet_count": row["wallet_count"],
            "elite_wallet_count": row["elite_wallet_count"],
            "combined_capital": round(float(row["combined_capital"]), 6),
            "entry_window_minutes": row["entry_window_minutes"],
            "timing_status": row["timing_status"],
        }
        digest = checksum(state)

        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO cluster_evolution (
                run_id, cluster_id, market_id, outcome, observed_at,
                smart_money_score, recommendation, signal_grade,
                wallet_count, elite_wallet_count, combined_capital,
                entry_window_minutes, timing_status, state_checksum, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, row["cluster_id"], row["market_id"], row["outcome"], observed_at,
             row["smart_money_score"], row["recommendation"], row["signal_grade"],
             row["wallet_count"], row["elite_wallet_count"], row["combined_capital"],
             row["entry_window_minutes"], row["timing_status"], digest, utc_now())
        )
        written += int(cursor.rowcount > 0)
    return written


def update_smart_money_timing(connection: sqlite3.Connection) -> int:
    if "smart_money_clusters" not in set(table_names(connection)):
        return 0

    cursor = connection.execute(
        """
        UPDATE smart_money_clusters
        SET
            entry_window_minutes = (
                SELECT bridge.entry_window_minutes
                FROM smart_money_timing_bridge AS bridge
                WHERE bridge.market_id = smart_money_clusters.market_id
                  AND bridge.outcome = smart_money_clusters.outcome
            ),
            timing_status = (
                SELECT bridge.timing_status
                FROM smart_money_timing_bridge AS bridge
                WHERE bridge.market_id = smart_money_clusters.market_id
                  AND bridge.outcome = smart_money_clusters.outcome
            ),
            timing_score = CASE
                WHEN (
                    SELECT bridge.timing_status
                    FROM smart_money_timing_bridge AS bridge
                    WHERE bridge.market_id = smart_money_clusters.market_id
                      AND bridge.outcome = smart_money_clusters.outcome
                ) = 'TIGHT' THEN 95.0
                WHEN (
                    SELECT bridge.timing_status
                    FROM smart_money_timing_bridge AS bridge
                    WHERE bridge.market_id = smart_money_clusters.market_id
                      AND bridge.outcome = smart_money_clusters.outcome
                ) = 'COORDINATED' THEN 78.0
                WHEN (
                    SELECT bridge.timing_status
                    FROM smart_money_timing_bridge AS bridge
                    WHERE bridge.market_id = smart_money_clusters.market_id
                      AND bridge.outcome = smart_money_clusters.outcome
                ) = 'DISTRIBUTED' THEN 55.0
                WHEN (
                    SELECT bridge.timing_status
                    FROM smart_money_timing_bridge AS bridge
                    WHERE bridge.market_id = smart_money_clusters.market_id
                      AND bridge.outcome = smart_money_clusters.outcome
                ) = 'STALE' THEN 25.0
                ELSE timing_score
            END
        WHERE EXISTS (
            SELECT 1
            FROM smart_money_timing_bridge AS bridge
            WHERE bridge.market_id = smart_money_clusters.market_id
              AND bridge.outcome = smart_money_clusters.outcome
        )
        """
    )
    return max(0, cursor.rowcount)


def print_source(label: str, source: Source | None) -> None:
    if source is None:
        print(f"{label:<18}: NOT FOUND")
        return
    mapped = ", ".join(k for k, v in source.mapping.items() if v is not None)
    print(f"{label:<18}: {source.table} ({source.rows:,} rows) | {mapped}")


def main() -> int:
    started_at = utc_now()
    run_id = f"timeline:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:8]}"
    warnings: list[str] = []

    print("=" * 122)
    print(f"HISTORICAL TIMELINE ENGINE v{ENGINE_VERSION}")
    print("=" * 122)
    print(f"Run ID:   {run_id}")
    print(f"Database: {DATABASE_PATH}")

    if not DATABASE_PATH.exists():
        print("ERROR: Database not found.", file=sys.stderr)
        return 1

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        ensure_schema(connection)

        market_source = discover_market_source(connection)
        wallet_source = discover_wallet_source(connection)

        if market_source is None:
            warnings.append("No compatible raw market source was found.")
        if wallet_source is None:
            warnings.append("No compatible wallet source was found.")

        print()
        print("TIMELINE SOURCE DISCOVERY")
        print("-" * 122)
        print_source("Market source", market_source)
        print_source("Wallet source", wallet_source)
        print("-" * 122)

        connection.execute(
            """
            INSERT INTO historical_timeline_runs (
                run_id, engine_version, started_at, status,
                market_source, wallet_source, warnings_json
            ) VALUES (?, ?, ?, 'RUNNING', ?, ?, ?)
            """,
            (run_id, ENGINE_VERSION, started_at,
             market_source.table if market_source else None,
             wallet_source.table if wallet_source else None,
             json.dumps(warnings))
        )
        connection.commit()

        market_events = ingest_market_events(connection, market_source)
        wallet_events, entry_changes = ingest_wallet_events(connection, wallet_source)
        timing_updates = update_smart_money_timing(connection)
        cluster_snapshots = capture_cluster_evolution(connection, run_id)

        completed_at = utc_now()
        connection.execute(
            """
            UPDATE historical_timeline_runs
            SET completed_at=?,
                status='SUCCESS',
                market_events_written=?,
                wallet_events_written=?,
                wallet_entries_created=?,
                cluster_snapshots_written=?,
                warnings_json=?
            WHERE run_id=?
            """,
            (completed_at, market_events, wallet_events, entry_changes,
             cluster_snapshots, json.dumps(warnings), run_id)
        )
        connection.commit()

        totals = {
            "market_events": connection.execute("SELECT COUNT(*) FROM market_event_log").fetchone()[0],
            "wallet_events": connection.execute("SELECT COUNT(*) FROM wallet_position_history").fetchone()[0],
            "wallet_entries": connection.execute("SELECT COUNT(*) FROM wallet_entry_log").fetchone()[0],
            "cluster_snapshots": connection.execute("SELECT COUNT(*) FROM cluster_evolution").fetchone()[0],
            "timed_clusters": connection.execute(
                "SELECT COUNT(*) FROM smart_money_clusters WHERE timing_status IS NOT NULL AND timing_status <> 'UNKNOWN'"
            ).fetchone()[0] if "smart_money_clusters" in set(table_names(connection)) else 0,
        }

    print()
    print("HISTORICAL TIMELINE HEALTH SUMMARY")
    print("-" * 122)
    print("Status:                    SUCCESS")
    print(f"Market events written:     {market_events:,}")
    print(f"Wallet events written:     {wallet_events:,}")
    print(f"Wallet entry changes:      {entry_changes:,}")
    print(f"Timing-linked clusters:    {timing_updates:,}")
    print(f"Cluster changes written:   {cluster_snapshots:,}")
    print(f"Total market events:       {totals['market_events']:,}")
    print(f"Total wallet events:       {totals['wallet_events']:,}")
    print(f"Total wallet entries:      {totals['wallet_entries']:,}")
    print(f"Total cluster history:     {totals['cluster_snapshots']:,}")
    print(f"Clusters with timing:      {totals['timed_clusters']:,}")
    print(f"Warnings:                  {len(warnings):,}")
    for warning in warnings:
        print(f"  - {warning}")
    print("=" * 122)
    print("HISTORICAL TIMELINE COMPLETE")
    print("=" * 122)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
