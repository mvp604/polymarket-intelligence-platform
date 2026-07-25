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
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "2.0.0"


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


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def view_exists(connection: sqlite3.Connection, view: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name=?",
        (view,),
    ).fetchone() is not None


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def normalized_score(value: Any) -> float:
    number = safe_float(value)
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return clamp(number)


def logarithmic_score(value: float, reference: float) -> float:
    if value <= 0:
        return 0.0
    return clamp(100.0 * math.log1p(value) / math.log1p(reference))


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


def recommendation_for(score: float, grade: str, timing_status: str) -> str:
    if grade == "S+" and timing_status in {"TIGHT", "COORDINATED"}:
        return "ACTIONABLE"
    if grade in {"S+", "S"}:
        return "WATCHLIST"
    if grade in {"A+", "A", "B"}:
        return "MONITOR"
    return "PASS"


def explanation(
    smart_money: float,
    wallet_quality: float,
    timing: float,
    capital: float,
    consensus: float,
    market_structure: float,
    reliability: float,
    wallet_count: int,
    elite_count: int,
    timing_status: str,
) -> str:
    reasons: list[str] = []

    if smart_money >= 80:
        reasons.append("Smart Money conviction is strong")
    elif smart_money >= 65:
        reasons.append("Smart Money conviction is constructive")
    else:
        reasons.append("Smart Money conviction is limited")

    if elite_count >= 2:
        reasons.append(f"{elite_count} elite wallets support the cluster")
    elif elite_count == 1:
        reasons.append("one elite wallet supports the cluster")
    else:
        reasons.append("elite-wallet confirmation is absent")

    if timing_status == "TIGHT":
        reasons.append("wallet entries are tightly synchronized")
    elif timing_status == "COORDINATED":
        reasons.append("wallet entries formed within a coordinated window")
    elif timing_status == "DISTRIBUTED":
        reasons.append("wallet accumulation is spread across time")
    elif timing_status == "STALE":
        reasons.append("the entry pattern may be stale")
    else:
        reasons.append("timing evidence remains incomplete")

    if capital >= 75:
        reasons.append("capital deployment is substantial")
    if consensus >= 75:
        reasons.append(f"consensus is broad across {wallet_count} wallets")
    if market_structure < 45:
        reasons.append("market structure reduces confidence")
    if reliability < 45:
        reasons.append("historical reliability is not yet established")

    return ". ".join(reasons) + "."


