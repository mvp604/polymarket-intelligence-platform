from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

ENGINE_VERSION = "2.0"
EPSILON = 1e-9


@dataclass(frozen=True)
class ReconciledPosition:
    performance_market_key: str
    wallet: str
    market_id: str
    title: str | None
    selected_outcome: str | None
    gamma_market_id: str | None
    condition_id: str | None
    resolution_status: str
    winning_outcome_name: str | None
    source_outcome_won: int | None
    source_outcome_lost: int | None
    shares: float
    average_entry_price: float
    cost_basis: float
    settlement_price: float | None
    settlement_value: float | None
    estimated_profit: float | None
    estimated_roi: float | None
    brier_score: float | None
    match_method: str
    match_confidence: float
    resolved_at: str | None
    observed_at: str | None
    realized_pnl: float
    data_quality: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().casefold().split())


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


def as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


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
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not table_exists(connection, table_name):
        return set()

    return {
        str(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def require_tables(
    connection: sqlite3.Connection,
    table_names: Iterable[str],
) -> None:
    missing = [
        table_name
        for table_name in table_names
        if not table_exists(connection, table_name)
    ]
    if missing:
        raise RuntimeError(
            "Required table(s) missing: " + ", ".join(missing)
        )


def ensure_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS
            idx_wcps_wallet_condition_outcome
        ON wallet_closed_position_snapshots(
            wallet,
            condition_id,
            outcome
        );

        CREATE INDEX IF NOT EXISTS
            idx_wcps_condition_id
        ON wallet_closed_position_snapshots(condition_id);

        CREATE INDEX IF NOT EXISTS
            idx_wpm_wallet
        ON wallet_performance_markets(wallet);

        CREATE INDEX IF NOT EXISTS
            idx_wpm_condition_id
        ON wallet_performance_markets(condition_id);
        """
    )


def latest_closed_snapshots(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    """
    Keep the latest snapshot for each wallet + condition + outcome.

    Closed-position snapshots can repeat across collection runs. Without this
    deduplication, wallet performance would count the same closed position
    multiple times.
    """
    return connection.execute(
        """
        WITH ranked AS (
            SELECT
                snapshot.*,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        LOWER(TRIM(snapshot.wallet)),
                        LOWER(TRIM(COALESCE(snapshot.condition_id, ''))),
                        LOWER(TRIM(COALESCE(snapshot.outcome, '')))
                    ORDER BY
                        COALESCE(snapshot.closed_timestamp, 0) DESC,
                        snapshot.observed_at DESC,
                        snapshot.id DESC
                ) AS row_rank
            FROM wallet_closed_position_snapshots AS snapshot
            WHERE snapshot.wallet IS NOT NULL
              AND TRIM(snapshot.wallet) <> ''
              AND snapshot.condition_id IS NOT NULL
              AND TRIM(snapshot.condition_id) <> ''
              AND snapshot.outcome IS NOT NULL
              AND TRIM(snapshot.outcome) <> ''
        )
        SELECT *
        FROM ranked
        WHERE row_rank = 1
        ORDER BY wallet, condition_id, outcome
        """
    ).fetchall()


def load_mapped_results(
    connection: sqlite3.Connection,
) -> dict[tuple[str, str], dict[str, Any]]:
    """
    Load mapped outcomes when the table exists.

    The audit showed mapped results using source_market_id/condition_id,
    source_outcome, resolution_status, winning_outcome_name,
    source_outcome_won/lost, settlement_price, and match confidence.
    """
    if not table_exists(connection, "mapped_market_results"):
        return {}

    columns = table_columns(connection, "mapped_market_results")
    required = {"condition_id", "source_outcome"}
    if not required.issubset(columns):
        return {}

    select_columns = [
        column
        for column in [
            "condition_id",
            "source_market_id",
            "source_outcome",
            "gamma_market_id",
            "resolution_status",
            "winning_outcome_name",
            "source_outcome_won",
            "source_outcome_lost",
            "settlement_price",
            "match_method",
            "match_confidence",
            "resolved_at_detected",
            "calculated_at",
            "updated_at",
        ]
        if column in columns
    ]

    order_column = next(
        (
            column
            for column in ["updated_at", "calculated_at"]
            if column in columns
        ),
        None,
    )

    query = (
        "SELECT "
        + ", ".join(f'"{column}"' for column in select_columns)
        + ' FROM "mapped_market_results"'
    )
    if order_column:
        query += f' ORDER BY "{order_column}" ASC'

    results: dict[tuple[str, str], dict[str, Any]] = {}
    for row in connection.execute(query).fetchall():
        item = dict(row)
        key = (
            normalize_text(item.get("condition_id")),
            normalize_text(item.get("source_outcome")),
        )
        if key[0] and key[1]:
            results[key] = item

    return results


def load_canonical_markets(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, Any]]:
    if not table_exists(connection, "canonical_market_identities"):
        return {}

    columns = table_columns(connection, "canonical_market_identities")
    wanted = [
        column
        for column in [
            "condition_id",
            "gamma_market_id",
            "question",
            "yes_outcome_name",
            "no_outcome_name",
            "yes_implied_price",
            "no_implied_price",
            "closed",
            "resolved",
            "last_built_at",
        ]
        if column in columns
    ]

    rows = connection.execute(
        "SELECT "
        + ", ".join(f'"{column}"' for column in wanted)
        + ' FROM "canonical_market_identities"'
    ).fetchall()

    return {
        normalize_text(row["condition_id"]): dict(row)
        for row in rows
        if normalize_text(row["condition_id"])
    }


def infer_snapshot_resolution(
    snapshot: sqlite3.Row,
) -> tuple[str, str | None, int | None, int | None, float | None, str, float]:
    """
    Conservative fallback when mapped_market_results has no resolved row.

    A closed-position snapshot with current_price exactly 1 or 0 is treated as
    settlement evidence. Intermediate prices remain unresolved.
    """
    current_price = as_float(snapshot["current_price"], default=-1.0)
    selected_outcome = str(snapshot["outcome"]).strip()
    opposite_outcome = (
        str(snapshot["opposite_outcome"]).strip()
        if snapshot["opposite_outcome"] not in (None, "")
        else None
    )

    if current_price >= 1.0 - EPSILON:
        return (
            "RESOLVED",
            selected_outcome,
            1,
            0,
            1.0,
            "CLOSED_SNAPSHOT_PRICE",
            95.0,
        )

    if 0.0 <= current_price <= EPSILON:
        return (
            "RESOLVED",
            opposite_outcome,
            0,
            1,
            0.0,
            "CLOSED_SNAPSHOT_PRICE",
            95.0,
        )

    return (
        "UNRESOLVED",
        None,
        None,
        None,
        None,
        "NO_VERIFIED_RESOLUTION",
        0.0,
    )


def reconcile_snapshot(
    snapshot: sqlite3.Row,
    mapped_results: dict[tuple[str, str], dict[str, Any]],
    canonical_markets: dict[str, dict[str, Any]],
) -> ReconciledPosition:
    wallet = str(snapshot["wallet"]).strip().lower()
    condition_id = str(snapshot["condition_id"]).strip()
    selected_outcome = str(snapshot["outcome"]).strip()
    outcome_key = normalize_text(selected_outcome)
    condition_key = normalize_text(condition_id)

    mapped = mapped_results.get((condition_key, outcome_key))
    canonical = canonical_markets.get(condition_key, {})

    resolution_status = "UNRESOLVED"
    winning_outcome_name: str | None = None
    won: int | None = None
    lost: int | None = None
    settlement_price: float | None = None
    match_method = "NO_VERIFIED_RESOLUTION"
    match_confidence = 0.0
    resolved_at: str | None = None

    if mapped:
        mapped_status = normalize_text(mapped.get("resolution_status"))
        mapped_won = as_int(mapped.get("source_outcome_won"))
        mapped_lost = as_int(mapped.get("source_outcome_lost"))
        mapped_settlement = mapped.get("settlement_price")

        is_resolved = (
            mapped_won in {0, 1}
            or mapped_lost in {0, 1}
            or mapped_settlement not in (None, "")
            or mapped_status in {
                "resolved",
                "likely_resolved",
                "final",
                "settled",
            }
        )

        if is_resolved and (
            mapped_won in {0, 1}
            or mapped_lost in {0, 1}
        ):
            resolution_status = str(
                mapped.get("resolution_status") or "RESOLVED"
            ).strip().upper()
            winning_outcome_name = (
                str(mapped.get("winning_outcome_name")).strip()
                if mapped.get("winning_outcome_name") not in (None, "")
                else None
            )
            won = mapped_won
            lost = mapped_lost
            settlement_price = (
                as_float(mapped_settlement)
                if mapped_settlement not in (None, "")
                else float(won)
            )
            match_method = str(
                mapped.get("match_method") or "MAPPED_RESULT"
            )
            match_confidence = as_float(
                mapped.get("match_confidence")
            )
            resolved_at = (
                str(mapped.get("resolved_at_detected")).strip()
                if mapped.get("resolved_at_detected") not in (None, "")
                else None
            )

    if won is None and lost is None:
        (
            resolution_status,
            winning_outcome_name,
            won,
            lost,
            settlement_price,
            match_method,
            match_confidence,
        ) = infer_snapshot_resolution(snapshot)

    total_bought = max(0.0, as_float(snapshot["total_bought"]))
    average_entry_price = clamp(
        as_float(snapshot["avg_price"]),
        0.0,
        1.0,
    )
    cost_basis = total_bought * average_entry_price
    realized_pnl = as_float(snapshot["realized_pnl"])

    settlement_value: float | None = None
    estimated_profit: float | None = None
    estimated_roi: float | None = None
    brier_score: float | None = None

    if won in {0, 1}:
        if settlement_price is None:
            settlement_price = float(won)

        settlement_value = total_bought * settlement_price

        # Prefer the closed-position API's realized PnL when present.
        # It reflects actual trading activity better than a pure hold-to-
        # settlement calculation.
        if abs(realized_pnl) > EPSILON:
            estimated_profit = realized_pnl
        else:
            estimated_profit = settlement_value - cost_basis

        if cost_basis > EPSILON:
            estimated_roi = estimated_profit / cost_basis

        predicted_probability = average_entry_price
        actual_result = float(won)
        brier_score = (predicted_probability - actual_result) ** 2

    gamma_market_id = (
        str(mapped.get("gamma_market_id")).strip()
        if mapped and mapped.get("gamma_market_id") not in (None, "")
        else (
            str(canonical.get("gamma_market_id")).strip()
            if canonical.get("gamma_market_id") not in (None, "")
            else None
        )
    )

    closed_timestamp = snapshot["closed_timestamp"]
    if resolved_at is None and closed_timestamp not in (None, ""):
        try:
            resolved_at = datetime.fromtimestamp(
                int(closed_timestamp),
                tz=timezone.utc,
            ).isoformat()
        except (TypeError, ValueError, OSError):
            resolved_at = None

    data_quality = (
        "HIGH"
        if won in {0, 1} and match_confidence >= 95.0
        else "MEDIUM"
        if won in {0, 1}
        else "LOW"
    )

    performance_market_key = (
        f"closed_snapshot:{wallet}:{condition_key}:{outcome_key}"
    )

    return ReconciledPosition(
        performance_market_key=performance_market_key,
        wallet=wallet,
        market_id=condition_id,
        title=(
            str(snapshot["title"]).strip()
            if snapshot["title"] not in (None, "")
            else canonical.get("question")
        ),
        selected_outcome=selected_outcome,
        gamma_market_id=gamma_market_id,
        condition_id=condition_id,
        resolution_status=resolution_status,
        winning_outcome_name=winning_outcome_name,
        source_outcome_won=won,
        source_outcome_lost=lost,
        shares=total_bought,
        average_entry_price=average_entry_price,
        cost_basis=cost_basis,
        settlement_price=settlement_price,
        settlement_value=settlement_value,
        estimated_profit=estimated_profit,
        estimated_roi=estimated_roi,
        brier_score=brier_score,
        match_method=match_method,
        match_confidence=match_confidence,
        resolved_at=resolved_at,
        observed_at=(
            str(snapshot["observed_at"]).strip()
            if snapshot["observed_at"] not in (None, "")
            else None
        ),
        realized_pnl=realized_pnl,
        data_quality=data_quality,
    )


def upsert_performance_market(
    connection: sqlite3.Connection,
    position: ReconciledPosition,
    calculated_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO wallet_performance_markets (
            performance_market_key,
            wallet,
            scan_id,
            scanned_at,
            market_id,
            title,
            selected_outcome,
            gamma_market_id,
            condition_id,
            resolution_status,
            winning_outcome_name,
            source_outcome_won,
            source_outcome_lost,
            shares,
            average_entry_price,
            cost_basis,
            settlement_price,
            settlement_value,
            estimated_profit,
            estimated_roi,
            brier_score,
            match_method,
            match_confidence,
            calculated_at,
            updated_at
        )
        VALUES (
            ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        ON CONFLICT(performance_market_key) DO UPDATE SET
            wallet = excluded.wallet,
            scanned_at = excluded.scanned_at,
            market_id = excluded.market_id,
            title = excluded.title,
            selected_outcome = excluded.selected_outcome,
            gamma_market_id = excluded.gamma_market_id,
            condition_id = excluded.condition_id,
            resolution_status = excluded.resolution_status,
            winning_outcome_name = excluded.winning_outcome_name,
            source_outcome_won = excluded.source_outcome_won,
            source_outcome_lost = excluded.source_outcome_lost,
            shares = excluded.shares,
            average_entry_price = excluded.average_entry_price,
            cost_basis = excluded.cost_basis,
            settlement_price = excluded.settlement_price,
            settlement_value = excluded.settlement_value,
            estimated_profit = excluded.estimated_profit,
            estimated_roi = excluded.estimated_roi,
            brier_score = excluded.brier_score,
            match_method = excluded.match_method,
            match_confidence = excluded.match_confidence,
            calculated_at = excluded.calculated_at,
            updated_at = excluded.updated_at
        """,
        (
            position.performance_market_key,
            position.wallet,
            position.observed_at,
            position.market_id,
            position.title,
            position.selected_outcome,
            position.gamma_market_id,
            position.condition_id,
            position.resolution_status,
            position.winning_outcome_name,
            position.source_outcome_won,
            position.source_outcome_lost,
            position.shares,
            position.average_entry_price,
            position.cost_basis,
            position.settlement_price,
            position.settlement_value,
            position.estimated_profit,
            position.estimated_roi,
            position.brier_score,
            position.match_method,
            position.match_confidence,
            calculated_at,
            calculated_at,
        ),
    )


