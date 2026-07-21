from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_DISPLAY_LIMIT = 30

ELITE_SCORE_THRESHOLD = 75.0
ELITE_GRADES = {"S+", "S", "A+"}

SYNC_WINDOWS_SECONDS = {
    "10m": 10 * 60,
    "1h": 60 * 60,
    "6h": 6 * 60 * 60,
    "24h": 24 * 60 * 60,
}

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


# =============================================================================
# GENERAL HELPERS
# =============================================================================


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


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
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


def weighted_average(
    pairs: list[tuple[float, float]],
    fallback: float = 0.0,
) -> float:
    numerator = 0.0
    denominator = 0.0

    for value, weight in pairs:
        safe_weight = max(safe_float(weight), 0.0)

        if safe_weight <= 0:
            continue

        numerator += safe_float(value) * safe_weight
        denominator += safe_weight

    if denominator <= 0:
        return fallback

    return numerator / denominator


def format_money(value: Any) -> str:
    return f"${safe_float(value):,.2f}"


def format_price(value: Any) -> str:
    return f"{safe_float(value):.4f}"


def format_percentage(value: Any) -> str:
    return f"{safe_float(value):.1%}"


def format_signed_percentage(value: Any) -> str:
    return f"{safe_float(value):+.1%}"


def format_age(seconds: Any) -> str:
    total = max(safe_int(seconds), 0)

    days, remainder = divmod(total, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds_left = divmod(remainder, 60)

    if days > 0:
        return (
            f"{days}d "
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds_left:02d}"
        )

    return (
        f"{hours:02d}:"
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


def create_institutional_consensus_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS institutional_consensus (
                consensus_key TEXT PRIMARY KEY,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                effective_wallet_count REAL
                    NOT NULL DEFAULT 0,

                independent_wallet_score REAL
                    NOT NULL DEFAULT 0,

                total_current_value REAL
                    NOT NULL DEFAULT 0,

                elite_current_value REAL
                    NOT NULL DEFAULT 0,

                elite_value_share REAL
                    NOT NULL DEFAULT 0,

                average_wallet_quality REAL
                    NOT NULL DEFAULT 0,

                weighted_wallet_quality REAL
                    NOT NULL DEFAULT 0,

                weighted_entry_price REAL,
                weighted_elite_entry_price REAL,

                entry_price_stddev REAL
                    NOT NULL DEFAULT 0,

                entry_price_dispersion_score REAL
                    NOT NULL DEFAULT 0,

                earliest_entry_at TEXT,
                latest_entry_at TEXT,

                entry_span_seconds INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_wallets_10m INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_wallets_1h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_wallets_6h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_wallets_24h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_elite_wallets_10m INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_elite_wallets_1h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_elite_wallets_6h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_elite_wallets_24h INTEGER
                    NOT NULL DEFAULT 0,

                time_sync_score REAL
                    NOT NULL DEFAULT 0,

                opposing_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                opposing_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                opposing_current_value REAL
                    NOT NULL DEFAULT 0,

                market_total_value REAL
                    NOT NULL DEFAULT 0,

                agreement_value_share REAL
                    NOT NULL DEFAULT 0,

                conflict_ratio REAL
                    NOT NULL DEFAULT 0,

                opposing_conflict_score REAL
                    NOT NULL DEFAULT 0,

                overlap_pair_coverage REAL
                    NOT NULL DEFAULT 0,

                average_pair_overlap REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 0,

                capital_score REAL
                    NOT NULL DEFAULT 0,

                wallet_quality_score REAL
                    NOT NULL DEFAULT 0,

                agreement_score REAL
                    NOT NULL DEFAULT 0,

                freshness_score REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                confidence_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                signal_status TEXT
                    NOT NULL DEFAULT 'PASS',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                wallets_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_institutional_consensus_rank
            ON institutional_consensus(
                consensus_strength DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_institutional_consensus_grade
            ON institutional_consensus(
                confidence_grade,
                consensus_strength DESC
            );

            CREATE TABLE IF NOT EXISTS institutional_consensus_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                consensus_key TEXT NOT NULL,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                wallet_count INTEGER,
                elite_wallet_count INTEGER,

                effective_wallet_count REAL,
                independent_wallet_score REAL,

                total_current_value REAL,
                elite_current_value REAL,
                elite_value_share REAL,

                average_wallet_quality REAL,
                weighted_wallet_quality REAL,

                weighted_entry_price REAL,
                weighted_elite_entry_price REAL,

                entry_price_stddev REAL,
                entry_price_dispersion_score REAL,

                earliest_entry_at TEXT,
                latest_entry_at TEXT,
                entry_span_seconds INTEGER,

                synchronized_wallets_10m INTEGER,
                synchronized_wallets_1h INTEGER,
                synchronized_wallets_6h INTEGER,
                synchronized_wallets_24h INTEGER,

                synchronized_elite_wallets_10m INTEGER,
                synchronized_elite_wallets_1h INTEGER,
                synchronized_elite_wallets_6h INTEGER,
                synchronized_elite_wallets_24h INTEGER,

                time_sync_score REAL,

                opposing_wallet_count INTEGER,
                opposing_elite_wallet_count INTEGER,
                opposing_current_value REAL,

                market_total_value REAL,
                agreement_value_share REAL,
                conflict_ratio REAL,
                opposing_conflict_score REAL,

                overlap_pair_coverage REAL,
                average_pair_overlap REAL,
                portfolio_independence_score REAL,

                capital_score REAL,
                wallet_quality_score REAL,
                agreement_score REAL,
                freshness_score REAL,

                consensus_strength REAL,
                confidence_grade TEXT,
                signal_status TEXT,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                data_completeness_score REAL,
                data_confidence TEXT,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_institutional_consensus_history_key
            ON institutional_consensus_history(
                consensus_key,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS institutional_consensus_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                active_groups_seen INTEGER
                    NOT NULL DEFAULT 0,

                consensus_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_created INTEGER
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
# SOURCE DATA
# =============================================================================


def wallet_quality_score(
    profile: dict[str, Any],
) -> float:
    return clamp(
        safe_float(profile.get("wallet_score")) * 0.45
        + safe_float(profile.get("dna_score")) * 0.25
        + safe_float(profile.get("leader_score")) * 0.20
        + safe_float(profile.get("activity_score")) * 0.10
    )


def wallet_is_elite(
    profile: dict[str, Any],
) -> bool:
    quality = wallet_quality_score(profile)

    wallet_grade = clean_text(
        profile.get("wallet_grade")
    ).upper()

    dna_grade = clean_text(
        profile.get("dna_grade")
    ).upper()

    return (
        quality >= ELITE_SCORE_THRESHOLD
        or wallet_grade in ELITE_GRADES
        or dna_grade in ELITE_GRADES
    )


def load_wallet_profiles() -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        rows = connection.execute(
            "SELECT * FROM wallet_profiles"
        ).fetchall()

        return {
            normalize_wallet(row["wallet"]): dict(row)
            for row in rows
            if normalize_wallet(row["wallet"])
        }

    finally:
        connection.close()


def load_current_positions(
    profiles: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            WITH latest_scans AS (
                SELECT
                    wallet,
                    MAX(id) AS latest_scan_id
                FROM wallet_scans
                GROUP BY wallet
            )
            SELECT
                positions.*
            FROM positions
            INNER JOIN latest_scans
                ON positions.wallet =
                   latest_scans.wallet
               AND positions.scan_id =
                   latest_scans.latest_scan_id
            WHERE positions.market_id
                  IS NOT NULL
              AND TRIM(
                    positions.market_id
                  ) != ''
            """
        ).fetchall()

    finally:
        connection.close()

    output: list[dict[str, Any]] = []

    for row in rows:
        wallet = normalize_wallet(row["wallet"])

        profile = profiles.get(wallet)

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


def load_first_observed_entries() -> dict[
    tuple[str, str, str],
    dict[str, Any],
]:
    """
    Reconstruct each wallet's first observed position in each market/outcome.

    The first observation is an approximation of entry timing, not an
    on-chain trade timestamp.
    """

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            WITH ranked AS (
                SELECT
                    positions.wallet,
                    positions.market_id,
                    positions.outcome,
                    positions.average_price,
                    positions.current_value,
                    positions.shares,
                    positions.scan_id,
                    wallet_scans.scanned_at,

                    ROW_NUMBER() OVER (
                        PARTITION BY
                            LOWER(positions.wallet),
                            LOWER(positions.market_id),
                            LOWER(TRIM(positions.outcome))
                        ORDER BY
                            wallet_scans.scanned_at ASC,
                            positions.id ASC
                    ) AS row_number
                FROM positions
                INNER JOIN wallet_scans
                    ON positions.scan_id =
                       wallet_scans.id
                WHERE positions.market_id
                      IS NOT NULL
                  AND TRIM(
                        positions.market_id
                      ) != ''
            )
            SELECT *
            FROM ranked
            WHERE row_number = 1
            """
        ).fetchall()

        return {
            (
                normalize_wallet(row["wallet"]),
                normalize_market_id(row["market_id"]),
                normalize_text(row["outcome"]),
            ): dict(row)
            for row in rows
        }

    finally:
        connection.close()


def load_overlap_lookup() -> dict[
    tuple[str, str],
    dict[str, Any],
]:
    connection = connect_database()

    try:
        if not table_exists(connection, "portfolio_overlap"):
            return {}

        rows = connection.execute(
            "SELECT * FROM portfolio_overlap"
        ).fetchall()

    finally:
        connection.close()

    lookup: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for row in rows:
        wallet_a = normalize_wallet(row["wallet_a"])
        wallet_b = normalize_wallet(row["wallet_b"])

        if not wallet_a or not wallet_b:
            continue

        lookup[
            tuple(sorted((wallet_a, wallet_b)))
        ] = dict(row)

    return lookup


def load_market_metadata() -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        rows = connection.execute(
            "SELECT * FROM market_metadata"
        ).fetchall()

        return {
            normalize_market_id(row["market_id"]): dict(row)
            for row in rows
            if normalize_market_id(row["market_id"])
        }

    finally:
        connection.close()


# =============================================================================
# CONSENSUS CALCULATIONS
# =============================================================================


def group_current_positions(
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
        grouped[
            (
                position["market_id"],
                normalize_text(position["outcome"]),
            )
        ].append(position)

    return dict(grouped)


def group_market_outcomes(
    grouped: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ],
) -> dict[
    str,
    list[
        tuple[
            tuple[str, str],
            list[dict[str, Any]],
        ]
    ],
]:
    market_groups: dict[
        str,
        list[
            tuple[
                tuple[str, str],
                list[dict[str, Any]],
            ]
        ],
    ] = defaultdict(list)

    for key, group in grouped.items():
        market_groups[key[0]].append((key, group))

    return dict(market_groups)


def calculate_overlap_metrics(
    wallets: list[str],
    overlap_lookup: dict[
        tuple[str, str],
        dict[str, Any],
    ],
) -> dict[str, float]:
    unique_wallets = sorted(set(wallets))

    possible_pairs = (
        len(unique_wallets)
        * (len(unique_wallets) - 1)
        // 2
    )

    if possible_pairs <= 0:
        return {
            "average_pair_overlap": 0.0,
            "overlap_pair_coverage": 0.0,
            "portfolio_independence_score": 70.0,
            "effective_wallet_count": float(len(unique_wallets)),
            "independent_wallet_score": 45.0,
        }

    overlaps: list[float] = []

    for index, wallet_a in enumerate(unique_wallets):
        for wallet_b in unique_wallets[index + 1 :]:
            row = overlap_lookup.get(
                tuple(sorted((wallet_a, wallet_b)))
            )

            if row is None:
                continue

            weighted_overlap = normalize_ratio(
                row.get("weighted_overlap_score")
            )

            jaccard = normalize_ratio(
                row.get("jaccard_similarity")
            )

            overlap = (
                weighted_overlap
                if weighted_overlap > 0
                else jaccard
            )

            overlaps.append(
                clamp(overlap, 0.0, 1.0)
            )

    coverage = len(overlaps) / possible_pairs

    average_overlap = (
        mean(overlaps)
        if overlaps
        else 0.0
    )

    independence = clamp(
        (1.0 - average_overlap) * 100.0
    )

    multiplier = clamp(
        1.0 - average_overlap * 0.60,
        0.35,
        1.0,
    )

    effective_wallet_count = (
        len(unique_wallets) * multiplier
    )

    independent_wallet_score = clamp(
        min(effective_wallet_count / 6.0, 1.0) * 70.0
        + independence * 0.30
    )

    return {
        "average_pair_overlap": average_overlap,
        "overlap_pair_coverage": coverage,
        "portfolio_independence_score": independence,
        "effective_wallet_count": effective_wallet_count,
        "independent_wallet_score": independent_wallet_score,
    }


def largest_synchronized_cluster(
    times: list[datetime],
    window_seconds: int,
) -> int:
    if not times:
        return 0

    ordered = sorted(times)

    best = 1
    left = 0

    for right in range(len(ordered)):
        while (
            ordered[right] - ordered[left]
        ).total_seconds() > window_seconds:
            left += 1

        best = max(best, right - left + 1)

    return best


def calculate_time_sync_metrics(
    entry_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    all_times: list[datetime] = []
    elite_times: list[datetime] = []

    for row in entry_rows:
        entered_at = parse_datetime(row["first_seen_at"])

        if entered_at is None:
            continue

        all_times.append(entered_at)

        if row["elite"]:
            elite_times.append(entered_at)

    earliest = min(all_times) if all_times else None
    latest = max(all_times) if all_times else None

    span_seconds = (
        int((latest - earliest).total_seconds())
        if earliest and latest
        else 0
    )

    all_clusters = {
        label: largest_synchronized_cluster(
            all_times,
            seconds,
        )
        for label, seconds
        in SYNC_WINDOWS_SECONDS.items()
    }

    elite_clusters = {
        label: largest_synchronized_cluster(
            elite_times,
            seconds,
        )
        for label, seconds
        in SYNC_WINDOWS_SECONDS.items()
    }

    wallet_count = len(entry_rows)

    elite_count = sum(
        1
        for row in entry_rows
        if row["elite"]
    )

    all_ratio_10m = (
        all_clusters["10m"] / wallet_count
        if wallet_count > 0
        else 0.0
    )

    all_ratio_1h = (
        all_clusters["1h"] / wallet_count
        if wallet_count > 0
        else 0.0
    )

    all_ratio_6h = (
        all_clusters["6h"] / wallet_count
        if wallet_count > 0
        else 0.0
    )

    all_ratio_24h = (
        all_clusters["24h"] / wallet_count
        if wallet_count > 0
        else 0.0
    )

    elite_ratio_1h = (
        elite_clusters["1h"] / elite_count
        if elite_count > 0
        else 0.0
    )

    elite_ratio_6h = (
        elite_clusters["6h"] / elite_count
        if elite_count > 0
        else 0.0
    )

    time_sync_score = clamp(
        all_ratio_10m * 25.0
        + all_ratio_1h * 25.0
        + all_ratio_6h * 20.0
        + all_ratio_24h * 10.0
        + elite_ratio_1h * 10.0
        + elite_ratio_6h * 10.0
    )

    return {
        "earliest_entry_at": (
            earliest.isoformat()
            if earliest
            else ""
        ),
        "latest_entry_at": (
            latest.isoformat()
            if latest
            else ""
        ),
        "entry_span_seconds": span_seconds,

        "synchronized_wallets_10m": all_clusters["10m"],
        "synchronized_wallets_1h": all_clusters["1h"],
        "synchronized_wallets_6h": all_clusters["6h"],
        "synchronized_wallets_24h": all_clusters["24h"],

        "synchronized_elite_wallets_10m": (
            elite_clusters["10m"]
        ),
        "synchronized_elite_wallets_1h": (
            elite_clusters["1h"]
        ),
        "synchronized_elite_wallets_6h": (
            elite_clusters["6h"]
        ),
        "synchronized_elite_wallets_24h": (
            elite_clusters["24h"]
        ),

        "time_sync_score": time_sync_score,
    }


def calculate_price_dispersion(
    entry_rows: list[dict[str, Any]],
) -> dict[str, float]:
    prices = [
        safe_float(row["entry_price"])
        for row in entry_rows
        if 0 <= safe_float(row["entry_price"]) <= 1
    ]

    if not prices:
        return {
            "entry_price_stddev": 0.0,
            "entry_price_dispersion_score": 0.0,
        }

    standard_deviation = (
        pstdev(prices)
        if len(prices) >= 2
        else 0.0
    )

    average_price = mean(prices)

    relative_dispersion = (
        standard_deviation / average_price
        if average_price > 0
        else 0.0
    )

    dispersion_score = clamp(
        100.0
        - relative_dispersion / 0.35 * 100.0
    )

    return {
        "entry_price_stddev": standard_deviation,
        "entry_price_dispersion_score": dispersion_score,
    }


def capital_score(current_value: float) -> float:
    if current_value <= 0:
        return 0.0

    lower = 1_000.0
    upper = 3_000_000.0

    if current_value <= lower:
        return clamp(current_value / lower * 15.0)

    return clamp(
        15.0
        + math.log10(current_value / lower)
        / math.log10(upper / lower)
        * 85.0
    )


def freshness_score(
    earliest_entry_at: str,
    latest_entry_at: str,
) -> float:
    latest = parse_datetime(latest_entry_at)

    if latest is None:
        return 25.0

    age_hours = max(
        (utc_now() - latest).total_seconds()
        / 3_600.0,
        0.0,
    )

    if age_hours <= 1:
        return 100.0

    if age_hours <= 6:
        return 92.0

    if age_hours <= 24:
        return 82.0

    if age_hours <= 72:
        return 68.0

    if age_hours <= 168:
        return 55.0

    if age_hours <= 720:
        return 40.0

    earliest = parse_datetime(earliest_entry_at)

    if earliest is None:
        return 25.0

    total_age_days = max(
        (utc_now() - earliest).total_seconds()
        / 86_400.0,
        0.0,
    )

    if total_age_days >= 180:
        return 18.0

    return 28.0


def classify_grade(score: float) -> str:
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


def classify_signal_status(
    grade: str,
    time_sync_score: float,
    freshness: float,
    conflict_ratio: float,
    elite_wallet_count: int,
    wallet_count: int,
    lifecycle_status: str,
) -> str:
    lifecycle = normalize_text(lifecycle_status)

    if lifecycle in INACTIVE_STATUSES:
        return "INACTIVE"

    if lifecycle in LIVE_STATUSES:
        return "LIVE CONSENSUS"

    if conflict_ratio >= 0.45:
        return "MIXED"

    if freshness < 35:
        if grade in {"S+", "S", "A+"}:
            return "STALE CONSENSUS"

        return "PASS"

    if (
        time_sync_score >= 75
        and elite_wallet_count >= 2
    ):
        return "COORDINATED ENTRY"

    if (
        time_sync_score >= 55
        and wallet_count >= 3
    ):
        return "SYNCHRONIZED ACCUMULATION"

    if grade in {"S+", "S", "A+"}:
        return "ACCUMULATING"

    if grade in {"A", "B"}:
        return "WATCH"

    return "PASS"


def data_completeness(
    wallet_count: int,
    profile_count: int,
    entry_time_count: int,
    overlap_coverage: float,
    metadata: dict[str, Any] | None,
) -> tuple[float, str]:
    score = 0.0

    if wallet_count > 0:
        score += clamp(
            profile_count / wallet_count * 30.0,
            0.0,
            30.0,
        )

        score += clamp(
            entry_time_count / wallet_count * 30.0,
            0.0,
            30.0,
        )

    score += clamp(
        overlap_coverage * 20.0,
        0.0,
        20.0,
    )

    if metadata is not None:
        score += 15.0

        if metadata.get("game_start_time"):
            score += 5.0

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


def build_consensus_records() -> list[dict[str, Any]]:
    profiles = load_wallet_profiles()
    current_positions = load_current_positions(profiles)
    first_entries = load_first_observed_entries()
    overlap_lookup = load_overlap_lookup()
    metadata_lookup = load_market_metadata()

    grouped = group_current_positions(current_positions)
    market_groups = group_market_outcomes(grouped)

    calculated_at = utc_now_iso()

    records: list[dict[str, Any]] = []

    for (
        market_id,
        normalized_outcome,
    ), group in grouped.items():
        wallet_rows: dict[str, dict[str, Any]] = {}

        for position in group:
            wallet = position["wallet"]

            prior = wallet_rows.get(wallet)

            if (
                prior is None
                or safe_float(
                    position.get("current_value")
                )
                > safe_float(
                    prior.get("current_value")
                )
            ):
                wallet_rows[wallet] = position

        unique_positions = list(wallet_rows.values())

        if not unique_positions:
            continue

        total_value = sum(
            max(
                safe_float(item.get("current_value")),
                0.0,
            )
            for item in unique_positions
        )

        if total_value <= 0:
            continue

        title = clean_text(unique_positions[0]["title"])
        outcome = clean_text(unique_positions[0]["outcome"])

        wallets = [
            item["wallet"]
            for item in unique_positions
        ]

        elite_wallet_count = 0
        elite_current_value = 0.0
        profile_count = 0
        entry_time_count = 0

        quality_values: list[float] = []
        quality_pairs: list[tuple[float, float]] = []

        entry_pairs: list[tuple[float, float]] = []
        elite_entry_pairs: list[tuple[float, float]] = []

        entry_rows: list[dict[str, Any]] = []
        wallet_payload: list[dict[str, Any]] = []

        for position in unique_positions:
            wallet = position["wallet"]
            profile = position["profile"]

            profile_count += 1

            current_value = max(
                safe_float(position.get("current_value")),
                0.0,
            )

            shares = max(
                safe_float(position.get("shares")),
                0.0,
            )

            weight = max(current_value, shares, 1.0)

            quality = wallet_quality_score(profile)

            elite = wallet_is_elite(profile)

            if elite:
                elite_wallet_count += 1
                elite_current_value += current_value

            quality_values.append(quality)
            quality_pairs.append((quality, current_value))

            first_entry = first_entries.get(
                (
                    wallet,
                    market_id,
                    normalized_outcome,
                )
            )

            entry_price = safe_float(
                (
                    first_entry.get("average_price")
                    if first_entry
                    else position.get("average_price")
                )
            )

            first_seen_at = clean_text(
                (
                    first_entry.get("scanned_at")
                    if first_entry
                    else ""
                )
            )

            if first_seen_at:
                entry_time_count += 1

            entry_pairs.append((entry_price, weight))

            if elite:
                elite_entry_pairs.append((entry_price, weight))

            entry_rows.append(
                {
                    "wallet": wallet,
                    "entry_price": entry_price,
                    "first_seen_at": first_seen_at,
                    "elite": elite,
                }
            )

            wallet_payload.append(
                {
                    "wallet": wallet,
                    "current_value": round(current_value, 2),
                    "entry_price": round(entry_price, 6),
                    "first_seen_at": first_seen_at,
                    "elite": elite,
                    "wallet_quality": round(quality, 2),
                    "wallet_grade": clean_text(
                        profile.get("wallet_grade")
                    ),
                    "dna_grade": clean_text(
                        profile.get("dna_grade")
                    ),
                }
            )

        weighted_entry = weighted_average(
            entry_pairs,
            fallback=mean(
                price
                for price, _ in entry_pairs
            ),
        )

        weighted_elite_entry = (
            weighted_average(elite_entry_pairs)
            if elite_entry_pairs
            else None
        )

        average_quality = mean(quality_values)

        weighted_quality = weighted_average(
            quality_pairs,
            fallback=average_quality,
        )

        overlap = calculate_overlap_metrics(
            wallets,
            overlap_lookup,
        )

        sync = calculate_time_sync_metrics(
            entry_rows
        )

        dispersion = calculate_price_dispersion(
            entry_rows
        )

        market_total_value = 0.0
        opposing_current_value = 0.0
        opposing_wallets: set[str] = set()
        opposing_elite_wallets: set[str] = set()

        for other_key, other_group in market_groups.get(
            market_id,
            [],
        ):
            group_value = sum(
                max(
                    safe_float(item.get("current_value")),
                    0.0,
                )
                for item in other_group
            )

            market_total_value += group_value

            if other_key[1] == normalized_outcome:
                continue

            opposing_current_value += group_value

            for item in other_group:
                opposing_wallets.add(item["wallet"])

                if wallet_is_elite(item["profile"]):
                    opposing_elite_wallets.add(
                        item["wallet"]
                    )

        agreement_value_share = (
            total_value / market_total_value
            if market_total_value > 0
            else 1.0
        )

        conflict_ratio = (
            opposing_current_value
            / market_total_value
            if market_total_value > 0
            else 0.0
        )

        opposing_conflict_score = clamp(
            (1.0 - conflict_ratio) * 100.0
        )

        elite_value_share = (
            elite_current_value / total_value
            if total_value > 0
            else 0.0
        )

        wallet_quality_component = clamp(
            weighted_quality * 0.70
            + average_quality * 0.30
        )

        agreement_score = clamp(
            agreement_value_share * 55.0
            + min(
                overlap["effective_wallet_count"] / 6.0,
                1.0,
            )
            * 25.0
            + min(
                elite_wallet_count / 3.0,
                1.0,
            )
            * 20.0
        )

        capital_component = capital_score(
            total_value
        )

        freshness_component = freshness_score(
            sync["earliest_entry_at"],
            sync["latest_entry_at"],
        )

        consensus_strength = clamp(
            wallet_quality_component * 0.22
            + agreement_score * 0.20
            + sync["time_sync_score"] * 0.18
            + overlap["independent_wallet_score"] * 0.14
            + dispersion["entry_price_dispersion_score"] * 0.08
            + capital_component * 0.10
            + freshness_component * 0.08
            - conflict_ratio * 18.0
        )

        grade = classify_grade(
            consensus_strength
        )

        metadata = metadata_lookup.get(
            market_id
        )

        lifecycle_status = clean_text(
            (
                metadata.get("lifecycle_status")
                if metadata
                else ""
            )
        ) or "UNKNOWN"

        seconds_value = (
            metadata.get("seconds_to_start")
            if metadata
            else None
        )

        seconds_to_start = (
            safe_int(seconds_value)
            if seconds_value is not None
            else None
        )

        signal_status = classify_signal_status(
            grade=grade,
            time_sync_score=sync["time_sync_score"],
            freshness=freshness_component,
            conflict_ratio=conflict_ratio,
            elite_wallet_count=elite_wallet_count,
            wallet_count=len(wallets),
            lifecycle_status=lifecycle_status,
        )

        completeness, confidence = data_completeness(
            wallet_count=len(wallets),
            profile_count=profile_count,
            entry_time_count=entry_time_count,
            overlap_coverage=overlap["overlap_pair_coverage"],
            metadata=metadata,
        )

        consensus_key = (
            f"{market_id}:{normalized_outcome}"
        )

        explanation = {
            "model_version": "1.0",
            "entry_timing_source": (
                "FIRST_OBSERVED_POSITION_SCAN"
            ),
            "score_components": {
                "wallet_quality": round(
                    wallet_quality_component,
                    2,
                ),
                "agreement": round(
                    agreement_score,
                    2,
                ),
                "time_sync": round(
                    sync["time_sync_score"],
                    2,
                ),
                "independence": round(
                    overlap["independent_wallet_score"],
                    2,
                ),
                "price_dispersion": round(
                    dispersion[
                        "entry_price_dispersion_score"
                    ],
                    2,
                ),
                "capital": round(
                    capital_component,
                    2,
                ),
                "freshness": round(
                    freshness_component,
                    2,
                ),
            },
            "limitations": [
                (
                    "Entry times are first observed scans, "
                    "not exact on-chain trade timestamps."
                ),
                (
                    "Consensus strength is a research score, "
                    "not a calibrated win probability."
                ),
            ],
        }

        records.append(
            {
                "consensus_key": consensus_key,

                "market_id": market_id,
                "title": title,
                "outcome": outcome,

                "wallet_count": len(wallets),
                "elite_wallet_count": elite_wallet_count,

                "effective_wallet_count": (
                    overlap["effective_wallet_count"]
                ),

                "independent_wallet_score": (
                    overlap["independent_wallet_score"]
                ),

                "total_current_value": total_value,
                "elite_current_value": elite_current_value,
                "elite_value_share": elite_value_share,

                "average_wallet_quality": average_quality,
                "weighted_wallet_quality": weighted_quality,

                "weighted_entry_price": weighted_entry,
                "weighted_elite_entry_price": (
                    weighted_elite_entry
                ),

                "entry_price_stddev": (
                    dispersion["entry_price_stddev"]
                ),

                "entry_price_dispersion_score": (
                    dispersion[
                        "entry_price_dispersion_score"
                    ]
                ),

                "earliest_entry_at": (
                    sync["earliest_entry_at"]
                ),

                "latest_entry_at": (
                    sync["latest_entry_at"]
                ),

                "entry_span_seconds": (
                    sync["entry_span_seconds"]
                ),

                "synchronized_wallets_10m": (
                    sync["synchronized_wallets_10m"]
                ),

                "synchronized_wallets_1h": (
                    sync["synchronized_wallets_1h"]
                ),

                "synchronized_wallets_6h": (
                    sync["synchronized_wallets_6h"]
                ),

                "synchronized_wallets_24h": (
                    sync["synchronized_wallets_24h"]
                ),

                "synchronized_elite_wallets_10m": (
                    sync[
                        "synchronized_elite_wallets_10m"
                    ]
                ),

                "synchronized_elite_wallets_1h": (
                    sync[
                        "synchronized_elite_wallets_1h"
                    ]
                ),

                "synchronized_elite_wallets_6h": (
                    sync[
                        "synchronized_elite_wallets_6h"
                    ]
                ),

                "synchronized_elite_wallets_24h": (
                    sync[
                        "synchronized_elite_wallets_24h"
                    ]
                ),

                "time_sync_score": (
                    sync["time_sync_score"]
                ),

                "opposing_wallet_count": len(
                    opposing_wallets
                ),

                "opposing_elite_wallet_count": len(
                    opposing_elite_wallets
                ),

                "opposing_current_value": (
                    opposing_current_value
                ),

                "market_total_value": (
                    market_total_value
                ),

                "agreement_value_share": (
                    agreement_value_share
                ),

                "conflict_ratio": conflict_ratio,

                "opposing_conflict_score": (
                    opposing_conflict_score
                ),

                "overlap_pair_coverage": (
                    overlap["overlap_pair_coverage"]
                ),

                "average_pair_overlap": (
                    overlap["average_pair_overlap"]
                ),

                "portfolio_independence_score": (
                    overlap[
                        "portfolio_independence_score"
                    ]
                ),

                "capital_score": capital_component,

                "wallet_quality_score": (
                    wallet_quality_component
                ),

                "agreement_score": agreement_score,

                "freshness_score": (
                    freshness_component
                ),

                "consensus_strength": (
                    consensus_strength
                ),

                "confidence_grade": grade,

                "signal_status": signal_status,

                "lifecycle_status": (
                    lifecycle_status
                ),

                "seconds_to_start": (
                    seconds_to_start
                ),

                "data_completeness_score": (
                    completeness
                ),

                "data_confidence": confidence,

                "wallets_json": json.dumps(
                    sorted(
                        wallet_payload,
                        key=lambda item: (
                            item["current_value"]
                        ),
                        reverse=True,
                    ),
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
            item["consensus_strength"],
            item["elite_wallet_count"],
            item["effective_wallet_count"],
            item["total_current_value"],
        ),
        reverse=True,
    )

    return records


# =============================================================================
# SAVING
# =============================================================================


CURRENT_COLUMNS = [
    "consensus_key",
    "market_id",
    "title",
    "outcome",
    "wallet_count",
    "elite_wallet_count",
    "effective_wallet_count",
    "independent_wallet_score",
    "total_current_value",
    "elite_current_value",
    "elite_value_share",
    "average_wallet_quality",
    "weighted_wallet_quality",
    "weighted_entry_price",
    "weighted_elite_entry_price",
    "entry_price_stddev",
    "entry_price_dispersion_score",
    "earliest_entry_at",
    "latest_entry_at",
    "entry_span_seconds",
    "synchronized_wallets_10m",
    "synchronized_wallets_1h",
    "synchronized_wallets_6h",
    "synchronized_wallets_24h",
    "synchronized_elite_wallets_10m",
    "synchronized_elite_wallets_1h",
    "synchronized_elite_wallets_6h",
    "synchronized_elite_wallets_24h",
    "time_sync_score",
    "opposing_wallet_count",
    "opposing_elite_wallet_count",
    "opposing_current_value",
    "market_total_value",
    "agreement_value_share",
    "conflict_ratio",
    "opposing_conflict_score",
    "overlap_pair_coverage",
    "average_pair_overlap",
    "portfolio_independence_score",
    "capital_score",
    "wallet_quality_score",
    "agreement_score",
    "freshness_score",
    "consensus_strength",
    "confidence_grade",
    "signal_status",
    "lifecycle_status",
    "seconds_to_start",
    "data_completeness_score",
    "data_confidence",
    "wallets_json",
    "explanation_json",
    "calculated_at",
    "updated_at",
]


HISTORY_COLUMNS = [
    "consensus_key",
    "market_id",
    "title",
    "outcome",
    "wallet_count",
    "elite_wallet_count",
    "effective_wallet_count",
    "independent_wallet_score",
    "total_current_value",
    "elite_current_value",
    "elite_value_share",
    "average_wallet_quality",
    "weighted_wallet_quality",
    "weighted_entry_price",
    "weighted_elite_entry_price",
    "entry_price_stddev",
    "entry_price_dispersion_score",
    "earliest_entry_at",
    "latest_entry_at",
    "entry_span_seconds",
    "synchronized_wallets_10m",
    "synchronized_wallets_1h",
    "synchronized_wallets_6h",
    "synchronized_wallets_24h",
    "synchronized_elite_wallets_10m",
    "synchronized_elite_wallets_1h",
    "synchronized_elite_wallets_6h",
    "synchronized_elite_wallets_24h",
    "time_sync_score",
    "opposing_wallet_count",
    "opposing_elite_wallet_count",
    "opposing_current_value",
    "market_total_value",
    "agreement_value_share",
    "conflict_ratio",
    "opposing_conflict_score",
    "overlap_pair_coverage",
    "average_pair_overlap",
    "portfolio_independence_score",
    "capital_score",
    "wallet_quality_score",
    "agreement_score",
    "freshness_score",
    "consensus_strength",
    "confidence_grade",
    "signal_status",
    "lifecycle_status",
    "seconds_to_start",
    "data_completeness_score",
    "data_confidence",
    "observed_at",
]


def save_consensus_records(
    records: list[dict[str, Any]],
) -> tuple[int, int]:
    connection = connect_database()

    try:
        connection.execute("BEGIN IMMEDIATE")

        active_keys = [
            record["consensus_key"]
            for record in records
        ]

        if active_keys:
            placeholders = ", ".join(
                "?"
                for _ in active_keys
            )

            connection.execute(
                f"""
                DELETE FROM institutional_consensus
                WHERE consensus_key
                NOT IN ({placeholders})
                """,
                active_keys,
            )

        else:
            connection.execute(
                "DELETE FROM institutional_consensus"
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
            if column != "consensus_key"
        )

        current_query = f"""
            INSERT INTO institutional_consensus (
                {current_names}
            )
            VALUES (
                {current_placeholders}
            )
            ON CONFLICT(consensus_key)
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
            INSERT INTO institutional_consensus_history (
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


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run() -> tuple[int, datetime]:
    started = utc_now()

    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO institutional_consensus_runs (
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
    active_groups_seen: int,
    consensus_rows_saved: int,
    history_rows_created: int,
    error_message: str = "",
) -> None:
    finished_at = utc_now()

    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE institutional_consensus_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                active_groups_seen = ?,
                consensus_rows_saved = ?,
                history_rows_created = ?,
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
                active_groups_seen,
                consensus_rows_saved,
                history_rows_created,
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
        print("INSTITUTIONAL CONSENSUS DATA READINESS")
        print("=" * 108)

        for table_name in (
            "wallet_scans",
            "positions",
            "wallet_profiles",
            "portfolio_overlap",
            "market_metadata",
            "institutional_consensus",
            "institutional_consensus_history",
            "institutional_consensus_runs",
        ):
            if table_exists(connection, table_name):
                print(
                    f"{table_name:<44}"
                    f"{table_row_count(connection, table_name):>12} rows"
                )
            else:
                print(
                    f"{table_name:<44}"
                    f"{'NOT FOUND':>12}"
                )

        print("=" * 108)

    finally:
        connection.close()


def display_summary(
    records: list[dict[str, Any]],
    current_saved: int,
    history_saved: int,
) -> None:
    grade_counts: dict[str, int] = defaultdict(int)
    status_counts: dict[str, int] = defaultdict(int)

    for record in records:
        grade_counts[
            record["confidence_grade"]
        ] += 1

        status_counts[
            record["signal_status"]
        ] += 1

    print()
    print("=" * 108)
    print("INSTITUTIONAL CONSENSUS SUMMARY")
    print("=" * 108)

    print(
        f"Consensus groups calculated:    "
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
        f"S+ signals:                     "
        f"{grade_counts['S+']}"
    )

    print(
        f"S or better:                    "
        f"{grade_counts['S+'] + grade_counts['S']}"
    )

    print(
        f"A or better:                    "
        f"{sum(grade_counts[g] for g in ('S+', 'S', 'A+', 'A'))}"
    )

    print()
    print("SIGNAL STATUS COUNTS")

    for label, total in sorted(
        status_counts.items(),
        key=lambda item: (
            item[1],
            item[0],
        ),
        reverse=True,
    ):
        print(
            f"{label:<40}"
            f"{total:>8}"
        )

    print("=" * 108)


def display_record(
    rank: int,
    record: dict[str, Any],
) -> None:
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
        f"Consensus strength:             "
        f"{record['consensus_strength']:.1f}/100"
    )

    print(
        f"Grade / status:                 "
        f"{record['confidence_grade']} "
        f"/ {record['signal_status']}"
    )

    print(
        f"Data confidence:                "
        f"{record['data_confidence']} "
        f"({record['data_completeness_score']:.1f}/100)"
    )

    print()
    print("WALLET AGREEMENT")

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
        f"Weighted wallet quality:        "
        f"{record['weighted_wallet_quality']:.1f}/100"
    )

    print(
        f"Portfolio independence:         "
        f"{record['portfolio_independence_score']:.1f}/100"
    )

    print(
        f"Agreement value share:          "
        f"{format_percentage(record['agreement_value_share'])}"
    )

    print(
        f"Opposing value:                 "
        f"{format_money(record['opposing_current_value'])}"
    )

    print()
    print("CAPITAL AND ENTRY")

    print(
        f"Current consensus value:        "
        f"{format_money(record['total_current_value'])}"
    )

    print(
        f"Elite capital share:            "
        f"{format_percentage(record['elite_value_share'])}"
    )

    print(
        f"Weighted entry price:           "
        f"{format_price(record['weighted_entry_price'])}"
    )

    if record["weighted_elite_entry_price"] is not None:
        print(
            f"Weighted elite entry:           "
            f"{format_price(record['weighted_elite_entry_price'])}"
        )

    print(
        f"Entry-price consistency:        "
        f"{record['entry_price_dispersion_score']:.1f}/100"
    )

    print()
    print("TIME SYNCHRONIZATION")

    print(
        f"10m / 1h synchronized:          "
        f"{record['synchronized_wallets_10m']} "
        f"/ {record['synchronized_wallets_1h']}"
    )

    print(
        f"6h / 24h synchronized:          "
        f"{record['synchronized_wallets_6h']} "
        f"/ {record['synchronized_wallets_24h']}"
    )

    print(
        f"Elite 1h / 6h synchronized:    "
        f"{record['synchronized_elite_wallets_1h']} "
        f"/ {record['synchronized_elite_wallets_6h']}"
    )

    print(
        f"Time synchronization score:     "
        f"{record['time_sync_score']:.1f}/100"
    )

    print(
        f"Entry span:                     "
        f"{format_age(record['entry_span_seconds'])}"
    )

    print()
    print("COMPONENTS")

    print(
        f"Wallet quality:                 "
        f"{record['wallet_quality_score']:.1f}"
    )

    print(
        f"Agreement:                      "
        f"{record['agreement_score']:.1f}"
    )

    print(
        f"Capital:                        "
        f"{record['capital_score']:.1f}"
    )

    print(
        f"Freshness:                      "
        f"{record['freshness_score']:.1f}"
    )

    print(
        f"Conflict ratio:                 "
        f"{format_percentage(record['conflict_ratio'])}"
    )

    print(
        f"Lifecycle:                      "
        f"{record['lifecycle_status']}"
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure synchronized elite-wallet agreement, "
            "entry consistency, independence and opposing conflict."
        )
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
        help=(
            "Maximum number of consensus signals to display."
        ),
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
    print("POLYMARKET INSTITUTIONAL CONSENSUS ENGINE v1")
    print("=" * 108)

    print(
        f"Database: {DATABASE_PATH}"
    )

    create_institutional_consensus_tables()

    display_readiness()

    run_id, started_at = start_run()

    active_groups_seen = 0
    current_saved = 0
    history_saved = 0

    try:
        records = build_consensus_records()

        active_groups_seen = len(records)

        current_saved, history_saved = (
            save_consensus_records(records)
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            active_groups_seen=active_groups_seen,
            consensus_rows_saved=current_saved,
            history_rows_created=history_saved,
        )

        display_summary(
            records=records,
            current_saved=current_saved,
            history_saved=history_saved,
        )

        print()
        print("TOP INSTITUTIONAL CONSENSUS SIGNALS")

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
        print("INSTITUTIONAL CONSENSUS ENGINE COMPLETE")
        print("=" * 108)

        print(
            "Current synchronized consensus was saved to "
            "institutional_consensus."
        )

        print(
            "Historical consensus snapshots were saved to "
            "institutional_consensus_history."
        )

        print(
            "Entry timing is reconstructed from the first "
            "observed wallet scan, not an exact trade timestamp."
        )

        print(
            "Consensus strength is a research ranking, "
            "not a calibrated win probability."
        )

        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            active_groups_seen=active_groups_seen,
            consensus_rows_saved=current_saved,
            history_rows_created=history_saved,
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()