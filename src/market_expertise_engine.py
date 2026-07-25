from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.0"

BAYES_ALPHA = 5.0
BAYES_BETA = 5.0
MIN_RATED_POSITIONS = 5
MIN_EXPERT_POSITIONS = 20
MIN_ELITE_EXPERT_POSITIONS = 50
EPSILON = 1e-9

ROI_FLOOR = -1.0
ROI_CEILING = 10.0


CATEGORY_RULES: dict[str, list[str]] = {
    "SOCCER": [
        r"\bsoccer\b", r"\bfootball\b", r"\bfifa\b",
        r"\bworld cup\b", r"\bpremier league\b", r"\bepl\b",
        r"\bla liga\b", r"\bserie a\b", r"\bbundesliga\b",
        r"\bligue 1\b", r"\bchampions league\b", r"\beuropa league\b",
        r"\bmls\b", r"\bcopa\b", r"\buefa\b", r"\bafcon\b",
        r"\bgoal(s)?\b", r"\bcorner(s)?\b", r"\bclean sheet\b",
        r"\bbtts\b", r"\bspread\b", r"\bexact score\b",
    ],
    "BASKETBALL": [
        r"\bnba\b", r"\bwnba\b", r"\bncaa basketball\b",
        r"\beuroleague\b", r"\bbasketball\b", r"\bpoints\b",
        r"\brebounds\b", r"\bassists\b", r"\btriple[- ]double\b",
    ],
    "BASEBALL": [
        r"\bmlb\b", r"\bbaseball\b", r"\bhome run\b",
        r"\bstrikeouts?\b", r"\brbi\b", r"\binnings?\b",
        r"\bworld series\b",
    ],
    "HOCKEY": [
        r"\bnhl\b", r"\bhockey\b", r"\bstanley cup\b",
        r"\bpuck line\b",
    ],
    "AMERICAN_FOOTBALL": [
        r"\bnfl\b", r"\bsuper bowl\b", r"\bncaa football\b",
        r"\bamerican football\b", r"\btouchdowns?\b",
    ],
    "MMA": [
        r"\bufc\b", r"\bmma\b", r"\bbellator\b",
        r"\bfight night\b", r"\bknockout\b", r"\bsubmission\b",
    ],
    "TENNIS": [
        r"\btennis\b", r"\bwimbledon\b", r"\baustralian open\b",
        r"\bfrench open\b", r"\bus open\b", r"\batp\b",
        r"\bwta\b", r"\baces?\b",
    ],
    "CRYPTO": [
        r"\bbitcoin\b", r"\bbtc\b", r"\bethereum\b", r"\beth\b",
        r"\bsolana\b", r"\bsol\b", r"\bcrypto\b", r"\bblockchain\b",
        r"\btoken\b", r"\bcoinbase\b", r"\bbinance\b",
    ],
    "POLITICS": [
        r"\belection\b", r"\bpresident\b", r"\bprime minister\b",
        r"\bcongress\b", r"\bsenate\b", r"\bgovernor\b",
        r"\brepublican\b", r"\bdemocrat\b", r"\bgop\b",
        r"\bnomination\b", r"\bparliament\b", r"\bmayor\b",
        r"\bapproval rating\b",
    ],
    "ECONOMY": [
        r"\binflation\b", r"\bcpi\b", r"\bgdp\b",
        r"\binterest rate\b", r"\bfed\b", r"\bfederal reserve\b",
        r"\bunemployment\b", r"\brecession\b", r"\beconomy\b",
        r"\bstock market\b", r"\bs&p\b", r"\bnasdaq\b",
    ],
    "GEOPOLITICS": [
        r"\bwar\b", r"\bceasefire\b", r"\binvasion\b",
        r"\bnato\b", r"\bukraine\b", r"\brussia\b",
        r"\bisrael\b", r"\bgaza\b", r"\biran\b",
        r"\bchina\b", r"\btaiwan\b", r"\bsanctions\b",
    ],
    "ENTERTAINMENT": [
        r"\boscar\b", r"\bemmy\b", r"\bgrammy\b",
        r"\bmovie\b", r"\bfilm\b", r"\bbox office\b",
        r"\balbum\b", r"\bsong\b", r"\bcelebrity\b",
        r"\breality show\b",
    ],
    "TECHNOLOGY": [
        r"\bopenai\b", r"\bchatgpt\b", r"\bartificial intelligence\b",
        r"\bai\b", r"\bapple\b", r"\bgoogle\b", r"\bmicrosoft\b",
        r"\btesla\b", r"\bspacex\b", r"\blaunch\b",
    ],
}

