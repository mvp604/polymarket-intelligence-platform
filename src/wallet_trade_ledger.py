from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"
DISPLAY_LIMIT = 25
EPSILON = 1e-9


def text(value: Any) -> str:
    return str(value or "").strip()


def wallet_text(value: Any) -> str:
    return text(value).lower()


def market_text(value: Any) -> str:
    return text(value).lower()


def outcome_text(value: Any) -> str:
    return text(value).casefold()


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


def divide(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b else default


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: Any) -> datetime | None:
    raw = text(value)
    if not raw:
        return None
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def money(value: Any) -> str:
    amount = number(value)
    if amount > 0:
        return f"+${amount:,.2f}"
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return "$0.00"


def configure_utf8() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def connect() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(f"Database not found: {DB}")

    connection = sqlite3.connect(DB, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def create_tables() -> None:
    connection = connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS wallet_trade_events (
                trade_event_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                previous_scan_id INTEGER,
                current_scan_id INTEGER NOT NULL,
                previous_scanned_at TEXT,
                current_scanned_at TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT,
                outcome TEXT,
                event_type TEXT NOT NULL,
                event_sequence INTEGER NOT NULL,
                previous_shares REAL NOT NULL DEFAULT 0,
                current_shares REAL NOT NULL DEFAULT 0,
                share_change REAL NOT NULL DEFAULT 0,
                previous_average_price REAL,
                current_average_price REAL,
                inferred_trade_price REAL,
                previous_current_price REAL,
                current_current_price REAL,
                previous_current_value REAL NOT NULL DEFAULT 0,
                current_current_value REAL NOT NULL DEFAULT 0,
                value_change REAL NOT NULL DEFAULT 0,
                estimated_cash_flow REAL NOT NULL DEFAULT 0,
                estimated_realized_pnl REAL,
                confidence_score REAL NOT NULL DEFAULT 0,
                explanation_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_wallet_trade_events_wallet
            ON wallet_trade_events(wallet, current_scanned_at);

            CREATE INDEX IF NOT EXISTS idx_wallet_trade_events_market
            ON wallet_trade_events(wallet, market_id, outcome, current_scanned_at);

            CREATE TABLE IF NOT EXISTS wallet_trade_positions (
                position_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT,
                outcome TEXT,
                first_scan_id INTEGER,
                last_scan_id INTEGER,
                first_seen_at TEXT,
                last_seen_at TEXT,
                opened_at TEXT,
                closed_at TEXT,
                event_count INTEGER NOT NULL DEFAULT 0,
                buy_event_count INTEGER NOT NULL DEFAULT 0,
                sell_event_count INTEGER NOT NULL DEFAULT 0,
                scale_in_count INTEGER NOT NULL DEFAULT 0,
                scale_out_count INTEGER NOT NULL DEFAULT 0,
                initial_shares REAL NOT NULL DEFAULT 0,
                peak_shares REAL NOT NULL DEFAULT 0,
                final_shares REAL NOT NULL DEFAULT 0,
                total_shares_added REAL NOT NULL DEFAULT 0,
                total_shares_removed REAL NOT NULL DEFAULT 0,
                initial_average_price REAL,
                latest_average_price REAL,
                estimated_buy_cost REAL NOT NULL DEFAULT 0,
                estimated_sell_proceeds REAL NOT NULL DEFAULT 0,
                estimated_realized_pnl REAL NOT NULL DEFAULT 0,
                latest_current_price REAL,
                latest_current_value REAL NOT NULL DEFAULT 0,
                estimated_unrealized_pnl REAL NOT NULL DEFAULT 0,
                total_estimated_pnl REAL NOT NULL DEFAULT 0,
                holding_seconds INTEGER,
                position_status TEXT NOT NULL DEFAULT 'OPEN',
                data_confidence TEXT NOT NULL DEFAULT 'LOW',
                explanation_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_wallet_trade_positions_wallet
            ON wallet_trade_positions(wallet, position_status);

            CREATE TABLE IF NOT EXISTS wallet_trade_ledger_summary (
                wallet TEXT PRIMARY KEY,
                scan_count INTEGER NOT NULL DEFAULT 0,
                reconstructed_position_count INTEGER NOT NULL DEFAULT 0,
                open_position_count INTEGER NOT NULL DEFAULT 0,
                closed_position_count INTEGER NOT NULL DEFAULT 0,
                trade_event_count INTEGER NOT NULL DEFAULT 0,
                open_event_count INTEGER NOT NULL DEFAULT 0,
                add_event_count INTEGER NOT NULL DEFAULT 0,
                trim_event_count INTEGER NOT NULL DEFAULT 0,
                close_event_count INTEGER NOT NULL DEFAULT 0,
                estimated_buy_cost REAL NOT NULL DEFAULT 0,
                estimated_sell_proceeds REAL NOT NULL DEFAULT 0,
                estimated_realized_pnl REAL NOT NULL DEFAULT 0,
                estimated_unrealized_pnl REAL NOT NULL DEFAULT 0,
                total_estimated_pnl REAL NOT NULL DEFAULT 0,
                average_hold_seconds REAL,
                average_trade_size REAL NOT NULL DEFAULT 0,
                scale_in_rate REAL NOT NULL DEFAULT 0,
                scale_out_rate REAL NOT NULL DEFAULT 0,
                complete_history_score REAL NOT NULL DEFAULT 0,
                ledger_confidence TEXT NOT NULL DEFAULT 'VERY LOW',
                first_scan_at TEXT,
                last_scan_at TEXT,
                explanation_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallet_trade_ledger_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                scan_count INTEGER,
                reconstructed_position_count INTEGER,
                open_position_count INTEGER,
                closed_position_count INTEGER,
                trade_event_count INTEGER,
                estimated_realized_pnl REAL,
                estimated_unrealized_pnl REAL,
                total_estimated_pnl REAL,
                complete_history_score REAL,
                ledger_confidence TEXT,
                observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallet_trade_ledger_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                scans_loaded INTEGER NOT NULL DEFAULT 0,
                positions_loaded INTEGER NOT NULL DEFAULT 0,
                wallets_processed INTEGER NOT NULL DEFAULT 0,
                trade_events_saved INTEGER NOT NULL DEFAULT 0,
                reconstructed_positions_saved INTEGER NOT NULL DEFAULT 0,
                summary_rows_saved INTEGER NOT NULL DEFAULT 0,
                history_rows_saved INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def load_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    connection = connect()
    try:
        for table in ("wallet_scans", "positions"):
            if not table_exists(connection, table):
                raise RuntimeError(f"Required table is missing: {table}")

        scans = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM wallet_scans
                ORDER BY wallet, scanned_at, id
                """
            )
        ]

        positions = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM positions
                ORDER BY wallet, scan_id, market_id, outcome
                """
            )
        ]

        return scans, positions
    finally:
        connection.close()


def identity(position: dict[str, Any]) -> tuple[str, str]:
    return (
        market_text(position.get("market_id")),
        outcome_text(position.get("outcome")),
    )


def classify(
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> tuple[str, float]:
    previous_shares = number(previous.get("shares") if previous else 0)
    current_shares = number(current.get("shares") if current else 0)
    change = current_shares - previous_shares

    if previous_shares <= EPSILON and current_shares > EPSILON:
        return "OPEN", change
    if previous_shares > EPSILON and current_shares <= EPSILON:
        return "CLOSE", change
    if change > EPSILON:
        return "ADD", change
    if change < -EPSILON:
        return "TRIM", change
    return "UNCHANGED", change


def infer_price(
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
    change: float,
) -> float | None:
    if abs(change) <= EPSILON:
        return None

    previous_shares = number(previous.get("shares") if previous else 0)
    current_shares = number(current.get("shares") if current else 0)
    previous_average = number(previous.get("average_price") if previous else 0)
    current_average = number(current.get("average_price") if current else 0)

    if change > 0:
        if previous is None:
            return max(0.0, min(current_average, 1.0))
        inferred = divide(
            current_average * current_shares
            - previous_average * previous_shares,
            change,
            current_average,
        )
        return max(0.0, min(inferred, 1.0))

    observed_sell_price = number(
        previous.get("current_price") if previous else previous_average,
        previous_average,
    )
    return max(0.0, min(observed_sell_price, 1.0))


def reconstruct() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
    int,
]:
    scans, positions = load_data()
    timestamp = now_iso()

    scans_by_wallet: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scan in scans:
        wallet = wallet_text(scan.get("wallet"))
        if wallet:
            scans_by_wallet[wallet].append(scan)

    positions_by_scan: dict[int, dict[tuple[str, str], dict[str, Any]]] = (
        defaultdict(dict)
    )
    for position in positions:
        positions_by_scan[integer(position.get("scan_id"))][identity(position)] = (
            position
        )

    events: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for wallet, wallet_scans in scans_by_wallet.items():
        wallet_scans.sort(
            key=lambda row: (
                text(row.get("scanned_at")),
                integer(row.get("id")),
            )
        )

        states: dict[tuple[str, str], dict[str, Any]] = {}
        wallet_events: list[dict[str, Any]] = []
        sequence = 0

        for scan_index, scan in enumerate(wallet_scans):
            current_scan_id = integer(scan.get("id"))
            current_time = text(scan.get("scanned_at"))
            previous_scan = wallet_scans[scan_index - 1] if scan_index else None
            previous_scan_id = (
                integer(previous_scan.get("id")) if previous_scan else None
            )
            previous_time = (
                text(previous_scan.get("scanned_at")) if previous_scan else ""
            )

            previous_positions = (
                positions_by_scan.get(previous_scan_id, {})
                if previous_scan_id is not None
                else {}
            )
            current_positions = positions_by_scan.get(current_scan_id, {})

            all_ids = set(previous_positions) | set(current_positions)

            for position_id in sorted(all_ids):
                previous = previous_positions.get(position_id)
                current = current_positions.get(position_id)
                event_type, change = classify(previous, current)
                sequence += 1

                source = current or previous or {}
                market_id, normalized_outcome = position_id
                title = text(source.get("title"))
                outcome = text(source.get("outcome"))

                previous_shares = number(
                    previous.get("shares") if previous else 0
                )
                current_shares = number(current.get("shares") if current else 0)
                previous_average = (
                    number(previous.get("average_price")) if previous else None
                )
                current_average = (
                    number(current.get("average_price")) if current else None
                )
                inferred_trade_price = infer_price(previous, current, change)

                previous_current_price = (
                    number(previous.get("current_price")) if previous else None
                )
                current_current_price = (
                    number(current.get("current_price")) if current else None
                )
                previous_value = (
                    number(previous.get("current_value")) if previous else 0.0
                )
                current_value = (
                    number(current.get("current_value")) if current else 0.0
                )

                cash_flow = 0.0
                realized_pnl = None
                confidence = 100.0 if event_type == "UNCHANGED" else 80.0

                if event_type in {"OPEN", "ADD"} and inferred_trade_price is not None:
                    cash_flow = -abs(change) * inferred_trade_price
                elif event_type in {"TRIM", "CLOSE"} and inferred_trade_price is not None:
                    removed = abs(change)
                    cash_flow = removed * inferred_trade_price
                    realized_pnl = removed * (
                        inferred_trade_price - (previous_average or 0.0)
                    )
                    confidence = 65.0

                event = {
                    "trade_event_key": (
                        f"{wallet}:{current_scan_id}:{market_id}:{normalized_outcome}"
                    ),
                    "wallet": wallet,
                    "previous_scan_id": previous_scan_id,
                    "current_scan_id": current_scan_id,
                    "previous_scanned_at": previous_time,
                    "current_scanned_at": current_time,
                    "market_id": market_id,
                    "title": title,
                    "outcome": outcome,
                    "event_type": event_type,
                    "event_sequence": sequence,
                    "previous_shares": previous_shares,
                    "current_shares": current_shares,
                    "share_change": change,
                    "previous_average_price": previous_average,
                    "current_average_price": current_average,
                    "inferred_trade_price": inferred_trade_price,
                    "previous_current_price": previous_current_price,
                    "current_current_price": current_current_price,
                    "previous_current_value": previous_value,
                    "current_current_value": current_value,
                    "value_change": current_value - previous_value,
                    "estimated_cash_flow": cash_flow,
                    "estimated_realized_pnl": realized_pnl,
                    "confidence_score": confidence,
                    "explanation_json": json.dumps(
                        {
                            "method": "CONSECUTIVE POSITION SNAPSHOT DIFFERENCE",
                            "warning": (
                                "Multiple actual trades between scans may be "
                                "collapsed into one inferred event."
                            ),
                        },
                        ensure_ascii=False,
                    ),
                    "calculated_at": timestamp,
                    "updated_at": timestamp,
                }

                events.append(event)
                wallet_events.append(event)

                state = states.get(position_id)
                if state is None:
                    state = {
                        "wallet": wallet,
                        "market_id": market_id,
                        "title": title,
                        "outcome": outcome,
                        "first_scan_id": current_scan_id,
                        "last_scan_id": current_scan_id,
                        "first_seen_at": current_time,
                        "last_seen_at": current_time,
                        "opened_at": "",
                        "closed_at": "",
                        "event_count": 0,
                        "buy_event_count": 0,
                        "sell_event_count": 0,
                        "scale_in_count": 0,
                        "scale_out_count": 0,
                        "initial_shares": 0.0,
                        "peak_shares": 0.0,
                        "final_shares": 0.0,
                        "total_shares_added": 0.0,
                        "total_shares_removed": 0.0,
                        "initial_average_price": None,
                        "latest_average_price": None,
                        "estimated_buy_cost": 0.0,
                        "estimated_sell_proceeds": 0.0,
                        "estimated_realized_pnl": 0.0,
                        "latest_current_price": None,
                        "latest_current_value": 0.0,
                    }
                    states[position_id] = state

                state["last_scan_id"] = current_scan_id
                state["last_seen_at"] = current_time
                state["event_count"] += 1

                if event_type == "OPEN":
                    state["opened_at"] = current_time
                    state["initial_shares"] = current_shares
                    state["initial_average_price"] = current_average
                    state["buy_event_count"] += 1
                elif event_type == "ADD":
                    state["buy_event_count"] += 1
                    state["scale_in_count"] += 1
                elif event_type == "TRIM":
                    state["sell_event_count"] += 1
                    state["scale_out_count"] += 1
                elif event_type == "CLOSE":
                    state["sell_event_count"] += 1
                    state["closed_at"] = current_time

                if change > 0:
                    state["total_shares_added"] += change
                    if inferred_trade_price is not None:
                        state["estimated_buy_cost"] += change * inferred_trade_price
                elif change < 0:
                    removed = abs(change)
                    state["total_shares_removed"] += removed
                    if inferred_trade_price is not None:
                        state["estimated_sell_proceeds"] += (
                            removed * inferred_trade_price
                        )
                    if realized_pnl is not None:
                        state["estimated_realized_pnl"] += realized_pnl

                state["peak_shares"] = max(
                    number(state["peak_shares"]),
                    previous_shares,
                    current_shares,
                )
                state["final_shares"] = current_shares

                if current is not None:
                    state["latest_average_price"] = current_average
                    state["latest_current_price"] = current_current_price
                    state["latest_current_value"] = current_value

        current_position_rows: list[dict[str, Any]] = []

        for position_id, state in states.items():
            market_id, normalized_outcome = position_id
            opened = parse_time(state["opened_at"] or state["first_seen_at"])
            ended = parse_time(state["closed_at"] or state["last_seen_at"])
            holding_seconds = (
                int((ended - opened).total_seconds())
                if opened is not None and ended is not None
                else None
            )

            final_shares = number(state["final_shares"])
            latest_average = number(state["latest_average_price"])
            latest_price = number(state["latest_current_price"])
            unrealized = final_shares * (latest_price - latest_average)
            total_pnl = number(state["estimated_realized_pnl"]) + unrealized
            status = "CLOSED" if final_shares <= EPSILON else "OPEN"

            if len(wallet_scans) >= 10:
                confidence = "HIGH"
            elif len(wallet_scans) >= 5:
                confidence = "MEDIUM"
            elif len(wallet_scans) >= 2:
                confidence = "LOW"
            else:
                confidence = "VERY LOW"

            row = {
                "position_key": f"{wallet}:{market_id}:{normalized_outcome}",
                "wallet": wallet,
                "market_id": market_id,
                "title": state["title"],
                "outcome": state["outcome"],
                "first_scan_id": state["first_scan_id"],
                "last_scan_id": state["last_scan_id"],
                "first_seen_at": state["first_seen_at"],
                "last_seen_at": state["last_seen_at"],
                "opened_at": state["opened_at"],
                "closed_at": state["closed_at"],
                "event_count": state["event_count"],
                "buy_event_count": state["buy_event_count"],
                "sell_event_count": state["sell_event_count"],
                "scale_in_count": state["scale_in_count"],
                "scale_out_count": state["scale_out_count"],
                "initial_shares": state["initial_shares"],
                "peak_shares": state["peak_shares"],
                "final_shares": final_shares,
                "total_shares_added": state["total_shares_added"],
                "total_shares_removed": state["total_shares_removed"],
                "initial_average_price": state["initial_average_price"],
                "latest_average_price": state["latest_average_price"],
                "estimated_buy_cost": state["estimated_buy_cost"],
                "estimated_sell_proceeds": state["estimated_sell_proceeds"],
                "estimated_realized_pnl": state["estimated_realized_pnl"],
                "latest_current_price": state["latest_current_price"],
                "latest_current_value": state["latest_current_value"],
                "estimated_unrealized_pnl": unrealized,
                "total_estimated_pnl": total_pnl,
                "holding_seconds": holding_seconds,
                "position_status": status,
                "data_confidence": confidence,
                "explanation_json": json.dumps(
                    {
                        "method": "SNAPSHOT-DIFFERENCED POSITION HISTORY",
                        "scan_count": len(wallet_scans),
                    },
                    ensure_ascii=False,
                ),
                "calculated_at": timestamp,
                "updated_at": timestamp,
            }

            position_rows.append(row)
            current_position_rows.append(row)

        actual_trade_events = [
            event
            for event in wallet_events
            if event["event_type"] != "UNCHANGED"
        ]
        holding_values = [
            integer(row["holding_seconds"])
            for row in current_position_rows
            if row["holding_seconds"] is not None
        ]
        trade_sizes = [
            abs(number(event["estimated_cash_flow"]))
            for event in actual_trade_events
        ]

        scan_count = len(wallet_scans)
        history_score = min(
            100.0,
            min(scan_count / 12.0, 1.0) * 65.0
            + min(len(actual_trade_events) / 20.0, 1.0) * 20.0
            + min(len(current_position_rows) / 20.0, 1.0) * 15.0,
        )

        if history_score >= 80:
            confidence = "VERY HIGH"
        elif history_score >= 60:
            confidence = "HIGH"
        elif history_score >= 40:
            confidence = "MEDIUM"
        elif history_score >= 20:
            confidence = "LOW"
        else:
            confidence = "VERY LOW"

        summaries.append(
            {
                "wallet": wallet,
                "scan_count": scan_count,
                "reconstructed_position_count": len(current_position_rows),
                "open_position_count": sum(
                    row["position_status"] == "OPEN"
                    for row in current_position_rows
                ),
                "closed_position_count": sum(
                    row["position_status"] == "CLOSED"
                    for row in current_position_rows
                ),
                "trade_event_count": len(actual_trade_events),
                "open_event_count": sum(
                    event["event_type"] == "OPEN" for event in wallet_events
                ),
                "add_event_count": sum(
                    event["event_type"] == "ADD" for event in wallet_events
                ),
                "trim_event_count": sum(
                    event["event_type"] == "TRIM" for event in wallet_events
                ),
                "close_event_count": sum(
                    event["event_type"] == "CLOSE" for event in wallet_events
                ),
                "estimated_buy_cost": sum(
                    row["estimated_buy_cost"] for row in current_position_rows
                ),
                "estimated_sell_proceeds": sum(
                    row["estimated_sell_proceeds"]
                    for row in current_position_rows
                ),
                "estimated_realized_pnl": sum(
                    row["estimated_realized_pnl"]
                    for row in current_position_rows
                ),
                "estimated_unrealized_pnl": sum(
                    row["estimated_unrealized_pnl"]
                    for row in current_position_rows
                ),
                "total_estimated_pnl": sum(
                    row["total_estimated_pnl"] for row in current_position_rows
                ),
                "average_hold_seconds": (
                    divide(sum(holding_values), len(holding_values))
                    if holding_values
                    else None
                ),
                "average_trade_size": (
                    divide(sum(trade_sizes), len(trade_sizes))
                    if trade_sizes
                    else 0.0
                ),
                "scale_in_rate": divide(
                    sum(event["event_type"] == "ADD" for event in wallet_events),
                    len(actual_trade_events),
                ),
                "scale_out_rate": divide(
                    sum(event["event_type"] == "TRIM" for event in wallet_events),
                    len(actual_trade_events),
                ),
                "complete_history_score": history_score,
                "ledger_confidence": confidence,
                "first_scan_at": text(wallet_scans[0].get("scanned_at")),
                "last_scan_at": text(wallet_scans[-1].get("scanned_at")),
                "explanation_json": json.dumps(
                    {
                        "method": "CONSECUTIVE POSITION SNAPSHOT DIFFERENCING",
                        "warning": (
                            "This is an inferred ledger, not a complete "
                            "transaction-level exchange ledger."
                        ),
                    },
                    ensure_ascii=False,
                ),
                "calculated_at": timestamp,
                "updated_at": timestamp,
            }
        )

    summaries.sort(
        key=lambda row: (
            row["complete_history_score"],
            row["trade_event_count"],
        ),
        reverse=True,
    )
    return events, position_rows, summaries, len(scans), len(positions)


EVENT_COLUMNS = [
    "trade_event_key",
    "wallet",
    "previous_scan_id",
    "current_scan_id",
    "previous_scanned_at",
    "current_scanned_at",
    "market_id",
    "title",
    "outcome",
    "event_type",
    "event_sequence",
    "previous_shares",
    "current_shares",
    "share_change",
    "previous_average_price",
    "current_average_price",
    "inferred_trade_price",
    "previous_current_price",
    "current_current_price",
    "previous_current_value",
    "current_current_value",
    "value_change",
    "estimated_cash_flow",
    "estimated_realized_pnl",
    "confidence_score",
    "explanation_json",
    "calculated_at",
    "updated_at",
]

POSITION_COLUMNS = [
    "position_key",
    "wallet",
    "market_id",
    "title",
    "outcome",
    "first_scan_id",
    "last_scan_id",
    "first_seen_at",
    "last_seen_at",
    "opened_at",
    "closed_at",
    "event_count",
    "buy_event_count",
    "sell_event_count",
    "scale_in_count",
    "scale_out_count",
    "initial_shares",
    "peak_shares",
    "final_shares",
    "total_shares_added",
    "total_shares_removed",
    "initial_average_price",
    "latest_average_price",
    "estimated_buy_cost",
    "estimated_sell_proceeds",
    "estimated_realized_pnl",
    "latest_current_price",
    "latest_current_value",
    "estimated_unrealized_pnl",
    "total_estimated_pnl",
    "holding_seconds",
    "position_status",
    "data_confidence",
    "explanation_json",
    "calculated_at",
    "updated_at",
]

SUMMARY_COLUMNS = [
    "wallet",
    "scan_count",
    "reconstructed_position_count",
    "open_position_count",
    "closed_position_count",
    "trade_event_count",
    "open_event_count",
    "add_event_count",
    "trim_event_count",
    "close_event_count",
    "estimated_buy_cost",
    "estimated_sell_proceeds",
    "estimated_realized_pnl",
    "estimated_unrealized_pnl",
    "total_estimated_pnl",
    "average_hold_seconds",
    "average_trade_size",
    "scale_in_rate",
    "scale_out_rate",
    "complete_history_score",
    "ledger_confidence",
    "first_scan_at",
    "last_scan_at",
    "explanation_json",
    "calculated_at",
    "updated_at",
]


def insert_query(table: str, columns: list[str]) -> str:
    names = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    return f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})'


