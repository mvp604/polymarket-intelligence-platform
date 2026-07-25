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
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.0.0"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def fnum(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def probability(value: Any) -> float | None:
    number = fnum(value)
    if number is None:
        return None
    if 0 <= number <= 1:
        return number
    if 0 <= number <= 100:
        return number / 100
    return None


def canonical(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    low = text.lower()
    if low in {"yes", "y", "true", "1"}:
        return "Yes"
    if low in {"no", "n", "false", "0"}:
        return "No"
    return text


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {
        "1", "true", "yes", "resolved", "closed", "complete", "completed", "final"
    }


def tables(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    ]


def cols(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')]


def pick(available: list[str], *names: str) -> str | None:
    lookup = {name.lower(): name for name in available}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        '''
        CREATE TABLE IF NOT EXISTS outcome_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            source_table TEXT,
            source_rows INTEGER NOT NULL DEFAULT 0,
            confirmed_resolutions INTEGER NOT NULL DEFAULT 0,
            new_resolutions INTEGER NOT NULL DEFAULT 0,
            opportunities_evaluated INTEGER NOT NULL DEFAULT 0,
            warnings_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS market_resolution_history (
            market_id TEXT PRIMARY KEY,
            title TEXT,
            winning_outcome TEXT NOT NULL,
            resolved_at TEXT,
            final_probability REAL,
            resolution_source TEXT NOT NULL,
            resolution_method TEXT NOT NULL,
            source_timestamp TEXT,
            first_detected_at TEXT NOT NULL,
            last_verified_at TEXT NOT NULL,
            resolution_checksum TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS opportunity_resolution_results (
            opportunity_id TEXT PRIMARY KEY,
            market_id TEXT NOT NULL,
            predicted_outcome TEXT NOT NULL,
            actual_outcome TEXT NOT NULL,
            correct_prediction INTEGER NOT NULL,
            entry_price REAL,
            gross_return_multiple REAL,
            realized_roi REAL,
            opportunity_score REAL,
            opportunity_grade TEXT,
            recommendation TEXT,
            timing_status TEXT,
            resolved_at TEXT,
            evaluated_at TEXT NOT NULL,
            source_resolution_checksum TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS outcome_feature_performance (
            feature_name TEXT NOT NULL,
            feature_value TEXT NOT NULL,
            sample_count INTEGER NOT NULL,
            correct_count INTEGER NOT NULL,
            accuracy REAL NOT NULL,
            average_roi REAL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(feature_name, feature_value)
        );

        DROP VIEW IF EXISTS outcome_performance_summary;
        CREATE VIEW outcome_performance_summary AS
        SELECT
            COUNT(*) AS evaluated_opportunities,
            COALESCE(SUM(correct_prediction), 0) AS correct_predictions,
            ROUND(100.0 * AVG(correct_prediction), 2) AS accuracy_percent,
            ROUND(100.0 * AVG(realized_roi), 2) AS average_roi_percent
        FROM opportunity_resolution_results;

        DROP VIEW IF EXISTS opportunity_grade_performance;
        CREATE VIEW opportunity_grade_performance AS
        SELECT
            COALESCE(opportunity_grade, 'UNKNOWN') AS opportunity_grade,
            COUNT(*) AS sample_count,
            SUM(correct_prediction) AS correct_count,
            ROUND(100.0 * AVG(correct_prediction), 2) AS accuracy_percent,
            ROUND(100.0 * AVG(realized_roi), 2) AS average_roi_percent
        FROM opportunity_resolution_results
        GROUP BY COALESCE(opportunity_grade, 'UNKNOWN');
        '''
    )


def discover(connection: sqlite3.Connection) -> dict[str, str | None]:
    preferred = [
        "market_snapshots",
        "official_market_snapshots",
        "gamma_market_snapshots",
        "markets",
        "gamma_markets",
    ]
    candidates = preferred + [t for t in tables(connection) if t not in preferred]
    best: tuple[int, dict[str, str | None]] | None = None

    for table in candidates:
        available = cols(connection, table)
        market_id = pick(available, "market_id", "condition_id", "conditionId", "id", "slug")
        if not market_id:
            continue
        mapping = {
            "table": table,
            "market_id": market_id,
            "title": pick(available, "title", "question", "market_title", "name"),
            "resolved": pick(available, "resolved", "is_resolved", "resolution_status"),
            "winner": pick(
                available,
                "winning_outcome", "winner", "resolved_outcome", "resolution", "result"
            ),
            "outcome": pick(available, "outcome", "token_outcome"),
            "price": pick(
                available,
                "final_price", "settlement_price", "price", "current_price", "last_price"
            ),
            "outcomes": pick(available, "outcomes", "outcome_names"),
            "prices": pick(
                available, "outcome_prices", "outcomePrices", "prices", "token_prices"
            ),
            "resolved_at": pick(
                available, "resolved_at", "resolution_time", "closed_at", "end_date", "endDate"
            ),
            "timestamp": pick(
                available, "timestamp", "observed_at", "scanned_at", "updated_at", "created_at"
            ),
        }
        score = (
            (6 if mapping["winner"] else 0)
            + (5 if mapping["outcomes"] and mapping["prices"] else 0)
            + (3 if mapping["resolved"] else 0)
            + (2 if mapping["resolved_at"] else 0)
            + (1 if table in preferred else 0)
        )
        if score and (best is None or score > best[0]):
            best = (score, mapping)

    if best is None:
        raise RuntimeError("No suitable resolution source table was found.")
    return best[1]


def expr(column: str | None, alias: str) -> str:
    return f'"{column}" AS "{alias}"' if column else f'NULL AS "{alias}"'


def read_source(connection: sqlite3.Connection, source: dict[str, str | None]) -> list[sqlite3.Row]:
    fields = [
        expr(source["market_id"], "market_id"),
        expr(source["title"], "title"),
        expr(source["resolved"], "resolved"),
        expr(source["winner"], "winner"),
        expr(source["outcome"], "outcome"),
        expr(source["price"], "price"),
        expr(source["outcomes"], "outcomes"),
        expr(source["prices"], "prices"),
        expr(source["resolved_at"], "resolved_at"),
        expr(source["timestamp"], "source_timestamp"),
    ]
    return connection.execute(
        f'SELECT {", ".join(fields)} FROM "{source["table"]}"'
    ).fetchall()


def json_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if value is None:
        return None
    try:
        return json.loads(str(value))
    except (json.JSONDecodeError, TypeError):
        return None


def derive(row: sqlite3.Row) -> tuple[str, float | None, str] | None:
    winner = canonical(row["winner"])
    if winner and winner.lower() not in {
        "resolved", "closed", "complete", "completed", "true", "false"
    }:
        return winner, probability(row["price"]), "explicit_winner"

    outcomes = json_value(row["outcomes"])
    prices = json_value(row["prices"])
    if isinstance(outcomes, list) and isinstance(prices, list) and len(outcomes) == len(prices):
        pairs = []
        for outcome, price in zip(outcomes, prices):
            name = canonical(outcome)
            prob = probability(price)
            if name is not None and prob is not None:
                pairs.append((name, prob))
        if pairs:
            selected = max(pairs, key=lambda pair: pair[1])
            others = [p for name, p in pairs if name != selected[0]]
            if selected[1] >= 0.99 and all(p <= 0.01 for p in others):
                return selected[0], selected[1], "settlement_prices"
            if truthy(row["resolved"]) and selected[1] >= 0.95:
                return selected[0], selected[1], "resolved_price_array"

    outcome = canonical(row["outcome"])
    price = probability(row["price"])
    if outcome and price is not None:
        if price >= 0.99:
            return outcome, price, "single_outcome_settlement"
        if price <= 0.01 and outcome in {"Yes", "No"}:
            return ("No" if outcome == "Yes" else "Yes"), 1 - price, "binary_inverse"

    return None


def confirmed_resolutions(rows: list[sqlite3.Row]) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    for row in rows:
        market_id = str(row["market_id"] or "").strip()
        result = derive(row)
        if not market_id or result is None:
            continue
        winner, final_probability, method = result
        item = {
            "market_id": market_id,
            "title": str(row["title"] or market_id),
            "winner": winner,
            "probability": final_probability,
            "method": method,
            "resolved_at": str(row["resolved_at"]) if row["resolved_at"] is not None else None,
            "timestamp": (
                str(row["source_timestamp"])
                if row["source_timestamp"] is not None
                else None
            ),
        }
        previous = resolved.get(market_id)
        if previous is None:
            resolved[market_id] = item
        else:
            old_time = previous["timestamp"] or previous["resolved_at"] or ""
            new_time = item["timestamp"] or item["resolved_at"] or ""
            if new_time >= old_time:
                resolved[market_id] = item
    return resolved


def checksum(item: dict[str, Any]) -> str:
    body = json.dumps(
        {
            "market_id": item["market_id"],
            "winner": item["winner"],
            "probability": item["probability"],
            "resolved_at": item["resolved_at"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()


def store_resolutions(
    connection: sqlite3.Connection,
    source_table: str,
    items: dict[str, dict[str, Any]],
) -> int:
    current_time = now()
    inserted = 0
    for item in items.values():
        digest = checksum(item)
        exists = connection.execute(
            "SELECT 1 FROM market_resolution_history WHERE market_id=?",
            (item["market_id"],),
        ).fetchone()
        inserted += int(exists is None)
        connection.execute(
            '''
            INSERT INTO market_resolution_history (
                market_id, title, winning_outcome, resolved_at,
                final_probability, resolution_source, resolution_method,
                source_timestamp, first_detected_at, last_verified_at,
                resolution_checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(market_id) DO UPDATE SET
                title=excluded.title,
                winning_outcome=excluded.winning_outcome,
                resolved_at=COALESCE(excluded.resolved_at, market_resolution_history.resolved_at),
                final_probability=excluded.final_probability,
                resolution_source=excluded.resolution_source,
                resolution_method=excluded.resolution_method,
                source_timestamp=excluded.source_timestamp,
                last_verified_at=excluded.last_verified_at,
                resolution_checksum=excluded.resolution_checksum
            ''',
            (
                item["market_id"],
                item["title"],
                item["winner"],
                item["resolved_at"],
                item["probability"],
                source_table,
                item["method"],
                item["timestamp"],
                current_time,
                current_time,
                digest,
            ),
        )
    return inserted


def evaluate(connection: sqlite3.Connection) -> int:
    if "opportunity_intelligence_v2" not in tables(connection):
        return 0
    rows = connection.execute(
        '''
        SELECT
            o.opportunity_id, o.market_id, o.outcome,
            o.current_price, o.opportunity_score,
            o.opportunity_grade, o.recommendation, o.timing_status,
            r.winning_outcome, r.resolved_at, r.resolution_checksum
        FROM opportunity_intelligence_v2 o
        JOIN market_resolution_history r ON r.market_id=o.market_id
        '''
    ).fetchall()

    current_time = now()
    for row in rows:
        predicted = canonical(row["outcome"]) or str(row["outcome"])
        actual = canonical(row["winning_outcome"]) or str(row["winning_outcome"])
        correct = int(predicted == actual)
        entry = probability(row["current_price"])
        multiple = None
        roi = None
        if entry is not None and 0 < entry <= 1:
            multiple = (1 / entry) if correct else 0
            roi = multiple - 1
        connection.execute(
            '''
            INSERT INTO opportunity_resolution_results (
                opportunity_id, market_id, predicted_outcome, actual_outcome,
                correct_prediction, entry_price, gross_return_multiple,
                realized_roi, opportunity_score, opportunity_grade,
                recommendation, timing_status, resolved_at, evaluated_at,
                source_resolution_checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(opportunity_id) DO UPDATE SET
                actual_outcome=excluded.actual_outcome,
                correct_prediction=excluded.correct_prediction,
                entry_price=excluded.entry_price,
                gross_return_multiple=excluded.gross_return_multiple,
                realized_roi=excluded.realized_roi,
                opportunity_score=excluded.opportunity_score,
                opportunity_grade=excluded.opportunity_grade,
                recommendation=excluded.recommendation,
                timing_status=excluded.timing_status,
                resolved_at=excluded.resolved_at,
                evaluated_at=excluded.evaluated_at,
                source_resolution_checksum=excluded.source_resolution_checksum
            ''',
            (
                row["opportunity_id"], row["market_id"], predicted, actual,
                correct, entry, multiple, roi, row["opportunity_score"],
                row["opportunity_grade"], row["recommendation"],
                row["timing_status"], row["resolved_at"], current_time,
                row["resolution_checksum"],
            ),
        )
    return len(rows)


def refresh_features(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM outcome_feature_performance")
    current_time = now()
    for feature in ("opportunity_grade", "recommendation", "timing_status"):
        rows = connection.execute(
            f'''
            SELECT COALESCE("{feature}", 'UNKNOWN') AS value,
                   COUNT(*) AS samples,
                   SUM(correct_prediction) AS correct,
                   AVG(correct_prediction) AS accuracy,
                   AVG(realized_roi) AS roi
            FROM opportunity_resolution_results
            GROUP BY COALESCE("{feature}", 'UNKNOWN')
            '''
        ).fetchall()
        for row in rows:
            connection.execute(
                '''
                INSERT INTO outcome_feature_performance (
                    feature_name, feature_value, sample_count,
                    correct_count, accuracy, average_roi, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    feature, row["value"], row["samples"], row["correct"],
                    row["accuracy"], row["roi"], current_time,
                ),
            )


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    run_id = f"outcome:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:8]}"
    print("=" * 112)
    print(f"OUTCOME INTELLIGENCE ENGINE v{ENGINE_VERSION}")
    print("=" * 112)
    print(f"Run ID:   {run_id}")
    print(f"Database: {DATABASE_PATH}")

    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=30000")
            ensure_schema(connection)
            source = discover(connection)
            source_rows = read_source(connection, source)
            confirmed = confirmed_resolutions(source_rows)

            connection.execute(
                '''
                INSERT INTO outcome_intelligence_runs (
                    run_id, engine_version, started_at, status,
                    source_table, source_rows, warnings_json
                ) VALUES (?, ?, ?, 'RUNNING', ?, ?, '[]')
                ''',
                (run_id, ENGINE_VERSION, now(), source["table"], len(source_rows)),
            )

            new_count = store_resolutions(connection, str(source["table"]), confirmed)
            evaluated = evaluate(connection)
            refresh_features(connection)

            connection.execute(
                '''
                UPDATE outcome_intelligence_runs
                SET completed_at=?, status='SUCCESS',
                    confirmed_resolutions=?, new_resolutions=?,
                    opportunities_evaluated=?
                WHERE run_id=?
                ''',
                (now(), len(confirmed), new_count, evaluated, run_id),
            )
            connection.commit()

            total_resolutions = connection.execute(
                "SELECT COUNT(*) FROM market_resolution_history"
            ).fetchone()[0]
            total_results = connection.execute(
                "SELECT COUNT(*) FROM opportunity_resolution_results"
            ).fetchone()[0]
            summary = connection.execute(
                "SELECT * FROM outcome_performance_summary"
            ).fetchone()

            print()
            print("OUTCOME INTELLIGENCE HEALTH SUMMARY")
            print("-" * 112)
            print("Status:                    SUCCESS")
            print(f"Resolution source:         {source['table']}")
            print(f"Source rows inspected:     {len(source_rows):,}")
            print(f"Confirmed resolutions:     {len(confirmed):,}")
            print(f"New resolutions stored:    {new_count:,}")
            print(f"Opportunities evaluated:   {evaluated:,}")
            print(f"Total resolution history:  {total_resolutions:,}")
            print(f"Total evaluated results:   {total_results:,}")
            print(f"Correct predictions:       {int(summary['correct_predictions'] or 0):,}")
            accuracy = summary["accuracy_percent"]
            roi = summary["average_roi_percent"]
            print(f"Accuracy:                  {'N/A' if accuracy is None else str(accuracy) + '%'}")
            print(f"Average realized ROI:      {'N/A' if roi is None else str(roi) + '%'}")
            print("Warnings:                  0")

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("=" * 112)
    print("OUTCOME INTELLIGENCE COMPLETE")
    print("=" * 112)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
