from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.platform_events import (
    PlatformEvent,
    build_deduplication_key,
    create_event_tables,
    publish_event,
    register_consumer,
)
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
MIGRATION_PATH = (
    PROJECT_ROOT
    / "database"
    / "migrations"
    / "004_institutional_reviews.sql"
)

ENGINE_VERSION = "1.0.0"
CONSUMER_NAME = "institutional_review_engine_v1"
SOURCE_EVENT_TYPES = ("OpportunityCreated", "OpportunityUpdated")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def normalized_score(value: Any) -> float:
    number = safe_float(value)
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return clamp(number)


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def ensure_schema(connection: sqlite3.Connection) -> None:
    if not MIGRATION_PATH.exists():
        raise RuntimeError(f"Migration file not found: {MIGRATION_PATH}")
    connection.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
    create_event_tables(connection)
    register_consumer(
        connection,
        consumer_name=CONSUMER_NAME,
        description=(
            "Creates deterministic institutional reviews for "
            "OpportunityCreated and OpportunityUpdated events."
        ),
    )


@dataclass(frozen=True, slots=True)
class Assessment:
    confidence_score: float
    grade: str
    decision: str
    risk_level: str
    wallet_strength: float
    capital_strength: float
    timing_strength: float
    market_quality: float
    reliability: float
    rationale: str
    risk_flags: tuple[str, ...]


def grade_for(score: float) -> str:
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
        return "WATCH"
    return "PASS"


def decision_for(
    score: float,
    grade: str,
    risk_level: str,
    opportunity_recommendation: str,
) -> str:
    source_decision = opportunity_recommendation.upper()

    if risk_level == "HIGH":
        return "REJECT"
    if (
        score >= 88
        and grade in {"S+", "S"}
        and source_decision == "ACTIONABLE"
    ):
        return "APPROVE"
    if score >= 76 and source_decision in {"ACTIONABLE", "WATCHLIST"}:
        return "REVIEW"
    if score >= 62 and source_decision != "PASS":
        return "MONITOR"
    return "REJECT"


def risk_level_for(
    *,
    wallet_count: int,
    elite_wallet_count: int,
    timing_status: str,
    market_quality: float,
    reliability: float,
    current_price: float | None,
) -> tuple[str, tuple[str, ...]]:
    flags: list[str] = []

    if wallet_count < 2:
        flags.append("INSUFFICIENT_WALLET_CONFIRMATION")
    if elite_wallet_count == 0:
        flags.append("NO_ELITE_WALLET_CONFIRMATION")
    if timing_status in {"STALE", "UNKNOWN"}:
        flags.append(f"TIMING_{timing_status}")
    if market_quality < 45:
        flags.append("WEAK_MARKET_STRUCTURE")
    if reliability < 45:
        flags.append("LIMITED_HISTORICAL_RELIABILITY")
    if current_price is not None:
        normalized_price = current_price * 100 if 0 <= current_price <= 1 else current_price
        if normalized_price <= 3 or normalized_price >= 97:
            flags.append("EXTREME_MARKET_PRICE")

    severe = {
        "INSUFFICIENT_WALLET_CONFIRMATION",
        "WEAK_MARKET_STRUCTURE",
        "EXTREME_MARKET_PRICE",
    }
    severe_count = sum(flag in severe for flag in flags)

    if severe_count >= 2 or len(flags) >= 4:
        return "HIGH", tuple(flags)
    if flags:
        return "MEDIUM", tuple(flags)
    return "LOW", tuple()


