from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 30
DEFAULT_MAX_CANDIDATES = 0

PROTECTED_STATUSES = {
    "QUALIFIED",
    "ELITE",
}

NON_PROMOTABLE_STATUSES = {
    "REJECTED",
}

ALLOWED_STATUSES = {
    "CANDIDATE",
    "WATCHLIST",
    "QUALIFIED",
    "ELITE",
    "DORMANT",
    "REJECTED",
}


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)

        try:
            stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )
        except (AttributeError, OSError):
            pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_wallet(value: Any) -> str:
    return clean_text(value).lower()


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(value, maximum))


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def format_money(value: Any) -> str:
    number = safe_float(value)

    if number > 0:
        return f"+${number:,.2f}"

    if number < 0:
        return f"-${abs(number):,.2f}"

    return "$0.00"


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(
        DATABASE_PATH,
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
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not table_exists(
        connection,
        table_name,
    ):
        return set()

    return {
        clean_text(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def require_table(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    if not table_exists(
        connection,
        table_name,
    ):
        raise RuntimeError(
            f"Required table is missing: {table_name}"
        )


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_qualification_tables() -> None:
    connection = connect_database()

    try:
        require_table(
            connection,
            "wallet_registry",
        )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidate_wallet_evaluations (
                wallet TEXT PRIMARY KEY,

                evaluation_score REAL
                    NOT NULL DEFAULT 0,

                evaluation_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                recommended_status TEXT
                    NOT NULL DEFAULT 'CANDIDATE',

                current_status TEXT
                    NOT NULL DEFAULT 'CANDIDATE',

                status_changed INTEGER
                    NOT NULL DEFAULT 0,

                qualification_ready INTEGER
                    NOT NULL DEFAULT 0,

                needs_position_scan INTEGER
                    NOT NULL DEFAULT 1,

                needs_history_scan INTEGER
                    NOT NULL DEFAULT 1,

                needs_manual_review INTEGER
                    NOT NULL DEFAULT 0,

                discovery_score REAL
                    NOT NULL DEFAULT 0,

                leaderboard_score REAL
                    NOT NULL DEFAULT 0,

                recurrence_score REAL
                    NOT NULL DEFAULT 0,

                rank_quality_score REAL
                    NOT NULL DEFAULT 0,

                pnl_quality_score REAL
                    NOT NULL DEFAULT 0,

                volume_quality_score REAL
                    NOT NULL DEFAULT 0,

                sports_relevance_score REAL
                    NOT NULL DEFAULT 0,

                analytical_evidence_score REAL
                    NOT NULL DEFAULT 0,

                alpha_score REAL,
                alpha_grade TEXT,
                alpha_confidence TEXT,

                elite_influence_score REAL,
                elite_tier TEXT,

                performance_score REAL,
                performance_grade TEXT,

                dna_score REAL,
                dna_grade TEXT,

                ledger_quality_score REAL,
                ledger_confidence TEXT,

                trade_event_count INTEGER
                    NOT NULL DEFAULT 0,

                closed_position_count INTEGER
                    NOT NULL DEFAULT 0,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                leaderboard_appearances INTEGER
                    NOT NULL DEFAULT 0,

                best_rank INTEGER,

                weekly_pnl_appearances INTEGER
                    NOT NULL DEFAULT 0,

                weekly_volume_appearances INTEGER
                    NOT NULL DEFAULT 0,

                monthly_pnl_appearances INTEGER
                    NOT NULL DEFAULT 0,

                all_time_pnl_appearances INTEGER
                    NOT NULL DEFAULT 0,

                sports_appearances INTEGER
                    NOT NULL DEFAULT 0,

                latest_pnl REAL
                    NOT NULL DEFAULT 0,

                best_observed_pnl REAL
                    NOT NULL DEFAULT 0,

                latest_volume REAL
                    NOT NULL DEFAULT 0,

                highest_observed_volume REAL
                    NOT NULL DEFAULT 0,

                positive_evidence_count INTEGER
                    NOT NULL DEFAULT 0,

                risk_flag_count INTEGER
                    NOT NULL DEFAULT 0,

                positive_evidence_json TEXT,
                risk_flags_json TEXT,
                explanation_json TEXT,

                evaluated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_candidate_wallet_evaluations_score
            ON candidate_wallet_evaluations(
                evaluation_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_candidate_wallet_evaluations_status
            ON candidate_wallet_evaluations(
                recommended_status,
                qualification_ready,
                evaluation_score DESC
            );

            CREATE TABLE IF NOT EXISTS candidate_qualification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,

                evaluation_score REAL,
                evaluation_grade TEXT,

                previous_status TEXT,
                recommended_status TEXT,
                resulting_status TEXT,

                qualification_ready INTEGER,
                needs_position_scan INTEGER,
                needs_history_scan INTEGER,

                analytical_evidence_score REAL,
                leaderboard_appearances INTEGER,
                alpha_score REAL,
                elite_influence_score REAL,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_candidate_qualification_history_wallet
            ON candidate_qualification_history(
                wallet,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS candidate_qualification_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                candidates_loaded INTEGER
                    NOT NULL DEFAULT 0,

                evaluations_saved INTEGER
                    NOT NULL DEFAULT 0,

                watchlist_recommendations INTEGER
                    NOT NULL DEFAULT 0,

                qualification_recommendations INTEGER
                    NOT NULL DEFAULT 0,

                candidates_promoted INTEGER
                    NOT NULL DEFAULT 0,

                protected_wallets_preserved INTEGER
                    NOT NULL DEFAULT 0,

                scan_required_count INTEGER
                    NOT NULL DEFAULT 0,

                manual_review_count INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                apply_status_changes INTEGER
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
# SOURCE LOADING
# =============================================================================


def load_table_by_wallet(
    table_name: str,
) -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            table_name,
        ):
            return {}

        columns = table_columns(
            connection,
            table_name,
        )

        if "wallet" not in columns:
            return {}

        rows = connection.execute(
            f'SELECT * FROM "{table_name}"'
        ).fetchall()

        return {
            normalize_wallet(
                row["wallet"]
            ): dict(row)
            for row in rows
            if normalize_wallet(
                row["wallet"]
            )
        }

    finally:
        connection.close()


def load_registry_candidates(
    max_candidates: int,
) -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        require_table(
            connection,
            "wallet_registry",
        )

        sql = """
            SELECT *
            FROM wallet_registry
            WHERE status IN (
                'CANDIDATE',
                'WATCHLIST',
                'QUALIFIED',
                'ELITE'
            )
            ORDER BY
                CASE status
                    WHEN 'ELITE' THEN 1
                    WHEN 'QUALIFIED' THEN 2
                    WHEN 'WATCHLIST' THEN 3
                    ELSE 4
                END,
                qualification_eligible DESC,
                leaderboard_appearance_count DESC,
                best_rank ASC,
                best_observed_pnl DESC
        """

        parameters: tuple[Any, ...] = ()

        if max_candidates > 0:
            sql += " LIMIT ?"
            parameters = (
                max_candidates,
            )

        rows = connection.execute(
            sql,
            parameters,
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


# =============================================================================
# SCORING
# =============================================================================


def logarithmic_score(
    value: float,
    reference: float,
) -> float:
    if value <= 0:
        return 0.0

    return clamp(
        math.log1p(value)
        / math.log1p(reference)
        * 100.0
    )


def rank_quality_score(
    best_rank: int,
) -> float:
    if best_rank <= 0:
        return 0.0

    if best_rank <= 5:
        return 100.0

    if best_rank <= 10:
        return 92.0

    if best_rank <= 25:
        return 82.0

    if best_rank <= 50:
        return 70.0

    if best_rank <= 100:
        return 56.0

    if best_rank <= 250:
        return 38.0

    return 20.0


def grade_from_score(
    score: float,
) -> str:
    if score >= 85:
        return "S"

    if score >= 75:
        return "A+"

    if score >= 65:
        return "A"

    if score >= 55:
        return "B"

    if score >= 45:
        return "WATCH"

    return "PASS"


def calculate_analytical_evidence_score(
    alpha: dict[str, Any],
    elite: dict[str, Any],
    performance: dict[str, Any],
    dna: dict[str, Any],
    ledger: dict[str, Any],
) -> tuple[float, int]:
    source_scores: list[float] = []

    if alpha:
        source_scores.append(
            safe_float(
                alpha.get(
                    "alpha_score"
                )
            )
        )

    if elite:
        source_scores.append(
            safe_float(
                elite.get(
                    "influence_score"
                )
            )
        )

    if performance:
        source_scores.append(
            safe_float(
                performance.get(
                    "performance_score"
                ),
                50.0,
            )
        )

    if dna:
        source_scores.append(
            safe_float(
                dna.get(
                    "dna_score"
                ),
                50.0,
            )
        )

    if ledger:
        source_scores.append(
            safe_float(
                ledger.get(
                    "complete_history_score"
                )
            )
        )

    if not source_scores:
        return 0.0, 0

    return (
        sum(source_scores)
        / len(source_scores),
        len(source_scores),
    )


def determine_recommended_status(
    current_status: str,
    evaluation_score: float,
    analytical_source_count: int,
    analytical_evidence_score: float,
    alpha_score: float | None,
    elite_influence_score: float | None,
    ledger_quality_score: float | None,
    trade_event_count: int,
    closed_position_count: int,
    leaderboard_appearances: int,
    risk_flags: list[str],
) -> tuple[str, int, int, int]:
    if current_status == "ELITE":
        return (
            "ELITE",
            1,
            0,
            0,
        )

    if current_status == "QUALIFIED":
        return (
            "QUALIFIED",
            1,
            0,
            0,
        )

    has_analytics = (
        analytical_source_count >= 3
    )

    strong_alpha = (
        alpha_score is not None
        and alpha_score >= 58.0
    )

    strong_influence = (
        elite_influence_score is not None
        and elite_influence_score >= 60.0
    )

    adequate_ledger = (
        ledger_quality_score is not None
        and ledger_quality_score >= 50.0
        and trade_event_count >= 10
    )

    closed_sample_ok = (
        closed_position_count >= 2
    )

    qualification_ready = int(
        evaluation_score >= 64.0
        and analytical_evidence_score >= 55.0
        and has_analytics
        and adequate_ledger
        and (
            strong_alpha
            or strong_influence
        )
        and len(
            risk_flags
        )
        <= 2
    )

    if qualification_ready:
        return (
            "QUALIFIED",
            1,
            0,
            0,
        )

    watchlist_ready = (
        evaluation_score >= 48.0
        or leaderboard_appearances >= 3
        or (
            analytical_source_count >= 1
            and analytical_evidence_score >= 45.0
        )
    )

    needs_position_scan = int(
        analytical_source_count == 0
    )

    needs_history_scan = int(
        not adequate_ledger
        or not closed_sample_ok
    )

    if watchlist_ready:
        return (
            "WATCHLIST",
            0,
            needs_position_scan,
            needs_history_scan,
        )

    return (
        "CANDIDATE",
        0,
        needs_position_scan,
        needs_history_scan,
    )


def build_evaluations(
    max_candidates: int,
) -> list[dict[str, Any]]:
    registry_rows = load_registry_candidates(
        max_candidates=max_candidates
    )

    if not registry_rows:
        raise RuntimeError(
            "No candidate wallets found in wallet_registry. "
            "Run weekly_wallet_discovery.py first."
        )

    alpha_lookup = load_table_by_wallet(
        "wallet_alpha_profiles"
    )

    elite_lookup = load_table_by_wallet(
        "elite_wallet_rankings"
    )

    performance_lookup = load_table_by_wallet(
        "wallet_performance"
    )

    dna_lookup = load_table_by_wallet(
        "wallet_dna_profiles"
    )

    ledger_lookup = load_table_by_wallet(
        "wallet_trade_ledger_summary"
    )

    evaluated_at = utc_now_iso()
    evaluations: list[
        dict[str, Any]
    ] = []

    for registry in registry_rows:
        wallet = normalize_wallet(
            registry.get(
                "wallet"
            )
        )

        current_status = (
            clean_text(
                registry.get(
                    "status"
                )
            ).upper()
            or "CANDIDATE"
        )

        if current_status not in ALLOWED_STATUSES:
            current_status = "CANDIDATE"

        alpha = alpha_lookup.get(
            wallet,
            {},
        )

        elite = elite_lookup.get(
            wallet,
            {},
        )

        performance = performance_lookup.get(
            wallet,
            {},
        )

        dna = dna_lookup.get(
            wallet,
            {},
        )

        ledger = ledger_lookup.get(
            wallet,
            {},
        )

        leaderboard_appearances = safe_int(
            registry.get(
                "leaderboard_appearance_count"
            )
        )

        best_rank = safe_int(
            registry.get(
                "best_rank"
            )
        )

        weekly_pnl_appearances = safe_int(
            registry.get(
                "weekly_pnl_appearances"
            )
        )

        weekly_volume_appearances = safe_int(
            registry.get(
                "weekly_volume_appearances"
            )
        )

        monthly_pnl_appearances = safe_int(
            registry.get(
                "monthly_pnl_appearances"
            )
        )

        all_time_pnl_appearances = safe_int(
            registry.get(
                "all_time_pnl_appearances"
            )
        )

        sports_appearances = safe_int(
            registry.get(
                "sports_appearances"
            )
        )

        latest_pnl = safe_float(
            registry.get(
                "latest_pnl"
            )
        )

        best_observed_pnl = safe_float(
            registry.get(
                "best_observed_pnl"
            )
        )

        latest_volume = safe_float(
            registry.get(
                "latest_volume"
            )
        )

        highest_observed_volume = safe_float(
            registry.get(
                "highest_observed_volume"
            )
        )

        recurrence_score = clamp(
            leaderboard_appearances
            / 9.0
            * 100.0
        )

        rank_score = rank_quality_score(
            best_rank
        )

        pnl_score = logarithmic_score(
            max(
                best_observed_pnl,
                0.0,
            ),
            10_000_000.0,
        )

        volume_score = logarithmic_score(
            max(
                highest_observed_volume,
                0.0,
            ),
            1_000_000_000.0,
        )

        sports_relevance_score = clamp(
            sports_appearances
            / max(
                leaderboard_appearances,
                1,
            )
            * 100.0
        )

        leaderboard_score = clamp(
            recurrence_score * 0.35
            + rank_score * 0.30
            + pnl_score * 0.20
            + volume_score * 0.15
        )

        discovery_score = clamp(
            leaderboard_score * 0.75
            + sports_relevance_score * 0.15
            + min(
                weekly_pnl_appearances
                + monthly_pnl_appearances,
                4,
            )
            / 4.0
            * 10.0
        )

        (
            analytical_evidence_score,
            analytical_source_count,
        ) = calculate_analytical_evidence_score(
            alpha=alpha,
            elite=elite,
            performance=performance,
            dna=dna,
            ledger=ledger,
        )

        alpha_score = (
            safe_float(
                alpha.get(
                    "alpha_score"
                )
            )
            if alpha
            else None
        )

        elite_influence_score = (
            safe_float(
                elite.get(
                    "influence_score"
                )
            )
            if elite
            else None
        )

        performance_score = (
            safe_float(
                performance.get(
                    "performance_score"
                ),
                50.0,
            )
            if performance
            else None
        )

        dna_score = (
            safe_float(
                dna.get(
                    "dna_score"
                ),
                50.0,
            )
            if dna
            else None
        )

        ledger_quality_score = (
            safe_float(
                ledger.get(
                    "complete_history_score"
                )
            )
            if ledger
            else None
        )

        trade_event_count = safe_int(
            ledger.get(
                "trade_event_count"
            )
        )

        closed_position_count = safe_int(
            ledger.get(
                "closed_position_count"
            )
        )

        resolved_positions = safe_int(
            performance.get(
                "resolved_positions"
            )
        )

        positive_evidence: list[str] = []
        risk_flags: list[str] = []

        if leaderboard_appearances >= 6:
            positive_evidence.append(
                "Appears across many official leaderboard boards"
            )

        elif leaderboard_appearances >= 3:
            positive_evidence.append(
                "Repeated official leaderboard appearances"
            )

        if best_rank > 0 and best_rank <= 25:
            positive_evidence.append(
                "Top-25 leaderboard rank observed"
            )

        if sports_appearances >= 3:
            positive_evidence.append(
                "Repeated sports leaderboard presence"
            )

        if alpha_score is not None and alpha_score >= 58:
            positive_evidence.append(
                "Positive observed alpha profile"
            )

        if (
            elite_influence_score is not None
            and elite_influence_score >= 60
        ):
            positive_evidence.append(
                "Strong existing influence score"
            )

        if (
            ledger_quality_score is not None
            and ledger_quality_score >= 60
        ):
            positive_evidence.append(
                "Substantial reconstructed trade history"
            )

        if analytical_source_count == 0:
            risk_flags.append(
                "No tracked position or historical analytics yet"
            )

        if leaderboard_appearances < 2:
            risk_flags.append(
                "One-off leaderboard appearance"
            )

        if best_observed_pnl < 0:
            risk_flags.append(
                "Negative observed leaderboard PnL"
            )

        if (
            alpha_score is not None
            and alpha_score < 48
        ):
            risk_flags.append(
                "Weak observed alpha score"
            )

        if (
            elite_influence_score is not None
            and elite_influence_score < 50
        ):
            risk_flags.append(
                "Weak influence score"
            )

        if (
            ledger_quality_score is not None
            and ledger_quality_score < 40
        ):
            risk_flags.append(
                "Incomplete trade-history coverage"
            )

        analytics_weight = (
            0.60
            if analytical_source_count >= 3
            else (
                0.40
                if analytical_source_count >= 1
                else 0.0
            )
        )

        discovery_weight = (
            1.0
            - analytics_weight
        )

        evaluation_score = clamp(
            discovery_score
            * discovery_weight
            + analytical_evidence_score
            * analytics_weight
        )

        if analytical_source_count == 0:
            evaluation_score = min(
                evaluation_score,
                59.9,
            )

        (
            recommended_status,
            qualification_ready,
            needs_position_scan,
            needs_history_scan,
        ) = determine_recommended_status(
            current_status=current_status,
            evaluation_score=(
                evaluation_score
            ),
            analytical_source_count=(
                analytical_source_count
            ),
            analytical_evidence_score=(
                analytical_evidence_score
            ),
            alpha_score=alpha_score,
            elite_influence_score=(
                elite_influence_score
            ),
            ledger_quality_score=(
                ledger_quality_score
            ),
            trade_event_count=(
                trade_event_count
            ),
            closed_position_count=(
                closed_position_count
            ),
            leaderboard_appearances=(
                leaderboard_appearances
            ),
            risk_flags=risk_flags,
        )

        needs_manual_review = int(
            (
                recommended_status
                == "QUALIFIED"
            )
            and (
                resolved_positions < 3
                or closed_position_count < 3
            )
        )

        if needs_manual_review:
            recommended_status = (
                "WATCHLIST"
            )

            qualification_ready = 0

            risk_flags.append(
                "Qualification held for manual review due to limited resolved history"
            )

        explanation = {
            "model_version": "1.0",
            "purpose": (
                "Separate discovery evidence from trusted "
                "historical qualification."
            ),
            "weights": {
                "discovery_weight": (
                    discovery_weight
                ),
                "analytics_weight": (
                    analytics_weight
                ),
            },
            "analytical_source_count": (
                analytical_source_count
            ),
            "important_rules": [
                (
                    "Leaderboard success alone cannot produce "
                    "automatic QUALIFIED status."
                ),
                (
                    "New candidates require tracked positions "
                    "and historical evidence before trusted consensus."
                ),
                (
                    "Existing QUALIFIED and ELITE statuses are preserved."
                ),
            ],
        }

        evaluations.append(
            {
                "wallet": wallet,
                "evaluation_score": round(
                    evaluation_score,
                    1,
                ),
                "evaluation_grade": (
                    grade_from_score(
                        evaluation_score
                    )
                ),
                "recommended_status": (
                    recommended_status
                ),
                "current_status": (
                    current_status
                ),
                "status_changed": int(
                    recommended_status
                    != current_status
                ),
                "qualification_ready": (
                    qualification_ready
                ),
                "needs_position_scan": (
                    needs_position_scan
                ),
                "needs_history_scan": (
                    needs_history_scan
                ),
                "needs_manual_review": (
                    needs_manual_review
                ),
                "discovery_score": (
                    discovery_score
                ),
                "leaderboard_score": (
                    leaderboard_score
                ),
                "recurrence_score": (
                    recurrence_score
                ),
                "rank_quality_score": (
                    rank_score
                ),
                "pnl_quality_score": (
                    pnl_score
                ),
                "volume_quality_score": (
                    volume_score
                ),
                "sports_relevance_score": (
                    sports_relevance_score
                ),
                "analytical_evidence_score": (
                    analytical_evidence_score
                ),
                "alpha_score": alpha_score,
                "alpha_grade": (
                    clean_text(
                        alpha.get(
                            "alpha_grade"
                        )
                    )
                    if alpha
                    else ""
                ),
                "alpha_confidence": (
                    clean_text(
                        alpha.get(
                            "data_confidence"
                        )
                    )
                    if alpha
                    else ""
                ),
                "elite_influence_score": (
                    elite_influence_score
                ),
                "elite_tier": (
                    clean_text(
                        elite.get(
                            "elite_tier"
                        )
                    )
                    if elite
                    else ""
                ),
                "performance_score": (
                    performance_score
                ),
                "performance_grade": (
                    clean_text(
                        performance.get(
                            "performance_grade"
                        )
                    )
                    if performance
                    else ""
                ),
                "dna_score": dna_score,
                "dna_grade": (
                    clean_text(
                        dna.get(
                            "dna_grade"
                        )
                    )
                    if dna
                    else ""
                ),
                "ledger_quality_score": (
                    ledger_quality_score
                ),
                "ledger_confidence": (
                    clean_text(
                        ledger.get(
                            "ledger_confidence"
                        )
                    )
                    if ledger
                    else ""
                ),
                "trade_event_count": (
                    trade_event_count
                ),
                "closed_position_count": (
                    closed_position_count
                ),
                "resolved_positions": (
                    resolved_positions
                ),
                "leaderboard_appearances": (
                    leaderboard_appearances
                ),
                "best_rank": best_rank,
                "weekly_pnl_appearances": (
                    weekly_pnl_appearances
                ),
                "weekly_volume_appearances": (
                    weekly_volume_appearances
                ),
                "monthly_pnl_appearances": (
                    monthly_pnl_appearances
                ),
                "all_time_pnl_appearances": (
                    all_time_pnl_appearances
                ),
                "sports_appearances": (
                    sports_appearances
                ),
                "latest_pnl": latest_pnl,
                "best_observed_pnl": (
                    best_observed_pnl
                ),
                "latest_volume": (
                    latest_volume
                ),
                "highest_observed_volume": (
                    highest_observed_volume
                ),
                "positive_evidence_count": (
                    len(
                        positive_evidence
                    )
                ),
                "risk_flag_count": (
                    len(
                        risk_flags
                    )
                ),
                "positive_evidence_json": (
                    stable_json(
                        positive_evidence
                    )
                ),
                "risk_flags_json": (
                    stable_json(
                        risk_flags
                    )
                ),
                "explanation_json": (
                    stable_json(
                        explanation
                    )
                ),
                "evaluated_at": (
                    evaluated_at
                ),
                "updated_at": (
                    evaluated_at
                ),
            }
        )

    evaluations.sort(
        key=lambda row: (
            row[
                "qualification_ready"
            ],
            row[
                "evaluation_score"
            ],
            row[
                "analytical_evidence_score"
            ],
            row[
                "leaderboard_appearances"
            ],
        ),
        reverse=True,
    )

    return evaluations


# =============================================================================
# SAVING
# =============================================================================


EVALUATION_COLUMNS = [
    "wallet",
    "evaluation_score",
    "evaluation_grade",
    "recommended_status",
    "current_status",
    "status_changed",
    "qualification_ready",
    "needs_position_scan",
    "needs_history_scan",
    "needs_manual_review",
    "discovery_score",
    "leaderboard_score",
    "recurrence_score",
    "rank_quality_score",
    "pnl_quality_score",
    "volume_quality_score",
    "sports_relevance_score",
    "analytical_evidence_score",
    "alpha_score",
    "alpha_grade",
    "alpha_confidence",
    "elite_influence_score",
    "elite_tier",
    "performance_score",
    "performance_grade",
    "dna_score",
    "dna_grade",
    "ledger_quality_score",
    "ledger_confidence",
    "trade_event_count",
    "closed_position_count",
    "resolved_positions",
    "leaderboard_appearances",
    "best_rank",
    "weekly_pnl_appearances",
    "weekly_volume_appearances",
    "monthly_pnl_appearances",
    "all_time_pnl_appearances",
    "sports_appearances",
    "latest_pnl",
    "best_observed_pnl",
    "latest_volume",
    "highest_observed_volume",
    "positive_evidence_count",
    "risk_flag_count",
    "positive_evidence_json",
    "risk_flags_json",
    "explanation_json",
    "evaluated_at",
    "updated_at",
]


def build_insert_query(
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


def save_evaluations(
    evaluations: list[dict[str, Any]],
    apply_status_changes: bool,
) -> tuple[int, int, int]:
    connection = connect_database()
    observed_at = utc_now_iso()

    evaluation_query = (
        build_insert_query(
            "candidate_wallet_evaluations",
            EVALUATION_COLUMNS,
        )
    )

    promoted_count = 0
    history_rows_saved = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        connection.execute(
            "DELETE FROM candidate_wallet_evaluations"
        )

        for row in evaluations:
            previous_status = row[
                "current_status"
            ]

            resulting_status = (
                previous_status
            )

            if apply_status_changes:
                recommended_status = row[
                    "recommended_status"
                ]

                if (
                    previous_status
                    in PROTECTED_STATUSES
                ):
                    resulting_status = (
                        previous_status
                    )

                elif (
                    previous_status
                    in NON_PROMOTABLE_STATUSES
                ):
                    resulting_status = (
                        previous_status
                    )

                elif recommended_status in {
                    "WATCHLIST",
                    "QUALIFIED",
                }:
                    resulting_status = (
                        recommended_status
                    )

                if (
                    resulting_status
                    != previous_status
                ):
                    connection.execute(
                        """
                        UPDATE wallet_registry
                        SET
                            status = ?,
                            active_for_scanning = ?,
                            updated_at = ?
                        WHERE wallet = ?
                        """,
                        (
                            resulting_status,
                            int(
                                resulting_status
                                in {
                                    "QUALIFIED",
                                    "ELITE",
                                }
                            ),
                            observed_at,
                            row["wallet"],
                        ),
                    )

                    connection.execute(
                        """
                        INSERT INTO wallet_status_history (
                            wallet,
                            previous_status,
                            new_status,
                            reason,
                            source_module,
                            changed_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?,
                            ?
                        )
                        """,
                        (
                            row["wallet"],
                            previous_status,
                            resulting_status,
                            (
                                "Candidate qualification "
                                f"score {row['evaluation_score']:.1f}; "
                                f"recommended {row['recommended_status']}."
                            ),
                            (
                                "candidate_qualification_engine"
                            ),
                            observed_at,
                        ),
                    )

                    promoted_count += 1

            row_to_save = dict(row)

            row_to_save[
                "status_changed"
            ] = int(
                resulting_status
                != previous_status
            )

            connection.execute(
                evaluation_query,
                tuple(
                    row_to_save[column]
                    for column
                    in EVALUATION_COLUMNS
                ),
            )

            connection.execute(
                """
                INSERT INTO candidate_qualification_history (
                    wallet,
                    evaluation_score,
                    evaluation_grade,
                    previous_status,
                    recommended_status,
                    resulting_status,
                    qualification_ready,
                    needs_position_scan,
                    needs_history_scan,
                    analytical_evidence_score,
                    leaderboard_appearances,
                    alpha_score,
                    elite_influence_score,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    row["wallet"],
                    row[
                        "evaluation_score"
                    ],
                    row[
                        "evaluation_grade"
                    ],
                    previous_status,
                    row[
                        "recommended_status"
                    ],
                    resulting_status,
                    row[
                        "qualification_ready"
                    ],
                    row[
                        "needs_position_scan"
                    ],
                    row[
                        "needs_history_scan"
                    ],
                    row[
                        "analytical_evidence_score"
                    ],
                    row[
                        "leaderboard_appearances"
                    ],
                    row[
                        "alpha_score"
                    ],
                    row[
                        "elite_influence_score"
                    ],
                    observed_at,
                ),
            )

            history_rows_saved += 1

        connection.commit()

        return (
            len(evaluations),
            promoted_count,
            history_rows_saved,
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run(
    apply_status_changes: bool,
) -> tuple[int, datetime]:
    started_at = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO candidate_qualification_runs (
                started_at,
                apply_status_changes,
                status
            )
            VALUES (
                ?, ?, 'RUNNING'
            )
            """,
            (
                started_at.isoformat(),
                int(
                    apply_status_changes
                ),
            ),
        )

        connection.commit()

        return (
            cursor.lastrowid,
            started_at,
        )

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started_at: datetime,
    status: str,
    evaluations: list[dict[str, Any]],
    evaluations_saved: int,
    candidates_promoted: int,
    history_rows_saved: int,
    apply_status_changes: bool,
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE candidate_qualification_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                candidates_loaded = ?,
                evaluations_saved = ?,
                watchlist_recommendations = ?,
                qualification_recommendations = ?,
                candidates_promoted = ?,
                protected_wallets_preserved = ?,
                scan_required_count = ?,
                manual_review_count = ?,
                history_rows_saved = ?,
                apply_status_changes = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                finished_at.isoformat(),
                (
                    finished_at
                    - started_at
                ).total_seconds(),
                len(evaluations),
                evaluations_saved,
                sum(
                    1
                    for row in evaluations
                    if row[
                        "recommended_status"
                    ]
                    == "WATCHLIST"
                ),
                sum(
                    1
                    for row in evaluations
                    if row[
                        "recommended_status"
                    ]
                    == "QUALIFIED"
                ),
                candidates_promoted,
                sum(
                    1
                    for row in evaluations
                    if row[
                        "current_status"
                    ]
                    in PROTECTED_STATUSES
                ),
                sum(
                    1
                    for row in evaluations
                    if row[
                        "needs_position_scan"
                    ]
                    or row[
                        "needs_history_scan"
                    ]
                ),
                sum(
                    1
                    for row in evaluations
                    if row[
                        "needs_manual_review"
                    ]
                ),
                history_rows_saved,
                int(
                    apply_status_changes
                ),
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
    evaluations: list[dict[str, Any]],
    promoted_count: int,
    apply_status_changes: bool,
    display_limit: int,
) -> None:
    recommendations = Counter(
        row[
            "recommended_status"
        ]
        for row in evaluations
    )

    print()
    print("=" * 112)
    print("CANDIDATE QUALIFICATION SUMMARY")
    print("=" * 112)

    print(
        f"Wallets evaluated:              "
        f"{len(evaluations)}"
    )

    print(
        f"QUALIFIED recommendations:      "
        f"{recommendations.get('QUALIFIED', 0)}"
    )

    print(
        f"WATCHLIST recommendations:      "
        f"{recommendations.get('WATCHLIST', 0)}"
    )

    print(
        f"CANDIDATE recommendations:      "
        f"{recommendations.get('CANDIDATE', 0)}"
    )

    print(
        f"Position/history scan required: "
        f"{sum(1 for row in evaluations if row['needs_position_scan'] or row['needs_history_scan'])}"
    )

    print(
        f"Manual review required:         "
        f"{sum(1 for row in evaluations if row['needs_manual_review'])}"
    )

    print(
        f"Status changes applied:         "
        f"{promoted_count if apply_status_changes else 0}"
    )

    print(
        f"Operating mode:                 "
        f"{'APPLY STATUS CHANGES' if apply_status_changes else 'DRY RUN / RECOMMENDATIONS ONLY'}"
    )

    print("=" * 112)

    print()
    print("TOP CANDIDATE EVALUATIONS")

    for rank, row in enumerate(
        evaluations[:display_limit],
        start=1,
    ):
        positive_evidence = json.loads(
            row[
                "positive_evidence_json"
            ]
        )

        risk_flags = json.loads(
            row[
                "risk_flags_json"
            ]
        )

        print()
        print("-" * 112)

        print(
            f"{rank}. {row['wallet']}"
        )

        print("-" * 112)

        print(
            f"Score / grade:                  "
            f"{row['evaluation_score']:.1f} "
            f"/ {row['evaluation_grade']}"
        )

        print(
            f"Current / recommended status:   "
            f"{row['current_status']} "
            f"/ {row['recommended_status']}"
        )

        print(
            f"Qualification ready:            "
            f"{'YES' if row['qualification_ready'] else 'NO'}"
        )

        print(
            f"Discovery / analytics score:    "
            f"{row['discovery_score']:.1f} "
            f"/ {row['analytical_evidence_score']:.1f}"
        )

        print(
            f"Appearances / best rank:        "
            f"{row['leaderboard_appearances']} "
            f"/ {row['best_rank'] or '-'}"
        )

        print(
            f"Best PnL / highest volume:      "
            f"{format_money(row['best_observed_pnl'])} "
            f"/ ${row['highest_observed_volume']:,.2f}"
        )

        print(
            f"Alpha / influence:              "
            f"{row['alpha_score'] if row['alpha_score'] is not None else '-'} "
            f"/ "
            f"{row['elite_influence_score'] if row['elite_influence_score'] is not None else '-'}"
        )

        print(
            f"Ledger quality / trade events:  "
            f"{row['ledger_quality_score'] if row['ledger_quality_score'] is not None else '-'} "
            f"/ {row['trade_event_count']}"
        )

        print(
            f"Closed / resolved positions:    "
            f"{row['closed_position_count']} "
            f"/ {row['resolved_positions']}"
        )

        print(
            f"Needs position / history scan:  "
            f"{'YES' if row['needs_position_scan'] else 'NO'} "
            f"/ {'YES' if row['needs_history_scan'] else 'NO'}"
        )

        if positive_evidence:
            print(
                "Positive evidence:              "
                + ", ".join(
                    positive_evidence
                )
            )

        if risk_flags:
            print(
                "Risk flags:                     "
                + ", ".join(
                    risk_flags
                )
            )


# =============================================================================
# ARGUMENTS AND MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate discovered candidate wallets using official "
            "leaderboard recurrence plus any available alpha, "
            "performance, DNA, elite-ranking and inferred-ledger evidence."
        )
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    parser.add_argument(
        "--max-candidates",
        type=int,
        default=DEFAULT_MAX_CANDIDATES,
        help=(
            "Maximum registry wallets to evaluate. "
            "Use 0 for all eligible registry records."
        ),
    )

    parser.add_argument(
        "--apply-status-changes",
        action="store_true",
        help=(
            "Apply WATCHLIST and QUALIFIED promotions to wallet_registry. "
            "Without this flag, the engine runs in recommendation-only mode."
        ),
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8_output()
    arguments = parse_arguments()

    print()
    print("=" * 112)
    print("POLYMARKET CANDIDATE QUALIFICATION ENGINE v1")
    print("=" * 112)

    print(
        f"Database:                    {DATABASE_PATH}"
    )

    print(
        "Method:                     "
        "DISCOVERY EVIDENCE + TRUSTED HISTORICAL ANALYTICS"
    )

    print(
        f"Status changes:              "
        f"{'ENABLED' if arguments.apply_status_changes else 'DISABLED (DRY RUN)'}"
    )

    print(
        "Core rule:                  "
        "LEADERBOARD SUCCESS ALONE CANNOT QUALIFY A WALLET"
    )

    print("=" * 112)

    create_qualification_tables()

    run_id, started_at = start_run(
        apply_status_changes=(
            arguments.apply_status_changes
        )
    )

    evaluations: list[
        dict[str, Any]
    ] = []

    evaluations_saved = 0
    promoted_count = 0
    history_rows_saved = 0

    try:
        evaluations = build_evaluations(
            max_candidates=max(
                arguments.max_candidates,
                0,
            )
        )

        (
            evaluations_saved,
            promoted_count,
            history_rows_saved,
        ) = save_evaluations(
            evaluations=evaluations,
            apply_status_changes=(
                arguments.apply_status_changes
            ),
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            evaluations=evaluations,
            evaluations_saved=(
                evaluations_saved
            ),
            candidates_promoted=(
                promoted_count
            ),
            history_rows_saved=(
                history_rows_saved
            ),
            apply_status_changes=(
                arguments.apply_status_changes
            ),
        )

        display_summary(
            evaluations=evaluations,
            promoted_count=(
                promoted_count
            ),
            apply_status_changes=(
                arguments.apply_status_changes
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 112)
        print("CANDIDATE QUALIFICATION ENGINE COMPLETE")
        print("=" * 112)

        print(
            "Current evaluations:         "
            "candidate_wallet_evaluations"
        )

        print(
            "Historical evaluations:      "
            "candidate_qualification_history"
        )

        print(
            "Run history:                 "
            "candidate_qualification_runs"
        )

        print()

        if arguments.apply_status_changes:
            print(
                "Approved WATCHLIST and QUALIFIED promotions "
                "were applied to wallet_registry."
            )

        else:
            print(
                "Dry-run complete. No wallet_registry statuses "
                "were changed."
            )

            print(
                "Review the output, then rerun with "
                "--apply-status-changes when ready."
            )

        print("=" * 112)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            evaluations=evaluations,
            evaluations_saved=(
                evaluations_saved
            ),
            candidates_promoted=(
                promoted_count
            ),
            history_rows_saved=(
                history_rows_saved
            ),
            apply_status_changes=(
                arguments.apply_status_changes
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()