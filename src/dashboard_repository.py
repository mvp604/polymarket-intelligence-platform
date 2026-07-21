from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

try:
    from data_access import DataAccess, DATABASE_PATH
except ImportError:
    from src.data_access import DataAccess, DATABASE_PATH

CURRENT_TABLE = "master_intelligence_dashboard"
HISTORY_TABLE = "master_intelligence_dashboard_history"
RUNS_TABLE = "master_intelligence_dashboard_runs"
SCHEMA_VERSION = 1


class DashboardRepositoryError(RuntimeError):
    pass


class DashboardValidationError(DashboardRepositoryError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_json(value: Any) -> str:
    if is_dataclass(value):
        value = asdict(value)
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def from_json(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def as_mapping(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        result = value.to_dict()
        if isinstance(result, Mapping):
            return dict(result)
    raise DashboardValidationError(
        f"Unsupported snapshot type: {type(value).__name__}"
    )


def nested_get(data: Mapping[str, Any], *paths: str, default: Any = None) -> Any:
    for path in paths:
        current: Any = data
        found = True
        for key in path.split("."):
            if not isinstance(current, Mapping) or key not in current:
                found = False
                break
            current = current[key]
        if found and current is not None:
            return current
    return default


def text(value: Any, default: str = "") -> str:
    return default if value is None else str(value).strip()


def number(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(value: Any, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def boolean_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(bool(value))
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes", "active", "on"}:
        return 1
    if normalized in {"0", "false", "no", "inactive", "off"}:
        return 0
    return default


class DashboardRepository:
    """Single SQL boundary for dashboard current state, history, and run logs."""

    def __init__(
        self,
        data_access: DataAccess | None = None,
        database_path: Path | str = DATABASE_PATH,
    ) -> None:
        self.data = data_access or DataAccess(database_path)
        self.database_path = Path(self.data.database_path)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.data.transaction() as connection:
            yield connection

    def initialize_schema(self) -> None:
        statements = [
            f"""
            CREATE TABLE IF NOT EXISTS {CURRENT_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT 'UNKNOWN',
                gamma_market_id TEXT,
                event_id TEXT,
                question TEXT,
                market_slug TEXT,
                event_slug TEXT,
                polymarket_url TEXT,
                category TEXT,
                market_type TEXT,
                lifecycle_status TEXT,
                active INTEGER NOT NULL DEFAULT 0,
                closed INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                resolved INTEGER NOT NULL DEFAULT 0,
                tradable_identity INTEGER NOT NULL DEFAULT 0,
                restricted INTEGER NOT NULL DEFAULT 0,
                start_time TEXT,
                end_time TEXT,
                seconds_to_start REAL,
                current_price REAL,
                yes_price REAL,
                no_price REAL,
                best_bid REAL,
                best_ask REAL,
                spread REAL,
                liquidity REAL,
                volume REAL,
                volume_24h REAL,
                open_interest REAL,
                wallet_count INTEGER,
                effective_wallet_count REAL,
                combined_value REAL,
                combined_shares REAL,
                consensus_strength REAL,
                conviction_score REAL,
                average_entry_price REAL,
                accumulation_score REAL,
                distribution_score REAL,
                position_trend TEXT,
                price_move_5m REAL,
                price_move_15m REAL,
                price_move_1h REAL,
                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,
                closing_line_value REAL,
                closing_line_score REAL,
                master_score REAL,
                opportunity_grade TEXT,
                opportunity_recommendation TEXT,
                opportunity_confidence REAL,
                edge_score REAL,
                data_completeness_score REAL,
                alert_count INTEGER NOT NULL DEFAULT 0,
                has_active_alert INTEGER NOT NULL DEFAULT 0,
                latest_alert_type TEXT,
                latest_alert_created_at TEXT,
                intelligence_score REAL,
                intelligence_grade TEXT,
                confidence_score REAL,
                risk_score REAL,
                final_recommendation TEXT,
                risk_flags_json TEXT NOT NULL DEFAULT '[]',
                canonical_json TEXT NOT NULL DEFAULT '{{}}',
                status_json TEXT NOT NULL DEFAULT '{{}}',
                price_metrics_json TEXT NOT NULL DEFAULT '{{}}',
                consensus_json TEXT NOT NULL DEFAULT '[]',
                evolution_json TEXT NOT NULL DEFAULT '[]',
                closing_line_json TEXT NOT NULL DEFAULT '[]',
                opportunity_json TEXT NOT NULL DEFAULT '{{}}',
                alerts_json TEXT NOT NULL DEFAULT '[]',
                positions_json TEXT NOT NULL DEFAULT '[]',
                source_snapshot_json TEXT NOT NULL DEFAULT '{{}}',
                source_updated_at TEXT,
                built_at TEXT NOT NULL,
                run_id TEXT,
                schema_version INTEGER NOT NULL DEFAULT {SCHEMA_VERSION},
                UNIQUE(condition_id, outcome)
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {HISTORY_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT 'UNKNOWN',
                run_id TEXT,
                question TEXT,
                lifecycle_status TEXT,
                current_price REAL,
                liquidity REAL,
                volume_24h REAL,
                spread REAL,
                wallet_count INTEGER,
                consensus_strength REAL,
                conviction_score REAL,
                master_score REAL,
                intelligence_score REAL,
                intelligence_grade TEXT,
                confidence_score REAL,
                risk_score REAL,
                final_recommendation TEXT,
                alert_count INTEGER NOT NULL DEFAULT 0,
                snapshot_json TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT {SCHEMA_VERSION}
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {RUNS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                mode TEXT NOT NULL DEFAULT 'focused',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                source_markets INTEGER NOT NULL DEFAULT 0,
                processed_rows INTEGER NOT NULL DEFAULT 0,
                inserted_rows INTEGER NOT NULL DEFAULT 0,
                updated_rows INTEGER NOT NULL DEFAULT 0,
                history_rows INTEGER NOT NULL DEFAULT 0,
                skipped_rows INTEGER NOT NULL DEFAULT 0,
                unmatched_rows INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                success INTEGER,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                error_message TEXT,
                details_json TEXT NOT NULL DEFAULT '{{}}',
                schema_version INTEGER NOT NULL DEFAULT {SCHEMA_VERSION}
            )
            """,
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_identity ON {CURRENT_TABLE}(condition_id, outcome)",
            f"CREATE INDEX IF NOT EXISTS idx_dashboard_master_score ON {CURRENT_TABLE}(master_score DESC)",
            f"CREATE INDEX IF NOT EXISTS idx_dashboard_intelligence_score ON {CURRENT_TABLE}(intelligence_score DESC)",
            f"CREATE INDEX IF NOT EXISTS idx_dashboard_category ON {CURRENT_TABLE}(category)",
            f"CREATE INDEX IF NOT EXISTS idx_dashboard_lifecycle ON {CURRENT_TABLE}(lifecycle_status)",
            f"CREATE INDEX IF NOT EXISTS idx_dashboard_history_market ON {HISTORY_TABLE}(condition_id, outcome, captured_at DESC)",
            f"CREATE INDEX IF NOT EXISTS idx_dashboard_runs_started ON {RUNS_TABLE}(started_at DESC)",
        ]
        with self.transaction() as connection:
            for statement in statements:
                connection.execute(statement)

    def schema_ready(self) -> bool:
        return all(
            self.data.table_exists(name)
            for name in (CURRENT_TABLE, HISTORY_TABLE, RUNS_TABLE)
        )

    def create_run(
        self,
        *,
        mode: str = "focused",
        source_markets: int = 0,
        details: Mapping[str, Any] | None = None,
    ) -> str:
        self.initialize_schema()
        run_id = uuid.uuid4().hex
        self.data.execute(
            f"""
            INSERT INTO {RUNS_TABLE} (
                run_id, mode, started_at, source_markets, status, details_json
            ) VALUES (?, ?, ?, ?, 'RUNNING', ?)
            """,
            (run_id, text(mode, "focused"), utc_now_iso(), max(0, source_markets), to_json(details or {})),
        )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        success: bool,
        processed_rows: int = 0,
        inserted_rows: int = 0,
        updated_rows: int = 0,
        history_rows: int = 0,
        skipped_rows: int = 0,
        unmatched_rows: int = 0,
        error_count: int = 0,
        error_message: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.initialize_schema()
        row = self.data.fetch_one(
            f"SELECT started_at, details_json FROM {RUNS_TABLE} WHERE run_id = ?",
            (run_id,),
        )
        if row is None:
            raise DashboardRepositoryError(f"Run not found: {run_id}")
        finished_at = utc_now_iso()
        try:
            duration = (
                datetime.fromisoformat(finished_at)
                - datetime.fromisoformat(row["started_at"])
            ).total_seconds()
        except (TypeError, ValueError):
            duration = None
        merged = from_json(row.get("details_json"), {}) or {}
        if details:
            merged.update(dict(details))
        self.data.execute(
            f"""
            UPDATE {RUNS_TABLE}
            SET finished_at=?, duration_seconds=?, processed_rows=?, inserted_rows=?,
                updated_rows=?, history_rows=?, skipped_rows=?, unmatched_rows=?,
                error_count=?, success=?, status=?, error_message=?, details_json=?
            WHERE run_id=?
            """,
            (
                finished_at, duration, processed_rows, inserted_rows, updated_rows,
                history_rows, skipped_rows, unmatched_rows, error_count,
                int(success), "SUCCESS" if success else "FAILED",
                error_message, to_json(merged), run_id,
            ),
        )

    def _flatten(self, snapshot: Any, run_id: str | None = None) -> dict[str, Any]:
        raw = as_mapping(snapshot)
        canonical = nested_get(raw, "canonical", "market", default={}) or {}
        status = nested_get(raw, "status", default={}) or {}
        prices = nested_get(raw, "price_metrics", default={}) or {}
        opportunity = nested_get(raw, "opportunity", default={}) or {}
        consensus = nested_get(raw, "institutional_consensus", "consensus", default=[]) or []
        evolution = nested_get(raw, "position_evolution", "evolution", default=[]) or []
        closing = nested_get(raw, "closing_line_metrics", "closing_line", default=[]) or []
        alerts = nested_get(raw, "alerts", default=[]) or []
        positions = nested_get(raw, "positions", default=[]) or []

        canonical = dict(canonical) if isinstance(canonical, Mapping) else {}
        status = dict(status) if isinstance(status, Mapping) else {}
        prices = dict(prices) if isinstance(prices, Mapping) else {}
        opportunity = dict(opportunity) if isinstance(opportunity, Mapping) else {}
        consensus_rows = [dict(x) for x in consensus if isinstance(x, Mapping)] if isinstance(consensus, list) else []
        evolution_rows = [dict(x) for x in evolution if isinstance(x, Mapping)] if isinstance(evolution, list) else []
        closing_rows = [dict(x) for x in closing if isinstance(x, Mapping)] if isinstance(closing, list) else []
        alert_rows = [dict(x) for x in alerts if isinstance(x, Mapping)] if isinstance(alerts, list) else []
        position_rows = [dict(x) for x in positions if isinstance(x, Mapping)] if isinstance(positions, list) else []
        c0 = consensus_rows[0] if consensus_rows else {}
        e0 = evolution_rows[0] if evolution_rows else {}
        cl0 = closing_rows[0] if closing_rows else {}
        a0 = alert_rows[0] if alert_rows else {}

        condition_id = text(
            nested_get(raw, "condition_id", "market_id", default=nested_get(canonical, "condition_id", default=nested_get(opportunity, "market_id", "condition_id")))
        ).lower()
        if not condition_id:
            raise DashboardValidationError("Snapshot is missing condition_id/market_id")
        outcome = text(nested_get(raw, "outcome", default=nested_get(opportunity, "outcome", default=nested_get(c0, "outcome", default="UNKNOWN"))), "UNKNOWN") or "UNKNOWN"
        active_alerts = [x for x in alert_rows if boolean_int(x.get("active", x.get("is_active", 1)))]
        risk_flags = nested_get(raw, "risk_flags", default=[])
        if not isinstance(risk_flags, list):
            risk_flags = [str(risk_flags)] if risk_flags else []

        return {
            "condition_id": condition_id,
            "outcome": outcome,
            "gamma_market_id": text(nested_get(canonical, "gamma_market_id", default=nested_get(raw, "gamma_market_id"))),
            "event_id": text(nested_get(canonical, "event_id", "gamma_event_id", default=nested_get(raw, "event_id"))),
            "question": text(nested_get(canonical, "question", "title", default=nested_get(raw, "question", "title"))),
            "market_slug": text(nested_get(canonical, "market_slug", "slug", default=nested_get(raw, "market_slug"))),
            "event_slug": text(nested_get(canonical, "event_slug", default=nested_get(raw, "event_slug"))),
            "polymarket_url": text(nested_get(canonical, "polymarket_url", "market_url", "url", default=nested_get(raw, "polymarket_url"))),
            "category": text(nested_get(canonical, "category", default=nested_get(raw, "category"))),
            "market_type": text(nested_get(canonical, "market_type", default=nested_get(raw, "market_type"))),
            "lifecycle_status": text(nested_get(status, "lifecycle_status", "status", default=nested_get(canonical, "lifecycle_status", default=nested_get(opportunity, "lifecycle_status")))),
            "active": boolean_int(nested_get(canonical, "active", default=nested_get(status, "active"))),
            "closed": boolean_int(nested_get(canonical, "closed", default=nested_get(status, "closed"))),
            "archived": boolean_int(nested_get(canonical, "archived", default=nested_get(status, "archived"))),
            "resolved": boolean_int(nested_get(status, "resolved", default=nested_get(canonical, "resolved"))),
            "tradable_identity": boolean_int(nested_get(canonical, "tradable_identity", "tradable", default=nested_get(raw, "tradable_identity"))),
            "restricted": boolean_int(nested_get(canonical, "restricted", default=0)),
            "start_time": text(nested_get(status, "start_time", "game_start_time", default=nested_get(canonical, "start_time", "event_start_time"))),
            "end_time": text(nested_get(status, "end_time", default=nested_get(canonical, "end_time"))),
            "seconds_to_start": number(nested_get(status, "seconds_to_start", default=nested_get(canonical, "seconds_to_start"))),
            "current_price": number(nested_get(prices, "current_price", "price", default=nested_get(opportunity, "current_price", "average_current_price"))),
            "yes_price": number(nested_get(prices, "yes_price", default=nested_get(canonical, "yes_price"))),
            "no_price": number(nested_get(prices, "no_price", default=nested_get(canonical, "no_price"))),
            "best_bid": number(nested_get(prices, "best_bid", default=nested_get(canonical, "best_bid"))),
            "best_ask": number(nested_get(prices, "best_ask", default=nested_get(canonical, "best_ask"))),
            "spread": number(nested_get(prices, "spread", default=nested_get(canonical, "spread"))),
            "liquidity": number(nested_get(canonical, "liquidity", default=nested_get(prices, "liquidity"))),
            "volume": number(nested_get(canonical, "volume")),
            "volume_24h": number(nested_get(canonical, "volume_24h", default=nested_get(prices, "volume_24h"))),
            "open_interest": number(nested_get(canonical, "open_interest", default=nested_get(prices, "open_interest"))),
            "wallet_count": integer(nested_get(c0, "wallet_count", "matching_wallets", default=nested_get(opportunity, "wallet_count"))),
            "effective_wallet_count": number(nested_get(opportunity, "effective_wallet_count", default=nested_get(c0, "effective_wallet_count"))),
            "combined_value": number(nested_get(c0, "combined_value", "total_value", default=nested_get(opportunity, "combined_value"))),
            "combined_shares": number(nested_get(c0, "combined_shares", "total_shares")),
            "consensus_strength": number(nested_get(c0, "consensus_strength", default=nested_get(opportunity, "consensus_strength"))),
            "conviction_score": number(nested_get(c0, "conviction_score", default=nested_get(opportunity, "conviction_score"))),
            "average_entry_price": number(nested_get(c0, "average_entry_price", "average_entry", default=nested_get(opportunity, "average_entry_price"))),
            "accumulation_score": number(nested_get(e0, "accumulation_score", "accumulation_strength")),
            "distribution_score": number(nested_get(e0, "distribution_score", "distribution_strength")),
            "position_trend": text(nested_get(e0, "position_trend", "trend", "evolution_state")),
            "price_move_5m": number(nested_get(prices, "price_move_5m", "move_5m")),
            "price_move_15m": number(nested_get(prices, "price_move_15m", "move_15m")),
            "price_move_1h": number(nested_get(prices, "price_move_1h", "move_1h")),
            "steam_score": number(nested_get(prices, "steam_score")),
            "reversal_score": number(nested_get(prices, "reversal_score")),
            "volatility_score": number(nested_get(prices, "volatility_score", "volatility")),
            "closing_line_value": number(nested_get(cl0, "closing_line_value", "clv", "observed_clv")),
            "closing_line_score": number(nested_get(cl0, "closing_line_score", "clv_score")),
            "master_score": number(nested_get(opportunity, "master_score", "opportunity_score", "score")),
            "opportunity_grade": text(nested_get(opportunity, "grade", "opportunity_grade", "master_grade")),
            "opportunity_recommendation": text(nested_get(opportunity, "recommendation", "final_recommendation")),
            "opportunity_confidence": number(nested_get(opportunity, "confidence", "confidence_score")),
            "edge_score": number(nested_get(opportunity, "edge_score", "edge")),
            "data_completeness_score": number(nested_get(opportunity, "data_completeness_score", "completeness_score")),
            "alert_count": len(alert_rows),
            "has_active_alert": int(bool(active_alerts)),
            "latest_alert_type": text(nested_get(a0, "alert_type", "type")),
            "latest_alert_created_at": text(nested_get(a0, "created_at", "alerted_at")),
            "intelligence_score": number(nested_get(raw, "intelligence_score")),
            "intelligence_grade": text(nested_get(raw, "intelligence_grade")),
            "confidence_score": number(nested_get(raw, "confidence_score")),
            "risk_score": number(nested_get(raw, "risk_score")),
            "final_recommendation": text(nested_get(raw, "final_recommendation")),
            "risk_flags_json": to_json(risk_flags),
            "canonical_json": to_json(canonical),
            "status_json": to_json(status),
            "price_metrics_json": to_json(prices),
            "consensus_json": to_json(consensus_rows),
            "evolution_json": to_json(evolution_rows),
            "closing_line_json": to_json(closing_rows),
            "opportunity_json": to_json(opportunity),
            "alerts_json": to_json(alert_rows),
            "positions_json": to_json(position_rows),
            "source_snapshot_json": to_json(raw),
            "source_updated_at": text(nested_get(raw, "source_updated_at", default=nested_get(opportunity, "updated_at", "calculated_at"))),
            "built_at": text(nested_get(raw, "built_at", "last_updated", default=utc_now_iso())),
            "run_id": run_id or text(nested_get(raw, "run_id")) or None,
            "schema_version": SCHEMA_VERSION,
        }

    def save_snapshot(self, snapshot: Any, *, run_id: str | None = None, save_history: bool = True) -> str:
        self.initialize_schema()
        values = self._flatten(snapshot, run_id)
        existing = self.data.fetch_one(
            f"SELECT id FROM {CURRENT_TABLE} WHERE condition_id=? AND outcome=?",
            (values["condition_id"], values["outcome"]),
        )
        columns = list(values)
        placeholders = ", ".join("?" for _ in columns)
        update_sql = ", ".join(
            f"{column}=excluded.{column}"
            for column in columns
            if column not in {"condition_id", "outcome"}
        )
        with self.transaction() as connection:
            connection.execute(
                f"""
                INSERT INTO {CURRENT_TABLE} ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(condition_id, outcome) DO UPDATE SET {update_sql}
                """,
                tuple(values[column] for column in columns),
            )
            if save_history:
                connection.execute(
                    f"""
                    INSERT INTO {HISTORY_TABLE} (
                        condition_id,outcome,run_id,question,lifecycle_status,current_price,
                        liquidity,volume_24h,spread,wallet_count,consensus_strength,
                        conviction_score,master_score,intelligence_score,intelligence_grade,
                        confidence_score,risk_score,final_recommendation,alert_count,
                        snapshot_json,captured_at,schema_version
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        values["condition_id"], values["outcome"], values["run_id"],
                        values["question"], values["lifecycle_status"], values["current_price"],
                        values["liquidity"], values["volume_24h"], values["spread"],
                        values["wallet_count"], values["consensus_strength"],
                        values["conviction_score"], values["master_score"],
                        values["intelligence_score"], values["intelligence_grade"],
                        values["confidence_score"], values["risk_score"],
                        values["final_recommendation"], values["alert_count"],
                        values["source_snapshot_json"], values["built_at"], SCHEMA_VERSION,
                    ),
                )
        return "updated" if existing else "inserted"

    def save_snapshots(
        self,
        snapshots: Iterable[Any],
        *,
        run_id: str | None = None,
        save_history: bool = True,
        continue_on_error: bool = True,
    ) -> dict[str, Any]:
        summary = {"processed": 0, "inserted": 0, "updated": 0, "history_rows": 0, "errors": []}
        for snapshot in snapshots:
            summary["processed"] += 1
            try:
                action = self.save_snapshot(snapshot, run_id=run_id, save_history=save_history)
                summary[action] += 1
                summary["history_rows"] += int(save_history)
            except Exception as error:
                summary["errors"].append(str(error))
                if not continue_on_error:
                    raise
        return summary

    def get_dashboard(
        self,
        *,
        limit: int = 500,
        category: str | None = None,
        lifecycle_status: str | None = None,
        tradable_only: bool = False,
        minimum_master_score: float | None = None,
        minimum_intelligence_score: float | None = None,
        order_by: str = "master_score",
        descending: bool = True,
    ) -> list[dict[str, Any]]:
        self.initialize_schema()
        allowed = {"master_score", "intelligence_score", "confidence_score", "risk_score", "consensus_strength", "conviction_score", "liquidity", "volume_24h", "current_price", "built_at"}
        order_by = order_by if order_by in allowed else "master_score"
        conditions: list[str] = []
        parameters: list[Any] = []
        if category:
            conditions.append("LOWER(category)=LOWER(?)")
            parameters.append(category)
        if lifecycle_status:
            conditions.append("LOWER(lifecycle_status)=LOWER(?)")
            parameters.append(lifecycle_status)
        if tradable_only:
            conditions.append("tradable_identity=1")
        if minimum_master_score is not None:
            conditions.append("master_score>=?")
            parameters.append(minimum_master_score)
        if minimum_intelligence_score is not None:
            conditions.append("intelligence_score>=?")
            parameters.append(minimum_intelligence_score)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(max(1, int(limit)))
        return self.data.fetch_all(
            f"SELECT * FROM {CURRENT_TABLE} {where} ORDER BY {order_by} {'DESC' if descending else 'ASC'}, built_at DESC LIMIT ?",
            parameters,
        )

    def get_market(self, condition_id: str, outcome: str | None = None) -> dict[str, Any] | None:
        self.initialize_schema()
        conditions = ["condition_id=?"]
        parameters: list[Any] = [text(condition_id).lower()]
        if outcome:
            conditions.append("outcome=?")
            parameters.append(text(outcome, "UNKNOWN"))
        return self.data.fetch_one(
            f"SELECT * FROM {CURRENT_TABLE} WHERE {' AND '.join(conditions)} ORDER BY master_score DESC LIMIT 1",
            parameters,
        )

    def get_top_opportunities(self, *, limit: int = 25, minimum_score: float | None = None, actionable_only: bool = False) -> list[dict[str, Any]]:
        self.initialize_schema()
        conditions: list[str] = []
        parameters: list[Any] = []
        if minimum_score is not None:
            conditions.append("COALESCE(intelligence_score,master_score)>=?")
            parameters.append(minimum_score)
        if actionable_only:
            conditions.append("UPPER(COALESCE(final_recommendation,opportunity_recommendation,'')) NOT IN ('','PASS','NO BET','AVOID','WATCH')")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(max(1, int(limit)))
        return self.data.fetch_all(
            f"SELECT * FROM {CURRENT_TABLE} {where} ORDER BY COALESCE(intelligence_score,master_score,0) DESC, confidence_score DESC LIMIT ?",
            parameters,
        )

    def get_dashboard_history(self, condition_id: str, outcome: str | None = None, *, limit: int = 250) -> list[dict[str, Any]]:
        self.initialize_schema()
        conditions = ["condition_id=?"]
        parameters: list[Any] = [text(condition_id).lower()]
        if outcome:
            conditions.append("outcome=?")
            parameters.append(text(outcome, "UNKNOWN"))
        parameters.append(max(1, int(limit)))
        return self.data.fetch_all(
            f"SELECT * FROM {HISTORY_TABLE} WHERE {' AND '.join(conditions)} ORDER BY captured_at DESC,id DESC LIMIT ?",
            parameters,
        )

    def get_last_run(self) -> dict[str, Any] | None:
        self.initialize_schema()
        return self.data.fetch_one(f"SELECT * FROM {RUNS_TABLE} ORDER BY started_at DESC,id DESC LIMIT 1")

    def clear_dashboard(self) -> int:
        self.initialize_schema()
        return self.data.execute(f"DELETE FROM {CURRENT_TABLE}")

    def clear_history(self) -> int:
        self.initialize_schema()
        return self.data.execute(f"DELETE FROM {HISTORY_TABLE}")

    def statistics(self) -> dict[str, Any]:
        self.initialize_schema()
        stats = self.data.fetch_one(
            f"""
            SELECT COUNT(*) dashboard_rows, COUNT(DISTINCT condition_id) unique_markets,
                   SUM(CASE WHEN tradable_identity=1 THEN 1 ELSE 0 END) tradable_rows,
                   SUM(CASE WHEN has_active_alert=1 THEN 1 ELSE 0 END) active_alert_rows,
                   AVG(master_score) avg_master_score, MAX(master_score) max_master_score,
                   AVG(intelligence_score) avg_intelligence_score,
                   MAX(intelligence_score) max_intelligence_score, MAX(built_at) latest_build
            FROM {CURRENT_TABLE}
            """
        ) or {}
        stats["history_rows"] = self.data.table_row_count(HISTORY_TABLE)
        stats["run_rows"] = self.data.table_row_count(RUNS_TABLE)
        return stats

    def integrity_check(self) -> dict[str, Any]:
        self.initialize_schema()
        duplicates = self.data.fetch_all(
            f"SELECT condition_id,outcome,COUNT(*) duplicate_count FROM {CURRENT_TABLE} GROUP BY condition_id,outcome HAVING COUNT(*)>1"
        )
        missing = self.data.fetch_one(
            f"SELECT COUNT(*) total FROM {CURRENT_TABLE} WHERE condition_id IS NULL OR TRIM(condition_id)=''"
        ) or {"total": 0}
        return {
            "schema_ready": self.schema_ready(),
            "duplicate_rows": duplicates,
            "missing_identity_rows": int(missing["total"]),
            "passed": self.schema_ready() and not duplicates and int(missing["total"]) == 0,
        }


def main() -> None:
    repository = DashboardRepository()
    repository.initialize_schema()
    integrity = repository.integrity_check()
    print()
    print("=" * 108)
    print("MASTER INTELLIGENCE DASHBOARD REPOSITORY")
    print("=" * 108)
    print(f"Database: {repository.database_path}")
    for table_name in (CURRENT_TABLE, HISTORY_TABLE, RUNS_TABLE):
        print(f"{table_name:<52}{repository.data.table_row_count(table_name):>12} rows")
    print("-" * 108)
    print(f"Schema ready: {'YES' if integrity['schema_ready'] else 'NO'}")
    print(f"Duplicate identities: {len(integrity['duplicate_rows'])}")
    print(f"Missing condition IDs: {integrity['missing_identity_rows']}")
    print(f"Integrity status: {'PASS' if integrity['passed'] else 'REVIEW'}")
    print("DASHBOARD REPOSITORY READY")
    print("=" * 108)


if __name__ == "__main__":
    main()