def assess(payload: dict[str, Any]) -> Assessment:
    opportunity_score = normalized_score(
        payload.get("score", payload.get("opportunity_score"))
    )
    wallet_quality = normalized_score(
        payload.get("wallet_quality_score", payload.get("wallet_component"))
    )
    timing = normalized_score(payload.get("timing_score"))
    market_quality = normalized_score(
        payload.get(
            "market_structure_score",
            payload.get("data_quality_score", 50.0),
        )
    )
    reliability = normalized_score(
        payload.get("historical_reliability_score", 40.0)
    )

    wallet_count = max(0, int(safe_float(payload.get("wallet_count"))))
    elite_count = max(
        0,
        int(
            safe_float(
                payload.get(
                    "elite_wallet_count",
                    payload.get("elite_count"),
                )
            )
        ),
    )
    combined_capital = max(
        0.0,
        safe_float(
            payload.get(
                "combined_capital",
                payload.get("capital", 0.0),
            )
        ),
    )

    if wallet_quality <= 0:
        elite_ratio = elite_count / max(wallet_count, 1)
        wallet_quality = clamp(
            35.0 + min(elite_count, 4) * 12.0 + elite_ratio * 28.0
        )

    capital_strength = (
        0.0
        if combined_capital <= 0
        else clamp(
            100.0
            * math.log1p(combined_capital)
            / math.log1p(1_000_000.0)
        )
    )

    timing_status = str(payload.get("timing_status") or "UNKNOWN").upper()
    if timing <= 0:
        timing = {
            "TIGHT": 95.0,
            "COORDINATED": 78.0,
            "DISTRIBUTED": 55.0,
            "STALE": 25.0,
        }.get(timing_status, 35.0)

    current_price_raw = payload.get("current_price")
    current_price = (
        safe_float(current_price_raw)
        if current_price_raw is not None
        else None
    )

    risk_level, flags = risk_level_for(
        wallet_count=wallet_count,
        elite_wallet_count=elite_count,
        timing_status=timing_status,
        market_quality=market_quality,
        reliability=reliability,
        current_price=current_price,
    )

    confidence = clamp(
        opportunity_score * 0.35
        + wallet_quality * 0.20
        + capital_strength * 0.15
        + timing * 0.12
        + market_quality * 0.10
        + reliability * 0.08
    )

    if risk_level == "HIGH":
        confidence = clamp(confidence - 12.0)
    elif risk_level == "MEDIUM":
        confidence = clamp(confidence - 5.0)

    grade = grade_for(confidence)
    recommendation = str(
        payload.get("decision")
        or payload.get("recommendation")
        or "PASS"
    ).upper()
    decision = decision_for(
        confidence,
        grade,
        risk_level,
        recommendation,
    )

    strengths: list[str] = []
    if opportunity_score >= 80:
        strengths.append("opportunity conviction is strong")
    if wallet_quality >= 75:
        strengths.append("wallet quality is institutionally credible")
    if elite_count >= 2:
        strengths.append(f"{elite_count} elite wallets confirm the signal")
    if capital_strength >= 70:
        strengths.append("capital deployment is substantial")
    if timing_status in {"TIGHT", "COORDINATED"}:
        strengths.append("entry timing is coordinated")
    if market_quality >= 70:
        strengths.append("market structure is supportive")

    if not strengths:
        strengths.append("evidence is incomplete or below institutional thresholds")

    rationale = (
        f"Institutional decision: {decision}. "
        + "; ".join(strengths).capitalize()
        + f". Risk level: {risk_level}."
    )

    return Assessment(
        confidence_score=round(confidence, 4),
        grade=grade,
        decision=decision,
        risk_level=risk_level,
        wallet_strength=round(wallet_quality, 4),
        capital_strength=round(capital_strength, 4),
        timing_strength=round(timing, 4),
        market_quality=round(market_quality, 4),
        reliability=round(reliability, 4),
        rationale=rationale,
        risk_flags=flags,
    )


def state_checksum(payload: dict[str, Any]) -> str:
    existing = payload.get("state_checksum")
    if existing:
        return str(existing)

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_source_events(
    connection: sqlite3.Connection,
    limit: int,
) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in SOURCE_EVENT_TYPES)
    return connection.execute(
        f"""
        SELECT
            e.id,
            e.event_id,
            e.event_type,
            e.aggregate_id,
            e.payload_json,
            e.occurred_at
        FROM platform_events AS e
        LEFT JOIN event_consumer_receipts AS r
          ON r.event_id = e.event_id
         AND r.consumer_name = ?
        WHERE e.event_type IN ({placeholders})
          AND r.id IS NULL
        ORDER BY e.id ASC
        LIMIT ?
        """,
        (CONSUMER_NAME, *SOURCE_EVENT_TYPES, limit),
    ).fetchall()


