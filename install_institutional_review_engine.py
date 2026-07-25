from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path.cwd()
DB_PATH = ROOT / "database" / "polymarket.db"
SRC_DIR = ROOT / "src"
BACKUP_DIR = ROOT / "database" / "backups"

ENGINE_PATH = SRC_DIR / "institutional_review_engine.py"
HEALTH_PATH = SRC_DIR / "institutional_review_health.py"


ENGINE_CODE = r"""from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("database") / "polymarket.db"
CONSUMER_NAME = "institutional_review_engine_v1"
ENGINE_VERSION = "1.0.0"
SOURCE_TABLE = "opportunity_intelligence_v2"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize(value: Any) -> str:
    return str(value or "").strip().upper()


def safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    escaped = table.replace('"', '""')
    return {
        row["name"]
        for row in connection.execute(
            f'PRAGMA table_info("{escaped}")'
        ).fetchall()
    }


def first_value(data: dict[str, Any], names: list[str]) -> Any:
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        if name.lower() in lowered:
            value = lowered[name.lower()]
            if value is not None:
                return value
    return None


def load_opportunity_row(
    connection: sqlite3.Connection,
    opportunity_id: str,
) -> dict[str, Any]:
    columns = table_columns(connection, SOURCE_TABLE)
    if "opportunity_id" not in columns:
        return {}

    row = connection.execute(
        f"""
        SELECT *
        FROM "{SOURCE_TABLE}"
        WHERE CAST(opportunity_id AS TEXT) = ?
        LIMIT 1
        """,
        (opportunity_id,),
    ).fetchone()

    return dict(row) if row else {}


def merge_payload_and_row(
    payload: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(row)
    for key, value in payload.items():
        if value is not None:
            merged[key] = value
    return merged


def derive_metrics(data: dict[str, Any]) -> dict[str, Any]:
    score = safe_float(
        first_value(
            data,
            ["score", "opportunity_score", "conviction_score"],
        )
    ) or 0.0

    grade = normalize(
        first_value(
            data,
            ["grade", "opportunity_grade", "confidence_grade"],
        )
    )

    decision = normalize(
        first_value(
            data,
            ["decision", "recommended_action", "action"],
        )
    )

    timing = normalize(
        first_value(
            data,
            ["timing", "timing_label", "timing_classification"],
        )
    )

    wallet_count = safe_int(
        first_value(
            data,
            ["wallet_count", "matching_wallets", "agreeing_wallets"],
        )
    )

    elite_wallet_count = safe_int(
        first_value(
            data,
            ["elite_wallet_count", "elite_count", "top_wallet_count"],
        )
    )

    capital = safe_float(
        first_value(
            data,
            [
                "combined_value",
                "capital",
                "total_capital",
                "combined_capital",
                "position_value",
                "current_value",
                "total_position_value",
                "total_current_value",
            ],
        )
    ) or 0.0

    market_id = str(
        first_value(data, ["market_id", "condition_id", "token_id"]) or ""
    )
    title = str(
        first_value(data, ["title", "market_title", "question"]) or ""
    )
    outcome = str(first_value(data, ["outcome", "side"]) or "")

    return {
        "score": round(score, 2),
        "grade": grade,
        "decision": decision,
        "timing": timing,
        "wallet_count": wallet_count,
        "elite_wallet_count": elite_wallet_count,
        "capital": round(capital, 2),
        "market_id": market_id,
        "title": title,
        "outcome": outcome,
    }


def is_meaningful(metrics: dict[str, Any]) -> bool:
    decision = metrics["decision"]
    score = metrics["score"]

    if decision in {
        "ACTIONABLE",
        "ALERT",
        "PLAY",
        "BET",
        "MONITOR",
        "WATCHLIST",
    }:
        return True

    if decision == "PASS":
        return False

    return score >= 70.0


def calculate_confidence(metrics: dict[str, Any]) -> tuple[float, str]:
    score = metrics["score"]
    wallet_count = metrics["wallet_count"]
    elite_wallet_count = metrics["elite_wallet_count"]
    capital = metrics["capital"]
    timing = metrics["timing"]
    decision = metrics["decision"]

    confidence = score * 0.70

    confidence += min(wallet_count, 6) * 2.0
    confidence += min(elite_wallet_count, 3) * 4.0

    if capital >= 1_000_000:
        confidence += 8.0
    elif capital >= 250_000:
        confidence += 6.0
    elif capital >= 50_000:
        confidence += 4.0
    elif capital >= 10_000:
        confidence += 2.0

    if timing in {"EARLY", "OPEN", "FAVORABLE"}:
        confidence += 6.0
    elif timing in {"COORDINATED", "STABLE"}:
        confidence += 4.0
    elif timing == "TIGHT":
        confidence -= 2.0
    elif timing in {"LATE", "CLOSED", "UNFAVORABLE"}:
        confidence -= 8.0

    if decision in {"ACTIONABLE", "ALERT", "PLAY", "BET"}:
        confidence += 8.0
    elif decision in {"MONITOR", "WATCHLIST"}:
        confidence += 3.0
    elif decision == "PASS":
        confidence -= 10.0

    confidence = max(0.0, min(100.0, confidence))

    if confidence >= 85:
        label = "VERY_HIGH"
    elif confidence >= 75:
        label = "HIGH"
    elif confidence >= 60:
        label = "MODERATE"
    elif confidence >= 45:
        label = "LOW"
    else:
        label = "VERY_LOW"

    return round(confidence, 2), label


def classify_strengths(metrics: dict[str, Any]) -> dict[str, str]:
    wallet_count = metrics["wallet_count"]
    elite_wallet_count = metrics["elite_wallet_count"]
    capital = metrics["capital"]
    timing = metrics["timing"]

    if wallet_count >= 5:
        consensus = "VERY_STRONG"
    elif wallet_count >= 4:
        consensus = "STRONG"
    elif wallet_count >= 2:
        consensus = "MODERATE"
    else:
        consensus = "WEAK"

    if capital >= 1_000_000:
        capital_strength = "VERY_STRONG"
    elif capital >= 250_000:
        capital_strength = "STRONG"
    elif capital >= 50_000:
        capital_strength = "MODERATE"
    else:
        capital_strength = "WEAK"

    if elite_wallet_count >= 2:
        wallet_quality = "VERY_STRONG"
    elif elite_wallet_count == 1:
        wallet_quality = "STRONG"
    else:
        wallet_quality = "UNCONFIRMED"

    if timing in {"EARLY", "OPEN", "FAVORABLE"}:
        timing_grade = "FAVORABLE"
    elif timing in {"COORDINATED", "STABLE"}:
        timing_grade = "ACCEPTABLE"
    elif timing == "TIGHT":
        timing_grade = "CONSTRAINED"
    elif timing in {"LATE", "CLOSED", "UNFAVORABLE"}:
        timing_grade = "UNFAVORABLE"
    else:
        timing_grade = "UNKNOWN"

    return {
        "consensus_strength": consensus,
        "capital_strength": capital_strength,
        "wallet_quality": wallet_quality,
        "timing_grade": timing_grade,
    }


def determine_risk(
    metrics: dict[str, Any],
    strengths: dict[str, str],
) -> tuple[str, list[str]]:
    risks: list[str] = []

    if metrics["wallet_count"] < 3:
        risks.append("Limited wallet agreement")
    if metrics["elite_wallet_count"] == 0:
        risks.append("No confirmed elite-wallet participation")
    if metrics["capital"] < 50_000:
        risks.append("Capital support is limited")
    if strengths["timing_grade"] == "CONSTRAINED":
        risks.append("Entry timing is tight")
    elif strengths["timing_grade"] == "UNFAVORABLE":
        risks.append("Entry timing is unfavorable")
    elif strengths["timing_grade"] == "UNKNOWN":
        risks.append("Timing evidence is incomplete")

    if len(risks) >= 4:
        level = "HIGH"
    elif len(risks) >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    return level, risks


def recommendation_for(metrics: dict[str, Any]) -> str:
    decision = metrics["decision"]

    if decision in {"ACTIONABLE", "ALERT", "PLAY", "BET"}:
        return "REVIEW_FOR_ALERT"
    if decision in {"MONITOR", "WATCHLIST"}:
        return "CONTINUE_MONITORING"
    return "NO_ACTION"


def build_reasoning(
    metrics: dict[str, Any],
    strengths: dict[str, str],
    risks: list[str],
) -> list[str]:
    reasons = [
        f"Opportunity score is {metrics['score']:.2f}.",
        f"{metrics['wallet_count']} wallets currently support the outcome.",
        f"{metrics['elite_wallet_count']} elite wallets are represented.",
    ]

    if metrics["capital"] > 0:
        reasons.append(
            f"Observed supporting capital is ${metrics['capital']:,.2f}."
        )
    else:
        reasons.append("Supporting capital was not available in the event payload.")

    reasons.append(
        f"Consensus strength is {strengths['consensus_strength']}."
    )
    reasons.append(
        f"Wallet quality is {strengths['wallet_quality']}."
    )
    reasons.append(
        f"Timing is classified as {strengths['timing_grade']}."
    )

    reasons.extend(f"Risk: {risk}." for risk in risks)
    return reasons


def build_summary(
    metrics: dict[str, Any],
    confidence_label: str,
    recommendation: str,
) -> str:
    market = metrics["title"] or metrics["market_id"] or "Unknown market"
    outcome = metrics["outcome"] or "Unknown outcome"

    return (
        f"{market} | {outcome}: score {metrics['score']:.2f}, "
        f"institutional confidence {confidence_label}, "
        f"recommendation {recommendation}."
    )


def fingerprint(
    opportunity_id: str,
    event_id: str,
    metrics: dict[str, Any],
) -> str:
    raw = json.dumps(
        {
            "opportunity_id": opportunity_id,
            "event_id": event_id,
            "metrics": metrics,
            "engine_version": ENGINE_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def publish_review_event(
    connection: sqlite3.Connection,
    review: dict[str, Any],
) -> bool:
    event_id = str(uuid.uuid4())
    deduplication_key = (
        f"OpportunityReviewed:{review['review_fingerprint']}"
    )

    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO platform_events (
            event_id,
            event_type,
            source_engine,
            source_version,
            aggregate_type,
            aggregate_id,
            payload_json,
            occurred_at,
            correlation_id,
            causation_id,
            deduplication_key,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            "OpportunityReviewed",
            CONSUMER_NAME,
            ENGINE_VERSION,
            "institutional_review",
            review["review_id"],
            json.dumps(
                {
                    "review_id": review["review_id"],
                    "opportunity_id": review["opportunity_id"],
                    "market_id": review["market_id"],
                    "source_event_id": review["source_event_id"],
                    "confidence_score": review["confidence_score"],
                    "confidence_label": review["confidence_label"],
                    "risk_level": review["risk_level"],
                    "recommendation": review["recommendation"],
                    "summary": review["summary"],
                },
                sort_keys=True,
            ),
            utc_now(),
            review["source_event_id"],
            review["source_event_id"],
            deduplication_key,
            "PENDING",
        ),
    )
    return cursor.rowcount == 1


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    connection.execute(
        """
        INSERT INTO event_consumers (consumer_name, description)
        VALUES (?, ?)
        ON CONFLICT(consumer_name) DO UPDATE SET
            description = excluded.description,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            CONSUMER_NAME,
            "Creates deterministic institutional reviews for meaningful opportunities.",
        ),
    )

    events = connection.execute(
        """
        SELECT
            e.event_id,
            e.aggregate_id,
            e.payload_json,
            e.occurred_at
        FROM platform_events AS e
        LEFT JOIN event_consumer_receipts AS r
            ON r.event_id = e.event_id
           AND r.consumer_name = ?
        WHERE e.event_type IN ('OpportunityCreated', 'OpportunityUpdated')
          AND r.id IS NULL
        ORDER BY e.id ASC
        """,
        (CONSUMER_NAME,),
    ).fetchall()

    reviewed = 0
    skipped = 0
    review_events_published = 0

    for event in events:
        payload = json.loads(event["payload_json"])
        opportunity_id = str(
            payload.get("opportunity_id") or event["aggregate_id"]
        )

        row = load_opportunity_row(connection, opportunity_id)
        data = merge_payload_and_row(payload, row)
        metrics = derive_metrics(data)

        if not is_meaningful(metrics):
            connection.execute(
                """
                INSERT OR IGNORE INTO event_consumer_receipts (
                    consumer_name,
                    event_id,
                    result_json
                )
                VALUES (?, ?, ?)
                """,
                (
                    CONSUMER_NAME,
                    event["event_id"],
                    json.dumps(
                        {
                            "status": "SKIPPED",
                            "reason": "Opportunity is not meaningful under current review rules.",
                            "decision": metrics["decision"],
                            "score": metrics["score"],
                        },
                        sort_keys=True,
                    ),
                ),
            )
            skipped += 1
            continue

        confidence_score, confidence_label = calculate_confidence(metrics)
        strengths = classify_strengths(metrics)
        risk_level, risks = determine_risk(metrics, strengths)
        recommendation = recommendation_for(metrics)
        reasoning = build_reasoning(metrics, strengths, risks)
        summary = build_summary(
            metrics,
            confidence_label,
            recommendation,
        )

        review_id = str(uuid.uuid4())
        review_fingerprint = fingerprint(
            opportunity_id,
            event["event_id"],
            metrics,
        )

        review = {
            "review_id": review_id,
            "opportunity_id": opportunity_id,
            "market_id": metrics["market_id"],
            "source_event_id": event["event_id"],
            "review_fingerprint": review_fingerprint,
            "confidence_score": confidence_score,
            "confidence_label": confidence_label,
            "risk_level": risk_level,
            "recommendation": recommendation,
            "summary": summary,
        }

        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO institutional_reviews (
                review_id,
                opportunity_id,
                market_id,
                source_event_id,
                review_timestamp,
                review_status,
                opportunity_score,
                opportunity_grade,
                opportunity_decision,
                confidence_score,
                confidence_label,
                consensus_strength,
                capital_strength,
                wallet_quality,
                timing_grade,
                risk_level,
                recommendation,
                summary,
                strengths_json,
                risks_json,
                reasoning_json,
                metrics_json,
                review_fingerprint,
                engine_version
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                review_id,
                opportunity_id,
                metrics["market_id"],
                event["event_id"],
                utc_now(),
                "COMPLETED",
                metrics["score"],
                metrics["grade"],
                metrics["decision"],
                confidence_score,
                confidence_label,
                strengths["consensus_strength"],
                strengths["capital_strength"],
                strengths["wallet_quality"],
                strengths["timing_grade"],
                risk_level,
                recommendation,
                summary,
                json.dumps(strengths, sort_keys=True),
                json.dumps(risks, sort_keys=True),
                json.dumps(reasoning, sort_keys=True),
                json.dumps(metrics, sort_keys=True),
                review_fingerprint,
                ENGINE_VERSION,
            ),
        )

        if cursor.rowcount == 1:
            reviewed += 1
            if publish_review_event(connection, review):
                review_events_published += 1

        connection.execute(
            """
            INSERT OR IGNORE INTO event_consumer_receipts (
                consumer_name,
                event_id,
                result_json
            )
            VALUES (?, ?, ?)
            """,
            (
                CONSUMER_NAME,
                event["event_id"],
                json.dumps(
                    {
                        "status": "REVIEWED",
                        "review_id": review_id,
                        "confidence_score": confidence_score,
                        "confidence_label": confidence_label,
                        "risk_level": risk_level,
                        "recommendation": recommendation,
                    },
                    sort_keys=True,
                ),
            ),
        )

    connection.execute(
        """
        UPDATE event_consumers
        SET
            last_run_at = CURRENT_TIMESTAMP,
            last_success_at = CURRENT_TIMESTAMP,
            last_error = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE consumer_name = ?
        """,
        (CONSUMER_NAME,),
    )

    connection.commit()

    totals = connection.execute(
        """
        SELECT recommendation, COUNT(*) AS total
        FROM institutional_reviews
        GROUP BY recommendation
        ORDER BY recommendation
        """
    ).fetchall()

    print("=" * 78)
    print("INSTITUTIONAL REVIEW ENGINE")
    print("=" * 78)
    print(f"Source events examined: {len(events):,}")
    print(f"New reviews created: {reviewed:,}")
    print(f"Non-meaningful events skipped: {skipped:,}")
    print(f"OpportunityReviewed events published: {review_events_published:,}")
    print()
    print("Stored review totals:")
    for row in totals:
        print(f"  {row['recommendation']}: {row['total']}")
    print("=" * 78)

    connection.close()


