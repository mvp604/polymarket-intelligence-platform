from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 25


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


def safe_divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    if denominator == 0:
        return default

    return numerator / denominator


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


def require_tables(
    connection: sqlite3.Connection,
    names: list[str],
) -> None:
    missing = [
        name
        for name in names
        if not table_exists(
            connection,
            name,
        )
    ]

    if missing:
        raise RuntimeError(
            "Required tables are missing: "
            + ", ".join(missing)
        )


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_dna_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS wallet_dna_profiles (
                wallet TEXT PRIMARY KEY,

                dna_score REAL
                    NOT NULL DEFAULT 0,

                dna_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                data_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                primary_archetype TEXT
                    NOT NULL DEFAULT 'INSUFFICIENT DATA',

                secondary_archetype TEXT,

                specialization_label TEXT,
                risk_label TEXT,
                conviction_label TEXT,
                diversification_label TEXT,
                performance_label TEXT,

                current_position_count INTEGER
                    NOT NULL DEFAULT 0,

                current_market_count INTEGER
                    NOT NULL DEFAULT 0,

                current_value REAL
                    NOT NULL DEFAULT 0,

                average_position_value REAL
                    NOT NULL DEFAULT 0,

                largest_position_value REAL
                    NOT NULL DEFAULT 0,

                largest_position_share REAL
                    NOT NULL DEFAULT 0,

                top_three_concentration REAL
                    NOT NULL DEFAULT 0,

                herfindahl_index REAL
                    NOT NULL DEFAULT 0,

                effective_market_count REAL
                    NOT NULL DEFAULT 0,

                concentration_score REAL
                    NOT NULL DEFAULT 0,

                diversification_score REAL
                    NOT NULL DEFAULT 0,

                conviction_score REAL
                    NOT NULL DEFAULT 0,

                whale_score REAL
                    NOT NULL DEFAULT 0,

                specialization_score REAL
                    NOT NULL DEFAULT 0,

                category_diversity INTEGER
                    NOT NULL DEFAULT 0,

                primary_category TEXT,
                primary_category_share REAL
                    NOT NULL DEFAULT 0,

                sports_share REAL
                    NOT NULL DEFAULT 0,

                politics_share REAL
                    NOT NULL DEFAULT 0,

                crypto_share REAL
                    NOT NULL DEFAULT 0,

                entertainment_share REAL
                    NOT NULL DEFAULT 0,

                other_share REAL
                    NOT NULL DEFAULT 0,

                sports_specialty TEXT,
                market_type_specialty TEXT,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                estimated_roi REAL
                    NOT NULL DEFAULT 0,

                estimated_profit REAL
                    NOT NULL DEFAULT 0,

                performance_score REAL
                    NOT NULL DEFAULT 50,

                performance_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                calibration_score REAL
                    NOT NULL DEFAULT 0,

                consistency_score REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 50,

                overlap_risk_score REAL
                    NOT NULL DEFAULT 50,

                traits_json TEXT,
                specialties_json TEXT,
                risks_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_dna_profiles_rank
            ON wallet_dna_profiles(
                dna_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_dna_profiles_archetype
            ON wallet_dna_profiles(
                primary_archetype,
                dna_score DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_dna_categories (
                category_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,
                category TEXT NOT NULL,

                position_count INTEGER
                    NOT NULL DEFAULT 0,

                market_count INTEGER
                    NOT NULL DEFAULT 0,

                current_value REAL
                    NOT NULL DEFAULT 0,

                portfolio_share REAL
                    NOT NULL DEFAULT 0,

                specialty_score REAL
                    NOT NULL DEFAULT 0,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    wallet
                )
                REFERENCES wallet_dna_profiles(
                    wallet
                )
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_dna_categories_wallet
            ON wallet_dna_categories(
                wallet,
                portfolio_share DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_dna_market_types (
                market_type_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,
                market_type TEXT NOT NULL,

                position_count INTEGER
                    NOT NULL DEFAULT 0,

                current_value REAL
                    NOT NULL DEFAULT 0,

                portfolio_share REAL
                    NOT NULL DEFAULT 0,

                specialty_score REAL
                    NOT NULL DEFAULT 0,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    wallet
                )
                REFERENCES wallet_dna_profiles(
                    wallet
                )
                ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS wallet_dna_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,

                dna_score REAL,
                dna_grade TEXT,
                data_confidence TEXT,

                primary_archetype TEXT,
                secondary_archetype TEXT,

                primary_category TEXT,
                primary_category_share REAL,

                current_value REAL,
                concentration_score REAL,
                diversification_score REAL,
                conviction_score REAL,
                performance_score REAL,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_wallet_dna_history_wallet
            ON wallet_dna_history(
                wallet,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS wallet_dna_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                latest_positions_loaded INTEGER
                    NOT NULL DEFAULT 0,

                wallets_analyzed INTEGER
                    NOT NULL DEFAULT 0,

                profiles_saved INTEGER
                    NOT NULL DEFAULT 0,

                category_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                market_type_rows_saved INTEGER
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
# SOURCE LOADING
# =============================================================================


def load_latest_positions() -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        require_tables(
            connection,
            [
                "wallet_scans",
                "positions",
            ],
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
            normalize_wallet(
                row["wallet"]
            ): dict(row)
            for row in rows
        }

    finally:
        connection.close()


def load_wallet_profiles() -> dict[
    str,
    dict[str, Any],
]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "wallet_profiles",
        ):
            return {}

        columns = table_columns(
            connection,
            "wallet_profiles",
        )

        if "wallet" not in columns:
            return {}

        rows = connection.execute(
            """
            SELECT *
            FROM wallet_profiles
            """
        ).fetchall()

        return {
            normalize_wallet(
                row["wallet"]
            ): dict(row)
            for row in rows
        }

    finally:
        connection.close()


def load_overlap_independence() -> dict[str, float]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "portfolio_overlap",
        ):
            return {}

        columns = table_columns(
            connection,
            "portfolio_overlap",
        )

        wallet_columns = [
            name
            for name in (
                "wallet",
                "wallet_a",
                "wallet_b",
                "wallet_1",
                "wallet_2",
            )
            if name in columns
        ]

        overlap_column = next(
            (
                name
                for name in (
                    "overlap_score",
                    "overlap_ratio",
                    "similarity_score",
                    "portfolio_overlap",
                )
                if name in columns
            ),
            None,
        )

        if (
            not wallet_columns
            or overlap_column is None
        ):
            return {}

        selected = ", ".join(
            [
                *wallet_columns,
                overlap_column,
            ]
        )

        rows = connection.execute(
            f"""
            SELECT {selected}
            FROM portfolio_overlap
            """
        ).fetchall()

    finally:
        connection.close()

    overlap_values: dict[
        str,
        list[float],
    ] = defaultdict(list)

    for row in rows:
        overlap = safe_float(
            row[overlap_column]
        )

        if overlap <= 1.0:
            overlap *= 100.0

        overlap = clamp(overlap)

        for wallet_column in wallet_columns:
            wallet = normalize_wallet(
                row[wallet_column]
            )

            if wallet:
                overlap_values[
                    wallet
                ].append(overlap)

    return {
        wallet: (
            100.0
            - (
                sum(values)
                / len(values)
            )
        )
        for wallet, values
        in overlap_values.items()
        if values
    }


# =============================================================================
# CLASSIFICATION HELPERS
# =============================================================================


SPORT_KEYWORDS = {
    "SOCCER": {
        "world cup",
        "uefa",
        "soccer",
        "football",
        "premier league",
        "champions league",
        "fc ",
        " vs ",
        "team to advance",
        "total corners",
        "btts",
    },
    "BASEBALL": {
        "mlb",
        "baseball",
        "yankees",
        "red sox",
        "cardinals",
        "diamondbacks",
        "rays",
    },
    "TENNIS": {
        "tennis",
        "wimbledon",
        "open:",
        "atp",
        "wta",
        "itf",
    },
    "BASKETBALL": {
        "nba",
        "wnba",
        "basketball",
    },
    "MMA": {
        "ufc",
        "mma",
    },
    "ESPORTS": {
        "esports",
        "lol:",
        "dota",
        "counter-strike",
        "valorant",
    },
}


def infer_category(
    title: str,
) -> str:
    normalized = normalize_text(
        title
    )

    politics_keywords = (
        "president",
        "presidential",
        "republican",
        "democratic",
        "election",
        "prime minister",
        "senate",
        "congress",
        "governor",
        "nato",
        "ukraine",
        "macron",
        "trump",
    )

    crypto_keywords = (
        "bitcoin",
        "ethereum",
        "crypto",
        "solana",
        "btc",
        "eth ",
        "all time high",
    )

    entertainment_keywords = (
        "ballon d'or",
        "oscar",
        "emmy",
        "grammy",
        "movie",
        "album",
        "celebrity",
    )

    if any(
        keyword in normalized
        for keyword in politics_keywords
    ):
        return "POLITICS"

    if any(
        keyword in normalized
        for keyword in crypto_keywords
    ):
        return "CRYPTO"

    for keywords in SPORT_KEYWORDS.values():
        if any(
            keyword in normalized
            for keyword in keywords
        ):
            return "SPORTS"

    if any(
        keyword in normalized
        for keyword in entertainment_keywords
    ):
        return "ENTERTAINMENT"

    return "OTHER"


def infer_sport(
    title: str,
) -> str:
    normalized = normalize_text(
        title
    )

    best_sport = ""
    best_matches = 0

    for sport, keywords in (
        SPORT_KEYWORDS.items()
    ):
        matches = sum(
            1
            for keyword in keywords
            if keyword in normalized
        )

        if matches > best_matches:
            best_matches = matches
            best_sport = sport

    return best_sport


def infer_market_type(
    title: str,
) -> str:
    normalized = normalize_text(
        title
    )

    if "exact score" in normalized:
        return "EXACT SCORE"

    if "total corners" in normalized:
        return "CORNERS TOTAL"

    if (
        "o/u" in normalized
        or re.search(
            r"\bover\b|\bunder\b",
            normalized,
        )
    ):
        return "TOTAL"

    if "both teams to score" in normalized:
        return "BTTS"

    if "spread:" in normalized:
        return "SPREAD"

    if "team to advance" in normalized:
        return "TO ADVANCE"

    if re.search(
        r"\d+\+\s*(goals|shots|assists|fouls)",
        normalized,
    ):
        return "PLAYER PROP"

    if (
        normalized.startswith("will ")
        and " win " in normalized
    ):
        return "MONEYLINE / WINNER"

    if " vs " in normalized:
        return "MATCH WINNER"

    return "OTHER"


def grade_from_score(
    score: float,
    position_count: int,
) -> str:
    if position_count < 3:
        return "UNRATED"

    if score >= 90:
        return "S+"

    if score >= 82:
        return "S"

    if score >= 74:
        return "A+"

    if score >= 66:
        return "A"

    if score >= 58:
        return "B"

    if score >= 48:
        return "C"

    return "PASS"


def confidence_from_positions(
    position_count: int,
    resolved_positions: int,
) -> str:
    effective_sample = (
        position_count
        + resolved_positions * 3
    )

    if effective_sample >= 100:
        return "VERY HIGH"

    if effective_sample >= 50:
        return "HIGH"

    if effective_sample >= 20:
        return "MEDIUM"

    if effective_sample >= 8:
        return "LOW"

    return "VERY LOW"


# =============================================================================
# DNA CALCULATION
# =============================================================================


def build_dna_profiles() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
]:
    positions = load_latest_positions()
    performance_lookup = (
        load_wallet_performance()
    )
    profile_lookup = (
        load_wallet_profiles()
    )
    independence_lookup = (
        load_overlap_independence()
    )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for position in positions:
        wallet = normalize_wallet(
            position.get("wallet")
        )

        if wallet:
            grouped[wallet].append(
                position
            )

    calculated_at = utc_now_iso()

    profile_rows: list[
        dict[str, Any]
    ] = []

    category_rows: list[
        dict[str, Any]
    ] = []

    market_type_rows: list[
        dict[str, Any]
    ] = []

    for wallet, wallet_positions in (
        grouped.items()
    ):
        values = [
            max(
                safe_float(
                    position.get(
                        "current_value"
                    )
                ),
                0.0,
            )
            for position in wallet_positions
        ]

        total_value = sum(values)
        position_count = len(
            wallet_positions
        )

        market_ids = {
            clean_text(
                position.get(
                    "market_id"
                )
            ).lower()
            for position in wallet_positions
            if clean_text(
                position.get(
                    "market_id"
                )
            )
        }

        market_count = len(
            market_ids
        )

        average_position_value = (
            safe_divide(
                total_value,
                position_count,
                0.0,
            )
        )

        largest_position_value = (
            max(values)
            if values
            else 0.0
        )

        sorted_values = sorted(
            values,
            reverse=True,
        )

        largest_position_share = (
            safe_divide(
                largest_position_value,
                total_value,
                0.0,
            )
        )

        top_three_concentration = (
            safe_divide(
                sum(
                    sorted_values[:3]
                ),
                total_value,
                0.0,
            )
        )

        portfolio_shares = [
            safe_divide(
                value,
                total_value,
                0.0,
            )
            for value in values
            if total_value > 0
        ]

        herfindahl_index = sum(
            share ** 2
            for share in portfolio_shares
        )

        effective_market_count = (
            safe_divide(
                1.0,
                herfindahl_index,
                0.0,
            )
            if herfindahl_index > 0
            else 0.0
        )

        concentration_score = clamp(
            (
                largest_position_share
                * 0.45
                + top_three_concentration
                * 0.35
                + min(
                    herfindahl_index * 3.0,
                    1.0,
                )
                * 0.20
            )
            * 100.0
        )

        diversification_score = clamp(
            100.0
            - concentration_score
        )

        conviction_score = clamp(
            largest_position_share
            * 55.0
            + top_three_concentration
            * 35.0
            + min(
                average_position_value
                / 50_000.0,
                1.0,
            )
            * 10.0
        )

        whale_score = clamp(
            math.log10(
                max(
                    total_value,
                    1.0,
                )
            )
            / 7.0
            * 100.0
        )

        category_values: dict[
            str,
            float,
        ] = defaultdict(float)

        category_counts: Counter[str] = (
            Counter()
        )

        sport_values: dict[
            str,
            float,
        ] = defaultdict(float)

        market_type_values: dict[
            str,
            float,
        ] = defaultdict(float)

        market_type_counts: Counter[str] = (
            Counter()
        )

        for position, value in zip(
            wallet_positions,
            values,
        ):
            title = clean_text(
                position.get("title")
            )

            category = infer_category(
                title
            )

            sport = infer_sport(
                title
            )

            market_type = (
                infer_market_type(
                    title
                )
            )

            category_values[
                category
            ] += value

            category_counts[
                category
            ] += 1

            if sport:
                sport_values[
                    sport
                ] += value

            market_type_values[
                market_type
            ] += value

            market_type_counts[
                market_type
            ] += 1

        category_shares = {
            category: safe_divide(
                value,
                total_value,
                0.0,
            )
            for category, value
            in category_values.items()
        }

        primary_category = max(
            category_shares,
            key=category_shares.get,
            default="OTHER",
        )

        primary_category_share = (
            category_shares.get(
                primary_category,
                0.0,
            )
        )

        category_diversity = sum(
            1
            for share
            in category_shares.values()
            if share >= 0.05
        )

        specialization_score = clamp(
            primary_category_share
            * 100.0
        )

        sports_specialty = max(
            sport_values,
            key=sport_values.get,
            default="",
        )

        market_type_specialty = max(
            market_type_values,
            key=market_type_values.get,
            default="",
        )

        performance = (
            performance_lookup.get(
                wallet,
                {}
            )
        )

        profile = profile_lookup.get(
            wallet,
            {}
        )

        resolved_positions = safe_int(
            performance.get(
                "resolved_positions"
            )
        )

        win_rate = safe_float(
            performance.get(
                "win_rate"
            )
        )

        estimated_roi = safe_float(
            performance.get(
                "estimated_roi"
            )
        )

        estimated_profit = safe_float(
            performance.get(
                "estimated_profit"
            )
        )

        performance_score = safe_float(
            performance.get(
                "performance_score"
            ),
            50.0,
        )

        performance_grade = (
            clean_text(
                performance.get(
                    "performance_grade"
                )
            )
            or "UNRATED"
        )

        calibration_score = safe_float(
            performance.get(
                "calibration_score"
            )
        )

        consistency_score = safe_float(
            performance.get(
                "consistency_score"
            )
        )

        portfolio_independence_score = (
            independence_lookup.get(
                wallet,
                safe_float(
                    profile.get(
                        "portfolio_independence_score"
                    ),
                    50.0,
                ),
            )
        )

        overlap_risk_score = clamp(
            100.0
            - portfolio_independence_score
        )

        sample_score = clamp(
            math.log1p(
                position_count
            )
            / math.log1p(100)
            * 100.0
        )

        dna_score = clamp(
            specialization_score * 0.20
            + conviction_score * 0.20
            + whale_score * 0.15
            + performance_score * 0.25
            + portfolio_independence_score * 0.10
            + sample_score * 0.10
        )

        dna_grade = grade_from_score(
            dna_score,
            position_count,
        )

        data_confidence = (
            confidence_from_positions(
                position_count,
                resolved_positions,
            )
        )

        traits: list[str] = []
        risks: list[str] = []
        specialties: list[str] = []

        if whale_score >= 80:
            traits.append("WHALE")

        elif whale_score >= 65:
            traits.append(
                "LARGE CAPITAL"
            )

        if conviction_score >= 75:
            traits.append(
                "HIGH CONVICTION"
            )

        elif conviction_score <= 35:
            traits.append(
                "DIVERSIFIED SIZING"
            )

        if specialization_score >= 75:
            traits.append("SPECIALIST")

        elif specialization_score <= 45:
            traits.append("GENERALIST")

        if portfolio_independence_score >= 70:
            traits.append(
                "INDEPENDENT POSITIONING"
            )

        elif portfolio_independence_score <= 35:
            risks.append(
                "HIGH PORTFOLIO OVERLAP"
            )

        if performance_score >= 70:
            traits.append(
                "STRONG OBSERVED PERFORMANCE"
            )

        elif (
            resolved_positions >= 3
            and performance_score < 45
        ):
            risks.append(
                "WEAK OBSERVED PERFORMANCE"
            )

        if primary_category:
            specialties.append(
                primary_category
            )

        if sports_specialty:
            specialties.append(
                sports_specialty
            )

        if market_type_specialty:
            specialties.append(
                market_type_specialty
            )

        if largest_position_share >= 0.60:
            risks.append(
                "SINGLE-POSITION CONCENTRATION"
            )

        if top_three_concentration >= 0.85:
            risks.append(
                "TOP-THREE CONCENTRATION"
            )

        if resolved_positions < 3:
            risks.append(
                "LIMITED RESOLUTION HISTORY"
            )

        if total_value >= 1_000_000:
            capital_label = "INSTITUTIONAL-SCALE"

        elif total_value >= 250_000:
            capital_label = "WHALE"

        elif total_value >= 50_000:
            capital_label = "LARGE TRADER"

        else:
            capital_label = "RETAIL-SCALE"

        if specialization_score >= 75:
            style_label = "SPECIALIST"

        elif diversification_score >= 70:
            style_label = "DIVERSIFIED"

        else:
            style_label = "MIXED"

        primary_archetype = (
            f"{capital_label} "
            f"{primary_category} "
            f"{style_label}"
        )

        if conviction_score >= 75:
            secondary_archetype = (
                "HIGH-CONVICTION "
                "CONCENTRATED TRADER"
            )

        elif diversification_score >= 70:
            secondary_archetype = (
                "BROAD PORTFOLIO TRADER"
            )

        elif portfolio_independence_score >= 70:
            secondary_archetype = (
                "INDEPENDENT SIGNAL WALLET"
            )

        else:
            secondary_archetype = (
                "MIXED-BEHAVIOR WALLET"
            )

        risk_label = (
            "HIGH CONCENTRATION"
            if concentration_score >= 75
            else (
                "MODERATE CONCENTRATION"
                if concentration_score >= 50
                else "LOW CONCENTRATION"
            )
        )

        conviction_label = (
            "HIGH CONVICTION"
            if conviction_score >= 70
            else (
                "MODERATE CONVICTION"
                if conviction_score >= 45
                else "LOW CONVICTION"
            )
        )

        diversification_label = (
            "HIGHLY DIVERSIFIED"
            if diversification_score >= 70
            else (
                "MODERATELY DIVERSIFIED"
                if diversification_score >= 45
                else "CONCENTRATED"
            )
        )

        performance_label = (
            "STRONG"
            if performance_score >= 70
            else (
                "DEVELOPING"
                if performance_score >= 50
                else "WEAK / INCOMPLETE"
            )
        )

        explanation = {
            "model_version": "1.0",
            "method": (
                "LATEST WALLET POSITION SNAPSHOT "
                "PLUS PERFORMANCE AND OVERLAP INPUTS"
            ),
            "score_components": {
                "specialization_score": round(
                    specialization_score,
                    2,
                ),
                "conviction_score": round(
                    conviction_score,
                    2,
                ),
                "whale_score": round(
                    whale_score,
                    2,
                ),
                "performance_score": round(
                    performance_score,
                    2,
                ),
                "portfolio_independence_score": round(
                    portfolio_independence_score,
                    2,
                ),
                "sample_score": round(
                    sample_score,
                    2,
                ),
            },
            "limitations": [
                (
                    "Trading timing cannot be classified "
                    "reliably until a complete activity "
                    "and transaction history is stored."
                ),
                (
                    "Performance inputs remain provisional "
                    "because the realized trade ledger and "
                    "market mapping coverage are incomplete."
                ),
                (
                    "DNA labels describe observed behavior, "
                    "not identity or intent."
                ),
            ],
        }

        profile_rows.append(
            {
                "wallet": wallet,
                "dna_score": dna_score,
                "dna_grade": dna_grade,
                "data_confidence": (
                    data_confidence
                ),
                "primary_archetype": (
                    primary_archetype
                ),
                "secondary_archetype": (
                    secondary_archetype
                ),
                "specialization_label": (
                    f"{primary_category} "
                    f"{style_label}"
                ),
                "risk_label": risk_label,
                "conviction_label": (
                    conviction_label
                ),
                "diversification_label": (
                    diversification_label
                ),
                "performance_label": (
                    performance_label
                ),
                "current_position_count": (
                    position_count
                ),
                "current_market_count": (
                    market_count
                ),
                "current_value": total_value,
                "average_position_value": (
                    average_position_value
                ),
                "largest_position_value": (
                    largest_position_value
                ),
                "largest_position_share": (
                    largest_position_share
                ),
                "top_three_concentration": (
                    top_three_concentration
                ),
                "herfindahl_index": (
                    herfindahl_index
                ),
                "effective_market_count": (
                    effective_market_count
                ),
                "concentration_score": (
                    concentration_score
                ),
                "diversification_score": (
                    diversification_score
                ),
                "conviction_score": (
                    conviction_score
                ),
                "whale_score": whale_score,
                "specialization_score": (
                    specialization_score
                ),
                "category_diversity": (
                    category_diversity
                ),
                "primary_category": (
                    primary_category
                ),
                "primary_category_share": (
                    primary_category_share
                ),
                "sports_share": (
                    category_shares.get(
                        "SPORTS",
                        0.0,
                    )
                ),
                "politics_share": (
                    category_shares.get(
                        "POLITICS",
                        0.0,
                    )
                ),
                "crypto_share": (
                    category_shares.get(
                        "CRYPTO",
                        0.0,
                    )
                ),
                "entertainment_share": (
                    category_shares.get(
                        "ENTERTAINMENT",
                        0.0,
                    )
                ),
                "other_share": (
                    category_shares.get(
                        "OTHER",
                        0.0,
                    )
                ),
                "sports_specialty": (
                    sports_specialty
                ),
                "market_type_specialty": (
                    market_type_specialty
                ),
                "resolved_positions": (
                    resolved_positions
                ),
                "win_rate": win_rate,
                "estimated_roi": (
                    estimated_roi
                ),
                "estimated_profit": (
                    estimated_profit
                ),
                "performance_score": (
                    performance_score
                ),
                "performance_grade": (
                    performance_grade
                ),
                "calibration_score": (
                    calibration_score
                ),
                "consistency_score": (
                    consistency_score
                ),
                "portfolio_independence_score": (
                    portfolio_independence_score
                ),
                "overlap_risk_score": (
                    overlap_risk_score
                ),
                "traits_json": stable_json(
                    traits
                ),
                "specialties_json": (
                    stable_json(
                        specialties
                    )
                ),
                "risks_json": stable_json(
                    risks
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
        )

        for category, value in (
            category_values.items()
        ):
            share = safe_divide(
                value,
                total_value,
                0.0,
            )

            category_rows.append(
                {
                    "category_key": (
                        f"{wallet}:"
                        f"{category}"
                    ),
                    "wallet": wallet,
                    "category": category,
                    "position_count": (
                        category_counts[
                            category
                        ]
                    ),
                    "market_count": (
                        category_counts[
                            category
                        ]
                    ),
                    "current_value": value,
                    "portfolio_share": (
                        share
                    ),
                    "specialty_score": (
                        clamp(
                            share * 100.0
                        )
                    ),
                    "calculated_at": (
                        calculated_at
                    ),
                    "updated_at": (
                        calculated_at
                    ),
                }
            )

        for market_type, value in (
            market_type_values.items()
        ):
            share = safe_divide(
                value,
                total_value,
                0.0,
            )

            market_type_rows.append(
                {
                    "market_type_key": (
                        f"{wallet}:"
                        f"{market_type}"
                    ),
                    "wallet": wallet,
                    "market_type": (
                        market_type
                    ),
                    "position_count": (
                        market_type_counts[
                            market_type
                        ]
                    ),
                    "current_value": value,
                    "portfolio_share": (
                        share
                    ),
                    "specialty_score": (
                        clamp(
                            share * 100.0
                        )
                    ),
                    "calculated_at": (
                        calculated_at
                    ),
                    "updated_at": (
                        calculated_at
                    ),
                }
            )

    profile_rows.sort(
        key=lambda row: (
            row["dna_score"],
            row["current_value"],
            row[
                "current_position_count"
            ],
        ),
        reverse=True,
    )

    return (
        profile_rows,
        category_rows,
        market_type_rows,
        len(positions),
    )


# =============================================================================
# SAVING
# =============================================================================


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


def save_dna_data(
    profiles: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    market_types: list[dict[str, Any]],
) -> tuple[int, int, int, int]:
    connection = connect_database()

    profile_columns = [
        "wallet",
        "dna_score",
        "dna_grade",
        "data_confidence",
        "primary_archetype",
        "secondary_archetype",
        "specialization_label",
        "risk_label",
        "conviction_label",
        "diversification_label",
        "performance_label",
        "current_position_count",
        "current_market_count",
        "current_value",
        "average_position_value",
        "largest_position_value",
        "largest_position_share",
        "top_three_concentration",
        "herfindahl_index",
        "effective_market_count",
        "concentration_score",
        "diversification_score",
        "conviction_score",
        "whale_score",
        "specialization_score",
        "category_diversity",
        "primary_category",
        "primary_category_share",
        "sports_share",
        "politics_share",
        "crypto_share",
        "entertainment_share",
        "other_share",
        "sports_specialty",
        "market_type_specialty",
        "resolved_positions",
        "win_rate",
        "estimated_roi",
        "estimated_profit",
        "performance_score",
        "performance_grade",
        "calibration_score",
        "consistency_score",
        "portfolio_independence_score",
        "overlap_risk_score",
        "traits_json",
        "specialties_json",
        "risks_json",
        "explanation_json",
        "calculated_at",
        "updated_at",
    ]

    category_columns = [
        "category_key",
        "wallet",
        "category",
        "position_count",
        "market_count",
        "current_value",
        "portfolio_share",
        "specialty_score",
        "calculated_at",
        "updated_at",
    ]

    market_type_columns = [
        "market_type_key",
        "wallet",
        "market_type",
        "position_count",
        "current_value",
        "portfolio_share",
        "specialty_score",
        "calculated_at",
        "updated_at",
    ]

    profile_query = build_upsert_query(
        "wallet_dna_profiles",
        profile_columns,
        "wallet",
    )

    category_query = build_upsert_query(
        "wallet_dna_categories",
        category_columns,
        "category_key",
    )

    market_type_query = (
        build_upsert_query(
            "wallet_dna_market_types",
            market_type_columns,
            "market_type_key",
        )
    )

    observed_at = utc_now_iso()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        connection.execute(
            "DELETE FROM wallet_dna_categories"
        )

        connection.execute(
            "DELETE FROM wallet_dna_market_types"
        )

        connection.execute(
            "DELETE FROM wallet_dna_profiles"
        )

        for row in profiles:
            connection.execute(
                profile_query,
                tuple(
                    row[column]
                    for column
                    in profile_columns
                ),
            )

            connection.execute(
                """
                INSERT INTO wallet_dna_history (
                    wallet,
                    dna_score,
                    dna_grade,
                    data_confidence,
                    primary_archetype,
                    secondary_archetype,
                    primary_category,
                    primary_category_share,
                    current_value,
                    concentration_score,
                    diversification_score,
                    conviction_score,
                    performance_score,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    row["wallet"],
                    row["dna_score"],
                    row["dna_grade"],
                    row[
                        "data_confidence"
                    ],
                    row[
                        "primary_archetype"
                    ],
                    row[
                        "secondary_archetype"
                    ],
                    row[
                        "primary_category"
                    ],
                    row[
                        "primary_category_share"
                    ],
                    row["current_value"],
                    row[
                        "concentration_score"
                    ],
                    row[
                        "diversification_score"
                    ],
                    row[
                        "conviction_score"
                    ],
                    row[
                        "performance_score"
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
                    in category_columns
                ),
            )

        for row in market_types:
            connection.execute(
                market_type_query,
                tuple(
                    row[column]
                    for column
                    in market_type_columns
                ),
            )

        connection.commit()

        return (
            len(profiles),
            len(categories),
            len(market_types),
            len(profiles),
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
            INSERT INTO wallet_dna_runs (
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
    latest_positions_loaded: int,
    wallets_analyzed: int,
    profiles_saved: int,
    category_rows_saved: int,
    market_type_rows_saved: int,
    history_rows_saved: int,
    error_message: str = "",
) -> None:
    finished = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE wallet_dna_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                latest_positions_loaded = ?,
                wallets_analyzed = ?,
                profiles_saved = ?,
                category_rows_saved = ?,
                market_type_rows_saved = ?,
                history_rows_saved = ?,
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
                latest_positions_loaded,
                wallets_analyzed,
                profiles_saved,
                category_rows_saved,
                market_type_rows_saved,
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
    profiles: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    market_types: list[dict[str, Any]],
    positions_loaded: int,
    display_limit: int,
) -> None:
    print()
    print("=" * 108)
    print("WALLET DNA ENGINE SUMMARY")
    print("=" * 108)

    print(
        f"Latest positions loaded:        "
        f"{positions_loaded}"
    )

    print(
        f"Wallets analyzed:               "
        f"{len(profiles)}"
    )

    print(
        f"Category rows:                  "
        f"{len(categories)}"
    )

    print(
        f"Market-type rows:               "
        f"{len(market_types)}"
    )

    print(
        f"Rated wallets:                  "
        f"{sum(1 for row in profiles if row['dna_grade'] != 'UNRATED')}"
    )

    print("=" * 108)

    print()
    print("TOP WALLET DNA PROFILES")

    for rank, row in enumerate(
        profiles[:display_limit],
        start=1,
    ):
        traits = json.loads(
            row["traits_json"]
        )

        risks = json.loads(
            row["risks_json"]
        )

        print()
        print("-" * 108)

        print(
            f"{rank}. {row['wallet']}"
        )

        print("-" * 108)

        print(
            f"DNA score / grade:              "
            f"{row['dna_score']:.1f} "
            f"/ {row['dna_grade']}"
        )

        print(
            f"Data confidence:                "
            f"{row['data_confidence']}"
        )

        print(
            f"Primary archetype:              "
            f"{row['primary_archetype']}"
        )

        print(
            f"Secondary archetype:            "
            f"{row['secondary_archetype']}"
        )

        print(
            f"Portfolio value:                "
            f"{format_money(row['current_value'])}"
        )

        print(
            f"Positions / markets:            "
            f"{row['current_position_count']} "
            f"/ {row['current_market_count']}"
        )

        print(
            f"Primary category:               "
            f"{row['primary_category']} "
            f"({format_percentage(row['primary_category_share'])})"
        )

        print(
            f"Sport / market specialty:       "
            f"{row['sports_specialty'] or '-'} "
            f"/ "
            f"{row['market_type_specialty'] or '-'}"
        )

        print(
            f"Conviction / concentration:     "
            f"{row['conviction_score']:.1f} "
            f"/ {row['concentration_score']:.1f}"
        )

        print(
            f"Performance:                    "
            f"{row['performance_score']:.1f} "
            f"/ {row['performance_grade']}"
        )

        if traits:
            print(
                "Traits:                         "
                + ", ".join(traits)
            )

        if risks:
            print(
                "Risks:                          "
                + ", ".join(risks)
            )


# =============================================================================
# ARGUMENTS AND MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify wallet portfolio behavior, "
            "specialization, concentration, conviction "
            "and observed performance into DNA profiles."
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
    print("=" * 108)
    print("POLYMARKET WALLET DNA ENGINE v1")
    print("=" * 108)

    print(
        f"Database: {DATABASE_PATH}"
    )

    print(
        "Method: latest position portfolio plus "
        "performance and overlap intelligence"
    )

    create_dna_tables()

    run_id, started_at = start_run()

    profiles: list[
        dict[str, Any]
    ] = []

    categories: list[
        dict[str, Any]
    ] = []

    market_types: list[
        dict[str, Any]
    ] = []

    positions_loaded = 0
    profiles_saved = 0
    categories_saved = 0
    market_types_saved = 0
    history_saved = 0

    try:
        (
            profiles,
            categories,
            market_types,
            positions_loaded,
        ) = build_dna_profiles()

        (
            profiles_saved,
            categories_saved,
            market_types_saved,
            history_saved,
        ) = save_dna_data(
            profiles=profiles,
            categories=categories,
            market_types=market_types,
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            latest_positions_loaded=(
                positions_loaded
            ),
            wallets_analyzed=(
                len(profiles)
            ),
            profiles_saved=(
                profiles_saved
            ),
            category_rows_saved=(
                categories_saved
            ),
            market_type_rows_saved=(
                market_types_saved
            ),
            history_rows_saved=(
                history_saved
            ),
        )

        display_summary(
            profiles=profiles,
            categories=categories,
            market_types=market_types,
            positions_loaded=(
                positions_loaded
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 108)
        print("WALLET DNA ENGINE COMPLETE")
        print("=" * 108)

        print(
            "Current DNA profiles were saved to "
            "wallet_dna_profiles."
        )

        print(
            "Category specialization was saved to "
            "wallet_dna_categories."
        )

        print(
            "Market-type specialization was saved to "
            "wallet_dna_market_types."
        )

        print(
            "Historical DNA snapshots were saved to "
            "wallet_dna_history."
        )

        print(
            "Timing labels are intentionally excluded until "
            "complete transaction and activity history exists."
        )

        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            latest_positions_loaded=(
                positions_loaded
            ),
            wallets_analyzed=(
                len(profiles)
            ),
            profiles_saved=(
                profiles_saved
            ),
            category_rows_saved=(
                categories_saved
            ),
            market_type_rows_saved=(
                market_types_saved
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