def score_sample_size(resolved_positions: int) -> float:
    if resolved_positions <= 0:
        return 0.0
    # Reaches 100 around 100 resolved positions, with diminishing returns.
    return clamp(25.0 * math.log10(resolved_positions + 1), 0.0, 100.0)


def score_profitability(roi: float) -> float:
    # 0% ROI = 50. Positive and negative ROI scale smoothly.
    return clamp(50.0 + 50.0 * math.tanh(roi), 0.0, 100.0)


def score_accuracy(win_rate: float) -> float:
    return clamp(win_rate * 100.0, 0.0, 100.0)


def score_entry_quality(
    weighted_brier_score: float | None,
) -> float:
    if weighted_brier_score is None:
        return 50.0
    return clamp((1.0 - weighted_brier_score) * 100.0, 0.0, 100.0)


def score_consistency(rois: list[float]) -> float:
    if not rois:
        return 0.0
    if len(rois) == 1:
        return 35.0

    mean = sum(rois) / len(rois)
    variance = sum((roi - mean) ** 2 for roi in rois) / len(rois)
    volatility = math.sqrt(max(0.0, variance))

    # Reward positive mean ROI and penalize highly volatile results.
    raw = 50.0 + 30.0 * math.tanh(mean) - 25.0 * math.tanh(volatility)
    return clamp(raw, 0.0, 100.0)


