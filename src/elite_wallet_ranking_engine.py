from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 25


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)

        try:
            stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )
        except (AttributeError, OSError):
            pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def wallet_text(value: Any) -> str:
    return text(value).lower()


def number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    if denominator == 0:
        return default

    return numerator / denominator


def clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:
    return max(low, min(value, high))


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def money(value: Any) -> str:
    amount = number(value)

    if amount > 0:
        return f"+${amount:,.2f}"

    if amount < 0:
        return f"-${abs(amount):,.2f}"

    return "$0.00"


def percentage(value: Any) -> str:
    return f"{number(value):.1%}"


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(
            f"Database not found: {DB}"
        )

    connection = sqlite3.connect(
        DB,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}"
    )

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
        ).fetchone()
        is not None
    )


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_tables() -> None:
    connection = connect()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS elite_wallet_rankings (
                wallet TEXT PRIMARY KEY,

                elite_rank INTEGER,
                elite_tier TEXT
                    NOT NULL DEFAULT 'WATCHLIST',

                influence_score REAL
                    NOT NULL DEFAULT 0,

                trust_weight REAL
                    NOT NULL DEFAULT 0,

                consensus_weight REAL
                    NOT NULL DEFAULT 0,

                prediction_weight REAL
                    NOT NULL DEFAULT 0,

                reliability_index REAL
                    NOT NULL DEFAULT 0,

                overall_research_weight REAL
                    NOT NULL DEFAULT 0,

                alpha_score REAL
                    NOT NULL DEFAULT 0,

                alpha_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                alpha_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                performance_score REAL
                    NOT NULL DEFAULT 50,

                performance_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                dna_score REAL
                    NOT NULL DEFAULT 50,

                dna_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                ledger_quality_score REAL
                    NOT NULL DEFAULT 0,

                ledger_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                trade_event_count INTEGER
                    NOT NULL DEFAULT 0,

                closed_position_count INTEGER
                    NOT NULL DEFAULT 0,

                open_position_count INTEGER
                    NOT NULL DEFAULT 0,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                realized_roi REAL
                    NOT NULL DEFAULT 0,

                total_roi REAL
                    NOT NULL DEFAULT 0,

                total_estimated_pnl REAL
                    NOT NULL DEFAULT 0,

                timing_score REAL
                    NOT NULL DEFAULT 50,

                entry_quality_score REAL
                    NOT NULL DEFAULT 50,

                exit_quality_score REAL
                    NOT NULL DEFAULT 50,

                risk_adjusted_score REAL
                    NOT NULL DEFAULT 50,

                consistency_score REAL
                    NOT NULL DEFAULT 50,

                calibration_score REAL
                    NOT NULL DEFAULT 50,

                conviction_score REAL
                    NOT NULL DEFAULT 50,

                specialization_score REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 50,

                sample_size_score REAL
                    NOT NULL DEFAULT 0,

                recency_score REAL
                    NOT NULL DEFAULT 50,

                activity_score REAL
                    NOT NULL DEFAULT 0,

                primary_archetype TEXT,
                primary_category TEXT,
                sports_specialty TEXT,
                market_type_specialty TEXT,

                sports_expertise_score REAL
                    NOT NULL DEFAULT 0,

                politics_expertise_score REAL
                    NOT NULL DEFAULT 0,

                crypto_expertise_score REAL
                    NOT NULL DEFAULT 0,

                entertainment_expertise_score REAL
                    NOT NULL DEFAULT 0,

                other_expertise_score REAL
                    NOT NULL DEFAULT 0,

                category_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                positive_pnl_bonus REAL
                    NOT NULL DEFAULT 0,

                specialization_bonus REAL
                    NOT NULL DEFAULT 0,

                independence_bonus REAL
                    NOT NULL DEFAULT 0,

                high_confidence_bonus REAL
                    NOT NULL DEFAULT 0,

                negative_pnl_penalty REAL
                    NOT NULL DEFAULT 0,

                low_sample_penalty REAL
                    NOT NULL DEFAULT 0,

                weak_confidence_penalty REAL
                    NOT NULL DEFAULT 0,

                total_penalty REAL
                    NOT NULL DEFAULT 0,

                strengths_json TEXT,
                risks_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_elite_wallet_rankings_rank
            ON elite_wallet_rankings(
                elite_rank
            );

            CREATE INDEX IF NOT EXISTS
            idx_elite_wallet_rankings_score
            ON elite_wallet_rankings(
                influence_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_elite_wallet_rankings_tier
            ON elite_wallet_rankings(
                elite_tier,
                influence_score DESC
            );

            CREATE TABLE IF NOT EXISTS elite_wallet_category_weights (
                category_weight_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,
                category TEXT NOT NULL,

                category_share REAL
                    NOT NULL DEFAULT 0,

                category_specialty_score REAL
                    NOT NULL DEFAULT 0,

                performance_score REAL
                    NOT NULL DEFAULT 50,

                alpha_score REAL
                    NOT NULL DEFAULT 0,

                category_influence_weight REAL
                    NOT NULL DEFAULT 0,

                category_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    wallet
                )
                REFERENCES elite_wallet_rankings(
                    wallet
                )
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_elite_wallet_category_weights_wallet
            ON elite_wallet_category_weights(
                wallet,
                category_influence_weight DESC
            );

            CREATE TABLE IF NOT EXISTS elite_wallet_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,
                elite_rank INTEGER,
                elite_tier TEXT,

                influence_score REAL,
                trust_weight REAL,
                consensus_weight REAL,
                prediction_weight REAL,
                reliability_index REAL,
                overall_research_weight REAL,

                alpha_score REAL,
                performance_score REAL,
                dna_score REAL,
                ledger_quality_score REAL,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_elite_wallet_history_wallet
            ON elite_wallet_history(
                wallet,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS elite_wallet_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                wallets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                rankings_saved INTEGER
                    NOT NULL DEFAULT 0,

                category_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# LOADERS
# =============================================================================


def load_by_wallet(
    table_name: str,
) -> dict[str, dict[str, Any]]:
    connection = connect()

    try:
        if not table_exists(
            connection,
            table_name,
        ):
            return {}

        rows = connection.execute(
            f'SELECT * FROM "{table_name}"'
        ).fetchall()

        return {
            wallet_text(
                row["wallet"]
            ): dict(row)
            for row in rows
            if wallet_text(
                row["wallet"]
            )
        }

    finally:
        connection.close()


def load_categories() -> dict[
    str,
    list[dict[str, Any]],
]:
    connection = connect()

    try:
        if not table_exists(
            connection,
            "wallet_dna_categories",
        ):
            return {}

        rows = connection.execute(
            """
            SELECT *
            FROM wallet_dna_categories
            ORDER BY
                wallet,
                portfolio_share DESC
            """
        ).fetchall()

    finally:
        connection.close()

    output: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for row in rows:
        wallet = wallet_text(
            row["wallet"]
        )

        output.setdefault(
            wallet,
            [],
        ).append(
            dict(row)
        )

    return output


# =============================================================================
# SCORING
# =============================================================================


def tier_from_score(
    score: float,
    confidence: str,
    event_count: int,
) -> str:
    confidence_upper = text(
        confidence
    ).upper()

    if (
        score >= 82
        and confidence_upper
        in {
            "HIGH",
            "VERY HIGH",
        }
        and event_count >= 20
    ):
        return "INSTITUTIONAL"

    if (
        score >= 72
        and event_count >= 10
    ):
        return "ELITE"

    if (
        score >= 60
        and event_count >= 5
    ):
        return "PROFESSIONAL"

    if score >= 50:
        return "WATCHLIST"

    return "EXCLUDE"


def category_confidence(
    category_share: float,
    event_count: int,
) -> str:
    score = (
        category_share * 70.0
        + min(
            event_count / 50.0,
            1.0,
        )
        * 30.0
    )

    if score >= 80:
        return "VERY HIGH"

    if score >= 65:
        return "HIGH"

    if score >= 45:
        return "MEDIUM"

    return "LOW"


def score_expertise(
    share: float,
    specialization_score: float,
    alpha_score: float,
    performance_score: float,
) -> float:
    return clamp(
        share * 100.0 * 0.45
        + specialization_score * 0.20
        + alpha_score * 0.20
        + performance_score * 0.15
    )


def build_rankings() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    alpha_lookup = load_by_wallet(
        "wallet_alpha_profiles"
    )

    if not alpha_lookup:
        raise RuntimeError(
            "wallet_alpha_profiles is empty or missing. "
            "Run wallet_alpha_engine.py first."
        )

    performance_lookup = load_by_wallet(
        "wallet_performance"
    )

    dna_lookup = load_by_wallet(
        "wallet_dna_profiles"
    )

    ledger_lookup = load_by_wallet(
        "wallet_trade_ledger_summary"
    )

    categories_lookup = load_categories()

    timestamp = now_iso()

    rankings: list[
        dict[str, Any]
    ] = []

    category_rows: list[
        dict[str, Any]
    ] = []

    for wallet, alpha in (
        alpha_lookup.items()
    ):
        performance = (
            performance_lookup.get(
                wallet,
                {},
            )
        )

        dna = dna_lookup.get(
            wallet,
            {},
        )

        ledger = ledger_lookup.get(
            wallet,
            {},
        )

        alpha_score = number(
            alpha.get(
                "alpha_score"
            )
        )

        alpha_grade = text(
            alpha.get(
                "alpha_grade"
            )
        ) or "UNRATED"

        alpha_confidence = text(
            alpha.get(
                "data_confidence"
            )
        ) or "VERY LOW"

        performance_score = number(
            performance.get(
                "performance_score"
            ),
            number(
                alpha.get(
                    "performance_score"
                ),
                50.0,
            ),
        )

        performance_grade = text(
            performance.get(
                "performance_grade"
            )
        ) or "UNRATED"

        dna_score = number(
            dna.get(
                "dna_score"
            ),
            number(
                alpha.get(
                    "dna_score"
                ),
                50.0,
            ),
        )

        dna_grade = text(
            dna.get(
                "dna_grade"
            )
        ) or "UNRATED"

        ledger_quality_score = number(
            ledger.get(
                "complete_history_score"
            ),
            number(
                alpha.get(
                    "ledger_quality_score"
                )
            ),
        )

        ledger_confidence = text(
            ledger.get(
                "ledger_confidence"
            )
        ) or "VERY LOW"

        trade_event_count = integer(
            alpha.get(
                "trade_event_count"
            )
        )

        closed_position_count = integer(
            alpha.get(
                "closed_position_count"
            )
        )

        open_position_count = integer(
            alpha.get(
                "open_position_count"
            )
        )

        resolved_positions = integer(
            performance.get(
                "resolved_positions"
            ),
            integer(
                alpha.get(
                    "resolved_positions"
                )
            ),
        )

        win_rate = number(
            performance.get(
                "win_rate"
            ),
            number(
                alpha.get(
                    "win_rate"
                )
            ),
        )

        realized_roi = number(
            alpha.get(
                "realized_roi"
            )
        )

        total_roi = number(
            alpha.get(
                "total_roi"
            )
        )

        total_estimated_pnl = number(
            alpha.get(
                "total_estimated_pnl"
            )
        )

        timing_score = number(
            alpha.get(
                "timing_score"
            ),
            50.0,
        )

        entry_quality_score = number(
            alpha.get(
                "entry_quality_score"
            ),
            50.0,
        )

        exit_quality_score = number(
            alpha.get(
                "exit_quality_score"
            ),
            50.0,
        )

        risk_adjusted_score = number(
            alpha.get(
                "risk_adjusted_score"
            ),
            50.0,
        )

        consistency_score = number(
            alpha.get(
                "consistency_score"
            ),
            50.0,
        )

        calibration_score = number(
            alpha.get(
                "calibration_score"
            ),
            50.0,
        )

        conviction_score = number(
            dna.get(
                "conviction_score"
            ),
            50.0,
        )

        specialization_score = number(
            dna.get(
                "specialization_score"
            )
        )

        independence_score = number(
            dna.get(
                "portfolio_independence_score"
            ),
            50.0,
        )

        sample_size_score = number(
            alpha.get(
                "sample_size_score"
            )
        )

        recency_score = 100.0

        activity_score = clamp(
            math.log1p(
                max(
                    trade_event_count,
                    0,
                )
            )
            / math.log1p(500)
            * 100.0
        )

        primary_archetype = text(
            dna.get(
                "primary_archetype"
            )
        )

        primary_category = text(
            dna.get(
                "primary_category"
            )
        )

        sports_specialty = text(
            dna.get(
                "sports_specialty"
            )
        )

        market_type_specialty = text(
            dna.get(
                "market_type_specialty"
            )
        )

        raw_influence_score = clamp(
            alpha_score * 0.30
            + performance_score * 0.16
            + dna_score * 0.14
            + risk_adjusted_score * 0.10
            + consistency_score * 0.08
            + ledger_quality_score * 0.07
            + timing_score * 0.05
            + specialization_score * 0.04
            + independence_score * 0.03
            + sample_size_score * 0.03
        )

        positive_pnl_bonus = (
            4.0
            if total_estimated_pnl > 0
            else 0.0
        )

        specialization_bonus = (
            max(
                specialization_score
                - 70.0,
                0.0,
            )
            / 30.0
            * 4.0
        )

        independence_bonus = (
            max(
                independence_score
                - 70.0,
                0.0,
            )
            / 30.0
            * 3.0
        )

        high_confidence_bonus = (
            3.0
            if alpha_confidence.upper()
            in {
                "HIGH",
                "VERY HIGH",
            }
            else 0.0
        )

        negative_pnl_penalty = (
            min(
                abs(
                    min(
                        total_roi,
                        0.0,
                    )
                )
                * 25.0,
                25.0,
            )
        )

        low_sample_penalty = 0.0

        if trade_event_count < 5:
            low_sample_penalty = 15.0

        elif trade_event_count < 15:
            low_sample_penalty = 8.0

        elif closed_position_count < 2:
            low_sample_penalty = 5.0

        weak_confidence_penalty = 0.0

        if alpha_confidence.upper() == (
            "VERY LOW"
        ):
            weak_confidence_penalty = 10.0

        elif alpha_confidence.upper() == (
            "LOW"
        ):
            weak_confidence_penalty = 5.0

        total_penalty = (
            negative_pnl_penalty
            + low_sample_penalty
            + weak_confidence_penalty
        )

        influence_score = clamp(
            raw_influence_score
            + positive_pnl_bonus
            + specialization_bonus
            + independence_bonus
            + high_confidence_bonus
            - total_penalty
        )

        reliability_index = clamp(
            alpha_score * 0.25
            + ledger_quality_score * 0.20
            + consistency_score * 0.15
            + calibration_score * 0.15
            + sample_size_score * 0.15
            + risk_adjusted_score * 0.10
        )

        trust_weight = clamp(
            (
                influence_score * 0.55
                + reliability_index * 0.45
            )
            / 100.0,
            0.0,
            1.5,
        )

        consensus_weight = clamp(
            (
                influence_score * 0.45
                + specialization_score * 0.20
                + independence_score * 0.15
                + conviction_score * 0.10
                + reliability_index * 0.10
            )
            / 60.0,
            0.0,
            2.0,
        )

        prediction_weight = clamp(
            (
                alpha_score * 0.30
                + performance_score * 0.20
                + reliability_index * 0.20
                + timing_score * 0.10
                + entry_quality_score * 0.10
                + calibration_score * 0.10
            )
            / 55.0,
            0.0,
            2.0,
        )

        overall_research_weight = clamp(
            trust_weight * 0.35
            + consensus_weight * 0.35
            + prediction_weight * 0.30,
            0.0,
            2.0,
        )

        category_shares = {
            text(
                row.get(
                    "category"
                )
            ).upper(): number(
                row.get(
                    "portfolio_share"
                )
            )
            for row in categories_lookup.get(
                wallet,
                [],
            )
        }

        sports_expertise_score = (
            score_expertise(
                category_shares.get(
                    "SPORTS",
                    0.0,
                ),
                specialization_score,
                alpha_score,
                performance_score,
            )
        )

        politics_expertise_score = (
            score_expertise(
                category_shares.get(
                    "POLITICS",
                    0.0,
                ),
                specialization_score,
                alpha_score,
                performance_score,
            )
        )

        crypto_expertise_score = (
            score_expertise(
                category_shares.get(
                    "CRYPTO",
                    0.0,
                ),
                specialization_score,
                alpha_score,
                performance_score,
            )
        )

        entertainment_expertise_score = (
            score_expertise(
                category_shares.get(
                    "ENTERTAINMENT",
                    0.0,
                ),
                specialization_score,
                alpha_score,
                performance_score,
            )
        )

        other_expertise_score = (
            score_expertise(
                category_shares.get(
                    "OTHER",
                    0.0,
                ),
                specialization_score,
                alpha_score,
                performance_score,
            )
        )

        primary_share = max(
            category_shares.values(),
            default=0.0,
        )

        category_confidence_label = (
            category_confidence(
                primary_share,
                trade_event_count,
            )
        )

        elite_tier = tier_from_score(
            influence_score,
            alpha_confidence,
            trade_event_count,
        )

        strengths: list[str] = []
        risks: list[str] = []

        if alpha_score >= 66:
            strengths.append(
                "Positive observed alpha"
            )

        if reliability_index >= 70:
            strengths.append(
                "High reliability index"
            )

        if specialization_score >= 75:
            strengths.append(
                "Strong market specialization"
            )

        if independence_score >= 70:
            strengths.append(
                "Independent portfolio behavior"
            )

        if total_estimated_pnl > 0:
            strengths.append(
                "Positive total estimated PnL"
            )

        if total_estimated_pnl < 0:
            risks.append(
                "Negative total estimated PnL"
            )

        if trade_event_count < 15:
            risks.append(
                "Limited trade-event sample"
            )

        if closed_position_count < 3:
            risks.append(
                "Limited closed-position history"
            )

        if alpha_confidence.upper() in {
            "LOW",
            "VERY LOW",
        }:
            risks.append(
                "Weak alpha confidence"
            )

        explanation = {
            "model_version": "1.0",
            "purpose": (
                "Convert alpha, performance, DNA, ledger "
                "quality and specialization into downstream "
                "consensus and prediction weights."
            ),
            "important_notes": [
                (
                    "Weights are comparative research weights, "
                    "not calibrated probabilities."
                ),
                (
                    "Category expertise is based on observed "
                    "portfolio specialization and current alpha."
                ),
                (
                    "The ranking remains dependent on inferred "
                    "snapshot-ledger quality."
                ),
            ],
            "bonuses": {
                "positive_pnl_bonus": round(
                    positive_pnl_bonus,
                    2,
                ),
                "specialization_bonus": round(
                    specialization_bonus,
                    2,
                ),
                "independence_bonus": round(
                    independence_bonus,
                    2,
                ),
                "high_confidence_bonus": round(
                    high_confidence_bonus,
                    2,
                ),
            },
            "penalties": {
                "negative_pnl_penalty": round(
                    negative_pnl_penalty,
                    2,
                ),
                "low_sample_penalty": round(
                    low_sample_penalty,
                    2,
                ),
                "weak_confidence_penalty": round(
                    weak_confidence_penalty,
                    2,
                ),
            },
        }

        rankings.append(
            {
                "wallet": wallet,
                "elite_rank": None,
                "elite_tier": elite_tier,
                "influence_score": (
                    round(
                        influence_score,
                        1,
                    )
                ),
                "trust_weight": (
                    round(
                        trust_weight,
                        4,
                    )
                ),
                "consensus_weight": (
                    round(
                        consensus_weight,
                        4,
                    )
                ),
                "prediction_weight": (
                    round(
                        prediction_weight,
                        4,
                    )
                ),
                "reliability_index": (
                    round(
                        reliability_index,
                        1,
                    )
                ),
                "overall_research_weight": (
                    round(
                        overall_research_weight,
                        4,
                    )
                ),
                "alpha_score": alpha_score,
                "alpha_grade": alpha_grade,
                "alpha_confidence": (
                    alpha_confidence
                ),
                "performance_score": (
                    performance_score
                ),
                "performance_grade": (
                    performance_grade
                ),
                "dna_score": dna_score,
                "dna_grade": dna_grade,
                "ledger_quality_score": (
                    ledger_quality_score
                ),
                "ledger_confidence": (
                    ledger_confidence
                ),
                "trade_event_count": (
                    trade_event_count
                ),
                "closed_position_count": (
                    closed_position_count
                ),
                "open_position_count": (
                    open_position_count
                ),
                "resolved_positions": (
                    resolved_positions
                ),
                "win_rate": win_rate,
                "realized_roi": realized_roi,
                "total_roi": total_roi,
                "total_estimated_pnl": (
                    total_estimated_pnl
                ),
                "timing_score": timing_score,
                "entry_quality_score": (
                    entry_quality_score
                ),
                "exit_quality_score": (
                    exit_quality_score
                ),
                "risk_adjusted_score": (
                    risk_adjusted_score
                ),
                "consistency_score": (
                    consistency_score
                ),
                "calibration_score": (
                    calibration_score
                ),
                "conviction_score": (
                    conviction_score
                ),
                "specialization_score": (
                    specialization_score
                ),
                "portfolio_independence_score": (
                    independence_score
                ),
                "sample_size_score": (
                    sample_size_score
                ),
                "recency_score": recency_score,
                "activity_score": (
                    activity_score
                ),
                "primary_archetype": (
                    primary_archetype
                ),
                "primary_category": (
                    primary_category
                ),
                "sports_specialty": (
                    sports_specialty
                ),
                "market_type_specialty": (
                    market_type_specialty
                ),
                "sports_expertise_score": (
                    sports_expertise_score
                ),
                "politics_expertise_score": (
                    politics_expertise_score
                ),
                "crypto_expertise_score": (
                    crypto_expertise_score
                ),
                "entertainment_expertise_score": (
                    entertainment_expertise_score
                ),
                "other_expertise_score": (
                    other_expertise_score
                ),
                "category_confidence": (
                    category_confidence_label
                ),
                "positive_pnl_bonus": (
                    positive_pnl_bonus
                ),
                "specialization_bonus": (
                    specialization_bonus
                ),
                "independence_bonus": (
                    independence_bonus
                ),
                "high_confidence_bonus": (
                    high_confidence_bonus
                ),
                "negative_pnl_penalty": (
                    negative_pnl_penalty
                ),
                "low_sample_penalty": (
                    low_sample_penalty
                ),
                "weak_confidence_penalty": (
                    weak_confidence_penalty
                ),
                "total_penalty": (
                    total_penalty
                ),
                "strengths_json": stable_json(
                    strengths
                ),
                "risks_json": stable_json(
                    risks
                ),
                "explanation_json": (
                    stable_json(
                        explanation
                    )
                ),
                "calculated_at": timestamp,
                "updated_at": timestamp,
            }
        )

        for category, share in (
            category_shares.items()
        ):
            specialty_score = (
                share * 100.0
            )

            influence_weight = clamp(
                (
                    influence_score * 0.40
                    + specialty_score * 0.25
                    + alpha_score * 0.20
                    + performance_score * 0.15
                )
                / 50.0,
                0.0,
                2.0,
            )

            category_rows.append(
                {
                    "category_weight_key": (
                        f"{wallet}:"
                        f"{category}"
                    ),
                    "wallet": wallet,
                    "category": category,
                    "category_share": share,
                    "category_specialty_score": (
                        specialty_score
                    ),
                    "performance_score": (
                        performance_score
                    ),
                    "alpha_score": alpha_score,
                    "category_influence_weight": (
                        influence_weight
                    ),
                    "category_confidence": (
                        category_confidence(
                            share,
                            trade_event_count,
                        )
                    ),
                    "calculated_at": (
                        timestamp
                    ),
                    "updated_at": timestamp,
                }
            )

    rankings.sort(
        key=lambda row: (
            row[
                "influence_score"
            ],
            row[
                "reliability_index"
            ],
            row[
                "trade_event_count"
            ],
        ),
        reverse=True,
    )

    for rank, row in enumerate(
        rankings,
        start=1,
    ):
        row["elite_rank"] = rank

    return (
        rankings,
        category_rows,
    )


# =============================================================================
# SAVE
# =============================================================================


RANKING_COLUMNS = [
    "wallet",
    "elite_rank",
    "elite_tier",
    "influence_score",
    "trust_weight",
    "consensus_weight",
    "prediction_weight",
    "reliability_index",
    "overall_research_weight",
    "alpha_score",
    "alpha_grade",
    "alpha_confidence",
    "performance_score",
    "performance_grade",
    "dna_score",
    "dna_grade",
    "ledger_quality_score",
    "ledger_confidence",
    "trade_event_count",
    "closed_position_count",
    "open_position_count",
    "resolved_positions",
    "win_rate",
    "realized_roi",
    "total_roi",
    "total_estimated_pnl",
    "timing_score",
    "entry_quality_score",
    "exit_quality_score",
    "risk_adjusted_score",
    "consistency_score",
    "calibration_score",
    "conviction_score",
    "specialization_score",
    "portfolio_independence_score",
    "sample_size_score",
    "recency_score",
    "activity_score",
    "primary_archetype",
    "primary_category",
    "sports_specialty",
    "market_type_specialty",
    "sports_expertise_score",
    "politics_expertise_score",
    "crypto_expertise_score",
    "entertainment_expertise_score",
    "other_expertise_score",
    "category_confidence",
    "positive_pnl_bonus",
    "specialization_bonus",
    "independence_bonus",
    "high_confidence_bonus",
    "negative_pnl_penalty",
    "low_sample_penalty",
    "weak_confidence_penalty",
    "total_penalty",
    "strengths_json",
    "risks_json",
    "explanation_json",
    "calculated_at",
    "updated_at",
]


CATEGORY_COLUMNS = [
    "category_weight_key",
    "wallet",
    "category",
    "category_share",
    "category_specialty_score",
    "performance_score",
    "alpha_score",
    "category_influence_weight",
    "category_confidence",
    "calculated_at",
    "updated_at",
]


def insert_query(
    table_name: str,
    columns: list[str],
) -> str:
    names = ", ".join(
        f'"{column}"'
        for column in columns
    )

    placeholders = ", ".join(
        "?"
        for _ in columns
    )

    return (
        f'INSERT INTO "{table_name}" '
        f'({names}) VALUES ({placeholders})'
    )


def save_rankings(
    rankings: list[dict[str, Any]],
    categories: list[dict[str, Any]],
) -> tuple[int, int, int]:
    connection = connect()
    observed_at = now_iso()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        connection.execute(
            "DELETE FROM elite_wallet_category_weights"
        )

        connection.execute(
            "DELETE FROM elite_wallet_rankings"
        )

        ranking_query = insert_query(
            "elite_wallet_rankings",
            RANKING_COLUMNS,
        )

        category_query = insert_query(
            "elite_wallet_category_weights",
            CATEGORY_COLUMNS,
        )

        for row in rankings:
            connection.execute(
                ranking_query,
                tuple(
                    row[column]
                    for column
                    in RANKING_COLUMNS
                ),
            )

            connection.execute(
                """
                INSERT INTO elite_wallet_history (
                    wallet,
                    elite_rank,
                    elite_tier,
                    influence_score,
                    trust_weight,
                    consensus_weight,
                    prediction_weight,
                    reliability_index,
                    overall_research_weight,
                    alpha_score,
                    performance_score,
                    dna_score,
                    ledger_quality_score,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    row["wallet"],
                    row["elite_rank"],
                    row["elite_tier"],
                    row[
                        "influence_score"
                    ],
                    row["trust_weight"],
                    row[
                        "consensus_weight"
                    ],
                    row[
                        "prediction_weight"
                    ],
                    row[
                        "reliability_index"
                    ],
                    row[
                        "overall_research_weight"
                    ],
                    row["alpha_score"],
                    row[
                        "performance_score"
                    ],
                    row["dna_score"],
                    row[
                        "ledger_quality_score"
                    ],
                    observed_at,
                ),
            )

        for row in categories:
            connection.execute(
                category_query,
                tuple(
                    row[column]
                    for column
                    in CATEGORY_COLUMNS
                ),
            )

        connection.commit()

        return (
            len(rankings),
            len(categories),
            len(rankings),
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run() -> tuple[int, datetime]:
    started = now_utc()
    connection = connect()

    try:
        cursor = connection.execute(
            """
            INSERT INTO elite_wallet_runs (
                started_at,
                status
            )
            VALUES (
                ?,
                'RUNNING'
            )
            """,
            (started.isoformat(),),
        )

        connection.commit()

        return (
            cursor.lastrowid,
            started,
        )

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started: datetime,
    status: str,
    wallets_loaded: int,
    rankings_saved: int,
    category_rows_saved: int,
    history_rows_saved: int,
    error_message: str = "",
) -> None:
    finished = now_utc()
    connection = connect()

    try:
        connection.execute(
            """
            UPDATE elite_wallet_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                wallets_loaded = ?,
                rankings_saved = ?,
                category_rows_saved = ?,
                history_rows_saved = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                finished.isoformat(),
                (
                    finished
                    - started
                ).total_seconds(),
                wallets_loaded,
                rankings_saved,
                category_rows_saved,
                history_rows_saved,
                status,
                error_message,
                run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# DISPLAY
# =============================================================================


def display_summary(
    rankings: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    display_limit: int,
) -> None:
    print()
    print("=" * 112)
    print("ELITE WALLET RANKING ENGINE SUMMARY")
    print("=" * 112)

    print(
        f"Wallets ranked:                 "
        f"{len(rankings)}"
    )

    print(
        f"Category weight rows:           "
        f"{len(categories)}"
    )

    for tier in (
        "INSTITUTIONAL",
        "ELITE",
        "PROFESSIONAL",
        "WATCHLIST",
        "EXCLUDE",
    ):
        print(
            f"{tier + ':':<32}"
            f"{sum(1 for row in rankings if row['elite_tier'] == tier):>8}"
        )

    print("=" * 112)

    print()
    print("TOP ELITE WALLET RANKINGS")

    for row in rankings[:display_limit]:
        strengths = json.loads(
            row["strengths_json"]
        )

        risks = json.loads(
            row["risks_json"]
        )

        print()
        print("-" * 112)

        print(
            f"#{row['elite_rank']} "
            f"{row['wallet']}"
        )

        print("-" * 112)

        print(
            f"Tier / influence:               "
            f"{row['elite_tier']} "
            f"/ {row['influence_score']:.1f}"
        )

        print(
            f"Trust / consensus / prediction: "
            f"{row['trust_weight']:.3f} "
            f"/ {row['consensus_weight']:.3f} "
            f"/ {row['prediction_weight']:.3f}"
        )

        print(
            f"Research weight / reliability:  "
            f"{row['overall_research_weight']:.3f} "
            f"/ {row['reliability_index']:.1f}"
        )

        print(
            f"Alpha / Performance / DNA:      "
            f"{row['alpha_score']:.1f} "
            f"/ {row['performance_score']:.1f} "
            f"/ {row['dna_score']:.1f}"
        )

        print(
            f"Ledger quality / events:        "
            f"{row['ledger_quality_score']:.1f} "
            f"/ {row['trade_event_count']}"
        )

        print(
            f"Closed / resolved positions:    "
            f"{row['closed_position_count']} "
            f"/ {row['resolved_positions']}"
        )

        print(
            f"Realized / total ROI:           "
            f"{percentage(row['realized_roi'])} "
            f"/ {percentage(row['total_roi'])}"
        )

        print(
            f"Total estimated PnL:            "
            f"{money(row['total_estimated_pnl'])}"
        )

        print(
            f"Primary category / specialty:   "
            f"{row['primary_category'] or '-'} "
            f"/ {row['sports_specialty'] or row['market_type_specialty'] or '-'}"
        )

        print(
            f"Sports / Politics / Crypto:     "
            f"{row['sports_expertise_score']:.1f} "
            f"/ {row['politics_expertise_score']:.1f} "
            f"/ {row['crypto_expertise_score']:.1f}"
        )

        print(
            f"Confidence / penalty:           "
            f"{row['alpha_confidence']} "
            f"/ -{row['total_penalty']:.1f}"
        )

        if strengths:
            print(
                "Strengths:                       "
                + ", ".join(
                    strengths
                )
            )

        if risks:
            print(
                "Risks:                           "
                + ", ".join(
                    risks
                )
            )


# =============================================================================
# MAIN
# =============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rank wallets by influence, trust, reliability, "
            "consensus weight, prediction weight and category expertise."
        )
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8()
    arguments = parse_args()

    print()
    print("=" * 112)
    print("POLYMARKET ELITE WALLET RANKING ENGINE v1")
    print("=" * 112)

    print(
        f"Database: {DB}"
    )

    print(
        "Method: alpha + performance + DNA + ledger + specialization"
    )

    create_tables()

    run_id, started = start_run()

    rankings: list[
        dict[str, Any]
    ] = []

    categories: list[
        dict[str, Any]
    ] = []

    rankings_saved = 0
    categories_saved = 0
    history_saved = 0

    try:
        (
            rankings,
            categories,
        ) = build_rankings()

        (
            rankings_saved,
            categories_saved,
            history_saved,
        ) = save_rankings(
            rankings,
            categories,
        )

        finish_run(
            run_id=run_id,
            started=started,
            status="SUCCESS",
            wallets_loaded=(
                len(rankings)
            ),
            rankings_saved=(
                rankings_saved
            ),
            category_rows_saved=(
                categories_saved
            ),
            history_rows_saved=(
                history_saved
            ),
        )

        display_summary(
            rankings,
            categories,
            max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 112)
        print("ELITE WALLET RANKING ENGINE COMPLETE")
        print("=" * 112)

        print(
            "Current rankings were saved to "
            "elite_wallet_rankings."
        )

        print(
            "Category-specific influence weights were saved to "
            "elite_wallet_category_weights."
        )

        print(
            "Historical ranking snapshots were saved to "
            "elite_wallet_history."
        )

        print(
            "These weights are intended for consensus and "
            "prediction weighting, not direct position sizing."
        )

        print("=" * 112)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started=started,
            status="FAILED",
            wallets_loaded=(
                len(rankings)
            ),
            rankings_saved=(
                rankings_saved
            ),
            category_rows_saved=(
                categories_saved
            ),
            history_rows_saved=(
                history_saved
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()