SPORT_CATEGORIES = {
    "SOCCER",
    "BASKETBALL",
    "BASEBALL",
    "HOCKEY",
    "AMERICAN_FOOTBALL",
    "MMA",
    "TENNIS",
}


@dataclass(frozen=True)
class ResolvedPosition:
    wallet: str
    condition_id: str
    title: str
    selected_outcome: str
    won: int
    lost: int
    cost_basis: float
    estimated_profit: float
    estimated_roi: float
    average_entry_price: float
    brier_score: float | None
    resolved_at: str | None
    category: str
    subcategory: str | None
    classification_confidence: float
    classification_method: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        if not math.isfinite(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA busy_timeout = 30000;")
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
        ).fetchone()
        is not None
    )


def require_table(connection: sqlite3.Connection, table_name: str) -> None:
    if not table_exists(connection, table_name):
        raise RuntimeError(f"Required table missing: {table_name}")


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_category_dictionary (
            condition_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            classification_confidence REAL NOT NULL DEFAULT 0,
            classification_method TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            manually_overridden INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_mcd_category
        ON market_category_dictionary(category);

        CREATE TABLE IF NOT EXISTS wallet_market_expertise (
            wallet TEXT NOT NULL,
            category TEXT NOT NULL,

            resolved_positions INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,

            raw_win_rate REAL NOT NULL DEFAULT 0,
            bayesian_win_rate REAL NOT NULL DEFAULT 0,
            bayesian_lower_bound REAL NOT NULL DEFAULT 0,
            bayesian_upper_bound REAL NOT NULL DEFAULT 0,

            total_cost_basis REAL NOT NULL DEFAULT 0,
            total_profit REAL NOT NULL DEFAULT 0,
            raw_roi REAL NOT NULL DEFAULT 0,
            median_position_roi REAL NOT NULL DEFAULT 0,
            trimmed_mean_roi REAL NOT NULL DEFAULT 0,
            winsorized_mean_roi REAL NOT NULL DEFAULT 0,

            gross_profit REAL NOT NULL DEFAULT 0,
            gross_loss REAL NOT NULL DEFAULT 0,
            profit_factor REAL,
            expectancy_per_position REAL NOT NULL DEFAULT 0,
            expectancy_per_dollar REAL NOT NULL DEFAULT 0,

            weighted_brier_score REAL,
            calibration_score REAL NOT NULL DEFAULT 0,
            consistency_score REAL NOT NULL DEFAULT 0,
            sample_strength_score REAL NOT NULL DEFAULT 0,
            profitability_quality_score REAL NOT NULL DEFAULT 0,
            repeatability_score REAL NOT NULL DEFAULT 0,
            category_trust_score REAL NOT NULL DEFAULT 0,

            global_trust_score REAL NOT NULL DEFAULT 0,
            global_influence_weight REAL NOT NULL DEFAULT 0,
            expertise_influence_weight REAL NOT NULL DEFAULT 0,

            expertise_grade TEXT NOT NULL DEFAULT 'UNRATED',
            expertise_tier TEXT NOT NULL DEFAULT 'UNRATED',
            data_confidence TEXT NOT NULL DEFAULT 'VERY LOW',
            consensus_eligible INTEGER NOT NULL DEFAULT 0,
            expert_eligible INTEGER NOT NULL DEFAULT 0,

            first_resolved_at TEXT,
            last_resolved_at TEXT,
            outlier_count INTEGER NOT NULL DEFAULT 0,
            explanation_json TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (wallet, category)
        );

        CREATE INDEX IF NOT EXISTS idx_wme_category_score
        ON wallet_market_expertise(
            category,
            category_trust_score DESC
        );

        CREATE INDEX IF NOT EXISTS idx_wme_wallet
        ON wallet_market_expertise(wallet);

        CREATE TABLE IF NOT EXISTS wallet_market_expertise_history (
            expertise_run_id TEXT NOT NULL,
            wallet TEXT NOT NULL,
            category TEXT NOT NULL,
            category_trust_score REAL NOT NULL,
            expertise_grade TEXT NOT NULL,
            expertise_tier TEXT NOT NULL,
            resolved_positions INTEGER NOT NULL,
            bayesian_win_rate REAL NOT NULL,
            bayesian_lower_bound REAL NOT NULL,
            trimmed_mean_roi REAL NOT NULL,
            profit_factor REAL,
            expertise_influence_weight REAL NOT NULL,
            data_confidence TEXT NOT NULL,
            consensus_eligible INTEGER NOT NULL,
            expert_eligible INTEGER NOT NULL,
            created_at TEXT NOT NULL,

            PRIMARY KEY (expertise_run_id, wallet, category)
        );

        CREATE INDEX IF NOT EXISTS idx_wmeh_wallet_category
        ON wallet_market_expertise_history(wallet, category);

        CREATE INDEX IF NOT EXISTS idx_wmeh_run
        ON wallet_market_expertise_history(expertise_run_id);
        """
    )


def normalize_text(value: str | None) -> str:
    text = (value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def classify_market(title: str, outcome: str) -> tuple[str, str | None, float, str]:
    text = normalize_text(f"{title} {outcome}")

    scores: dict[str, int] = {}
    matched_patterns: dict[str, list[str]] = defaultdict(list)

    for category, patterns in CATEGORY_RULES.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                score += 1
                matched_patterns[category].append(pattern)
        if score:
            scores[category] = score

    if not scores:
        return "OTHER", None, 0.35, "fallback:no_rule_match"

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    top_category, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    margin = top_score - second_score
    confidence = clamp(
        0.55 + 0.10 * top_score + 0.05 * margin,
        0.55,
        0.98,
    )

    subcategory: str | None = None
    if top_category in SPORT_CATEGORIES:
        subcategory = top_category

    method = (
        "rules:"
        + ",".join(matched_patterns[top_category][:5])
    )

    return top_category, subcategory, confidence, method


def upsert_market_classification(
    connection: sqlite3.Connection,
    condition_id: str,
    title: str,
    category: str,
    subcategory: str | None,
    confidence: float,
    method: str,
    timestamp: str,
) -> None:
    connection.execute(
        """
        INSERT INTO market_category_dictionary (
            condition_id,
            title,
            category,
            subcategory,
            classification_confidence,
            classification_method,
            rule_version,
            manually_overridden,
            first_seen_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(condition_id) DO UPDATE SET
            title = excluded.title,
            category = CASE
                WHEN market_category_dictionary.manually_overridden = 1
                THEN market_category_dictionary.category
                ELSE excluded.category
            END,
            subcategory = CASE
                WHEN market_category_dictionary.manually_overridden = 1
                THEN market_category_dictionary.subcategory
                ELSE excluded.subcategory
            END,
            classification_confidence = CASE
                WHEN market_category_dictionary.manually_overridden = 1
                THEN market_category_dictionary.classification_confidence
                ELSE excluded.classification_confidence
            END,
            classification_method = CASE
                WHEN market_category_dictionary.manually_overridden = 1
                THEN market_category_dictionary.classification_method
                ELSE excluded.classification_method
            END,
            rule_version = excluded.rule_version,
            updated_at = excluded.updated_at
        """,
        (
            condition_id,
            title,
            category,
            subcategory,
            confidence,
            method,
            ENGINE_VERSION,
            timestamp,
            timestamp,
        ),
    )


def load_resolved_positions(
    connection: sqlite3.Connection,
    timestamp: str,
) -> list[ResolvedPosition]:
    rows = connection.execute(
        """
        SELECT
            wallet,
            condition_id,
            title,
            selected_outcome,
            source_outcome_won,
            source_outcome_lost,
            cost_basis,
            estimated_profit,
            estimated_roi,
            average_entry_price,
            brier_score,
            scanned_at
        FROM wallet_performance_markets
        WHERE performance_market_key LIKE 'closed_snapshot:%'
          AND source_outcome_won IN (0, 1)
        ORDER BY wallet, condition_id, selected_outcome
        """
    ).fetchall()

    positions: list[ResolvedPosition] = []

    for row in rows:
        condition_id = str(row["condition_id"] or "")
        title = str(row["title"] or "")
        outcome = str(row["selected_outcome"] or "")

        existing = connection.execute(
            """
            SELECT
                category,
                subcategory,
                classification_confidence,
                classification_method
            FROM market_category_dictionary
            WHERE condition_id = ?
            """,
            (condition_id,),
        ).fetchone()

        if existing is not None:
            category = str(existing["category"])
            subcategory = (
                str(existing["subcategory"])
                if existing["subcategory"] is not None
                else None
            )
            classification_confidence = as_float(
                existing["classification_confidence"]
            )
            classification_method = str(
                existing["classification_method"]
            )
        else:
            (
                category,
                subcategory,
                classification_confidence,
                classification_method,
            ) = classify_market(title, outcome)

            upsert_market_classification(
                connection=connection,
                condition_id=condition_id,
                title=title,
                category=category,
                subcategory=subcategory,
                confidence=classification_confidence,
                method=classification_method,
                timestamp=timestamp,
            )

        positions.append(
            ResolvedPosition(
                wallet=str(row["wallet"]).strip().lower(),
                condition_id=condition_id,
                title=title,
                selected_outcome=outcome,
                won=int(row["source_outcome_won"]),
                lost=int(row["source_outcome_lost"] or 0),
                cost_basis=max(0.0, as_float(row["cost_basis"])),
                estimated_profit=as_float(row["estimated_profit"]),
                estimated_roi=as_float(row["estimated_roi"]),
                average_entry_price=clamp(
                    as_float(row["average_entry_price"]),
                    0.0,
                    1.0,
                ),
                brier_score=(
                    as_float(row["brier_score"])
                    if row["brier_score"] is not None
                    else None
                ),
                resolved_at=(
                    str(row["scanned_at"])
                    if row["scanned_at"] not in (None, "")
                    else None
                ),
                category=category,
                subcategory=subcategory,
                classification_confidence=classification_confidence,
                classification_method=classification_method,
            )
        )

    return positions


def load_global_profiles(
    connection: sqlite3.Connection,
) -> dict[str, sqlite3.Row]:
    return {
        str(row["wallet"]).lower(): row
        for row in connection.execute(
            """
            SELECT *
            FROM elite_wallet_profiles
            """
        ).fetchall()
    }


def percentile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    probability = clamp(probability, 0.0, 1.0)
    position = probability * (len(ordered) - 1)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return ordered[lower_index]

    fraction = position - lower_index
    return (
        ordered[lower_index] * (1.0 - fraction)
        + ordered[upper_index] * fraction
    )


def trimmed_mean(values: list[float], fraction: float = 0.10) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    trim_count = int(len(ordered) * fraction)

    if trim_count == 0:
        return sum(ordered) / len(ordered)

    if trim_count * 2 >= len(ordered):
        return median(ordered)

    trimmed = ordered[trim_count:-trim_count]
    return sum(trimmed) / len(trimmed)


def winsorized_mean(values: list[float]) -> float:
    if not values:
        return 0.0

    lower = percentile(values, 0.05)
    upper = percentile(values, 0.95)
    adjusted = [clamp(value, lower, upper) for value in values]
    return sum(adjusted) / len(adjusted)


def beta_interval(wins: int, losses: int) -> tuple[float, float, float]:
    alpha = BAYES_ALPHA + wins
    beta = BAYES_BETA + losses
    total = alpha + beta

    mean = alpha / total
    variance = (
        alpha * beta
        / ((total ** 2) * (total + 1.0))
    )
    deviation = math.sqrt(max(0.0, variance))

    return (
        mean,
        clamp(mean - 1.96 * deviation, 0.0, 1.0),
        clamp(mean + 1.96 * deviation, 0.0, 1.0),
    )


def sample_strength_score(count: int) -> float:
    if count <= 0:
        return 0.0
    return clamp(50.0 * math.log10(count + 1), 0.0, 100.0)


def consistency_score(rois: list[float]) -> float:
    if not rois:
        return 0.0
    if len(rois) == 1:
        return 30.0

    mean_roi = sum(rois) / len(rois)
    variance = sum((roi - mean_roi) ** 2 for roi in rois) / len(rois)
    volatility = math.sqrt(max(0.0, variance))

    return clamp(
        50.0
        + 30.0 * math.tanh(mean_roi)
        - 30.0 * math.tanh(volatility),
        0.0,
        100.0,
    )


def profitability_quality(
    trimmed_roi: float,
    winsorized_roi: float,
    profit_factor: float | None,
) -> float:
    trimmed_component = 50.0 + 35.0 * math.tanh(trimmed_roi)
    winsorized_component = 50.0 + 30.0 * math.tanh(winsorized_roi)

    if profit_factor is None:
        profit_factor_component = 50.0
    else:
        profit_factor_component = clamp(
            50.0 + 25.0 * math.log10(max(profit_factor, 0.01)),
            0.0,
            100.0,
        )

    return clamp(
        trimmed_component * 0.45
        + winsorized_component * 0.30
        + profit_factor_component * 0.25,
        0.0,
        100.0,
    )


def repeatability_score(
    bayesian_win_rate: float,
    lower_bound: float,
    trimmed_roi: float,
    consistency: float,
) -> float:
    roi_component = 50.0 + 35.0 * math.tanh(trimmed_roi)

    return clamp(
        bayesian_win_rate * 100.0 * 0.30
        + lower_bound * 100.0 * 0.35
        + roi_component * 0.20
        + consistency * 0.15,
        0.0,
        100.0,
    )


def confidence_label(count: int) -> str:
    if count >= 100:
        return "VERY HIGH"
    if count >= 40:
        return "HIGH"
    if count >= 15:
        return "MEDIUM"
    if count >= 5:
        return "LOW"
    return "VERY LOW"


def grade_from_score(score: float, count: int) -> str:
    if count < MIN_RATED_POSITIONS:
        return "UNRATED"
    if score >= 90:
        return "S+"
    if score >= 84:
        return "S"
    if score >= 78:
        return "A+"
    if score >= 72:
        return "A"
    if score >= 65:
        return "B"
    if score >= 58:
        return "C"
    if score >= 50:
        return "WATCH"
    return "PASS"


def tier_from_profile(
    score: float,
    count: int,
    lower_bound: float,
    trimmed_roi: float,
) -> str:
    if count < MIN_RATED_POSITIONS:
        return "UNRATED"

    if (
        count >= MIN_ELITE_EXPERT_POSITIONS
        and score >= 82
        and lower_bound >= 0.65
        and trimmed_roi > 0
    ):
        return "ELITE_EXPERT"

    if (
        count >= MIN_EXPERT_POSITIONS
        and score >= 70
        and lower_bound >= 0.55
        and trimmed_roi > 0
    ):
        return "EXPERT"

    if score >= 58 and trimmed_roi > 0:
        return "QUALIFIED"

    if count >= MIN_RATED_POSITIONS:
        return "WATCH"

    return "UNRATED"


def aggregate_category(
    wallet: str,
    category: str,
    positions: list[ResolvedPosition],
    global_profile: sqlite3.Row | None,
    calculated_at: str,
) -> dict[str, Any]:
    count = len(positions)
    wins = sum(position.won for position in positions)
    losses = sum(position.lost for position in positions)

    raw_win_rate = wins / count if count else 0.0
    (
        bayesian_win_rate,
        lower_bound,
        upper_bound,
    ) = beta_interval(wins, losses)

    total_cost_basis = sum(position.cost_basis for position in positions)
    total_profit = sum(position.estimated_profit for position in positions)
    raw_roi = (
        total_profit / total_cost_basis
        if total_cost_basis > EPSILON
        else 0.0
    )

    raw_rois = [position.estimated_roi for position in positions]
    capped_rois = [
        clamp(roi, ROI_FLOOR, ROI_CEILING)
        for roi in raw_rois
    ]

    median_roi = median(raw_rois) if raw_rois else 0.0
    trimmed_roi = trimmed_mean(capped_rois)
    winsorized_roi = winsorized_mean(capped_rois)

    gross_profit = sum(
        max(0.0, position.estimated_profit)
        for position in positions
    )
    gross_loss = abs(
        sum(
            min(0.0, position.estimated_profit)
            for position in positions
        )
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > EPSILON
        else None
    )

    expectancy_per_position = total_profit / count if count else 0.0
    expectancy_per_dollar = (
        total_profit / total_cost_basis
        if total_cost_basis > EPSILON
        else 0.0
    )

    brier_weight = sum(
        position.cost_basis
        for position in positions
        if position.brier_score is not None
    )
    weighted_brier_score = (
        sum(
            (position.brier_score or 0.0) * position.cost_basis
            for position in positions
            if position.brier_score is not None
        ) / brier_weight
        if brier_weight > EPSILON
        else None
    )
    calibration = (
        clamp((1.0 - weighted_brier_score) * 100.0, 0.0, 100.0)
        if weighted_brier_score is not None
        else 0.0
    )

    consistency = consistency_score(capped_rois)
    sample_strength = sample_strength_score(count)
    profitability = profitability_quality(
        trimmed_roi,
        winsorized_roi,
        profit_factor,
    )
    repeatability = repeatability_score(
        bayesian_win_rate,
        lower_bound,
        trimmed_roi,
        consistency,
    )

    category_trust_score = clamp(
        bayesian_win_rate * 100.0 * 0.22
        + lower_bound * 100.0 * 0.24
        + profitability * 0.20
        + repeatability * 0.16
        + calibration * 0.08
        + consistency * 0.05
        + sample_strength * 0.05,
        0.0,
        100.0,
    )

    global_trust_score = (
        as_float(global_profile["trust_score"])
        if global_profile is not None
        else 0.0
    )
    global_influence_weight = (
        as_float(global_profile["influence_weight"])
        if global_profile is not None
        else 0.0
    )

    confidence = confidence_label(count)
    grade = grade_from_score(category_trust_score, count)
    tier = tier_from_profile(
        category_trust_score,
        count,
        lower_bound,
        trimmed_roi,
    )

    consensus_eligible = int(
        count >= MIN_RATED_POSITIONS
        and category_trust_score >= 50
        and lower_bound >= 0.40
    )
    expert_eligible = int(
        tier in {"EXPERT", "ELITE_EXPERT"}
    )

    category_confidence_multiplier = {
        "VERY HIGH": 1.00,
        "HIGH": 0.95,
        "MEDIUM": 0.85,
        "LOW": 0.70,
        "VERY LOW": 0.50,
    }[confidence]

    expertise_influence_weight = clamp(
        (category_trust_score / 100.0)
        * category_confidence_multiplier
        * (0.50 + 0.50 * global_influence_weight),
        0.0,
        1.0,
    )

    if not consensus_eligible:
        expertise_influence_weight = 0.0

    resolved_dates = sorted(
        position.resolved_at
        for position in positions
        if position.resolved_at
    )

    outlier_count = sum(
        roi < ROI_FLOOR or roi > ROI_CEILING
        for roi in raw_rois
    )

    explanation = {
        "engine": "MARKET EXPERTISE ENGINE",
        "engine_version": ENGINE_VERSION,
        "category": category,
        "classification_note": (
            "Category classifications are rule-based in v1 and can be "
            "manually overridden in market_category_dictionary."
        ),
        "score_weights": {
            "bayesian_win_rate": 0.22,
            "bayesian_lower_bound": 0.24,
            "profitability_quality": 0.20,
            "repeatability": 0.16,
            "calibration": 0.08,
            "consistency": 0.05,
            "sample_strength": 0.05,
        },
        "eligibility_rules": {
            "minimum_rated_positions": MIN_RATED_POSITIONS,
            "minimum_expert_positions": MIN_EXPERT_POSITIONS,
            "minimum_elite_expert_positions":
                MIN_ELITE_EXPERT_POSITIONS,
        },
        "important_note": (
            "Global wallet trust and category expertise are separate. "
            "Consensus Engine v2 should use expertise_influence_weight "
            "for markets in this category."
        ),
    }

    return {
        "wallet": wallet,
        "category": category,
        "resolved_positions": count,
        "wins": wins,
        "losses": losses,
        "raw_win_rate": raw_win_rate,
        "bayesian_win_rate": bayesian_win_rate,
        "bayesian_lower_bound": lower_bound,
        "bayesian_upper_bound": upper_bound,
        "total_cost_basis": total_cost_basis,
        "total_profit": total_profit,
        "raw_roi": raw_roi,
        "median_position_roi": median_roi,
        "trimmed_mean_roi": trimmed_roi,
        "winsorized_mean_roi": winsorized_roi,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "expectancy_per_position": expectancy_per_position,
        "expectancy_per_dollar": expectancy_per_dollar,
        "weighted_brier_score": weighted_brier_score,
        "calibration_score": calibration,
        "consistency_score": consistency,
        "sample_strength_score": sample_strength,
        "profitability_quality_score": profitability,
        "repeatability_score": repeatability,
        "category_trust_score": category_trust_score,
        "global_trust_score": global_trust_score,
        "global_influence_weight": global_influence_weight,
        "expertise_influence_weight": expertise_influence_weight,
        "expertise_grade": grade,
        "expertise_tier": tier,
        "data_confidence": confidence,
        "consensus_eligible": consensus_eligible,
        "expert_eligible": expert_eligible,
        "first_resolved_at": resolved_dates[0] if resolved_dates else None,
        "last_resolved_at": resolved_dates[-1] if resolved_dates else None,
        "outlier_count": outlier_count,
        "explanation_json": json.dumps(
            explanation,
            sort_keys=True,
        ),
        "calculated_at": calculated_at,
        "updated_at": calculated_at,
    }


def upsert_expertise(
    connection: sqlite3.Connection,
    profile: dict[str, Any],
) -> None:
    columns = list(profile.keys())
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in columns
        if column not in {"wallet", "category"}
    )

    connection.execute(
        f"""
        INSERT INTO wallet_market_expertise (
            {", ".join(columns)}
        )
        VALUES ({placeholders})
        ON CONFLICT(wallet, category) DO UPDATE SET
            {updates}
        """,
        tuple(profile[column] for column in columns),
    )


def store_history(
    connection: sqlite3.Connection,
    profiles: list[dict[str, Any]],
    run_id: str,
    created_at: str,
) -> None:
    for profile in profiles:
        connection.execute(
            """
            INSERT INTO wallet_market_expertise_history (
                expertise_run_id,
                wallet,
                category,
                category_trust_score,
                expertise_grade,
                expertise_tier,
                resolved_positions,
                bayesian_win_rate,
                bayesian_lower_bound,
                trimmed_mean_roi,
                profit_factor,
                expertise_influence_weight,
                data_confidence,
                consensus_eligible,
                expert_eligible,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                profile["wallet"],
                profile["category"],
                profile["category_trust_score"],
                profile["expertise_grade"],
                profile["expertise_tier"],
                profile["resolved_positions"],
                profile["bayesian_win_rate"],
                profile["bayesian_lower_bound"],
                profile["trimmed_mean_roi"],
                profile["profit_factor"],
                profile["expertise_influence_weight"],
                profile["data_confidence"],
                profile["consensus_eligible"],
                profile["expert_eligible"],
                created_at,
            ),
        )


def print_report(
    profiles: list[dict[str, Any]],
    position_count: int,
    classified_market_count: int,
    run_id: str,
) -> None:
    ranked = sorted(
        profiles,
        key=lambda item: (
            item["expert_eligible"],
            item["category_trust_score"],
            item["resolved_positions"],
        ),
        reverse=True,
    )

    categories = sorted({
        profile["category"]
        for profile in profiles
    })
    experts = sum(profile["expert_eligible"] for profile in profiles)

    print("\n" + "=" * 120)
    print("MARKET EXPERTISE ENGINE COMPLETE")
    print("=" * 120)
    print(f"Database: {DATABASE_PATH}")
    print(f"Resolved positions analyzed: {position_count}")
    print(f"Markets classified: {classified_market_count}")
    print(f"Wallet-category profiles: {len(profiles)}")
    print(f"Categories represented: {len(categories)}")
    print(f"Expert-qualified profiles: {experts}")
    print(f"Expertise run ID: {run_id}")

    print("\nCategory distribution:")
    for category in categories:
        category_profiles = [
            profile
            for profile in profiles
            if profile["category"] == category
        ]
        total_positions = sum(
            profile["resolved_positions"]
            for profile in category_profiles
        )
        print(
            f"  {category:<20} "
            f"wallets={len(category_profiles):>2} "
            f"positions={total_positions:>4}"
        )

    print("\nTop wallet-category expertise profiles:")
    for index, profile in enumerate(ranked[:30], start=1):
        pf_text = (
            f"{profile['profit_factor']:.2f}"
            if profile["profit_factor"] is not None
            else "N/A"
        )

        print(
            f"{index:>2}. {profile['wallet']} | "
            f"category={profile['category']} | "
            f"tier={profile['expertise_tier']} | "
            f"grade={profile['expertise_grade']} | "
            f"trust={profile['category_trust_score']:.2f} | "
            f"influence={profile['expertise_influence_weight']:.3f} | "
            f"resolved={profile['resolved_positions']} | "
            f"bayes={profile['bayesian_win_rate']:.2%} | "
            f"floor={profile['bayesian_lower_bound']:.2%} | "
            f"trimmed_roi={profile['trimmed_mean_roi']:.2%} | "
            f"PF={pf_text} | "
            f"confidence={profile['data_confidence']}"
        )


def run() -> None:
    calculated_at = utc_now()
    run_id = (
        "market_expertise_run:"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )

    connection = connect_database()

    try:
        require_table(connection, "wallet_performance_markets")
        require_table(connection, "elite_wallet_profiles")
        ensure_schema(connection)

        with connection:
            positions = load_resolved_positions(
                connection,
                calculated_at,
            )

        if not positions:
            raise RuntimeError(
                "No resolved closed-snapshot positions were found."
            )

        global_profiles = load_global_profiles(connection)

        grouped: dict[
            tuple[str, str],
            list[ResolvedPosition],
        ] = defaultdict(list)

        for position in positions:
            grouped[
                (position.wallet, position.category)
            ].append(position)

        profiles = [
            aggregate_category(
                wallet=wallet,
                category=category,
                positions=category_positions,
                global_profile=global_profiles.get(wallet),
                calculated_at=calculated_at,
            )
            for (
                wallet,
                category,
            ), category_positions in sorted(grouped.items())
        ]

        with connection:
            connection.execute(
                "DELETE FROM wallet_market_expertise"
            )

            for profile in profiles:
                upsert_expertise(connection, profile)

            store_history(
                connection=connection,
                profiles=profiles,
                run_id=run_id,
                created_at=calculated_at,
            )

        classified_market_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM market_category_dictionary
            """
        ).fetchone()[0]

        print_report(
            profiles=profiles,
            position_count=len(positions),
            classified_market_count=int(classified_market_count),
            run_id=run_id,
        )

    finally:
        connection.close()


if __name__ == "__main__":
    run()