def performance_grade(
    score: float,
    resolved_positions: int,
) -> str:
    if resolved_positions < 5:
        return "UNRATED"
    if score >= 92:
        return "S+"
    if score >= 86:
        return "S"
    if score >= 80:
        return "A+"
    if score >= 74:
        return "A"
    if score >= 66:
        return "B"
    if score >= 58:
        return "C"
    if score >= 50:
        return "WATCH"
    return "EXCLUDE"


def confidence_grade(resolved_positions: int) -> str:
    if resolved_positions >= 100:
        return "VERY HIGH"
    if resolved_positions >= 40:
        return "HIGH"
    if resolved_positions >= 15:
        return "MEDIUM"
    if resolved_positions >= 5:
        return "LOW"
    return "VERY LOW"


def aggregate_wallet(
    wallet: str,
    positions: list[ReconciledPosition],
    calculated_at: str,
) -> dict[str, Any]:
    resolved = [
        position
        for position in positions
        if position.source_outcome_won in {0, 1}
    ]
    unresolved = [
        position
        for position in positions
        if position.source_outcome_won not in {0, 1}
    ]

    wins = sum(
        1 for position in resolved
        if position.source_outcome_won == 1
    )
    losses = sum(
        1 for position in resolved
        if position.source_outcome_lost == 1
    )
    resolved_count = len(resolved)
    win_rate = wins / resolved_count if resolved_count else 0.0

    total_cost_basis = sum(position.cost_basis for position in resolved)
    total_settlement_value = sum(
        position.settlement_value or 0.0
        for position in resolved
    )
    total_profit = sum(
        position.estimated_profit or 0.0
        for position in resolved
    )
    estimated_roi = (
        total_profit / total_cost_basis
        if total_cost_basis > EPSILON
        else 0.0
    )

    weighted_entry_numerator = sum(
        position.average_entry_price * position.cost_basis
        for position in resolved
    )
    average_entry_price = (
        weighted_entry_numerator / total_cost_basis
        if total_cost_basis > EPSILON
        else 0.0
    )

    winning_positions = [
        position for position in resolved
        if position.source_outcome_won == 1
    ]
    losing_positions = [
        position for position in resolved
        if position.source_outcome_lost == 1
    ]

    def weighted_average_entry(
        items: list[ReconciledPosition],
    ) -> float | None:
        weight = sum(item.cost_basis for item in items)
        if weight <= EPSILON:
            return None
        return sum(
            item.average_entry_price * item.cost_basis
            for item in items
        ) / weight

    average_winning_entry = weighted_average_entry(winning_positions)
    average_losing_entry = weighted_average_entry(losing_positions)

    # For a binary outcome, realized edge relative to entry is
    # actual result minus entry probability.
    average_edge_at_entry = (
        sum(
            (
                float(position.source_outcome_won)
                - position.average_entry_price
            )
            * position.cost_basis
            for position in resolved
        )
        / total_cost_basis
        if total_cost_basis > EPSILON
        else 0.0
    )

    gross_profit = sum(
        max(0.0, position.estimated_profit or 0.0)
        for position in resolved
    )
    gross_loss = abs(
        sum(
            min(0.0, position.estimated_profit or 0.0)
            for position in resolved
        )
    )
    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > EPSILON
        else None
    )

    average_win = gross_profit / wins if wins else 0.0
    average_loss = gross_loss / losses if losses else 0.0
    payoff_ratio = (
        average_win / average_loss
        if average_loss > EPSILON
        else None
    )

    brier_weight = sum(
        position.cost_basis
        for position in resolved
        if position.brier_score is not None
    )
    weighted_brier_score = (
        sum(
            (position.brier_score or 0.0) * position.cost_basis
            for position in resolved
            if position.brier_score is not None
        )
        / brier_weight
        if brier_weight > EPSILON
        else None
    )
    calibration_score = (
        clamp((1.0 - weighted_brier_score) * 100.0, 0.0, 100.0)
        if weighted_brier_score is not None
        else 0.0
    )

    position_rois = [
        position.estimated_roi
        for position in resolved
        if position.estimated_roi is not None
    ]
    consistency_score = score_consistency(position_rois)
    sample_size_score = score_sample_size(resolved_count)
    profitability_score = score_profitability(estimated_roi)
    accuracy_score = score_accuracy(win_rate)
    entry_quality_score = score_entry_quality(weighted_brier_score)

    performance_score = (
        accuracy_score * 0.25
        + profitability_score * 0.25
        + calibration_score * 0.15
        + consistency_score * 0.15
        + entry_quality_score * 0.10
        + sample_size_score * 0.10
    )

    grade = performance_grade(performance_score, resolved_count)
    confidence = confidence_grade(resolved_count)

    resolved_dates = sorted(
        date
        for date in (
            position.resolved_at or position.observed_at
            for position in resolved
        )
        if date
    )

    explanation = {
        "engine": "PERFORMANCE RECONCILIATION ENGINE",
        "engine_version": ENGINE_VERSION,
        "method": (
            "LATEST DEDUPLICATED CLOSED POSITION SNAPSHOT JOINED TO "
            "MAPPED RESOLUTION; CLOSED SETTLEMENT PRICE USED AS "
            "CONSERVATIVE FALLBACK"
        ),
        "important_limitation": (
            "Realized PnL is taken from the closed-position snapshot when "
            "available. Cost basis is estimated as total_bought * avg_price. "
            "This is more complete than the prior latest-open-snapshot method "
            "but is not a full order-by-order tax ledger."
        ),
        "position_counts": {
            "mapped_markets": len(positions),
            "resolved_positions": resolved_count,
            "unresolved_positions": len(unresolved),
            "wins": wins,
            "losses": losses,
        },
        "score_components": {
            "accuracy_score": accuracy_score,
            "profitability_score": profitability_score,
            "calibration_score": calibration_score,
            "consistency_score": consistency_score,
            "entry_quality_score": entry_quality_score,
            "sample_size_score": sample_size_score,
        },
    }

    return {
        "wallet": wallet,
        "resolved_positions": resolved_count,
        "wins": wins,
        "losses": losses,
        "unresolved_mapped_positions": len(unresolved),
        "win_rate": win_rate,
        "total_cost_basis": total_cost_basis,
        "total_settlement_value": total_settlement_value,
        "estimated_profit": total_profit,
        "estimated_roi": estimated_roi,
        "average_entry_price": average_entry_price,
        "average_winning_entry": average_winning_entry,
        "average_losing_entry": average_losing_entry,
        "average_edge_at_entry": average_edge_at_entry,
        "profit_factor": profit_factor,
        "payoff_ratio": payoff_ratio,
        "weighted_brier_score": weighted_brier_score,
        "calibration_score": calibration_score,
        "consistency_score": consistency_score,
        "sample_size_score": sample_size_score,
        "profitability_score": profitability_score,
        "accuracy_score": accuracy_score,
        "entry_quality_score": entry_quality_score,
        "performance_score": performance_score,
        "performance_grade": grade,
        "data_confidence": confidence,
        "mapped_market_count": len(positions),
        "first_resolved_scan_at": (
            resolved_dates[0] if resolved_dates else None
        ),
        "last_resolved_scan_at": (
            resolved_dates[-1] if resolved_dates else None
        ),
        "explanation_json": json.dumps(
            explanation,
            sort_keys=True,
        ),
        "calculated_at": calculated_at,
        "updated_at": calculated_at,
    }


