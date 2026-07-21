from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_LOOKBACK_HOURS = 24
DEFAULT_DISPLAY_LIMIT = 30
DEFAULT_MIN_GROSS_FLOW = 100.0
DEFAULT_MIN_WALLETS = 2


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8() -> None:
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
    return max(
        minimum,
        min(
            value,
            maximum,
        ),
    )


def divide(
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
    amount = safe_float(value)

    if amount > 0:
        return f"+${amount:,.2f}"

    if amount < 0:
        return f"-${abs(amount):,.2f}"

    return "$0.00"


def signed_percent(value: float) -> str:
    return f"{value:+.1f}%"


def parse_iso(value: Any) -> datetime | None:
    raw = clean_text(value)

    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(
            raw.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except ValueError:
        return None


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
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
            WHERE type='table'
              AND name=?
            """,
            (table_name,),
        ).fetchone()
        is not None
    )


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


def create_tables() -> None:
    connection = connect_database()

    try:
        require_table(
            connection,
            "market_memory_snapshots",
        )

        require_table(
            connection,
            "market_memory_wallet_flows",
        )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS smart_money_flow_signals (
                signal_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,
                market_id TEXT,
                event_id TEXT,

                title TEXT,
                slug TEXT,
                event_slug TEXT,
                category TEXT,

                lookback_hours INTEGER NOT NULL,

                current_snapshot_key TEXT NOT NULL,
                previous_snapshot_key TEXT,

                current_snapshot_at TEXT NOT NULL,
                previous_snapshot_at TEXT,

                elapsed_hours REAL,

                current_trade_count INTEGER
                    NOT NULL DEFAULT 0,

                previous_trade_count INTEGER
                    NOT NULL DEFAULT 0,

                trade_count_change INTEGER
                    NOT NULL DEFAULT 0,

                current_unique_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                previous_unique_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                wallet_count_change INTEGER
                    NOT NULL DEFAULT 0,

                new_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                exited_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                persistent_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                bullish_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                bearish_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                current_buy_notional REAL
                    NOT NULL DEFAULT 0,

                current_sell_notional REAL
                    NOT NULL DEFAULT 0,

                current_net_flow REAL
                    NOT NULL DEFAULT 0,

                previous_net_flow REAL
                    NOT NULL DEFAULT 0,

                net_flow_change REAL
                    NOT NULL DEFAULT 0,

                current_gross_flow REAL
                    NOT NULL DEFAULT 0,

                previous_gross_flow REAL
                    NOT NULL DEFAULT 0,

                gross_flow_change REAL
                    NOT NULL DEFAULT 0,

                net_flow_velocity REAL
                    NOT NULL DEFAULT 0,

                gross_flow_velocity REAL
                    NOT NULL DEFAULT 0,

                flow_acceleration REAL
                    NOT NULL DEFAULT 0,

                buy_sell_imbalance REAL
                    NOT NULL DEFAULT 0,

                trusted_buy_notional REAL
                    NOT NULL DEFAULT 0,

                trusted_sell_notional REAL
                    NOT NULL DEFAULT 0,

                trusted_net_flow REAL
                    NOT NULL DEFAULT 0,

                elite_net_flow REAL
                    NOT NULL DEFAULT 0,

                qualified_net_flow REAL
                    NOT NULL DEFAULT 0,

                watchlist_net_flow REAL
                    NOT NULL DEFAULT 0,

                largest_buyer_wallet TEXT,
                largest_buyer_notional REAL
                    NOT NULL DEFAULT 0,

                largest_seller_wallet TEXT,
                largest_seller_notional REAL
                    NOT NULL DEFAULT 0,

                whale_concentration REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                concentration_risk REAL
                    NOT NULL DEFAULT 0,

                persistence_score REAL
                    NOT NULL DEFAULT 0,

                breadth_score REAL
                    NOT NULL DEFAULT 0,

                velocity_score REAL
                    NOT NULL DEFAULT 0,

                acceleration_score REAL
                    NOT NULL DEFAULT 0,

                imbalance_score REAL
                    NOT NULL DEFAULT 0,

                trusted_flow_score REAL
                    NOT NULL DEFAULT 0,

                accumulation_score REAL
                    NOT NULL DEFAULT 0,

                distribution_score REAL
                    NOT NULL DEFAULT 0,

                rotation_score REAL
                    NOT NULL DEFAULT 0,

                smart_money_flow_score REAL
                    NOT NULL DEFAULT 0,

                smart_money_flow_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                flow_direction TEXT
                    NOT NULL DEFAULT 'NEUTRAL',

                recommended_action TEXT
                    NOT NULL DEFAULT 'IGNORE',

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                is_actionable INTEGER
                    NOT NULL DEFAULT 0,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                winning_outcome TEXT,

                positive_evidence_json TEXT,
                risk_flags_json TEXT,
                metadata_json TEXT,

                observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_smart_money_flow_score
            ON smart_money_flow_signals(
                smart_money_flow_score DESC,
                observed_at DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_smart_money_flow_condition
            ON smart_money_flow_signals(
                condition_id,
                lookback_hours,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS smart_money_flow_wallet_events (
                event_key TEXT PRIMARY KEY,

                signal_key TEXT NOT NULL,
                condition_id TEXT NOT NULL,
                wallet TEXT NOT NULL,

                event_type TEXT NOT NULL,

                previous_direction TEXT,
                current_direction TEXT,

                previous_net_flow REAL
                    NOT NULL DEFAULT 0,

                current_net_flow REAL
                    NOT NULL DEFAULT 0,

                net_flow_change REAL
                    NOT NULL DEFAULT 0,

                wallet_status TEXT,
                elite_tier TEXT,

                consensus_weight REAL
                    NOT NULL DEFAULT 0,

                prediction_weight REAL
                    NOT NULL DEFAULT 0,

                wallet_influence_score REAL
                    NOT NULL DEFAULT 0,

                first_trade_timestamp INTEGER,
                last_trade_timestamp INTEGER,

                created_at TEXT NOT NULL,

                FOREIGN KEY(signal_key)
                    REFERENCES smart_money_flow_signals(signal_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
            idx_smart_money_flow_wallet_events_market
            ON smart_money_flow_wallet_events(
                condition_id,
                event_type,
                net_flow_change DESC
            );

            CREATE TABLE IF NOT EXISTS smart_money_flow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                lookback_hours INTEGER NOT NULL,

                current_snapshot_at TEXT,
                previous_snapshot_at TEXT,

                current_markets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                previous_markets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                signals_saved INTEGER
                    NOT NULL DEFAULT 0,

                wallet_events_saved INTEGER
                    NOT NULL DEFAULT 0,

                actionable_signals INTEGER
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
# SNAPSHOT LOADING
# =============================================================================


def load_snapshot_times(
    lookback_hours: int,
) -> list[str]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT DISTINCT snapshot_at
            FROM market_memory_snapshots
            WHERE lookback_hours = ?
            ORDER BY snapshot_at DESC
            """,
            (
                lookback_hours,
            ),
        ).fetchall()

        return [
            clean_text(
                row["snapshot_at"]
            )
            for row in rows
            if clean_text(
                row["snapshot_at"]
            )
        ]

    finally:
        connection.close()


def load_snapshots_at(
    snapshot_at: str,
    lookback_hours: int,
) -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM market_memory_snapshots
            WHERE snapshot_at = ?
              AND lookback_hours = ?
            """,
            (
                snapshot_at,
                lookback_hours,
            ),
        ).fetchall()

        return {
            clean_text(
                row["condition_id"]
            ).lower(): dict(row)
            for row in rows
            if clean_text(
                row["condition_id"]
            )
        }

    finally:
        connection.close()


def load_wallet_flows(
    snapshot_key: str,
) -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM market_memory_wallet_flows
            WHERE snapshot_key = ?
            """,
            (
                snapshot_key,
            ),
        ).fetchall()

        return {
            clean_text(
                row["wallet"]
            ).lower(): dict(row)
            for row in rows
            if clean_text(
                row["wallet"]
            )
        }

    finally:
        connection.close()


