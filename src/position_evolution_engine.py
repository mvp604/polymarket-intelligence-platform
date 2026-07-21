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

ELITE_SCORE_THRESHOLD = 75.0
ELITE_GRADES = {"S+", "S", "A+"}

INACTIVE_STATUSES = {
    "resolved",
    "closed",
    "ended",
    "ended_unconfirmed",
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


def format_money(value: Any) -> str:
    number = safe_float(value)

    if number > 0:
        return f"+${number:,.2f}"

    if number < 0:
        return f"-${abs(number):,.2f}"

    return "$0.00"


def format_percentage(value: Any) -> str:
    return f"{safe_float(value):+.1%}"


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


def create_position_evolution_tables() -> None:
    connection = connect_database()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS position_evolution (
                evolution_key TEXT PRIMARY KEY,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                prior_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                current_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                wallet_count_change INTEGER
                    NOT NULL DEFAULT 0,

                prior_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                current_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count_change INTEGER
                    NOT NULL DEFAULT 0,

                new_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                exited_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                increased_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                reduced_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                unchanged_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                new_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                exited_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                prior_total_value REAL
                    NOT NULL DEFAULT 0,

                current_total_value REAL
                    NOT NULL DEFAULT 0,

                net_value_change REAL
                    NOT NULL DEFAULT 0,

                gross_inflow REAL
                    NOT NULL DEFAULT 0,

                gross_outflow REAL
                    NOT NULL DEFAULT 0,

                prior_total_shares REAL
                    NOT NULL DEFAULT 0,

                current_total_shares REAL
                    NOT NULL DEFAULT 0,

                net_share_change REAL
                    NOT NULL DEFAULT 0,

                capital_growth_ratio REAL
                    NOT NULL DEFAULT 0,

                elite_capital_change REAL
                    NOT NULL DEFAULT 0,

                new_wallet_score REAL
                    NOT NULL DEFAULT 0,

                retention_score REAL
                    NOT NULL DEFAULT 0,

                elite_change_score REAL
                    NOT NULL DEFAULT 0,

                capital_flow_score REAL
                    NOT NULL DEFAULT 0,

                strengthening_score REAL
                    NOT NULL DEFAULT 0,

                weakening_score REAL
                    NOT NULL DEFAULT 0,

                evolution_score REAL
                    NOT NULL DEFAULT 0,

                evolution_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                evolution_status TEXT
                    NOT NULL DEFAULT 'NO CHANGE',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                prior_scan_at TEXT,
                current_scan_at TEXT,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                wallet_changes_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_position_evolution_rank
            ON position_evolution(
                evolution_score DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_position_evolution_status
            ON position_evolution(
                evolution_status,
                evolution_score DESC
            );

            CREATE TABLE IF NOT EXISTS position_evolution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                evolution_key TEXT NOT NULL,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                prior_wallet_count INTEGER,
                current_wallet_count INTEGER,
                wallet_count_change INTEGER,

                prior_elite_wallet_count INTEGER,
                current_elite_wallet_count INTEGER,
                elite_wallet_count_change INTEGER,

                new_wallet_count INTEGER,
                exited_wallet_count INTEGER,
                increased_wallet_count INTEGER,
                reduced_wallet_count INTEGER,
                unchanged_wallet_count INTEGER,

                new_elite_wallet_count INTEGER,
                exited_elite_wallet_count INTEGER,

                prior_total_value REAL,
                current_total_value REAL,
                net_value_change REAL,
                gross_inflow REAL,
                gross_outflow REAL,

                prior_total_shares REAL,
                current_total_shares REAL,
                net_share_change REAL,

                capital_growth_ratio REAL,
                elite_capital_change REAL,

                new_wallet_score REAL,
                retention_score REAL,
                elite_change_score REAL,
                capital_flow_score REAL,
                strengthening_score REAL,
                weakening_score REAL,

                evolution_score REAL,
                evolution_grade TEXT,
                evolution_status TEXT,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                prior_scan_at TEXT,
                current_scan_at TEXT,

                data_completeness_score REAL,
                data_confidence TEXT,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_position_evolution_history_key
            ON position_evolution_history(
                evolution_key,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS position_evolution_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                wallet_pairs_compared INTEGER
                    NOT NULL DEFAULT 0,

                market_groups_calculated INTEGER
                    NOT NULL DEFAULT 0,

                current_rows_saved INTEGER
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


def load_latest_two_scans() -> dict[
    str,
    tuple[dict[str, Any] | None, dict[str, Any]],
]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            WITH ranked AS (
                SELECT
                    id,
                    wallet,
                    scanned_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY wallet
                        ORDER BY id DESC
                    ) AS row_number
                FROM wallet_scans
            )
            SELECT
                id,
                wallet,
                scanned_at,
                row_number
            FROM ranked
            WHERE row_number <= 2
            ORDER BY wallet, row_number
            """
        ).fetchall()

    finally:
        connection.close()

    grouped: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)

    for row in rows:
        wallet = normalize_wallet(row["wallet"])
        grouped[wallet][safe_int(row["row_number"])] = dict(row)

    output: dict[
        str,
        tuple[
            dict[str, Any] | None,
            dict[str, Any],
        ],
    ] = {}

    for wallet, ranked in grouped.items():
        latest = ranked.get(1)

        if latest is None:
            continue

        prior = ranked.get(2)

        output[wallet] = (
            prior,
            latest,
        )

    return output


def load_positions_for_scan_ids(
    scan_ids: set[int],
) -> dict[int, list[dict[str, Any]]]:
    if not scan_ids:
        return {}

    connection = connect_database()

    try:
        placeholders = ", ".join(
            "?"
            for _ in scan_ids
        )

        rows = connection.execute(
            f"""
            SELECT *
            FROM positions
            WHERE scan_id IN ({placeholders})
            """,
            list(scan_ids),
        ).fetchall()

    finally:
        connection.close()

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        grouped[safe_int(row["scan_id"])].append(dict(row))

    return dict(grouped)


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
# WALLET DELTAS
# =============================================================================


def index_scan_positions(
    positions: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for position in positions:
        market_id = normalize_market_id(
            position.get("market_id")
        )

        outcome = normalize_text(
            position.get("outcome")
        )

        if not market_id or not outcome:
            continue

        key = (
            market_id,
            outcome,
        )

        prior = indexed.get(key)

        if (
            prior is None
            or safe_float(
                position.get("current_value")
            )
            > safe_float(
                prior.get("current_value")
            )
        ):
            indexed[key] = position

    return indexed


def classify_wallet_change(
    prior_value: float,
    current_value: float,
    prior_shares: float,
    current_shares: float,
) -> str:
    value_delta = current_value - prior_value
    share_delta = current_shares - prior_shares

    threshold = max(
        abs(prior_value) * 0.02,
        1.0,
    )

    if prior_value <= 0 and current_value > 0:
        return "NEW"

    if prior_value > 0 and current_value <= 0:
        return "EXITED"

    if value_delta > threshold or share_delta > 0.01:
        return "INCREASED"

    if value_delta < -threshold or share_delta < -0.01:
        return "REDUCED"

    return "UNCHANGED"


def build_wallet_changes() -> tuple[
    list[dict[str, Any]],
    int,
]:
    profiles = load_wallet_profiles()
    scan_pairs = load_latest_two_scans()

    scan_ids: set[int] = set()

    for prior, latest in scan_pairs.values():
        scan_ids.add(safe_int(latest["id"]))

        if prior is not None:
            scan_ids.add(safe_int(prior["id"]))

    positions_by_scan = load_positions_for_scan_ids(
        scan_ids
    )

    changes: list[dict[str, Any]] = []
    compared_pairs = 0

    for wallet, (
        prior_scan,
        current_scan,
    ) in scan_pairs.items():
        profile = profiles.get(wallet)

        if profile is None:
            continue

        if prior_scan is None:
            prior_index: dict[
                tuple[str, str],
                dict[str, Any],
            ] = {}
        else:
            compared_pairs += 1

            prior_index = index_scan_positions(
                positions_by_scan.get(
                    safe_int(prior_scan["id"]),
                    [],
                )
            )

        current_index = index_scan_positions(
            positions_by_scan.get(
                safe_int(current_scan["id"]),
                [],
            )
        )

        keys = set(prior_index) | set(current_index)

        elite = wallet_is_elite(profile)

        for key in keys:
            prior_position = prior_index.get(key)
            current_position = current_index.get(key)

            prior_value = safe_float(
                prior_position.get("current_value")
                if prior_position
                else 0.0
            )

            current_value = safe_float(
                current_position.get("current_value")
                if current_position
                else 0.0
            )

            prior_shares = safe_float(
                prior_position.get("shares")
                if prior_position
                else 0.0
            )

            current_shares = safe_float(
                current_position.get("shares")
                if current_position
                else 0.0
            )

            change_type = classify_wallet_change(
                prior_value=prior_value,
                current_value=current_value,
                prior_shares=prior_shares,
                current_shares=current_shares,
            )

            source_position = (
                current_position
                or prior_position
            )

            changes.append(
                {
                    "wallet": wallet,
                    "market_id": key[0],
                    "outcome_key": key[1],
                    "title": clean_text(
                        source_position.get("title")
                    )
                    or "Unknown market",
                    "outcome": clean_text(
                        source_position.get("outcome")
                    )
                    or "Unknown",
                    "elite": elite,
                    "wallet_quality": (
                        wallet_quality_score(profile)
                    ),
                    "prior_value": prior_value,
                    "current_value": current_value,
                    "value_change": (
                        current_value
                        - prior_value
                    ),
                    "prior_shares": prior_shares,
                    "current_shares": current_shares,
                    "share_change": (
                        current_shares
                        - prior_shares
                    ),
                    "change_type": change_type,
                    "prior_scan_at": (
                        clean_text(
                            prior_scan.get("scanned_at")
                        )
                        if prior_scan
                        else ""
                    ),
                    "current_scan_at": (
                        clean_text(
                            current_scan.get("scanned_at")
                        )
                    ),
                }
            )

    return changes, compared_pairs


# =============================================================================
# MARKET-LEVEL EVOLUTION
# =============================================================================


def grade_from_score(score: float) -> str:
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


def classify_evolution_status(
    strengthening_score: float,
    weakening_score: float,
    wallet_change: int,
    elite_change: int,
    net_value_change: float,
    lifecycle_status: str,
) -> str:
    if normalize_text(
        lifecycle_status
    ) in INACTIVE_STATUSES:
        return "INACTIVE"

    if weakening_score >= 75:
        return "SHARP DISTRIBUTION"

    if weakening_score >= 55:
        return "WEAKENING"

    if strengthening_score >= 80:
        return "ACCELERATING ACCUMULATION"

    if strengthening_score >= 65:
        return "STRENGTHENING"

    if elite_change > 0:
        return "ELITE ADDING"

    if elite_change < 0:
        return "ELITE EXITING"

    if wallet_change > 0:
        return "NEW BUYERS"

    if wallet_change < 0:
        return "BUYERS EXITING"

    if net_value_change > 0:
        return "CAPITAL INFLOW"

    if net_value_change < 0:
        return "CAPITAL OUTFLOW"

    return "NO MATERIAL CHANGE"


def data_completeness(
    prior_wallet_count: int,
    current_wallet_count: int,
    metadata: dict[str, Any] | None,
    has_prior_scan: bool,
) -> tuple[float, str]:
    score = 0.0

    if current_wallet_count > 0:
        score += 30.0

    if has_prior_scan:
        score += 40.0

    if prior_wallet_count > 0:
        score += 15.0

    if metadata is not None:
        score += 15.0

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


def build_evolution_records() -> tuple[
    list[dict[str, Any]],
    int,
]:
    wallet_changes, compared_pairs = (
        build_wallet_changes()
    )

    metadata_lookup = (
        load_market_metadata()
    )

    grouped: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for change in wallet_changes:
        grouped[
            (
                change["market_id"],
                change["outcome_key"],
            )
        ].append(change)

    calculated_at = utc_now_iso()

    records: list[dict[str, Any]] = []

    for (
        market_id,
        outcome_key,
    ), group in grouped.items():
        title = clean_text(
            group[0]["title"]
        )

        outcome = clean_text(
            group[0]["outcome"]
        )

        prior_wallets = {
            item["wallet"]
            for item in group
            if item["prior_value"] > 0
        }

        current_wallets = {
            item["wallet"]
            for item in group
            if item["current_value"] > 0
        }

        prior_elite_wallets = {
            item["wallet"]
            for item in group
            if item["elite"]
            and item["prior_value"] > 0
        }

        current_elite_wallets = {
            item["wallet"]
            for item in group
            if item["elite"]
            and item["current_value"] > 0
        }

        prior_wallet_count = len(
            prior_wallets
        )

        current_wallet_count = len(
            current_wallets
        )

        prior_elite_count = len(
            prior_elite_wallets
        )

        current_elite_count = len(
            current_elite_wallets
        )

        wallet_count_change = (
            current_wallet_count
            - prior_wallet_count
        )

        elite_wallet_count_change = (
            current_elite_count
            - prior_elite_count
        )

        count_by_type: dict[str, int] = defaultdict(int)

        for item in group:
            count_by_type[
                item["change_type"]
            ] += 1

        prior_total_value = sum(
            item["prior_value"]
            for item in group
        )

        current_total_value = sum(
            item["current_value"]
            for item in group
        )

        net_value_change = (
            current_total_value
            - prior_total_value
        )

        gross_inflow = sum(
            max(
                item["value_change"],
                0.0,
            )
            for item in group
        )

        gross_outflow = sum(
            abs(
                min(
                    item["value_change"],
                    0.0,
                )
            )
            for item in group
        )

        prior_total_shares = sum(
            item["prior_shares"]
            for item in group
        )

        current_total_shares = sum(
            item["current_shares"]
            for item in group
        )

        net_share_change = (
            current_total_shares
            - prior_total_shares
        )

        capital_growth_ratio = (
            net_value_change
            / prior_total_value
            if prior_total_value > 0
            else (
                1.0
                if current_total_value > 0
                else 0.0
            )
        )

        elite_capital_change = sum(
            item["value_change"]
            for item in group
            if item["elite"]
        )

        new_wallet_score = clamp(
            count_by_type["NEW"]
            / max(
                current_wallet_count,
                1,
            )
            * 100.0
        )

        retained_wallets = len(
            prior_wallets
            & current_wallets
        )

        retention_score = clamp(
            retained_wallets
            / max(
                prior_wallet_count,
                1,
            )
            * 100.0
        )

        elite_change_score = clamp(
            50.0
            + elite_wallet_count_change
            * 18.0
            + (
                elite_capital_change
                / max(
                    current_total_value,
                    1.0,
                )
            )
            * 35.0
        )

        capital_flow_score = clamp(
            50.0
            + clamp(
                capital_growth_ratio,
                -1.0,
                1.0,
            )
            * 40.0
            + (
                gross_inflow
                / max(
                    gross_inflow
                    + gross_outflow,
                    1.0,
                )
                - 0.5
            )
            * 20.0
        )

        strengthening_score = clamp(
            new_wallet_score * 0.25
            + retention_score * 0.15
            + elite_change_score * 0.30
            + capital_flow_score * 0.30
        )

        exit_ratio = (
            count_by_type["EXITED"]
            / max(
                prior_wallet_count,
                1,
            )
        )

        reduction_ratio = (
            count_by_type["REDUCED"]
            / max(
                len(group),
                1,
            )
        )

        negative_capital_ratio = (
            gross_outflow
            / max(
                gross_inflow
                + gross_outflow,
                1.0,
            )
        )

        weakening_score = clamp(
            exit_ratio * 40.0
            + reduction_ratio * 25.0
            + negative_capital_ratio * 25.0
            + (
                10.0
                if elite_wallet_count_change < 0
                else 0.0
            )
        )

        evolution_score = clamp(
            50.0
            + (
                strengthening_score
                - weakening_score
            )
            * 0.70
        )

        evolution_grade = grade_from_score(
            evolution_score
        )

        metadata = metadata_lookup.get(
            market_id
        )

        lifecycle_status = clean_text(
            metadata.get(
                "lifecycle_status"
            )
            if metadata
            else ""
        ) or "UNKNOWN"

        seconds_value = (
            metadata.get(
                "seconds_to_start"
            )
            if metadata
            else None
        )

        seconds_to_start = (
            safe_int(seconds_value)
            if seconds_value is not None
            else None
        )

        status = classify_evolution_status(
            strengthening_score=(
                strengthening_score
            ),
            weakening_score=(
                weakening_score
            ),
            wallet_change=(
                wallet_count_change
            ),
            elite_change=(
                elite_wallet_count_change
            ),
            net_value_change=(
                net_value_change
            ),
            lifecycle_status=(
                lifecycle_status
            ),
        )

        prior_scan_times = [
            parse_datetime(
                item["prior_scan_at"]
            )
            for item in group
            if item["prior_scan_at"]
        ]

        current_scan_times = [
            parse_datetime(
                item["current_scan_at"]
            )
            for item in group
            if item["current_scan_at"]
        ]

        prior_scan_at = (
            max(
                time
                for time in prior_scan_times
                if time is not None
            ).isoformat()
            if any(
                time is not None
                for time in prior_scan_times
            )
            else ""
        )

        current_scan_at = (
            max(
                time
                for time in current_scan_times
                if time is not None
            ).isoformat()
            if any(
                time is not None
                for time in current_scan_times
            )
            else ""
        )

        completeness, confidence = (
            data_completeness(
                prior_wallet_count=(
                    prior_wallet_count
                ),
                current_wallet_count=(
                    current_wallet_count
                ),
                metadata=metadata,
                has_prior_scan=bool(
                    prior_scan_at
                ),
            )
        )

        wallet_payload = [
            {
                "wallet": item["wallet"],
                "elite": item["elite"],
                "wallet_quality": round(
                    item["wallet_quality"],
                    2,
                ),
                "change_type": (
                    item["change_type"]
                ),
                "prior_value": round(
                    item["prior_value"],
                    2,
                ),
                "current_value": round(
                    item["current_value"],
                    2,
                ),
                "value_change": round(
                    item["value_change"],
                    2,
                ),
                "prior_shares": round(
                    item["prior_shares"],
                    4,
                ),
                "current_shares": round(
                    item["current_shares"],
                    4,
                ),
                "share_change": round(
                    item["share_change"],
                    4,
                ),
            }
            for item in sorted(
                group,
                key=lambda row: abs(
                    row["value_change"]
                ),
                reverse=True,
            )
        ]

        explanation = {
            "model_version": "1.0",
            "comparison_method": (
                "LATEST WALLET SCAN VS PREVIOUS WALLET SCAN"
            ),
            "score_components": {
                "new_wallet_score": round(
                    new_wallet_score,
                    2,
                ),
                "retention_score": round(
                    retention_score,
                    2,
                ),
                "elite_change_score": round(
                    elite_change_score,
                    2,
                ),
                "capital_flow_score": round(
                    capital_flow_score,
                    2,
                ),
                "strengthening_score": round(
                    strengthening_score,
                    2,
                ),
                "weakening_score": round(
                    weakening_score,
                    2,
                ),
            },
            "limitations": [
                (
                    "Changes are based on scan snapshots, "
                    "not exact trade-by-trade execution history."
                ),
                (
                    "Current value can change because of both "
                    "position size and market price."
                ),
            ],
        }

        records.append(
            {
                "evolution_key": (
                    f"{market_id}:{outcome_key}"
                ),

                "market_id": market_id,
                "title": title,
                "outcome": outcome,

                "prior_wallet_count": (
                    prior_wallet_count
                ),

                "current_wallet_count": (
                    current_wallet_count
                ),

                "wallet_count_change": (
                    wallet_count_change
                ),

                "prior_elite_wallet_count": (
                    prior_elite_count
                ),

                "current_elite_wallet_count": (
                    current_elite_count
                ),

                "elite_wallet_count_change": (
                    elite_wallet_count_change
                ),

                "new_wallet_count": (
                    count_by_type["NEW"]
                ),

                "exited_wallet_count": (
                    count_by_type["EXITED"]
                ),

                "increased_wallet_count": (
                    count_by_type["INCREASED"]
                ),

                "reduced_wallet_count": (
                    count_by_type["REDUCED"]
                ),

                "unchanged_wallet_count": (
                    count_by_type["UNCHANGED"]
                ),

                "new_elite_wallet_count": sum(
                    1
                    for item in group
                    if item["elite"]
                    and item["change_type"]
                    == "NEW"
                ),

                "exited_elite_wallet_count": sum(
                    1
                    for item in group
                    if item["elite"]
                    and item["change_type"]
                    == "EXITED"
                ),

                "prior_total_value": (
                    prior_total_value
                ),

                "current_total_value": (
                    current_total_value
                ),

                "net_value_change": (
                    net_value_change
                ),

                "gross_inflow": gross_inflow,
                "gross_outflow": gross_outflow,

                "prior_total_shares": (
                    prior_total_shares
                ),

                "current_total_shares": (
                    current_total_shares
                ),

                "net_share_change": (
                    net_share_change
                ),

                "capital_growth_ratio": (
                    capital_growth_ratio
                ),

                "elite_capital_change": (
                    elite_capital_change
                ),

                "new_wallet_score": (
                    new_wallet_score
                ),

                "retention_score": (
                    retention_score
                ),

                "elite_change_score": (
                    elite_change_score
                ),

                "capital_flow_score": (
                    capital_flow_score
                ),

                "strengthening_score": (
                    strengthening_score
                ),

                "weakening_score": (
                    weakening_score
                ),

                "evolution_score": (
                    evolution_score
                ),

                "evolution_grade": (
                    evolution_grade
                ),

                "evolution_status": (
                    status
                ),

                "lifecycle_status": (
                    lifecycle_status
                ),

                "seconds_to_start": (
                    seconds_to_start
                ),

                "prior_scan_at": (
                    prior_scan_at
                ),

                "current_scan_at": (
                    current_scan_at
                ),

                "data_completeness_score": (
                    completeness
                ),

                "data_confidence": (
                    confidence
                ),

                "wallet_changes_json": (
                    json.dumps(
                        wallet_payload,
                        ensure_ascii=False,
                    )
                ),

                "explanation_json": (
                    json.dumps(
                        explanation,
                        ensure_ascii=False,
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

    records.sort(
        key=lambda item: (
            item["evolution_score"],
            item["strengthening_score"],
            item["elite_wallet_count_change"],
            item["net_value_change"],
        ),
        reverse=True,
    )

    return records, compared_pairs


# =============================================================================
# SAVING
# =============================================================================


CURRENT_COLUMNS = [
    "evolution_key",
    "market_id",
    "title",
    "outcome",
    "prior_wallet_count",
    "current_wallet_count",
    "wallet_count_change",
    "prior_elite_wallet_count",
    "current_elite_wallet_count",
    "elite_wallet_count_change",
    "new_wallet_count",
    "exited_wallet_count",
    "increased_wallet_count",
    "reduced_wallet_count",
    "unchanged_wallet_count",
    "new_elite_wallet_count",
    "exited_elite_wallet_count",
    "prior_total_value",
    "current_total_value",
    "net_value_change",
    "gross_inflow",
    "gross_outflow",
    "prior_total_shares",
    "current_total_shares",
    "net_share_change",
    "capital_growth_ratio",
    "elite_capital_change",
    "new_wallet_score",
    "retention_score",
    "elite_change_score",
    "capital_flow_score",
    "strengthening_score",
    "weakening_score",
    "evolution_score",
    "evolution_grade",
    "evolution_status",
    "lifecycle_status",
    "seconds_to_start",
    "prior_scan_at",
    "current_scan_at",
    "data_completeness_score",
    "data_confidence",
    "wallet_changes_json",
    "explanation_json",
    "calculated_at",
    "updated_at",
]


HISTORY_COLUMNS = [
    "evolution_key",
    "market_id",
    "title",
    "outcome",
    "prior_wallet_count",
    "current_wallet_count",
    "wallet_count_change",
    "prior_elite_wallet_count",
    "current_elite_wallet_count",
    "elite_wallet_count_change",
    "new_wallet_count",
    "exited_wallet_count",
    "increased_wallet_count",
    "reduced_wallet_count",
    "unchanged_wallet_count",
    "new_elite_wallet_count",
    "exited_elite_wallet_count",
    "prior_total_value",
    "current_total_value",
    "net_value_change",
    "gross_inflow",
    "gross_outflow",
    "prior_total_shares",
    "current_total_shares",
    "net_share_change",
    "capital_growth_ratio",
    "elite_capital_change",
    "new_wallet_score",
    "retention_score",
    "elite_change_score",
    "capital_flow_score",
    "strengthening_score",
    "weakening_score",
    "evolution_score",
    "evolution_grade",
    "evolution_status",
    "lifecycle_status",
    "seconds_to_start",
    "prior_scan_at",
    "current_scan_at",
    "data_completeness_score",
    "data_confidence",
    "observed_at",
]


def save_records(
    records: list[dict[str, Any]],
) -> tuple[int, int]:
    connection = connect_database()

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        active_keys = [
            record["evolution_key"]
            for record in records
        ]

        if active_keys:
            placeholders = ", ".join(
                "?"
                for _ in active_keys
            )

            connection.execute(
                f"""
                DELETE FROM position_evolution
                WHERE evolution_key
                NOT IN ({placeholders})
                """,
                active_keys,
            )

        else:
            connection.execute(
                "DELETE FROM position_evolution"
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
            if column != "evolution_key"
        )

        current_query = f"""
            INSERT INTO position_evolution (
                {current_names}
            )
            VALUES (
                {current_placeholders}
            )
            ON CONFLICT(evolution_key)
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
            INSERT INTO position_evolution_history (
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
            INSERT INTO position_evolution_runs (
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
    wallet_pairs_compared: int,
    market_groups_calculated: int,
    current_rows_saved: int,
    history_rows_created: int,
    error_message: str = "",
) -> None:
    finished = utc_now()

    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE position_evolution_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                wallet_pairs_compared = ?,
                market_groups_calculated = ?,
                current_rows_saved = ?,
                history_rows_created = ?,
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
                wallet_pairs_compared,
                market_groups_calculated,
                current_rows_saved,
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
        print("POSITION EVOLUTION DATA READINESS")
        print("=" * 108)

        for table_name in (
            "wallet_scans",
            "positions",
            "wallet_profiles",
            "market_metadata",
            "position_evolution",
            "position_evolution_history",
            "position_evolution_runs",
        ):
            if table_exists(connection, table_name):
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
    wallet_pairs_compared: int,
    current_saved: int,
    history_saved: int,
) -> None:
    status_counts: dict[str, int] = defaultdict(int)

    for record in records:
        status_counts[
            record["evolution_status"]
        ] += 1

    print()
    print("=" * 108)
    print("POSITION EVOLUTION SUMMARY")
    print("=" * 108)

    print(
        f"Wallet scan pairs compared:     "
        f"{wallet_pairs_compared}"
    )

    print(
        f"Market groups calculated:       "
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

    print()
    print("EVOLUTION STATUS COUNTS")

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
        f"Evolution score:                "
        f"{record['evolution_score']:.1f}/100"
    )

    print(
        f"Grade / status:                 "
        f"{record['evolution_grade']} "
        f"/ {record['evolution_status']}"
    )

    print(
        f"Data confidence:                "
        f"{record['data_confidence']} "
        f"({record['data_completeness_score']:.1f}/100)"
    )

    print()
    print("WALLET EVOLUTION")

    print(
        f"Wallets prior / current:        "
        f"{record['prior_wallet_count']} "
        f"/ {record['current_wallet_count']}"
    )

    print(
        f"Wallet count change:            "
        f"{record['wallet_count_change']:+d}"
    )

    print(
        f"Elite prior / current:          "
        f"{record['prior_elite_wallet_count']} "
        f"/ {record['current_elite_wallet_count']}"
    )

    print(
        f"Elite-wallet change:            "
        f"{record['elite_wallet_count_change']:+d}"
    )

    print(
        f"New / exited wallets:           "
        f"{record['new_wallet_count']} "
        f"/ {record['exited_wallet_count']}"
    )

    print(
        f"Increased / reduced:            "
        f"{record['increased_wallet_count']} "
        f"/ {record['reduced_wallet_count']}"
    )

    print()
    print("CAPITAL FLOW")

    print(
        f"Prior value:                    "
        f"${record['prior_total_value']:,.2f}"
    )

    print(
        f"Current value:                  "
        f"${record['current_total_value']:,.2f}"
    )

    print(
        f"Net value change:               "
        f"{format_money(record['net_value_change'])}"
    )

    print(
        f"Gross inflow / outflow:         "
        f"{format_money(record['gross_inflow'])} "
        f"/ "
        f"{format_money(-record['gross_outflow'])}"
    )

    print(
        f"Capital growth:                 "
        f"{format_percentage(record['capital_growth_ratio'])}"
    )

    print(
        f"Elite capital change:           "
        f"{format_money(record['elite_capital_change'])}"
    )

    print()
    print("COMPONENTS")

    print(
        f"New-wallet score:               "
        f"{record['new_wallet_score']:.1f}"
    )

    print(
        f"Retention score:                "
        f"{record['retention_score']:.1f}"
    )

    print(
        f"Elite-change score:             "
        f"{record['elite_change_score']:.1f}"
    )

    print(
        f"Capital-flow score:             "
        f"{record['capital_flow_score']:.1f}"
    )

    print(
        f"Strengthening / weakening:      "
        f"{record['strengthening_score']:.1f}"
        f" / "
        f"{record['weakening_score']:.1f}"
    )

    print(
        f"Lifecycle:                      "
        f"{record['lifecycle_status']}"
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare each wallet's latest and prior scans "
            "to measure position strengthening and weakening."
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
    print("POLYMARKET POSITION EVOLUTION ENGINE v1")
    print("=" * 108)

    print(
        f"Database: {DATABASE_PATH}"
    )

    create_position_evolution_tables()

    display_readiness()

    run_id, started_at = start_run()

    wallet_pairs_compared = 0
    current_saved = 0
    history_saved = 0
    records: list[dict[str, Any]] = []

    try:
        (
            records,
            wallet_pairs_compared,
        ) = build_evolution_records()

        current_saved, history_saved = (
            save_records(records)
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            wallet_pairs_compared=(
                wallet_pairs_compared
            ),
            market_groups_calculated=(
                len(records)
            ),
            current_rows_saved=(
                current_saved
            ),
            history_rows_created=(
                history_saved
            ),
        )

        display_summary(
            records=records,
            wallet_pairs_compared=(
                wallet_pairs_compared
            ),
            current_saved=current_saved,
            history_saved=history_saved,
        )

        print()
        print("TOP POSITION EVOLUTION SIGNALS")

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
        print("POSITION EVOLUTION ENGINE COMPLETE")
        print("=" * 108)

        print(
            "Current evolution metrics were saved to "
            "position_evolution."
        )

        print(
            "Historical snapshots were saved to "
            "position_evolution_history."
        )

        print(
            "Comparisons use each wallet's latest scan "
            "versus its immediately previous scan."
        )

        print(
            "Current value changes can reflect both position "
            "size changes and market-price movement."
        )

        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            wallet_pairs_compared=(
                wallet_pairs_compared
            ),
            market_groups_calculated=(
                len(records)
            ),
            current_rows_saved=(
                current_saved
            ),
            history_rows_created=(
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