def insert_review(
    connection: sqlite3.Connection,
    *,
    source_event: sqlite3.Row,
    payload: dict[str, Any],
    assessment: Assessment,
    run_id: str,
    reviewed_at: str,
) -> tuple[bool, str]:
    opportunity_id = str(
        payload.get("opportunity_id") or source_event["aggregate_id"]
    )
    market_id = str(payload.get("market_id") or opportunity_id)
    outcome = str(
        payload.get("outcome")
        or payload.get("selected_outcome")
        or "UNKNOWN"
    )
    source_checksum = state_checksum(payload)
    review_id = hashlib.sha256(
        (
            f"{opportunity_id}|{source_checksum}|"
            f"{ENGINE_VERSION}"
        ).encode("utf-8")
    ).hexdigest()[:32]

    evidence = {
        "source_event_id": source_event["event_id"],
        "source_event_type": source_event["event_type"],
        "opportunity_payload": payload,
    }

    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO institutional_reviews (
            review_id, opportunity_id, market_id, outcome, title, category,
            source_event_id, source_event_type, source_state_checksum,
            opportunity_score, opportunity_grade,
            opportunity_recommendation,
            institutional_confidence_score, institutional_grade,
            institutional_decision, risk_level,
            wallet_strength_score, capital_strength_score,
            timing_strength_score, market_quality_score,
            reliability_score, wallet_count, elite_wallet_count,
            combined_capital, current_price, timing_status,
            rationale, risk_flags_json, evidence_json,
            model_version, reviewed_at, run_id
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            review_id,
            opportunity_id,
            market_id,
            outcome,
            payload.get("title") or payload.get("question"),
            payload.get("category"),
            source_event["event_id"],
            source_event["event_type"],
            source_checksum,
            normalized_score(
                payload.get("score", payload.get("opportunity_score"))
            ),
            str(
                payload.get("grade")
                or payload.get("opportunity_grade")
                or "PASS"
            ),
            str(
                payload.get("decision")
                or payload.get("recommendation")
                or "PASS"
            ),
            assessment.confidence_score,
            assessment.grade,
            assessment.decision,
            assessment.risk_level,
            assessment.wallet_strength,
            assessment.capital_strength,
            assessment.timing_strength,
            assessment.market_quality,
            assessment.reliability,
            max(0, int(safe_float(payload.get("wallet_count")))),
            max(
                0,
                int(
                    safe_float(
                        payload.get(
                            "elite_wallet_count",
                            payload.get("elite_count"),
                        )
                    )
                ),
            ),
            max(
                0.0,
                safe_float(
                    payload.get(
                        "combined_capital",
                        payload.get("capital"),
                    )
                ),
            ),
            (
                safe_float(payload.get("current_price"))
                if payload.get("current_price") is not None
                else None
            ),
            str(payload.get("timing_status") or "UNKNOWN").upper(),
            assessment.rationale,
            json.dumps(assessment.risk_flags, sort_keys=True),
            json.dumps(evidence, sort_keys=True, default=str),
            ENGINE_VERSION,
            reviewed_at,
            run_id,
        ),
    )
    return cursor.rowcount == 1, review_id


def publish_review_event(
    connection: sqlite3.Connection,
    *,
    review_id: str,
    source_event: sqlite3.Row,
    payload: dict[str, Any],
    assessment: Assessment,
) -> bool:
    opportunity_id = str(
        payload.get("opportunity_id") or source_event["aggregate_id"]
    )
    event_payload = {
        "review_id": review_id,
        "opportunity_id": opportunity_id,
        "market_id": payload.get("market_id"),
        "outcome": payload.get("outcome")
        or payload.get("selected_outcome"),
        "score": assessment.confidence_score,
        "grade": assessment.grade,
        "decision": assessment.decision,
        "risk_level": assessment.risk_level,
        "rationale": assessment.rationale,
        "source_event_id": source_event["event_id"],
    }

    deduplication_key = build_deduplication_key(
        event_type="OpportunityReviewed",
        aggregate_type="opportunity",
        aggregate_id=opportunity_id,
        state_value={
            "review_id": review_id,
            "decision": assessment.decision,
            "score": assessment.confidence_score,
        },
    )

    event = PlatformEvent.create(
        event_type="OpportunityReviewed",
        source_engine=CONSUMER_NAME,
        source_version=ENGINE_VERSION,
        aggregate_type="opportunity",
        aggregate_id=opportunity_id,
        payload=event_payload,
        correlation_id=source_event["event_id"],
        causation_id=source_event["event_id"],
        deduplication_key=deduplication_key,
    )
    return publish_event(connection, event)


def record_receipt(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    result: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO event_consumer_receipts (
            consumer_name, event_id, result_json
        ) VALUES (?, ?, ?)
        ON CONFLICT(consumer_name, event_id) DO UPDATE SET
            processed_at=CURRENT_TIMESTAMP,
            result_json=excluded.result_json
        """,
        (
            CONSUMER_NAME,
            event_id,
            json.dumps(result, sort_keys=True, default=str),
        ),
    )


def update_consumer_success(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE event_consumers
        SET last_run_at=CURRENT_TIMESTAMP,
            last_success_at=CURRENT_TIMESTAMP,
            last_error=NULL,
            updated_at=CURRENT_TIMESTAMP
        WHERE consumer_name=?
        """,
        (CONSUMER_NAME,),
    )


def update_consumer_failure(
    connection: sqlite3.Connection,
    error: Exception,
) -> None:
    connection.execute(
        """
        UPDATE event_consumers
        SET last_run_at=CURRENT_TIMESTAMP,
            last_error=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE consumer_name=?
        """,
        (str(error)[:4000], CONSUMER_NAME),
    )