def state_checksum(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS opportunity_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            clusters_read INTEGER NOT NULL DEFAULT 0,
            opportunities_scored INTEGER NOT NULL DEFAULT 0,
            actionable_count INTEGER NOT NULL DEFAULT 0,
            watchlist_count INTEGER NOT NULL DEFAULT 0,
            monitor_count INTEGER NOT NULL DEFAULT 0,
            pass_count INTEGER NOT NULL DEFAULT 0,
            warnings_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS opportunity_intelligence_v2 (
            opportunity_id TEXT PRIMARY KEY,
            market_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            title TEXT,
            category TEXT,
            smart_money_score REAL NOT NULL,
            wallet_quality_score REAL NOT NULL,
            timing_score REAL NOT NULL,
            capital_score REAL NOT NULL,
            consensus_score REAL NOT NULL,
            market_structure_score REAL NOT NULL,
            historical_reliability_score REAL NOT NULL,
            opportunity_score REAL NOT NULL,
            opportunity_grade TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            timing_status TEXT NOT NULL,
            entry_window_minutes REAL,
            wallet_count INTEGER NOT NULL,
            elite_wallet_count INTEGER NOT NULL,
            combined_capital REAL NOT NULL,
            current_price REAL,
            liquidity REAL,
            spread REAL,
            explanation TEXT NOT NULL,
            state_checksum TEXT NOT NULL,
            source_cluster_id TEXT NOT NULL,
            first_detected_at TEXT NOT NULL,
            last_updated_at TEXT NOT NULL,
            last_run_id TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_opportunity_v2_rank
        ON opportunity_intelligence_v2(recommendation, opportunity_score DESC);

        CREATE INDEX IF NOT EXISTS idx_opportunity_v2_market
        ON opportunity_intelligence_v2(market_id, outcome);

        CREATE TABLE IF NOT EXISTS opportunity_intelligence_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id TEXT NOT NULL,
            market_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            opportunity_score REAL NOT NULL,
            opportunity_grade TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            smart_money_score REAL NOT NULL,
            wallet_quality_score REAL NOT NULL,
            timing_score REAL NOT NULL,
            capital_score REAL NOT NULL,
            consensus_score REAL NOT NULL,
            market_structure_score REAL NOT NULL,
            historical_reliability_score REAL NOT NULL,
            wallet_count INTEGER NOT NULL,
            elite_wallet_count INTEGER NOT NULL,
            combined_capital REAL NOT NULL,
            current_price REAL,
            state_checksum TEXT NOT NULL,
            run_id TEXT NOT NULL,
            UNIQUE(opportunity_id, state_checksum)
        );

        CREATE INDEX IF NOT EXISTS idx_opportunity_history_market_time
        ON opportunity_intelligence_history(market_id, outcome, observed_at);

        DROP VIEW IF EXISTS ranked_opportunity_intelligence_v2;
        CREATE VIEW ranked_opportunity_intelligence_v2 AS
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY
                    CASE recommendation
                        WHEN 'ACTIONABLE' THEN 1
                        WHEN 'WATCHLIST' THEN 2
                        WHEN 'MONITOR' THEN 3
                        ELSE 4
                    END,
                    opportunity_score DESC,
                    combined_capital DESC
            ) AS rank,
            *
        FROM opportunity_intelligence_v2;
        """
    )


@dataclass
class ClusterColumns:
    cluster_id: str
    market_id: str
    outcome: str
    title: str | None
    category: str | None
    smart_money_score: str
    wallet_count: str
    elite_wallet_count: str
    combined_capital: str
    timing_score: str | None
    timing_status: str | None
    entry_window_minutes: str | None
    current_price: str | None
    liquidity: str | None
    spread: str | None
    average_wallet_score: str | None


def detect_cluster_columns(connection: sqlite3.Connection) -> ClusterColumns:
    if not table_exists(connection, "smart_money_clusters"):
        raise RuntimeError("Required table smart_money_clusters does not exist.")

    available = columns(connection, "smart_money_clusters")

    required = {
        "cluster_id",
        "market_id",
        "outcome",
        "smart_money_score",
        "wallet_count",
        "elite_wallet_count",
        "combined_capital",
    }
    missing = sorted(required - available)
    if missing:
        raise RuntimeError(
            "smart_money_clusters is missing required columns: " + ", ".join(missing)
        )

    def optional(*names: str) -> str | None:
        for name in names:
            if name in available:
                return name
        return None

    return ClusterColumns(
        cluster_id="cluster_id",
        market_id="market_id",
        outcome="outcome",
        title=optional("title", "market_title", "question"),
        category=optional("category", "market_category", "sport"),
        smart_money_score="smart_money_score",
        wallet_count="wallet_count",
        elite_wallet_count="elite_wallet_count",
        combined_capital="combined_capital",
        timing_score=optional("timing_score"),
        timing_status=optional("timing_status"),
        entry_window_minutes=optional("entry_window_minutes"),
        current_price=optional("current_price", "price", "average_current_price"),
        liquidity=optional("liquidity", "market_liquidity"),
        spread=optional("spread", "bid_ask_spread"),
        average_wallet_score=optional("average_wallet_score", "elite_quality_score", "wallet_quality_score"),
    )


def select_expression(column: str | None, alias: str, default_sql: str = "NULL") -> str:
    if column:
        return f'"{column}" AS "{alias}"'
    return f"{default_sql} AS \"{alias}\""


def load_clusters(connection: sqlite3.Connection, cc: ClusterColumns) -> list[sqlite3.Row]:
    expressions = [
        select_expression(cc.cluster_id, "cluster_id"),
        select_expression(cc.market_id, "market_id"),
        select_expression(cc.outcome, "outcome"),
        select_expression(cc.title, "title"),
        select_expression(cc.category, "category"),
        select_expression(cc.smart_money_score, "smart_money_score"),
        select_expression(cc.wallet_count, "wallet_count"),
        select_expression(cc.elite_wallet_count, "elite_wallet_count"),
        select_expression(cc.combined_capital, "combined_capital"),
        select_expression(cc.timing_score, "timing_score"),
        select_expression(cc.timing_status, "timing_status", "'UNKNOWN'"),
        select_expression(cc.entry_window_minutes, "entry_window_minutes"),
        select_expression(cc.current_price, "current_price"),
        select_expression(cc.liquidity, "liquidity"),
        select_expression(cc.spread, "spread"),
        select_expression(cc.average_wallet_score, "average_wallet_score"),
    ]
    return connection.execute(
        f'SELECT {", ".join(expressions)} FROM smart_money_clusters'
    ).fetchall()


def market_structure_score(price: float | None, liquidity: float | None, spread: float | None) -> float:
    score = 50.0

    if liquidity is not None:
        score = 0.65 * logarithmic_score(max(liquidity, 0.0), 1_000_000.0) + 0.35 * score

    if spread is not None:
        normalized_spread = spread * 100.0 if 0.0 <= spread <= 1.0 else spread
        spread_component = clamp(100.0 - normalized_spread * 12.5)
        score = 0.65 * score + 0.35 * spread_component

    if price is not None:
        normalized_price = price * 100.0 if 0.0 <= price <= 1.0 else price
        if normalized_price <= 2.0 or normalized_price >= 98.0:
            score -= 12.0
        elif normalized_price <= 5.0 or normalized_price >= 95.0:
            score -= 6.0

    return clamp(score)


def historical_reliability(connection: sqlite3.Connection, market_id: str, outcome: str) -> float:
    if not table_exists(connection, "consensus_history"):
        return 40.0

    available = columns(connection, "consensus_history")
    if not {"market_id", "outcome"} <= available:
        return 40.0

    score_column = None
    for candidate in ("conviction_score", "score", "consensus_score"):
        if candidate in available:
            score_column = candidate
            break

    if score_column is None:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM consensus_history
            WHERE market_id=? AND outcome=?
            """,
            (market_id, outcome),
        ).fetchone()[0]
        return clamp(35.0 + min(count, 20) * 2.0)

    row = connection.execute(
        f"""
        SELECT COUNT(*) AS samples, AVG("{score_column}") AS average_score
        FROM consensus_history
        WHERE market_id=? AND outcome=?
        """,
        (market_id, outcome),
    ).fetchone()

    samples = int(row["samples"] or 0)
    average = normalized_score(row["average_score"])
    sample_component = clamp(samples * 5.0)
    return clamp(0.7 * average + 0.3 * sample_component)