if __name__ == "__main__":
    main()
"""


HEALTH_CODE = r"""from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database") / "polymarket.db"


def object_exists(
    connection: sqlite3.Connection,
    object_type: str,
    name: str,
) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = ? AND name = ?
            """,
            (object_type, name),
        ).fetchone()
        is not None
    )


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    print("=" * 78)
    print("INSTITUTIONAL REVIEW HEALTH")
    print("=" * 78)

    healthy = True

    for table in [
        "institutional_reviews",
        "platform_events",
        "event_consumers",
        "event_consumer_receipts",
    ]:
        present = object_exists(connection, "table", table)
        healthy = healthy and present
        print(f"{table}: {'OK' if present else 'MISSING'}")

    if object_exists(
        connection,
        "view",
        "current_institutional_reviews",
    ):
        print("current_institutional_reviews: OK")
    else:
        print("current_institutional_reviews: MISSING")
        healthy = False

    totals = connection.execute(
        """
        SELECT
            COUNT(*) AS total_reviews,
            SUM(CASE WHEN review_status = 'COMPLETED' THEN 1 ELSE 0 END)
                AS completed_reviews,
            COUNT(DISTINCT opportunity_id) AS reviewed_opportunities,
            MAX(review_timestamp) AS latest_review
        FROM institutional_reviews
        """
    ).fetchone()

    published = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM platform_events
        WHERE event_type = 'OpportunityReviewed'
        """
    ).fetchone()["total"]

    pending_review_events = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM platform_events
        WHERE event_type = 'OpportunityReviewed'
          AND status = 'PENDING'
        """
    ).fetchone()["total"]

    duplicate_fingerprints = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM (
            SELECT review_fingerprint
            FROM institutional_reviews
            GROUP BY review_fingerprint
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()["total"]

    print(f"Total reviews: {totals['total_reviews'] or 0}")
    print(f"Completed reviews: {totals['completed_reviews'] or 0}")
    print(
        f"Distinct reviewed opportunities: "
        f"{totals['reviewed_opportunities'] or 0}"
    )
    print(f"OpportunityReviewed events: {published}")
    print(f"Pending OpportunityReviewed events: {pending_review_events}")
    print(f"Duplicate review fingerprints: {duplicate_fingerprints}")
    print(f"Latest review: {totals['latest_review']}")

    healthy = healthy and duplicate_fingerprints == 0

    consumer = connection.execute(
        """
        SELECT
            consumer_name,
            last_run_at,
            last_success_at,
            last_error
        FROM event_consumers
        WHERE consumer_name = 'institutional_review_engine_v1'
        """
    ).fetchone()

    if consumer:
        print(f"Consumer registered: {consumer['consumer_name']}")
        print(f"Last successful run: {consumer['last_success_at']}")
        print(f"Last error: {consumer['last_error']}")
        healthy = healthy and not consumer["last_error"]
    else:
        print("Consumer registered: NO")
        healthy = False

    print(f"Overall status: {'HEALTHY' if healthy else 'ATTENTION REQUIRED'}")
    print("=" * 78)

    connection.close()

    if not healthy:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
"""


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    if not SRC_DIR.exists():
        raise FileNotFoundError(f"Source directory not found: {SRC_DIR}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"polymarket_before_institutional_reviews_{stamp}.db"
    shutil.copy2(DB_PATH, backup)

    if ENGINE_PATH.exists():
        shutil.copy2(
            ENGINE_PATH,
            ENGINE_PATH.with_suffix(f".py.backup_{stamp}"),
        )
    if HEALTH_PATH.exists():
        shutil.copy2(
            HEALTH_PATH,
            HEALTH_PATH.with_suffix(f".py.backup_{stamp}"),
        )

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS institutional_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id TEXT NOT NULL UNIQUE,
                opportunity_id TEXT NOT NULL,
                market_id TEXT,
                source_event_id TEXT NOT NULL,
                review_timestamp TEXT NOT NULL,
                review_status TEXT NOT NULL,
                opportunity_score REAL,
                opportunity_grade TEXT,
                opportunity_decision TEXT,
                confidence_score REAL NOT NULL,
                confidence_label TEXT NOT NULL,
                consensus_strength TEXT NOT NULL,
                capital_strength TEXT NOT NULL,
                wallet_quality TEXT NOT NULL,
                timing_grade TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                summary TEXT NOT NULL,
                strengths_json TEXT NOT NULL,
                risks_json TEXT NOT NULL,
                reasoning_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                review_fingerprint TEXT NOT NULL UNIQUE,
                engine_version TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_institutional_reviews_opportunity
                ON institutional_reviews(opportunity_id, review_timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_institutional_reviews_market
                ON institutional_reviews(market_id, review_timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_institutional_reviews_recommendation
                ON institutional_reviews(recommendation, confidence_score DESC);

            CREATE INDEX IF NOT EXISTS idx_institutional_reviews_source_event
                ON institutional_reviews(source_event_id);

            DROP VIEW IF EXISTS current_institutional_reviews;

            CREATE VIEW current_institutional_reviews AS
            SELECT reviews.*
            FROM institutional_reviews AS reviews
            INNER JOIN (
                SELECT
                    opportunity_id,
                    MAX(id) AS latest_id
                FROM institutional_reviews
                GROUP BY opportunity_id
            ) AS latest
                ON latest.latest_id = reviews.id;
            """
        )

        ENGINE_PATH.write_text(ENGINE_CODE, encoding="utf-8")
        HEALTH_PATH.write_text(HEALTH_CODE, encoding="utf-8")

        # Queue all production opportunity events for this new consumer only.
        # Existing consumers and event status remain untouched.
        prior_receipts = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM event_consumer_receipts
            WHERE consumer_name = 'institutional_review_engine_v1'
            """
        ).fetchone()["total"]

        connection.commit()

        print("=" * 78)
        print("INSTITUTIONAL REVIEW ENGINE INSTALLATION COMPLETE")
        print("=" * 78)
        print(f"Database backup: {backup}")
        print(f"Engine created: {ENGINE_PATH}")
        print(f"Health check created: {HEALTH_PATH}")
        print("Table created: institutional_reviews")
        print("View created: current_institutional_reviews")
        print(f"Existing review-engine receipts: {prior_receipts}")
        print()
        print("The first run will examine existing opportunity events.")
        print("PASS opportunities will be recorded as skipped.")
        print("MONITOR/WATCHLIST/ACTIONABLE opportunities receive reviews.")
        print()
        print("Run next:")
        print("  python src/institutional_review_engine.py")
        print("  python src/institutional_review_health.py")
        print("=" * 78)

    except Exception:
        connection.rollback()
        print(f"Installation failed. Database backup: {backup}")
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
