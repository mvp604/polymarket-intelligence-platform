from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 30

FUSION_WEIGHTS = {
    "master_opportunity": 0.24,
    "institutional_consensus": 0.18,
    "position_evolution": 0.14,
    "wallet_dna": 0.14,
    "wallet_performance": 0.10,
    "closing_line": 0.08,
    "price_action": 0.06,
    "mapping_quality": 0.03,
    "market_timing": 0.03,
}

INACTIVE_LIFECYCLES = {
    "resolved",
    "closed",
    "ended",
    "ended_unconfirmed",
    "inactive",
}

LIVE_LIFECYCLES = {
    "live",
    "started",
    "live_unconfirmed",
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


def safe_mean(
    values: list[float],
    default: float = 0.0,
) -> float:
    clean_values = [
        value
        for value in values
        if value is not None
    ]

    if not clean_values:
        return default

    return sum(clean_values) / len(clean_values)


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


def format_percentage(value: Any) -> str:
    return f"{safe_float(value):.1%}"


def normalize_ratio(value: Any) -> float:
    number = safe_float(value)

    if number > 1.0:
        number /= 100.0

    return max(0.0, min(number, 1.0))


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
        SELECT name
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


def create_signal_fusion_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS signal_fusion_scores (
                opportunity_key TEXT PRIMARY KEY,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                gamma_market_id TEXT,
                gamma_event_id TEXT,
                condition_id TEXT,

                fusion_score REAL
                    NOT NULL DEFAULT 0,

                fusion_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                confidence_tier TEXT
                    NOT NULL DEFAULT 'LOW',

                signal_strength TEXT
                    NOT NULL DEFAULT 'WEAK',

                recommendation TEXT
                    NOT NULL DEFAULT 'PASS',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                master_score REAL
                    NOT NULL DEFAULT 0,

                institutional_score REAL
                    NOT NULL DEFAULT 0,

                evolution_score REAL
                    NOT NULL DEFAULT 0,

                wallet_dna_score REAL
                    NOT NULL DEFAULT 0,

                wallet_performance_score REAL
                    NOT NULL DEFAULT 0,

                closing_line_score REAL
                    NOT NULL DEFAULT 0,

                price_action_score REAL
                    NOT NULL DEFAULT 0,

                mapping_quality_score REAL
                    NOT NULL DEFAULT 0,

                timing_score REAL
                    NOT NULL DEFAULT 0,

                agreeing_wallets INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallets INTEGER
                    NOT NULL DEFAULT 0,

                effective_wallets REAL
                    NOT NULL DEFAULT 0,

                combined_current_value REAL
                    NOT NULL DEFAULT 0,

                average_wallet_dna REAL
                    NOT NULL DEFAULT 0,

                average_wallet_performance REAL
                    NOT NULL DEFAULT 0,

                specialist_wallet_share REAL
                    NOT NULL DEFAULT 0,

                independent_wallet_share REAL
                    NOT NULL DEFAULT 0,

                conflict_ratio REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 0,

                strengthening_score REAL
                    NOT NULL DEFAULT 0,

                weakening_score REAL
                    NOT NULL DEFAULT 0,

                net_value_change REAL
                    NOT NULL DEFAULT 0,

                clv_score REAL,
                edge_remaining_score REAL,
                chase_risk_score REAL,

                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,

                mapping_status TEXT,
                match_method TEXT,
                match_confidence REAL,

                source_count INTEGER
                    NOT NULL DEFAULT 0,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                live_penalty REAL
                    NOT NULL DEFAULT 0,

                inactive_penalty REAL
                    NOT NULL DEFAULT 0,

                conflict_penalty REAL
                    NOT NULL DEFAULT 0,

                chase_penalty REAL
                    NOT NULL DEFAULT 0,

                reversal_penalty REAL
                    NOT NULL DEFAULT 0,

                weakening_penalty REAL
                    NOT NULL DEFAULT 0,

                low_sample_penalty REAL
                    NOT NULL DEFAULT 0,

                mapping_penalty REAL
                    NOT NULL DEFAULT 0,

                total_penalty REAL
                    NOT NULL DEFAULT 0,

                positive_signals_json TEXT,
                negative_signals_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_signal_fusion_scores_rank
            ON signal_fusion_scores(
                fusion_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_signal_fusion_scores_grade
            ON signal_fusion_scores(
                fusion_grade,
                fusion_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_signal_fusion_scores_recommendation
            ON signal_fusion_scores(
                recommendation,
                fusion_score DESC
            );

            CREATE TABLE IF NOT EXISTS signal_fusion_wallets (
                fusion_wallet_key TEXT PRIMARY KEY,

                opportunity_key TEXT NOT NULL,
                wallet TEXT NOT NULL,

                wallet_current_value REAL
                    NOT NULL DEFAULT 0,

                wallet_share_of_signal REAL
                    NOT NULL DEFAULT 0,

                dna_score REAL
                    NOT NULL DEFAULT 50,

                dna_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                primary_archetype TEXT,

                primary_category TEXT,
                primary_category_share REAL
                    NOT NULL DEFAULT 0,

                sports_specialty TEXT,
                market_type_specialty TEXT,

                performance_score REAL
                    NOT NULL DEFAULT 50,

                performance_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                estimated_roi REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 50,

                specialist_match INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet INTEGER
                    NOT NULL DEFAULT 0,

                contribution_score REAL
                    NOT NULL DEFAULT 0,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    opportunity_key
                )
                REFERENCES signal_fusion_scores(
                    opportunity_key
                )
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_signal_fusion_wallets_opportunity
            ON signal_fusion_wallets(
                opportunity_key,
                contribution_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_signal_fusion_wallets_wallet
            ON signal_fusion_wallets(
                wallet,
                opportunity_key
            );

            CREATE TABLE IF NOT EXISTS signal_fusion_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                fusion_score REAL,
                fusion_grade TEXT,
                confidence_tier TEXT,
                signal_strength TEXT,
                recommendation TEXT,

                agreeing_wallets INTEGER,
                elite_wallets INTEGER,
                combined_current_value REAL,

                master_score REAL,
                institutional_score REAL,
                evolution_score REAL,
                wallet_dna_score REAL,
                wallet_performance_score REAL,
                closing_line_score REAL,
                price_action_score REAL,
                mapping_quality_score REAL,
                timing_score REAL,

                total_penalty REAL,
                data_completeness_score REAL,
                data_confidence TEXT,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_signal_fusion_history_key
            ON signal_fusion_history(
                opportunity_key,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS signal_fusion_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,

                fusion_score REAL,
                fusion_grade TEXT,
                recommendation TEXT,

                message TEXT NOT NULL,
                details_json TEXT,

                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_signal_fusion_alerts_created
            ON signal_fusion_alerts(
                created_at DESC
            );

            CREATE TABLE IF NOT EXISTS signal_fusion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                opportunities_loaded INTEGER
                    NOT NULL DEFAULT 0,

                wallet_rows_loaded INTEGER
                    NOT NULL DEFAULT 0,

                fusion_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                fusion_wallet_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                alerts_saved INTEGER
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


def load_table_by_key(
    table_name: str,
    key_column: str,
) -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            table_name,
        ):
            return {}

        rows = connection.execute(
            f'SELECT * FROM "{table_name}"'
        ).fetchall()

        output: dict[
            str,
            dict[str, Any],
        ] = {}

        for row in rows:
            key = clean_text(
                row[key_column]
            )

            if key:
                output[key] = dict(row)

        return output

    finally:
        connection.close()


def load_wallet_dna() -> dict[
    str,
    dict[str, Any],
]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "wallet_dna_profiles",
        ):
            return {}

        rows = connection.execute(
            """
            SELECT *
            FROM wallet_dna_profiles
            """
        ).fetchall()

        return {
            clean_text(
                row["wallet"]
            ).lower(): dict(row)
            for row in rows
        }

    finally:
        connection.close()


def load_wallet_performance() -> dict[
    str,
    dict[str, Any],
]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "wallet_performance",
        ):
            return {}

        rows = connection.execute(
            """
            SELECT *
            FROM wallet_performance
            """
        ).fetchall()

        return {
            clean_text(
                row["wallet"]
            ).lower(): dict(row)
            for row in rows
        }

    finally:
        connection.close()


def load_latest_positions() -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        require_table(
            connection,
            "positions",
        )

        require_table(
            connection,
            "wallet_scans",
        )

        rows = connection.execute(
            """
            WITH latest_scans AS (
                SELECT
                    wallet,
                    MAX(id) AS scan_id
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT
                p.*,
                ws.scanned_at
            FROM latest_scans ls
            JOIN wallet_scans ws
              ON ws.id = ls.scan_id
            JOIN positions p
              ON p.scan_id = ls.scan_id
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


def load_market_mapping_lookup() -> dict[
    str,
    dict[str, Any],
]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "market_mappings",
        ):
            return {}

        rows = connection.execute(
            """
            SELECT *
            FROM market_mappings
            ORDER BY
                match_confidence DESC
            """
        ).fetchall()

    finally:
        connection.close()

    output: dict[
        str,
        dict[str, Any],
    ] = {}

    for row in rows:
        market_id = clean_text(
            row["source_market_id"]
        ).lower()

        if (
            market_id
            and market_id not in output
        ):
            output[
                market_id
            ] = dict(row)

    return output


# =============================================================================
# MATCHING AND AGGREGATION
# =============================================================================


def normalize_outcome(value: Any) -> str:
    normalized = normalize_text(value)

    aliases = {
        "y": "yes",
        "n": "no",
    }

    return aliases.get(
        normalized,
        normalized,
    )


def infer_signal_category(
    title: str,
) -> str:
    normalized = normalize_text(
        title
    )

    if any(
        keyword in normalized
        for keyword in (
            "world cup",
            "soccer",
            "football",
            "team to advance",
            "total corners",
            "btts",
            "tennis",
            "wimbledon",
            "atp",
            "wta",
            "mlb",
            "nba",
            "nfl",
            "ufc",
            "esports",
            " vs ",
        )
    ):
        return "SPORTS"

    if any(
        keyword in normalized
        for keyword in (
            "president",
            "election",
            "senate",
            "republican",
            "democratic",
            "prime minister",
            "congress",
            "governor",
        )
    ):
        return "POLITICS"

    if any(
        keyword in normalized
        for keyword in (
            "bitcoin",
            "ethereum",
            "crypto",
            "solana",
            "btc",
            "eth",
        )
    ):
        return "CRYPTO"

    return "OTHER"


def infer_signal_sport(
    title: str,
) -> str:
    normalized = normalize_text(
        title
    )

    if any(
        keyword in normalized
        for keyword in (
            "world cup",
            "soccer",
            "football",
            "team to advance",
            "total corners",
            "btts",
        )
    ):
        return "SOCCER"

    if any(
        keyword in normalized
        for keyword in (
            "tennis",
            "wimbledon",
            "atp",
            "wta",
        )
    ):
        return "TENNIS"

    if "mlb" in normalized:
        return "BASEBALL"

    if any(
        keyword in normalized
        for keyword in (
            "nba",
            "wnba",
        )
    ):
        return "BASKETBALL"

    if any(
        keyword in normalized
        for keyword in (
            "ufc",
            "mma",
        )
    ):
        return "MMA"

    if any(
        keyword in normalized
        for keyword in (
            "esports",
            "lol:",
            "dota",
            "valorant",
        )
    ):
        return "ESPORTS"

    return ""


def infer_signal_market_type(
    title: str,
) -> str:
    normalized = normalize_text(
        title
    )

    if "exact score" in normalized:
        return "EXACT SCORE"

    if "total corners" in normalized:
        return "CORNERS TOTAL"

    if "o/u" in normalized:
        return "TOTAL"

    if "both teams to score" in normalized:
        return "BTTS"

    if "spread:" in normalized:
        return "SPREAD"

    if "team to advance" in normalized:
        return "TO ADVANCE"

    if (
        normalized.startswith("will ")
        and " win " in normalized
    ):
        return "MONEYLINE / WINNER"

    if " vs " in normalized:
        return "MATCH WINNER"

    return "OTHER"


def build_position_groups(
    positions: list[dict[str, Any]],
) -> dict[
    tuple[str, str],
    list[dict[str, Any]],
]:
    grouped: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for position in positions:
        market_id = clean_text(
            position.get(
                "market_id"
            )
        ).lower()

        outcome = normalize_outcome(
            position.get(
                "outcome"
            )
        )

        if market_id:
            grouped[
                (
                    market_id,
                    outcome,
                )
            ].append(
                position
            )

    return grouped


# =============================================================================
# COMPONENT SCORING
# =============================================================================


def score_wallet_inputs(
    title: str,
    positions: list[dict[str, Any]],
    dna_lookup: dict[
        str,
        dict[str, Any],
    ],
    performance_lookup: dict[
        str,
        dict[str, Any],
    ],
) -> tuple[
    float,
    float,
    float,
    float,
    int,
    list[dict[str, Any]],
]:
    signal_category = (
        infer_signal_category(
            title
        )
    )

    signal_sport = (
        infer_signal_sport(
            title
        )
    )

    signal_market_type = (
        infer_signal_market_type(
            title
        )
    )

    total_value = sum(
        max(
            safe_float(
                position.get(
                    "current_value"
                )
            ),
            0.0,
        )
        for position in positions
    )

    weighted_dna = 0.0
    weighted_performance = 0.0
    specialist_value = 0.0
    independent_value = 0.0
    elite_wallets = 0

    wallet_rows: list[
        dict[str, Any]
    ] = []

    for position in positions:
        wallet = clean_text(
            position.get(
                "wallet"
            )
        ).lower()

        value = max(
            safe_float(
                position.get(
                    "current_value"
                )
            ),
            0.0,
        )

        weight = (
            value / total_value
            if total_value > 0
            else (
                1.0 / len(positions)
                if positions
                else 0.0
            )
        )

        dna = dna_lookup.get(
            wallet,
            {},
        )

        performance = (
            performance_lookup.get(
                wallet,
                {}
            )
        )

        dna_score = safe_float(
            dna.get(
                "dna_score"
            ),
            50.0,
        )

        performance_score = safe_float(
            performance.get(
                "performance_score"
            ),
            50.0,
        )

        independence_score = safe_float(
            dna.get(
                "portfolio_independence_score"
            ),
            50.0,
        )

        primary_category = clean_text(
            dna.get(
                "primary_category"
            )
        ).upper()

        sports_specialty = clean_text(
            dna.get(
                "sports_specialty"
            )
        ).upper()

        market_type_specialty = clean_text(
            dna.get(
                "market_type_specialty"
            )
        ).upper()

        specialist_match = int(
            (
                signal_category
                and primary_category
                == signal_category
            )
            and (
                not signal_sport
                or not sports_specialty
                or sports_specialty
                == signal_sport
            )
            and (
                not signal_market_type
                or not market_type_specialty
                or market_type_specialty
                == signal_market_type
            )
        )

        elite_wallet = int(
            dna_score >= 74.0
            and (
                performance_score
                >= 58.0
                or safe_int(
                    performance.get(
                        "resolved_positions"
                    )
                )
                < 3
            )
        )

        weighted_dna += (
            dna_score * weight
        )

        weighted_performance += (
            performance_score * weight
        )

        if specialist_match:
            specialist_value += value

        if independence_score >= 65:
            independent_value += value

        elite_wallets += elite_wallet

        contribution_score = clamp(
            dna_score * 0.45
            + performance_score * 0.30
            + independence_score * 0.15
            + specialist_match * 10.0
        )

        wallet_rows.append(
            {
                "wallet": wallet,
                "wallet_current_value": (
                    value
                ),
                "wallet_share_of_signal": (
                    weight
                ),
                "dna_score": dna_score,
                "dna_grade": clean_text(
                    dna.get(
                        "dna_grade"
                    )
                )
                or "UNRATED",
                "primary_archetype": (
                    clean_text(
                        dna.get(
                            "primary_archetype"
                        )
                    )
                ),
                "primary_category": (
                    primary_category
                ),
                "primary_category_share": (
                    safe_float(
                        dna.get(
                            "primary_category_share"
                        )
                    )
                ),
                "sports_specialty": (
                    sports_specialty
                ),
                "market_type_specialty": (
                    market_type_specialty
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
                    or "UNRATED"
                ),
                "resolved_positions": (
                    safe_int(
                        performance.get(
                            "resolved_positions"
                        )
                    )
                ),
                "win_rate": safe_float(
                    performance.get(
                        "win_rate"
                    )
                ),
                "estimated_roi": (
                    safe_float(
                        performance.get(
                            "estimated_roi"
                        )
                    )
                ),
                "portfolio_independence_score": (
                    independence_score
                ),
                "specialist_match": (
                    specialist_match
                ),
                "elite_wallet": (
                    elite_wallet
                ),
                "contribution_score": (
                    contribution_score
                ),
            }
        )

    specialist_share = (
        specialist_value
        / total_value
        if total_value > 0
        else 0.0
    )

    independent_share = (
        independent_value
        / total_value
        if total_value > 0
        else 0.0
    )

    return (
        weighted_dna,
        weighted_performance,
        specialist_share,
        independent_share,
        elite_wallets,
        wallet_rows,
    )


def score_mapping_quality(
    mapping: dict[str, Any] | None,
) -> float:
    if not mapping:
        return 20.0

    status = normalize_text(
        mapping.get(
            "mapping_status"
        )
    )

    confidence = safe_float(
        mapping.get(
            "match_confidence"
        )
    )

    if status == "mapped":
        return clamp(
            max(
                confidence,
                70.0,
            )
        )

    if status == "review_required":
        return clamp(
            min(
                confidence,
                70.0,
            )
        )

    return 20.0


def score_market_timing(
    lifecycle_status: str,
    seconds_to_start: int | None,
) -> float:
    lifecycle = normalize_text(
        lifecycle_status
    )

    if lifecycle in INACTIVE_LIFECYCLES:
        return 0.0

    if lifecycle in LIVE_LIFECYCLES:
        return 20.0

    if seconds_to_start is None:
        return 50.0

    if seconds_to_start <= 0:
        return 20.0

    minutes = (
        seconds_to_start / 60.0
    )

    if minutes <= 5:
        return 35.0

    if minutes <= 30:
        return 85.0

    if minutes <= 180:
        return 100.0

    if minutes <= 720:
        return 90.0

    if minutes <= 1_440:
        return 80.0

    if minutes <= 4_320:
        return 68.0

    return 55.0


def grade_from_score(
    score: float,
) -> tuple[str, str, str]:
    if score >= 92:
        return (
            "S+",
            "VERY HIGH",
            "VERY STRONG",
        )

    if score >= 84:
        return (
            "S",
            "HIGH",
            "STRONG",
        )

    if score >= 76:
        return (
            "A+",
            "HIGH",
            "STRONG",
        )

    if score >= 68:
        return (
            "A",
            "MEDIUM",
            "QUALIFIED",
        )

    if score >= 60:
        return (
            "B",
            "MEDIUM",
            "MODERATE",
        )

    if score >= 50:
        return (
            "C",
            "LOW",
            "WEAK",
        )

    return (
        "PASS",
        "LOW",
        "VERY WEAK",
    )


def determine_recommendation(
    fusion_score: float,
    lifecycle_status: str,
    seconds_to_start: int | None,
    conflict_ratio: float,
    chase_risk_score: float | None,
    reversal_score: float | None,
    source_count: int,
    mapping_status: str,
) -> str:
    lifecycle = normalize_text(
        lifecycle_status
    )

    if lifecycle in INACTIVE_LIFECYCLES:
        return "PASS - MARKET INACTIVE"

    if lifecycle in LIVE_LIFECYCLES:
        return "LIVE REVIEW REQUIRED"

    if (
        seconds_to_start is not None
        and seconds_to_start <= 300
    ):
        return "PASS - TOO CLOSE TO START"

    if conflict_ratio >= 0.45:
        return (
            "PASS - SMART MONEY CONFLICT"
        )

    if (
        reversal_score is not None
        and reversal_score >= 60
    ):
        return "PASS - ACTIVE REVERSAL"

    if (
        chase_risk_score is not None
        and chase_risk_score >= 75
    ):
        return "DO NOT CHASE"

    if source_count < 5:
        return "WATCH - DATA INCOMPLETE"

    if normalize_text(
        mapping_status
    ) != "mapped":
        return "WATCH - MAPPING INCOMPLETE"

    if fusion_score >= 92:
        return "ELITE BUY ZONE"

    if fusion_score >= 84:
        return (
            "HIGH-PRIORITY ENTRY REVIEW"
        )

    if fusion_score >= 76:
        return (
            "QUALIFIED ENTRY REVIEW"
        )

    if fusion_score >= 68:
        return "MONITOR FOR ENTRY"

    if fusion_score >= 60:
        return "WATCHLIST"

    return "PASS"


# =============================================================================
# FUSION BUILD
# =============================================================================


def build_fusion_records() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
]:
    master_rows = load_table_by_key(
        "master_opportunities",
        "opportunity_key",
    )

    if not master_rows:
        raise RuntimeError(
            "master_opportunities is empty or missing. "
            "Run master_opportunity_engine.py first."
        )

    institutional_rows = load_table_by_key(
        "institutional_consensus",
        "consensus_key",
    )

    evolution_rows = load_table_by_key(
        "position_evolution",
        "evolution_key",
    )

    closing_rows = load_table_by_key(
        "closing_line_metrics",
        "opportunity_key",
    )

    price_rows = load_table_by_key(
        "market_price_metrics",
        "market_id",
    )

    dna_lookup = load_wallet_dna()
    performance_lookup = (
        load_wallet_performance()
    )

    positions = load_latest_positions()
    position_groups = (
        build_position_groups(
            positions
        )
    )

    mapping_lookup = (
        load_market_mapping_lookup()
    )

    calculated_at = utc_now_iso()

    fusion_records: list[
        dict[str, Any]
    ] = []

    fusion_wallet_rows: list[
        dict[str, Any]
    ] = []

    for opportunity_key, master in (
        master_rows.items()
    ):
        market_id = clean_text(
            master.get(
                "market_id"
            )
        ).lower()

        outcome = normalize_outcome(
            master.get(
                "outcome"
            )
        )

        title = clean_text(
            master.get(
                "title"
            )
        )

        institutional = (
            institutional_rows.get(
                opportunity_key,
                {},
            )
        )

        evolution = (
            evolution_rows.get(
                opportunity_key,
                {},
            )
        )

        closing = closing_rows.get(
            opportunity_key,
            {},
        )

        price = (
            price_rows.get(
                market_id,
                {}
            )
        )

        mapping = (
            mapping_lookup.get(
                market_id
            )
        )

        group_positions = (
            position_groups.get(
                (
                    market_id,
                    outcome,
                ),
                [],
            )
        )

        (
            average_wallet_dna,
            average_wallet_performance,
            specialist_wallet_share,
            independent_wallet_share,
            elite_wallets,
            wallet_rows,
        ) = score_wallet_inputs(
            title=title,
            positions=group_positions,
            dna_lookup=dna_lookup,
            performance_lookup=(
                performance_lookup
            ),
        )

        master_score = safe_float(
            master.get(
                "master_score"
            )
        )

        institutional_score = safe_float(
            institutional.get(
                "consensus_strength"
            ),
            safe_float(
                master.get(
                    "institutional_score"
                ),
                50.0,
            ),
        )

        evolution_score = safe_float(
            evolution.get(
                "evolution_score"
            ),
            safe_float(
                master.get(
                    "evolution_score"
                ),
                50.0,
            ),
        )

        closing_line_score = safe_float(
            master.get(
                "closing_line_score"
            ),
            50.0,
        )

        price_action_score = safe_float(
            master.get(
                "price_action_score"
            ),
            50.0,
        )

        mapping_quality_score = (
            score_mapping_quality(
                mapping
            )
        )

        lifecycle_status = clean_text(
            master.get(
                "lifecycle_status"
            )
        ) or "UNKNOWN"

        seconds_value = master.get(
            "seconds_to_start"
        )

        seconds_to_start = (
            safe_int(
                seconds_value
            )
            if seconds_value
            is not None
            else None
        )

        timing_score = (
            score_market_timing(
                lifecycle_status,
                seconds_to_start,
            )
        )

        agreeing_wallets = safe_int(
            master.get(
                "wallet_count"
            ),
            len(
                group_positions
            ),
        )

        effective_wallets = safe_float(
            master.get(
                "effective_wallet_count"
            ),
            float(
                agreeing_wallets
            ),
        )

        combined_current_value = safe_float(
            master.get(
                "combined_current_value"
            ),
            sum(
                safe_float(
                    position.get(
                        "current_value"
                    )
                )
                for position
                in group_positions
            ),
        )

        conflict_ratio = normalize_ratio(
            master.get(
                "conflict_ratio"
            )
        )

        portfolio_independence_score = safe_float(
            master.get(
                "portfolio_independence_score"
            ),
            independent_wallet_share
            * 100.0,
        )

        strengthening_score = safe_float(
            evolution.get(
                "strengthening_score"
            ),
            safe_float(
                master.get(
                    "strengthening_score"
                ),
                50.0,
            ),
        )

        weakening_score = safe_float(
            evolution.get(
                "weakening_score"
            ),
            safe_float(
                master.get(
                    "weakening_score"
                ),
                0.0,
            ),
        )

        net_value_change = safe_float(
            evolution.get(
                "net_value_change"
            ),
            safe_float(
                master.get(
                    "net_value_change"
                )
            ),
        )

        clv_score = (
            safe_float(
                closing.get(
                    "clv_score"
                )
            )
            if closing
            and closing.get(
                "clv_score"
            )
            is not None
            else None
        )

        edge_remaining_score = (
            safe_float(
                closing.get(
                    "edge_remaining_score"
                )
            )
            if closing
            and closing.get(
                "edge_remaining_score"
            )
            is not None
            else None
        )

        chase_risk_score = (
            safe_float(
                closing.get(
                    "chase_risk_score"
                )
            )
            if closing
            and closing.get(
                "chase_risk_score"
            )
            is not None
            else None
        )

        steam_score = (
            safe_float(
                price.get(
                    "steam_score"
                )
            )
            if price
            else None
        )

        reversal_score = (
            safe_float(
                price.get(
                    "reversal_score"
                )
            )
            if price
            else None
        )

        volatility_score = (
            safe_float(
                price.get(
                    "volatility_score"
                )
            )
            if price
            else None
        )

        source_presence = {
            "master": True,
            "institutional": bool(
                institutional
            ),
            "evolution": bool(
                evolution
            ),
            "closing": bool(
                closing
            ),
            "price": bool(
                price
            ),
            "wallet_dna": bool(
                group_positions
            )
            and bool(
                dna_lookup
            ),
            "wallet_performance": bool(
                group_positions
            )
            and bool(
                performance_lookup
            ),
            "mapping": bool(
                mapping
            ),
        }

        source_count = sum(
            int(value)
            for value in source_presence.values()
        )

        source_coverage = (
            source_count
            / len(
                source_presence
            )
            * 100.0
        )

        input_quality_values = [
            safe_float(
                master.get(
                    "data_completeness_score"
                )
            ),
            source_coverage,
            mapping_quality_score,
        ]

        data_completeness_score = (
            safe_mean(
                input_quality_values,
                0.0,
            )
        )

        if data_completeness_score >= 85:
            data_confidence = "VERY HIGH"

        elif data_completeness_score >= 70:
            data_confidence = "HIGH"

        elif data_completeness_score >= 55:
            data_confidence = "MEDIUM"

        elif data_completeness_score >= 40:
            data_confidence = "LOW"

        else:
            data_confidence = "VERY LOW"

        raw_fusion_score = (
            master_score
            * FUSION_WEIGHTS[
                "master_opportunity"
            ]
            + institutional_score
            * FUSION_WEIGHTS[
                "institutional_consensus"
            ]
            + evolution_score
            * FUSION_WEIGHTS[
                "position_evolution"
            ]
            + average_wallet_dna
            * FUSION_WEIGHTS[
                "wallet_dna"
            ]
            + average_wallet_performance
            * FUSION_WEIGHTS[
                "wallet_performance"
            ]
            + closing_line_score
            * FUSION_WEIGHTS[
                "closing_line"
            ]
            + price_action_score
            * FUSION_WEIGHTS[
                "price_action"
            ]
            + mapping_quality_score
            * FUSION_WEIGHTS[
                "mapping_quality"
            ]
            + timing_score
            * FUSION_WEIGHTS[
                "market_timing"
            ]
        )

        specialist_bonus = (
            specialist_wallet_share
            * 8.0
        )

        elite_bonus = min(
            elite_wallets * 1.5,
            6.0,
        )

        independence_bonus = max(
            portfolio_independence_score
            - 60.0,
            0.0,
        ) / 40.0 * 4.0

        strengthening_bonus = max(
            strengthening_score
            - 60.0,
            0.0,
        ) / 40.0 * 5.0

        raw_fusion_score += (
            specialist_bonus
            + elite_bonus
            + independence_bonus
            + strengthening_bonus
        )

        lifecycle_normalized = (
            normalize_text(
                lifecycle_status
            )
        )

        live_penalty = (
            35.0
            if lifecycle_normalized
            in LIVE_LIFECYCLES
            else 0.0
        )

        inactive_penalty = (
            100.0
            if lifecycle_normalized
            in INACTIVE_LIFECYCLES
            else 0.0
        )

        conflict_penalty = clamp(
            conflict_ratio
            * 25.0,
            0.0,
            25.0,
        )

        chase_penalty = 0.0

        if chase_risk_score is not None:
            chase_penalty = clamp(
                max(
                    chase_risk_score
                    - 45.0,
                    0.0,
                )
                / 55.0
                * 18.0,
                0.0,
                18.0,
            )

        reversal_penalty = 0.0

        if reversal_score is not None:
            reversal_penalty = clamp(
                reversal_score
                / 100.0
                * 18.0,
                0.0,
                18.0,
            )

        weakening_penalty = clamp(
            max(
                weakening_score
                - 35.0,
                0.0,
            )
            / 65.0
            * 16.0,
            0.0,
            16.0,
        )

        low_sample_penalty = 0.0

        if agreeing_wallets <= 1:
            low_sample_penalty = 12.0

        elif effective_wallets < 1.5:
            low_sample_penalty = 8.0

        elif agreeing_wallets == 2:
            low_sample_penalty = 4.0

        mapping_penalty = clamp(
            max(
                70.0
                - mapping_quality_score,
                0.0,
            )
            / 70.0
            * 10.0,
            0.0,
            10.0,
        )

        total_penalty = (
            live_penalty
            + inactive_penalty
            + conflict_penalty
            + chase_penalty
            + reversal_penalty
            + weakening_penalty
            + low_sample_penalty
            + mapping_penalty
        )

        fusion_score = clamp(
            raw_fusion_score
            - total_penalty
        )

        (
            fusion_grade,
            confidence_tier,
            signal_strength,
        ) = grade_from_score(
            fusion_score
        )

        if agreeing_wallets <= 1:
            fusion_score = min(
                fusion_score,
                74.9,
            )

            (
                fusion_grade,
                confidence_tier,
                signal_strength,
            ) = grade_from_score(
                fusion_score
            )

        if (
            lifecycle_normalized
            in LIVE_LIFECYCLES
        ):
            fusion_grade = "PASS"
            confidence_tier = "LIVE"
            signal_strength = "LIVE"

        if (
            lifecycle_normalized
            in INACTIVE_LIFECYCLES
        ):
            fusion_score = 0.0
            fusion_grade = "PASS"
            confidence_tier = "INACTIVE"
            signal_strength = "INACTIVE"

        mapping_status = (
            clean_text(
                mapping.get(
                    "mapping_status"
                )
            )
            if mapping
            else "UNRESOLVED"
        )

        match_method = (
            clean_text(
                mapping.get(
                    "match_method"
                )
            )
            if mapping
            else "NONE"
        )

        match_confidence = (
            safe_float(
                mapping.get(
                    "match_confidence"
                )
            )
            if mapping
            else 0.0
        )

        recommendation = (
            determine_recommendation(
                fusion_score=(
                    fusion_score
                ),
                lifecycle_status=(
                    lifecycle_status
                ),
                seconds_to_start=(
                    seconds_to_start
                ),
                conflict_ratio=(
                    conflict_ratio
                ),
                chase_risk_score=(
                    chase_risk_score
                ),
                reversal_score=(
                    reversal_score
                ),
                source_count=(
                    source_count
                ),
                mapping_status=(
                    mapping_status
                ),
            )
        )

        positive_signals: list[str] = []
        negative_signals: list[str] = []

        if institutional_score >= 74:
            positive_signals.append(
                "Strong institutional consensus"
            )

        if strengthening_score >= 70:
            positive_signals.append(
                "Position evolution is strengthening"
            )

        if net_value_change > 0:
            positive_signals.append(
                "Net smart-money capital inflow"
            )

        if average_wallet_dna >= 70:
            positive_signals.append(
                "High average wallet DNA"
            )

        if specialist_wallet_share >= 0.60:
            positive_signals.append(
                "Specialist wallets dominate the signal"
            )

        if elite_wallets >= 2:
            positive_signals.append(
                "Multiple elite wallets agree"
            )

        if (
            edge_remaining_score is not None
            and edge_remaining_score >= 70
        ):
            positive_signals.append(
                "Strong remaining edge"
            )

        if (
            steam_score is not None
            and steam_score >= 50
        ):
            positive_signals.append(
                "Price steam confirms direction"
            )

        if portfolio_independence_score >= 70:
            positive_signals.append(
                "Consensus is relatively independent"
            )

        if conflict_ratio >= 0.30:
            negative_signals.append(
                "Meaningful opposing smart money"
            )

        if (
            chase_risk_score is not None
            and chase_risk_score >= 55
        ):
            negative_signals.append(
                "Late-entry or chase risk"
            )

        if (
            reversal_score is not None
            and reversal_score >= 35
        ):
            negative_signals.append(
                "Price reversal risk"
            )

        if weakening_score >= 55:
            negative_signals.append(
                "Position evolution is weakening"
            )

        if agreeing_wallets <= 1:
            negative_signals.append(
                "Single-wallet signal"
            )

        if mapping_status != "MAPPED":
            negative_signals.append(
                "Market mapping is incomplete"
            )

        if source_count < 5:
            negative_signals.append(
                "Limited source coverage"
            )

        explanation = {
            "model_version": "1.0",
            "weights": FUSION_WEIGHTS,
            "components": {
                "master_opportunity": round(
                    master_score,
                    2,
                ),
                "institutional_consensus": round(
                    institutional_score,
                    2,
                ),
                "position_evolution": round(
                    evolution_score,
                    2,
                ),
                "wallet_dna": round(
                    average_wallet_dna,
                    2,
                ),
                "wallet_performance": round(
                    average_wallet_performance,
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
                "mapping_quality": round(
                    mapping_quality_score,
                    2,
                ),
                "market_timing": round(
                    timing_score,
                    2,
                ),
            },
            "bonuses": {
                "specialist_bonus": round(
                    specialist_bonus,
                    2,
                ),
                "elite_wallet_bonus": round(
                    elite_bonus,
                    2,
                ),
                "independence_bonus": round(
                    independence_bonus,
                    2,
                ),
                "strengthening_bonus": round(
                    strengthening_bonus,
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
                "conflict": round(
                    conflict_penalty,
                    2,
                ),
                "chase": round(
                    chase_penalty,
                    2,
                ),
                "reversal": round(
                    reversal_penalty,
                    2,
                ),
                "weakening": round(
                    weakening_penalty,
                    2,
                ),
                "low_sample": round(
                    low_sample_penalty,
                    2,
                ),
                "mapping": round(
                    mapping_penalty,
                    2,
                ),
            },
            "important_notes": [
                (
                    "Fusion score is a research ranking, "
                    "not a calibrated probability."
                ),
                (
                    "Wallet performance remains provisional "
                    "until mapping and realized trade-ledger "
                    "coverage improve."
                ),
                (
                    "Live and inactive markets cannot receive "
                    "actionable fusion recommendations."
                ),
            ],
        }

        fusion_record = {
            "opportunity_key": (
                opportunity_key
            ),
            "market_id": market_id,
            "title": title,
            "outcome": clean_text(
                master.get(
                    "outcome"
                )
            ),
            "gamma_market_id": (
                clean_text(
                    mapping.get(
                        "gamma_market_id"
                    )
                )
                if mapping
                else ""
            ),
            "gamma_event_id": (
                clean_text(
                    mapping.get(
                        "gamma_event_id"
                    )
                )
                if mapping
                else ""
            ),
            "condition_id": (
                clean_text(
                    mapping.get(
                        "condition_id"
                    )
                )
                if mapping
                else market_id
            ),
            "fusion_score": round(
                fusion_score,
                1,
            ),
            "fusion_grade": (
                fusion_grade
            ),
            "confidence_tier": (
                confidence_tier
            ),
            "signal_strength": (
                signal_strength
            ),
            "recommendation": (
                recommendation
            ),
            "lifecycle_status": (
                lifecycle_status
            ),
            "seconds_to_start": (
                seconds_to_start
            ),
            "master_score": (
                master_score
            ),
            "institutional_score": (
                institutional_score
            ),
            "evolution_score": (
                evolution_score
            ),
            "wallet_dna_score": (
                average_wallet_dna
            ),
            "wallet_performance_score": (
                average_wallet_performance
            ),
            "closing_line_score": (
                closing_line_score
            ),
            "price_action_score": (
                price_action_score
            ),
            "mapping_quality_score": (
                mapping_quality_score
            ),
            "timing_score": timing_score,
            "agreeing_wallets": (
                agreeing_wallets
            ),
            "elite_wallets": (
                elite_wallets
            ),
            "effective_wallets": (
                effective_wallets
            ),
            "combined_current_value": (
                combined_current_value
            ),
            "average_wallet_dna": (
                average_wallet_dna
            ),
            "average_wallet_performance": (
                average_wallet_performance
            ),
            "specialist_wallet_share": (
                specialist_wallet_share
            ),
            "independent_wallet_share": (
                independent_wallet_share
            ),
            "conflict_ratio": (
                conflict_ratio
            ),
            "portfolio_independence_score": (
                portfolio_independence_score
            ),
            "strengthening_score": (
                strengthening_score
            ),
            "weakening_score": (
                weakening_score
            ),
            "net_value_change": (
                net_value_change
            ),
            "clv_score": clv_score,
            "edge_remaining_score": (
                edge_remaining_score
            ),
            "chase_risk_score": (
                chase_risk_score
            ),
            "steam_score": steam_score,
            "reversal_score": (
                reversal_score
            ),
            "volatility_score": (
                volatility_score
            ),
            "mapping_status": (
                mapping_status
            ),
            "match_method": (
                match_method
            ),
            "match_confidence": (
                match_confidence
            ),
            "source_count": source_count,
            "data_completeness_score": (
                data_completeness_score
            ),
            "data_confidence": (
                data_confidence
            ),
            "live_penalty": (
                live_penalty
            ),
            "inactive_penalty": (
                inactive_penalty
            ),
            "conflict_penalty": (
                conflict_penalty
            ),
            "chase_penalty": (
                chase_penalty
            ),
            "reversal_penalty": (
                reversal_penalty
            ),
            "weakening_penalty": (
                weakening_penalty
            ),
            "low_sample_penalty": (
                low_sample_penalty
            ),
            "mapping_penalty": (
                mapping_penalty
            ),
            "total_penalty": (
                total_penalty
            ),
            "positive_signals_json": (
                stable_json(
                    positive_signals
                )
            ),
            "negative_signals_json": (
                stable_json(
                    negative_signals
                )
            ),
            "explanation_json": (
                stable_json(
                    explanation
                )
            ),
            "calculated_at": (
                calculated_at
            ),
            "updated_at": (
                calculated_at
            ),
        }

        fusion_records.append(
            fusion_record
        )

        for wallet_row in wallet_rows:
            fusion_wallet_rows.append(
                {
                    "fusion_wallet_key": (
                        f"{opportunity_key}:"
                        f"{wallet_row['wallet']}"
                    ),
                    "opportunity_key": (
                        opportunity_key
                    ),
                    **wallet_row,
                    "calculated_at": (
                        calculated_at
                    ),
                    "updated_at": (
                        calculated_at
                    ),
                }
            )

    fusion_records.sort(
        key=lambda row: (
            row["fusion_score"],
            row["elite_wallets"],
            row[
                "combined_current_value"
            ],
        ),
        reverse=True,
    )

    fusion_wallet_rows.sort(
        key=lambda row: (
            row["opportunity_key"],
            row[
                "contribution_score"
            ],
        ),
        reverse=True,
    )

    return (
        fusion_records,
        fusion_wallet_rows,
        len(positions),
    )


# =============================================================================
# SAVING
# =============================================================================


FUSION_COLUMNS = [
    "opportunity_key",
    "market_id",
    "title",
    "outcome",
    "gamma_market_id",
    "gamma_event_id",
    "condition_id",
    "fusion_score",
    "fusion_grade",
    "confidence_tier",
    "signal_strength",
    "recommendation",
    "lifecycle_status",
    "seconds_to_start",
    "master_score",
    "institutional_score",
    "evolution_score",
    "wallet_dna_score",
    "wallet_performance_score",
    "closing_line_score",
    "price_action_score",
    "mapping_quality_score",
    "timing_score",
    "agreeing_wallets",
    "elite_wallets",
    "effective_wallets",
    "combined_current_value",
    "average_wallet_dna",
    "average_wallet_performance",
    "specialist_wallet_share",
    "independent_wallet_share",
    "conflict_ratio",
    "portfolio_independence_score",
    "strengthening_score",
    "weakening_score",
    "net_value_change",
    "clv_score",
    "edge_remaining_score",
    "chase_risk_score",
    "steam_score",
    "reversal_score",
    "volatility_score",
    "mapping_status",
    "match_method",
    "match_confidence",
    "source_count",
    "data_completeness_score",
    "data_confidence",
    "live_penalty",
    "inactive_penalty",
    "conflict_penalty",
    "chase_penalty",
    "reversal_penalty",
    "weakening_penalty",
    "low_sample_penalty",
    "mapping_penalty",
    "total_penalty",
    "positive_signals_json",
    "negative_signals_json",
    "explanation_json",
    "calculated_at",
    "updated_at",
]


WALLET_COLUMNS = [
    "fusion_wallet_key",
    "opportunity_key",
    "wallet",
    "wallet_current_value",
    "wallet_share_of_signal",
    "dna_score",
    "dna_grade",
    "primary_archetype",
    "primary_category",
    "primary_category_share",
    "sports_specialty",
    "market_type_specialty",
    "performance_score",
    "performance_grade",
    "resolved_positions",
    "win_rate",
    "estimated_roi",
    "portfolio_independence_score",
    "specialist_match",
    "elite_wallet",
    "contribution_score",
    "calculated_at",
    "updated_at",
]


def build_upsert_query(
    table_name: str,
    columns: list[str],
    primary_key: str,
) -> str:
    names = ", ".join(
        f'"{column}"'
        for column in columns
    )

    placeholders = ", ".join(
        "?"
        for _ in columns
    )

    updates = ", ".join(
        f'"{column}" = excluded."{column}"'
        for column in columns
        if column != primary_key
    )

    return f"""
        INSERT INTO "{table_name}" (
            {names}
        )
        VALUES (
            {placeholders}
        )
        ON CONFLICT("{primary_key}")
        DO UPDATE SET
            {updates}
    """


def create_alerts(
    connection: sqlite3.Connection,
    records: list[dict[str, Any]],
    created_at: str,
) -> int:
    alerts_saved = 0

    for record in records:
        recommendation = (
            record["recommendation"]
        )

        alert_type = ""
        severity = ""

        if recommendation == "ELITE BUY ZONE":
            alert_type = "ELITE_SIGNAL"
            severity = "HIGH"

        elif recommendation == (
            "HIGH-PRIORITY ENTRY REVIEW"
        ):
            alert_type = "HIGH_PRIORITY"
            severity = "MEDIUM"

        elif recommendation == (
            "DO NOT CHASE"
        ):
            alert_type = "CHASE_RISK"
            severity = "MEDIUM"

        elif recommendation == (
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
            f"Fusion score "
            f"{record['fusion_score']:.1f}"
        )

        details = {
            "fusion_grade": (
                record[
                    "fusion_grade"
                ]
            ),
            "confidence_tier": (
                record[
                    "confidence_tier"
                ]
            ),
            "signal_strength": (
                record[
                    "signal_strength"
                ]
            ),
            "positive_signals": (
                json.loads(
                    record[
                        "positive_signals_json"
                    ]
                )
            ),
            "negative_signals": (
                json.loads(
                    record[
                        "negative_signals_json"
                    ]
                )
            ),
        }

        connection.execute(
            """
            INSERT INTO signal_fusion_alerts (
                opportunity_key,
                market_id,
                title,
                outcome,
                alert_type,
                severity,
                fusion_score,
                fusion_grade,
                recommendation,
                message,
                details_json,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                record[
                    "opportunity_key"
                ],
                record["market_id"],
                record["title"],
                record["outcome"],
                alert_type,
                severity,
                record[
                    "fusion_score"
                ],
                record[
                    "fusion_grade"
                ],
                recommendation,
                message,
                stable_json(
                    details
                ),
                created_at,
            ),
        )

        alerts_saved += 1

    return alerts_saved


def save_fusion_data(
    records: list[dict[str, Any]],
    wallet_rows: list[dict[str, Any]],
) -> tuple[int, int, int, int]:
    connection = connect_database()

    fusion_query = build_upsert_query(
        "signal_fusion_scores",
        FUSION_COLUMNS,
        "opportunity_key",
    )

    wallet_query = build_upsert_query(
        "signal_fusion_wallets",
        WALLET_COLUMNS,
        "fusion_wallet_key",
    )

    observed_at = utc_now_iso()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        connection.execute(
            "DELETE FROM signal_fusion_scores"
        )

        connection.execute(
            "DELETE FROM signal_fusion_wallets"
        )

        for record in records:
            connection.execute(
                fusion_query,
                tuple(
                    record[column]
                    for column
                    in FUSION_COLUMNS
                ),
            )

            connection.execute(
                """
                INSERT INTO signal_fusion_history (
                    opportunity_key,
                    market_id,
                    title,
                    outcome,
                    fusion_score,
                    fusion_grade,
                    confidence_tier,
                    signal_strength,
                    recommendation,
                    agreeing_wallets,
                    elite_wallets,
                    combined_current_value,
                    master_score,
                    institutional_score,
                    evolution_score,
                    wallet_dna_score,
                    wallet_performance_score,
                    closing_line_score,
                    price_action_score,
                    mapping_quality_score,
                    timing_score,
                    total_penalty,
                    data_completeness_score,
                    data_confidence,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?
                )
                """,
                (
                    record[
                        "opportunity_key"
                    ],
                    record[
                        "market_id"
                    ],
                    record[
                        "title"
                    ],
                    record[
                        "outcome"
                    ],
                    record[
                        "fusion_score"
                    ],
                    record[
                        "fusion_grade"
                    ],
                    record[
                        "confidence_tier"
                    ],
                    record[
                        "signal_strength"
                    ],
                    record[
                        "recommendation"
                    ],
                    record[
                        "agreeing_wallets"
                    ],
                    record[
                        "elite_wallets"
                    ],
                    record[
                        "combined_current_value"
                    ],
                    record[
                        "master_score"
                    ],
                    record[
                        "institutional_score"
                    ],
                    record[
                        "evolution_score"
                    ],
                    record[
                        "wallet_dna_score"
                    ],
                    record[
                        "wallet_performance_score"
                    ],
                    record[
                        "closing_line_score"
                    ],
                    record[
                        "price_action_score"
                    ],
                    record[
                        "mapping_quality_score"
                    ],
                    record[
                        "timing_score"
                    ],
                    record[
                        "total_penalty"
                    ],
                    record[
                        "data_completeness_score"
                    ],
                    record[
                        "data_confidence"
                    ],
                    observed_at,
                ),
            )

        for wallet_row in wallet_rows:
            connection.execute(
                wallet_query,
                tuple(
                    wallet_row[column]
                    for column
                    in WALLET_COLUMNS
                ),
            )

        alerts_saved = create_alerts(
            connection=connection,
            records=records,
            created_at=observed_at,
        )

        connection.commit()

        return (
            len(records),
            len(wallet_rows),
            len(records),
            alerts_saved,
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
    started = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO signal_fusion_runs (
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
    started_at: datetime,
    status: str,
    opportunities_loaded: int,
    wallet_rows_loaded: int,
    fusion_rows_saved: int,
    fusion_wallet_rows_saved: int,
    history_rows_saved: int,
    alerts_saved: int,
    error_message: str = "",
) -> None:
    finished = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE signal_fusion_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                opportunities_loaded = ?,
                wallet_rows_loaded = ?,
                fusion_rows_saved = ?,
                fusion_wallet_rows_saved = ?,
                history_rows_saved = ?,
                alerts_saved = ?,
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
                opportunities_loaded,
                wallet_rows_loaded,
                fusion_rows_saved,
                fusion_wallet_rows_saved,
                history_rows_saved,
                alerts_saved,
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
    records: list[dict[str, Any]],
    wallet_rows: list[dict[str, Any]],
    positions_loaded: int,
    alerts_saved: int,
    display_limit: int,
) -> None:
    grade_counts = Counter(
        record[
            "fusion_grade"
        ]
        for record in records
    )

    recommendation_counts = Counter(
        record[
            "recommendation"
        ]
        for record in records
    )

    print()
    print("=" * 112)
    print("SIGNAL FUSION ENGINE SUMMARY")
    print("=" * 112)

    print(
        f"Master opportunities loaded:    "
        f"{len(records)}"
    )

    print(
        f"Latest positions loaded:        "
        f"{positions_loaded}"
    )

    print(
        f"Wallet contribution rows:       "
        f"{len(wallet_rows)}"
    )

    print(
        f"S+ signals:                     "
        f"{grade_counts.get('S+', 0)}"
    )

    print(
        f"S or better:                    "
        f"{grade_counts.get('S+', 0) + grade_counts.get('S', 0)}"
    )

    print(
        f"A or better:                    "
        f"{sum(grade_counts.get(grade, 0) for grade in ('S+', 'S', 'A+', 'A'))}"
    )

    print(
        f"Alerts saved:                   "
        f"{alerts_saved}"
    )

    print()
    print("TOP RECOMMENDATION COUNTS")

    for label, count in (
        recommendation_counts.most_common(
            12
        )
    ):
        print(
            f"{label:<52}"
            f"{count:>8}"
        )

    print("=" * 112)

    print()
    print("TOP UNIFIED SIGNALS")

    for rank, record in enumerate(
        records[
            :display_limit
        ],
        start=1,
    ):
        positive_signals = json.loads(
            record[
                "positive_signals_json"
            ]
        )

        negative_signals = json.loads(
            record[
                "negative_signals_json"
            ]
        )

        print()
        print("-" * 112)

        print(
            f"{rank}. "
            f"{record['title']} — "
            f"{record['outcome']}"
        )

        print("-" * 112)

        print(
            f"Fusion score / grade:           "
            f"{record['fusion_score']:.1f} "
            f"/ {record['fusion_grade']}"
        )

        print(
            f"Confidence / strength:          "
            f"{record['confidence_tier']} "
            f"/ {record['signal_strength']}"
        )

        print(
            f"Recommendation:                 "
            f"{record['recommendation']}"
        )

        print(
            f"Wallets / elite wallets:        "
            f"{record['agreeing_wallets']} "
            f"/ {record['elite_wallets']}"
        )

        print(
            f"Smart-money value:              "
            f"{format_money(record['combined_current_value'])}"
        )

        print(
            f"Master / Institutional:         "
            f"{record['master_score']:.1f} "
            f"/ {record['institutional_score']:.1f}"
        )

        print(
            f"Evolution / Wallet DNA:         "
            f"{record['evolution_score']:.1f} "
            f"/ {record['wallet_dna_score']:.1f}"
        )

        print(
            f"Wallet performance:             "
            f"{record['wallet_performance_score']:.1f}"
        )

        print(
            f"CLV / price action:             "
            f"{record['closing_line_score']:.1f} "
            f"/ {record['price_action_score']:.1f}"
        )

        print(
            f"Specialist / independent share: "
            f"{format_percentage(record['specialist_wallet_share'])} "
            f"/ {format_percentage(record['independent_wallet_share'])}"
        )

        print(
            f"Mapping:                        "
            f"{record['mapping_status']} "
            f"/ {record['match_method']} "
            f"/ {record['match_confidence']:.1f}"
        )

        print(
            f"Data confidence:                "
            f"{record['data_confidence']} "
            f"({record['data_completeness_score']:.1f})"
        )

        print(
            f"Total penalty:                  "
            f"-{record['total_penalty']:.1f}"
        )

        if positive_signals:
            print()
            print("POSITIVE SIGNALS")

            for signal in positive_signals:
                print(
                    f"  + {signal}"
                )

        if negative_signals:
            print()
            print("RISK SIGNALS")

            for signal in negative_signals:
                print(
                    f"  - {signal}"
                )


# =============================================================================
# ARGUMENTS AND MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fuse master opportunity, institutional consensus, "
            "position evolution, wallet DNA, wallet performance, "
            "closing-line, price, mapping and timing intelligence."
        )
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8_output()
    arguments = parse_arguments()

    print()
    print("=" * 112)
    print("POLYMARKET SIGNAL FUSION ENGINE v1")
    print("=" * 112)

    print(
        f"Database: {DATABASE_PATH}"
    )

    print(
        "Method: unified multi-engine intelligence fusion"
    )

    create_signal_fusion_tables()

    run_id, started_at = start_run()

    records: list[
        dict[str, Any]
    ] = []

    wallet_rows: list[
        dict[str, Any]
    ] = []

    positions_loaded = 0

    fusion_saved = 0
    wallet_saved = 0
    history_saved = 0
    alerts_saved = 0

    try:
        (
            records,
            wallet_rows,
            positions_loaded,
        ) = build_fusion_records()

        (
            fusion_saved,
            wallet_saved,
            history_saved,
            alerts_saved,
        ) = save_fusion_data(
            records=records,
            wallet_rows=wallet_rows,
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            opportunities_loaded=(
                len(records)
            ),
            wallet_rows_loaded=(
                len(wallet_rows)
            ),
            fusion_rows_saved=(
                fusion_saved
            ),
            fusion_wallet_rows_saved=(
                wallet_saved
            ),
            history_rows_saved=(
                history_saved
            ),
            alerts_saved=(
                alerts_saved
            ),
        )

        display_summary(
            records=records,
            wallet_rows=wallet_rows,
            positions_loaded=(
                positions_loaded
            ),
            alerts_saved=alerts_saved,
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 112)
        print("SIGNAL FUSION ENGINE COMPLETE")
        print("=" * 112)

        print(
            "Unified market scores were saved to "
            "signal_fusion_scores."
        )

        print(
            "Per-wallet signal contributions were saved to "
            "signal_fusion_wallets."
        )

        print(
            "Historical signal snapshots were saved to "
            "signal_fusion_history."
        )

        print(
            "Actionable and risk alerts were saved to "
            "signal_fusion_alerts."
        )

        print(
            "Fusion scores are research rankings, "
            "not calibrated probabilities."
        )

        print("=" * 112)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            opportunities_loaded=(
                len(records)
            ),
            wallet_rows_loaded=(
                len(wallet_rows)
            ),
            fusion_rows_saved=(
                fusion_saved
            ),
            fusion_wallet_rows_saved=(
                wallet_saved
            ),
            history_rows_saved=(
                history_saved
            ),
            alerts_saved=(
                alerts_saved
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()