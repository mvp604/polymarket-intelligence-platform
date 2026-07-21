#!/usr/bin/env python3
"""
Polymarket Intelligence Platform
Institutional Trust Engine v2.0

Builds an auditable trust profile for each qualified wallet using the consolidated
elite-wallet intelligence layer. The engine separates the trust score from the
confidence in that score and produces a bounded multiplier for downstream
consensus weighting.

Default mode is DRY RUN. Use --apply to persist current profiles and history.
Run metadata is recorded in both modes when the database is available.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
METHODOLOGY_VERSION = "2.0"
SOURCE_TABLE = "elite_wallet_rankings"
PROFILE_TABLE = "wallet_trust_profiles"
HISTORY_TABLE = "wallet_trust_history"
RUNS_TABLE = "wallet_trust_runs"
DEFAULT_WALLET_LIMIT = 100
DEFAULT_MIN_TRUST_INPUT_SCORE = 45.0
DEFAULT_DISPLAY_LIMIT = 20


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def configure_utf8_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def normalize_ratio(value: Any) -> float:
    number = safe_float(value)
    if abs(number) <= 1.0:
        number *= 100.0
    return clamp(number)


def weighted_average(items: Iterable[tuple[float, float]]) -> float:
    values = [(safe_float(v), safe_float(w)) for v, w in items if safe_float(w) > 0]
    total_weight = sum(weight for _, weight in values)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in values) / total_weight


def connect() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    connection = sqlite3.connect(DATABASE_PATH, timeout=60.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 60000")
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in connection.execute(f'PRAGMA table_info("{table_name}")')}


def create_tables() -> None:
    connection = connect()
    try:
        connection.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS {PROFILE_TABLE} (
                wallet TEXT PRIMARY KEY,
                username TEXT,
                trust_score REAL NOT NULL DEFAULT 0,
                trust_grade TEXT NOT NULL DEFAULT 'UNRATED',
                historical_reliability REAL NOT NULL DEFAULT 0,
                performance_quality REAL NOT NULL DEFAULT 0,
                behavioral_discipline REAL NOT NULL DEFAULT 0,
                predictive_timing REAL NOT NULL DEFAULT 0,
                leadership_score REAL NOT NULL DEFAULT 0,
                market_influence_score REAL NOT NULL DEFAULT 0,
                evidence_quality REAL NOT NULL DEFAULT 0,
                recent_activity_score REAL NOT NULL DEFAULT 0,
                consensus_multiplier REAL NOT NULL DEFAULT 1,
                confidence REAL NOT NULL DEFAULT 0,
                confidence_grade TEXT NOT NULL DEFAULT 'VERY LOW',
                warning_flags TEXT,
                strengths_json TEXT,
                explanation TEXT,
                source_elite_rank INTEGER,
                source_elite_tier TEXT,
                source_influence_score REAL NOT NULL DEFAULT 0,
                source_calculated_at TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                methodology_version TEXT NOT NULL DEFAULT '{METHODOLOGY_VERSION}'
            );

            CREATE INDEX IF NOT EXISTS idx_wallet_trust_score
                ON {PROFILE_TABLE}(trust_score DESC, confidence DESC);
            CREATE INDEX IF NOT EXISTS idx_wallet_trust_multiplier
                ON {PROFILE_TABLE}(consensus_multiplier DESC);

            CREATE TABLE IF NOT EXISTS {HISTORY_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                wallet TEXT NOT NULL,
                trust_score REAL NOT NULL,
                consensus_multiplier REAL NOT NULL,
                trust_grade TEXT NOT NULL,
                confidence REAL NOT NULL,
                confidence_grade TEXT NOT NULL,
                calculated_at TEXT NOT NULL,
                methodology_version TEXT NOT NULL,
                FOREIGN KEY(wallet) REFERENCES {PROFILE_TABLE}(wallet)
                    ON UPDATE CASCADE ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_wallet_trust_history_wallet_time
                ON {HISTORY_TABLE}(wallet, calculated_at DESC);

            CREATE TABLE IF NOT EXISTS {RUNS_TABLE} (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                mode TEXT NOT NULL,
                methodology_version TEXT NOT NULL,
                wallet_limit INTEGER NOT NULL,
                min_trust_input_score REAL NOT NULL,
                wallets_selected INTEGER NOT NULL DEFAULT 0,
                wallets_analyzed INTEGER NOT NULL DEFAULT 0,
                wallets_skipped INTEGER NOT NULL DEFAULT 0,
                profiles_saved INTEGER NOT NULL DEFAULT 0,
                history_saved INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                duration_seconds REAL NOT NULL DEFAULT 0,
                error_message TEXT
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


@dataclass(frozen=True)
class TrustProfile:
    wallet: str
    username: str | None
    trust_score: float
    trust_grade: str
    historical_reliability: float
    performance_quality: float
    behavioral_discipline: float
    predictive_timing: float
    leadership_score: float
    market_influence_score: float
    evidence_quality: float
    recent_activity_score: float
    consensus_multiplier: float
    confidence: float
    confidence_grade: str
    warning_flags: str
    strengths_json: str
    explanation: str
    source_elite_rank: int
    source_elite_tier: str
    source_influence_score: float
    source_calculated_at: str | None
    calculated_at: str
    updated_at: str
    methodology_version: str = METHODOLOGY_VERSION

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def grade_for_trust(score: float, confidence: float) -> str:
    # High trust cannot receive an institutional grade without adequate evidence.
    if score >= 92 and confidence >= 75:
        return "S+"
    if score >= 86 and confidence >= 65:
        return "S"
    if score >= 79 and confidence >= 55:
        return "A+"
    if score >= 71:
        return "A"
    if score >= 63:
        return "B+"
    if score >= 54:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def confidence_grade(score: float) -> str:
    if score >= 85:
        return "VERY HIGH"
    if score >= 70:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    if score >= 30:
        return "LOW"
    return "VERY LOW"


def row_value(row: sqlite3.Row, key: str, default: Any = 0) -> Any:
    return row[key] if key in row.keys() and row[key] is not None else default


def calculate_components(row: sqlite3.Row) -> dict[str, float]:
    win_rate = normalize_ratio(row_value(row, "win_rate"))
    realized_roi = safe_float(row_value(row, "realized_roi"))
    total_roi = safe_float(row_value(row, "total_roi"))
    positive_roi_score = clamp(50.0 + realized_roi * 100.0)
    total_roi_score = clamp(50.0 + total_roi * 100.0)

    performance_score = safe_float(row_value(row, "performance_score"), 50.0)
    alpha_score = safe_float(row_value(row, "alpha_score"), 50.0)
    consistency = safe_float(row_value(row, "consistency_score"), 50.0)
    risk_adjusted = safe_float(row_value(row, "risk_adjusted_score"), 50.0)
    calibration = safe_float(row_value(row, "calibration_score"), 50.0)
    timing = safe_float(row_value(row, "timing_score"), 50.0)
    entry = safe_float(row_value(row, "entry_quality_score"), timing)
    exit_quality = safe_float(row_value(row, "exit_quality_score"), timing)
    independence = safe_float(row_value(row, "portfolio_independence_score"), 50.0)
    conviction = safe_float(row_value(row, "conviction_score"), 50.0)
    specialization = safe_float(row_value(row, "specialization_score"), 50.0)
    influence = safe_float(row_value(row, "influence_score"), 50.0)
    research_weight = safe_float(row_value(row, "overall_research_weight"), 1.0)
    ledger_quality = safe_float(row_value(row, "ledger_quality_score"), 0.0)
    sample_size = safe_float(row_value(row, "sample_size_score"), 0.0)
    recency = safe_float(row_value(row, "recency_score"), 0.0)
    activity = safe_float(row_value(row, "activity_score"), 0.0)

    resolved = safe_int(row_value(row, "resolved_positions"))
    closed_count = safe_int(row_value(row, "closed_position_count"))
    trade_count = safe_int(row_value(row, "trade_event_count"))
    open_count = safe_int(row_value(row, "open_position_count"))
    evidence_events = max(resolved, closed_count) + min(trade_count, 250) * 0.20 + min(open_count, 100) * 0.05
    event_score = clamp(math.log1p(max(evidence_events, 0)) / math.log(101) * 100.0)

    historical_reliability = weighted_average([
        (win_rate, 0.28), (consistency, 0.24), (calibration, 0.18),
        (positive_roi_score, 0.15), (sample_size, 0.15),
    ])
    performance_quality = weighted_average([
        (performance_score, 0.34), (alpha_score, 0.24),
        (risk_adjusted, 0.18), (positive_roi_score, 0.12),
        (total_roi_score, 0.12),
    ])
    behavioral_discipline = weighted_average([
        (risk_adjusted, 0.30), (consistency, 0.25), (independence, 0.20),
        (conviction, 0.15), (calibration, 0.10),
    ])
    predictive_timing = weighted_average([
        (timing, 0.45), (entry, 0.30), (exit_quality, 0.15), (alpha_score, 0.10),
    ])
    leadership = weighted_average([
        (influence, 0.42), (alpha_score, 0.22), (specialization, 0.16),
        (independence, 0.10), (conviction, 0.10),
    ])
    market_influence = clamp(influence * 0.70 + clamp((research_weight - 0.5) / 1.5 * 100.0) * 0.30)
    evidence_quality = weighted_average([
        (ledger_quality, 0.34), (sample_size, 0.28), (event_score, 0.24),
        (safe_float(row_value(row, "alpha_confidence"), 0.0), 0.14),
    ])
    recent_activity = weighted_average([(recency, 0.55), (activity, 0.45)])

    return {
        "historical_reliability": clamp(historical_reliability),
        "performance_quality": clamp(performance_quality),
        "behavioral_discipline": clamp(behavioral_discipline),
        "predictive_timing": clamp(predictive_timing),
        "leadership_score": clamp(leadership),
        "market_influence_score": clamp(market_influence),
        "evidence_quality": clamp(evidence_quality),
        "recent_activity_score": clamp(recent_activity),
        "event_score": event_score,
    }


def build_profile(row: sqlite3.Row, calculated_at: str) -> TrustProfile:
    components = calculate_components(row)

    base_score = weighted_average([
        (components["historical_reliability"], 0.20),
        (components["performance_quality"], 0.20),
        (components["behavioral_discipline"], 0.14),
        (components["predictive_timing"], 0.13),
        (components["leadership_score"], 0.10),
        (components["market_influence_score"], 0.08),
        (components["evidence_quality"], 0.10),
        (components["recent_activity_score"], 0.05),
    ])

    flags: list[str] = []
    strengths: list[str] = []
    penalty = 0.0

    resolved = safe_int(row_value(row, "resolved_positions"))
    trades = safe_int(row_value(row, "trade_event_count"))
    total_pnl = safe_float(row_value(row, "total_estimated_pnl"))
    total_penalty = safe_float(row_value(row, "total_penalty"))
    alpha_confidence = text(row_value(row, "alpha_confidence", "VERY LOW")).upper()
    ledger_confidence = text(row_value(row, "ledger_confidence", "VERY LOW")).upper()

    if resolved < 10:
        flags.append("LOW_RESOLVED_SAMPLE")
        penalty += 4.0
    if trades < 20:
        flags.append("LOW_TRADE_EVIDENCE")
        penalty += 2.5
    if total_pnl < 0:
        flags.append("NEGATIVE_ESTIMATED_PNL")
        penalty += min(8.0, 2.0 + math.log10(abs(total_pnl) + 1.0))
    if components["recent_activity_score"] < 35:
        flags.append("STALE_OR_LOW_ACTIVITY")
        penalty += 2.0
    if components["behavioral_discipline"] < 45:
        flags.append("WEAK_BEHAVIORAL_DISCIPLINE")
        penalty += 3.0
    if total_penalty > 8:
        flags.append("SOURCE_MODEL_PENALTIES")
        penalty += min(4.0, total_penalty * 0.20)

    if components["historical_reliability"] >= 75:
        strengths.append("STRONG_HISTORICAL_RELIABILITY")
    if components["performance_quality"] >= 75:
        strengths.append("STRONG_PERFORMANCE_QUALITY")
    if components["predictive_timing"] >= 75:
        strengths.append("STRONG_PREDICTIVE_TIMING")
    if components["leadership_score"] >= 75:
        strengths.append("MARKET_LEADERSHIP")
    if components["evidence_quality"] >= 75:
        strengths.append("HIGH_EVIDENCE_QUALITY")

    trust_score = clamp(base_score - penalty)

    confidence = weighted_average([
        (components["evidence_quality"], 0.50),
        (components["event_score"], 0.20),
        (safe_float(row_value(row, "sample_size_score")), 0.15),
        (100.0 if alpha_confidence in {"HIGH", "VERY HIGH"} else 65.0 if alpha_confidence == "MEDIUM" else 30.0, 0.08),
        (100.0 if ledger_confidence in {"HIGH", "VERY HIGH"} else 65.0 if ledger_confidence == "MEDIUM" else 30.0, 0.07),
    ])
    confidence = clamp(confidence)
    trust_grade = grade_for_trust(trust_score, confidence)

    # Shrink the score toward neutral when evidence is weak, then map to a
    # conservative 0.55-1.50 downstream influence range.
    evidence_factor = 0.35 + 0.65 * (confidence / 100.0)
    effective_score = 50.0 + (trust_score - 50.0) * evidence_factor
    multiplier = clamp(1.0 + (effective_score - 50.0) / 100.0, 0.55, 1.50)
    if "NEGATIVE_ESTIMATED_PNL" in flags:
        multiplier = max(0.55, multiplier - 0.05)
    if confidence < 30:
        multiplier = min(multiplier, 1.05)

    explanation = (
        f"Trust {trust_score:.1f}/100 ({trust_grade}) with {confidence:.1f}% "
        f"confidence. Reliability {components['historical_reliability']:.1f}, "
        f"performance {components['performance_quality']:.1f}, discipline "
        f"{components['behavioral_discipline']:.1f}, timing "
        f"{components['predictive_timing']:.1f}, evidence "
        f"{components['evidence_quality']:.1f}. Consensus influence is "
        f"bounded at {multiplier:.3f}x and shrunk toward neutral when evidence is limited."
    )

    return TrustProfile(
        wallet=text(row_value(row, "wallet")),
        username=text(row_value(row, "username")) or None,
        trust_score=round(trust_score, 4),
        trust_grade=trust_grade,
        historical_reliability=round(components["historical_reliability"], 4),
        performance_quality=round(components["performance_quality"], 4),
        behavioral_discipline=round(components["behavioral_discipline"], 4),
        predictive_timing=round(components["predictive_timing"], 4),
        leadership_score=round(components["leadership_score"], 4),
        market_influence_score=round(components["market_influence_score"], 4),
        evidence_quality=round(components["evidence_quality"], 4),
        recent_activity_score=round(components["recent_activity_score"], 4),
        consensus_multiplier=round(multiplier, 4),
        confidence=round(confidence, 4),
        confidence_grade=confidence_grade(confidence),
        warning_flags=json.dumps(flags, separators=(",", ":")),
        strengths_json=json.dumps(strengths, separators=(",", ":")),
        explanation=explanation,
        source_elite_rank=safe_int(row_value(row, "elite_rank")),
        source_elite_tier=text(row_value(row, "elite_tier", "UNRATED")),
        source_influence_score=round(safe_float(row_value(row, "influence_score")), 4),
        source_calculated_at=text(row_value(row, "calculated_at")) or None,
        calculated_at=calculated_at,
        updated_at=calculated_at,
    )


def validate_source(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, SOURCE_TABLE):
        raise RuntimeError(f"Required table {SOURCE_TABLE} is missing. Run elite_wallet_ranking_engine.py first.")
    columns = table_columns(connection, SOURCE_TABLE)
    required = {"wallet", "influence_score"}
    missing = sorted(required - columns)
    if missing:
        raise RuntimeError(f"{SOURCE_TABLE} is missing required columns: {', '.join(missing)}")
    count = connection.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLE}").fetchone()[0]
    if count == 0:
        raise RuntimeError(f"{SOURCE_TABLE} is empty. Run elite_wallet_ranking_engine.py first.")


def load_wallets(wallet_limit: int, min_score: float) -> list[sqlite3.Row]:
    connection = connect()
    try:
        validate_source(connection)
        return connection.execute(
            f"""
            SELECT *
            FROM {SOURCE_TABLE}
            WHERE COALESCE(influence_score, 0) >= ?
            ORDER BY influence_score DESC, elite_rank ASC, wallet ASC
            LIMIT ?
            """,
            (min_score, wallet_limit),
        ).fetchall()
    finally:
        connection.close()


def start_run(run_id: str, args: argparse.Namespace, mode: str) -> datetime:
    started = utc_now()
    connection = connect()
    try:
        connection.execute(
            f"""
            INSERT INTO {RUNS_TABLE} (
                run_id, started_at, mode, methodology_version,
                wallet_limit, min_trust_input_score, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'RUNNING')
            """,
            (run_id, started.isoformat(timespec="seconds"), mode,
             METHODOLOGY_VERSION, args.wallet_limit, args.min_trust_input_score),
        )
        connection.commit()
    finally:
        connection.close()
    return started


def finish_run(run_id: str, started: datetime, status: str, selected: int,
               analyzed: int, skipped: int, profiles_saved: int,
               history_saved: int, error_message: str | None = None) -> None:
    finished = utc_now()
    duration = (finished - started).total_seconds()
    connection = connect()
    try:
        connection.execute(
            f"""
            UPDATE {RUNS_TABLE}
            SET finished_at=?, wallets_selected=?, wallets_analyzed=?,
                wallets_skipped=?, profiles_saved=?, history_saved=?,
                status=?, duration_seconds=?, error_message=?
            WHERE run_id=?
            """,
            (finished.isoformat(timespec="seconds"), selected, analyzed, skipped,
             profiles_saved, history_saved, status, duration, error_message, run_id),
        )
        connection.commit()
    finally:
        connection.close()


def save_profiles(profiles: list[TrustProfile], run_id: str) -> tuple[int, int]:
    if not profiles:
        return 0, 0
    columns = list(profiles[0].as_dict().keys())
    names = ", ".join(f'"{name}"' for name in columns)
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(
        f'"{name}"=excluded."{name}"' for name in columns if name != "wallet"
    )
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        for profile in profiles:
            data = profile.as_dict()
            connection.execute(
                f"INSERT INTO {PROFILE_TABLE} ({names}) VALUES ({placeholders}) "
                f"ON CONFLICT(wallet) DO UPDATE SET {updates}",
                tuple(data[column] for column in columns),
            )
            connection.execute(
                f"""
                INSERT INTO {HISTORY_TABLE} (
                    run_id, wallet, trust_score, consensus_multiplier,
                    trust_grade, confidence, confidence_grade,
                    calculated_at, methodology_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, profile.wallet, profile.trust_score,
                 profile.consensus_multiplier, profile.trust_grade,
                 profile.confidence, profile.confidence_grade,
                 profile.calculated_at, profile.methodology_version),
            )
        connection.commit()
        return len(profiles), len(profiles)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def display_report(profiles: list[TrustProfile], args: argparse.Namespace,
                   run_id: str, mode: str, duration: float,
                   profiles_saved: int, history_saved: int) -> None:
    print()
    print("=" * 116)
    print("POLYMARKET INSTITUTIONAL TRUST ENGINE v2.0")
    print("=" * 116)
    print(f"Database:                         {DATABASE_PATH}")
    print(f"Mode:                             {mode}")
    print(f"Run ID:                           {run_id}")
    print(f"Methodology:                      {METHODOLOGY_VERSION}")
    print(f"Minimum input influence score:    {args.min_trust_input_score:.1f}")
    print(f"Wallet limit:                     {args.wallet_limit}")
    print(f"Wallets analyzed:                 {len(profiles)}")
    print(f"Profiles saved:                   {profiles_saved}")
    print(f"History saved:                    {history_saved}")
    print(f"Duration:                         {duration:.3f}s")
    print("=" * 116)

    if not profiles:
        print("No wallets met the input threshold.")
        return

    print()
    print("RANKED TRUST PROFILES")
    print("-" * 116)
    for index, profile in enumerate(profiles[: max(1, args.display_limit)], start=1):
        flags = json.loads(profile.warning_flags or "[]")
        print(
            f"{index:>3}. {profile.trust_grade:<3} trust={profile.trust_score:>6.2f} "
            f"confidence={profile.confidence:>6.2f}% multiplier={profile.consensus_multiplier:>5.3f} "
            f"{profile.username or profile.wallet}"
        )
        print(f"     {profile.wallet}")
        print(
            "     reliability/performance/discipline/timing="
            f"{profile.historical_reliability:.1f}/{profile.performance_quality:.1f}/"
            f"{profile.behavioral_discipline:.1f}/{profile.predictive_timing:.1f} | "
            f"evidence={profile.evidence_quality:.1f} activity={profile.recent_activity_score:.1f}"
        )
        if flags:
            print("     warnings=" + ", ".join(flags))

    print()
    print("=" * 116)
    if mode == "DRY RUN":
        print("Dry run complete. No trust profiles or history snapshots were changed.")
        print("Review the ranking, then rerun with --apply to persist the results.")
    else:
        print(f"Current profiles: {PROFILE_TABLE}")
        print(f"Historical snapshots: {HISTORY_TABLE}")
    print("Consensus multipliers are research weights, not position-sizing instructions.")
    print("=" * 116)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build inspectable wallet trust profiles for weighted consensus."
    )
    parser.add_argument("--wallet-limit", type=int, default=DEFAULT_WALLET_LIMIT)
    parser.add_argument(
        "--min-trust-input-score", type=float,
        default=DEFAULT_MIN_TRUST_INPUT_SCORE,
        help="Minimum elite influence_score required for analysis.",
    )
    parser.add_argument("--display-limit", type=int, default=DEFAULT_DISPLAY_LIMIT)
    parser.add_argument("--apply", action="store_true", help="Persist profiles and history.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Explicitly select dry-run mode (the default).",
    )
    return parser.parse_args()


