from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
CONFIG_PATH = PROJECT_ROOT / "config" / "elite_wallet_v2.json"
ENGINE_VERSION = "2.0.0"


@dataclass(frozen=True)
class WalletMetrics:
    wallet: str
    resolved_positions: int
    wins: int
    losses: int
    raw_win_rate: float
    bayesian_win_rate: float
    bayesian_lower_bound: float
    bayesian_upper_bound: float
    raw_roi: float
    trimmed_mean_roi: float
    winsorized_mean_roi: float
    profit_factor: float
    expectancy_per_dollar: float
    outlier_count: int
    unresolved_positions: int
    trust_score: float
    skill_score: float
    repeatability_score: float
    profitability_quality_score: float
    calibration_score: float
    consistency_score: float
    risk_control_score: float
    sample_strength_score: float
    confidence_adjusted_score: float
    data_confidence: float
    confidence_multiplier: float
    influence_weight: float
    elite_tier: str
    overall_grade: str
    eligibility_status: str
    eligibility_reason: str
    consensus_eligible: int
    elite_eligible: int
    strengths_json: str
    warnings_json: str
    explanation_json: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def pct(value: float) -> float:
    return round(value * 100.0, 4)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    }


def require_schema(connection: sqlite3.Connection) -> None:
    required = {
        "elite_wallet_profiles": {
            "wallet",
            "eligibility_status",
            "eligibility_reason",
            "elite_tier",
            "overall_grade",
            "trust_score",
            "skill_score",
            "repeatability_score",
            "profitability_quality_score",
            "calibration_score",
            "consistency_score",
            "risk_control_score",
            "sample_strength_score",
            "confidence_adjusted_score",
            "resolved_positions",
            "wins",
            "losses",
            "raw_win_rate",
            "bayesian_win_rate",
            "bayesian_lower_bound",
            "bayesian_upper_bound",
            "raw_roi",
            "trimmed_mean_roi",
            "winsorized_mean_roi",
            "profit_factor",
            "expectancy_per_dollar",
            "outlier_count",
            "unresolved_positions",
            "data_confidence",
            "confidence_multiplier",
            "influence_weight",
            "consensus_eligible",
            "elite_eligible",
            "strengths_json",
            "warnings_json",
            "explanation_json",
            "engine_version",
            "calculated_at",
            "updated_at",
        },
        "positions": {
            "wallet",
            "cash_pnl",
            "percent_pnl",
            "current_value",
            "market_id",
            "title",
            "outcome",
        },
    }
    failures: list[str] = []
    for table, columns in required.items():
        actual = table_columns(connection, table)
        if not actual:
            failures.append(f"missing table: {table}")
            continue
        for column in sorted(columns - actual):
            failures.append(f"missing column: {table}.{column}")
    if failures:
        raise RuntimeError("; ".join(failures))


def ensure_supporting_schema(connection: sqlite3.Connection) -> None:
    sql_path = PROJECT_ROOT / "migrations" / "elite_wallet_v2_supporting_schema.sql"
    connection.executescript(sql_path.read_text(encoding="utf-8"))


def score_sample_strength(resolved: int, config: dict[str, Any]) -> float:
    target = float(config["sample_size_full_confidence"])
    return clamp((resolved / target) * 100.0)


def bayesian_rate(wins: int, losses: int, prior_wins: float, prior_losses: float) -> float:
    return (wins + prior_wins) / (wins + losses + prior_wins + prior_losses)


def approximate_interval(rate: float, sample: int) -> tuple[float, float]:
    if sample <= 0:
        return 0.0, 1.0
    se = math.sqrt(max(rate * (1.0 - rate), 0.0) / sample)
    return max(0.0, rate - 1.96 * se), min(1.0, rate + 1.96 * se)


def trimmed_mean(values: list[float], proportion: float = 0.1) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    cut = int(len(ordered) * proportion)
    trimmed = ordered[cut:len(ordered) - cut] if len(ordered) - 2 * cut > 0 else ordered
    return sum(trimmed) / len(trimmed)