def upsert_wallet_performance(
    connection: sqlite3.Connection,
    summary: dict[str, Any],
) -> None:
    columns = [
        "wallet",
        "resolved_positions",
        "wins",
        "losses",
        "unresolved_mapped_positions",
        "win_rate",
        "total_cost_basis",
        "total_settlement_value",
        "estimated_profit",
        "estimated_roi",
        "average_entry_price",
        "average_winning_entry",
        "average_losing_entry",
        "average_edge_at_entry",
        "profit_factor",
        "payoff_ratio",
        "weighted_brier_score",
        "calibration_score",
        "consistency_score",
        "sample_size_score",
        "profitability_score",
        "accuracy_score",
        "entry_quality_score",
        "performance_score",
        "performance_grade",
        "data_confidence",
        "mapped_market_count",
        "first_resolved_scan_at",
        "last_resolved_scan_at",
        "explanation_json",
        "calculated_at",
        "updated_at",
    ]

    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in columns
        if column != "wallet"
    )

    connection.execute(
        f"""
        INSERT INTO wallet_performance (
            {", ".join(columns)}
        )
        VALUES ({placeholders})
        ON CONFLICT(wallet) DO UPDATE SET
            {updates}
        """,
        tuple(summary[column] for column in columns),
    )


def print_report(
    positions: list[ReconciledPosition],
    summaries: list[dict[str, Any]],
) -> None:
    resolved = sum(
        1 for position in positions
        if position.source_outcome_won in {0, 1}
    )
    unresolved = len(positions) - resolved
    wins = sum(
        1 for position in positions
        if position.source_outcome_won == 1
    )
    losses = sum(
        1 for position in positions
        if position.source_outcome_lost == 1
    )

    print("\n" + "=" * 100)
    print("PERFORMANCE RECONCILIATION COMPLETE")
    print("=" * 100)
    print(f"Database: {DATABASE_PATH}")
    print(f"Deduplicated closed positions: {len(positions)}")
    print(f"Resolved positions: {resolved}")
    print(f"Unresolved positions: {unresolved}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Wallets updated: {len(summaries)}")

    ranked = sorted(
        summaries,
        key=lambda item: (
            item["performance_score"],
            item["resolved_positions"],
        ),
        reverse=True,
    )

    print("\nTop wallet performance rows:")
    for index, item in enumerate(ranked[:10], start=1):
        print(
            f"{index:>2}. {item['wallet']} | "
            f"grade={item['performance_grade']} | "
            f"score={item['performance_score']:.2f} | "
            f"resolved={item['resolved_positions']} | "
            f"W-L={item['wins']}-{item['losses']} | "
            f"win_rate={item['win_rate']:.2%} | "
            f"roi={item['estimated_roi']:.2%} | "
            f"confidence={item['data_confidence']}"
        )


