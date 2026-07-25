from __future__ import annotations

import argparse
import math
import sqlite3
import statistics
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_NAME = "Feature Engine"
ENGINE_VERSION = "1.0.0"
FEATURE_VERSION = "1.0.0"
DEFAULT_DATABASE_PATH = Path("database/polymarket.db")


@dataclass(slots=True)
class Config:
    database_path: Path
    history_limit: int
    minimum_snapshot_count: int
    display_limit: int
    write_history: bool


@dataclass(slots=True)
class Stats:
    run_id: str
    started_at: str
    markets_reviewed: int = 0
    features_inserted: int = 0
    features_updated: int = 0
    history_rows_written: int = 0
    insufficient_history: int = 0
    wallet_features_available: int = 0
    wallet_features_missing: int = 0
    errors: int = 0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def build_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"feature_engine:{stamp}:{uuid.uuid4().hex[:8]}"


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


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    if not table_exists(connection, table_name):
        return set()
    return {row["name"] for row in connection.execute(f'PRAGMA table_info("{table_name}")')}


def first_existing(candidates: list[str], available: set[str]) -> str | None:
    return next((candidate for candidate in candidates if candidate in available), None)


def ensure_source_tables(connection: sqlite3.Connection) -> None:
    missing = [name for name in ("market_catalog", "market_snapshots") if not table_exists(connection, name)]
    if missing:
        raise RuntimeError("Missing required source table(s): " + ", ".join(missing))


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS feature_engine_runs (
        run_id TEXT PRIMARY KEY,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        engine_version TEXT NOT NULL,
        feature_version TEXT NOT NULL,
        database_path TEXT NOT NULL,
        markets_reviewed INTEGER NOT NULL DEFAULT 0,
        features_inserted INTEGER NOT NULL DEFAULT 0,
        features_updated INTEGER NOT NULL DEFAULT 0,
        history_rows_written INTEGER NOT NULL DEFAULT 0,
        insufficient_history INTEGER NOT NULL DEFAULT 0,
        wallet_features_available INTEGER NOT NULL DEFAULT 0,
        wallet_features_missing INTEGER NOT NULL DEFAULT 0,
        errors INTEGER NOT NULL DEFAULT 0,
        runtime_seconds REAL NOT NULL DEFAULT 0,
        error_message TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS market_features_current (
        condition_id TEXT PRIMARY KEY,
        feature_version TEXT NOT NULL,
        calculated_at TEXT NOT NULL,
        question TEXT NOT NULL DEFAULT '',
        event_id TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '',
        sport TEXT NOT NULL DEFAULT '',
        league TEXT NOT NULL DEFAULT '',
        active INTEGER NOT NULL DEFAULT 0,
        closed INTEGER NOT NULL DEFAULT 0,
        resolved INTEGER NOT NULL DEFAULT 0,
        accepting_orders INTEGER NOT NULL DEFAULT 0,
        yes_price REAL,
        no_price REAL,
        liquidity REAL,
        volume REAL,
        spread REAL,
        snapshot_count INTEGER NOT NULL DEFAULT 0,
        first_observed_at TEXT NOT NULL DEFAULT '',
        latest_observed_at TEXT NOT NULL DEFAULT '',
        market_age_hours REAL,
        price_change_latest REAL,
        price_change_1h REAL,
        price_change_24h REAL,
        price_velocity_per_hour REAL,
        price_volatility REAL,
        price_momentum_score REAL NOT NULL DEFAULT 50,
        liquidity_change_latest REAL,
        liquidity_change_24h REAL,
        liquidity_trend_score REAL NOT NULL DEFAULT 50,
        volume_change_latest REAL,
        volume_change_24h REAL,
        volume_velocity_per_hour REAL,
        volume_trend_score REAL NOT NULL DEFAULT 50,
        spread_change_latest REAL,
        spread_change_24h REAL,
        spread_quality_score REAL NOT NULL DEFAULT 50,
        change_event_count INTEGER NOT NULL DEFAULT 0,
        price_event_count INTEGER NOT NULL DEFAULT 0,
        liquidity_event_count INTEGER NOT NULL DEFAULT 0,
        volume_event_count INTEGER NOT NULL DEFAULT 0,
        spread_event_count INTEGER NOT NULL DEFAULT 0,
        status_event_count INTEGER NOT NULL DEFAULT 0,
        wallet_count INTEGER NOT NULL DEFAULT 0,
        elite_wallet_count INTEGER NOT NULL DEFAULT 0,
        average_wallet_roi REAL,
        wallet_confidence_score REAL NOT NULL DEFAULT 0,
        market_health_score REAL NOT NULL DEFAULT 0,
        risk_score REAL NOT NULL DEFAULT 100,
        opportunity_base_score REAL NOT NULL DEFAULT 0,
        confidence_grade TEXT NOT NULL DEFAULT 'D',
        source_run_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(condition_id) REFERENCES market_catalog(condition_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS market_feature_history (
        feature_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        condition_id TEXT NOT NULL,
        feature_version TEXT NOT NULL,
        calculated_at TEXT NOT NULL,
        yes_price REAL,
        liquidity REAL,
        volume REAL,
        spread REAL,
        price_change_1h REAL,
        price_change_24h REAL,
        price_velocity_per_hour REAL,
        price_volatility REAL,
        price_momentum_score REAL,
        liquidity_change_24h REAL,
        liquidity_trend_score REAL,
        volume_change_24h REAL,
        volume_velocity_per_hour REAL,
        volume_trend_score REAL,
        spread_change_24h REAL,
        spread_quality_score REAL,
        wallet_count INTEGER NOT NULL DEFAULT 0,
        elite_wallet_count INTEGER NOT NULL DEFAULT 0,
        wallet_confidence_score REAL NOT NULL DEFAULT 0,
        market_health_score REAL NOT NULL DEFAULT 0,
        risk_score REAL NOT NULL DEFAULT 100,
        opportunity_base_score REAL NOT NULL DEFAULT 0,
        confidence_grade TEXT NOT NULL DEFAULT 'D',
        source_run_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(condition_id, calculated_at, feature_version),
        FOREIGN KEY(condition_id) REFERENCES market_catalog(condition_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_market_features_opportunity
        ON market_features_current(opportunity_base_score DESC, market_health_score DESC);
    CREATE INDEX IF NOT EXISTS idx_market_features_status
        ON market_features_current(active, closed, resolved, opportunity_base_score DESC);
    CREATE INDEX IF NOT EXISTS idx_market_feature_history_market_time
        ON market_feature_history(condition_id, calculated_at DESC);
    """)
    connection.commit()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) or math.isinf(number) else number


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def hours_between(earlier: Any, later: Any) -> float | None:
    a, b = parse_datetime(earlier), parse_datetime(later)
    return None if a is None or b is None else max((b - a).total_seconds() / 3600.0, 0.0)


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def numeric_change(current: Any, previous: Any) -> float | None:
    a, b = safe_float(current), safe_float(previous)
    return None if a is None or b is None else a - b


def nearest_snapshot(snapshots: list[sqlite3.Row], target_hours: float) -> sqlite3.Row | None:
    if len(snapshots) < 2:
        return None
    latest = parse_datetime(snapshots[0]["observed_at"])
    if latest is None:
        return None
    target = latest.timestamp() - target_hours * 3600
    candidates = []
    for row in snapshots[1:]:
        observed = parse_datetime(row["observed_at"])
        if observed:
            candidates.append((abs(observed.timestamp() - target), row))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def calculate_volatility(snapshots: list[sqlite3.Row]) -> float | None:
    prices = [safe_float(row["yes_price"]) for row in reversed(snapshots)]
    prices = [price for price in prices if price is not None]
    if len(prices) < 2:
        return None
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    return abs(changes[0]) if len(changes) == 1 else statistics.pstdev(changes)


def momentum_score(change_1h: float | None, change_24h: float | None, velocity: float | None) -> float:
    score = 50.0
    if change_1h is not None:
        score += clamp(change_1h / 0.10 * 20, -20, 20)
    if change_24h is not None:
        score += clamp(change_24h / 0.20 * 20, -20, 20)
    if velocity is not None:
        score += clamp(velocity / 0.05 * 10, -10, 10)
    return clamp(score)


def trend_score(latest: float | None, daily: float | None, latest_scale: float, daily_scale: float) -> float:
    score = 50.0
    if latest is not None:
        score += clamp(latest / latest_scale * 20, -20, 20)
    if daily is not None:
        score += clamp(daily / daily_scale * 30, -30, 30)
    return clamp(score)


def spread_quality_score(spread: float | None) -> float:
    if spread is None: return 25.0
    if spread <= 0.005: return 100.0
    if spread <= 0.01: return 90.0
    if spread <= 0.02: return 75.0
    if spread <= 0.05: return 50.0
    if spread <= 0.10: return 25.0
    return 5.0


def confidence_grade(score: float) -> str:
    if score >= 92: return "A+"
    if score >= 85: return "A"
    if score >= 78: return "B+"
    if score >= 70: return "B"
    if score >= 60: return "C+"
    if score >= 50: return "C"
    return "D"


def sql_column(alias: str, actual: str | None, output: str, fallback: str = "NULL") -> str:
    return f"{fallback} AS {output}" if actual is None else f'{alias}."{actual}" AS {output}'


def fetch_markets(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    columns = table_columns(connection, "market_catalog")
    mapping = {
        "condition_id": first_existing(["condition_id", "market_id", "id"], columns),
        "question": first_existing(["question", "title", "market_question"], columns),
        "event_id": first_existing(["event_id", "gamma_event_id", "parent_event_id"], columns),
        "category": first_existing(["category", "category_name", "market_category"], columns),
        "sport": first_existing(["sport", "sport_name"], columns),
        "league": first_existing(["league", "league_name", "competition"], columns),
    }
    if mapping["condition_id"] is None:
        raise RuntimeError("market_catalog has no recognizable condition identifier")
    fields = [
        sql_column("mc", mapping["condition_id"], "condition_id", "''"),
        sql_column("mc", mapping["question"], "question", "''"),
        sql_column("mc", mapping["event_id"], "event_id", "''"),
        sql_column("mc", mapping["category"], "category", "''"),
        sql_column("mc", mapping["sport"], "sport", "''"),
        sql_column("mc", mapping["league"], "league", "''"),
    ]
    return connection.execute(f"SELECT {', '.join(fields)} FROM market_catalog AS mc").fetchall()


def fetch_snapshots(connection: sqlite3.Connection, condition_id: str, limit: int) -> list[sqlite3.Row]:
    columns = table_columns(connection, "market_snapshots")
    mapping = {
        "snapshot_id": first_existing(["snapshot_id", "id"], columns),
        "condition_id": first_existing(["condition_id", "market_id"], columns),
        "observed_at": first_existing(["observed_at", "captured_at", "scanned_at", "created_at"], columns),
        "active": first_existing(["active", "is_active"], columns),
        "closed": first_existing(["closed", "is_closed"], columns),
        "resolved": first_existing(["resolved", "is_resolved"], columns),
        "accepting_orders": first_existing(["accepting_orders", "orders_enabled"], columns),
        "yes_price": first_existing(["yes_price", "current_price", "price"], columns),
        "no_price": first_existing(["no_price"], columns),
        "liquidity": first_existing(["liquidity", "liquidity_num"], columns),
        "volume": first_existing(["volume", "volume_num", "total_volume"], columns),
        "spread": first_existing(["spread"], columns),
    }
    if mapping["condition_id"] is None or mapping["observed_at"] is None:
        raise RuntimeError("market_snapshots lacks a recognizable market ID or timestamp")
    fields = [
        sql_column("ms", mapping["snapshot_id"], "snapshot_id", "ms.rowid"),
        sql_column("ms", mapping["condition_id"], "condition_id", "''"),
        sql_column("ms", mapping["observed_at"], "observed_at", "''"),
        sql_column("ms", mapping["active"], "active", "0"),
        sql_column("ms", mapping["closed"], "closed", "0"),
        sql_column("ms", mapping["resolved"], "resolved", "0"),
        sql_column("ms", mapping["accepting_orders"], "accepting_orders", "0"),
        sql_column("ms", mapping["yes_price"], "yes_price"),
        sql_column("ms", mapping["no_price"], "no_price"),
        sql_column("ms", mapping["liquidity"], "liquidity"),
        sql_column("ms", mapping["volume"], "volume"),
        sql_column("ms", mapping["spread"], "spread"),
    ]
    secondary = f'ms."{mapping["snapshot_id"]}" DESC' if mapping["snapshot_id"] else "ms.rowid DESC"
    query = f'''SELECT {", ".join(fields)}
                FROM market_snapshots AS ms
                WHERE ms."{mapping['condition_id']}"=?
                ORDER BY ms."{mapping['observed_at']}" DESC, {secondary}
                LIMIT ?'''
    return connection.execute(query, (condition_id, limit)).fetchall()


def fetch_change_counts(connection: sqlite3.Connection, condition_id: str) -> dict[str, int]:
    result = {"total": 0, "price": 0, "liquidity": 0, "volume": 0, "spread": 0, "status": 0}
    if not table_exists(connection, "market_change_events"):
        return result
    rows = connection.execute(
        "SELECT change_type, COUNT(*) total FROM market_change_events WHERE condition_id=? GROUP BY change_type",
        (condition_id,),
    )
    for row in rows:
        change_type, count = row["change_type"], safe_int(row["total"])
        result["total"] += count
        key = {
            "PRICE_MOVE": "price", "LIQUIDITY_MOVE": "liquidity", "VOLUME_MOVE": "volume", "SPREAD_MOVE": "spread"
        }.get(change_type)
        if key:
            result[key] += count
        elif change_type in {"NEW_MARKET", "MARKET_CLOSED", "MARKET_RESOLVED", "MARKET_REOPENED"}:
            result["status"] += count
    return result


def fetch_wallet_features(connection: sqlite3.Connection, condition_id: str) -> dict[str, Any]:
    result = {"wallet_count": 0, "elite_wallet_count": 0, "average_wallet_roi": None, "wallet_confidence_score": 0.0}
    selected = None
    for table_name in ("positions", "wallet_positions", "elite_wallet_positions"):
        columns = table_columns(connection, table_name)
        market_column = first_existing(["condition_id", "market_id"], columns)
        if market_column:
            selected = (table_name, market_column, columns)
            break
    if selected is None:
        return result
    table_name, market_column, columns = selected
    wallet_column = first_existing(["wallet", "wallet_address", "address"], columns)
    if wallet_column is None:
        return result
    roi_column = first_existing(["roi", "percent_pnl", "roi_percent"], columns)
    value_column = first_existing(["current_value", "position_value", "value"], columns)
    roi_sql = f'AVG(CAST("{roi_column}" AS REAL))' if roi_column else "NULL"
    elite_sql = (
        f'COUNT(DISTINCT CASE WHEN CAST("{value_column}" AS REAL)>=500 THEN "{wallet_column}" END)'
        if value_column else "0"
    )
    row = connection.execute(
        f'''SELECT COUNT(DISTINCT "{wallet_column}") wallet_count,
                   {elite_sql} elite_wallet_count,
                   {roi_sql} average_wallet_roi
            FROM "{table_name}" WHERE "{market_column}"=?''',
        (condition_id,),
    ).fetchone()
    wallet_count = safe_int(row["wallet_count"])
    elite_count = safe_int(row["elite_wallet_count"])
    roi = safe_float(row["average_wallet_roi"])
    confidence = min(wallet_count * 8, 40) + min(elite_count * 12, 36) + (clamp(roi, 0, 24) if roi is not None else 0)
    return {"wallet_count": wallet_count, "elite_wallet_count": elite_count, "average_wallet_roi": roi, "wallet_confidence_score": clamp(confidence)}


def build_feature(market: sqlite3.Row, snapshots: list[sqlite3.Row], changes: dict[str, int], wallets: dict[str, Any]) -> dict[str, Any]:
    latest = snapshots[0]
    previous = snapshots[1] if len(snapshots) > 1 else None
    one_hour, one_day = nearest_snapshot(snapshots, 1), nearest_snapshot(snapshots, 24)
    yes_price = safe_float(latest["yes_price"])
    no_price = safe_float(latest["no_price"])
    if no_price is None and yes_price is not None:
        no_price = 1 - yes_price
    liquidity, volume, spread = map(safe_float, (latest["liquidity"], latest["volume"], latest["spread"]))
    price_latest = numeric_change(latest["yes_price"], previous["yes_price"]) if previous else None
    price_1h = numeric_change(latest["yes_price"], one_hour["yes_price"]) if one_hour else None
    price_24h = numeric_change(latest["yes_price"], one_day["yes_price"]) if one_day else None
    elapsed = hours_between(previous["observed_at"], latest["observed_at"]) if previous else None
    price_velocity = price_latest / elapsed if price_latest is not None and elapsed and elapsed > 0 else None
    volatility = calculate_volatility(snapshots)
    price_momentum = momentum_score(price_1h, price_24h, price_velocity)
    liq_latest = numeric_change(latest["liquidity"], previous["liquidity"]) if previous else None
    liq_24h = numeric_change(latest["liquidity"], one_day["liquidity"]) if one_day else None
    liq_trend = trend_score(liq_latest, liq_24h, 25000, 100000)
    vol_latest = numeric_change(latest["volume"], previous["volume"]) if previous else None
    vol_24h = numeric_change(latest["volume"], one_day["volume"]) if one_day else None
    vol_velocity = vol_latest / elapsed if vol_latest is not None and elapsed and elapsed > 0 else None
    vol_trend = trend_score(vol_latest, vol_24h, 25000, 100000)
    spread_latest = numeric_change(latest["spread"], previous["spread"]) if previous else None
    spread_24h = numeric_change(latest["spread"], one_day["spread"]) if one_day else None
    spread_quality = spread_quality_score(spread)
    first_observed, latest_observed = snapshots[-1]["observed_at"], latest["observed_at"]
    wallet_conf = safe_float(wallets.get("wallet_confidence_score")) or 0
    history_quality = clamp(len(snapshots) * 5)
    market_health = clamp(
        spread_quality * .30 + clamp((liquidity or 0) / 250000 * 100) * .25 +
        clamp((volume or 0) / 1000000 * 100) * .20 + liq_trend * .10 + vol_trend * .10 + history_quality * .05
    )
    risk = clamp(
        clamp((volatility or 0) / .10 * 100) * .35 + (100 - spread_quality) * .30 +
        (100 if safe_int(latest["closed"]) or safe_int(latest["resolved"]) else 0) * .25 + (100 - history_quality) * .10
    )
    opportunity = clamp(price_momentum * .25 + market_health * .30 + wallet_conf * .30 + (100 - risk) * .15)
    return {
        "condition_id": str(market["condition_id"]), "feature_version": FEATURE_VERSION, "calculated_at": utc_now(),
        "question": str(market["question"] or ""), "event_id": str(market["event_id"] or ""),
        "category": str(market["category"] or ""), "sport": str(market["sport"] or ""), "league": str(market["league"] or ""),
        "active": safe_int(latest["active"]), "closed": safe_int(latest["closed"]), "resolved": safe_int(latest["resolved"]),
        "accepting_orders": safe_int(latest["accepting_orders"]), "yes_price": yes_price, "no_price": no_price,
        "liquidity": liquidity, "volume": volume, "spread": spread, "snapshot_count": len(snapshots),
        "first_observed_at": str(first_observed or ""), "latest_observed_at": str(latest_observed or ""),
        "market_age_hours": hours_between(first_observed, latest_observed), "price_change_latest": price_latest,
        "price_change_1h": price_1h, "price_change_24h": price_24h, "price_velocity_per_hour": price_velocity,
        "price_volatility": volatility, "price_momentum_score": price_momentum, "liquidity_change_latest": liq_latest,
        "liquidity_change_24h": liq_24h, "liquidity_trend_score": liq_trend, "volume_change_latest": vol_latest,
        "volume_change_24h": vol_24h, "volume_velocity_per_hour": vol_velocity, "volume_trend_score": vol_trend,
        "spread_change_latest": spread_latest, "spread_change_24h": spread_24h, "spread_quality_score": spread_quality,
        "change_event_count": changes["total"], "price_event_count": changes["price"], "liquidity_event_count": changes["liquidity"],
        "volume_event_count": changes["volume"], "spread_event_count": changes["spread"], "status_event_count": changes["status"],
        "wallet_count": safe_int(wallets.get("wallet_count")), "elite_wallet_count": safe_int(wallets.get("elite_wallet_count")),
        "average_wallet_roi": safe_float(wallets.get("average_wallet_roi")), "wallet_confidence_score": wallet_conf,
        "market_health_score": market_health, "risk_score": risk, "opportunity_base_score": opportunity,
        "confidence_grade": confidence_grade(opportunity),
    }


def start_run(connection: sqlite3.Connection, config: Config, stats: Stats) -> None:
    now = utc_now()
    connection.execute(
        "INSERT INTO feature_engine_runs(run_id,started_at,status,engine_version,feature_version,database_path,created_at,updated_at) VALUES(?,?,'RUNNING',?,?,?,?,?)",
        (stats.run_id, stats.started_at, ENGINE_VERSION, FEATURE_VERSION, str(config.database_path), now, now),
    )
    connection.commit()


def upsert_current(connection: sqlite3.Connection, feature: dict[str, Any], run_id: str) -> bool:
    exists = connection.execute("SELECT 1 FROM market_features_current WHERE condition_id=?", (feature["condition_id"],)).fetchone() is not None
    now = utc_now()
    data = {**feature, "source_run_id": run_id, "created_at": now, "updated_at": now}
    columns = list(data)
    updates = [column for column in columns if column not in {"condition_id", "created_at"}]
    connection.execute(
        f'''INSERT INTO market_features_current ({", ".join(f'"{c}"' for c in columns)})
            VALUES ({", ".join("?" for _ in columns)})
            ON CONFLICT(condition_id) DO UPDATE SET {", ".join(f'"{c}"=excluded."{c}"' for c in updates)}''',
        [data[column] for column in columns],
    )
    return not exists


def insert_history(connection: sqlite3.Connection, feature: dict[str, Any], run_id: str) -> None:
    columns = [
        "condition_id", "feature_version", "calculated_at", "yes_price", "liquidity", "volume", "spread",
        "price_change_1h", "price_change_24h", "price_velocity_per_hour", "price_volatility", "price_momentum_score",
        "liquidity_change_24h", "liquidity_trend_score", "volume_change_24h", "volume_velocity_per_hour",
        "volume_trend_score", "spread_change_24h", "spread_quality_score", "wallet_count", "elite_wallet_count",
        "wallet_confidence_score", "market_health_score", "risk_score", "opportunity_base_score", "confidence_grade",
    ]
    values = [feature[column] for column in columns] + [run_id, utc_now()]
    columns += ["source_run_id", "created_at"]
    connection.execute(
        f'INSERT OR IGNORE INTO market_feature_history ({", ".join(f"\"{c}\"" for c in columns)}) VALUES ({", ".join("?" for _ in columns)})',
        values,
    )


def finalize_run(connection: sqlite3.Connection, stats: Stats, status: str, runtime: float, error_message: str) -> None:
    connection.execute(
        '''UPDATE feature_engine_runs SET completed_at=?,status=?,markets_reviewed=?,features_inserted=?,features_updated=?,
           history_rows_written=?,insufficient_history=?,wallet_features_available=?,wallet_features_missing=?,errors=?,
           runtime_seconds=?,error_message=?,updated_at=? WHERE run_id=?''',
        (utc_now(), status, stats.markets_reviewed, stats.features_inserted, stats.features_updated, stats.history_rows_written,
         stats.insufficient_history, stats.wallet_features_available, stats.wallet_features_missing, stats.errors,
         runtime, error_message, utc_now(), stats.run_id),
    )
    connection.commit()


def print_header(title: str, width: int = 122) -> None:
    print("=" * width); print(title); print("=" * width)


def print_top_features(connection: sqlite3.Connection, limit: int) -> None:
    if limit <= 0: return
    rows = connection.execute(
        '''SELECT confidence_grade,opportunity_base_score,market_health_score,risk_score,wallet_confidence_score,yes_price,question
           FROM market_features_current WHERE active=1 AND closed=0 AND resolved=0
           ORDER BY opportunity_base_score DESC,market_health_score DESC,risk_score ASC LIMIT ?''',
        (limit,),
    ).fetchall()
    if not rows: return
    print(); print_header("TOP FEATURE PROFILES")
    for index, row in enumerate(rows, 1):
        yes = "-" if row["yes_price"] is None else f'{row["yes_price"]:.3f}'
        print(f'{index:>3}. {row["confidence_grade"]:<3} Opportunity={row["opportunity_base_score"]:>6.2f} '
              f'Health={row["market_health_score"]:>6.2f} Risk={row["risk_score"]:>6.2f} '
              f'Wallet={row["wallet_confidence_score"]:>6.2f} YES={yes:>5} | {str(row["question"])[:67]}')


def print_summary(config: Config, stats: Stats, runtime: float, status: str) -> None:
    print(); print_header("FEATURE ENGINE HEALTH SUMMARY")
    print(f"Status:                     {status}")
    print(f"Run ID:                     {stats.run_id}")
    print(f"Database:                   {config.database_path}")
    print(f"Markets reviewed:           {stats.markets_reviewed:,}")
    print(f"Features inserted:          {stats.features_inserted:,}")
    print(f"Features updated:           {stats.features_updated:,}")
    print(f"History rows written:       {stats.history_rows_written:,}")
    print(f"Insufficient history:       {stats.insufficient_history:,}")
    print(f"Wallet features available:  {stats.wallet_features_available:,}")
    print(f"Wallet features missing:    {stats.wallet_features_missing:,}")
    print(f"Errors:                     {stats.errors:,}")
    print(f"Runtime:                    {runtime:.2f}s")
    print_header("FEATURE ENGINE COMPLETE")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build canonical Polymarket market features")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE_PATH))
    parser.add_argument("--history-limit", type=int, default=100)
    parser.add_argument("--minimum-snapshot-count", type=int, default=2)
    parser.add_argument("--display-limit", type=int, default=25)
    parser.add_argument("--no-history", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.history_limit < 2: raise SystemExit("--history-limit must be at least 2")
    if args.minimum_snapshot_count < 1: raise SystemExit("--minimum-snapshot-count must be at least 1")
    if args.display_limit < 0: raise SystemExit("--display-limit cannot be negative")
    config = Config(resolve_path(args.database), args.history_limit, args.minimum_snapshot_count, args.display_limit, not args.no_history)
    stats = Stats(build_run_id(), utc_now())
    print_header(f"{ENGINE_NAME.upper()} v{ENGINE_VERSION}")
    print(f"Run ID:                     {stats.run_id}")
    print(f"Database:                   {config.database_path}")
    print(f"Feature version:            {FEATURE_VERSION}")
    print(f"Snapshot history limit:     {config.history_limit}")
    print(f"Minimum snapshot count:     {config.minimum_snapshot_count}")
    print(f"Write feature history:      {config.write_history}")
    connection = connect_database(config.database_path)
    ensure_source_tables(connection); ensure_schema(connection); start_run(connection, config, stats)
    status, error_message, started = "SUCCESS", "", time.perf_counter()
    try:
        for market in fetch_markets(connection):
            condition_id = str(market["condition_id"] or "")
            if not condition_id:
                stats.errors += 1; continue
            stats.markets_reviewed += 1
            try:
                snapshots = fetch_snapshots(connection, condition_id, config.history_limit)
                if not snapshots:
                    stats.insufficient_history += 1; continue
                if len(snapshots) < config.minimum_snapshot_count:
                    stats.insufficient_history += 1
                changes = fetch_change_counts(connection, condition_id)
                wallets = fetch_wallet_features(connection, condition_id)
                if safe_int(wallets.get("wallet_count")) > 0: stats.wallet_features_available += 1
                else: stats.wallet_features_missing += 1
                feature = build_feature(market, snapshots, changes, wallets)
                if upsert_current(connection, feature, stats.run_id): stats.features_inserted += 1
                else: stats.features_updated += 1
                if config.write_history:
                    insert_history(connection, feature, stats.run_id); stats.history_rows_written += 1
                if stats.markets_reviewed % 500 == 0:
                    connection.commit()
                    print(f"Processed {stats.markets_reviewed:,} markets | inserted={stats.features_inserted:,} | updated={stats.features_updated:,}")
            except Exception as market_error:
                stats.errors += 1
                print(f"Feature calculation failed for {condition_id}: {market_error}", file=sys.stderr)
        connection.commit()
    except KeyboardInterrupt:
        status, error_message = "INTERRUPTED", "Engine interrupted by user"
    except Exception as error:
        status, error_message = "FAILED", str(error)
        print(f"Feature engine failed: {error_message}", file=sys.stderr)
    finally:
        runtime = time.perf_counter() - started
        try:
            finalize_run(connection, stats, status, runtime, error_message)
            print_top_features(connection, config.display_limit)
        finally:
            connection.close()
    print_summary(config, stats, runtime, status)
    if error_message: print(f"Message:                    {error_message}")
    return 0 if status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())