def winsorized_mean(values: list[float], proportion: float = 0.1) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    cut = int(len(ordered) * proportion)
    if cut == 0:
        return sum(ordered) / len(ordered)
    low = ordered[cut]
    high = ordered[-cut - 1]
    adjusted = [max(low, min(high, value)) for value in ordered]
    return sum(adjusted) / len(adjusted)


def category_from_title(title: str) -> str:
    text = (title or "").lower()
    groups = {
        "Soccer": ("soccer", "football", "fifa", "world cup", "premier league", "champions league"),
        "Basketball": ("nba", "wnba", "basketball", "ncaa"),
        "Baseball": ("mlb", "baseball"),
        "UFC": ("ufc", "mma", "fight"),
        "Politics": ("president", "election", "nomination", "senate", "congress", "governor"),
        "Crypto": ("bitcoin", "ethereum", "crypto", "solana", "btc", "eth"),
        "Economics": ("cpi", "inflation", "fed", "interest rate", "gdp", "unemployment"),
        "Entertainment": ("movie", "oscars", "grammy", "box office", "album"),
    }
    for category, tokens in groups.items():
        if any(token in text for token in tokens):
            return category
    return "Other"


def derive_tier(score: float, sample: float, config: dict[str, Any]) -> tuple[str, str]:
    tiers = config["tiers"]
    for tier in tiers:
        if score >= tier["minimum_score"] and sample >= tier["minimum_sample_strength"]:
            return tier["name"], tier["grade"]
    return "Observation", "PASS"


