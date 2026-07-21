from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 30

INACTIVE_STATUSES = {
    "resolved",
    "closed",
    "ended",
    "ended_unconfirmed",
}

LIVE_STATUSES = {
    "live",
    "live_unconfirmed",
    "started",
}

PREGAME_STATUSES = {
    "pregame",
    "starting_soon",
}

MASTER_WEIGHTS = {
    "opportunity": 0.20,
    "institutional": 0.22,
    "evolution": 0.18,
    "closing_line": 0.15,
    "price_action": 0.08,
    "wallet_quality": 0.10,
    "timing": 0.07,
}


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8_output() -> None:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except (AttributeError, OSError):
        pass

    try:
        sys.stderr.reconfigure(
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


def normalize_text(value: Any) -> str:
    return clean_text(value).casefold()


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


def format_money(value: Any) -> str:
    number = safe_float(value)

    if number > 0:
        return f"+${number:,.2f}"

    if number < 0:
        return f"-${abs(number):,.2f}"

    return "$0.00"


def format_percentage(value: Any) -> str:
    return f"{safe_float(value):.1%}"


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
        return (
            f"T-{days}d "
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds_left:02d}"
        )

    return (
        f"T-{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds_left:02d}"
    )


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
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def table_row_count(
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    if not table_exists(connection, table_name):
        return 0

    row = connection.execute(
        f'SELECT COUNT(*) AS total FROM "{table_name}"'
    ).fetchone()

    return safe_int(row["total"] if row else 0)


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_master_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS master_opportunities (
                opportunity_key TEXT PRIMARY KEY,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                market_type TEXT,

                master_score REAL
                    NOT NULL DEFAULT 0,

                master_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                master_tier TEXT
                    NOT NULL DEFAULT 'PASS',

                recommendation TEXT
                    NOT NULL DEFAULT 'PASS',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                opportunity_score REAL
                    NOT NULL DEFAULT 0,

                institutional_score REAL
                    NOT NULL DEFAULT 0,

                evolution_score REAL
                    NOT NULL DEFAULT 0,

                closing_line_score REAL
                    NOT NULL DEFAULT 0,

                price_action_score REAL
                    NOT NULL DEFAULT 0,

                wallet_quality_score REAL
                    NOT NULL DEFAULT 0,

                timing_score REAL
                    NOT NULL DEFAULT 0,

                opportunity_grade TEXT,
                institutional_grade TEXT,
                evolution_grade TEXT,

                institutional_status TEXT,
                evolution_status TEXT,
                closing_recommendation TEXT,
                movement_status TEXT,

                wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                effective_wallet_count REAL
                    NOT NULL DEFAULT 0,

                combined_current_value REAL
                    NOT NULL DEFAULT 0,

                weighted_wallet_quality REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                strengthening_score REAL
                    NOT NULL DEFAULT 0,

                weakening_score REAL
                    NOT NULL DEFAULT 0,

                net_value_change REAL
                    NOT NULL DEFAULT 0,

                elite_wallet_count_change INTEGER
                    NOT NULL DEFAULT 0,

                clv_score REAL,
                edge_remaining_score REAL,
                chase_risk_score REAL,

                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,

                conflict_ratio REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 0,

                remaining_upside REAL
                    NOT NULL DEFAULT 0,

                is_market_leader INTEGER
                    NOT NULL DEFAULT 0,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                source_coverage_score REAL
                    NOT NULL DEFAULT 0,

                source_count INTEGER
                    NOT NULL DEFAULT 0,

                live_penalty REAL
                    NOT NULL DEFAULT 0,

                inactive_penalty REAL
                    NOT NULL DEFAULT 0,

                single_wallet_penalty REAL
                    NOT NULL DEFAULT 0,

                weak_consensus_penalty REAL
                    NOT NULL DEFAULT 0,

                chase_penalty REAL
                    NOT NULL DEFAULT 0,

                conflict_penalty REAL
                    NOT NULL DEFAULT 0,

                reversal_penalty REAL
                    NOT NULL DEFAULT 0,

                low_upside_penalty REAL
                    NOT NULL DEFAULT 0,

                weakening_penalty REAL
                    NOT NULL DEFAULT 0,

                incomplete_data_penalty REAL
                    NOT NULL DEFAULT 0,

                total_penalty REAL
                    NOT NULL DEFAULT 0,

                reasons_json TEXT,
                risk_flags_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_master_opportunities_rank
            ON master_opportunities(
                master_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_master_opportunities_grade
            ON master_opportunities(
                master_grade,
                master_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_master_opportunities_recommendation
            ON master_opportunities(
                recommendation,
                master_score DESC
            );

            CREATE TABLE IF NOT EXISTS master_opportunity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                master_score REAL,
                master_grade TEXT,
                master_tier TEXT,
                recommendation TEXT,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                opportunity_score REAL,
                institutional_score REAL,
                evolution_score REAL,
                closing_line_score REAL,
                price_action_score REAL,
                wallet_quality_score REAL,
                timing_score REAL,

                wallet_count INTEGER,
                elite_wallet_count INTEGER,
                effective_wallet_count REAL,

                combined_current_value REAL,
                consensus_strength REAL,
                strengthening_score REAL,
                weakening_score REAL,
                net_value_change REAL,

                clv_score REAL,
                edge_remaining_score REAL,
                chase_risk_score REAL,

                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,

                conflict_ratio REAL,
                portfolio_independence_score REAL,
                remaining_upside REAL,

                data_completeness_score REAL,
                data_confidence TEXT,
                source_coverage_score REAL,
                source_count INTEGER,

                total_penalty REAL,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_master_history_key_time
            ON master_opportunity_history(
                opportunity_key,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS master_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,

                master_score REAL,
                master_grade TEXT,
                recommendation TEXT,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                message TEXT NOT NULL,
                details_json TEXT,

                created_at TEXT NOT NULL,

                UNIQUE(
                    opportunity_key,
                    alert_type,
                    created_at
                )
            );

            CREATE INDEX IF NOT EXISTS
            idx_master_alerts_created
            ON master_alerts(
                created_at DESC
            );

            CREATE TABLE IF NOT EXISTS master_opportunity_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                source_rows_seen INTEGER
                    NOT NULL DEFAULT 0,

                master_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_created INTEGER
                    NOT NULL DEFAULT 0,

                alerts_created INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# SOURCE LOADING
# =============================================================================


def load_rows_by_key(
    table_name: str,
    key_column: str,
) -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        if not table_exists(connection, table_name):
            return {}

        rows = connection.execute(
            f'SELECT * FROM "{table_name}"'
        ).fetchall()

        output: dict[str, dict[str, Any]] = {}

        for row in rows:
            key = clean_text(row[key_column])

            if key:
                output[key] = dict(row)

        return output

    finally:
        connection.close()


def load_rows_by_market_id(
    table_name: str,
) -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        if not table_exists(connection, table_name):
            return {}

        rows = connection.execute(
            f'SELECT * FROM "{table_name}"'
        ).fetchall()

        output: dict[str, dict[str, Any]] = {}

        for row in rows:
            market_id = clean_text(row["market_id"]).lower()

            if market_id:
                output[market_id] = dict(row)

        return output

    finally:
        connection.close()


# =============================================================================
# COMPONENT SCORING
# =============================================================================


def score_closing_line(
    closing: dict[str, Any] | None,
) -> float:
    if not closing:
        return 50.0

    clv_score = safe_float(
        closing.get("clv_score"),
        50.0,
    )

    edge_score = safe_float(
        closing.get("edge_remaining_score"),
        50.0,
    )

    chase_risk = safe_float(
        closing.get("chase_risk_score"),
        50.0,
    )

    return clamp(
        clv_score * 0.35
        + edge_score * 0.45
        + (100.0 - chase_risk) * 0.20
    )


def score_price_action(
    price: dict[str, Any] | None,
) -> float:
    if not price:
        return 50.0

    steam = safe_float(
        price.get("steam_score"),
        0.0,
    )

    reversal = safe_float(
        price.get("reversal_score"),
        0.0,
    )

    volatility = safe_float(
        price.get("volatility_score"),
        0.0,
    )

    move_status = normalize_text(
        price.get("move_status")
    )

    base = 50.0

    base += steam * 0.35
    base -= reversal * 0.45

    if move_status == "strong_steam":
        base += 12.0

    elif move_status == "steam":
        base += 7.0

    elif move_status == "stable":
        base += 2.0

    elif move_status in {
        "strong_reversal",
        "sharp_decline",
    }:
        base -= 15.0

    elif move_status in {
        "reversal_watch",
        "bearish",
    }:
        base -= 8.0

    if volatility >= 80:
        base -= 8.0

    elif volatility >= 60:
        base -= 4.0

    return clamp(base)


def score_wallet_quality(
    opportunity: dict[str, Any],
    institutional: dict[str, Any] | None,
) -> float:
    values = [
        safe_float(
            opportunity.get("weighted_wallet_quality"),
            safe_float(
                opportunity.get("average_wallet_quality"),
                0.0,
            ),
        ),
    ]

    if institutional:
        values.append(
            safe_float(
                institutional.get("weighted_wallet_quality"),
                0.0,
            )
        )

    values = [
        value
        for value in values
        if value > 0
    ]

    if not values:
        return 50.0

    return clamp(
        sum(values) / len(values)
    )


def score_timing(
    lifecycle_status: str,
    seconds_to_start: int | None,
) -> float:
    lifecycle = normalize_text(lifecycle_status)

    if lifecycle in INACTIVE_STATUSES:
        return 0.0

    if lifecycle in LIVE_STATUSES:
        return 20.0

    if seconds_to_start is None:
        return 48.0

    minutes = seconds_to_start / 60.0

    if minutes <= 0:
        return 20.0

    if minutes <= 5:
        return 35.0

    if minutes <= 15:
        return 60.0

    if minutes <= 60:
        return 100.0

    if minutes <= 180:
        return 95.0

    if minutes <= 360:
        return 88.0

    if minutes <= 720:
        return 80.0

    if minutes <= 1_440:
        return 72.0

    if minutes <= 4_320:
        return 62.0

    return 52.0


# =============================================================================
# GRADING AND RECOMMENDATIONS
# =============================================================================


def grade_from_score(score: float) -> tuple[str, str]:
    if score >= 90:
        return "S+", "ELITE"

    if score >= 82:
        return "S", "HIGH CONVICTION"

    if score >= 74:
        return "A+", "STRONG"

    if score >= 66:
        return "A", "QUALIFIED"

    if score >= 58:
        return "B", "WATCH"

    if score >= 48:
        return "C", "DEVELOPING"

    return "PASS", "PASS"


def determine_recommendation(
    score: float,
    lifecycle_status: str,
    seconds_to_start: int | None,
    chase_risk_score: float | None,
    reversal_score: float | None,
    conflict_ratio: float,
    remaining_upside: float,
    is_market_leader: int,
    source_count: int,
    data_confidence: str,
) -> str:
    lifecycle = normalize_text(lifecycle_status)

    if lifecycle in INACTIVE_STATUSES:
        return "PASS - MARKET INACTIVE"

    if lifecycle in LIVE_STATUSES:
        return "LIVE REVIEW REQUIRED"

    if is_market_leader == 0:
        return "PASS - OPPOSING SIDE LEADS"

    if seconds_to_start is not None and seconds_to_start <= 300:
        return "PASS - TOO CLOSE TO START"

    if reversal_score is not None and reversal_score >= 60:
        return "PASS - ACTIVE REVERSAL"

    if chase_risk_score is not None and chase_risk_score >= 75:
        return "DO NOT CHASE"

    if conflict_ratio >= 0.45:
        return "PASS - SMART MONEY CONFLICT"

    if remaining_upside <= 0.02:
        return "PASS - MINIMAL UPSIDE"

    if source_count < 3:
        return "WATCH - DATA INCOMPLETE"

    if data_confidence in {
        "LOW",
        "VERY LOW",
    }:
        return "WATCH - DATA INCOMPLETE"

    if score >= 90:
        return "BUY ZONE - ELITE RESEARCH PRIORITY"

    if score >= 82:
        return "HIGH-PRIORITY ENTRY REVIEW"

    if score >= 74:
        return "QUALIFIED ENTRY REVIEW"

    if score >= 66:
        return "MONITOR FOR CONFIRMATION"

    if score >= 58:
        return "WATCHLIST"

    return "PASS"


# =============================================================================
# MASTER BUILD
# =============================================================================


def build_master_records() -> list[dict[str, Any]]:
    opportunity_rows = load_rows_by_key(
        "opportunity_scores",
        "opportunity_key",
    )

    institutional_rows = load_rows_by_key(
        "institutional_consensus",
        "consensus_key",
    )

    evolution_rows = load_rows_by_key(
        "position_evolution",
        "evolution_key",
    )

    closing_rows = load_rows_by_key(
        "closing_line_metrics",
        "opportunity_key",
    )

    price_rows = load_rows_by_market_id(
        "market_price_metrics"
    )

    metadata_rows = load_rows_by_market_id(
        "market_metadata"
    )

    calculated_at = utc_now_iso()

    records: list[dict[str, Any]] = []

    for opportunity_key, opportunity in opportunity_rows.items():
        market_id = clean_text(
            opportunity.get("market_id")
        ).lower()

        institutional = institutional_rows.get(
            opportunity_key
        )

        evolution = evolution_rows.get(
            opportunity_key
        )

        closing = closing_rows.get(
            opportunity_key
        )

        price = price_rows.get(
            market_id
        )

        metadata = metadata_rows.get(
            market_id
        )

        source_count = sum(
            source is not None
            for source in (
                opportunity,
                institutional,
                evolution,
                closing,
                price,
                metadata,
            )
        )

        opportunity_score = safe_float(
            opportunity.get("opportunity_score"),
            0.0,
        )

        institutional_score = safe_float(
            (
                institutional.get("consensus_strength")
                if institutional
                else 50.0
            ),
            50.0,
        )

        evolution_score = safe_float(
            (
                evolution.get("evolution_score")
                if evolution
                else 50.0
            ),
            50.0,
        )

        closing_line_score = score_closing_line(
            closing
        )

        price_action_score = score_price_action(
            price
        )

        wallet_quality_score = score_wallet_quality(
            opportunity,
            institutional,
        )

        lifecycle_status = clean_text(
            (
                metadata.get("lifecycle_status")
                if metadata
                else opportunity.get("lifecycle_status")
            )
        ) or "UNKNOWN"

        seconds_value = (
            metadata.get("seconds_to_start")
            if metadata
            else opportunity.get("seconds_to_start")
        )

        seconds_to_start = (
            safe_int(seconds_value)
            if seconds_value is not None
            else None
        )

        timing_score = score_timing(
            lifecycle_status,
            seconds_to_start,
        )

        weighted_base_score = (
            opportunity_score
            * MASTER_WEIGHTS["opportunity"]
            + institutional_score
            * MASTER_WEIGHTS["institutional"]
            + evolution_score
            * MASTER_WEIGHTS["evolution"]
            + closing_line_score
            * MASTER_WEIGHTS["closing_line"]
            + price_action_score
            * MASTER_WEIGHTS["price_action"]
            + wallet_quality_score
            * MASTER_WEIGHTS["wallet_quality"]
            + timing_score
            * MASTER_WEIGHTS["timing"]
        )

        wallet_count = safe_int(
            opportunity.get("wallet_count"),
            safe_int(
                (
                    institutional.get("wallet_count")
                    if institutional
                    else 0
                )
            ),
        )

        elite_wallet_count = safe_int(
            opportunity.get("elite_wallet_count"),
            safe_int(
                (
                    institutional.get("elite_wallet_count")
                    if institutional
                    else 0
                )
            ),
        )

        effective_wallet_count = safe_float(
            opportunity.get("effective_wallet_count"),
            safe_float(
                (
                    institutional.get("effective_wallet_count")
                    if institutional
                    else 0.0
                )
            ),
        )

        combined_current_value = safe_float(
            opportunity.get("combined_current_value"),
            safe_float(
                (
                    institutional.get("total_current_value")
                    if institutional
                    else 0.0
                )
            ),
        )

        consensus_strength = safe_float(
            (
                institutional.get("consensus_strength")
                if institutional
                else 0.0
            )
        )

        strengthening_score = safe_float(
            (
                evolution.get("strengthening_score")
                if evolution
                else 50.0
            ),
            50.0,
        )

        weakening_score = safe_float(
            (
                evolution.get("weakening_score")
                if evolution
                else 0.0
            ),
            0.0,
        )

        net_value_change = safe_float(
            (
                evolution.get("net_value_change")
                if evolution
                else 0.0
            )
        )

        elite_wallet_count_change = safe_int(
            (
                evolution.get("elite_wallet_count_change")
                if evolution
                else 0
            )
        )

        clv_score = (
            safe_float(closing.get("clv_score"))
            if closing
            and closing.get("clv_score") is not None
            else None
        )

        edge_remaining_score = (
            safe_float(
                closing.get("edge_remaining_score")
            )
            if closing
            and closing.get("edge_remaining_score") is not None
            else None
        )

        chase_risk_score = (
            safe_float(
                closing.get("chase_risk_score")
            )
            if closing
            and closing.get("chase_risk_score") is not None
            else None
        )

        steam_score = (
            safe_float(price.get("steam_score"))
            if price
            else None
        )

        reversal_score = (
            safe_float(price.get("reversal_score"))
            if price
            else None
        )

        volatility_score = (
            safe_float(price.get("volatility_score"))
            if price
            else None
        )

        conflict_ratio = max(
            safe_float(
                opportunity.get("conflict_ratio"),
                0.0,
            ),
            safe_float(
                (
                    institutional.get("conflict_ratio")
                    if institutional
                    else 0.0
                ),
                0.0,
            ),
        )

        portfolio_independence_score = safe_float(
            opportunity.get("portfolio_independence_score"),
            safe_float(
                (
                    institutional.get(
                        "portfolio_independence_score"
                    )
                    if institutional
                    else 0.0
                )
            ),
        )

        remaining_upside = safe_float(
            opportunity.get("remaining_upside"),
            (
                safe_float(
                    closing.get("gross_edge_remaining")
                )
                if closing
                else 0.0
            ),
        )

        is_market_leader = safe_int(
            opportunity.get("is_market_leader"),
            1,
        )

        data_scores: list[float] = []

        for source in (
            opportunity,
            institutional,
            evolution,
            closing,
        ):
            if source is None:
                continue

            value = source.get(
                "data_completeness_score"
            )

            if value is not None:
                data_scores.append(
                    safe_float(value)
                )

        data_completeness_score = (
            sum(data_scores)
            / len(data_scores)
            if data_scores
            else 0.0
        )

        source_coverage_score = (
            source_count / 6.0 * 100.0
        )

        combined_completeness = clamp(
            data_completeness_score * 0.65
            + source_coverage_score * 0.35
        )

        if combined_completeness >= 85:
            data_confidence = "VERY HIGH"

        elif combined_completeness >= 70:
            data_confidence = "HIGH"

        elif combined_completeness >= 55:
            data_confidence = "MEDIUM"

        elif combined_completeness >= 40:
            data_confidence = "LOW"

        else:
            data_confidence = "VERY LOW"

        live_penalty = (
            35.0
            if normalize_text(lifecycle_status)
            in LIVE_STATUSES
            else 0.0
        )

        inactive_penalty = (
            100.0
            if normalize_text(lifecycle_status)
            in INACTIVE_STATUSES
            else 0.0
        )

        single_wallet_penalty = 0.0

        if wallet_count <= 1:
            single_wallet_penalty = 10.0

        elif effective_wallet_count < 1.5:
            single_wallet_penalty = 6.0

        if elite_wallet_count <= 1:
            single_wallet_penalty += 3.0

        weak_consensus_penalty = 0.0

        if consensus_strength < 50:
            weak_consensus_penalty = 10.0

        elif consensus_strength < 60:
            weak_consensus_penalty = 5.0

        chase_penalty = 0.0

        if chase_risk_score is not None:
            chase_penalty = clamp(
                max(
                    chase_risk_score - 45.0,
                    0.0,
                )
                / 55.0
                * 18.0,
                0.0,
                18.0,
            )

        conflict_penalty = clamp(
            conflict_ratio * 24.0,
            0.0,
            24.0,
        )

        reversal_penalty = 0.0

        if reversal_score is not None:
            reversal_penalty = clamp(
                reversal_score
                / 100.0
                * 20.0,
                0.0,
                20.0,
            )

        low_upside_penalty = 0.0

        if closing is not None:
            if remaining_upside <= 0.02:
                low_upside_penalty = 20.0

            elif remaining_upside <= 0.05:
                low_upside_penalty = 12.0

            elif remaining_upside <= 0.10:
                low_upside_penalty = 6.0

        weakening_penalty = clamp(
            max(
                weakening_score - 30.0,
                0.0,
            )
            / 70.0
            * 18.0,
            0.0,
            18.0,
        )

        incomplete_data_penalty = (
            max(
                0.0,
                65.0 - combined_completeness,
            )
            / 65.0
            * 12.0
        )

        total_penalty = (
            live_penalty
            + inactive_penalty
            + single_wallet_penalty
            + weak_consensus_penalty
            + chase_penalty
            + conflict_penalty
            + reversal_penalty
            + low_upside_penalty
            + weakening_penalty
            + incomplete_data_penalty
        )

        master_score = clamp(
            weighted_base_score
            - total_penalty
        )

        grade, tier = grade_from_score(
            master_score
        )

        if (
            wallet_count <= 1
            or elite_wallet_count <= 1
            or effective_wallet_count < 1.5
        ) and grade in {"S+", "S"}:
            grade = "A+"
            tier = "STRONG"

            master_score = min(
                master_score,
                79.9,
            )

        if normalize_text(lifecycle_status) in LIVE_STATUSES:
            grade = "PASS"
            tier = "LIVE"

        if normalize_text(lifecycle_status) in INACTIVE_STATUSES:
            grade = "PASS"
            tier = "INACTIVE"
            master_score = 0.0

        recommendation = determine_recommendation(
            score=master_score,
            lifecycle_status=lifecycle_status,
            seconds_to_start=seconds_to_start,
            chase_risk_score=chase_risk_score,
            reversal_score=reversal_score,
            conflict_ratio=conflict_ratio,
            remaining_upside=remaining_upside,
            is_market_leader=is_market_leader,
            source_count=source_count,
            data_confidence=data_confidence,
        )

        reasons: list[str] = []
        risk_flags: list[str] = []

        if institutional_score >= 74:
            reasons.append(
                "Strong institutional consensus"
            )

        if strengthening_score >= 70:
            reasons.append(
                "Position evolution is strengthening"
            )

        if net_value_change > 0:
            reasons.append(
                "Net smart-money capital inflow"
            )

        if elite_wallet_count_change > 0:
            reasons.append(
                "Elite wallet participation increased"
            )

        if edge_remaining_score is not None and edge_remaining_score >= 70:
            reasons.append(
                "Strong remaining edge location"
            )

        if clv_score is not None and clv_score >= 65:
            reasons.append(
                "Positive reconstructed CLV"
            )

        if steam_score is not None and steam_score >= 50:
            reasons.append(
                "Price steam detected"
            )

        if portfolio_independence_score >= 70:
            reasons.append(
                "Consensus is relatively independent"
            )

        if conflict_ratio >= 0.30:
            risk_flags.append(
                "Meaningful opposing smart money"
            )

        if chase_risk_score is not None and chase_risk_score >= 55:
            risk_flags.append(
                "Late-entry or chase risk"
            )

        if reversal_score is not None and reversal_score >= 35:
            risk_flags.append(
                "Reversal risk"
            )

        if weakening_score >= 55:
            risk_flags.append(
                "Position evolution is weakening"
            )

        if wallet_count <= 1:
            risk_flags.append(
                "Single-wallet signal"
            )

        if source_count < 4:
            risk_flags.append(
                "Limited source coverage"
            )

        explanation = {
            "model_version": "3.0",
            "weights": MASTER_WEIGHTS,
            "components": {
                "opportunity": round(
                    opportunity_score,
                    2,
                ),
                "institutional": round(
                    institutional_score,
                    2,
                ),
                "evolution": round(
                    evolution_score,
                    2,
                ),
                "closing_line": round(
                    closing_line_score,
                    2,
                ),
                "price_action": round(
                    price_action_score,
                    2,
                ),
                "wallet_quality": round(
                    wallet_quality_score,
                    2,
                ),
                "timing": round(
                    timing_score,
                    2,
                ),
            },
            "penalties": {
                "live": round(
                    live_penalty,
                    2,
                ),
                "inactive": round(
                    inactive_penalty,
                    2,
                ),
                "single_wallet": round(
                    single_wallet_penalty,
                    2,
                ),
                "weak_consensus": round(
                    weak_consensus_penalty,
                    2,
                ),
                "chase": round(
                    chase_penalty,
                    2,
                ),
                "conflict": round(
                    conflict_penalty,
                    2,
                ),
                "reversal": round(
                    reversal_penalty,
                    2,
                ),
                "low_upside": round(
                    low_upside_penalty,
                    2,
                ),
                "weakening": round(
                    weakening_penalty,
                    2,
                ),
                "incomplete_data": round(
                    incomplete_data_penalty,
                    2,
                ),
            },
            "notes": [
                (
                    "The master score is a research ranking, "
                    "not a calibrated probability."
                ),
                (
                    "Live and inactive markets are blocked "
                    "from actionable grades."
                ),
                (
                    "Single-wallet signals cannot receive "
                    "S or S+ grades."
                ),
            ],
        }

        records.append(
            {
                "opportunity_key": opportunity_key,
                "market_id": market_id,
                "title": clean_text(
                    opportunity.get("title")
                ),
                "outcome": clean_text(
                    opportunity.get("outcome")
                ),
                "market_type": clean_text(
                    opportunity.get("market_type")
                ),

                "master_score": round(
                    master_score,
                    1,
                ),
                "master_grade": grade,
                "master_tier": tier,
                "recommendation": recommendation,

                "lifecycle_status": lifecycle_status,
                "seconds_to_start": seconds_to_start,

                "opportunity_score": opportunity_score,
                "institutional_score": institutional_score,
                "evolution_score": evolution_score,
                "closing_line_score": closing_line_score,
                "price_action_score": price_action_score,
                "wallet_quality_score": wallet_quality_score,
                "timing_score": timing_score,

                "opportunity_grade": clean_text(
                    opportunity.get(
                        "opportunity_grade"
                    )
                ),

                "institutional_grade": clean_text(
                    (
                        institutional.get(
                            "confidence_grade"
                        )
                        if institutional
                        else ""
                    )
                ),

                "evolution_grade": clean_text(
                    (
                        evolution.get(
                            "evolution_grade"
                        )
                        if evolution
                        else ""
                    )
                ),

                "institutional_status": clean_text(
                    (
                        institutional.get(
                            "signal_status"
                        )
                        if institutional
                        else ""
                    )
                ),

                "evolution_status": clean_text(
                    (
                        evolution.get(
                            "evolution_status"
                        )
                        if evolution
                        else ""
                    )
                ),

                "closing_recommendation": clean_text(
                    (
                        closing.get(
                            "recommendation"
                        )
                        if closing
                        else ""
                    )
                ),

                "movement_status": clean_text(
                    (
                        price.get(
                            "move_status"
                        )
                        if price
                        else ""
                    )
                ),

                "wallet_count": wallet_count,
                "elite_wallet_count": elite_wallet_count,
                "effective_wallet_count": effective_wallet_count,

                "combined_current_value": combined_current_value,
                "weighted_wallet_quality": wallet_quality_score,
                "consensus_strength": consensus_strength,

                "strengthening_score": strengthening_score,
                "weakening_score": weakening_score,
                "net_value_change": net_value_change,
                "elite_wallet_count_change": elite_wallet_count_change,

                "clv_score": clv_score,
                "edge_remaining_score": edge_remaining_score,
                "chase_risk_score": chase_risk_score,

                "steam_score": steam_score,
                "reversal_score": reversal_score,
                "volatility_score": volatility_score,

                "conflict_ratio": conflict_ratio,
                "portfolio_independence_score": (
                    portfolio_independence_score
                ),

                "remaining_upside": remaining_upside,
                "is_market_leader": is_market_leader,

                "data_completeness_score": (
                    combined_completeness
                ),

                "data_confidence": data_confidence,

                "source_coverage_score": source_coverage_score,
                "source_count": source_count,

                "live_penalty": live_penalty,
                "inactive_penalty": inactive_penalty,
                "single_wallet_penalty": single_wallet_penalty,
                "weak_consensus_penalty": weak_consensus_penalty,
                "chase_penalty": chase_penalty,
                "conflict_penalty": conflict_penalty,
                "reversal_penalty": reversal_penalty,
                "low_upside_penalty": low_upside_penalty,
                "weakening_penalty": weakening_penalty,
                "incomplete_data_penalty": incomplete_data_penalty,
                "total_penalty": total_penalty,

                "reasons_json": json.dumps(
                    reasons,
                    ensure_ascii=False,
                ),

                "risk_flags_json": json.dumps(
                    risk_flags,
                    ensure_ascii=False,
                ),

                "explanation_json": json.dumps(
                    explanation,
                    ensure_ascii=False,
                ),

                "calculated_at": calculated_at,
                "updated_at": calculated_at,
            }
        )

    records.sort(
        key=lambda item: (
            item["master_score"],
            item["master_grade"],
            item["data_completeness_score"],
            item["effective_wallet_count"],
            item["combined_current_value"],
        ),
        reverse=True,
    )

    return records


# =============================================================================
# SAVING
# =============================================================================


CURRENT_COLUMNS = [
    "opportunity_key",
    "market_id",
    "title",
    "outcome",
    "market_type",
    "master_score",
    "master_grade",
    "master_tier",
    "recommendation",
    "lifecycle_status",
    "seconds_to_start",
    "opportunity_score",
    "institutional_score",
    "evolution_score",
    "closing_line_score",
    "price_action_score",
    "wallet_quality_score",
    "timing_score",
    "opportunity_grade",
    "institutional_grade",
    "evolution_grade",
    "institutional_status",
    "evolution_status",
    "closing_recommendation",
    "movement_status",
    "wallet_count",
    "elite_wallet_count",
    "effective_wallet_count",
    "combined_current_value",
    "weighted_wallet_quality",
    "consensus_strength",
    "strengthening_score",
    "weakening_score",
    "net_value_change",
    "elite_wallet_count_change",
    "clv_score",
    "edge_remaining_score",
    "chase_risk_score",
    "steam_score",
    "reversal_score",
    "volatility_score",
    "conflict_ratio",
    "portfolio_independence_score",
    "remaining_upside",
    "is_market_leader",
    "data_completeness_score",
    "data_confidence",
    "source_coverage_score",
    "source_count",
    "live_penalty",
    "inactive_penalty",
    "single_wallet_penalty",
    "weak_consensus_penalty",
    "chase_penalty",
    "conflict_penalty",
    "reversal_penalty",
    "low_upside_penalty",
    "weakening_penalty",
    "incomplete_data_penalty",
    "total_penalty",
    "reasons_json",
    "risk_flags_json",
    "explanation_json",
    "calculated_at",
    "updated_at",
]


HISTORY_COLUMNS = [
    "opportunity_key",
    "market_id",
    "title",
    "outcome",
    "master_score",
    "master_grade",
    "master_tier",
    "recommendation",
    "lifecycle_status",
    "seconds_to_start",
    "opportunity_score",
    "institutional_score",
    "evolution_score",
    "closing_line_score",
    "price_action_score",
    "wallet_quality_score",
    "timing_score",
    "wallet_count",
    "elite_wallet_count",
    "effective_wallet_count",
    "combined_current_value",
    "consensus_strength",
    "strengthening_score",
    "weakening_score",
    "net_value_change",
    "clv_score",
    "edge_remaining_score",
    "chase_risk_score",
    "steam_score",
    "reversal_score",
    "volatility_score",
    "conflict_ratio",
    "portfolio_independence_score",
    "remaining_upside",
    "data_completeness_score",
    "data_confidence",
    "source_coverage_score",
    "source_count",
    "total_penalty",
    "observed_at",
]


def save_master_records(
    records: list[dict[str, Any]],
) -> tuple[int, int]:
    connection = connect_database()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        active_keys = [
            record["opportunity_key"]
            for record in records
        ]

        if active_keys:
            placeholders = ", ".join(
                "?"
                for _ in active_keys
            )

            connection.execute(
                f"""
                DELETE FROM master_opportunities
                WHERE opportunity_key
                NOT IN ({placeholders})
                """,
                active_keys,
            )

        else:
            connection.execute(
                "DELETE FROM master_opportunities"
            )

        current_names = ", ".join(
            f'"{column}"'
            for column in CURRENT_COLUMNS
        )

        current_placeholders = ", ".join(
            "?"
            for _ in CURRENT_COLUMNS
        )

        current_updates = ", ".join(
            f'"{column}" = excluded."{column}"'
            for column in CURRENT_COLUMNS
            if column != "opportunity_key"
        )

        current_query = f"""
            INSERT INTO master_opportunities (
                {current_names}
            )
            VALUES (
                {current_placeholders}
            )
            ON CONFLICT(opportunity_key)
            DO UPDATE SET
                {current_updates}
        """

        history_names = ", ".join(
            f'"{column}"'
            for column in HISTORY_COLUMNS
        )

        history_placeholders = ", ".join(
            "?"
            for _ in HISTORY_COLUMNS
        )

        history_query = f"""
            INSERT INTO master_opportunity_history (
                {history_names}
            )
            VALUES (
                {history_placeholders}
            )
        """

        observed_at = utc_now_iso()

        for record in records:
            connection.execute(
                current_query,
                tuple(
                    record[column]
                    for column in CURRENT_COLUMNS
                ),
            )

            history_payload = dict(record)
            history_payload["observed_at"] = observed_at

            connection.execute(
                history_query,
                tuple(
                    history_payload[column]
                    for column in HISTORY_COLUMNS
                ),
            )

        connection.commit()

        return len(records), len(records)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def create_master_alerts(
    records: list[dict[str, Any]],
) -> int:
    connection = connect_database()
    alerts_created = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        created_at = utc_now_iso()

        for record in records:
            recommendation = record["recommendation"]

            alert_type = ""
            severity = ""

            if recommendation.startswith(
                "BUY ZONE"
            ):
                alert_type = "BUY_ZONE"
                severity = "HIGH"

            elif recommendation.startswith(
                "HIGH-PRIORITY"
            ):
                alert_type = "HIGH_PRIORITY"
                severity = "MEDIUM"

            elif recommendation.startswith(
                "DO NOT CHASE"
            ):
                alert_type = "CHASE_RISK"
                severity = "MEDIUM"

            elif recommendation.startswith(
                "PASS - ACTIVE REVERSAL"
            ):
                alert_type = "REVERSAL"
                severity = "HIGH"

            else:
                continue

            message = (
                f"{record['title']} — "
                f"{record['outcome']} | "
                f"{recommendation} | "
                f"Master score "
                f"{record['master_score']:.1f}"
            )

            details = {
                "master_grade": (
                    record["master_grade"]
                ),
                "data_confidence": (
                    record["data_confidence"]
                ),
                "reasons": json.loads(
                    record["reasons_json"]
                ),
                "risk_flags": json.loads(
                    record["risk_flags_json"]
                ),
            }

            connection.execute(
                """
                INSERT OR IGNORE INTO master_alerts (
                    opportunity_key,
                    market_id,
                    title,
                    outcome,
                    alert_type,
                    severity,
                    master_score,
                    master_grade,
                    recommendation,
                    lifecycle_status,
                    seconds_to_start,
                    message,
                    details_json,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    record["opportunity_key"],
                    record["market_id"],
                    record["title"],
                    record["outcome"],
                    alert_type,
                    severity,
                    record["master_score"],
                    record["master_grade"],
                    record["recommendation"],
                    record["lifecycle_status"],
                    record["seconds_to_start"],
                    message,
                    json.dumps(
                        details,
                        ensure_ascii=False,
                    ),
                    created_at,
                ),
            )

            alerts_created += 1

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return alerts_created


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run() -> tuple[int, datetime]:
    started = utc_now()

    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO master_opportunity_runs (
                started_at,
                status
            )
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
    started_at: datetime,
    status: str,
    source_rows_seen: int,
    master_rows_saved: int,
    history_rows_created: int,
    alerts_created: int,
    error_message: str = "",
) -> None:
    finished = utc_now()

    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE master_opportunity_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                source_rows_seen = ?,
                master_rows_saved = ?,
                history_rows_created = ?,
                alerts_created = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                finished.isoformat(),
                (
                    finished
                    - started_at
                ).total_seconds(),
                source_rows_seen,
                master_rows_saved,
                history_rows_created,
                alerts_created,
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


def display_readiness() -> None:
    connection = connect_database()

    try:
        print()
        print("=" * 108)
        print("MASTER OPPORTUNITY DATA READINESS")
        print("=" * 108)

        for table_name in (
            "opportunity_scores",
            "institutional_consensus",
            "position_evolution",
            "closing_line_metrics",
            "market_price_metrics",
            "market_metadata",
            "master_opportunities",
            "master_opportunity_history",
            "master_alerts",
            "master_opportunity_runs",
        ):
            if table_exists(
                connection,
                table_name,
            ):
                print(
                    f"{table_name:<42}"
                    f"{table_row_count(connection, table_name):>12} rows"
                )

            else:
                print(
                    f"{table_name:<42}"
                    f"{'NOT FOUND':>12}"
                )

        print("=" * 108)

    finally:
        connection.close()


def display_summary(
    records: list[dict[str, Any]],
    current_saved: int,
    history_saved: int,
    alerts_created: int,
) -> None:
    grade_counts: dict[str, int] = defaultdict(int)
    recommendation_counts: dict[str, int] = defaultdict(int)

    for record in records:
        grade_counts[
            record["master_grade"]
        ] += 1

        recommendation_counts[
            record["recommendation"]
        ] += 1

    print()
    print("=" * 108)
    print("MASTER OPPORTUNITY SUMMARY")
    print("=" * 108)

    print(
        f"Master records calculated:      "
        f"{len(records)}"
    )

    print(
        f"Current rows saved:             "
        f"{current_saved}"
    )

    print(
        f"History rows created:           "
        f"{history_saved}"
    )

    print(
        f"Alerts created:                 "
        f"{alerts_created}"
    )

    print(
        f"S+ opportunities:              "
        f"{grade_counts['S+']}"
    )

    print(
        f"S or better:                   "
        f"{grade_counts['S+'] + grade_counts['S']}"
    )

    print(
        f"A or better:                   "
        f"{sum(grade_counts[g] for g in ('S+', 'S', 'A+', 'A'))}"
    )

    print()
    print("TOP RECOMMENDATION COUNTS")

    for label, total in sorted(
        recommendation_counts.items(),
        key=lambda item: (
            item[1],
            item[0],
        ),
        reverse=True,
    )[:12]:
        print(
            f"{label:<48}"
            f"{total:>8}"
        )

    print("=" * 108)


def display_record(
    rank: int,
    record: dict[str, Any],
) -> None:
    reasons = json.loads(
        record["reasons_json"]
    )

    risks = json.loads(
        record["risk_flags_json"]
    )

    print()
    print("-" * 108)

    print(
        f"{rank}. "
        f"{record['title']}"
    )

    print("-" * 108)

    print(
        f"Outcome:                        "
        f"{record['outcome']}"
    )

    print(
        f"Master score:                   "
        f"{record['master_score']:.1f}/100"
    )

    print(
        f"Grade / tier:                   "
        f"{record['master_grade']} "
        f"/ {record['master_tier']}"
    )

    print(
        f"Recommendation:                 "
        f"{record['recommendation']}"
    )

    print(
        f"Data confidence:                "
        f"{record['data_confidence']} "
        f"({record['data_completeness_score']:.1f}/100)"
    )

    print(
        f"Source coverage:                "
        f"{record['source_count']}/6 "
        f"({record['source_coverage_score']:.1f}%)"
    )

    print()
    print("CORE COMPONENTS")

    print(
        f"Opportunity / Institutional:    "
        f"{record['opportunity_score']:.1f}"
        f" / "
        f"{record['institutional_score']:.1f}"
    )

    print(
        f"Evolution / Closing line:       "
        f"{record['evolution_score']:.1f}"
        f" / "
        f"{record['closing_line_score']:.1f}"
    )

    print(
        f"Price action / Wallet quality:  "
        f"{record['price_action_score']:.1f}"
        f" / "
        f"{record['wallet_quality_score']:.1f}"
    )

    print(
        f"Timing:                         "
        f"{record['timing_score']:.1f}"
    )

    print()
    print("SMART MONEY")

    print(
        f"Wallets / elite wallets:        "
        f"{record['wallet_count']} "
        f"/ {record['elite_wallet_count']}"
    )

    print(
        f"Effective wallets:              "
        f"{record['effective_wallet_count']:.2f}"
    )

    print(
        f"Consensus strength:             "
        f"{record['consensus_strength']:.1f}"
    )

    print(
        f"Strengthening / weakening:      "
        f"{record['strengthening_score']:.1f}"
        f" / "
        f"{record['weakening_score']:.1f}"
    )

    print(
        f"Net capital change:             "
        f"{format_money(record['net_value_change'])}"
    )

    print()
    print("ENTRY AND MARKET RISK")

    print(
        f"CLV / edge / chase:             "
        f"{record['clv_score'] if record['clv_score'] is not None else 'N/A'}"
        f" / "
        f"{record['edge_remaining_score'] if record['edge_remaining_score'] is not None else 'N/A'}"
        f" / "
        f"{record['chase_risk_score'] if record['chase_risk_score'] is not None else 'N/A'}"
    )

    print(
        f"Steam / reversal / volatility:  "
        f"{record['steam_score'] if record['steam_score'] is not None else 'N/A'}"
        f" / "
        f"{record['reversal_score'] if record['reversal_score'] is not None else 'N/A'}"
        f" / "
        f"{record['volatility_score'] if record['volatility_score'] is not None else 'N/A'}"
    )

    print(
        f"Conflict ratio:                 "
        f"{format_percentage(record['conflict_ratio'])}"
    )

    print(
        f"Total penalty:                  "
        f"-{record['total_penalty']:.1f}"
    )

    print(
        f"Lifecycle / T-minus:            "
        f"{record['lifecycle_status']} "
        f"/ {format_t_minus(record['seconds_to_start'])}"
    )

    if reasons:
        print()
        print("WHY IT RANKED")

        for reason in reasons:
            print(
                f"  + {reason}"
            )

    if risks:
        print()
        print("RISK FLAGS")

        for risk in risks:
            print(
                f"  - {risk}"
            )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine opportunity, institutional consensus, "
            "position evolution, closing-line, price and "
            "market-status intelligence into one master ranking."
        )
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    configure_utf8_output()

    arguments = parse_arguments()

    print()
    print("=" * 108)
    print("POLYMARKET MASTER OPPORTUNITY ENGINE v3")
    print("=" * 108)

    print(
        f"Database: {DATABASE_PATH}"
    )

    create_master_tables()

    display_readiness()

    run_id, started_at = start_run()

    records: list[dict[str, Any]] = []
    current_saved = 0
    history_saved = 0
    alerts_created = 0

    try:
        records = build_master_records()

        current_saved, history_saved = (
            save_master_records(records)
        )

        alerts_created = (
            create_master_alerts(records)
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            source_rows_seen=len(records),
            master_rows_saved=current_saved,
            history_rows_created=history_saved,
            alerts_created=alerts_created,
        )

        display_summary(
            records=records,
            current_saved=current_saved,
            history_saved=history_saved,
            alerts_created=alerts_created,
        )

        print()
        print("TOP MASTER OPPORTUNITIES")

        for rank, record in enumerate(
            records[
                : max(
                    arguments.display_limit,
                    1,
                )
            ],
            start=1,
        ):
            display_record(
                rank,
                record,
            )

        print()
        print("=" * 108)
        print("MASTER OPPORTUNITY ENGINE v3 COMPLETE")
        print("=" * 108)

        print(
            "Current master rankings were saved to "
            "master_opportunities."
        )

        print(
            "Historical snapshots were saved to "
            "master_opportunity_history."
        )

        print(
            "Actionable alerts were saved to "
            "master_alerts."
        )

        print(
            "Live and inactive markets cannot receive "
            "actionable master grades."
        )

        print(
            "Single-wallet signals cannot receive "
            "S or S+ grades."
        )

        print(
            "The master score is a research ranking, "
            "not a calibrated win probability."
        )

        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            source_rows_seen=len(records),
            master_rows_saved=current_saved,
            history_rows_created=history_saved,
            alerts_created=alerts_created,
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()