from __future__ import annotations

import json
import math
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
DATABASE_BUSY_TIMEOUT_MS = 30_000
TOP_RESULTS_TO_DISPLAY = 30
MINIMUM_CURRENT_VALUE = 1.0
INACTIVE_STATUSES = {"resolved", "closed", "ended", "ended_unconfirmed"}
LIVE_STATUSES = {"live", "live_unconfirmed", "started"}
PREGAME_STATUSES = {"pregame", "starting_soon"}
DATE_PATTERN = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
SCORE_WEIGHTS = {
    "conviction": 0.18,
    "wallet_quality": 0.18,
    "consensus": 0.15,
    "capital": 0.12,
    "profitability": 0.10,
    "backtest": 0.09,
    "momentum": 0.07,
    "timing": 0.06,
    "freshness": 0.05,
}


def configure_utf8_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_text(value: Any) -> str:
    return clean_text(value).casefold()


def normalize_wallet(value: Any) -> str:
    return clean_text(value).lower()


def normalize_market_id(value: Any) -> str:
    return clean_text(value).lower()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_ratio(value: Any) -> float:
    number = safe_float(value)
    if abs(number) > 2:
        number /= 100.0
    return number


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(value, maximum))


def parse_datetime(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def weighted_average(pairs: list[tuple[float, float]], fallback: float = 0.0) -> float:
    numerator = 0.0
    denominator = 0.0
    for value, weight in pairs:
        weight = max(safe_float(weight), 0.0)
        if weight <= 0:
            continue
        numerator += safe_float(value) * weight
        denominator += weight
    return fallback if denominator <= 0 else numerator / denominator


def format_money(value: Any) -> str:
    return f"${safe_float(value):,.2f}"


def format_signed_money(value: Any) -> str:
    number = safe_float(value)
    if number > 0:
        return f"+${number:,.2f}"
    if number < 0:
        return f"-${abs(number):,.2f}"
    return "$0.00"


def format_percentage(value: Any, decimal_places: int = 1) -> str:
    return f"{normalize_ratio(value):.{decimal_places}%}"


def format_t_minus(seconds_to_start: Any) -> str:
    if seconds_to_start is None:
        return "NO CONFIRMED START"
    seconds = safe_int(seconds_to_start)
    if seconds <= 0:
        return "STARTED"
    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds_left = divmod(remainder, 60)
    if days > 0:
        return f"T-{days}d {hours:02d}:{minutes:02d}:{seconds_left:02d}"
    return f"T-{hours:02d}:{minutes:02d}:{seconds_left:02d}"


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {DATABASE_BUSY_TIMEOUT_MS}")
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    if not table_exists(connection, table_name):
        return set()
    return {
        clean_text(row["name"])
        for row in connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    }


def table_row_count(connection: sqlite3.Connection, table_name: str) -> int:
    if not table_exists(connection, table_name):
        return 0
    row = connection.execute(
        f'SELECT COUNT(*) AS total FROM "{table_name}"'
    ).fetchone()
    return safe_int(row["total"] if row else 0)


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    """Add a missing column to an existing SQLite table safely."""

    if column_name in table_columns(connection, table_name):
        return

    connection.execute(
        f'ALTER TABLE "{table_name}" '
        f'ADD COLUMN "{column_name}" {definition}'
    )


def migration_safe_definition(definition: str) -> str:
    """
    Convert a CREATE TABLE definition into an ALTER TABLE-safe definition.

    Existing v1 tables already contain rows. SQLite cannot add a NOT NULL
    column without a non-NULL default, so migration-added columns are made
    nullable while preserving their type and any DEFAULT value.
    """

    safe_definition = definition.replace("PRIMARY KEY", "")
    safe_definition = safe_definition.replace("UNIQUE", "")
    safe_definition = safe_definition.replace("NOT NULL", "")
    safe_definition = " ".join(safe_definition.split())

    return safe_definition or "TEXT"


BASE_COLUMNS: dict[str, str] = {
    "opportunity_key": "TEXT PRIMARY KEY",
    "market_id": "TEXT NOT NULL",
    "title": "TEXT NOT NULL",
    "outcome": "TEXT NOT NULL",
    "opportunity_score": "REAL NOT NULL DEFAULT 0",
    "opportunity_tier": "TEXT NOT NULL DEFAULT 'PASS'",
    "opportunity_grade": "TEXT NOT NULL DEFAULT 'D'",
    "recommended_action": "TEXT NOT NULL DEFAULT 'PASS'",
    "wallet_count": "INTEGER NOT NULL DEFAULT 0",
    "average_wallet_quality": "REAL NOT NULL DEFAULT 0",
    "combined_current_value": "REAL NOT NULL DEFAULT 0",
    "combined_open_pnl": "REAL NOT NULL DEFAULT 0",
    "open_pnl_ratio": "REAL NOT NULL DEFAULT 0",
    "average_entry_price": "REAL NOT NULL DEFAULT 0",
    "average_current_price": "REAL NOT NULL DEFAULT 0",
    "observed_price_move": "REAL NOT NULL DEFAULT 0",
    "average_wallet_concentration": "REAL NOT NULL DEFAULT 0",
    "conviction_score": "REAL NOT NULL DEFAULT 0",
    "consensus_component": "REAL NOT NULL DEFAULT 0",
    "wallet_quality_component": "REAL NOT NULL DEFAULT 0",
    "capital_component": "REAL NOT NULL DEFAULT 0",
    "profitability_component": "REAL NOT NULL DEFAULT 0",
    "momentum_component": "REAL NOT NULL DEFAULT 0",
    "timing_component": "REAL NOT NULL DEFAULT 0",
    "freshness_component": "REAL NOT NULL DEFAULT 0",
    "concentration_penalty": "REAL NOT NULL DEFAULT 0",
    "lifecycle_status": "TEXT",
    "game_start_time": "TEXT",
    "seconds_to_start": "INTEGER",
    "is_pregame": "INTEGER NOT NULL DEFAULT 0",
    "is_live": "INTEGER NOT NULL DEFAULT 0",
    "is_ended": "INTEGER NOT NULL DEFAULT 0",
    "is_closed": "INTEGER NOT NULL DEFAULT 0",
    "is_resolved": "INTEGER NOT NULL DEFAULT 0",
    "score": "TEXT",
    "period": "TEXT",
    "elapsed": "TEXT",
    "signal_observed_at": "TEXT",
    "metadata_updated_at": "TEXT",
    "explanation_json": "TEXT",
    "calculated_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL",
}

V2_COLUMNS: dict[str, str] = {
    "market_type": "TEXT",
    "weighted_wallet_quality": "REAL NOT NULL DEFAULT 0",
    "average_dna_score": "REAL NOT NULL DEFAULT 0",
    "weighted_dna_score": "REAL NOT NULL DEFAULT 0",
    "average_leader_score": "REAL NOT NULL DEFAULT 0",
    "weighted_leader_score": "REAL NOT NULL DEFAULT 0",
    "average_activity_score": "REAL NOT NULL DEFAULT 0",
    "profitable_wallet_rate": "REAL NOT NULL DEFAULT 0",
    "elite_wallet_count": "INTEGER NOT NULL DEFAULT 0",
    "elite_wallet_value": "REAL NOT NULL DEFAULT 0",
    "elite_wallet_value_share": "REAL NOT NULL DEFAULT 0",
    "largest_wallet_share": "REAL NOT NULL DEFAULT 0",
    "top_three_wallet_share": "REAL NOT NULL DEFAULT 0",
    "effective_wallet_count": "REAL NOT NULL DEFAULT 0",
    "average_pair_overlap": "REAL NOT NULL DEFAULT 0",
    "portfolio_independence_score": "REAL NOT NULL DEFAULT 0",
    "overlap_pair_coverage": "REAL NOT NULL DEFAULT 0",
    "opposing_wallet_count": "INTEGER NOT NULL DEFAULT 0",
    "opposing_value": "REAL NOT NULL DEFAULT 0",
    "market_total_value": "REAL NOT NULL DEFAULT 0",
    "market_value_share": "REAL NOT NULL DEFAULT 0",
    "conflict_ratio": "REAL NOT NULL DEFAULT 0",
    "backtest_sample_size": "INTEGER NOT NULL DEFAULT 0",
    "backtest_win_rate": "REAL NOT NULL DEFAULT 0",
    "backtest_average_return": "REAL NOT NULL DEFAULT 0",
    "backtest_component": "REAL NOT NULL DEFAULT 50",
    "data_completeness_score": "REAL NOT NULL DEFAULT 0",
    "data_confidence": "TEXT NOT NULL DEFAULT 'LOW'",
    "overlap_penalty": "REAL NOT NULL DEFAULT 0",
    "conflict_penalty": "REAL NOT NULL DEFAULT 0",
    "extreme_price_penalty": "REAL NOT NULL DEFAULT 0",
    "low_upside_penalty": "REAL NOT NULL DEFAULT 0",
    "chase_penalty": "REAL NOT NULL DEFAULT 0",
    "stale_penalty": "REAL NOT NULL DEFAULT 0",
    "total_penalty": "REAL NOT NULL DEFAULT 0",
    "remaining_upside": "REAL NOT NULL DEFAULT 0",
    "is_market_leader": "INTEGER NOT NULL DEFAULT 0",
    "wallets_json": "TEXT",
}


def create_or_migrate_opportunity_tables() -> None:
    connection = connect_database()
    try:
        columns = {**BASE_COLUMNS, **V2_COLUMNS}
        if not table_exists(connection, "opportunity_scores"):
            definitions = ", ".join(
                f'"{name}" {definition}' for name, definition in columns.items()
            )
            connection.execute(f"CREATE TABLE opportunity_scores ({definitions})")
        else:
            for name, definition in columns.items():
                if name != "opportunity_key":
                    ensure_column(
                        connection,
                        "opportunity_scores",
                        name,
                        migration_safe_definition(definition),
                    )

        if not table_exists(connection, "opportunity_score_history"):
            definitions = ['"id" INTEGER PRIMARY KEY AUTOINCREMENT']
            for name, definition in columns.items():
                clean_definition = definition.replace("PRIMARY KEY", "").strip()
                if name == "opportunity_key":
                    clean_definition = "TEXT NOT NULL"
                definitions.append(f'"{name}" {clean_definition}')
            connection.execute(
                f"CREATE TABLE opportunity_score_history ({', '.join(definitions)})"
            )
        else:
            for name, definition in columns.items():
                if name != "opportunity_key":
                    ensure_column(
                        connection,
                        "opportunity_score_history",
                        name,
                        migration_safe_definition(definition),
                    )

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_opportunity_scores_rank "
            "ON opportunity_scores(opportunity_score DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_opportunity_history_key "
            "ON opportunity_score_history(opportunity_key, calculated_at DESC)"
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def load_wallet_profiles() -> dict[str, dict[str, Any]]:
    connection = connect_database()
    try:
        rows = connection.execute("SELECT * FROM wallet_profiles").fetchall()
        return {
            normalize_wallet(row["wallet"]): dict(row)
            for row in rows
            if normalize_wallet(row["wallet"])
        }
    finally:
        connection.close()


def load_latest_positions(
    wallet_profiles: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    connection = connect_database()
    try:
        rows = connection.execute(
            """
            WITH latest_scans AS (
                SELECT wallet, MAX(id) AS latest_scan_id
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT p.*
            FROM positions AS p
            INNER JOIN latest_scans AS s
                ON p.wallet = s.wallet
               AND p.scan_id = s.latest_scan_id
            WHERE p.market_id IS NOT NULL
              AND TRIM(p.market_id) != ''
            """
        ).fetchall()
    finally:
        connection.close()

    output: list[dict[str, Any]] = []
    for row in rows:
        wallet = normalize_wallet(row["wallet"])
        profile = wallet_profiles.get(wallet)
        if profile is None:
            continue
        item = dict(row)
        item["wallet"] = wallet
        item["market_id"] = normalize_market_id(row["market_id"])
        item["title"] = clean_text(row["title"]) or "Unknown market"
        item["outcome"] = clean_text(row["outcome"]) or "Unknown"
        item["profile"] = profile
        output.append(item)
    return output


def load_latest_consensus() -> dict[tuple[str, str], dict[str, Any]]:
    connection = connect_database()
    try:
        rows = connection.execute(
            """
            WITH latest AS (
                SELECT market_id,
                       LOWER(TRIM(outcome)) AS normalized_outcome,
                       MAX(id) AS latest_id
                FROM consensus_history
                GROUP BY market_id, LOWER(TRIM(outcome))
            )
            SELECT c.*
            FROM consensus_history AS c
            INNER JOIN latest AS l ON c.id = l.latest_id
            """
        ).fetchall()
        return {
            (normalize_market_id(row["market_id"]), normalize_text(row["outcome"])): dict(row)
            for row in rows
        }
    finally:
        connection.close()


def load_market_metadata() -> dict[str, dict[str, Any]]:
    connection = connect_database()
    try:
        rows = connection.execute("SELECT * FROM market_metadata").fetchall()
        return {
            normalize_market_id(row["market_id"]): dict(row)
            for row in rows
            if normalize_market_id(row["market_id"])
        }
    finally:
        connection.close()


def load_overlap_lookup() -> dict[tuple[str, str], dict[str, Any]]:
    connection = connect_database()
    try:
        rows = connection.execute("SELECT * FROM portfolio_overlap").fetchall()
    finally:
        connection.close()
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        a = normalize_wallet(row["wallet_a"])
        b = normalize_wallet(row["wallet_b"])
        if a and b:
            lookup[tuple(sorted((a, b)))] = dict(row)
    return lookup


def load_backtests() -> list[dict[str, Any]]:
    connection = connect_database()
    try:
        return [
            dict(row)
            for row in connection.execute("SELECT * FROM backtest_results").fetchall()
        ]
    finally:
        connection.close()


def classify_market_type(title: str) -> str:
    text = normalize_text(title)
    if "exact score" in text:
        return "EXACT_SCORE"
    if "corners" in text:
        return "CORNERS"
    if "o/u" in text or "over/under" in text:
        return "TOTAL"
    if "both teams to score" in text:
        return "BTTS"
    if "spread:" in text:
        return "SPREAD"
    if "team to advance" in text:
        return "ADVANCE"
    if "halftime" in text:
        return "HALFTIME"
    if "world cup" in text and "win the" in text:
        return "FUTURE"
    if text.startswith("will ") and " win on " in text:
        return "MONEYLINE"
    if " vs." in text or " vs " in text:
        return "MATCH"
    return "OTHER"


def title_date(title: str) -> date | None:
    match = DATE_PATTERN.search(title)
    if match is None:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def is_inactive(metadata: dict[str, Any] | None) -> bool:
    if not metadata:
        return False
    status = normalize_text(metadata.get("lifecycle_status"))
    return (
        status in INACTIVE_STATUSES
        or safe_int(metadata.get("is_ended")) == 1
        or safe_int(metadata.get("is_closed")) == 1
        or safe_int(metadata.get("is_resolved")) == 1
    )


def is_stale(title: str, metadata: dict[str, Any] | None) -> bool:
    extracted = title_date(title)
    if extracted is None or extracted >= utc_now().date():
        return False
    status = normalize_text((metadata or {}).get("lifecycle_status"))
    return status not in PREGAME_STATUSES


def wallet_quality(profile: dict[str, Any]) -> float:
    return clamp(
        safe_float(profile.get("wallet_score")) * 0.45
        + safe_float(profile.get("dna_score")) * 0.25
        + safe_float(profile.get("leader_score")) * 0.20
        + safe_float(profile.get("activity_score")) * 0.10
    )


def overlap_metrics(
    wallets: list[str],
    lookup: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, float]:
    unique = sorted(set(wallets))
    possible = len(unique) * (len(unique) - 1) // 2
    if possible <= 0:
        return {
            "average_pair_overlap": 0.0,
            "portfolio_independence_score": 70.0,
            "overlap_pair_coverage": 0.0,
            "effective_wallet_multiplier": 1.0,
        }
    values: list[float] = []
    for index, wallet_a in enumerate(unique):
        for wallet_b in unique[index + 1 :]:
            row = lookup.get(tuple(sorted((wallet_a, wallet_b))))
            if row is None:
                continue
            weighted = normalize_ratio(row.get("weighted_overlap_score"))
            jaccard = normalize_ratio(row.get("jaccard_similarity"))
            values.append(clamp(weighted if weighted > 0 else jaccard, 0.0, 1.0))
    coverage = len(values) / possible
    average_overlap = mean(values) if values else 0.0
    return {
        "average_pair_overlap": average_overlap,
        "portfolio_independence_score": clamp((1.0 - average_overlap) * 100.0),
        "overlap_pair_coverage": coverage,
        "effective_wallet_multiplier": clamp(1.0 - average_overlap * 0.60, 0.35, 1.0),
    }


def backtest_summary(
    rows: list[dict[str, Any]], conviction_grade: str
) -> tuple[int, float, float, float]:
    evaluated: list[tuple[bool, float]] = []
    grade = clean_text(conviction_grade).upper()
    for row in rows:
        status = normalize_text(row.get("result_status"))
        profit = safe_float(row.get("hypothetical_profit"))
        selected = normalize_text(row.get("selected_outcome"))
        winning = normalize_text(row.get("winning_outcome"))
        result: bool | None = None
        if any(word in status for word in ("win", "won", "success", "correct")):
            result = True
        elif any(word in status for word in ("loss", "lost", "fail", "incorrect")):
            result = False
        elif profit > 0:
            result = True
        elif profit < 0:
            result = False
        elif selected and winning:
            result = selected == winning
        if result is None:
            continue
        row_grade = clean_text(row.get("conviction_grade")).upper()
        if grade and row_grade and row_grade != grade:
            continue
        evaluated.append((result, normalize_ratio(row.get("hypothetical_return_pct"))))
    if not evaluated:
        return 0, 0.0, 0.0, 50.0
    sample_size = len(evaluated)
    win_rate = sum(1 for result, _ in evaluated if result) / sample_size
    average_return = mean(value for _, value in evaluated)
    raw = clamp(50 + (win_rate - 0.50) * 80 + average_return * 30)
    reliability = min(sample_size / 30.0, 1.0)
    return sample_size, win_rate, average_return, clamp(50 + (raw - 50) * reliability)


def capital_score(value: float) -> float:
    if value <= 0:
        return 0.0
    lower = 1_000.0
    upper = 3_000_000.0
    if value <= lower:
        return clamp(value / lower * 12.0)
    return clamp(12.0 + math.log10(value / lower) / math.log10(upper / lower) * 88.0)


def momentum_score(move: float) -> float:
    if move <= -0.25:
        return 5.0
    if move <= -0.10:
        return 20.0
    if move < 0:
        return clamp(50 + move * 300)
    if move <= 0.03:
        return clamp(50 + move * 600)
    if move <= 0.10:
        return clamp(68 + (move - 0.03) * 300)
    if move <= 0.18:
        return clamp(89 - (move - 0.10) * 150)
    if move <= 0.30:
        return clamp(77 - (move - 0.18) * 200)
    return 40.0


def timing_score(status: str, seconds_to_start: int | None) -> float:
    normalized = normalize_text(status)
    if normalized in INACTIVE_STATUSES:
        return 0.0
    if normalized in LIVE_STATUSES:
        return 20.0
    if seconds_to_start is None:
        return 48.0
    minutes = safe_int(seconds_to_start) / 60.0
    if minutes <= 0:
        return 20.0
    if minutes <= 5:
        return 35.0
    if minutes <= 15:
        return 62.0
    if minutes <= 60:
        return 100.0
    if minutes <= 180:
        return 95.0
    if minutes <= 360:
        return 88.0
    if minutes <= 720:
        return 78.0
    if minutes <= 1_440:
        return 68.0
    if minutes <= 4_320:
        return 58.0
    return 48.0


def freshness_score(observed_at: Any) -> float:
    observed = parse_datetime(observed_at)
    if observed is None:
        return 40.0
    age_minutes = max((utc_now() - observed).total_seconds() / 60.0, 0.0)
    if age_minutes <= 5:
        return 100.0
    if age_minutes <= 15:
        return 95.0
    if age_minutes <= 30:
        return 90.0
    if age_minutes <= 60:
        return 82.0
    if age_minutes <= 180:
        return 72.0
    if age_minutes <= 360:
        return 62.0
    if age_minutes <= 720:
        return 55.0
    if age_minutes <= 1_440:
        return 48.0
    if age_minutes <= 4_320:
        return 38.0
    return 25.0


def grade_from_score(score: float) -> tuple[str, str]:
    if score >= 88:
        return "ELITE", "S+"
    if score >= 80:
        return "HIGH CONVICTION", "S"
    if score >= 73:
        return "STRONG", "A+"
    if score >= 66:
        return "QUALIFIED", "A"
    if score >= 58:
        return "DEVELOPING", "B"
    if score >= 48:
        return "WATCH", "C"
    return "PASS", "D"


def calculate_opportunities() -> list[dict[str, Any]]:
    profiles = load_wallet_profiles()
    positions = load_latest_positions(profiles)
    consensus_lookup = load_latest_consensus()
    metadata_lookup = load_market_metadata()
    overlap_lookup = load_overlap_lookup()
    backtests = load_backtests()

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    market_groups: dict[str, list[tuple[tuple[str, str], list[dict[str, Any]]]]] = defaultdict(list)
    for position in positions:
        key = (position["market_id"], normalize_text(position["outcome"]))
        grouped[key].append(position)
    for key, group in grouped.items():
        market_groups[key[0]].append((key, group))

    calculated_at = utc_now_iso()
    opportunities: list[dict[str, Any]] = []

    for key, group in grouped.items():
        market_id, normalized_outcome = key
        title = clean_text(group[0]["title"])
        outcome = clean_text(group[0]["outcome"])
        metadata = metadata_lookup.get(market_id)
        if is_inactive(metadata) or is_stale(title, metadata):
            continue

        combined_value = sum(max(safe_float(item["current_value"]), 0.0) for item in group)
        if combined_value < MINIMUM_CURRENT_VALUE:
            continue

        wallets = sorted({item["wallet"] for item in group})
        wallet_count = len(wallets)
        wallet_values: dict[str, float] = defaultdict(float)
        wallet_signal_pnl: dict[str, float] = defaultdict(float)
        for item in group:
            wallet_values[item["wallet"]] += max(safe_float(item["current_value"]), 0.0)
            wallet_signal_pnl[item["wallet"]] += safe_float(item["cash_pnl"])

        qualities: list[float] = []
        quality_pairs: list[tuple[float, float]] = []
        dna_pairs: list[tuple[float, float]] = []
        leader_pairs: list[tuple[float, float]] = []
        activities: list[float] = []
        concentrations: list[float] = []
        elite_wallet_count = 0
        elite_wallet_value = 0.0
        profitable_wallets = 0
        wallet_payload: list[dict[str, Any]] = []

        for wallet in wallets:
            profile = next(item["profile"] for item in group if item["wallet"] == wallet)
            value = wallet_values[wallet]
            quality = wallet_quality(profile)
            dna = clamp(safe_float(profile.get("dna_score")))
            leader = clamp(safe_float(profile.get("leader_score")))
            activity = clamp(safe_float(profile.get("activity_score")))
            concentration = normalize_ratio(profile.get("concentration_ratio"))
            qualities.append(quality)
            quality_pairs.append((quality, value))
            dna_pairs.append((dna, value))
            leader_pairs.append((leader, value))
            activities.append(activity)
            concentrations.append(concentration)

            wallet_grade = clean_text(profile.get("wallet_grade")).upper()
            dna_grade = clean_text(profile.get("dna_grade")).upper()
            is_elite = quality >= 75 or wallet_grade in {"S+", "S", "A+"} or dna_grade in {"S+", "S", "A+"}
            if is_elite:
                elite_wallet_count += 1
                elite_wallet_value += value
            if wallet_signal_pnl[wallet] > 0:
                profitable_wallets += 1
            wallet_payload.append({
                "wallet": wallet,
                "current_value": round(value, 2),
                "wallet_score": round(safe_float(profile.get("wallet_score")), 2),
                "composite_quality": round(quality, 2),
                "dna_score": round(dna, 2),
                "leader_score": round(leader, 2),
                "wallet_grade": wallet_grade,
                "dna_grade": dna_grade,
                "risk_profile": clean_text(profile.get("risk_profile")),
            })

        average_wallet_quality = mean(qualities)
        weighted_wallet_quality = weighted_average(quality_pairs, average_wallet_quality)
        weighted_dna = weighted_average(dna_pairs)
        weighted_leader = weighted_average(leader_pairs)
        average_activity = mean(activities)
        wallet_quality_component = clamp(
            weighted_wallet_quality * 0.50
            + weighted_dna * 0.25
            + weighted_leader * 0.20
            + average_activity * 0.05
        )

        overlap = overlap_metrics(wallets, overlap_lookup)
        effective_wallet_count = wallet_count * overlap["effective_wallet_multiplier"]
        consensus_component = clamp(
            min(96.0, 20 + effective_wallet_count * 12)
            + min(elite_wallet_count * 2.5, 10.0)
            + (overlap["portfolio_independence_score"] - 50) * 0.10
        )

        combined_pnl = sum(safe_float(item["cash_pnl"]) for item in group)
        profitable_wallet_rate = profitable_wallets / wallet_count
        signal_pnl_ratio = combined_pnl / combined_value if combined_value > 0 else 0.0
        profitability_component = clamp(
            (50 + signal_pnl_ratio * 140) * 0.60
            + profitable_wallet_rate * 100 * 0.40
        )

        average_entry_price = weighted_average(
            [(safe_float(item["average_price"]), max(safe_float(item["shares"]), safe_float(item["current_value"]), 0.0)) for item in group],
            mean(safe_float(item["average_price"]) for item in group),
        )
        average_current_price = weighted_average(
            [(safe_float(item["current_price"]), max(safe_float(item["current_value"]), safe_float(item["shares"]), 0.0)) for item in group],
            mean(safe_float(item["current_price"]) for item in group),
        )
        observed_price_move = average_current_price - average_entry_price

        consensus_record = consensus_lookup.get((market_id, normalized_outcome))
        supplied_conviction = safe_float(consensus_record.get("conviction_score") if consensus_record else 0)
        conviction_score = clamp(supplied_conviction) if supplied_conviction > 0 else clamp(
            consensus_component * 0.30
            + wallet_quality_component * 0.30
            + capital_score(combined_value) * 0.22
            + profitability_component * 0.18
        )
        conviction_grade = clean_text(consensus_record.get("conviction_grade") if consensus_record else "")
        if not conviction_grade:
            _, conviction_grade = grade_from_score(conviction_score)

        sample_size, win_rate, avg_return, backtest_component = backtest_summary(backtests, conviction_grade)
        lifecycle_status = clean_text((metadata or {}).get("lifecycle_status")) or "UNKNOWN"
        seconds_value = (metadata or {}).get("seconds_to_start")
        seconds_to_start = safe_int(seconds_value) if seconds_value is not None else None
        signal_observed_at = clean_text(consensus_record.get("scanned_at") if consensus_record else "")

        market_total_value = 0.0
        opposing_value = 0.0
        opposing_wallets: set[str] = set()
        group_values: list[float] = []
        for group_key, other_group in market_groups[market_id]:
            group_value = sum(max(safe_float(item["current_value"]), 0.0) for item in other_group)
            market_total_value += group_value
            group_values.append(group_value)
            if group_key[1] != normalized_outcome:
                opposing_value += group_value
                opposing_wallets.update(item["wallet"] for item in other_group)

        market_value_share = combined_value / market_total_value if market_total_value > 0 else 1.0
        is_market_leader = combined_value >= max(group_values, default=combined_value) - 0.01
        sorted_values = sorted(wallet_values.values(), reverse=True)
        largest_wallet_share = sorted_values[0] / combined_value
        top_three_wallet_share = sum(sorted_values[:3]) / combined_value

        concentration_penalty = clamp(
            max(0.0, largest_wallet_share - 0.35) / 0.65 * 10.0
            + (max(0.0, top_three_wallet_share - 0.80) / 0.20 * 4.0 if wallet_count >= 4 else 0.0),
            0.0,
            14.0,
        )
        overlap_penalty = clamp(
            max(0.0, overlap["average_pair_overlap"] - 0.20) / 0.80 * 10.0 * max(overlap["overlap_pair_coverage"], 0.35),
            0.0,
            10.0,
        )
        conflict_penalty = 0.0
        if opposing_value > 0:
            if market_value_share < 0.50:
                conflict_penalty = clamp(8 + (0.50 - market_value_share) / 0.50 * 7, 0.0, 15.0)
            elif market_value_share < 0.65:
                conflict_penalty = 3 + (0.65 - market_value_share) / 0.15 * 5
            elif market_value_share < 0.80:
                conflict_penalty = (0.80 - market_value_share) / 0.15 * 3

        extreme_price_penalty = 0.0
        if average_current_price >= 0.995:
            extreme_price_penalty = 18.0
        elif average_current_price >= 0.98:
            extreme_price_penalty = 14.0
        elif average_current_price >= 0.95:
            extreme_price_penalty = 10.0
        elif average_current_price >= 0.90:
            extreme_price_penalty = 5.0
        elif average_current_price <= 0.01:
            extreme_price_penalty = 10.0
        elif average_current_price <= 0.03:
            extreme_price_penalty = 7.0

        market_type = classify_market_type(title)
        if market_type == "EXACT_SCORE" and normalize_text(outcome) == "no" and average_current_price >= 0.90:
            extreme_price_penalty = clamp(extreme_price_penalty + 4, 0.0, 20.0)

        remaining_upside = max(1.0 - average_current_price, 0.0)
        if remaining_upside >= 0.20:
            low_upside_penalty = 0.0
        elif remaining_upside >= 0.12:
            low_upside_penalty = (0.20 - remaining_upside) / 0.08 * 3
        elif remaining_upside >= 0.07:
            low_upside_penalty = 3 + (0.12 - remaining_upside) / 0.05 * 5
        elif remaining_upside >= 0.03:
            low_upside_penalty = 8 + (0.07 - remaining_upside) / 0.04 * 5
        else:
            low_upside_penalty = 15.0

        if observed_price_move <= 0.12:
            chase_penalty = 0.0
        elif observed_price_move <= 0.18:
            chase_penalty = (observed_price_move - 0.12) / 0.06 * 3
        elif observed_price_move <= 0.30:
            chase_penalty = 3 + (observed_price_move - 0.18) / 0.12 * 6
        else:
            chase_penalty = clamp(9 + (observed_price_move - 0.30) * 20, 0.0, 14.0)

        completeness = 30.0
        if metadata:
            completeness += 20.0
            if metadata.get("game_start_time"):
                completeness += 5.0
        completeness += clamp(overlap["overlap_pair_coverage"] * 15.0, 0.0, 15.0)
        completeness += clamp(sample_size / 20.0 * 15.0, 0.0, 15.0)
        if consensus_record:
            completeness += 10.0
        if combined_value > 0:
            completeness += 5.0
        completeness = clamp(completeness)
        if completeness >= 85:
            data_confidence = "VERY HIGH"
        elif completeness >= 70:
            data_confidence = "HIGH"
        elif completeness >= 55:
            data_confidence = "MEDIUM"
        elif completeness >= 40:
            data_confidence = "LOW"
        else:
            data_confidence = "VERY LOW"

        components = {
            "conviction": conviction_score,
            "wallet_quality": wallet_quality_component,
            "consensus": consensus_component,
            "capital": capital_score(combined_value),
            "profitability": profitability_component,
            "backtest": backtest_component,
            "momentum": momentum_score(observed_price_move),
            "timing": timing_score(lifecycle_status, seconds_to_start),
            "freshness": freshness_score(signal_observed_at),
        }
        base_score = sum(components[name] * weight for name, weight in SCORE_WEIGHTS.items())
        total_penalty = (
            concentration_penalty
            + overlap_penalty
            + conflict_penalty
            + extreme_price_penalty
            + low_upside_penalty
            + chase_penalty
        )
        final_score = round(clamp(base_score - total_penalty), 1)
        tier, grade = grade_from_score(final_score)

        if normalize_text(lifecycle_status) in LIVE_STATUSES:
            recommended_action = "LIVE REVIEW REQUIRED" if final_score >= 82 else "PASS - EVENT ALREADY STARTED"
        elif not is_market_leader:
            recommended_action = "PASS - OPPOSING SIDE LEADS"
        elif average_current_price >= 0.98:
            recommended_action = "PASS - MINIMAL UPSIDE"
        elif observed_price_move >= 0.18:
            recommended_action = "WAIT - POSSIBLE CHASE RISK"
        elif total_penalty >= 22:
            recommended_action = "PASS - RISK PENALTIES TOO HIGH"
        elif seconds_to_start is not None and seconds_to_start / 60 <= 5:
            recommended_action = "PASS - TOO CLOSE TO START"
        elif data_confidence in {"VERY LOW", "LOW"}:
            recommended_action = "RESEARCH - DATA INCOMPLETE" if final_score >= 73 else "WATCH - DATA INCOMPLETE"
        elif grade == "S+":
            recommended_action = "ELITE RESEARCH PRIORITY"
        elif grade == "S":
            recommended_action = "HIGH-PRIORITY REVIEW"
        elif grade == "A+":
            recommended_action = "QUALIFIED RESEARCH"
        elif grade == "A":
            recommended_action = "MONITOR FOR CONFIRMATION"
        elif grade == "B":
            recommended_action = "WATCHLIST"
        else:
            recommended_action = "PASS"

        explanation = {
            "model_version": "2.0",
            "score_weights": SCORE_WEIGHTS,
            "components": {key: round(value, 2) for key, value in components.items()},
            "penalties": {
                "concentration": round(concentration_penalty, 2),
                "portfolio_overlap": round(overlap_penalty, 2),
                "opposing_signal": round(conflict_penalty, 2),
                "extreme_price": round(extreme_price_penalty, 2),
                "low_upside": round(low_upside_penalty, 2),
                "chase_risk": round(chase_penalty, 2),
            },
        }

        opportunities.append({
            "opportunity_key": f"{market_id}:{normalized_outcome}",
            "market_id": market_id,
            "title": title,
            "outcome": outcome,
            "opportunity_score": final_score,
            "opportunity_tier": tier,
            "opportunity_grade": grade,
            "recommended_action": recommended_action,
            "wallet_count": wallet_count,
            "average_wallet_quality": round(average_wallet_quality, 2),
            "combined_current_value": combined_value,
            "combined_open_pnl": combined_pnl,
            "open_pnl_ratio": signal_pnl_ratio,
            "average_entry_price": average_entry_price,
            "average_current_price": average_current_price,
            "observed_price_move": observed_price_move,
            "average_wallet_concentration": mean(concentrations),
            "conviction_score": round(conviction_score, 2),
            "consensus_component": round(consensus_component, 2),
            "wallet_quality_component": round(wallet_quality_component, 2),
            "capital_component": round(components["capital"], 2),
            "profitability_component": round(profitability_component, 2),
            "momentum_component": round(components["momentum"], 2),
            "timing_component": round(components["timing"], 2),
            "freshness_component": round(components["freshness"], 2),
            "concentration_penalty": round(concentration_penalty, 2),
            "lifecycle_status": lifecycle_status,
            "game_start_time": clean_text((metadata or {}).get("game_start_time")),
            "seconds_to_start": seconds_to_start,
            "is_pregame": safe_int((metadata or {}).get("is_pregame")),
            "is_live": safe_int((metadata or {}).get("is_live")),
            "is_ended": safe_int((metadata or {}).get("is_ended")),
            "is_closed": safe_int((metadata or {}).get("is_closed")),
            "is_resolved": safe_int((metadata or {}).get("is_resolved")),
            "score": clean_text((metadata or {}).get("score")),
            "period": clean_text((metadata or {}).get("period")),
            "elapsed": clean_text((metadata or {}).get("elapsed")),
            "signal_observed_at": signal_observed_at,
            "metadata_updated_at": clean_text((metadata or {}).get("updated_at")),
            "explanation_json": json.dumps(explanation, ensure_ascii=False),
            "calculated_at": calculated_at,
            "updated_at": calculated_at,
            "market_type": market_type,
            "weighted_wallet_quality": round(weighted_wallet_quality, 2),
            "average_dna_score": round(mean(safe_float(next(item["profile"].get("dna_score") for item in group if item["wallet"] == wallet)) for wallet in wallets), 2),
            "weighted_dna_score": round(weighted_dna, 2),
            "average_leader_score": round(mean(safe_float(next(item["profile"].get("leader_score") for item in group if item["wallet"] == wallet)) for wallet in wallets), 2),
            "weighted_leader_score": round(weighted_leader, 2),
            "average_activity_score": round(average_activity, 2),
            "profitable_wallet_rate": profitable_wallet_rate,
            "elite_wallet_count": elite_wallet_count,
            "elite_wallet_value": elite_wallet_value,
            "elite_wallet_value_share": elite_wallet_value / combined_value if combined_value > 0 else 0.0,
            "largest_wallet_share": largest_wallet_share,
            "top_three_wallet_share": top_three_wallet_share,
            "effective_wallet_count": round(effective_wallet_count, 2),
            "average_pair_overlap": overlap["average_pair_overlap"],
            "portfolio_independence_score": overlap["portfolio_independence_score"],
            "overlap_pair_coverage": overlap["overlap_pair_coverage"],
            "opposing_wallet_count": len(opposing_wallets),
            "opposing_value": opposing_value,
            "market_total_value": market_total_value,
            "market_value_share": market_value_share,
            "conflict_ratio": 1.0 - market_value_share,
            "backtest_sample_size": sample_size,
            "backtest_win_rate": win_rate,
            "backtest_average_return": avg_return,
            "backtest_component": round(backtest_component, 2),
            "data_completeness_score": round(completeness, 2),
            "data_confidence": data_confidence,
            "overlap_penalty": round(overlap_penalty, 2),
            "conflict_penalty": round(conflict_penalty, 2),
            "extreme_price_penalty": round(extreme_price_penalty, 2),
            "low_upside_penalty": round(low_upside_penalty, 2),
            "chase_penalty": round(chase_penalty, 2),
            "stale_penalty": 0.0,
            "total_penalty": round(total_penalty, 2),
            "remaining_upside": remaining_upside,
            "is_market_leader": int(is_market_leader),
            "wallets_json": json.dumps(sorted(wallet_payload, key=lambda item: item["current_value"], reverse=True), ensure_ascii=False),
        })

    opportunities.sort(
        key=lambda item: (
            item["opportunity_score"],
            item["is_market_leader"],
            item["data_completeness_score"],
            item["effective_wallet_count"],
            item["combined_current_value"],
        ),
        reverse=True,
    )
    return opportunities


def save_opportunities(opportunities: list[dict[str, Any]]) -> tuple[int, int]:
    connection = connect_database()
    try:
        current_columns = table_columns(connection, "opportunity_scores")
        history_columns = table_columns(connection, "opportunity_score_history")
        connection.execute("BEGIN IMMEDIATE")
        active_keys = [item["opportunity_key"] for item in opportunities]
        if active_keys:
            placeholders = ", ".join("?" for _ in active_keys)
            connection.execute(
                f"DELETE FROM opportunity_scores WHERE opportunity_key NOT IN ({placeholders})",
                active_keys,
            )
        else:
            connection.execute("DELETE FROM opportunity_scores")

        current_saved = 0
        history_saved = 0
        if opportunities:
            current_payload_columns = [column for column in opportunities[0] if column in current_columns]
            history_payload_columns = [column for column in opportunities[0] if column in history_columns]
            current_query = (
                f"INSERT INTO opportunity_scores ({', '.join(f'\"{c}\"' for c in current_payload_columns)}) "
                f"VALUES ({', '.join('?' for _ in current_payload_columns)}) "
                f"ON CONFLICT(opportunity_key) DO UPDATE SET "
                + ", ".join(f'\"{c}\"=excluded.\"{c}\"' for c in current_payload_columns if c != "opportunity_key")
            )
            history_query = (
                f"INSERT INTO opportunity_score_history ({', '.join(f'\"{c}\"' for c in history_payload_columns)}) "
                f"VALUES ({', '.join('?' for _ in history_payload_columns)})"
            )
            for item in opportunities:
                connection.execute(current_query, tuple(item[column] for column in current_payload_columns))
                current_saved += 1
                connection.execute(history_query, tuple(item[column] for column in history_payload_columns))
                history_saved += 1
        connection.commit()
        return current_saved, history_saved
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def display_readiness() -> None:
    connection = connect_database()
    try:
        print()
        print("=" * 108)
        print("OPPORTUNITY DATA READINESS")
        print("=" * 108)
        for table_name in (
            "wallet_scans",
            "positions",
            "wallet_profiles",
            "portfolio_overlap",
            "consensus_history",
            "market_metadata",
            "backtest_results",
            "opportunity_scores",
            "opportunity_score_history",
        ):
            if table_exists(connection, table_name):
                print(f"{table_name:<40}{table_row_count(connection, table_name):>12} rows")
            else:
                print(f"{table_name:<40}{'NOT FOUND':>12}")
        print("=" * 108)
    finally:
        connection.close()


def display_summary(opportunities: list[dict[str, Any]], current_saved: int, history_saved: int) -> None:
    grade_counts: dict[str, int] = defaultdict(int)
    for item in opportunities:
        grade_counts[item["opportunity_grade"]] += 1
    print()
    print("=" * 108)
    print("OPPORTUNITY INTELLIGENCE SUMMARY")
    print("=" * 108)
    print(f"Opportunities calculated:       {len(opportunities)}")
    print(f"Market-leading outcomes:        {sum(item['is_market_leader'] for item in opportunities)}")
    print(f"Elite S+:                       {grade_counts['S+']}")
    print(f"S or better:                    {grade_counts['S+'] + grade_counts['S']}")
    print(f"A or better:                    {sum(grade_counts[g] for g in ('S+', 'S', 'A+', 'A'))}")
    print(f"Current signal value:           {format_money(sum(item['combined_current_value'] for item in opportunities))}")
    print(f"Current rows saved:             {current_saved}")
    print(f"History rows saved:             {history_saved}")
    print("=" * 108)


def display_opportunity(rank: int, item: dict[str, Any]) -> None:
    print()
    print("-" * 108)
    print(f"{rank}. {item['title']}")
    print("-" * 108)
    print(f"Outcome:                        {item['outcome']}")
    print(f"Market type:                    {item['market_type']}")
    print(f"Opportunity score:              {item['opportunity_score']:.1f}/100")
    print(f"Tier / grade:                   {item['opportunity_tier']} / {item['opportunity_grade']}")
    print(f"Recommended action:             {item['recommended_action']}")
    print(f"Data confidence:                {item['data_confidence']} ({item['data_completeness_score']:.1f}/100)")
    print(f"Wallets / effective wallets:    {item['wallet_count']} / {item['effective_wallet_count']:.2f}")
    print(f"Average wallet quality:         {item['average_wallet_quality']:.1f}")
    print(f"Weighted wallet quality:        {item['weighted_wallet_quality']:.1f}")
    print(f"Portfolio independence:         {item['portfolio_independence_score']:.1f}/100")
    print(f"Combined current value:         {format_money(item['combined_current_value'])}")
    print(f"Combined open PnL:              {format_signed_money(item['combined_open_pnl'])}")
    print(f"Signal PnL ratio:               {format_percentage(item['open_pnl_ratio'])}")
    print(f"Opposing value:                 {format_money(item['opposing_value'])}")
    print(f"Backtest sample size:           {item['backtest_sample_size']}")
    print(f"Backtest win rate:              {format_percentage(item['backtest_win_rate'])}")
    print(f"Lifecycle status:               {item['lifecycle_status']}")
    print(f"T-minus:                        {format_t_minus(item['seconds_to_start'])}")
    print(f"Total penalties:                -{item['total_penalty']:.1f}")


def main() -> None:
    configure_utf8_output()
    print()
    print("=" * 108)
    print("POLYMARKET OPPORTUNITY INTELLIGENCE ENGINE v2")
    print("=" * 108)
    print(f"Database: {DATABASE_PATH}")
    create_or_migrate_opportunity_tables()
    display_readiness()
    opportunities = calculate_opportunities()
    if not opportunities:
        print("No eligible current opportunities were found.")
        return
    current_saved, history_saved = save_opportunities(opportunities)
    display_summary(opportunities, current_saved, history_saved)
    print()
    print("TOP OPPORTUNITIES")
    for rank, item in enumerate(opportunities[:TOP_RESULTS_TO_DISPLAY], start=1):
        display_opportunity(rank, item)
    print()
    print("=" * 108)
    print("OPPORTUNITY INTELLIGENCE ENGINE v2 COMPLETE")
    print("=" * 108)
    print("Current wallet-level rankings were saved to opportunity_scores.")
    print("Historical snapshots were saved to opportunity_score_history.")
    print("Zero-value, inactive and stale dated markets were excluded.")
    print("The score is a research ranking, not a calibrated win probability.")
    print("AI Research remains separate and was not used.")
    print("=" * 108)


if __name__ == "__main__":
    main()