def compute_metrics(wallet: str, rows: list[sqlite3.Row], config: dict[str, Any]) -> WalletMetrics:
    roi_values = [float(row["percent_pnl"] or 0.0) for row in rows]
    pnl_values = [float(row["cash_pnl"] or 0.0) for row in rows]
    resolved_rows = [row for row in rows if row["cash_pnl"] is not None]
    wins = sum(1 for row in resolved_rows if float(row["cash_pnl"] or 0.0) > 0)
    losses = sum(1 for row in resolved_rows if float(row["cash_pnl"] or 0.0) < 0)
    unresolved = len(rows) - len(resolved_rows)
    resolved = wins + losses

    raw_rate = wins / resolved if resolved else 0.0
    bayes = bayesian_rate(
        wins,
        losses,
        float(config["bayesian_prior_wins"]),
        float(config["bayesian_prior_losses"]),
    )
    lower, upper = approximate_interval(bayes, resolved + int(config["bayesian_prior_wins"] + config["bayesian_prior_losses"]))

    positive = sum(value for value in pnl_values if value > 0)
    negative = abs(sum(value for value in pnl_values if value < 0))
    profit_factor = positive / negative if negative > 0 else (positive if positive > 0 else 0.0)
    total_value = sum(max(float(row["current_value"] or 0.0), 0.0) for row in rows)
    expectancy = sum(pnl_values) / total_value if total_value > 0 else 0.0

    raw_roi = sum(roi_values) / len(roi_values) if roi_values else 0.0
    trim_roi = trimmed_mean(roi_values)
    win_roi = winsorized_mean(roi_values)
    outlier_cutoff = float(config["roi_outlier_absolute_percent"])
    outliers = sum(1 for value in roi_values if abs(value) >= outlier_cutoff)

    sample_strength = score_sample_strength(resolved, config)
    skill = clamp(pct(bayes))
    profitability = clamp(50.0 + win_roi / float(config["roi_score_divisor"]))
    consistency_penalty = min(50.0, (max(roi_values) - min(roi_values)) / float(config["consistency_range_divisor"])) if roi_values else 50.0
    consistency = clamp(100.0 - consistency_penalty)
    risk_control = clamp(100.0 - (outliers / max(len(roi_values), 1)) * 100.0)
    calibration = clamp(50.0 + (pct(bayes) - 50.0) * 0.75)
    repeatability = clamp((skill * 0.45) + (consistency * 0.35) + (sample_strength * 0.20))
    trust = clamp(
        sample_strength * 0.25
        + consistency * 0.20
        + risk_control * 0.20
        + skill * 0.20
        + profitability * 0.15
    )

    confidence_multiplier = clamp(sample_strength) / 100.0
    confidence_adjusted = clamp(
        (
            trust * 0.25
            + skill * 0.20
            + repeatability * 0.20
            + profitability * 0.15
            + risk_control * 0.10
            + calibration * 0.10
        )
        * confidence_multiplier
    )
    tier, grade = derive_tier(confidence_adjusted, sample_strength, config)

    min_consensus = int(config["minimum_consensus_positions"])
    min_elite = int(config["minimum_elite_positions"])
    consensus_eligible = int(resolved >= min_consensus and confidence_adjusted >= float(config["minimum_consensus_score"]))
    elite_eligible = int(resolved >= min_elite and confidence_adjusted >= float(config["minimum_elite_score"]))

    if elite_eligible:
        status = "ELITE_ELIGIBLE"
        reason = "Meets elite sample-size and confidence-adjusted score requirements."
    elif consensus_eligible:
        status = "CONSENSUS_ELIGIBLE"
        reason = "Eligible for consensus weighting but below elite threshold."
    elif resolved < min_consensus:
        status = "INSUFFICIENT_SAMPLE"
        reason = f"Only {resolved} resolved positions; {min_consensus} required."
    else:
        status = "OBSERVATION"
        reason = "Sample is sufficient, but confidence-adjusted score is below the consensus threshold."

    strengths: list[str] = []
    warnings: list[str] = []
    if skill >= 70:
        strengths.append("Strong Bayesian win-rate profile")
    if consistency >= 70:
        strengths.append("Consistent position outcomes")
    if risk_control >= 75:
        strengths.append("Strong outlier and downside control")
    if sample_strength >= 80:
        strengths.append("Large resolved-position sample")
    if profitability >= 70:
        strengths.append("High profitability quality")
    if resolved < min_consensus:
        warnings.append("Insufficient resolved-position history")
    if outliers > max(2, len(roi_values) // 10):
        warnings.append("Outcome distribution contains multiple ROI outliers")
    if profit_factor < 1.0 and losses:
        warnings.append("Gross losses exceed gross gains")
    if unresolved > resolved:
        warnings.append("More unresolved than resolved positions")

    explanation = {
        "summary": (
            f"{wallet} is classified as {tier} ({grade}) with a "
            f"confidence-adjusted score of {confidence_adjusted:.2f}."
        ),
        "drivers": {
            "trust_score": round(trust, 4),
            "skill_score": round(skill, 4),
            "repeatability_score": round(repeatability, 4),
            "sample_strength_score": round(sample_strength, 4),
            "risk_control_score": round(risk_control, 4),
        },
        "eligibility_reason": reason,
    }

    return WalletMetrics(
        wallet=wallet,
        resolved_positions=resolved,
        wins=wins,
        losses=losses,
        raw_win_rate=round(pct(raw_rate), 4),
        bayesian_win_rate=round(pct(bayes), 4),
        bayesian_lower_bound=round(pct(lower), 4),
        bayesian_upper_bound=round(pct(upper), 4),
        raw_roi=round(raw_roi, 4),
        trimmed_mean_roi=round(trim_roi, 4),
        winsorized_mean_roi=round(win_roi, 4),
        profit_factor=round(profit_factor, 4),
        expectancy_per_dollar=round(expectancy, 6),
        outlier_count=outliers,
        unresolved_positions=unresolved,
        trust_score=round(trust, 4),
        skill_score=round(skill, 4),
        repeatability_score=round(repeatability, 4),
        profitability_quality_score=round(profitability, 4),
        calibration_score=round(calibration, 4),
        consistency_score=round(consistency, 4),
        risk_control_score=round(risk_control, 4),
        sample_strength_score=round(sample_strength, 4),
        confidence_adjusted_score=round(confidence_adjusted, 4),
        data_confidence=round(sample_strength, 4),
        confidence_multiplier=round(confidence_multiplier, 6),
        influence_weight=round(confidence_adjusted / 100.0, 6),
        elite_tier=tier,
        overall_grade=grade,
        eligibility_status=status,
        eligibility_reason=reason,
        consensus_eligible=consensus_eligible,
        elite_eligible=elite_eligible,
        strengths_json=json.dumps(strengths),
        warnings_json=json.dumps(warnings),
        explanation_json=json.dumps(explanation, sort_keys=True),
    )


def profile_checksum(metrics: WalletMetrics) -> str:
    payload = json.dumps(metrics.__dict__, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_positions(connection: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    rows = connection.execute(
        """
        SELECT wallet, market_id, title, outcome, current_value, cash_pnl, percent_pnl
        FROM positions
        WHERE wallet IS NOT NULL AND TRIM(wallet) <> ''
        """
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(str(row["wallet"]), []).append(row)
    return grouped


def upsert_profile(connection: sqlite3.Connection, metrics: WalletMetrics, calculated_at: str) -> None:
    connection.execute(
        """
        INSERT INTO elite_wallet_profiles (
            wallet, eligibility_status, eligibility_reason, elite_tier,
            overall_grade, trust_score, skill_score, repeatability_score,
            profitability_quality_score, calibration_score, consistency_score,
            risk_control_score, sample_strength_score, confidence_adjusted_score,
            resolved_positions, wins, losses, raw_win_rate, bayesian_win_rate,
            bayesian_lower_bound, bayesian_upper_bound, raw_roi, trimmed_mean_roi,
            winsorized_mean_roi, profit_factor, expectancy_per_dollar,
            outlier_count, unresolved_positions, data_confidence,
            confidence_multiplier, influence_weight, consensus_eligible,
            elite_eligible, strengths_json, warnings_json, explanation_json,
            engine_version, calculated_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(wallet) DO UPDATE SET
            eligibility_status=excluded.eligibility_status,
            eligibility_reason=excluded.eligibility_reason,
            elite_tier=excluded.elite_tier,
            overall_grade=excluded.overall_grade,
            trust_score=excluded.trust_score,
            skill_score=excluded.skill_score,
            repeatability_score=excluded.repeatability_score,
            profitability_quality_score=excluded.profitability_quality_score,
            calibration_score=excluded.calibration_score,
            consistency_score=excluded.consistency_score,
            risk_control_score=excluded.risk_control_score,
            sample_strength_score=excluded.sample_strength_score,
            confidence_adjusted_score=excluded.confidence_adjusted_score,
            resolved_positions=excluded.resolved_positions,
            wins=excluded.wins,
            losses=excluded.losses,
            raw_win_rate=excluded.raw_win_rate,
            bayesian_win_rate=excluded.bayesian_win_rate,
            bayesian_lower_bound=excluded.bayesian_lower_bound,
            bayesian_upper_bound=excluded.bayesian_upper_bound,
            raw_roi=excluded.raw_roi,
            trimmed_mean_roi=excluded.trimmed_mean_roi,
            winsorized_mean_roi=excluded.winsorized_mean_roi,
            profit_factor=excluded.profit_factor,
            expectancy_per_dollar=excluded.expectancy_per_dollar,
            outlier_count=excluded.outlier_count,
            unresolved_positions=excluded.unresolved_positions,
            data_confidence=excluded.data_confidence,
            confidence_multiplier=excluded.confidence_multiplier,
            influence_weight=excluded.influence_weight,
            consensus_eligible=excluded.consensus_eligible,
            elite_eligible=excluded.elite_eligible,
            strengths_json=excluded.strengths_json,
            warnings_json=excluded.warnings_json,
            explanation_json=excluded.explanation_json,
            engine_version=excluded.engine_version,
            calculated_at=excluded.calculated_at,
            updated_at=excluded.updated_at
        """,
        (
            metrics.wallet, metrics.eligibility_status, metrics.eligibility_reason,
            metrics.elite_tier, metrics.overall_grade, metrics.trust_score,
            metrics.skill_score, metrics.repeatability_score,
            metrics.profitability_quality_score, metrics.calibration_score,
            metrics.consistency_score, metrics.risk_control_score,
            metrics.sample_strength_score, metrics.confidence_adjusted_score,
            metrics.resolved_positions, metrics.wins, metrics.losses,
            metrics.raw_win_rate, metrics.bayesian_win_rate,
            metrics.bayesian_lower_bound, metrics.bayesian_upper_bound,
            metrics.raw_roi, metrics.trimmed_mean_roi,
            metrics.winsorized_mean_roi, metrics.profit_factor,
            metrics.expectancy_per_dollar, metrics.outlier_count,
            metrics.unresolved_positions, metrics.data_confidence,
            metrics.confidence_multiplier, metrics.influence_weight,
            metrics.consensus_eligible, metrics.elite_eligible,
            metrics.strengths_json, metrics.warnings_json,
            metrics.explanation_json, ENGINE_VERSION, calculated_at,
            calculated_at,
        ),
    )


def insert_history(connection: sqlite3.Connection, metrics: WalletMetrics, calculated_at: str) -> None:
    checksum = profile_checksum(metrics)
    existing = connection.execute(
        """
        SELECT 1
        FROM elite_wallet_profile_history
        WHERE wallet=? AND profile_checksum=?
        LIMIT 1
        """,
        (metrics.wallet, checksum),
    ).fetchone()
    if existing:
        return
    connection.execute(
        """
        INSERT INTO elite_wallet_profile_history (
            wallet, eligibility_status, elite_tier, overall_grade,
            trust_score, skill_score, repeatability_score,
            profitability_quality_score, calibration_score, consistency_score,
            risk_control_score, sample_strength_score,
            confidence_adjusted_score, resolved_positions, wins, losses,
            raw_win_rate, raw_roi, profit_factor, data_confidence,
            influence_weight, profile_checksum, engine_version, calculated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metrics.wallet, metrics.eligibility_status, metrics.elite_tier,
            metrics.overall_grade, metrics.trust_score, metrics.skill_score,
            metrics.repeatability_score, metrics.profitability_quality_score,
            metrics.calibration_score, metrics.consistency_score,
            metrics.risk_control_score, metrics.sample_strength_score,
            metrics.confidence_adjusted_score, metrics.resolved_positions,
            metrics.wins, metrics.losses, metrics.raw_win_rate,
            metrics.raw_roi, metrics.profit_factor, metrics.data_confidence,
            metrics.influence_weight, checksum, ENGINE_VERSION, calculated_at,
        ),
    )


def upsert_categories(connection: sqlite3.Connection, wallet: str, rows: list[sqlite3.Row], config: dict[str, Any], calculated_at: str) -> None:
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(category_from_title(str(row["title"] or "")), []).append(row)

    for category, category_rows in grouped.items():
        metrics = compute_metrics(wallet, category_rows, config)
        connection.execute(
            """
            INSERT INTO elite_wallet_category_profiles (
                wallet, category, resolved_positions, wins, losses,
                bayesian_win_rate, raw_roi, profit_factor,
                sample_strength_score, confidence_adjusted_score,
                category_grade, consensus_eligible, elite_eligible,
                engine_version, calculated_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(wallet, category) DO UPDATE SET
                resolved_positions=excluded.resolved_positions,
                wins=excluded.wins,
                losses=excluded.losses,
                bayesian_win_rate=excluded.bayesian_win_rate,
                raw_roi=excluded.raw_roi,
                profit_factor=excluded.profit_factor,
                sample_strength_score=excluded.sample_strength_score,
                confidence_adjusted_score=excluded.confidence_adjusted_score,
                category_grade=excluded.category_grade,
                consensus_eligible=excluded.consensus_eligible,
                elite_eligible=excluded.elite_eligible,
                engine_version=excluded.engine_version,
                calculated_at=excluded.calculated_at,
                updated_at=excluded.updated_at
            """,
            (
                wallet, category, metrics.resolved_positions, metrics.wins,
                metrics.losses, metrics.bayesian_win_rate, metrics.raw_roi,
                metrics.profit_factor, metrics.sample_strength_score,
                metrics.confidence_adjusted_score, metrics.overall_grade,
                metrics.consensus_eligible, metrics.elite_eligible,
                ENGINE_VERSION, calculated_at, calculated_at,
            ),
        )


def publish_event(connection: sqlite3.Connection, wallet: str, metrics: WalletMetrics, calculated_at: str) -> None:
    columns = table_columns(connection, "platform_events")
    if not columns:
        return
    payload = json.dumps({
        "wallet": wallet,
        "elite_tier": metrics.elite_tier,
        "overall_grade": metrics.overall_grade,
        "confidence_adjusted_score": metrics.confidence_adjusted_score,
        "eligibility_status": metrics.eligibility_status,
    }, sort_keys=True)
    event_id = hashlib.sha256(
        f"EliteWalletProfileUpdated:{wallet}:{profile_checksum(metrics)}".encode("utf-8")
    ).hexdigest()
    required = {
        "event_id", "event_type", "source_engine", "source_version",
        "aggregate_type", "aggregate_id", "payload_json", "occurred_at",
        "stored_at", "deduplication_key", "status"
    }
    if not required.issubset(columns):
        return
    connection.execute(
        """
        INSERT OR IGNORE INTO platform_events (
            event_id, event_type, source_engine, source_version,
            aggregate_type, aggregate_id, payload_json, occurred_at,
            stored_at, deduplication_key, status, processing_attempts
        ) VALUES (?, 'EliteWalletProfileUpdated', ?, ?, 'wallet', ?, ?, ?, ?, ?, 'PENDING', 0)
        """,
        (
            event_id, "elite_wallet_intelligence_v2", ENGINE_VERSION,
            wallet, payload, calculated_at, calculated_at, event_id,
        ),
    )


def print_board(connection: sqlite3.Connection, limit: int = 20) -> None:
    rows = connection.execute(
        """
        SELECT wallet, elite_tier, overall_grade, confidence_adjusted_score,
               trust_score, skill_score, repeatability_score,
               sample_strength_score, resolved_positions, raw_roi
        FROM ranked_elite_wallets
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    print()
    print("ELITE WALLET INTELLIGENCE v2 BOARD")
    print("-" * 150)
    for index, row in enumerate(rows, start=1):
        wallet = str(row["wallet"])
        short_wallet = wallet[:8] + "..." + wallet[-6:] if len(wallet) > 18 else wallet
        print(
            f"{index:>3}  {float(row['confidence_adjusted_score'] or 0):>6.2f} "
            f"{str(row['overall_grade'] or ''):<6} "
            f"{str(row['elite_tier'] or ''):<15} "
            f"T:{float(row['trust_score'] or 0):>6.2f} "
            f"S:{float(row['skill_score'] or 0):>6.2f} "
            f"R:{float(row['repeatability_score'] or 0):>6.2f} "
            f"N:{int(row['resolved_positions'] or 0):>5} "
            f"ROI:{float(row['raw_roi'] or 0):>8.2f} "
            f"{short_wallet}"
        )
    print("-" * 150)


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    config = load_config()
    calculated_at = utc_now()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        require_schema(connection)
        ensure_supporting_schema(connection)

        grouped = load_positions(connection)
        profiles_written = 0
        history_written_before = connection.execute(
            "SELECT COUNT(*) FROM elite_wallet_profile_history"
        ).fetchone()[0]
        events_before = connection.execute(
            "SELECT COUNT(*) FROM platform_events WHERE event_type='EliteWalletProfileUpdated'"
        ).fetchone()[0] if table_columns(connection, "platform_events") else 0

        for wallet, rows in grouped.items():
            metrics = compute_metrics(wallet, rows, config)
            upsert_profile(connection, metrics, calculated_at)
            insert_history(connection, metrics, calculated_at)
            upsert_categories(connection, wallet, rows, config, calculated_at)
            publish_event(connection, wallet, metrics, calculated_at)
            profiles_written += 1

        connection.commit()

        history_written_after = connection.execute(
            "SELECT COUNT(*) FROM elite_wallet_profile_history"
        ).fetchone()[0]
        events_after = connection.execute(
            "SELECT COUNT(*) FROM platform_events WHERE event_type='EliteWalletProfileUpdated'"
        ).fetchone()[0] if table_columns(connection, "platform_events") else 0

        print_board(connection, int(config["board_limit"]))
        print()
        print("=" * 80)
        print(f"ELITE WALLET INTELLIGENCE v{ENGINE_VERSION}")
        print("=" * 80)
        print(f"Wallets evaluated:       {profiles_written:,}")
        print(f"History rows created:    {history_written_after - history_written_before:,}")
        print(f"Events published:        {events_after - events_before:,}")
        print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