# =============================================================================
# SCORING
# =============================================================================


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


def confidence_label(
    wallet_count: int,
    gross_flow: float,
    has_previous: bool,
    persistent_wallets: int,
) -> str:
    points = 0

    if wallet_count >= 5:
        points += 2
    elif wallet_count >= 2:
        points += 1

    if gross_flow >= 100_000:
        points += 2
    elif gross_flow >= 10_000:
        points += 1

    if has_previous:
        points += 1

    if persistent_wallets >= 2:
        points += 1

    if points >= 5:
        return "HIGH"

    if points >= 3:
        return "MEDIUM"

    return "LOW"


def action_from_scores(
    score: float,
    accumulation_score: float,
    distribution_score: float,
    data_confidence: str,
) -> str:
    if data_confidence == "LOW":
        return "WATCH"

    if (
        score >= 75
        and accumulation_score >= 65
    ):
        return "STRONG ACCUMULATION"

    if (
        score >= 60
        and accumulation_score >= 55
    ):
        return "ACCUMULATION"

    if (
        score >= 60
        and distribution_score >= 55
    ):
        return "DISTRIBUTION"

    if score >= 45:
        return "WATCH"

    return "IGNORE"


def flow_direction(
    net_flow: float,
    gross_flow: float,
) -> str:
    ratio = divide(
        net_flow,
        gross_flow,
        0.0,
    )

    if ratio >= 0.10:
        return "INFLOW"

    if ratio <= -0.10:
        return "OUTFLOW"

    return "NEUTRAL"