def run() -> None:
    calculated_at = utc_now()
    connection = connect_database()

    try:
        require_tables(
            connection,
            [
                "wallet_closed_position_snapshots",
                "wallet_performance_markets",
                "wallet_performance",
            ],
        )
        ensure_indexes(connection)

        snapshots = latest_closed_snapshots(connection)
        mapped_results = load_mapped_results(connection)
        canonical_markets = load_canonical_markets(connection)

        reconciled = [
            reconcile_snapshot(
                snapshot=snapshot,
                mapped_results=mapped_results,
                canonical_markets=canonical_markets,
            )
            for snapshot in snapshots
        ]

        positions_by_wallet: dict[
            str,
            list[ReconciledPosition],
        ] = defaultdict(list)

        with connection:
            # Remove only rows created by this engine, preserving the older
            # performance-market records for comparison.
            connection.execute(
                """
                DELETE FROM wallet_performance_markets
                WHERE performance_market_key LIKE
                    'closed_snapshot:%'
                """
            )

            for position in reconciled:
                upsert_performance_market(
                    connection=connection,
                    position=position,
                    calculated_at=calculated_at,
                )
                positions_by_wallet[position.wallet].append(position)

            summaries = [
                aggregate_wallet(
                    wallet=wallet,
                    positions=positions,
                    calculated_at=calculated_at,
                )
                for wallet, positions in positions_by_wallet.items()
            ]

            for summary in summaries:
                upsert_wallet_performance(connection, summary)

        print_report(reconciled, summaries)

    finally:
        connection.close()


if __name__ == "__main__":
    run()