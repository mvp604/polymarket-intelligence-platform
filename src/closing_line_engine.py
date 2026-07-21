from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 30

ELITE_SCORE = 75.0
ELITE_GRADES = {"S+", "S", "A+"}
INACTIVE = {"resolved", "closed", "ended", "ended_unconfirmed"}
LIVE = {"live", "live_unconfirmed", "started"}


def configure_utf8_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def norm(value: Any) -> str:
    return text(value).casefold()


def wallet_norm(value: Any) -> str:
    return text(value).lower()


def market_norm(value: Any) -> str:
    return text(value).lower()


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def inum(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(value, high))


def parse_time(value: Any) -> datetime | None:
    raw = text(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def weighted_average(
    pairs: list[tuple[float, float]],
    fallback: float = 0.0,
) -> float:
    numerator = 0.0
    denominator = 0.0
    for value, weight in pairs:
        weight = max(fnum(weight), 0.0)
        if weight <= 0:
            continue
        numerator += fnum(value) * weight
        denominator += weight
    return fallback if denominator <= 0 else numerator / denominator


def connect() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return connection


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def row_count(connection: sqlite3.Connection, name: str) -> int:
    if not table_exists(connection, name):
        return 0
    return inum(connection.execute(
        f'SELECT COUNT(*) FROM "{name}"'
    ).fetchone()[0])


def create_tables() -> None:
    connection = connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS entry_price_cache (
                opportunity_key TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                wallet_count INTEGER NOT NULL DEFAULT 0,
                elite_wallet_count INTEGER NOT NULL DEFAULT 0,
                total_current_value REAL NOT NULL DEFAULT 0,
                elite_current_value REAL NOT NULL DEFAULT 0,
                first_wallet_entry REAL,
                first_wallet_entry_at TEXT,
                first_elite_entry REAL,
                first_elite_entry_at TEXT,
                weighted_average_entry REAL,
                weighted_average_elite_entry REAL,
                best_observed_entry REAL,
                worst_observed_entry REAL,
                earliest_position_scan_id INTEGER,
                latest_position_scan_id INTEGER,
                wallets_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_entry_cache_market
            ON entry_price_cache(market_id);

            CREATE TABLE IF NOT EXISTS closing_line_metrics (
                opportunity_key TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                current_price REAL NOT NULL,
                first_wallet_entry REAL,
                first_elite_entry REAL,
                weighted_average_entry REAL,
                weighted_average_elite_entry REAL,
                best_observed_entry REAL,
                worst_observed_entry REAL,
                highest_observed_price REAL,
                lowest_observed_price REAL,
                price_move_from_entry REAL,
                price_move_from_elite_entry REAL,
                relative_move_from_entry REAL,
                relative_move_from_elite_entry REAL,
                gross_edge_at_entry REAL,
                gross_edge_remaining REAL,
                edge_remaining_ratio REAL,
                move_consumed_ratio REAL,
                clv_points REAL,
                clv_relative REAL,
                clv_score REAL,
                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,
                movement_status TEXT,
                entry_age_seconds INTEGER,
                elite_entry_age_seconds INTEGER,
                market_speed TEXT,
                steam_stage TEXT,
                lifecycle_status TEXT,
                seconds_to_start INTEGER,
                wallet_count INTEGER NOT NULL DEFAULT 0,
                elite_wallet_count INTEGER NOT NULL DEFAULT 0,
                data_completeness_score REAL NOT NULL DEFAULT 0,
                data_confidence TEXT NOT NULL DEFAULT 'LOW',
                chase_risk_score REAL NOT NULL DEFAULT 0,
                edge_remaining_score REAL NOT NULL DEFAULT 0,
                recommendation TEXT NOT NULL DEFAULT 'WATCH',
                explanation_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_closing_metrics_edge
            ON closing_line_metrics(edge_remaining_score DESC);

            CREATE INDEX IF NOT EXISTS idx_closing_metrics_rec
            ON closing_line_metrics(recommendation, clv_score DESC);

            CREATE TABLE IF NOT EXISTS closing_line_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                current_price REAL NOT NULL,
                weighted_average_entry REAL,
                weighted_average_elite_entry REAL,
                highest_observed_price REAL,
                lowest_observed_price REAL,
                price_move_from_entry REAL,
                price_move_from_elite_entry REAL,
                relative_move_from_entry REAL,
                relative_move_from_elite_entry REAL,
                gross_edge_remaining REAL,
                edge_remaining_ratio REAL,
                move_consumed_ratio REAL,
                clv_points REAL,
                clv_relative REAL,
                clv_score REAL,
                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,
                movement_status TEXT,
                market_speed TEXT,
                steam_stage TEXT,
                lifecycle_status TEXT,
                seconds_to_start INTEGER,
                wallet_count INTEGER,
                elite_wallet_count INTEGER,
                data_completeness_score REAL,
                data_confidence TEXT,
                chase_risk_score REAL,
                edge_remaining_score REAL,
                recommendation TEXT,
                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_closing_history_key
            ON closing_line_history(opportunity_key, observed_at DESC);

            CREATE TABLE IF NOT EXISTS closing_line_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                opportunities_seen INTEGER NOT NULL DEFAULT 0,
                entry_rows_updated INTEGER NOT NULL DEFAULT 0,
                metrics_updated INTEGER NOT NULL DEFAULT 0,
                history_rows_created INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def wallet_quality(profile: dict[str, Any]) -> float:
    return clamp(
        fnum(profile.get("wallet_score")) * 0.45
        + fnum(profile.get("dna_score")) * 0.25
        + fnum(profile.get("leader_score")) * 0.20
        + fnum(profile.get("activity_score")) * 0.10
    )


def is_elite(profile: dict[str, Any]) -> bool:
    return (
        wallet_quality(profile) >= ELITE_SCORE
        or text(profile.get("wallet_grade")).upper() in ELITE_GRADES
        or text(profile.get("dna_grade")).upper() in ELITE_GRADES
    )


def load_profiles() -> dict[str, dict[str, Any]]:
    connection = connect()
    try:
        rows = connection.execute("SELECT * FROM wallet_profiles").fetchall()
        return {
            wallet_norm(row["wallet"]): dict(row)
            for row in rows
            if wallet_norm(row["wallet"])
        }
    finally:
        connection.close()


def load_scan_times() -> dict[int, str]:
    connection = connect()
    try:
        rows = connection.execute(
            "SELECT id, scanned_at FROM wallet_scans"
        ).fetchall()
        return {inum(row["id"]): text(row["scanned_at"]) for row in rows}
    finally:
        connection.close()


def load_latest_positions(
    profiles: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    connection = connect()
    try:
        rows = connection.execute(
            """
            WITH latest AS (
                SELECT wallet, MAX(id) AS latest_scan_id
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT p.*
            FROM positions AS p
            INNER JOIN latest AS l
                ON p.wallet = l.wallet
               AND p.scan_id = l.latest_scan_id
            WHERE p.market_id IS NOT NULL
              AND TRIM(p.market_id) != ''
            """
        ).fetchall()
    finally:
        connection.close()

    output: list[dict[str, Any]] = []
    for row in rows:
        wallet = wallet_norm(row["wallet"])
        profile = profiles.get(wallet)
        if profile is None:
            continue
        item = dict(row)
        item["wallet"] = wallet
        item["market_id"] = market_norm(row["market_id"])
        item["title"] = text(row["title"]) or "Unknown market"
        item["outcome"] = text(row["outcome"]) or "Unknown"
        item["profile"] = profile
        output.append(item)
    return output


def load_metadata() -> dict[str, dict[str, Any]]:
    connection = connect()
    try:
        rows = connection.execute("SELECT * FROM market_metadata").fetchall()
        return {
            market_norm(row["market_id"]): dict(row)
            for row in rows
            if market_norm(row["market_id"])
        }
    finally:
        connection.close()


def load_price_metrics() -> dict[str, dict[str, Any]]:
    connection = connect()
    try:
        if not table_exists(connection, "market_price_metrics"):
            return {}
        rows = connection.execute("SELECT * FROM market_price_metrics").fetchall()
        return {
            market_norm(row["market_id"]): dict(row)
            for row in rows
            if market_norm(row["market_id"])
        }
    finally:
        connection.close()


def load_price_extremes() -> dict[str, dict[str, float]]:
    connection = connect()
    try:
        if not table_exists(connection, "market_price_history"):
            return {}
        rows = connection.execute(
            """
            SELECT market_id,
                   MAX(current_price) AS highest_price,
                   MIN(current_price) AS lowest_price
            FROM market_price_history
            GROUP BY market_id
            """
        ).fetchall()
        return {
            market_norm(row["market_id"]): {
                "highest_price": fnum(row["highest_price"]),
                "lowest_price": fnum(row["lowest_price"]),
            }
            for row in rows
        }
    finally:
        connection.close()


def build_entries() -> list[dict[str, Any]]:
    profiles = load_profiles()
    scans = load_scan_times()
    positions = load_latest_positions(profiles)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for position in positions:
        grouped[
            (position["market_id"], norm(position["outcome"]))
        ].append(position)

    calculated_at = now_iso()
    records: list[dict[str, Any]] = []

    for (market_id, outcome_key), group in grouped.items():
        wallet_rows: dict[str, dict[str, Any]] = {}
        for position in group:
            wallet = position["wallet"]
            prior = wallet_rows.get(wallet)
            if prior is None or fnum(position["current_value"]) > fnum(prior["current_value"]):
                wallet_rows[wallet] = position

        unique = list(wallet_rows.values())
        if not unique:
            continue

        total_value = sum(max(fnum(item["current_value"]), 0.0) for item in unique)
        if total_value <= 0:
            continue

        all_pairs: list[tuple[float, float]] = []
        elite_pairs: list[tuple[float, float]] = []
        entries: list[float] = []
        elite_count = 0
        elite_value = 0.0
        first_entry: float | None = None
        first_entry_at = ""
        first_elite: float | None = None
        first_elite_at = ""
        first_time: datetime | None = None
        first_elite_time: datetime | None = None
        scan_ids: list[int] = []
        wallets_payload: list[dict[str, Any]] = []

        for item in unique:
            profile = item["profile"]
            scan_id = inum(item["scan_id"])
            scan_ids.append(scan_id)
            scanned_at_text = text(scans.get(scan_id))
            scanned_at = parse_time(scanned_at_text)

            entry_price = clamp(fnum(item["average_price"]), 0.0, 1.0)
            current_value = max(fnum(item["current_value"]), 0.0)
            shares = max(fnum(item["shares"]), 0.0)
            weight = max(current_value, shares, 1.0)
            elite = is_elite(profile)

            entries.append(entry_price)
            all_pairs.append((entry_price, weight))

            if elite:
                elite_count += 1
                elite_value += current_value
                elite_pairs.append((entry_price, weight))

            if scanned_at is not None:
                if first_time is None or scanned_at < first_time:
                    first_time = scanned_at
                    first_entry = entry_price
                    first_entry_at = scanned_at_text

                if elite and (
                    first_elite_time is None
                    or scanned_at < first_elite_time
                ):
                    first_elite_time = scanned_at
                    first_elite = entry_price
                    first_elite_at = scanned_at_text

            wallets_payload.append(
                {
                    "wallet": item["wallet"],
                    "entry_price": round(entry_price, 6),
                    "current_value": round(current_value, 2),
                    "elite": elite,
                    "wallet_quality": round(wallet_quality(profile), 2),
                    "scan_id": scan_id,
                    "scanned_at": scanned_at_text,
                }
            )

        weighted_all = weighted_average(all_pairs, mean(entries))
        weighted_elite = (
            weighted_average(elite_pairs)
            if elite_pairs
            else None
        )

        if first_entry is None:
            first_entry = weighted_all
        if first_elite is None and weighted_elite is not None:
            first_elite = weighted_elite

        records.append(
            {
                "opportunity_key": f"{market_id}:{outcome_key}",
                "market_id": market_id,
                "title": text(unique[0]["title"]),
                "outcome": text(unique[0]["outcome"]),
                "wallet_count": len(unique),
                "elite_wallet_count": elite_count,
                "total_current_value": total_value,
                "elite_current_value": elite_value,
                "first_wallet_entry": first_entry,
                "first_wallet_entry_at": first_entry_at,
                "first_elite_entry": first_elite,
                "first_elite_entry_at": first_elite_at,
                "weighted_average_entry": weighted_all,
                "weighted_average_elite_entry": weighted_elite,
                "best_observed_entry": min(entries),
                "worst_observed_entry": max(entries),
                "earliest_position_scan_id": min(scan_ids),
                "latest_position_scan_id": max(scan_ids),
                "wallets_json": json.dumps(
                    sorted(
                        wallets_payload,
                        key=lambda item: item["current_value"],
                        reverse=True,
                    ),
                    ensure_ascii=False,
                ),
                "calculated_at": calculated_at,
                "updated_at": calculated_at,
            }
        )

    return records


def save_entries(records: list[dict[str, Any]]) -> int:
    columns = [
        "opportunity_key", "market_id", "title", "outcome",
        "wallet_count", "elite_wallet_count",
        "total_current_value", "elite_current_value",
        "first_wallet_entry", "first_wallet_entry_at",
        "first_elite_entry", "first_elite_entry_at",
        "weighted_average_entry", "weighted_average_elite_entry",
        "best_observed_entry", "worst_observed_entry",
        "earliest_position_scan_id", "latest_position_scan_id",
        "wallets_json", "calculated_at", "updated_at",
    ]

    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")

        keys = [record["opportunity_key"] for record in records]
        if keys:
            placeholders = ", ".join("?" for _ in keys)
            connection.execute(
                f"DELETE FROM entry_price_cache "
                f"WHERE opportunity_key NOT IN ({placeholders})",
                keys,
            )
        else:
            connection.execute("DELETE FROM entry_price_cache")

        names = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(
            f'"{column}" = excluded."{column}"'
            for column in columns
            if column != "opportunity_key"
        )

        query = f"""
            INSERT INTO entry_price_cache ({names})
            VALUES ({placeholders})
            ON CONFLICT(opportunity_key)
            DO UPDATE SET {updates}
        """

        for record in records:
            connection.execute(
                query,
                tuple(record[column] for column in columns),
            )

        connection.commit()
        return len(records)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def choose_current_price(
    metadata: dict[str, Any] | None,
    price_metric: dict[str, Any] | None,
) -> float | None:
    if price_metric:
        value = fnum(price_metric.get("current_price"), -1)
        if 0 <= value <= 1:
            return value
    if metadata:
        value = fnum(metadata.get("current_price"), -1)
        if 0 <= value <= 1:
            return value
    return None


def clv_score(points: float, relative: float) -> float:
    point_part = clamp(50 + points / 0.20 * 50)
    relative_part = clamp(50 + relative / 0.50 * 50)
    return clamp(point_part * 0.60 + relative_part * 0.40)


def classify_speed(metric: dict[str, Any] | None) -> str:
    if not metric:
        return "UNKNOWN"
    move_5m = abs(fnum(metric.get("move_5m")))
    move_15m = abs(fnum(metric.get("move_15m")))
    move_1h = abs(fnum(metric.get("move_1h")))
    if move_5m >= 0.04:
        return "VERY FAST"
    if move_5m >= 0.02 or move_15m >= 0.04:
        return "FAST"
    if move_15m >= 0.02 or move_1h >= 0.05:
        return "MODERATE"
    if move_1h >= 0.02:
        return "SLOW"
    return "STABLE"


def steam_stage(
    steam: float,
    reversal: float,
    remaining_ratio: float,
    consumed_ratio: float,
    points: float,
) -> str:
    if reversal >= 60:
        return "REVERSAL"
    if reversal >= 35:
        return "REVERSAL WATCH"
    if points < -0.03:
        return "NEGATIVE MOVE"
    if steam >= 75:
        if remaining_ratio <= 0.25 or consumed_ratio >= 0.85:
            return "EXHAUSTED STEAM"
        return "STRONG STEAM"
    if steam >= 50:
        if remaining_ratio <= 0.35:
            return "LATE STEAM"
        return "EARLY STEAM"
    if points > 0.03:
        return "SLOW ACCUMULATION"
    return "NO STEAM"


def chase_risk(
    current_price: float,
    points: float,
    remaining_ratio: float,
    consumed_ratio: float,
    stage: str,
) -> float:
    score = 0.0
    if points > 0:
        score += clamp(points / 0.25 * 35, 0, 35)
    score += clamp((1 - min(remaining_ratio, 1)) * 30, 0, 30)
    score += clamp(min(consumed_ratio, 1) * 20, 0, 20)
    if current_price >= 0.90:
        score += 10
    if current_price >= 0.98:
        score += 10
    if stage in {"LATE STEAM", "EXHAUSTED STEAM"}:
        score += 15
    if stage in {"REVERSAL", "REVERSAL WATCH"}:
        score += 10
    return clamp(score)


def confidence_score(
    entry: dict[str, Any],
    metadata: dict[str, Any] | None,
    metric: dict[str, Any] | None,
    extremes: dict[str, float] | None,
) -> tuple[float, str]:
    score = 25.0
    if entry["weighted_average_elite_entry"] is not None:
        score += 15
    if entry["first_wallet_entry_at"]:
        score += 10
    if entry["first_elite_entry_at"]:
        score += 10
    if metadata:
        score += 15
    if metric:
        score += 20
    if extremes:
        score += 5
    score = clamp(score)

    if score >= 85:
        return score, "VERY HIGH"
    if score >= 70:
        return score, "HIGH"
    if score >= 55:
        return score, "MEDIUM"
    if score >= 40:
        return score, "LOW"
    return score, "VERY LOW"


def recommendation(
    lifecycle: str,
    current_price: float,
    chase: float,
    edge_score: float,
    stage: str,
    confidence: str,
    seconds_to_start: int | None,
) -> str:
    status = norm(lifecycle)
    if status in INACTIVE:
        return "NO ACTION - MARKET INACTIVE"
    if status in LIVE:
        return "LIVE REVIEW REQUIRED"
    if current_price >= 0.98:
        return "PASS - MINIMAL UPSIDE"
    if stage == "REVERSAL":
        return "PASS - ACTIVE REVERSAL"
    if stage == "REVERSAL WATCH":
        return "WAIT - REVERSAL RISK"
    if chase >= 75:
        return "DO NOT CHASE"
    if chase >= 55:
        return "WAIT - LATE ENTRY RISK"
    if seconds_to_start is not None and seconds_to_start <= 300:
        return "PASS - TOO CLOSE TO START"
    if confidence in {"LOW", "VERY LOW"}:
        return "WATCH - DATA INCOMPLETE"
    if edge_score >= 75:
        return "BUY ZONE - RESEARCH PRIORITY"
    if edge_score >= 60:
        return "QUALIFIED ENTRY REVIEW"
    if edge_score >= 45:
        return "WATCH"
    return "PASS - EDGE MOSTLY CONSUMED"


def calculate_metrics(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metadata_lookup = load_metadata()
    price_lookup = load_price_metrics()
    extremes_lookup = load_price_extremes()
    calculated_at = now_iso()
    output: list[dict[str, Any]] = []

    for entry in entries:
        market_id = entry["market_id"]
        metadata = metadata_lookup.get(market_id)
        price_metric = price_lookup.get(market_id)
        extremes = extremes_lookup.get(market_id)

        current_price = choose_current_price(metadata, price_metric)
        if current_price is None:
            continue

        primary_entry = (
            entry["weighted_average_elite_entry"]
            if entry["weighted_average_elite_entry"] is not None
            else entry["weighted_average_entry"]
        )
        if primary_entry is None or primary_entry <= 0:
            continue

        highest = max(
            current_price,
            fnum((extremes or {}).get("highest_price"), current_price),
        )
        lowest = min(
            current_price,
            fnum((extremes or {}).get("lowest_price"), current_price),
        )

        move_all = current_price - entry["weighted_average_entry"]
        move_elite = (
            current_price - entry["weighted_average_elite_entry"]
            if entry["weighted_average_elite_entry"] is not None
            else move_all
        )
        relative_all = (
            move_all / entry["weighted_average_entry"]
            if entry["weighted_average_entry"] > 0
            else 0.0
        )
        relative_elite = (
            move_elite / entry["weighted_average_elite_entry"]
            if entry["weighted_average_elite_entry"] is not None
            and entry["weighted_average_elite_entry"] > 0
            else relative_all
        )

        gross_at_entry = max(1 - primary_entry, 0.0)
        gross_remaining = max(1 - current_price, 0.0)
        remaining_ratio = (
            gross_remaining / gross_at_entry
            if gross_at_entry > 0
            else 0.0
        )

        realized_move = max(current_price - primary_entry, 0.0)
        observed_possible = max(highest - primary_entry, 0.0)
        if observed_possible > 0:
            consumed_ratio = realized_move / observed_possible
        elif gross_at_entry > 0:
            consumed_ratio = realized_move / gross_at_entry
        else:
            consumed_ratio = 1.0

        points = current_price - primary_entry
        relative = points / primary_entry if primary_entry > 0 else 0.0
        clv = clv_score(points, relative)

        steam = fnum((price_metric or {}).get("steam_score"))
        reversal = fnum((price_metric or {}).get("reversal_score"))
        volatility = fnum((price_metric or {}).get("volatility_score"))
        movement = text((price_metric or {}).get("move_status")) or "INSUFFICIENT_DATA"
        speed = classify_speed(price_metric)
        stage = steam_stage(
            steam,
            reversal,
            remaining_ratio,
            consumed_ratio,
            points,
        )
        chase = chase_risk(
            current_price,
            points,
            remaining_ratio,
            consumed_ratio,
            stage,
        )
        edge_score = clamp(
            min(remaining_ratio, 1) * 60
            + clv * 0.20
            + (100 - chase) * 0.20
        )

        completeness, confidence = confidence_score(
            entry,
            metadata,
            price_metric,
            extremes,
        )

        lifecycle = text((metadata or {}).get("lifecycle_status")) or "UNKNOWN"
        seconds_value = (metadata or {}).get("seconds_to_start")
        seconds_to_start = (
            inum(seconds_value)
            if seconds_value is not None
            else None
        )

        entry_time = parse_time(entry["first_wallet_entry_at"])
        elite_time = parse_time(entry["first_elite_entry_at"])
        current_time = now_utc()
        entry_age = (
            max(int((current_time - entry_time).total_seconds()), 0)
            if entry_time
            else 0
        )
        elite_age = (
            max(int((current_time - elite_time).total_seconds()), 0)
            if elite_time
            else 0
        )

        rec = recommendation(
            lifecycle,
            current_price,
            chase,
            edge_score,
            stage,
            confidence,
            seconds_to_start,
        )

        explanation = {
            "model_version": "1.0",
            "primary_entry_source": (
                "WEIGHTED_ELITE_ENTRY"
                if entry["weighted_average_elite_entry"] is not None
                else "WEIGHTED_ALL_WALLETS"
            ),
            "warning": (
                "Edge remaining is a price-location metric, "
                "not a fair-value or win-probability estimate."
            ),
        }

        output.append(
            {
                "opportunity_key": entry["opportunity_key"],
                "market_id": market_id,
                "title": entry["title"],
                "outcome": entry["outcome"],
                "current_price": current_price,
                "first_wallet_entry": entry["first_wallet_entry"],
                "first_elite_entry": entry["first_elite_entry"],
                "weighted_average_entry": entry["weighted_average_entry"],
                "weighted_average_elite_entry": entry["weighted_average_elite_entry"],
                "best_observed_entry": entry["best_observed_entry"],
                "worst_observed_entry": entry["worst_observed_entry"],
                "highest_observed_price": highest,
                "lowest_observed_price": lowest,
                "price_move_from_entry": move_all,
                "price_move_from_elite_entry": move_elite,
                "relative_move_from_entry": relative_all,
                "relative_move_from_elite_entry": relative_elite,
                "gross_edge_at_entry": gross_at_entry,
                "gross_edge_remaining": gross_remaining,
                "edge_remaining_ratio": remaining_ratio,
                "move_consumed_ratio": consumed_ratio,
                "clv_points": points,
                "clv_relative": relative,
                "clv_score": clv,
                "steam_score": steam,
                "reversal_score": reversal,
                "volatility_score": volatility,
                "movement_status": movement,
                "entry_age_seconds": entry_age,
                "elite_entry_age_seconds": elite_age,
                "market_speed": speed,
                "steam_stage": stage,
                "lifecycle_status": lifecycle,
                "seconds_to_start": seconds_to_start,
                "wallet_count": entry["wallet_count"],
                "elite_wallet_count": entry["elite_wallet_count"],
                "data_completeness_score": completeness,
                "data_confidence": confidence,
                "chase_risk_score": chase,
                "edge_remaining_score": edge_score,
                "recommendation": rec,
                "explanation_json": json.dumps(
                    explanation,
                    ensure_ascii=False,
                ),
                "calculated_at": calculated_at,
                "updated_at": calculated_at,
            }
        )

    output.sort(
        key=lambda item: (
            item["edge_remaining_score"],
            item["clv_score"],
            -item["chase_risk_score"],
            item["elite_wallet_count"],
        ),
        reverse=True,
    )
    return output


METRIC_COLUMNS = [
    "opportunity_key", "market_id", "title", "outcome",
    "current_price", "first_wallet_entry", "first_elite_entry",
    "weighted_average_entry", "weighted_average_elite_entry",
    "best_observed_entry", "worst_observed_entry",
    "highest_observed_price", "lowest_observed_price",
    "price_move_from_entry", "price_move_from_elite_entry",
    "relative_move_from_entry", "relative_move_from_elite_entry",
    "gross_edge_at_entry", "gross_edge_remaining",
    "edge_remaining_ratio", "move_consumed_ratio",
    "clv_points", "clv_relative", "clv_score",
    "steam_score", "reversal_score", "volatility_score",
    "movement_status", "entry_age_seconds", "elite_entry_age_seconds",
    "market_speed", "steam_stage", "lifecycle_status",
    "seconds_to_start", "wallet_count", "elite_wallet_count",
    "data_completeness_score", "data_confidence",
    "chase_risk_score", "edge_remaining_score",
    "recommendation", "explanation_json",
    "calculated_at", "updated_at",
]

HISTORY_COLUMNS = [
    "opportunity_key", "market_id", "title", "outcome",
    "current_price", "weighted_average_entry",
    "weighted_average_elite_entry", "highest_observed_price",
    "lowest_observed_price", "price_move_from_entry",
    "price_move_from_elite_entry", "relative_move_from_entry",
    "relative_move_from_elite_entry", "gross_edge_remaining",
    "edge_remaining_ratio", "move_consumed_ratio",
    "clv_points", "clv_relative", "clv_score",
    "steam_score", "reversal_score", "volatility_score",
    "movement_status", "market_speed", "steam_stage",
    "lifecycle_status", "seconds_to_start",
    "wallet_count", "elite_wallet_count",
    "data_completeness_score", "data_confidence",
    "chase_risk_score", "edge_remaining_score",
    "recommendation", "observed_at",
]


def save_metrics(metrics: list[dict[str, Any]]) -> tuple[int, int]:
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")

        keys = [item["opportunity_key"] for item in metrics]
        if keys:
            placeholders = ", ".join("?" for _ in keys)
            connection.execute(
                f"DELETE FROM closing_line_metrics "
                f"WHERE opportunity_key NOT IN ({placeholders})",
                keys,
            )
        else:
            connection.execute("DELETE FROM closing_line_metrics")

        metric_names = ", ".join(f'"{column}"' for column in METRIC_COLUMNS)
        metric_placeholders = ", ".join("?" for _ in METRIC_COLUMNS)
        updates = ", ".join(
            f'"{column}" = excluded."{column}"'
            for column in METRIC_COLUMNS
            if column != "opportunity_key"
        )
        metric_query = f"""
            INSERT INTO closing_line_metrics ({metric_names})
            VALUES ({metric_placeholders})
            ON CONFLICT(opportunity_key)
            DO UPDATE SET {updates}
        """

        history_names = ", ".join(f'"{column}"' for column in HISTORY_COLUMNS)
        history_placeholders = ", ".join("?" for _ in HISTORY_COLUMNS)
        history_query = f"""
            INSERT INTO closing_line_history ({history_names})
            VALUES ({history_placeholders})
        """

        observed_at = now_iso()

        for item in metrics:
            connection.execute(
                metric_query,
                tuple(item[column] for column in METRIC_COLUMNS),
            )
            history = dict(item)
            history["observed_at"] = observed_at
            connection.execute(
                history_query,
                tuple(history[column] for column in HISTORY_COLUMNS),
            )

        connection.commit()
        return len(metrics), len(metrics)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def start_run() -> tuple[int, datetime]:
    started = now_utc()
    connection = connect()
    try:
        cursor = connection.execute(
            """
            INSERT INTO closing_line_runs(started_at, status)
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
    seen: int,
    entries_updated: int,
    metrics_updated: int,
    history_created: int,
    error: str = "",
) -> None:
    finished = now_utc()
    connection = connect()
    try:
        connection.execute(
            """
            UPDATE closing_line_runs
            SET finished_at = ?,
                elapsed_seconds = ?,
                opportunities_seen = ?,
                entry_rows_updated = ?,
                metrics_updated = ?,
                history_rows_created = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                finished.isoformat(),
                (finished - started).total_seconds(),
                seen,
                entries_updated,
                metrics_updated,
                history_created,
                status,
                error,
                run_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def display_readiness() -> None:
    connection = connect()
    try:
        print()
        print("=" * 100)
        print("CLOSING LINE DATA READINESS")
        print("=" * 100)
        for name in (
            "wallet_scans",
            "positions",
            "wallet_profiles",
            "market_metadata",
            "market_price_history",
            "market_price_metrics",
            "entry_price_cache",
            "closing_line_metrics",
            "closing_line_history",
            "closing_line_runs",
        ):
            if table_exists(connection, name):
                print(f"{name:<40}{row_count(connection, name):>12} rows")
            else:
                print(f"{name:<40}{'NOT FOUND':>12}")
        print("=" * 100)
    finally:
        connection.close()


def fmt_price(value: Any) -> str:
    return f"{fnum(value):.4f}"


def fmt_move(value: Any) -> str:
    return f"{fnum(value):+.4f}"


def fmt_pct(value: Any) -> str:
    return f"{fnum(value):+.1%}"


def display_metric(rank: int, item: dict[str, Any]) -> None:
    print()
    print("-" * 100)
    print(f"{rank}. {item['title']}")
    print("-" * 100)
    print(f"Outcome:                    {item['outcome']}")
    print(f"Recommendation:             {item['recommendation']}")
    print(
        f"Data confidence:            "
        f"{item['data_confidence']} "
        f"({item['data_completeness_score']:.1f}/100)"
    )
    print(f"All-wallet entry:           {fmt_price(item['weighted_average_entry'])}")
    if item["weighted_average_elite_entry"] is not None:
        print(
            f"Elite-wallet entry:         "
            f"{fmt_price(item['weighted_average_elite_entry'])}"
        )
    print(f"Current price:              {fmt_price(item['current_price'])}")
    print(f"CLV points / relative:      {fmt_move(item['clv_points'])} / {fmt_pct(item['clv_relative'])}")
    print(f"CLV score:                  {item['clv_score']:.1f}/100")
    print(f"Edge remaining score:       {item['edge_remaining_score']:.1f}/100")
    print(f"Chase risk:                 {item['chase_risk_score']:.1f}/100")
    print(f"Steam / reversal:           {item['steam_score']:.1f} / {item['reversal_score']:.1f}")
    print(f"Speed / stage:              {item['market_speed']} / {item['steam_stage']}")
    print(f"Wallets / elite:            {item['wallet_count']} / {item['elite_wallet_count']}")
    print(f"Lifecycle:                  {item['lifecycle_status']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate entry, CLV, steam, chase-risk and edge intelligence."
    )
    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )
    return parser.parse_args()


def main() -> None:
    configure_utf8_output()
    args = parse_args()

    print()
    print("=" * 100)
    print("POLYMARKET CLOSING LINE INTELLIGENCE ENGINE v1")
    print("=" * 100)
    print(f"Database: {DATABASE_PATH}")

    create_tables()
    display_readiness()

    run_id, started = start_run()
    seen = entries_updated = metrics_updated = history_created = 0

    try:
        entries = build_entries()
        seen = len(entries)
        entries_updated = save_entries(entries)

        metrics = calculate_metrics(entries)
        metrics_updated, history_created = save_metrics(metrics)

        finish_run(
            run_id,
            started,
            "SUCCESS",
            seen,
            entries_updated,
            metrics_updated,
            history_created,
        )

        print()
        print("=" * 100)
        print("CLOSING LINE INTELLIGENCE SUMMARY")
        print("=" * 100)
        print(f"Entry records calculated:   {seen}")
        print(f"Entry rows updated:         {entries_updated}")
        print(f"Closing metrics updated:    {metrics_updated}")
        print(f"History rows created:       {history_created}")
        print("=" * 100)

        print()
        print("TOP CLOSING-LINE OPPORTUNITIES")

        for rank, item in enumerate(
            metrics[: max(args.display_limit, 1)],
            start=1,
        ):
            display_metric(rank, item)

        print()
        print("=" * 100)
        print("CLOSING LINE INTELLIGENCE ENGINE COMPLETE")
        print("=" * 100)
        print("Entry reconstruction: entry_price_cache")
        print("Current CLV metrics: closing_line_metrics")
        print("Historical snapshots: closing_line_history")
        print(
            "Early runs may show UNKNOWN speed or NO STEAM "
            "until price history matures."
        )
        print(
            "Edge remaining is a price-location metric, "
            "not a fair-value estimate."
        )
        print("=" * 100)

    except Exception as error:
        finish_run(
            run_id,
            started,
            "FAILED",
            seen,
            entries_updated,
            metrics_updated,
            history_created,
            f"{type(error).__name__}: {error}",
        )
        raise


if __name__ == "__main__":
    main()