def save(
    events: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> tuple[int, int, int, int]:
    connection = connect()
    observed_at = now_iso()

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM wallet_trade_events")
        connection.execute("DELETE FROM wallet_trade_positions")
        connection.execute("DELETE FROM wallet_trade_ledger_summary")

        event_query = insert_query("wallet_trade_events", EVENT_COLUMNS)
        position_query = insert_query("wallet_trade_positions", POSITION_COLUMNS)
        summary_query = insert_query(
            "wallet_trade_ledger_summary",
            SUMMARY_COLUMNS,
        )

        for row in events:
            connection.execute(
                event_query,
                tuple(row[column] for column in EVENT_COLUMNS),
            )

        for row in positions:
            connection.execute(
                position_query,
                tuple(row[column] for column in POSITION_COLUMNS),
            )

        for row in summaries:
            connection.execute(
                summary_query,
                tuple(row[column] for column in SUMMARY_COLUMNS),
            )
            connection.execute(
                """
                INSERT INTO wallet_trade_ledger_history (
                    wallet,
                    scan_count,
                    reconstructed_position_count,
                    open_position_count,
                    closed_position_count,
                    trade_event_count,
                    estimated_realized_pnl,
                    estimated_unrealized_pnl,
                    total_estimated_pnl,
                    complete_history_score,
                    ledger_confidence,
                    observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["wallet"],
                    row["scan_count"],
                    row["reconstructed_position_count"],
                    row["open_position_count"],
                    row["closed_position_count"],
                    row["trade_event_count"],
                    row["estimated_realized_pnl"],
                    row["estimated_unrealized_pnl"],
                    row["total_estimated_pnl"],
                    row["complete_history_score"],
                    row["ledger_confidence"],
                    observed_at,
                ),
            )

        connection.commit()
        return len(events), len(positions), len(summaries), len(summaries)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def start_run() -> tuple[int, datetime]:
    started = datetime.now(timezone.utc)
    connection = connect()
    try:
        cursor = connection.execute(
            """
            INSERT INTO wallet_trade_ledger_runs(started_at, status)
            VALUES (?, 'RUNNING')
            """,
            (started.isoformat(),),
        )
        connection.commit()
        return cursor.lastrowid, started
    finally:
        connection.close()


def finish_run(
    run_id: int,
    started: datetime,
    status: str,
    scans_loaded: int,
    positions_loaded: int,
    wallets_processed: int,
    events_saved: int,
    positions_saved: int,
    summaries_saved: int,
    history_saved: int,
    error_message: str = "",
) -> None:
    finished = datetime.now(timezone.utc)
    connection = connect()
    try:
        connection.execute(
            """
            UPDATE wallet_trade_ledger_runs
            SET finished_at=?,
                elapsed_seconds=?,
                scans_loaded=?,
                positions_loaded=?,
                wallets_processed=?,
                trade_events_saved=?,
                reconstructed_positions_saved=?,
                summary_rows_saved=?,
                history_rows_saved=?,
                status=?,
                error_message=?
            WHERE id=?
            """,
            (
                finished.isoformat(),
                (finished - started).total_seconds(),
                scans_loaded,
                positions_loaded,
                wallets_processed,
                events_saved,
                positions_saved,
                summaries_saved,
                history_saved,
                status,
                error_message,
                run_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def show_summary(
    events: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    scans_loaded: int,
    raw_positions_loaded: int,
    display_limit: int,
) -> None:
    print()
    print("=" * 112)
    print("WALLET TRADE LEDGER SUMMARY")
    print("=" * 112)
    print(f"Wallet scans loaded:            {scans_loaded}")
    print(f"Raw position rows loaded:       {raw_positions_loaded}")
    print(f"Wallets reconstructed:          {len(summaries)}")
    print(f"Trade events inferred:          {len(events)}")
    print(f"Position histories rebuilt:     {len(positions)}")
    print(
        "Estimated realized PnL:         "
        + money(sum(row["estimated_realized_pnl"] for row in summaries))
    )
    print(
        "Estimated unrealized PnL:       "
        + money(sum(row["estimated_unrealized_pnl"] for row in summaries))
    )
    print("=" * 112)

    print()
    print("TOP WALLET LEDGER COVERAGE")

    for rank, row in enumerate(summaries[:display_limit], start=1):
        print()
        print("-" * 112)
        print(f"{rank}. {row['wallet']}")
        print("-" * 112)
        print(
            f"Ledger confidence:              "
            f"{row['ledger_confidence']} "
            f"({row['complete_history_score']:.1f})"
        )
        print(f"Scans:                          {row['scan_count']}")
        print(
            f"Positions reconstructed:        "
            f"{row['reconstructed_position_count']}"
        )
        print(
            f"Open / closed positions:        "
            f"{row['open_position_count']} / {row['closed_position_count']}"
        )
        print(f"Trade events:                   {row['trade_event_count']}")
        print(
            f"Open / add / trim / close:      "
            f"{row['open_event_count']} / "
            f"{row['add_event_count']} / "
            f"{row['trim_event_count']} / "
            f"{row['close_event_count']}"
        )
        print(
            f"Estimated realized PnL:         "
            f"{money(row['estimated_realized_pnl'])}"
        )
        print(
            f"Estimated unrealized PnL:       "
            f"{money(row['estimated_unrealized_pnl'])}"
        )
        print(
            f"Total estimated PnL:            "
            f"{money(row['total_estimated_pnl'])}"
        )
        print(
            f"Average trade size:             "
            f"{money(row['average_trade_size'])}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Infer wallet trade events by comparing consecutive "
            "stored position snapshots."
        )
    )
    parser.add_argument("--display-limit", type=int, default=DISPLAY_LIMIT)
    return parser.parse_args()


def main() -> None:
    configure_utf8()
    args = parse_args()

    print()
    print("=" * 112)
    print("POLYMARKET WALLET TRADE LEDGER v1")
    print("=" * 112)
    print(f"Database: {DB}")
    print("Method: consecutive position snapshot differencing")

    create_tables()
    run_id, started = start_run()

    events: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    scans_loaded = 0
    raw_positions_loaded = 0
    events_saved = 0
    positions_saved = 0
    summaries_saved = 0
    history_saved = 0

    try:
        (
            events,
            positions,
            summaries,
            scans_loaded,
            raw_positions_loaded,
        ) = reconstruct()

        (
            events_saved,
            positions_saved,
            summaries_saved,
            history_saved,
        ) = save(events, positions, summaries)

        finish_run(
            run_id,
            started,
            "SUCCESS",
            scans_loaded,
            raw_positions_loaded,
            len(summaries),
            events_saved,
            positions_saved,
            summaries_saved,
            history_saved,
        )

        show_summary(
            events,
            positions,
            summaries,
            scans_loaded,
            raw_positions_loaded,
            max(args.display_limit, 1),
        )

        print()
        print("=" * 112)
        print("WALLET TRADE LEDGER COMPLETE")
        print("=" * 112)
        print("Inferred events: wallet_trade_events")
        print("Reconstructed positions: wallet_trade_positions")
        print("Wallet summaries: wallet_trade_ledger_summary")
        print("Historical snapshots: wallet_trade_ledger_history")
        print(
            "Important: this is an inferred snapshot ledger, "
            "not a transaction-complete exchange ledger."
        )
        print("=" * 112)

    except Exception as error:
        finish_run(
            run_id,
            started,
            "FAILED",
            scans_loaded,
            raw_positions_loaded,
            len(summaries),
            events_saved,
            positions_saved,
            summaries_saved,
            history_saved,
            f"{type(error).__name__}: {error}",
        )
        raise


if __name__ == "__main__":
    main()