from __future__ import annotations

# BEGIN MARKET CHANGE UTF8
import sys

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
# END MARKET CHANGE UTF8


import argparse
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ENGINE_NAME = "Market Change Engine"
ENGINE_VERSION = "1.0.0"
DEFAULT_DATABASE_PATH = Path("database/polymarket.db")


@dataclass(slots=True)
class Config:
    database_path: Path
    min_price_change: float
    min_liquidity_change: float
    min_volume_change: float
    min_spread_change: float
    display_limit: int


@dataclass(slots=True)
class Stats:
    run_id: str
    started_at: str
    markets_reviewed: int = 0
    events_written: int = 0
    new_markets: int = 0
    price_moves: int = 0
    liquidity_moves: int = 0
    volume_moves: int = 0
    spread_moves: int = 0
    closed_markets: int = 0
    resolved_markets: int = 0
    reopened_markets: int = 0
    no_previous_snapshot: int = 0


@dataclass(slots=True)
class ChangeEvent:
    condition_id: str
    question: str
    change_type: str
    direction: str
    previous_value: float | None
    current_value: float | None
    absolute_change: float | None
    percent_change: float | None
    previous_snapshot_id: int | None
    current_snapshot_id: int
    previous_observed_at: str
    current_observed_at: str
    severity: str
    details: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def build_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"market_change:{stamp}:{uuid.uuid4().hex[:8]}"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root() / path
    return path.resolve()


