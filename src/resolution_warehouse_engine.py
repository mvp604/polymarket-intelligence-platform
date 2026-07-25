from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import resolution_outcome_engine as outcome_engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return "warehouse_run:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def normalize_condition_id(value: Any) -> str:
    return str(value or "").strip().lower()


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def parse_array(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def ensure_sources(connection: sqlite3.Connection) -> None:
    required = ["signal_ledger", "market_resolutions", "consensus_market_resolutions"]
    missing = [name for name in required if not table_exists(connection, name)]
    if missing:
        raise RuntimeError(
            "Missing required tables: " + ", ".join(missing) +
            ". Run the Consensus and Resolution & Outcome engines first."
        )


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS resolution_mapping_queue (
            condition_id TEXT PRIMARY KEY,
            event_id TEXT,
            market_title TEXT NOT NULL,
            signal_count INTEGER NOT NULL DEFAULT 1,
            mapping_status TEXT NOT NULL DEFAULT 'MISSING',
            mapping_method TEXT,
            gamma_market_id TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT NOT NULL,
            last_attempt_at TEXT,
            mapped_at TEXT,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_resolution_mapping_queue_status
        ON resolution_mapping_queue(mapping_status, last_attempt_at);

        CREATE TABLE IF NOT EXISTS resolution_warehouse_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            pending_signals INTEGER NOT NULL,
            unique_conditions INTEGER NOT NULL,
            legacy_exact_matches INTEGER NOT NULL,
            gamma_matches INTEGER NOT NULL,
            unresolved_mappings INTEGER NOT NULL,
            resolved_records_imported INTEGER NOT NULL,
            results_evaluated INTEGER NOT NULL,
            api_successes INTEGER NOT NULL,
            api_failures INTEGER NOT NULL,
            engine_version TEXT NOT NULL
        );
        """
    )


@dataclass
class SyncStats:
    pending_signals: int = 0
    unique_conditions: int = 0
    legacy_exact_matches: int = 0
    gamma_matches: int = 0
    unresolved_mappings: int = 0
    resolved_records_imported: int = 0
    results_evaluated: int = 0


def pending_conditions(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            condition_id,
            MIN(event_id) AS event_id,
            MIN(market_title) AS market_title,
            COUNT(*) AS signal_count
        FROM signal_ledger
        WHERE signal_status = 'PENDING'
        GROUP BY condition_id
        ORDER BY MIN(signal_date), condition_id
        """
    ).fetchall()


def legacy_resolution(connection: sqlite3.Connection, condition_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM market_resolutions
        WHERE LOWER(condition_id) = ?
        ORDER BY
            resolved DESC,
            confidence_score DESC,
            last_checked_at DESC,
            updated_at DESC
        LIMIT 1
        """,
        (condition_id,),
    ).fetchone()


def market_payload_from_legacy(row: sqlite3.Row) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    raw = row["source_payload_json"]
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {}

    payload.setdefault("id", row["gamma_market_id"] or "")
    payload.setdefault("conditionId", row["condition_id"] or "")
    payload.setdefault("question", row["question"] or "")
    payload.setdefault("slug", row["slug"] or "")
    payload.setdefault("resolutionSource", row["resolution_source"] or "")
    payload.setdefault("endDate", row["end_time"] or "")
    payload.setdefault("active", bool(row["active"]))
    payload.setdefault("closed", bool(row["closed"]))

    # Some older warehouse rows already know the winner even when the raw payload
    # does not expose terminal outcomePrices cleanly. Reconstruct a deterministic
    # terminal array only when the warehouse explicitly marks the row resolved.
    outcomes = parse_array(payload.get("outcomes"))
    prices = parse_array(payload.get("outcomePrices"))
    winner_name = str(row["winning_outcome_name"] or "").strip()
    winner_index = row["winning_outcome_index"]
    if safe_int(row["resolved"]) == 1 and winner_name:
        if not outcomes:
            outcomes = [winner_name]
        if winner_index is None:
            for index, outcome in enumerate(outcomes):
                if str(outcome).strip().upper() == winner_name.upper():
                    winner_index = index
                    break
        if winner_index is not None and 0 <= int(winner_index) < len(outcomes):
            prices = [0.0] * len(outcomes)
            prices[int(winner_index)] = 1.0
            payload["closed"] = True
            payload["acceptingOrders"] = False

    if outcomes:
        payload["outcomes"] = json.dumps(outcomes)
    if prices:
        payload["outcomePrices"] = json.dumps(prices)
    return payload


def queue_mapping(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    status: str,
    method: str | None,
    gamma_market_id: str | None,
    note: str,
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO resolution_mapping_queue (
            condition_id, event_id, market_title, signal_count, mapping_status,
            mapping_method, gamma_market_id, attempts, first_seen_at,
            last_attempt_at, mapped_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        ON CONFLICT(condition_id) DO UPDATE SET
            event_id = excluded.event_id,
            market_title = excluded.market_title,
            signal_count = excluded.signal_count,
            mapping_status = excluded.mapping_status,
            mapping_method = excluded.mapping_method,
            gamma_market_id = COALESCE(excluded.gamma_market_id, resolution_mapping_queue.gamma_market_id),
            attempts = resolution_mapping_queue.attempts + 1,
            last_attempt_at = excluded.last_attempt_at,
            mapped_at = CASE
                WHEN excluded.mapping_status = 'MAPPED' THEN excluded.mapped_at
                ELSE resolution_mapping_queue.mapped_at
            END,
            notes = excluded.notes
        """,
        (
            normalize_condition_id(row["condition_id"]),
            str(row["event_id"] or ""),
            str(row["market_title"] or ""),
            safe_int(row["signal_count"], 1),
            status,
            method,
            gamma_market_id,
            now,
            now,
            now if status == "MAPPED" else None,
            note,
        ),
    )