def run(limit: int = 10_000) -> dict[str, int]:
    if not DATABASE_PATH.exists():
        raise RuntimeError(f"Database not found: {DATABASE_PATH}")

    run_id = (
        f"institutional-review:"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:"
        f"{uuid.uuid4().hex[:8]}"
    )
    started_at = utc_now()
    counts = {
        "source_events_read": 0,
        "reviews_created": 0,
        "reviews_skipped": 0,
        "events_published": 0,
    }

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        ensure_schema(connection)

        connection.execute(
            """
            INSERT INTO institutional_review_runs (
                run_id, engine_version, started_at, status
            ) VALUES (?, ?, ?, 'RUNNING')
            """,
            (run_id, ENGINE_VERSION, started_at),
        )
        connection.commit()

        try:
            events = load_source_events(connection, limit)
            counts["source_events_read"] = len(events)

            for source_event in events:
                payload = json.loads(source_event["payload_json"])
                assessment = assess(payload)
                reviewed_at = utc_now()

                created, review_id = insert_review(
                    connection,
                    source_event=source_event,
                    payload=payload,
                    assessment=assessment,
                    run_id=run_id,
                    reviewed_at=reviewed_at,
                )
                connection.commit()

                if created:
                    counts["reviews_created"] += 1
                    if publish_review_event(
                        connection,
                        review_id=review_id,
                        source_event=source_event,
                        payload=payload,
                        assessment=assessment,
                    ):
                        counts["events_published"] += 1
                else:
                    counts["reviews_skipped"] += 1

                record_receipt(
                    connection,
                    event_id=source_event["event_id"],
                    result={
                        "review_id": review_id,
                        "created": created,
                        "decision": assessment.decision,
                        "score": assessment.confidence_score,
                    },
                )
                connection.commit()

            update_consumer_success(connection)
            connection.execute(
                """
                UPDATE institutional_review_runs
                SET completed_at=?,
                    status='SUCCESS',
                    source_events_read=?,
                    reviews_created=?,
                    reviews_skipped=?,
                    events_published=?
                WHERE run_id=?
                """,
                (
                    utc_now(),
                    counts["source_events_read"],
                    counts["reviews_created"],
                    counts["reviews_skipped"],
                    counts["events_published"],
                    run_id,
                ),
            )
            connection.commit()
        except Exception as error:
            connection.rollback()
            update_consumer_failure(connection, error)
            connection.execute(
                """
                UPDATE institutional_review_runs
                SET completed_at=?,
                    status='FAILED',
                    source_events_read=?,
                    reviews_created=?,
                    reviews_skipped=?,
                    events_published=?,
                    error_message=?
                WHERE run_id=?
                """,
                (
                    utc_now(),
                    counts["source_events_read"],
                    counts["reviews_created"],
                    counts["reviews_skipped"],
                    counts["events_published"],
                    str(error)[:4000],
                    run_id,
                ),
            )
            connection.commit()
            raise

    return counts


def print_board(connection: sqlite3.Connection, limit: int = 20) -> None:
    rows = connection.execute(
        """
        SELECT
            rank, title, outcome, institutional_confidence_score,
            institutional_grade, institutional_decision, risk_level,
            wallet_count, elite_wallet_count, combined_capital
        FROM ranked_institutional_reviews
        ORDER BY rank
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    print()
    print("INSTITUTIONAL REVIEW BOARD")
    print("-" * 140)
    for row in rows:
        label = f"{row['title'] or 'Unknown market'} | {row['outcome']}"
        print(
            f"{row['rank']:>3}  "
            f"{row['institutional_confidence_score']:>6.2f}  "
            f"{row['institutional_grade']:<5}  "
            f"{row['institutional_decision']:<8}  "
            f"{row['risk_level']:<6}  "
            f"W:{row['wallet_count']:<3} "
            f"E:{row['elite_wallet_count']:<3} "
            f"${row['combined_capital']:>12,.2f}  "
            f"{label[:70]}"
        )
    print("-" * 140)


def main() -> int:
    try:
        counts = run()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        print_board(connection)

    print()
    print("=" * 72)
    print(f"INSTITUTIONAL REVIEW ENGINE v{ENGINE_VERSION}")
    print("=" * 72)
    print(f"Source events read:       {counts['source_events_read']:,}")
    print(f"Reviews created:          {counts['reviews_created']:,}")
    print(f"Reviews skipped:          {counts['reviews_skipped']:,}")
    print(f"Review events published:  {counts['events_published']:,}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