def score_cluster(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    cluster_id = str(row["cluster_id"])
    market_id = str(row["market_id"])
    outcome = str(row["outcome"] or "UNKNOWN")
    title = str(row["title"] or market_id)
    category = str(row["category"] or "Unclassified")

    smart_money = normalized_score(row["smart_money_score"])
    wallet_count = max(0, int(safe_float(row["wallet_count"])))
    elite_count = max(0, int(safe_float(row["elite_wallet_count"])))
    capital_value = max(0.0, safe_float(row["combined_capital"]))

    timing_status = str(row["timing_status"] or "UNKNOWN").upper()
    if row["timing_score"] is not None:
        timing = normalized_score(row["timing_score"])
    else:
        timing = {
            "TIGHT": 95.0,
            "COORDINATED": 78.0,
            "DISTRIBUTED": 55.0,
            "STALE": 25.0,
        }.get(timing_status, 35.0)

    if row["average_wallet_score"] is not None:
        wallet_quality = normalized_score(row["average_wallet_score"])
    else:
        elite_ratio = elite_count / max(wallet_count, 1)
        wallet_quality = clamp(
            35.0
            + min(elite_count, 4) * 12.0
            + elite_ratio * 28.0
        )

    capital = logarithmic_score(capital_value, 1_000_000.0)
    consensus = clamp(
        22.0
        + min(wallet_count, 10) * 6.5
        + min(elite_count, 4) * 5.0
    )

    current_price = safe_float(row["current_price"], default=float("nan"))
    if math.isnan(current_price):
        current_price = None
    liquidity = safe_float(row["liquidity"], default=float("nan"))
    if math.isnan(liquidity):
        liquidity = None
    spread = safe_float(row["spread"], default=float("nan"))
    if math.isnan(spread):
        spread = None

    structure = market_structure_score(current_price, liquidity, spread)
    reliability = historical_reliability(connection, market_id, outcome)

    opportunity = clamp(
        smart_money * 0.30
        + wallet_quality * 0.20
        + timing * 0.15
        + capital * 0.10
        + consensus * 0.10
        + structure * 0.10
        + reliability * 0.05
    )

    grade = grade_for(opportunity)
    recommendation = recommendation_for(opportunity, grade, timing_status)
    explanation_text = explanation(
        smart_money,
        wallet_quality,
        timing,
        capital,
        consensus,
        structure,
        reliability,
        wallet_count,
        elite_count,
        timing_status,
    )

    opportunity_id = hashlib.sha256(
        f"{market_id}|{outcome}|{cluster_id}".encode("utf-8")
    ).hexdigest()[:32]

    payload = {
        "opportunity_id": opportunity_id,
        "market_id": market_id,
        "outcome": outcome,
        "title": title,
        "category": category,
        "smart_money_score": round(smart_money, 4),
        "wallet_quality_score": round(wallet_quality, 4),
        "timing_score": round(timing, 4),
        "capital_score": round(capital, 4),
        "consensus_score": round(consensus, 4),
        "market_structure_score": round(structure, 4),
        "historical_reliability_score": round(reliability, 4),
        "opportunity_score": round(opportunity, 4),
        "opportunity_grade": grade,
        "recommendation": recommendation,
        "timing_status": timing_status,
        "entry_window_minutes": (
            safe_float(row["entry_window_minutes"])
            if row["entry_window_minutes"] is not None
            else None
        ),
        "wallet_count": wallet_count,
        "elite_wallet_count": elite_count,
        "combined_capital": round(capital_value, 6),
        "current_price": current_price,
        "liquidity": liquidity,
        "spread": spread,
        "explanation": explanation_text,
        "source_cluster_id": cluster_id,
    }
    payload["state_checksum"] = state_checksum(payload)
    return payload


def upsert_opportunity(
    connection: sqlite3.Connection,
    result: dict[str, Any],
    run_id: str,
    observed_at: str,
) -> bool:
    old = connection.execute(
        """
        SELECT first_detected_at, state_checksum
        FROM opportunity_intelligence_v2
        WHERE opportunity_id=?
        """,
        (result["opportunity_id"],),
    ).fetchone()

    first_detected = old["first_detected_at"] if old else observed_at

    connection.execute(
        """
        INSERT INTO opportunity_intelligence_v2 (
            opportunity_id, market_id, outcome, title, category,
            smart_money_score, wallet_quality_score, timing_score,
            capital_score, consensus_score, market_structure_score,
            historical_reliability_score, opportunity_score,
            opportunity_grade, recommendation, timing_status,
            entry_window_minutes, wallet_count, elite_wallet_count,
            combined_capital, current_price, liquidity, spread,
            explanation, state_checksum, source_cluster_id,
            first_detected_at, last_updated_at, last_run_id
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(opportunity_id) DO UPDATE SET
            market_id=excluded.market_id,
            outcome=excluded.outcome,
            title=excluded.title,
            category=excluded.category,
            smart_money_score=excluded.smart_money_score,
            wallet_quality_score=excluded.wallet_quality_score,
            timing_score=excluded.timing_score,
            capital_score=excluded.capital_score,
            consensus_score=excluded.consensus_score,
            market_structure_score=excluded.market_structure_score,
            historical_reliability_score=excluded.historical_reliability_score,
            opportunity_score=excluded.opportunity_score,
            opportunity_grade=excluded.opportunity_grade,
            recommendation=excluded.recommendation,
            timing_status=excluded.timing_status,
            entry_window_minutes=excluded.entry_window_minutes,
            wallet_count=excluded.wallet_count,
            elite_wallet_count=excluded.elite_wallet_count,
            combined_capital=excluded.combined_capital,
            current_price=excluded.current_price,
            liquidity=excluded.liquidity,
            spread=excluded.spread,
            explanation=excluded.explanation,
            state_checksum=excluded.state_checksum,
            source_cluster_id=excluded.source_cluster_id,
            last_updated_at=excluded.last_updated_at,
            last_run_id=excluded.last_run_id
        """,
        (
            result["opportunity_id"],
            result["market_id"],
            result["outcome"],
            result["title"],
            result["category"],
            result["smart_money_score"],
            result["wallet_quality_score"],
            result["timing_score"],
            result["capital_score"],
            result["consensus_score"],
            result["market_structure_score"],
            result["historical_reliability_score"],
            result["opportunity_score"],
            result["opportunity_grade"],
            result["recommendation"],
            result["timing_status"],
            result["entry_window_minutes"],
            result["wallet_count"],
            result["elite_wallet_count"],
            result["combined_capital"],
            result["current_price"],
            result["liquidity"],
            result["spread"],
            result["explanation"],
            result["state_checksum"],
            result["source_cluster_id"],
            first_detected,
            observed_at,
            run_id,
        ),
    )

    changed = old is None or old["state_checksum"] != result["state_checksum"]
    if changed:
        connection.execute(
            """
            INSERT OR IGNORE INTO opportunity_intelligence_history (
                opportunity_id, market_id, outcome, observed_at,
                opportunity_score, opportunity_grade, recommendation,
                smart_money_score, wallet_quality_score, timing_score,
                capital_score, consensus_score, market_structure_score,
                historical_reliability_score, wallet_count,
                elite_wallet_count, combined_capital, current_price,
                state_checksum, run_id
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                result["opportunity_id"],
                result["market_id"],
                result["outcome"],
                observed_at,
                result["opportunity_score"],
                result["opportunity_grade"],
                result["recommendation"],
                result["smart_money_score"],
                result["wallet_quality_score"],
                result["timing_score"],
                result["capital_score"],
                result["consensus_score"],
                result["market_structure_score"],
                result["historical_reliability_score"],
                result["wallet_count"],
                result["elite_wallet_count"],
                result["combined_capital"],
                result["current_price"],
                result["state_checksum"],
                run_id,
            ),
        )
    return changed


def print_top_board(connection: sqlite3.Connection, limit: int = 20) -> None:
    rows = connection.execute(
        """
        SELECT
            rank, title, outcome, opportunity_score, opportunity_grade,
            recommendation, timing_status, wallet_count,
            elite_wallet_count, combined_capital
        FROM ranked_opportunity_intelligence_v2
        ORDER BY rank
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    print()
    print("TOP OPPORTUNITY BOARD")
    print("-" * 140)
    print(
        f"{'Rank':>4}  {'Score':>6}  {'Grade':<5}  {'Decision':<11}  "
        f"{'Timing':<12}  {'Wallets':>7}  {'Elite':>5}  {'Capital':>14}  Market / Outcome"
    )
    print("-" * 140)
    for row in rows:
        label = f"{row['title']} | {row['outcome']}"
        if len(label) > 64:
            label = label[:61] + "..."
        print(
            f"{row['rank']:>4}  {row['opportunity_score']:>6.2f}  "
            f"{row['opportunity_grade']:<5}  {row['recommendation']:<11}  "
            f"{row['timing_status']:<12}  {row['wallet_count']:>7}  "
            f"{row['elite_wallet_count']:>5}  ${row['combined_capital']:>13,.2f}  {label}"
        )
    print("-" * 140)


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    run_id = f"opportunity-v2:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:8]}"
    started_at = utc_now()
    warnings: list[str] = []

    print("=" * 140)
    print(f"OPPORTUNITY INTELLIGENCE ENGINE v{ENGINE_VERSION}")
    print("=" * 140)
    print(f"Run ID:   {run_id}")
    print(f"Database: {DATABASE_PATH}")

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        ensure_schema(connection)
        cluster_columns = detect_cluster_columns(connection)
        cluster_rows = load_clusters(connection, cluster_columns)

        connection.execute(
            """
            INSERT INTO opportunity_intelligence_runs (
                run_id, engine_version, started_at, status, clusters_read, warnings_json
            ) VALUES (?, ?, ?, 'RUNNING', ?, ?)
            """,
            (run_id, ENGINE_VERSION, started_at, len(cluster_rows), json.dumps(warnings)),
        )
        connection.commit()

        counts = {
            "ACTIONABLE": 0,
            "WATCHLIST": 0,
            "MONITOR": 0,
            "PASS": 0,
        }
        history_changes = 0
        observed_at = utc_now()

        for row in cluster_rows:
            result = score_cluster(connection, row)
            history_changes += int(
                upsert_opportunity(connection, result, run_id, observed_at)
            )
            counts[result["recommendation"]] += 1

        connection.execute(
            """
            UPDATE opportunity_intelligence_runs
            SET
                completed_at=?,
                status='SUCCESS',
                opportunities_scored=?,
                actionable_count=?,
                watchlist_count=?,
                monitor_count=?,
                pass_count=?,
                warnings_json=?
            WHERE run_id=?
            """,
            (
                utc_now(),
                len(cluster_rows),
                counts["ACTIONABLE"],
                counts["WATCHLIST"],
                counts["MONITOR"],
                counts["PASS"],
                json.dumps(warnings),
                run_id,
            ),
        )
        connection.commit()

        print_top_board(connection)

        total_current = connection.execute(
            "SELECT COUNT(*) FROM opportunity_intelligence_v2"
        ).fetchone()[0]
        total_history = connection.execute(
            "SELECT COUNT(*) FROM opportunity_intelligence_history"
        ).fetchone()[0]

    print()
    print("OPPORTUNITY INTELLIGENCE HEALTH SUMMARY")
    print("-" * 140)
    print("Status:                    SUCCESS")
    print(f"Clusters read:             {len(cluster_rows):,}")
    print(f"Opportunities scored:      {len(cluster_rows):,}")
    print(f"State changes archived:    {history_changes:,}")
    print(f"Current opportunities:     {total_current:,}")
    print(f"Historical score records:  {total_history:,}")
    print(f"Actionable:                {counts['ACTIONABLE']:,}")
    print(f"Watchlist:                 {counts['WATCHLIST']:,}")
    print(f"Monitor:                   {counts['MONITOR']:,}")
    print(f"Pass:                      {counts['PASS']:,}")
    print(f"Warnings:                  {len(warnings):,}")
    print("=" * 140)
    print("OPPORTUNITY INTELLIGENCE COMPLETE")
    print("=" * 140)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
