from __future__ import annotations

import argparse
import math
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENGINE_NAME = "Consensus Intelligence Engine"
ENGINE_VERSION = "1.0.1"
DEFAULT_DATABASE_PATH = Path("database/polymarket.db")


@dataclass(slots=True)
class Config:
    database_path: Path
    minimum_wallets: int
    minimum_elite_wallets: int
    minimum_wallet_confidence: float
    minimum_market_health: float
    maximum_risk: float
    display_limit: int


@dataclass(slots=True)
class Stats:
    run_id: str
    started_at: str
    markets_reviewed: int = 0
    eligible_markets: int = 0
    consensus_inserted: int = 0
    consensus_updated: int = 0
    signals_created: int = 0
    passes: int = 0
    errors: int = 0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def build_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"consensus:{stamp}:{uuid.uuid4().hex[:8]}"


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


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def ensure_source_tables(connection: sqlite3.Connection) -> None:
    required = ["market_catalog", "market_features_current"]
    missing = [name for name in required if not table_exists(connection, name)]
    if missing:
        raise RuntimeError(
            "Missing required source table(s): " + ", ".join(missing)
        )


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS consensus_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            database_path TEXT NOT NULL,
            markets_reviewed INTEGER NOT NULL DEFAULT 0,
            eligible_markets INTEGER NOT NULL DEFAULT 0,
            consensus_inserted INTEGER NOT NULL DEFAULT 0,
            consensus_updated INTEGER NOT NULL DEFAULT 0,
            signals_created INTEGER NOT NULL DEFAULT 0,
            passes INTEGER NOT NULL DEFAULT 0,
            errors INTEGER NOT NULL DEFAULT 0,
            runtime_seconds REAL NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS consensus_intelligence_current (
            condition_id TEXT PRIMARY KEY,
            question TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            sport TEXT NOT NULL DEFAULT '',
            league TEXT NOT NULL DEFAULT '',

            active INTEGER NOT NULL DEFAULT 0,
            closed INTEGER NOT NULL DEFAULT 0,
            resolved INTEGER NOT NULL DEFAULT 0,

            yes_price REAL,
            no_price REAL,
            liquidity REAL,
            volume REAL,
            spread REAL,

            wallet_count INTEGER NOT NULL DEFAULT 0,
            elite_wallet_count INTEGER NOT NULL DEFAULT 0,
            average_wallet_roi REAL,
            wallet_confidence_score REAL NOT NULL DEFAULT 0,

            market_health_score REAL NOT NULL DEFAULT 0,
            risk_score REAL NOT NULL DEFAULT 100,
            price_momentum_score REAL NOT NULL DEFAULT 50,
            opportunity_base_score REAL NOT NULL DEFAULT 0,

            consensus_side TEXT NOT NULL DEFAULT 'PASS',
            agreement_score REAL NOT NULL DEFAULT 0,
            conviction_score REAL NOT NULL DEFAULT 0,
            smart_money_density REAL NOT NULL DEFAULT 0,
            consensus_momentum REAL NOT NULL DEFAULT 50,
            final_consensus_score REAL NOT NULL DEFAULT 0,
            confidence_grade TEXT NOT NULL DEFAULT 'D',
            signal_status TEXT NOT NULL DEFAULT 'PASS',
            signal_reason TEXT NOT NULL DEFAULT '',

            source_feature_calculated_at TEXT NOT NULL DEFAULT '',
            source_run_id TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY(condition_id)
                REFERENCES market_catalog(condition_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS consensus_intelligence_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_id TEXT NOT NULL,
            consensus_side TEXT NOT NULL,
            agreement_score REAL NOT NULL,
            conviction_score REAL NOT NULL,
            smart_money_density REAL NOT NULL,
            consensus_momentum REAL NOT NULL,
            final_consensus_score REAL NOT NULL,
            confidence_grade TEXT NOT NULL,
            signal_status TEXT NOT NULL,
            wallet_count INTEGER NOT NULL,
            elite_wallet_count INTEGER NOT NULL,
            yes_price REAL,
            source_run_id TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(condition_id, source_run_id),
            FOREIGN KEY(condition_id)
                REFERENCES market_catalog(condition_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_consensus_current_score
            ON consensus_intelligence_current(
                signal_status,
                final_consensus_score DESC,
                risk_score ASC
            );

        CREATE INDEX IF NOT EXISTS idx_consensus_history_market_time
            ON consensus_intelligence_history(
                condition_id,
                calculated_at DESC
            );
        """
    )
    connection.commit()


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def grade(score: float) -> str:
    if score >= 92:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 78:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C+"
    if score >= 50:
        return "C"
    return "D"


def consensus_side(yes_price: float | None, momentum: float) -> str:
    if yes_price is None:
        return "PASS"

    if momentum >= 55:
        return "YES"
    if momentum <= 45:
        return "NO"

    if yes_price >= 0.65:
        return "YES"
    if yes_price <= 0.35:
        return "NO"
    return "PASS"


def calculate_consensus(row: sqlite3.Row, config: Config) -> dict[str, Any]:
    wallet_count = safe_int(row["wallet_count"])
    elite_wallet_count = safe_int(row["elite_wallet_count"])
    wallet_confidence = safe_float(row["wallet_confidence_score"])
    health = safe_float(row["market_health_score"])
    risk = safe_float(row["risk_score"], 100.0)
    momentum = safe_float(row["price_momentum_score"], 50.0)
    opportunity = safe_float(row["opportunity_base_score"])
    yes_price_raw = row["yes_price"]
    yes_price = None if yes_price_raw is None else safe_float(yes_price_raw)

    agreement = clamp(wallet_count / max(config.minimum_wallets * 3, 1) * 100.0)
    elite_component = clamp(
        elite_wallet_count / max(config.minimum_elite_wallets * 3, 1) * 100.0
    )
    density = (
        clamp(elite_wallet_count / wallet_count * 100.0)
        if wallet_count > 0
        else 0.0
    )

    conviction = clamp(
        wallet_confidence * 0.45
        + agreement * 0.25
        + elite_component * 0.20
        + density * 0.10
    )

    consensus_momentum = clamp(
        50.0 + (momentum - 50.0) * 0.70
    )

    final_score = clamp(
        conviction * 0.40
        + health * 0.20
        + consensus_momentum * 0.15
        + opportunity * 0.15
        + (100.0 - risk) * 0.10
    )

    side = consensus_side(yes_price, momentum)

    eligible = (
        wallet_count >= config.minimum_wallets
        and elite_wallet_count >= config.minimum_elite_wallets
        and wallet_confidence >= config.minimum_wallet_confidence
        and health >= config.minimum_market_health
        and risk <= config.maximum_risk
        and side != "PASS"
    )

    if eligible and final_score >= 85:
        status = "ELITE"
    elif eligible and final_score >= 75:
        status = "HIGH_CONVICTION"
    elif eligible and final_score >= 65:
        status = "WATCH"
    else:
        status = "PASS"

    reasons: list[str] = []
    if wallet_count < config.minimum_wallets:
        reasons.append("insufficient_wallets")
    if elite_wallet_count < config.minimum_elite_wallets:
        reasons.append("insufficient_elite_wallets")
    if wallet_confidence < config.minimum_wallet_confidence:
        reasons.append("low_wallet_confidence")
    if health < config.minimum_market_health:
        reasons.append("low_market_health")
    if risk > config.maximum_risk:
        reasons.append("risk_too_high")
    if side == "PASS":
        reasons.append("no_clear_side")
    if not reasons:
        reasons.append("qualified")

    return {
        "condition_id": row["condition_id"],
        "question": row["question"] or "",
        "category": row["category"] or "",
        "sport": row["sport"] or "",
        "league": row["league"] or "",
        "active": safe_int(row["active"]),
        "closed": safe_int(row["closed"]),
        "resolved": safe_int(row["resolved"]),
        "yes_price": yes_price,
        "no_price": row["no_price"],
        "liquidity": row["liquidity"],
        "volume": row["volume"],
        "spread": row["spread"],
        "wallet_count": wallet_count,
        "elite_wallet_count": elite_wallet_count,
        "average_wallet_roi": row["average_wallet_roi"],
        "wallet_confidence_score": wallet_confidence,
        "market_health_score": health,
        "risk_score": risk,
        "price_momentum_score": momentum,
        "opportunity_base_score": opportunity,
        "consensus_side": side,
        "agreement_score": agreement,
        "conviction_score": conviction,
        "smart_money_density": density,
        "consensus_momentum": consensus_momentum,
        "final_consensus_score": final_score,
        "confidence_grade": grade(final_score),
        "signal_status": status,
        "signal_reason": ",".join(reasons),
        "source_feature_calculated_at": row["calculated_at"] or "",
    }


def start_run(
    connection: sqlite3.Connection,
    config: Config,
    stats: Stats,
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO consensus_intelligence_runs (
            run_id, started_at, status, engine_version,
            database_path, created_at, updated_at
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


def upsert_current(
    connection: sqlite3.Connection,
    record: dict[str, Any],
    run_id: str,
) -> bool:
    exists = connection.execute(
        """
        SELECT 1
        FROM consensus_intelligence_current
        WHERE condition_id = ?
        """,
        (record["condition_id"],),
    ).fetchone() is not None

    now = utc_now()
    data = dict(record)
    data["source_run_id"] = run_id
    data["calculated_at"] = now
    data["created_at"] = now
    data["updated_at"] = now

    columns = list(data)
    updates = [
        column
        for column in columns
        if column not in {"condition_id", "created_at"}
    ]

    connection.execute(
        f"""
        INSERT INTO consensus_intelligence_current (
            {", ".join(f'"{column}"' for column in columns)}
        )
        VALUES ({", ".join("?" for _ in columns)})
        ON CONFLICT(condition_id) DO UPDATE SET
            {", ".join(f'"{column}"=excluded."{column}"' for column in updates)}
        """,
        [data[column] for column in columns],
    )
    return not exists


def insert_history(
    connection: sqlite3.Connection,
    record: dict[str, Any],
    run_id: str,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO consensus_intelligence_history (
            condition_id,
            consensus_side,
            agreement_score,
            conviction_score,
            smart_money_density,
            consensus_momentum,
            final_consensus_score,
            confidence_grade,
            signal_status,
            wallet_count,
            elite_wallet_count,
            yes_price,
            source_run_id,
            calculated_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["condition_id"],
            record["consensus_side"],
            record["agreement_score"],
            record["conviction_score"],
            record["smart_money_density"],
            record["consensus_momentum"],
            record["final_consensus_score"],
            record["confidence_grade"],
            record["signal_status"],
            record["wallet_count"],
            record["elite_wallet_count"],
            record["yes_price"],
            run_id,
            utc_now(),
            utc_now(),
        ),
    )


def finalize_run(
    connection: sqlite3.Connection,
    stats: Stats,
    status: str,
    runtime: float,
    error_message: str,
) -> None:
    connection.execute(
        """
        UPDATE consensus_intelligence_runs
        SET completed_at=?,
            status=?,
            markets_reviewed=?,
            eligible_markets=?,
            consensus_inserted=?,
            consensus_updated=?,
            signals_created=?,
            passes=?,
            errors=?,
            runtime_seconds=?,
            error_message=?,
            updated_at=?
        WHERE run_id=?
        """,
        (
            utc_now(),
            status,
            stats.markets_reviewed,
            stats.eligible_markets,
            stats.consensus_inserted,
            stats.consensus_updated,
            stats.signals_created,
            stats.passes,
            stats.errors,
            runtime,
            error_message,
            utc_now(),
            stats.run_id,
        ),
    )
    connection.commit()


def print_header(title: str, width: int = 124) -> None:
    print("=" * width)
    print(title)
    print("=" * width)


def print_top_signals(connection: sqlite3.Connection, limit: int) -> None:
    rows = connection.execute(
        """
        SELECT
            signal_status,
            confidence_grade,
            consensus_side,
            final_consensus_score,
            conviction_score,
            wallet_count,
            elite_wallet_count,
            risk_score,
            yes_price,
            question
        FROM consensus_intelligence_current
        WHERE signal_status != 'PASS'
        ORDER BY
            CASE signal_status
                WHEN 'ELITE' THEN 3
                WHEN 'HIGH_CONVICTION' THEN 2
                ELSE 1
            END DESC,
            final_consensus_score DESC,
            risk_score ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    if not rows:
        return

    print()
    print_header("TOP CONSENSUS SIGNALS")
    for index, row in enumerate(rows, start=1):
        print(
            f"{index:>3}. {row['signal_status']:<16} "
            f"{row['confidence_grade']:<3} "
            f"{row['consensus_side']:<3} "
            f"Score={row['final_consensus_score']:>6.2f} "
            f"Conv={row['conviction_score']:>6.2f} "
            f"W={row['wallet_count']:>3} "
            f"E={row['elite_wallet_count']:>3} "
            f"Risk={row['risk_score']:>6.2f} | "
            f"{str(row['question'])[:60]}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(DEFAULT_DATABASE_PATH))
    parser.add_argument("--minimum-wallets", type=int, default=2)
    parser.add_argument("--minimum-elite-wallets", type=int, default=1)
    parser.add_argument(
        "--minimum-wallet-confidence",
        type=float,
        default=20.0,
    )
    parser.add_argument(
        "--minimum-market-health",
        type=float,
        default=45.0,
    )
    parser.add_argument("--maximum-risk", type=float, default=55.0)
    parser.add_argument("--display-limit", type=int, default=25)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = Config(
        database_path=resolve_path(args.database),
        minimum_wallets=max(args.minimum_wallets, 1),
        minimum_elite_wallets=max(args.minimum_elite_wallets, 0),
        minimum_wallet_confidence=max(args.minimum_wallet_confidence, 0.0),
        minimum_market_health=max(args.minimum_market_health, 0.0),
        maximum_risk=max(args.maximum_risk, 0.0),
        display_limit=max(args.display_limit, 0),
    )
    stats = Stats(build_run_id(), utc_now())

    print_header(f"{ENGINE_NAME.upper()} v{ENGINE_VERSION}")
    print(f"Run ID:                     {stats.run_id}")
    print(f"Database:                   {config.database_path}")
    print(f"Minimum wallets:            {config.minimum_wallets}")
    print(f"Minimum elite wallets:      {config.minimum_elite_wallets}")
    print(f"Minimum wallet confidence:  {config.minimum_wallet_confidence:.2f}")
    print(f"Minimum market health:      {config.minimum_market_health:.2f}")
    print(f"Maximum risk:               {config.maximum_risk:.2f}")

    connection = connect_database(config.database_path)
    ensure_source_tables(connection)
    ensure_schema(connection)
    start_run(connection, config, stats)

    status = "SUCCESS"
    error_message = ""
    started = time.perf_counter()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM market_features_current
            WHERE active=1 AND closed=0 AND resolved=0
            ORDER BY opportunity_base_score DESC
            """
        ).fetchall()

        for row in rows:
            stats.markets_reviewed += 1
            try:
                record = calculate_consensus(row, config)

                if record["signal_status"] == "PASS":
                    stats.passes += 1
                else:
                    stats.eligible_markets += 1
                    stats.signals_created += 1

                if upsert_current(connection, record, stats.run_id):
                    stats.consensus_inserted += 1
                else:
                    stats.consensus_updated += 1

                insert_history(connection, record, stats.run_id)

                if stats.markets_reviewed % 500 == 0:
                    connection.commit()
                    print(
                        f"Processed {stats.markets_reviewed:,} markets | "
                        f"signals={stats.signals_created:,} | "
                        f"passes={stats.passes:,}"
                    )

            except Exception as market_error:
                stats.errors += 1
                print(
                    f"Consensus calculation failed for "
                    f"{row['condition_id']}: {market_error}",
                    file=sys.stderr,
                )

        connection.commit()

    except KeyboardInterrupt:
        status = "INTERRUPTED"
        error_message = "Engine interrupted by user."
    except Exception as error:
        status = "FAILED"
        error_message = str(error)
        print(f"Consensus engine failed: {error_message}", file=sys.stderr)
    finally:
        runtime = time.perf_counter() - started
        try:
            finalize_run(
                connection,
                stats,
                status,
                runtime,
                error_message,
            )
            print_top_signals(connection, config.display_limit)
        finally:
            connection.close()

    print()
    print_header("CONSENSUS INTELLIGENCE HEALTH SUMMARY")
    print(f"Status:                     {status}")
    print(f"Markets reviewed:           {stats.markets_reviewed:,}")
    print(f"Eligible markets:           {stats.eligible_markets:,}")
    print(f"Consensus inserted:         {stats.consensus_inserted:,}")
    print(f"Consensus updated:          {stats.consensus_updated:,}")
    print(f"Signals created:            {stats.signals_created:,}")
    print(f"Passes:                     {stats.passes:,}")
    print(f"Errors:                     {stats.errors:,}")
    print(f"Runtime:                    {runtime:.2f}s")
    print_header("CONSENSUS INTELLIGENCE COMPLETE")

    if error_message:
        print(f"Message:                    {error_message}")

    return 0 if status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())