def wallet_event_type(
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> str:
    if previous is None and current is not None:
        return "ENTERED"

    if previous is not None and current is None:
        return "EXITED"

    if previous is None or current is None:
        return "UNKNOWN"

    previous_direction = clean_text(
        previous.get(
            "directional_label"
        )
    ).upper()

    current_direction = clean_text(
        current.get(
            "directional_label"
        )
    ).upper()

    if (
        previous_direction != current_direction
        and current_direction
        in {
            "BULLISH",
            "BEARISH",
        }
    ):
        return "FLIPPED"

    previous_net = safe_float(
        previous.get(
            "net_flow"
        )
    )

    current_net = safe_float(
        current.get(
            "net_flow"
        )
    )

    if abs(
        current_net
    ) > abs(
        previous_net
    ) * 1.25:
        return "ACCELERATED"

    if abs(
        current_net
    ) < abs(
        previous_net
    ) * 0.75:
        return "DECELERATED"

    return "PERSISTED"


def build_signals(
    lookback_hours: int,
    minimum_gross_flow: float,
    minimum_wallets: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
    str | None,
    int,
    int,
]:
    snapshot_times = load_snapshot_times(
        lookback_hours
    )

    if not snapshot_times:
        raise RuntimeError(
            "No market memory snapshots exist for the selected "
            f"{lookback_hours}-hour lookback."
        )

    current_snapshot_at = snapshot_times[
        0
    ]

    previous_snapshot_at = (
        snapshot_times[1]
        if len(snapshot_times) >= 2
        else None
    )

    current_snapshots = load_snapshots_at(
        current_snapshot_at,
        lookback_hours,
    )

    previous_snapshots = (
        load_snapshots_at(
            previous_snapshot_at,
            lookback_hours,
        )
        if previous_snapshot_at
        else {}
    )

    current_time = parse_iso(
        current_snapshot_at
    )

    previous_time = parse_iso(
        previous_snapshot_at
    )

    elapsed_hours = (
        (
            current_time
            - previous_time
        ).total_seconds()
        / 3600.0
        if current_time
        and previous_time
        else float(
            lookback_hours
        )
    )

    elapsed_hours = max(
        elapsed_hours,
        0.01,
    )

    signals: list[
        dict[str, Any]
    ] = []

    wallet_events: list[
        dict[str, Any]
    ] = []

    observed_at = utc_now_iso()

    for condition_id, current in current_snapshots.items():
        current_gross = safe_float(
            current.get(
                "gross_flow"
            )
        )

        current_wallet_count = safe_int(
            current.get(
                "unique_wallet_count"
            )
        )

        if (
            current_gross
            < minimum_gross_flow
            or current_wallet_count
            < minimum_wallets
        ):
            continue

        previous = previous_snapshots.get(
            condition_id
        )

        previous_snapshot_key = (
            clean_text(
                previous.get(
                    "snapshot_key"
                )
            )
            if previous
            else ""
        )

        current_snapshot_key = clean_text(
            current.get(
                "snapshot_key"
            )
        )

        current_wallet_flows = load_wallet_flows(
            current_snapshot_key
        )

        previous_wallet_flows = (
            load_wallet_flows(
                previous_snapshot_key
            )
            if previous_snapshot_key
            else {}
        )

        current_wallets = set(
            current_wallet_flows
        )

        previous_wallets = set(
            previous_wallet_flows
        )

        new_wallets = (
            current_wallets
            - previous_wallets
        )

        exited_wallets = (
            previous_wallets
            - current_wallets
        )

        persistent_wallets = (
            current_wallets
            & previous_wallets
        )

        previous_net_flow = (
            safe_float(
                previous.get(
                    "net_flow"
                )
            )
            if previous
            else 0.0
        )

        previous_gross_flow = (
            safe_float(
                previous.get(
                    "gross_flow"
                )
            )
            if previous
            else 0.0
        )

        current_net_flow = safe_float(
            current.get(
                "net_flow"
            )
        )

        net_flow_change = (
            current_net_flow
            - previous_net_flow
        )

        gross_flow_change = (
            current_gross
            - previous_gross_flow
        )

        net_flow_velocity = (
            net_flow_change
            / elapsed_hours
        )

        gross_flow_velocity = (
            gross_flow_change
            / elapsed_hours
        )

        previous_velocity = divide(
            previous_net_flow,
            float(
                lookback_hours
            ),
            0.0,
        )

        flow_acceleration = (
            net_flow_velocity
            - previous_velocity
        )

        buy_notional = safe_float(
            current.get(
                "buy_notional"
            )
        )

        sell_notional = safe_float(
            current.get(
                "sell_notional"
            )
        )

        buy_sell_imbalance = divide(
            buy_notional
            - sell_notional,
            buy_notional
            + sell_notional,
            0.0,
        )

        trusted_buy = (
            safe_float(
                current.get(
                    "elite_buy_notional"
                )
            )
            + safe_float(
                current.get(
                    "qualified_buy_notional"
                )
            )
            + safe_float(
                current.get(
                    "watchlist_buy_notional"
                )
            )
        )

        trusted_sell = (
            safe_float(
                current.get(
                    "elite_sell_notional"
                )
            )
            + safe_float(
                current.get(
                    "qualified_sell_notional"
                )
            )
            + safe_float(
                current.get(
                    "watchlist_sell_notional"
                )
            )
        )

        trusted_net = (
            trusted_buy
            - trusted_sell
        )

        elite_net_flow = (
            safe_float(
                current.get(
                    "elite_buy_notional"
                )
            )
            - safe_float(
                current.get(
                    "elite_sell_notional"
                )
            )
        )

        qualified_net_flow = (
            safe_float(
                current.get(
                    "qualified_buy_notional"
                )
            )
            - safe_float(
                current.get(
                    "qualified_sell_notional"
                )
            )
        )

        watchlist_net_flow = (
            safe_float(
                current.get(
                    "watchlist_buy_notional"
                )
            )
            - safe_float(
                current.get(
                    "watchlist_sell_notional"
                )
            )
        )

        largest_buyer_notional = safe_float(
            current.get(
                "largest_buyer_notional"
            )
        )

        largest_seller_notional = safe_float(
            current.get(
                "largest_seller_notional"
            )
        )

        whale_concentration = clamp(
            divide(
                max(
                    largest_buyer_notional,
                    largest_seller_notional,
                ),
                max(
                    current_gross,
                    1.0,
                ),
                0.0,
            )
            * 100.0
        )

        persistence_score = clamp(
            divide(
                len(
                    persistent_wallets
                ),
                max(
                    len(
                        current_wallets
                        | previous_wallets
                    ),
                    1,
                ),
                0.0,
            )
            * 100.0
        )

        breadth_score = clamp(
            current_wallet_count
            / 8.0
            * 100.0
        )

        velocity_score = clamp(
            math.log1p(
                abs(
                    net_flow_velocity
                )
            )
            / math.log1p(
                100_000.0
            )
            * 100.0
        )

        acceleration_score = clamp(
            math.log1p(
                abs(
                    flow_acceleration
                )
            )
            / math.log1p(
                100_000.0
            )
            * 100.0
        )

        imbalance_score = clamp(
            abs(
                buy_sell_imbalance
            )
            * 100.0
        )

        trusted_flow_score = clamp(
            divide(
                abs(
                    trusted_net
                ),
                max(
                    current_gross,
                    1.0,
                ),
                0.0,
            )
            * 100.0
        )

        consensus_strength = safe_float(
            current.get(
                "consensus_strength"
            )
        )

        concentration_risk = safe_float(
            current.get(
                "concentration_risk"
            )
        )

        positive_flow_component = clamp(
            divide(
                max(
                    current_net_flow,
                    0.0,
                ),
                max(
                    current_gross,
                    1.0,
                ),
                0.0,
            )
            * 100.0
        )

        negative_flow_component = clamp(
            divide(
                max(
                    -current_net_flow,
                    0.0,
                ),
                max(
                    current_gross,
                    1.0,
                ),
                0.0,
            )
            * 100.0
        )

        accumulation_score = clamp(
            positive_flow_component
            * 0.30
            + consensus_strength
            * 0.20
            + persistence_score
            * 0.15
            + breadth_score
            * 0.10
            + velocity_score
            * 0.10
            + acceleration_score
            * 0.05
            + trusted_flow_score
            * 0.10
            - concentration_risk
            * 0.15
        )

        distribution_score = clamp(
            negative_flow_component
            * 0.35
            + consensus_strength
            * 0.20
            + persistence_score
            * 0.15
            + velocity_score
            * 0.10
            + acceleration_score
            * 0.10
            + trusted_flow_score
            * 0.10
            - concentration_risk
            * 0.15
        )

        rotation_score = clamp(
            divide(
                len(
                    new_wallets
                )
                + len(
                    exited_wallets
                ),
                max(
                    current_wallet_count
                    + safe_int(
                        previous.get(
                            "unique_wallet_count"
                        )
                    )
                    if previous
                    else current_wallet_count,
                    1,
                ),
                0.0,
            )
            * 100.0
            + acceleration_score
            * 0.25
        )

        dominant_score = max(
            accumulation_score,
            distribution_score,
        )

        smart_money_flow_score = clamp(
            dominant_score
            * 0.45
            + consensus_strength
            * 0.15
            + persistence_score
            * 0.10
            + breadth_score
            * 0.10
            + velocity_score
            * 0.08
            + acceleration_score
            * 0.05
            + trusted_flow_score
            * 0.07
            - whale_concentration
            * 0.10
        )

        direction = flow_direction(
            current_net_flow,
            current_gross,
        )

        confidence = confidence_label(
            wallet_count=(
                current_wallet_count
            ),
            gross_flow=current_gross,
            has_previous=(
                previous is not None
            ),
            persistent_wallets=len(
                persistent_wallets
            ),
        )

        action = action_from_scores(
            score=smart_money_flow_score,
            accumulation_score=(
                accumulation_score
            ),
            distribution_score=(
                distribution_score
            ),
            data_confidence=confidence,
        )

        actionable = int(
            action
            in {
                "STRONG ACCUMULATION",
                "ACCUMULATION",
                "DISTRIBUTION",
            }
        )

        positive_evidence: list[str] = []
        risk_flags: list[str] = []

        if current_wallet_count >= 5:
            positive_evidence.append(
                "Broad wallet participation"
            )

        if len(
            persistent_wallets
        ) >= 2:
            positive_evidence.append(
                "Persistent wallet participation"
            )

        if trusted_flow_score >= 50:
            positive_evidence.append(
                "Majority of flow came from trusted wallets"
            )

        if consensus_strength >= 75:
            positive_evidence.append(
                "Strong directional agreement"
            )

        if net_flow_velocity > 10_000:
            positive_evidence.append(
                "Rapid positive capital flow"
            )

        if net_flow_velocity < -10_000:
            positive_evidence.append(
                "Rapid capital outflow"
            )

        if whale_concentration >= 70:
            risk_flags.append(
                "Flow is dominated by one wallet"
            )

        if previous is None:
            risk_flags.append(
                "No prior same-window snapshot for comparison"
            )

        if current_wallet_count < 3:
            risk_flags.append(
                "Limited wallet breadth"
            )

        if current_gross < 10_000:
            risk_flags.append(
                "Low gross flow"
            )

        if confidence == "LOW":
            risk_flags.append(
                "Low data confidence"
            )

        signal_key = (
            f"{condition_id}:"
            f"{lookback_hours}:"
            f"{current_snapshot_at}"
        )

        signal = {
            "signal_key": signal_key,
            "condition_id": condition_id,
            "market_id": clean_text(
                current.get(
                    "market_id"
                )
            ),
            "event_id": clean_text(
                current.get(
                    "event_id"
                )
            ),
            "title": clean_text(
                current.get(
                    "title"
                )
            ),
            "slug": clean_text(
                current.get(
                    "slug"
                )
            ),
            "event_slug": clean_text(
                current.get(
                    "event_slug"
                )
            ),
            "category": clean_text(
                current.get(
                    "category"
                )
            ),
            "lookback_hours": (
                lookback_hours
            ),
            "current_snapshot_key": (
                current_snapshot_key
            ),
            "previous_snapshot_key": (
                previous_snapshot_key
                or None
            ),
            "current_snapshot_at": (
                current_snapshot_at
            ),
            "previous_snapshot_at": (
                previous_snapshot_at
            ),
            "elapsed_hours": (
                elapsed_hours
            ),
            "current_trade_count": safe_int(
                current.get(
                    "trade_count"
                )
            ),
            "previous_trade_count": (
                safe_int(
                    previous.get(
                        "trade_count"
                    )
                )
                if previous
                else 0
            ),
            "trade_count_change": (
                safe_int(
                    current.get(
                        "trade_count"
                    )
                )
                - (
                    safe_int(
                        previous.get(
                            "trade_count"
                        )
                    )
                    if previous
                    else 0
                )
            ),
            "current_unique_wallet_count": (
                current_wallet_count
            ),
            "previous_unique_wallet_count": (
                safe_int(
                    previous.get(
                        "unique_wallet_count"
                    )
                )
                if previous
                else 0
            ),
            "wallet_count_change": (
                current_wallet_count
                - (
                    safe_int(
                        previous.get(
                            "unique_wallet_count"
                        )
                    )
                    if previous
                    else 0
                )
            ),
            "new_wallet_count": len(
                new_wallets
            ),
            "exited_wallet_count": len(
                exited_wallets
            ),
            "persistent_wallet_count": len(
                persistent_wallets
            ),
            "bullish_wallet_count": (
                safe_int(
                    current.get(
                        "bullish_wallet_count"
                    )
                )
            ),
            "bearish_wallet_count": (
                safe_int(
                    current.get(
                        "bearish_wallet_count"
                    )
                )
            ),
            "current_buy_notional": (
                buy_notional
            ),
            "current_sell_notional": (
                sell_notional
            ),
            "current_net_flow": (
                current_net_flow
            ),
            "previous_net_flow": (
                previous_net_flow
            ),
            "net_flow_change": (
                net_flow_change
            ),
            "current_gross_flow": (
                current_gross
            ),
            "previous_gross_flow": (
                previous_gross_flow
            ),
            "gross_flow_change": (
                gross_flow_change
            ),
            "net_flow_velocity": (
                net_flow_velocity
            ),
            "gross_flow_velocity": (
                gross_flow_velocity
            ),
            "flow_acceleration": (
                flow_acceleration
            ),
            "buy_sell_imbalance": (
                buy_sell_imbalance
            ),
            "trusted_buy_notional": (
                trusted_buy
            ),
            "trusted_sell_notional": (
                trusted_sell
            ),
            "trusted_net_flow": (
                trusted_net
            ),
            "elite_net_flow": (
                elite_net_flow
            ),
            "qualified_net_flow": (
                qualified_net_flow
            ),
            "watchlist_net_flow": (
                watchlist_net_flow
            ),
            "largest_buyer_wallet": (
                clean_text(
                    current.get(
                        "largest_buyer_wallet"
                    )
                )
            ),
            "largest_buyer_notional": (
                largest_buyer_notional
            ),
            "largest_seller_wallet": (
                clean_text(
                    current.get(
                        "largest_seller_wallet"
                    )
                )
            ),
            "largest_seller_notional": (
                largest_seller_notional
            ),
            "whale_concentration": (
                whale_concentration
            ),
            "consensus_strength": (
                consensus_strength
            ),
            "concentration_risk": (
                concentration_risk
            ),
            "persistence_score": (
                persistence_score
            ),
            "breadth_score": (
                breadth_score
            ),
            "velocity_score": (
                velocity_score
            ),
            "acceleration_score": (
                acceleration_score
            ),
            "imbalance_score": (
                imbalance_score
            ),
            "trusted_flow_score": (
                trusted_flow_score
            ),
            "accumulation_score": (
                accumulation_score
            ),
            "distribution_score": (
                distribution_score
            ),
            "rotation_score": (
                rotation_score
            ),
            "smart_money_flow_score": (
                smart_money_flow_score
            ),
            "smart_money_flow_grade": (
                grade_from_score(
                    smart_money_flow_score
                )
            ),
            "flow_direction": direction,
            "recommended_action": action,
            "data_confidence": (
                confidence
            ),
            "is_actionable": actionable,
            "resolved": safe_int(
                current.get(
                    "resolved"
                )
            ),
            "winning_outcome": clean_text(
                current.get(
                    "winning_outcome"
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
            "metadata_json": stable_json(
                {
                    "model_version": "1.0",
                    "minimum_gross_flow": (
                        minimum_gross_flow
                    ),
                    "minimum_wallets": (
                        minimum_wallets
                    ),
                    "new_wallets": sorted(
                        new_wallets
                    ),
                    "exited_wallets": sorted(
                        exited_wallets
                    ),
                    "persistent_wallets": sorted(
                        persistent_wallets
                    ),
                }
            ),
            "observed_at": observed_at,
            "created_at": observed_at,
            "updated_at": observed_at,
        }

        signals.append(signal)

        all_wallets = (
            current_wallets
            | previous_wallets
        )

        for wallet in all_wallets:
            previous_flow = (
                previous_wallet_flows.get(
                    wallet
                )
            )

            current_flow = (
                current_wallet_flows.get(
                    wallet
                )
            )

            source = (
                current_flow
                or previous_flow
                or {}
            )

            event_type = wallet_event_type(
                previous_flow,
                current_flow,
            )

            previous_net = (
                safe_float(
                    previous_flow.get(
                        "net_flow"
                    )
                )
                if previous_flow
                else 0.0
            )

            current_net = (
                safe_float(
                    current_flow.get(
                        "net_flow"
                    )
                )
                if current_flow
                else 0.0
            )

            wallet_events.append(
                {
                    "event_key": (
                        f"{signal_key}:"
                        f"{wallet}:"
                        f"{event_type}"
                    ),
                    "signal_key": signal_key,
                    "condition_id": (
                        condition_id
                    ),
                    "wallet": wallet,
                    "event_type": (
                        event_type
                    ),
                    "previous_direction": (
                        clean_text(
                            previous_flow.get(
                                "directional_label"
                            )
                        )
                        if previous_flow
                        else ""
                    ),
                    "current_direction": (
                        clean_text(
                            current_flow.get(
                                "directional_label"
                            )
                        )
                        if current_flow
                        else ""
                    ),
                    "previous_net_flow": (
                        previous_net
                    ),
                    "current_net_flow": (
                        current_net
                    ),
                    "net_flow_change": (
                        current_net
                        - previous_net
                    ),
                    "wallet_status": clean_text(
                        source.get(
                            "wallet_status"
                        )
                    ),
                    "elite_tier": clean_text(
                        source.get(
                            "elite_tier"
                        )
                    ),
                    "consensus_weight": (
                        safe_float(
                            source.get(
                                "consensus_weight"
                            )
                        )
                    ),
                    "prediction_weight": (
                        safe_float(
                            source.get(
                                "prediction_weight"
                            )
                        )
                    ),
                    "wallet_influence_score": (
                        safe_float(
                            source.get(
                                "wallet_influence_score"
                            )
                        )
                    ),
                    "first_trade_timestamp": (
                        safe_int(
                            source.get(
                                "first_trade_timestamp"
                            )
                        )
                    ),
                    "last_trade_timestamp": (
                        safe_int(
                            source.get(
                                "last_trade_timestamp"
                            )
                        )
                    ),
                    "created_at": (
                        observed_at
                    ),
                }
            )

    signals.sort(
        key=lambda row: (
            row[
                "is_actionable"
            ],
            row[
                "smart_money_flow_score"
            ],
            abs(
                row[
                    "current_net_flow"
                ]
            ),
            row[
                "current_unique_wallet_count"
            ],
        ),
        reverse=True,
    )

    wallet_events.sort(
        key=lambda row: abs(
            row[
                "net_flow_change"
            ]
        ),
        reverse=True,
    )

    return (
        signals,
        wallet_events,
        current_snapshot_at,
        previous_snapshot_at,
        len(current_snapshots),
        len(previous_snapshots),
    )


# =============================================================================
# SAVE
# =============================================================================


SIGNAL_COLUMNS = [
    "signal_key",
    "condition_id",
    "market_id",
    "event_id",
    "title",
    "slug",
    "event_slug",
    "category",
    "lookback_hours",
    "current_snapshot_key",
    "previous_snapshot_key",
    "current_snapshot_at",
    "previous_snapshot_at",
    "elapsed_hours",
    "current_trade_count",
    "previous_trade_count",
    "trade_count_change",
    "current_unique_wallet_count",
    "previous_unique_wallet_count",
    "wallet_count_change",
    "new_wallet_count",
    "exited_wallet_count",
    "persistent_wallet_count",
    "bullish_wallet_count",
    "bearish_wallet_count",
    "current_buy_notional",
    "current_sell_notional",
    "current_net_flow",
    "previous_net_flow",
    "net_flow_change",
    "current_gross_flow",
    "previous_gross_flow",
    "gross_flow_change",
    "net_flow_velocity",
    "gross_flow_velocity",
    "flow_acceleration",
    "buy_sell_imbalance",
    "trusted_buy_notional",
    "trusted_sell_notional",
    "trusted_net_flow",
    "elite_net_flow",
    "qualified_net_flow",
    "watchlist_net_flow",
    "largest_buyer_wallet",
    "largest_buyer_notional",
    "largest_seller_wallet",
    "largest_seller_notional",
    "whale_concentration",
    "consensus_strength",
    "concentration_risk",
    "persistence_score",
    "breadth_score",
    "velocity_score",
    "acceleration_score",
    "imbalance_score",
    "trusted_flow_score",
    "accumulation_score",
    "distribution_score",
    "rotation_score",
    "smart_money_flow_score",
    "smart_money_flow_grade",
    "flow_direction",
    "recommended_action",
    "data_confidence",
    "is_actionable",
    "resolved",
    "winning_outcome",
    "positive_evidence_json",
    "risk_flags_json",
    "metadata_json",
    "observed_at",
    "created_at",
    "updated_at",
]


WALLET_EVENT_COLUMNS = [
    "event_key",
    "signal_key",
    "condition_id",
    "wallet",
    "event_type",
    "previous_direction",
    "current_direction",
    "previous_net_flow",
    "current_net_flow",
    "net_flow_change",
    "wallet_status",
    "elite_tier",
    "consensus_weight",
    "prediction_weight",
    "wallet_influence_score",
    "first_trade_timestamp",
    "last_trade_timestamp",
    "created_at",
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
        f'INSERT OR REPLACE INTO "{table_name}" '
        f'({names}) VALUES ({placeholders})'
    )


def save_signals(
    signals: list[dict[str, Any]],
    wallet_events: list[dict[str, Any]],
) -> tuple[int, int]:
    connection = connect_database()

    signal_query = build_insert_query(
        "smart_money_flow_signals",
        SIGNAL_COLUMNS,
    )

    wallet_event_query = build_insert_query(
        "smart_money_flow_wallet_events",
        WALLET_EVENT_COLUMNS,
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for row in signals:
            connection.execute(
                signal_query,
                tuple(
                    row[column]
                    for column in SIGNAL_COLUMNS
                ),
            )

        for row in wallet_events:
            connection.execute(
                wallet_event_query,
                tuple(
                    row[column]
                    for column in WALLET_EVENT_COLUMNS
                ),
            )

        connection.commit()

        return (
            len(signals),
            len(wallet_events),
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
    lookback_hours: int,
) -> tuple[int, datetime]:
    started_at = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO smart_money_flow_runs (
                started_at,
                lookback_hours,
                status
            )
            VALUES (
                ?, ?, 'RUNNING'
            )
            """,
            (
                started_at.isoformat(),
                lookback_hours,
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
    current_snapshot_at: str,
    previous_snapshot_at: str | None,
    current_markets_loaded: int,
    previous_markets_loaded: int,
    signals_saved: int,
    wallet_events_saved: int,
    actionable_signals: int,
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE smart_money_flow_runs
            SET
                finished_at = ?,
                elapsed_seconds = ?,
                current_snapshot_at = ?,
                previous_snapshot_at = ?,
                current_markets_loaded = ?,
                previous_markets_loaded = ?,
                signals_saved = ?,
                wallet_events_saved = ?,
                actionable_signals = ?,
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
                current_snapshot_at,
                previous_snapshot_at,
                current_markets_loaded,
                previous_markets_loaded,
                signals_saved,
                wallet_events_saved,
                actionable_signals,
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
    signals: list[dict[str, Any]],
    wallet_events: list[dict[str, Any]],
    current_snapshot_at: str,
    previous_snapshot_at: str | None,
    display_limit: int,
) -> None:
    print()
    print("=" * 116)
    print("SMART MONEY FLOW ENGINE SUMMARY")
    print("=" * 116)

    print(
        f"Current snapshot:               "
        f"{current_snapshot_at}"
    )

    print(
        f"Previous snapshot:              "
        f"{previous_snapshot_at or 'NONE'}"
    )

    print(
        f"Market signals created:         "
        f"{len(signals)}"
    )

    print(
        f"Wallet flow events created:     "
        f"{len(wallet_events)}"
    )

    print(
        f"Actionable signals:             "
        f"{sum(1 for row in signals if row['is_actionable'])}"
    )

    print(
        f"Accumulation signals:           "
        f"{sum(1 for row in signals if row['recommended_action'] in {'STRONG ACCUMULATION', 'ACCUMULATION'})}"
    )

    print(
        f"Distribution signals:           "
        f"{sum(1 for row in signals if row['recommended_action'] == 'DISTRIBUTION')}"
    )

    print("=" * 116)

    print()
    print("TOP SMART MONEY FLOW SIGNALS")

    for rank, row in enumerate(
        signals[:display_limit],
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
        print("-" * 116)

        print(
            f"{rank}. "
            f"{row['title'] or row['slug'] or row['condition_id']}"
        )

        print("-" * 116)

        print(
            f"Score / grade / action:         "
            f"{row['smart_money_flow_score']:.1f} "
            f"/ {row['smart_money_flow_grade']} "
            f"/ {row['recommended_action']}"
        )

        print(
            f"Direction / confidence:         "
            f"{row['flow_direction']} "
            f"/ {row['data_confidence']}"
        )

        print(
            f"Current net / change:           "
            f"{format_money(row['current_net_flow'])} "
            f"/ {format_money(row['net_flow_change'])}"
        )

        print(
            f"Velocity / acceleration:        "
            f"{format_money(row['net_flow_velocity'])}/hr "
            f"/ {format_money(row['flow_acceleration'])}/hr"
        )

        print(
            f"Wallets current/new/exited:     "
            f"{row['current_unique_wallet_count']} "
            f"/ {row['new_wallet_count']} "
            f"/ {row['exited_wallet_count']}"
        )

        print(
            f"Persistent wallets:             "
            f"{row['persistent_wallet_count']}"
        )

        print(
            f"Trusted net flow:               "
            f"{format_money(row['trusted_net_flow'])}"
        )

        print(
            f"Accumulation / distribution:    "
            f"{row['accumulation_score']:.1f} "
            f"/ {row['distribution_score']:.1f}"
        )

        print(
            f"Rotation / persistence:         "
            f"{row['rotation_score']:.1f} "
            f"/ {row['persistence_score']:.1f}"
        )

        print(
            f"Consensus / concentration:      "
            f"{row['consensus_strength']:.1f} "
            f"/ {row['concentration_risk']:.1f}"
        )

        print(
            f"Largest buyer:                  "
            f"{row['largest_buyer_wallet'] or '-'} "
            f"(${row['largest_buyer_notional']:,.2f})"
        )

        print(
            f"Largest seller:                 "
            f"{row['largest_seller_wallet'] or '-'} "
            f"(${row['largest_seller_notional']:,.2f})"
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
# MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare market-memory snapshots with the same lookback "
            "window to identify accumulation, distribution, capital "
            "velocity, wallet entry/exit and smart-money rotation."
        )
    )

    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=DEFAULT_LOOKBACK_HOURS,
    )

    parser.add_argument(
        "--minimum-gross-flow",
        type=float,
        default=DEFAULT_MIN_GROSS_FLOW,
    )

    parser.add_argument(
        "--minimum-wallets",
        type=int,
        default=DEFAULT_MIN_WALLETS,
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8()
    arguments = parse_arguments()

    lookback_hours = max(
        arguments.lookback_hours,
        1,
    )

    minimum_gross_flow = max(
        arguments.minimum_gross_flow,
        0.0,
    )

    minimum_wallets = max(
        arguments.minimum_wallets,
        1,
    )

    print()
    print("=" * 116)
    print("POLYMARKET SMART MONEY FLOW ENGINE v1")
    print("=" * 116)

    print(
        f"Database:                    {DB}"
    )

    print(
        f"Memory lookback:             "
        f"{lookback_hours} hours"
    )

    print(
        f"Minimum gross flow:          "
        f"${minimum_gross_flow:,.2f}"
    )

    print(
        f"Minimum wallets:             "
        f"{minimum_wallets}"
    )

    print(
        "Method:                     "
        "SNAPSHOT DELTAS + WALLET ENTRY/EXIT + FLOW VELOCITY"
    )

    print("=" * 116)

    create_tables()

    run_id, started_at = start_run(
        lookback_hours
    )

    signals: list[
        dict[str, Any]
    ] = []

    wallet_events: list[
        dict[str, Any]
    ] = []

    current_snapshot_at = ""
    previous_snapshot_at: str | None = None
    current_markets_loaded = 0
    previous_markets_loaded = 0
    signals_saved = 0
    wallet_events_saved = 0

    try:
        (
            signals,
            wallet_events,
            current_snapshot_at,
            previous_snapshot_at,
            current_markets_loaded,
            previous_markets_loaded,
        ) = build_signals(
            lookback_hours=(
                lookback_hours
            ),
            minimum_gross_flow=(
                minimum_gross_flow
            ),
            minimum_wallets=(
                minimum_wallets
            ),
        )

        if not signals:
            raise RuntimeError(
                "No market signals passed the selected minimum "
                "gross-flow and wallet filters."
            )

        (
            signals_saved,
            wallet_events_saved,
        ) = save_signals(
            signals=signals,
            wallet_events=wallet_events,
        )

        actionable_signals = sum(
            1
            for row in signals
            if row[
                "is_actionable"
            ]
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            current_snapshot_at=(
                current_snapshot_at
            ),
            previous_snapshot_at=(
                previous_snapshot_at
            ),
            current_markets_loaded=(
                current_markets_loaded
            ),
            previous_markets_loaded=(
                previous_markets_loaded
            ),
            signals_saved=(
                signals_saved
            ),
            wallet_events_saved=(
                wallet_events_saved
            ),
            actionable_signals=(
                actionable_signals
            ),
        )

        display_summary(
            signals=signals,
            wallet_events=wallet_events,
            current_snapshot_at=(
                current_snapshot_at
            ),
            previous_snapshot_at=(
                previous_snapshot_at
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 116)
        print("SMART MONEY FLOW ENGINE COMPLETE")
        print("=" * 116)

        print(
            "Market flow signals:         "
            "smart_money_flow_signals"
        )

        print(
            "Wallet flow events:          "
            "smart_money_flow_wallet_events"
        )

        print(
            "Run history:                 "
            "smart_money_flow_runs"
        )

        print("=" * 116)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            current_snapshot_at=(
                current_snapshot_at
            ),
            previous_snapshot_at=(
                previous_snapshot_at
            ),
            current_markets_loaded=(
                current_markets_loaded
            ),
            previous_markets_loaded=(
                previous_markets_loaded
            ),
            signals_saved=(
                signals_saved
            ),
            wallet_events_saved=(
                wallet_events_saved
            ),
            actionable_signals=sum(
                1
                for row in signals
                if row.get(
                    "is_actionable"
                )
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()