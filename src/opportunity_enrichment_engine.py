from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
import uuid
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
)

DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
MIGRATION_PATH = (
    PROJECT_ROOT / "database" / "migrations" / "005_opportunity_enrichment.sql"
)
ENGINE_VERSION = "1.0.0"


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


def logarithmic_score(value: float, reference: float = 1_000_000.0) -> float:
    if value <= 0:
        return 0.0
    return clamp(100.0 * math.log1p(value) / math.log1p(reference))


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    }


def ensure_schema(connection: sqlite3.Connection) -> None:
    if not MIGRATION_PATH.exists():
        raise RuntimeError(f"Migration file not found: {MIGRATION_PATH}")
    connection.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
    create_event_tables(connection)


def value_from(row: sqlite3.Row, *names: str, default: Any = None) -> Any:
    keys = set(row.keys())
    for name in names:
        if name in keys and row[name] is not None:
            return row[name]
    return default


def load_opportunities(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    if not table_exists(connection, "opportunity_intelligence_v2"):
        raise RuntimeError("Required table opportunity_intelligence_v2 is missing.")

    cluster_join = ""
    select_cluster = """
        NULL AS cluster_wallet_count,
        NULL AS cluster_elite_wallet_count,
        NULL AS cluster_combined_capital,
        NULL AS cluster_timing_score,
        NULL AS cluster_timing_status,
        NULL AS cluster_current_price,
        NULL AS cluster_liquidity,
        NULL AS cluster_spread,
        NULL AS cluster_wallet_quality
    """

    if table_exists(connection, "smart_money_clusters"):
        available = columns(connection, "smart_money_clusters")
        if "cluster_id" in available:
            def expr(column: str, alias: str) -> str:
                return (
                    f'c."{column}" AS "{alias}"'
                    if column in available
                    else f'NULL AS "{alias}"'
                )

            select_cluster = ",\n".join(
                [
                    expr("wallet_count", "cluster_wallet_count"),
                    expr("elite_wallet_count", "cluster_elite_wallet_count"),
                    expr("combined_capital", "cluster_combined_capital"),
                    expr("timing_score", "cluster_timing_score"),
                    expr("timing_status", "cluster_timing_status"),
                    expr("current_price", "cluster_current_price"),
                    expr("liquidity", "cluster_liquidity"),
                    expr("spread", "cluster_spread"),
                    (
                        expr("average_wallet_score", "cluster_wallet_quality")
                        if "average_wallet_score" in available
                        else (
                            expr("wallet_quality_score", "cluster_wallet_quality")
                            if "wallet_quality_score" in available
                            else "NULL AS cluster_wallet_quality"
                        )
                    ),
                ]
            )
            cluster_join = """
            LEFT JOIN smart_money_clusters AS c
              ON c.cluster_id = o.source_cluster_id
            """

    return connection.execute(
        f"""
        SELECT
            o.*,
            {select_cluster}
        FROM opportunity_intelligence_v2 AS o
        {cluster_join}
        ORDER BY o.opportunity_score DESC
        """
    ).fetchall()


def historical_reliability(
    connection: sqlite3.Connection,
    market_id: str,
    outcome: str,
    fallback: float,
) -> float:
    if not table_exists(connection, "consensus_history"):
        return fallback

    available = columns(connection, "consensus_history")
    if not {"market_id", "outcome"} <= available:
        return fallback

    score_column = next(
        (
            candidate
            for candidate in ("conviction_score", "score", "consensus_score")
            if candidate in available
        ),
        None,
    )
    if score_column is None:
        samples = connection.execute(
            """
            SELECT COUNT(*)
            FROM consensus_history
            WHERE market_id=? AND outcome=?
            """,
            (market_id, outcome),
        ).fetchone()[0]
        return max(fallback, clamp(35.0 + min(samples, 20) * 2.0))

    result = connection.execute(
        f"""
        SELECT COUNT(*) AS samples, AVG("{score_column}") AS average_score
        FROM consensus_history
        WHERE market_id=? AND outcome=?
        """,
        (market_id, outcome),
    ).fetchone()

    samples = int(result["samples"] or 0)
    score = normalized_score(result["average_score"])
    return max(fallback, clamp(score * 0.75 + min(samples * 4.0, 100.0) * 0.25))


def market_structure(
    current_price: float | None,
    liquidity: float | None,
    spread: float | None,
    fallback: float,
) -> float:
    components: list[tuple[float, float]] = []
    if liquidity is not None:
        components.append((logarithmic_score(max(liquidity, 0.0)), 0.50))
    if spread is not None:
        normalized_spread = spread * 100.0 if 0 <= spread <= 1 else spread
        components.append((clamp(100.0 - normalized_spread * 12.5), 0.30))
    if current_price is not None:
        normalized_price = (
            current_price * 100.0 if 0 <= current_price <= 1 else current_price
        )
        price_score = 70.0
        if normalized_price <= 2 or normalized_price >= 98:
            price_score = 20.0
        elif normalized_price <= 5 or normalized_price >= 95:
            price_score = 40.0
        components.append((price_score, 0.20))

    if not components:
        return fallback

    total_weight = sum(weight for _, weight in components)
    observed = sum(score * weight for score, weight in components) / total_weight
    return clamp(observed * 0.80 + fallback * 0.20)


def checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enrich(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    opportunity_id = str(row["opportunity_id"])
    market_id = str(row["market_id"])
    outcome = str(row["outcome"])
    wallet_count = max(
        0,
        int(
            safe_float(
                value_from(row, "cluster_wallet_count", "wallet_count")
            )
        ),
    )
    elite_count = max(
        0,
        int(
            safe_float(
                value_from(
                    row,
                    "cluster_elite_wallet_count",
                    "elite_wallet_count",
                )
            )
        ),
    )
    capital = max(
        0.0,
        safe_float(
            value_from(
                row,
                "cluster_combined_capital",
                "combined_capital",
            )
        ),
    )

    wallet_quality = normalized_score(
        value_from(
            row,
            "cluster_wallet_quality",
            "wallet_quality_score",
        )
    )
    if wallet_quality <= 0:
        elite_ratio = elite_count / max(wallet_count, 1)
        wallet_quality = clamp(
            35.0 + min(elite_count, 4) * 12.0 + elite_ratio * 28.0
        )

    timing_status = str(
        value_from(
            row,
            "cluster_timing_status",
            "timing_status",
            default="UNKNOWN",
        )
        or "UNKNOWN"
    ).upper()
    timing_score = normalized_score(
        value_from(row, "cluster_timing_score", "timing_score")
    )
    if timing_score <= 0:
        timing_score = {
            "TIGHT": 95.0,
            "COORDINATED": 78.0,
            "DISTRIBUTED": 55.0,
            "STALE": 25.0,
        }.get(timing_status, 35.0)

    def optional_float(*names: str) -> float | None:
        value = value_from(row, *names)
        if value is None:
            return None
        return safe_float(value)

    current_price = optional_float("cluster_current_price", "current_price")
    liquidity = optional_float("cluster_liquidity", "liquidity")
    spread = optional_float("cluster_spread", "spread")

    structure_fallback = normalized_score(row["market_structure_score"])
    structure = market_structure(
        current_price,
        liquidity,
        spread,
        structure_fallback,
    )
    reliability = historical_reliability(
        connection,
        market_id,
        outcome,
        normalized_score(row["historical_reliability_score"]),
    )
    capital_strength = logarithmic_score(capital)

    completeness_inputs = [
        wallet_count > 0,
        elite_count > 0,
        capital > 0,
        timing_status != "UNKNOWN",
        current_price is not None,
        liquidity is not None,
        spread is not None,
        reliability > 0,
    ]
    completeness = 100.0 * sum(completeness_inputs) / len(completeness_inputs)

    evidence = {
        "wallet_source": (
            "smart_money_clusters"
            if value_from(row, "cluster_wallet_count") is not None
            else "opportunity_intelligence_v2"
        ),
        "market_price_available": current_price is not None,
        "liquidity_available": liquidity is not None,
        "spread_available": spread is not None,
        "capital_available": capital > 0,
        "historical_reliability_available": reliability > 0,
    }

    payload = {
        "opportunity_id": opportunity_id,
        "market_id": market_id,
        "outcome": outcome,
        "title": row["title"],
        "category": row["category"],
        "state_checksum": row["state_checksum"],
        "score": normalized_score(row["opportunity_score"]),
        "opportunity_score": normalized_score(row["opportunity_score"]),
        "grade": row["opportunity_grade"],
        "opportunity_grade": row["opportunity_grade"],
        "decision": row["recommendation"],
        "recommendation": row["recommendation"],
        "wallet_count": wallet_count,
        "elite_wallet_count": elite_count,
        "combined_capital": round(capital, 6),
        "wallet_quality_score": round(wallet_quality, 4),
        "capital_strength_score": round(capital_strength, 4),
        "timing_score": round(timing_score, 4),
        "timing_status": timing_status,
        "current_price": current_price,
        "liquidity": liquidity,
        "spread": spread,
        "market_structure_score": round(structure, 4),
        "historical_reliability_score": round(reliability, 4),
        "data_completeness_score": round(completeness, 4),
        "source_cluster_id": row["source_cluster_id"],
        "evidence": evidence,
    }
    payload["enrichment_checksum"] = checksum(payload)
    return payload


def upsert(
    connection: sqlite3.Connection,
    result: dict[str, Any],
    run_id: str,
    observed_at: str,
) -> str:
    old = connection.execute(
        """
        SELECT enrichment_checksum, first_enriched_at
        FROM opportunity_enrichment_current
        WHERE opportunity_id=?
        """,
        (result["opportunity_id"],),
    ).fetchone()

    first_enriched_at = old["first_enriched_at"] if old else observed_at
    status = "unchanged"
    if old is None:
        status = "created"
    elif old["enrichment_checksum"] != result["enrichment_checksum"]:
        status = "updated"

    connection.execute(
        """
        INSERT INTO opportunity_enrichment_current (
            opportunity_id, market_id, outcome, title, category,
            source_state_checksum, enrichment_checksum,
            opportunity_score, opportunity_grade, recommendation,
            wallet_count, elite_wallet_count, combined_capital,
            wallet_quality_score, capital_strength_score,
            timing_score, timing_status, current_price, liquidity, spread,
            market_structure_score, historical_reliability_score,
            data_completeness_score, source_cluster_id, evidence_json,
            model_version, first_enriched_at, last_enriched_at, last_run_id
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(opportunity_id) DO UPDATE SET
            market_id=excluded.market_id,
            outcome=excluded.outcome,
            title=excluded.title,
            category=excluded.category,
            source_state_checksum=excluded.source_state_checksum,
            enrichment_checksum=excluded.enrichment_checksum,
            opportunity_score=excluded.opportunity_score,
            opportunity_grade=excluded.opportunity_grade,
            recommendation=excluded.recommendation,
            wallet_count=excluded.wallet_count,
            elite_wallet_count=excluded.elite_wallet_count,
            combined_capital=excluded.combined_capital,
            wallet_quality_score=excluded.wallet_quality_score,
            capital_strength_score=excluded.capital_strength_score,
            timing_score=excluded.timing_score,
            timing_status=excluded.timing_status,
            current_price=excluded.current_price,
            liquidity=excluded.liquidity,
            spread=excluded.spread,
            market_structure_score=excluded.market_structure_score,
            historical_reliability_score=excluded.historical_reliability_score,
            data_completeness_score=excluded.data_completeness_score,
            source_cluster_id=excluded.source_cluster_id,
            evidence_json=excluded.evidence_json,
            model_version=excluded.model_version,
            last_enriched_at=excluded.last_enriched_at,
            last_run_id=excluded.last_run_id
        """,
        (
            result["opportunity_id"],
            result["market_id"],
            result["outcome"],
            result["title"],
            result["category"],
            result["state_checksum"],
            result["enrichment_checksum"],
            result["opportunity_score"],
            result["opportunity_grade"],
            result["recommendation"],
            result["wallet_count"],
            result["elite_wallet_count"],
            result["combined_capital"],
            result["wallet_quality_score"],
            result["capital_strength_score"],
            result["timing_score"],
            result["timing_status"],
            result["current_price"],
            result["liquidity"],
            result["spread"],
            result["market_structure_score"],
            result["historical_reliability_score"],
            result["data_completeness_score"],
            result["source_cluster_id"],
            json.dumps(result["evidence"], sort_keys=True),
            ENGINE_VERSION,
            first_enriched_at,
            observed_at,
            run_id,
        ),
    )

    if status in {"created", "updated"}:
        connection.execute(
            """
            INSERT OR IGNORE INTO opportunity_enrichment_history (
                opportunity_id, market_id, outcome, observed_at,
                enrichment_checksum, opportunity_score, recommendation,
                wallet_count, elite_wallet_count, combined_capital,
                wallet_quality_score, capital_strength_score, timing_score,
                market_structure_score, historical_reliability_score,
                data_completeness_score, evidence_json, run_id
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                result["opportunity_id"],
                result["market_id"],
                result["outcome"],
                observed_at,
                result["enrichment_checksum"],
                result["opportunity_score"],
                result["recommendation"],
                result["wallet_count"],
                result["elite_wallet_count"],
                result["combined_capital"],
                result["wallet_quality_score"],
                result["capital_strength_score"],
                result["timing_score"],
                result["market_structure_score"],
                result["historical_reliability_score"],
                result["data_completeness_score"],
                json.dumps(result["evidence"], sort_keys=True),
                run_id,
            ),
        )

    return status


def publish_enriched_event(
    connection: sqlite3.Connection,
    result: dict[str, Any],
) -> bool:
    key = build_deduplication_key(
        event_type="OpportunityEnriched",
        aggregate_type="opportunity",
        aggregate_id=result["opportunity_id"],
        state_value=result["enrichment_checksum"],
    )
    event = PlatformEvent.create(
        event_type="OpportunityEnriched",
        source_engine="opportunity_enrichment_engine",
        source_version=ENGINE_VERSION,
        aggregate_type="opportunity",
        aggregate_id=result["opportunity_id"],
        payload=result,
        deduplication_key=key,
    )
    return publish_event(connection, event)


def print_board(connection: sqlite3.Connection, limit: int = 20) -> None:
    rows = connection.execute(
        """
        SELECT
            rank, title, outcome, opportunity_score, recommendation,
            wallet_count, elite_wallet_count, combined_capital,
            market_structure_score, historical_reliability_score,
            data_completeness_score
        FROM ranked_opportunity_enrichment
        ORDER BY rank
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    print()
    print("OPPORTUNITY ENRICHMENT BOARD")
    print("-" * 145)
    for row in rows:
        label = f"{row['title'] or 'Unknown'} | {row['outcome']}"
        print(
            f"{row['rank']:>3} "
            f"{row['opportunity_score']:>6.2f} "
            f"{row['recommendation']:<11} "
            f"W:{row['wallet_count']:<3} "
            f"E:{row['elite_wallet_count']:<3} "
            f"${row['combined_capital']:>12,.2f} "
            f"M:{row['market_structure_score']:>6.2f} "
            f"R:{row['historical_reliability_score']:>6.2f} "
            f"D:{row['data_completeness_score']:>6.2f} "
            f"{label[:64]}"
        )
    print("-" * 145)


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    run_id = (
        f"opportunity-enrichment:"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:"
        f"{uuid.uuid4().hex[:8]}"
    )
    started_at = utc_now()
    counts = {
        "read": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "events": 0,
    }

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        ensure_schema(connection)

        connection.execute(
            """
            INSERT INTO opportunity_enrichment_runs (
                run_id, engine_version, started_at, status
            ) VALUES (?, ?, ?, 'RUNNING')
            """,
            (run_id, ENGINE_VERSION, started_at),
        )
        connection.commit()

        try:
            opportunities = load_opportunities(connection)
            counts["read"] = len(opportunities)
            observed_at = utc_now()

            for row in opportunities:
                result = enrich(connection, row)
                status = upsert(connection, result, run_id, observed_at)
                counts[status] += 1
                if status in {"created", "updated"}:
                    connection.commit()
                    counts["events"] += int(
                        publish_enriched_event(connection, result)
                    )

            connection.execute(
                """
                UPDATE opportunity_enrichment_runs
                SET completed_at=?,
                    status='SUCCESS',
                    opportunities_read=?,
                    enrichments_created=?,
                    enrichments_updated=?,
                    events_published=?
                WHERE run_id=?
                """,
                (
                    utc_now(),
                    counts["read"],
                    counts["created"],
                    counts["updated"],
                    counts["events"],
                    run_id,
                ),
            )
            connection.commit()
            print_board(connection)
        except Exception as error:
            connection.rollback()
            connection.execute(
                """
                UPDATE opportunity_enrichment_runs
                SET completed_at=?, status='FAILED', error_message=?
                WHERE run_id=?
                """,
                (utc_now(), str(error)[:4000], run_id),
            )
            connection.commit()
            raise

    print()
    print("=" * 78)
    print(f"OPPORTUNITY ENRICHMENT ENGINE v{ENGINE_VERSION}")
    print("=" * 78)
    print(f"Opportunities read:       {counts['read']:,}")
    print(f"Enrichments created:      {counts['created']:,}")
    print(f"Enrichments updated:      {counts['updated']:,}")
    print(f"Enrichments unchanged:    {counts['unchanged']:,}")
    print(f"Events published:         {counts['events']:,}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