def import_market(
    connection: sqlite3.Connection,
    signal_row: sqlite3.Row,
    market: dict[str, Any],
) -> bool:
    before = connection.execute(
        "SELECT market_status FROM consensus_market_resolutions WHERE condition_id=?",
        (normalize_condition_id(signal_row["condition_id"]),),
    ).fetchone()
    was_resolved = before is not None and str(before["market_status"]) == "RESOLVED"

    is_resolved = outcome_engine.upsert_resolution(
        connection,
        normalize_condition_id(signal_row["condition_id"]),
        str(signal_row["market_title"]),
        str(signal_row["event_id"]),
        market,
    )
    return bool(is_resolved and not was_resolved)


def sync_pending_signals(connection: sqlite3.Connection) -> tuple[SyncStats, outcome_engine.GammaClient]:
    stats = SyncStats()
    client = outcome_engine.GammaClient()
    rows = pending_conditions(connection)
    stats.unique_conditions = len(rows)
    stats.pending_signals = sum(safe_int(row["signal_count"]) for row in rows)

    for row in rows:
        condition_id = normalize_condition_id(row["condition_id"])
        legacy = legacy_resolution(connection, condition_id)
        if legacy is not None:
            market = market_payload_from_legacy(legacy)
            newly_resolved = import_market(connection, row, market)
            stats.legacy_exact_matches += 1
            stats.resolved_records_imported += int(newly_resolved)
            queue_mapping(
                connection,
                row,
                "MAPPED",
                "LEGACY_CONDITION_ID",
                str(legacy["gamma_market_id"] or ""),
                f"Exact condition_id match in market_resolutions; status={legacy['resolution_status']}",
            )
            continue

        market = client.fetch_market(condition_id)
        if market is not None:
            newly_resolved = import_market(connection, row, market)
            stats.gamma_matches += 1
            stats.resolved_records_imported += int(newly_resolved)
            queue_mapping(
                connection,
                row,
                "MAPPED",
                "GAMMA_CONDITION_ID",
                str(market.get("id") or ""),
                "Fetched directly from Gamma by condition_id",
            )
            continue

        stats.unresolved_mappings += 1
        queue_mapping(
            connection,
            row,
            "MISSING",
            None,
            None,
            "No exact legacy row and Gamma returned no exact conditionId match",
        )

    return stats, client


