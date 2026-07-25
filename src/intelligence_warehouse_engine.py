from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize(name: str) -> str:
    return "".join(character for character in name.lower() if character.isalnum())


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {str(row[0]) for row in rows}


def columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    ]


def choose_column(available: Iterable[str], candidates: Iterable[str]) -> str | None:
    lookup = {normalize(column): column for column in available}
    for candidate in candidates:
        match = lookup.get(normalize(candidate))
        if match:
            return match
    return None


def value(row: sqlite3.Row, available: list[str], candidates: Iterable[str]) -> Any:
    column = choose_column(available, candidates)
    return row[column] if column else None


def as_float(item: Any) -> float | None:
    if item is None or item == "":
        return None
    try:
        return float(item)
    except (TypeError, ValueError):
        return None


def as_int(item: Any) -> int | None:
    numeric = as_float(item)
    return int(numeric) if numeric is not None else None


def as_text(item: Any) -> str | None:
    if item is None:
        return None
    text = str(item).strip()
    return text or None


def row_json(row: sqlite3.Row) -> str:
    return json.dumps(dict(row), default=str, separators=(",", ":"), ensure_ascii=False)


def first_existing(tables: set[str], candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        if candidate in tables:
            return candidate
    return None


def read_rows(
    connection: sqlite3.Connection,
    table: str,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    sql = f'SELECT * FROM "{table}"'
    if limit:
        sql += f" LIMIT {int(limit)}"
    return connection.execute(sql).fetchall()


def load_wallets(
    connection: sqlite3.Connection,
    tables: set[str],
    warehouse_time: str,
) -> tuple[int, list[str]]:
    warnings: list[str] = []
    source = first_existing(
        tables,
        (
            "wallet_performance",
            "elite_wallet_rankings",
            "wallet_scores",
        ),
    )
    if not source:
        return 0, ["No wallet intelligence source table was found."]

    available = columns(connection, source)
    wallet_column = choose_column(
        available,
        ("wallet", "wallet_address", "address", "proxy_wallet"),
    )
    if not wallet_column:
        return 0, [f"{source} has no recognizable wallet-address column."]

    rows = read_rows(connection, source)
    written = 0

    for row in rows:
        wallet = as_text(row[wallet_column])
        if not wallet:
            continue

        connection.execute(
            """
            INSERT INTO intelligence_wallets (
                wallet,
                performance_score,
                performance_grade,
                confidence_score,
                data_confidence,
                resolved_positions,
                wins,
                losses,
                win_rate,
                estimated_profit,
                estimated_roi,
                average_entry_price,
                calibration_score,
                unresolved_positions,
                trend,
                source_table,
                source_updated_at,
                warehouse_updated_at,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                performance_score = excluded.performance_score,
                performance_grade = excluded.performance_grade,
                confidence_score = excluded.confidence_score,
                data_confidence = excluded.data_confidence,
                resolved_positions = excluded.resolved_positions,
                wins = excluded.wins,
                losses = excluded.losses,
                win_rate = excluded.win_rate,
                estimated_profit = excluded.estimated_profit,
                estimated_roi = excluded.estimated_roi,
                average_entry_price = excluded.average_entry_price,
                calibration_score = excluded.calibration_score,
                unresolved_positions = excluded.unresolved_positions,
                trend = excluded.trend,
                source_table = excluded.source_table,
                source_updated_at = excluded.source_updated_at,
                warehouse_updated_at = excluded.warehouse_updated_at,
                raw_json = excluded.raw_json
            """,
            (
                wallet,
                as_float(value(row, available, ("performance_score", "score", "wallet_score"))),
                as_text(value(row, available, ("performance_grade", "grade", "rating"))),
                as_float(value(row, available, ("confidence_score", "confidence", "wallet_confidence"))),
                as_text(value(row, available, ("data_confidence", "confidence_grade"))),
                as_int(value(row, available, ("resolved_positions", "resolved_count"))),
                as_int(value(row, available, ("wins", "win_count"))),
                as_int(value(row, available, ("losses", "loss_count"))),
                as_float(value(row, available, ("win_rate", "winrate"))),
                as_float(value(row, available, ("estimated_profit", "profit", "pnl"))),
                as_float(value(row, available, ("estimated_roi", "roi"))),
                as_float(value(row, available, ("average_entry_price", "avg_entry_price"))),
                as_float(value(row, available, ("calibration_score", "calibration"))),
                as_int(value(row, available, ("unresolved_mapped_positions", "unresolved_positions"))),
                as_text(value(row, available, ("trend", "performance_trend"))),
                source,
                as_text(value(row, available, ("updated_at", "scored_at", "calculated_at"))),
                warehouse_time,
                row_json(row),
            ),
        )
        written += 1

    return written, warnings


def load_markets(
    connection: sqlite3.Connection,
    tables: set[str],
    warehouse_time: str,
) -> tuple[int, list[str]]:
    warnings: list[str] = []

    feature_source = first_existing(
        tables,
        (
            "market_features",
            "market_feature_profiles",
            "features",
        ),
    )
    market_source = first_existing(
        tables,
        (
            "markets",
            "universal_markets",
            "market_metadata",
        ),
    )
    consensus_source = first_existing(
        tables,
        (
            "consensus_intelligence",
            "market_consensus",
            "consensus_signals",
        ),
    )

    source = feature_source or market_source or consensus_source
    if not source:
        return 0, ["No market intelligence source table was found."]

    available = columns(connection, source)
    market_id_column = choose_column(
        available,
        (
            "market_id",
            "condition_id",
            "id",
            "token_id",
            "slug",
        ),
    )
    if not market_id_column:
        return 0, [f"{source} has no recognizable market identifier column."]

    rows = read_rows(connection, source)
    written = 0

    for row in rows:
        market_id = as_text(row[market_id_column])
        if not market_id:
            continue

        question = as_text(value(row, available, ("question", "title", "market_question")))
        connection.execute(
            """
            INSERT INTO intelligence_markets (
                market_id,
                question,
                category,
                outcome,
                current_price,
                liquidity,
                volume,
                spread,
                opportunity_score,
                health_score,
                risk_score,
                wallet_score,
                consensus_score,
                signal_grade,
                signal_status,
                source_table,
                source_updated_at,
                warehouse_updated_at,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(market_id) DO UPDATE SET
                question = COALESCE(excluded.question, intelligence_markets.question),
                category = COALESCE(excluded.category, intelligence_markets.category),
                outcome = COALESCE(excluded.outcome, intelligence_markets.outcome),
                current_price = COALESCE(excluded.current_price, intelligence_markets.current_price),
                liquidity = COALESCE(excluded.liquidity, intelligence_markets.liquidity),
                volume = COALESCE(excluded.volume, intelligence_markets.volume),
                spread = COALESCE(excluded.spread, intelligence_markets.spread),
                opportunity_score = COALESCE(excluded.opportunity_score, intelligence_markets.opportunity_score),
                health_score = COALESCE(excluded.health_score, intelligence_markets.health_score),
                risk_score = COALESCE(excluded.risk_score, intelligence_markets.risk_score),
                wallet_score = COALESCE(excluded.wallet_score, intelligence_markets.wallet_score),
                consensus_score = COALESCE(excluded.consensus_score, intelligence_markets.consensus_score),
                signal_grade = COALESCE(excluded.signal_grade, intelligence_markets.signal_grade),
                signal_status = COALESCE(excluded.signal_status, intelligence_markets.signal_status),
                source_table = excluded.source_table,
                source_updated_at = excluded.source_updated_at,
                warehouse_updated_at = excluded.warehouse_updated_at,
                raw_json = excluded.raw_json
            """,
            (
                market_id,
                question,
                as_text(value(row, available, ("category", "market_category", "sport", "tag"))),
                as_text(value(row, available, ("outcome", "selected_outcome"))),
                as_float(value(row, available, ("current_price", "yes_price", "price", "last_price"))),
                as_float(value(row, available, ("liquidity", "liquidity_num"))),
                as_float(value(row, available, ("volume", "volume_num"))),
                as_float(value(row, available, ("spread", "current_spread"))),
                as_float(value(row, available, ("opportunity_score", "opportunity"))),
                as_float(value(row, available, ("health_score", "market_health", "health"))),
                as_float(value(row, available, ("risk_score", "risk"))),
                as_float(value(row, available, ("wallet_score", "wallet_feature_score"))),
                as_float(value(row, available, ("consensus_score", "conviction_score"))),
                as_text(value(row, available, ("signal_grade", "grade"))),
                as_text(value(row, available, ("signal_status", "status"))),
                source,
                as_text(value(row, available, ("updated_at", "calculated_at", "snapshot_at"))),
                warehouse_time,
                row_json(row),
            ),
        )
        written += 1

    return written, warnings


def signal_key_for(row: sqlite3.Row, available: list[str]) -> str:
    direct = as_text(value(row, available, ("signal_id", "id", "signal_key")))
    if direct:
        return direct

    parts = [
        as_text(value(row, available, ("market_id", "condition_id"))) or "",
        as_text(value(row, available, ("question", "title"))) or "",
        as_text(value(row, available, ("selected_outcome", "outcome", "pick"))) or "",
        as_text(value(row, available, ("generated_at", "created_at", "scanned_at"))) or "",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def load_signals(
    connection: sqlite3.Connection,
    tables: set[str],
    warehouse_time: str,
) -> tuple[int, list[str]]:
    warnings: list[str] = []
    source = first_existing(
        tables,
        (
            "signal_results",
            "market_signals",
            "consensus_signals",
            "consensus_history",
            "actionable_signals",
        ),
    )
    if not source:
        return 0, ["No signal-ledger source table was found."]

    available = columns(connection, source)
    rows = read_rows(connection, source)
    written = 0

    for row in rows:
        key = signal_key_for(row, available)
        connection.execute(
            """
            INSERT INTO intelligence_signals (
                signal_key,
                market_id,
                question,
                selected_outcome,
                signal_grade,
                signal_score,
                confidence_score,
                entry_price,
                result_status,
                units_result,
                roi,
                generated_at,
                resolved_at,
                source_table,
                warehouse_updated_at,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signal_key) DO UPDATE SET
                market_id = COALESCE(excluded.market_id, intelligence_signals.market_id),
                question = COALESCE(excluded.question, intelligence_signals.question),
                selected_outcome = COALESCE(excluded.selected_outcome, intelligence_signals.selected_outcome),
                signal_grade = COALESCE(excluded.signal_grade, intelligence_signals.signal_grade),
                signal_score = COALESCE(excluded.signal_score, intelligence_signals.signal_score),
                confidence_score = COALESCE(excluded.confidence_score, intelligence_signals.confidence_score),
                entry_price = COALESCE(excluded.entry_price, intelligence_signals.entry_price),
                result_status = COALESCE(excluded.result_status, intelligence_signals.result_status),
                units_result = COALESCE(excluded.units_result, intelligence_signals.units_result),
                roi = COALESCE(excluded.roi, intelligence_signals.roi),
                generated_at = COALESCE(excluded.generated_at, intelligence_signals.generated_at),
                resolved_at = COALESCE(excluded.resolved_at, intelligence_signals.resolved_at),
                source_table = excluded.source_table,
                warehouse_updated_at = excluded.warehouse_updated_at,
                raw_json = excluded.raw_json
            """,
            (
                key,
                as_text(value(row, available, ("market_id", "condition_id"))),
                as_text(value(row, available, ("question", "title", "market_question"))),
                as_text(value(row, available, ("selected_outcome", "outcome", "pick"))),
                as_text(value(row, available, ("signal_grade", "grade", "conviction_grade"))),
                as_float(value(row, available, ("signal_score", "score", "conviction_score"))),
                as_float(value(row, available, ("confidence_score", "confidence"))),
                as_float(value(row, available, ("entry_price", "average_entry_price"))),
                as_text(value(row, available, ("result_status", "result", "status"))),
                as_float(value(row, available, ("units_result", "units", "profit_units"))),
                as_float(value(row, available, ("roi", "result_roi"))),
                as_text(value(row, available, ("generated_at", "created_at", "scanned_at"))),
                as_text(value(row, available, ("resolved_at", "evaluated_at"))),
                source,
                warehouse_time,
                row_json(row),
            ),
        )
        written += 1

    return written, warnings


def apply_schema(connection: sqlite3.Connection) -> None:
    project_root = Path(__file__).resolve().parents[1]
    migration_path = project_root / "database" / "migrations" / "002_intelligence_warehouse.sql"
    if not migration_path.exists():
        raise FileNotFoundError(f"Migration not found: {migration_path}")
    connection.executescript(migration_path.read_text(encoding="utf-8-sig"))


def print_top_rows(connection: sqlite3.Connection) -> None:
    print()
    print("TOP INTELLIGENCE MARKETS")
    print("-" * 118)
    rows = connection.execute(
        """
        SELECT market_id, question, opportunity_score, health_score, risk_score, signal_grade
        FROM intelligence_top_markets
        WHERE opportunity_score IS NOT NULL
        LIMIT 15
        """
    ).fetchall()

    if not rows:
        print("No opportunity-scored markets are available yet.")
        return

    for index, row in enumerate(rows, start=1):
        question = (row["question"] or row["market_id"] or "")[:72]
        opportunity = row["opportunity_score"]
        health = row["health_score"]
        risk = row["risk_score"]
        grade = row["signal_grade"] or "-"
        print(
            f"{index:>2}. {grade:<3} "
            f"Opportunity={opportunity if opportunity is not None else 0:>6.2f} "
            f"Health={health if health is not None else 0:>6.2f} "
            f"Risk={risk if risk is not None else 0:>6.2f} | {question}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build unified intelligence warehouse tables.")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "database" / "polymarket.db",
    )
    args = parser.parse_args()

    database_path = args.database.resolve()
    run_id = f"intelligence_warehouse:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:8]}"
    started_at = utc_now()
    warehouse_time = started_at
    warnings: list[str] = []

    print("=" * 118)
    print(f"INTELLIGENCE WAREHOUSE ENGINE v{VERSION}")
    print("=" * 118)
    print(f"Run ID:   {run_id}")
    print(f"Database: {database_path}")

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        apply_schema(connection)

        tables = table_names(connection)
        connection.execute(
            """
            INSERT INTO intelligence_warehouse_runs (
                run_id, started_at, status, source_tables_json
            )
            VALUES (?, ?, 'RUNNING', ?)
            """,
            (run_id, started_at, json.dumps(sorted(tables))),
        )
        connection.commit()

        try:
            wallet_rows, wallet_warnings = load_wallets(connection, tables, warehouse_time)
            market_rows, market_warnings = load_markets(connection, tables, warehouse_time)
            signal_rows, signal_warnings = load_signals(connection, tables, warehouse_time)
            warnings.extend(wallet_warnings)
            warnings.extend(market_warnings)
            warnings.extend(signal_warnings)

            connection.execute(
                """
                UPDATE intelligence_warehouse_runs
                SET completed_at = ?,
                    status = 'SUCCESS',
                    wallet_rows = ?,
                    market_rows = ?,
                    signal_rows = ?,
                    warnings_json = ?
                WHERE run_id = ?
                """,
                (
                    utc_now(),
                    wallet_rows,
                    market_rows,
                    signal_rows,
                    json.dumps(warnings, ensure_ascii=False),
                    run_id,
                ),
            )
            connection.commit()

        except Exception as exc:
            connection.rollback()
            connection.execute(
                """
                UPDATE intelligence_warehouse_runs
                SET completed_at = ?,
                    status = 'FAILED',
                    warnings_json = ?,
                    error_message = ?
                WHERE run_id = ?
                """,
                (
                    utc_now(),
                    json.dumps(warnings, ensure_ascii=False),
                    str(exc),
                    run_id,
                ),
            )
            connection.commit()
            raise

        print()
        print("INTELLIGENCE WAREHOUSE HEALTH SUMMARY")
        print("-" * 118)
        print("Status:          SUCCESS")
        print(f"Wallet rows:     {wallet_rows:,}")
        print(f"Market rows:     {market_rows:,}")
        print(f"Signal rows:     {signal_rows:,}")
        print(f"Warnings:        {len(warnings):,}")

        for warning in warnings:
            print(f"  WARNING: {warning}")

        print_top_rows(connection)

    print("=" * 118)
    print("INTELLIGENCE WAREHOUSE COMPLETE")
    print("=" * 118)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())