def main() -> None:
    configure_utf8_output()
    args = parse_args()
    if args.wallet_limit < 1:
        raise SystemExit("--wallet-limit must be at least 1")
    if args.display_limit < 1:
        raise SystemExit("--display-limit must be at least 1")
    if args.apply and args.dry_run:
        raise SystemExit("Choose either --apply or --dry-run, not both")

    mode = "APPLY" if args.apply else "DRY RUN"
    run_id = uuid.uuid4().hex
    create_tables()
    started = start_run(run_id, args, mode)
    selected = analyzed = skipped = profiles_saved = history_saved = 0
    profiles: list[TrustProfile] = []

    try:
        rows = load_wallets(args.wallet_limit, args.min_trust_input_score)
        selected = len(rows)
        calculated_at = iso_now()
        for row in rows:
            wallet = text(row_value(row, "wallet"))
            if not wallet:
                skipped += 1
                continue
            profiles.append(build_profile(row, calculated_at))
        analyzed = len(profiles)
        profiles.sort(key=lambda p: (p.trust_score, p.confidence, p.consensus_multiplier), reverse=True)

        if args.apply:
            profiles_saved, history_saved = save_profiles(profiles, run_id)

        duration = (utc_now() - started).total_seconds()
        finish_run(run_id, started, "SUCCESS", selected, analyzed, skipped,
                   profiles_saved, history_saved)
        display_report(profiles, args, run_id, mode, duration,
                       profiles_saved, history_saved)
    except Exception as error:
        finish_run(
            run_id, started, "FAILED", selected, analyzed, skipped,
            profiles_saved, history_saved,
            f"{type(error).__name__}: {error}",
        )
        raise


if __name__ == "__main__":
    main()