def print_report(
    connection: sqlite3.Connection,
    run_id: str,
    stats: SyncStats,
    client: outcome_engine.GammaClient,
) -> None:
    print("=" * 126)
    print("RESOLUTION WAREHOUSE ENGINE COMPLETE")
    print("=" * 126)
    print(f"Database: {DATABASE_PATH}")
    print(f"Pending signals inspected: {stats.pending_signals}")
    print(f"Unique condition IDs: {stats.unique_conditions}")
    print(f"Exact legacy warehouse matches: {stats.legacy_exact_matches}")
    print(f"Direct Gamma matches: {stats.gamma_matches}")
    print(f"Still missing mappings: {stats.unresolved_mappings}")
    print(f"New resolved records imported: {stats.resolved_records_imported}")
    print(f"Signal results evaluated: {stats.results_evaluated}")
    print(f"Gamma API successes/failures: {client.stats.successes}/{client.stats.failures}")
    print(f"Run ID: {run_id}")

    print("\nLATEST SIGNAL STATUS")
    print("-" * 126)
    rows = connection.execute(
        """
        SELECT signal_grade, market_title, recommended_outcome, signal_status
        FROM signal_ledger
        ORDER BY
            signal_date DESC,
            CASE signal_grade WHEN 'S+' THEN 1 WHEN 'S' THEN 2 WHEN 'A' THEN 3 WHEN 'B' THEN 4 ELSE 5 END,
            consensus_score DESC
        LIMIT 30
        """
    ).fetchall()
    for index, row in enumerate(rows, 1):
        print(
            f"{index:>2}. {str(row['market_title'])[:62]:<62} | "
            f"{str(row['recommended_outcome'])[:16]:<16} | {str(row['signal_grade']):<3} | "
            f"{str(row['signal_status'])}"
        )

    print("\nMAPPING QUEUE")
    print("-" * 126)
    queue_rows = connection.execute(
        """
        SELECT mapping_status, mapping_method, market_title, condition_id, attempts, notes
        FROM resolution_mapping_queue
        ORDER BY CASE mapping_status WHEN 'MISSING' THEN 1 ELSE 2 END, market_title
        """
    ).fetchall()
    if not queue_rows:
        print("No mapping rows recorded.")
    for row in queue_rows:
        print(
            f"{str(row['mapping_status']):<8} | {str(row['mapping_method'] or '-'):<22} | "
            f"{str(row['market_title'])[:58]:<58} | attempts={row['attempts']}"
        )

    print("\nFINAL OUTCOMES")
    print("-" * 126)
    results = connection.execute(
        """
        SELECT signal_grade, market_title, recommended_outcome, resolved_outcome,
               result, profit_loss_units, roi_pct
        FROM signal_results
        ORDER BY evaluated_at DESC
        LIMIT 30
        """
    ).fetchall()
    if not results:
        print("No signals have been graded yet.")
    for row in results:
        pnl = row["profit_loss_units"]
        roi = row["roi_pct"]
        pnl_text = "n/a" if pnl is None else f"{float(pnl):+.3f}u"
        roi_text = "n/a" if roi is None else f"{float(roi):+.2f}%"
        print(
            f"{str(row['result']):<5} | {str(row['signal_grade']):<3} | "
            f"{str(row['market_title'])[:58]:<58} | "
            f"pick={str(row['recommended_outcome']):<14} | winner={str(row['resolved_outcome']):<14} | "
            f"{pnl_text:<10} | {roi_text}"
        )


def main() -> None:
    run_id = make_run_id()
    started_at = utc_now()
    connection = connect_database()
    try:
        ensure_sources(connection)
        ensure_schema(connection)
        stats, client = sync_pending_signals(connection)
        stats.results_evaluated = outcome_engine.evaluate_resolved_signals(connection)
        outcome_engine.rebuild_daily_outcomes(connection)
        completed_at = utc_now()
        connection.execute(
            """
            INSERT INTO resolution_warehouse_runs (
                run_id, started_at, completed_at, pending_signals, unique_conditions,
                legacy_exact_matches, gamma_matches, unresolved_mappings,
                resolved_records_imported, results_evaluated, api_successes,
                api_failures, engine_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, started_at, completed_at, stats.pending_signals,
                stats.unique_conditions, stats.legacy_exact_matches,
                stats.gamma_matches, stats.unresolved_mappings,
                stats.resolved_records_imported, stats.results_evaluated,
                client.stats.successes, client.stats.failures, ENGINE_VERSION,
            ),
        )
        connection.commit()
        print_report(connection, run_id, stats, client)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()