def connect_database(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_change_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            database_path TEXT NOT NULL,
            markets_reviewed INTEGER NOT NULL DEFAULT 0,
            events_written INTEGER NOT NULL DEFAULT 0,
            new_markets INTEGER NOT NULL DEFAULT 0,
            price_moves INTEGER NOT NULL DEFAULT 0,
            liquidity_moves INTEGER NOT NULL DEFAULT 0,
            volume_moves INTEGER NOT NULL DEFAULT 0,
            spread_moves INTEGER NOT NULL DEFAULT 0,
            closed_markets INTEGER NOT NULL DEFAULT 0,
            resolved_markets INTEGER NOT NULL DEFAULT 0,
            reopened_markets INTEGER NOT NULL DEFAULT 0,
            no_previous_snapshot INTEGER NOT NULL DEFAULT 0,
            runtime_seconds REAL NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS market_change_events (
            change_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            condition_id TEXT NOT NULL,
            question TEXT NOT NULL DEFAULT '',
            change_type TEXT NOT NULL,
            direction TEXT NOT NULL DEFAULT '',
            previous_value REAL,
            current_value REAL,
            absolute_change REAL,
            percent_change REAL,
            previous_snapshot_id INTEGER,
            current_snapshot_id INTEGER NOT NULL,
            previous_observed_at TEXT NOT NULL DEFAULT '',
            current_observed_at TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'INFO',
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(run_id, condition_id, change_type),
            FOREIGN KEY(run_id)
                REFERENCES market_change_runs(run_id)
                ON DELETE CASCADE,
            FOREIGN KEY(condition_id)
                REFERENCES market_catalog(condition_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_market_change_events_type_time
            ON market_change_events(change_type, current_observed_at DESC);

        CREATE INDEX IF NOT EXISTS idx_market_change_events_condition_time
            ON market_change_events(condition_id, current_observed_at DESC);

        CREATE INDEX IF NOT EXISTS idx_market_change_events_severity
            ON market_change_events(severity, current_observed_at DESC);
        """
    )
    connection.commit()


def percent_change(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100.0


def severity_for(change_type: str, absolute_change: float | None) -> str:
    value = abs(absolute_change or 0.0)

    if change_type in {"MARKET_RESOLVED", "MARKET_CLOSED", "MARKET_REOPENED"}:
        return "HIGH"
    if change_type == "NEW_MARKET":
        return "MEDIUM"
    if change_type == "PRICE_MOVE":
        if value >= 0.20:
            return "CRITICAL"
        if value >= 0.10:
            return "HIGH"
        if value >= 0.05:
            return "MEDIUM"
    if change_type in {"LIQUIDITY_MOVE", "VOLUME_MOVE"}:
        if value >= 100000:
            return "HIGH"
        if value >= 25000:
            return "MEDIUM"
    if change_type == "SPREAD_MOVE":
        if value >= 0.05:
            return "HIGH"
        if value >= 0.02:
            return "MEDIUM"
    return "INFO"


def make_numeric_event(
    row: sqlite3.Row,
    change_type: str,
    previous_value: float | None,
    current_value: float | None,
    label: str,
) -> ChangeEvent:
    absolute = None
    direction = ""
    if previous_value is not None and current_value is not None:
        absolute = current_value - previous_value
        direction = "UP" if absolute > 0 else "DOWN" if absolute < 0 else "FLAT"

    pct = percent_change(previous_value, current_value)
    details = (
        f"{label} changed from {previous_value} to {current_value}; "
        f"absolute_change={absolute}; percent_change={pct}"
    )

    return ChangeEvent(
        condition_id=row["condition_id"],
        question=row["question"],
        change_type=change_type,
        direction=direction,
        previous_value=previous_value,
        current_value=current_value,
        absolute_change=absolute,
        percent_change=pct,
        previous_snapshot_id=row["previous_snapshot_id"],
        current_snapshot_id=row["current_snapshot_id"],
        previous_observed_at=row["previous_observed_at"] or "",
        current_observed_at=row["current_observed_at"],
        severity=severity_for(change_type, absolute),
        details=details,
    )


def make_status_event(
    row: sqlite3.Row,
    change_type: str,
    previous_value: int | None,
    current_value: int,
    details: str,
) -> ChangeEvent:
    absolute = None if previous_value is None else float(current_value - previous_value)
    return ChangeEvent(
        condition_id=row["condition_id"],
        question=row["question"],
        change_type=change_type,
        direction="",
        previous_value=None if previous_value is None else float(previous_value),
        current_value=float(current_value),
        absolute_change=absolute,
        percent_change=None,
        previous_snapshot_id=row["previous_snapshot_id"],
        current_snapshot_id=row["current_snapshot_id"],
        previous_observed_at=row["previous_observed_at"] or "",
        current_observed_at=row["current_observed_at"],
        severity=severity_for(change_type, absolute),
        details=details,
    )


def latest_snapshot_pairs(connection: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    return connection.execute(
        """
        WITH ranked AS (
            SELECT
                ms.*,
                ROW_NUMBER() OVER (
                    PARTITION BY ms.condition_id
                    ORDER BY ms.observed_at DESC, ms.snapshot_id DESC
                ) AS snapshot_rank
            FROM market_snapshots AS ms
        ),
        current_snapshot AS (
            SELECT * FROM ranked WHERE snapshot_rank = 1
        ),
        previous_snapshot AS (
            SELECT * FROM ranked WHERE snapshot_rank = 2
        )
        SELECT
            c.condition_id,
            mc.question,
            c.snapshot_id AS current_snapshot_id,
            p.snapshot_id AS previous_snapshot_id,
            c.observed_at AS current_observed_at,
            p.observed_at AS previous_observed_at,

            c.active AS current_active,
            p.active AS previous_active,
            c.closed AS current_closed,
            p.closed AS previous_closed,
            c.resolved AS current_resolved,
            p.resolved AS previous_resolved,
            c.accepting_orders AS current_accepting_orders,
            p.accepting_orders AS previous_accepting_orders,

            c.yes_price AS current_yes_price,
            p.yes_price AS previous_yes_price,
            c.liquidity AS current_liquidity,
            p.liquidity AS previous_liquidity,
            c.volume AS current_volume,
            p.volume AS previous_volume,
            c.spread AS current_spread,
            p.spread AS previous_spread
        FROM current_snapshot AS c
        LEFT JOIN previous_snapshot AS p
            ON p.condition_id = c.condition_id
        JOIN market_catalog AS mc
            ON mc.condition_id = c.condition_id
        ORDER BY c.observed_at DESC, c.condition_id
        """
    )


def detect_changes(row: sqlite3.Row, config: Config) -> list[ChangeEvent]:
    events: list[ChangeEvent] = []

    if row["previous_snapshot_id"] is None:
        events.append(
            make_status_event(
                row,
                "NEW_MARKET",
                None,
                1,
                "No earlier snapshot exists for this market.",
            )
        )
        return events

    previous_closed = int(row["previous_closed"])
    current_closed = int(row["current_closed"])
    previous_resolved = int(row["previous_resolved"])
    current_resolved = int(row["current_resolved"])
    previous_active = int(row["previous_active"])
    current_active = int(row["current_active"])

    if previous_closed == 0 and current_closed == 1:
        events.append(
            make_status_event(
                row,
                "MARKET_CLOSED",
                previous_closed,
                current_closed,
                "Market changed from open to closed.",
            )
        )

    if previous_resolved == 0 and current_resolved == 1:
        events.append(
            make_status_event(
                row,
                "MARKET_RESOLVED",
                previous_resolved,
                current_resolved,
                "Market changed from unresolved to resolved.",
            )
        )

    if previous_active == 0 and current_active == 1:
        events.append(
            make_status_event(
                row,
                "MARKET_REOPENED",
                previous_active,
                current_active,
                "Market changed from inactive to active.",
            )
        )

    previous_price = row["previous_yes_price"]
    current_price = row["current_yes_price"]
    if previous_price is not None and current_price is not None:
        if abs(current_price - previous_price) >= config.min_price_change:
            events.append(
                make_numeric_event(
                    row,
                    "PRICE_MOVE",
                    previous_price,
                    current_price,
                    "YES price",
                )
            )

    previous_liquidity = row["previous_liquidity"]
    current_liquidity = row["current_liquidity"]
    if (
        previous_liquidity is not None
        and current_liquidity is not None
        and abs(current_liquidity - previous_liquidity)
        >= config.min_liquidity_change
    ):
        events.append(
            make_numeric_event(
                row,
                "LIQUIDITY_MOVE",
                previous_liquidity,
                current_liquidity,
                "Liquidity",
            )
        )

    previous_volume = row["previous_volume"]
    current_volume = row["current_volume"]
    if (
        previous_volume is not None
        and current_volume is not None
        and abs(current_volume - previous_volume) >= config.min_volume_change
    ):
        events.append(
            make_numeric_event(
                row,
                "VOLUME_MOVE",
                previous_volume,
                current_volume,
                "Cumulative volume",
            )
        )

    previous_spread = row["previous_spread"]
    current_spread = row["current_spread"]
    if previous_spread is not None and current_spread is not None:
        if abs(current_spread - previous_spread) >= config.min_spread_change:
            events.append(
                make_numeric_event(
                    row,
                    "SPREAD_MOVE",
                    previous_spread,
                    current_spread,
                    "Spread",
                )
            )

    return events


def insert_run_start(
    connection: sqlite3.Connection,
    config: Config,
    stats: Stats,
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO market_change_runs (
            run_id,
            started_at,
            status,
            engine_version,
            database_path,
            created_at,
            updated_at
        )
        VALUES (?, ?, 'RUNNING', ?, ?, ?, ?)
        """,
        (
            stats.run_id,
            stats.started_at,
            ENGINE_VERSION,
            str(config.database_path),
            now,
            now,
        ),
    )
    connection.commit()


def insert_event(
    connection: sqlite3.Connection,
    run_id: str,
    event: ChangeEvent,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO market_change_events (
            run_id,
            condition_id,
            question,
            change_type,
            direction,
            previous_value,
            current_value,
            absolute_change,
            percent_change,
            previous_snapshot_id,
            current_snapshot_id,
            previous_observed_at,
            current_observed_at,
            severity,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            event.condition_id,
            event.question,
            event.change_type,
            event.direction,
            event.previous_value,
            event.current_value,
            event.absolute_change,
            event.percent_change,
            event.previous_snapshot_id,
            event.current_snapshot_id,
            event.previous_observed_at,
            event.current_observed_at,
            event.severity,
            event.details,
            utc_now(),
        ),
    )


def finalize_run(
    connection: sqlite3.Connection,
    stats: Stats,
    status: str,
    runtime_seconds: float,
    error_message: str,
) -> None:
    connection.execute(
        """
        UPDATE market_change_runs
        SET
            completed_at = ?,
            status = ?,
            markets_reviewed = ?,
            events_written = ?,
            new_markets = ?,
            price_moves = ?,
            liquidity_moves = ?,
            volume_moves = ?,
            spread_moves = ?,
            closed_markets = ?,
            resolved_markets = ?,
            reopened_markets = ?,
            no_previous_snapshot = ?,
            runtime_seconds = ?,
            error_message = ?,
            updated_at = ?
        WHERE run_id = ?
        """,
        (
            utc_now(),
            status,
            stats.markets_reviewed,
            stats.events_written,
            stats.new_markets,
            stats.price_moves,
            stats.liquidity_moves,
            stats.volume_moves,
            stats.spread_moves,
            stats.closed_markets,
            stats.resolved_markets,
            stats.reopened_markets,
            stats.no_previous_snapshot,
            runtime_seconds,
            error_message,
            utc_now(),
            stats.run_id,
        ),
    )
    connection.commit()


def print_header(title: str, width: int = 118) -> None:
    print("=" * width)
    print(title)
    print("=" * width)


def print_events(events: list[ChangeEvent], limit: int) -> None:
    if not events or limit <= 0:
        return

    print()
    print_header("TOP MARKET CHANGES")

    priority = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "INFO": 1}
    ordered = sorted(
        events,
        key=lambda item: (
            priority.get(item.severity, 0),
            abs(item.absolute_change or 0.0),
        ),
        reverse=True,
    )

    for index, event in enumerate(ordered[:limit], start=1):
        change = (
            "-"
            if event.absolute_change is None
            else f"{event.absolute_change:+,.4f}"
        )
        print(
            f"{index:>3}. {event.severity:<8} "
            f"{event.change_type:<16} "
            f"{event.direction:<4} "
            f"Î”={change:<14} | "
            f"{event.question[:72]}"
        )


def print_summary(
    config: Config,
    stats: Stats,
    runtime_seconds: float,
    status: str,
) -> None:
    print()
    print_header("MARKET CHANGE ENGINE HEALTH SUMMARY")
    print(f"Status:                     {status}")
    print(f"Run ID:                     {stats.run_id}")
    print(f"Database:                   {config.database_path}")
    print(f"Markets reviewed:           {stats.markets_reviewed:,}")
    print(f"Events written:             {stats.events_written:,}")
    print(f"New markets:                {stats.new_markets:,}")
    print(f"Price moves:                {stats.price_moves:,}")
    print(f"Liquidity moves:            {stats.liquidity_moves:,}")
    print(f"Volume moves:               {stats.volume_moves:,}")
    print(f"Spread moves:               {stats.spread_moves:,}")
    print(f"Closed markets:             {stats.closed_markets:,}")
    print(f"Resolved markets:           {stats.resolved_markets:,}")
    print(f"Reopened markets:           {stats.reopened_markets:,}")
    print(f"No previous snapshot:       {stats.no_previous_snapshot:,}")
    print(f"Runtime:                    {runtime_seconds:.2f}s")
    print_header("MARKET CHANGE ENGINE COMPLETE")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the latest two market snapshots and store structured "
            "Polymarket market-change events."
        )
    )
    parser.add_argument(
        "--database",
        default=str(DEFAULT_DATABASE_PATH),
        help="SQLite database path.",
    )
    parser.add_argument(
        "--min-price-change",
        type=float,
        default=0.01,
        help="Minimum absolute YES-price movement. Default: 0.01.",
    )
    parser.add_argument(
        "--min-liquidity-change",
        type=float,
        default=5000.0,
        help="Minimum absolute liquidity change. Default: 5000.",
    )
    parser.add_argument(
        "--min-volume-change",
        type=float,
        default=5000.0,
        help="Minimum absolute cumulative-volume change. Default: 5000.",
    )
    parser.add_argument(
        "--min-spread-change",
        type=float,
        default=0.01,
        help="Minimum absolute spread change. Default: 0.01.",
    )
    parser.add_argument(
        "--display-limit",
        type=int,
        default=25,
        help="Maximum change events to display.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    for name in (
        "min_price_change",
        "min_liquidity_change",
        "min_volume_change",
        "min_spread_change",
    ):
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} cannot be negative.")

    if args.display_limit < 0:
        parser.error("--display-limit cannot be negative.")

    config = Config(
        database_path=resolve_path(args.database),
        min_price_change=args.min_price_change,
        min_liquidity_change=args.min_liquidity_change,
        min_volume_change=args.min_volume_change,
        min_spread_change=args.min_spread_change,
        display_limit=args.display_limit,
    )
    stats = Stats(
        run_id=build_run_id(),
        started_at=utc_now(),
    )

    print_header(f"{ENGINE_NAME.upper()} v{ENGINE_VERSION}")
    print(f"Run ID:                     {stats.run_id}")
    print(f"Database:                   {config.database_path}")
    print(f"Minimum price change:       {config.min_price_change}")
    print(f"Minimum liquidity change:   {config.min_liquidity_change:,.2f}")
    print(f"Minimum volume change:      {config.min_volume_change:,.2f}")
    print(f"Minimum spread change:      {config.min_spread_change}")

    connection = connect_database(config.database_path)
    ensure_schema(connection)
    insert_run_start(connection, config, stats)

    started_clock = time.perf_counter()
    status = "SUCCESS"
    error_message = ""
    all_events: list[ChangeEvent] = []

    try:
        snapshot_count = connection.execute(
            "SELECT COUNT(*) FROM market_snapshots"
        ).fetchone()[0]
        if snapshot_count == 0:
            status = "NO_DATA"
            error_message = "No market snapshots are available."

        else:
            for row in latest_snapshot_pairs(connection):
                stats.markets_reviewed += 1
                changes = detect_changes(row, config)

                if row["previous_snapshot_id"] is None:
                    stats.no_previous_snapshot += 1

                for event in changes:
                    insert_event(connection, stats.run_id, event)
                    stats.events_written += 1
                    all_events.append(event)

                    if event.change_type == "NEW_MARKET":
                        stats.new_markets += 1
                    elif event.change_type == "PRICE_MOVE":
                        stats.price_moves += 1
                    elif event.change_type == "LIQUIDITY_MOVE":
                        stats.liquidity_moves += 1
                    elif event.change_type == "VOLUME_MOVE":
                        stats.volume_moves += 1
                    elif event.change_type == "SPREAD_MOVE":
                        stats.spread_moves += 1
                    elif event.change_type == "MARKET_CLOSED":
                        stats.closed_markets += 1
                    elif event.change_type == "MARKET_RESOLVED":
                        stats.resolved_markets += 1
                    elif event.change_type == "MARKET_REOPENED":
                        stats.reopened_markets += 1

            connection.commit()

    except KeyboardInterrupt:
        status = "INTERRUPTED"
        error_message = "Engine interrupted by user."
    except Exception as error:
        status = "FAILED"
        error_message = str(error)
        print(f"Market change engine failed: {error_message}", file=sys.stderr)
    finally:
        runtime_seconds = time.perf_counter() - started_clock
        try:
            finalize_run(
                connection,
                stats,
                status,
                runtime_seconds,
                error_message,
            )
        finally:
            connection.close()

    print_events(all_events, config.display_limit)
    print_summary(config, stats, runtime_seconds, status)

    if error_message:
        print(f"Message:                    {error_message}")

    return 0 if status in {"SUCCESS", "NO_DATA"} else 1


if __name__ == "__main__":
    raise SystemExit(main())