from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
CONFIG_PATH = PROJECT_ROOT / "config" / "outcome_resolution_eod_v1.json"
SQL_PATH = PROJECT_ROOT / "migrations" / "outcome_resolution_eod_v1.sql"
REPORT_DIR = PROJECT_ROOT / "reports" / "daily"
ENGINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class ResolutionRecord:
    market_id: str
    outcome: str
    final_result: str
    resolved_value: float | None
    resolution_status: str
    source: str
    resolved_at: str
    notes: str | None = None


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SQL_PATH.read_text(encoding="utf-8"))


def require_schema(connection: sqlite3.Connection) -> None:
    required = {
        "smart_money_market_signals": {
            "market_id",
            "title",
            "outcome",
            "category",
            "heat_score",
            "signal_grade",
            "signal_status",
            "combined_capital",
            "wallet_count",
            "elite_wallet_count",
            "last_observed_at",
        }
    }
    failures: list[str] = []
    for table_name, columns in required.items():
        actual = table_columns(connection, table_name)
        if not actual:
            failures.append(f"missing table: {table_name}")
            continue
        for column in sorted(columns - actual):
            failures.append(f"missing column: {table_name}.{column}")
    if failures:
        raise RuntimeError("; ".join(failures))


def normalize_result(value: str) -> str:
    text = (value or "").strip().upper()
    aliases = {
        "WIN": "WIN",
        "WON": "WIN",
        "YES": "WIN",
        "TRUE": "WIN",
        "1": "WIN",
        "LOSS": "LOSS",
        "LOST": "LOSS",
        "NO": "LOSS",
        "FALSE": "LOSS",
        "0": "LOSS",
        "VOID": "VOID",
        "PUSH": "VOID",
        "CANCELLED": "VOID",
        "CANCELED": "VOID",
        "UNRESOLVED": "UNRESOLVED",
        "PENDING": "UNRESOLVED",
    }
    return aliases.get(text, text or "UNRESOLVED")


def resolution_checksum(record: ResolutionRecord) -> str:
    payload = json.dumps(record.__dict__, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def upsert_resolution(
    connection: sqlite3.Connection,
    record: ResolutionRecord,
) -> None:
    checksum = resolution_checksum(record)
    connection.execute(
        """
        INSERT INTO market_resolutions (
            market_id, outcome, final_result, resolved_value,
            resolution_status, resolution_source, resolved_at,
            notes, resolution_checksum, engine_version, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(market_id, outcome) DO UPDATE SET
            final_result=excluded.final_result,
            resolved_value=excluded.resolved_value,
            resolution_status=excluded.resolution_status,
            resolution_source=excluded.resolution_source,
            resolved_at=excluded.resolved_at,
            notes=excluded.notes,
            resolution_checksum=excluded.resolution_checksum,
            engine_version=excluded.engine_version,
            updated_at=excluded.updated_at
        """,
        (
            record.market_id,
            record.outcome,
            normalize_result(record.final_result),
            record.resolved_value,
            record.resolution_status,
            record.source,
            record.resolved_at,
            record.notes,
            checksum,
            ENGINE_VERSION,
            utc_now(),
            utc_now(),
        ),
    )


def grade_signal_outcome(
    signal_status: str,
    signal_grade: str,
    final_result: str,
) -> tuple[str, float]:
    result = normalize_result(final_result)
    if result == "VOID":
        return "VOID", 0.0
    if result == "UNRESOLVED":
        return "PENDING", 0.0

    actionable = signal_status in {
        "STRONG_ELITE_CONSENSUS",
        "SMART_MONEY_WATCH",
    } and signal_grade not in {"PASS", "WATCH"}

    if not actionable:
        return "NO_ACTION", 0.0

    if result == "WIN":
        return "HIT", 1.0
    if result == "LOSS":
        return "MISS", 0.0
    return "PENDING", 0.0


def settle_signal_results(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        """
        SELECT
            s.market_id,
            s.title,
            s.outcome,
            s.category,
            s.heat_score,
            s.signal_grade,
            s.signal_status,
            s.combined_capital,
            s.wallet_count,
            s.elite_wallet_count,
            s.last_observed_at,
            r.final_result,
            r.resolved_value,
            r.resolution_status,
            r.resolution_source,
            r.resolved_at
        FROM smart_money_market_signals s
        JOIN market_resolutions r
          ON r.market_id = s.market_id
         AND r.outcome = s.outcome
        WHERE r.resolution_status = 'FINAL'
        """
    ).fetchall()

    settled = 0
    for row in rows:
        evaluation, hit_value = grade_signal_outcome(
            str(row["signal_status"] or ""),
            str(row["signal_grade"] or ""),
            str(row["final_result"] or ""),
        )
        connection.execute(
            """
            INSERT INTO resolved_signal_results (
                market_id, title, outcome, category, heat_score,
                signal_grade, signal_status, combined_capital,
                wallet_count, elite_wallet_count, final_result,
                resolved_value, evaluation, hit_value,
                resolution_source, signal_observed_at, resolved_at,
                engine_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(market_id, outcome) DO UPDATE SET
                title=excluded.title,
                category=excluded.category,
                heat_score=excluded.heat_score,
                signal_grade=excluded.signal_grade,
                signal_status=excluded.signal_status,
                combined_capital=excluded.combined_capital,
                wallet_count=excluded.wallet_count,
                elite_wallet_count=excluded.elite_wallet_count,
                final_result=excluded.final_result,
                resolved_value=excluded.resolved_value,
                evaluation=excluded.evaluation,
                hit_value=excluded.hit_value,
                resolution_source=excluded.resolution_source,
                signal_observed_at=excluded.signal_observed_at,
                resolved_at=excluded.resolved_at,
                engine_version=excluded.engine_version,
                updated_at=excluded.updated_at
            """,
            (
                row["market_id"],
                row["title"],
                row["outcome"],
                row["category"],
                row["heat_score"],
                row["signal_grade"],
                row["signal_status"],
                row["combined_capital"],
                row["wallet_count"],
                row["elite_wallet_count"],
                row["final_result"],
                row["resolved_value"],
                evaluation,
                hit_value,
                row["resolution_source"],
                row["last_observed_at"],
                row["resolved_at"],
                ENGINE_VERSION,
                utc_now(),
                utc_now(),
            ),
        )
        settled += 1
    return settled


def report_day_bounds(report_date: str) -> tuple[str, str]:
    start = datetime.fromisoformat(report_date).replace(tzinfo=UTC)
    end = start + timedelta(days=1)
    return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")


def fetch_daily_summary(
    connection: sqlite3.Connection,
    report_date: str,
) -> dict[str, Any]:
    start, end = report_day_bounds(report_date)

    summary = connection.execute(
        """
        SELECT
            COUNT(*) AS total_resolved,
            SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) AS hits,
            SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) AS misses,
            SUM(CASE WHEN evaluation='VOID' THEN 1 ELSE 0 END) AS voids,
            SUM(CASE WHEN evaluation='NO_ACTION' THEN 1 ELSE 0 END) AS no_action,
            AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) AS hit_rate,
            AVG(heat_score) AS average_heat_score,
            MAX(heat_score) AS maximum_heat_score,
            SUM(combined_capital) AS combined_capital
        FROM resolved_signal_results
        WHERE resolved_at >= ? AND resolved_at < ?
        """,
        (start, end),
    ).fetchone()

    grades = connection.execute(
        """
        SELECT
            signal_grade,
            COUNT(*) AS total,
            SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) AS hits,
            SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) AS misses,
            AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) AS hit_rate,
            AVG(heat_score) AS average_heat
        FROM resolved_signal_results
        WHERE resolved_at >= ? AND resolved_at < ?
        GROUP BY signal_grade
        ORDER BY average_heat DESC
        """,
        (start, end),
    ).fetchall()

    categories = connection.execute(
        """
        SELECT
            category,
            COUNT(*) AS total,
            SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) AS hits,
            SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) AS misses,
            AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) AS hit_rate,
            AVG(heat_score) AS average_heat
        FROM resolved_signal_results
        WHERE resolved_at >= ? AND resolved_at < ?
        GROUP BY category
        ORDER BY hit_rate DESC, total DESC
        """,
        (start, end),
    ).fetchall()

    strongest = connection.execute(
        """
        SELECT
            title, outcome, category, heat_score, signal_grade,
            signal_status, final_result, evaluation, combined_capital,
            wallet_count, elite_wallet_count
        FROM resolved_signal_results
        WHERE resolved_at >= ? AND resolved_at < ?
        ORDER BY heat_score DESC, combined_capital DESC
        LIMIT 20
        """,
        (start, end),
    ).fetchall()

    misses = connection.execute(
        """
        SELECT
            title, outcome, category, heat_score, signal_grade,
            signal_status, final_result, combined_capital,
            wallet_count, elite_wallet_count
        FROM resolved_signal_results
        WHERE resolved_at >= ? AND resolved_at < ?
          AND evaluation='MISS'
        ORDER BY heat_score DESC, combined_capital DESC
        LIMIT 20
        """,
        (start, end),
    ).fetchall()

    return {
        "report_date": report_date,
        "summary": dict(summary) if summary else {},
        "grades": [dict(row) for row in grades],
        "categories": [dict(row) for row in categories],
        "strongest_signals": [dict(row) for row in strongest],
        "highest_conviction_misses": [dict(row) for row in misses],
    }


def safe_rate(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def build_markdown_report(data: dict[str, Any]) -> str:
    summary = data["summary"]
    date = data["report_date"]
    lines: list[str] = [
        f"# Polymarket Intelligence Daily Report — {date}",
        "",
        "## Executive Summary",
        "",
        f"- Resolved signals: {int(summary.get('total_resolved') or 0):,}",
        f"- Hits: {int(summary.get('hits') or 0):,}",
        f"- Misses: {int(summary.get('misses') or 0):,}",
        f"- Voids: {int(summary.get('voids') or 0):,}",
        f"- No-action outcomes: {int(summary.get('no_action') or 0):,}",
        f"- Actionable hit rate: {safe_rate(summary.get('hit_rate'))}",
        f"- Average heat score: {float(summary.get('average_heat_score') or 0):.2f}",
        f"- Maximum heat score: {float(summary.get('maximum_heat_score') or 0):.2f}",
        f"- Combined signal capital: ${float(summary.get('combined_capital') or 0):,.2f}",
        "",
        "## Performance by Signal Grade",
        "",
        "| Grade | Total | Hits | Misses | Hit Rate | Avg. Heat |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for row in data["grades"]:
        lines.append(
            f"| {row.get('signal_grade') or 'Unknown'} "
            f"| {int(row.get('total') or 0)} "
            f"| {int(row.get('hits') or 0)} "
            f"| {int(row.get('misses') or 0)} "
            f"| {safe_rate(row.get('hit_rate'))} "
            f"| {float(row.get('average_heat') or 0):.2f} |"
        )

    lines.extend([
        "",
        "## Performance by Category",
        "",
        "| Category | Total | Hits | Misses | Hit Rate | Avg. Heat |",
        "|---|---:|---:|---:|---:|---:|",
    ])

    for row in data["categories"]:
        lines.append(
            f"| {row.get('category') or 'Other'} "
            f"| {int(row.get('total') or 0)} "
            f"| {int(row.get('hits') or 0)} "
            f"| {int(row.get('misses') or 0)} "
            f"| {safe_rate(row.get('hit_rate'))} "
            f"| {float(row.get('average_heat') or 0):.2f} |"
        )

    lines.extend([
        "",
        "## Highest-Conviction Resolved Signals",
        "",
    ])
    for index, row in enumerate(data["strongest_signals"], start=1):
        lines.extend([
            f"### {index}. {row.get('title')}",
            "",
            f"- Outcome: {row.get('outcome')}",
            f"- Final result: {row.get('final_result')}",
            f"- Evaluation: {row.get('evaluation')}",
            f"- Signal: {row.get('signal_grade')} / {row.get('signal_status')}",
            f"- Heat score: {float(row.get('heat_score') or 0):.2f}",
            f"- Wallets: {int(row.get('wallet_count') or 0)}",
            f"- Elite wallets: {int(row.get('elite_wallet_count') or 0)}",
            f"- Combined capital: ${float(row.get('combined_capital') or 0):,.2f}",
            "",
        ])

    lines.extend([
        "## Highest-Conviction Misses",
        "",
    ])
    if not data["highest_conviction_misses"]:
        lines.append("No actionable misses were recorded for this date.")
    else:
        for index, row in enumerate(data["highest_conviction_misses"], start=1):
            lines.extend([
                f"### {index}. {row.get('title')}",
                "",
                f"- Outcome: {row.get('outcome')}",
                f"- Final result: {row.get('final_result')}",
                f"- Signal: {row.get('signal_grade')} / {row.get('signal_status')}",
                f"- Heat score: {float(row.get('heat_score') or 0):.2f}",
                f"- Wallets: {int(row.get('wallet_count') or 0)}",
                f"- Elite wallets: {int(row.get('elite_wallet_count') or 0)}",
                f"- Combined capital: ${float(row.get('combined_capital') or 0):,.2f}",
                "",
            ])

    lines.extend([
        "## Daily Review",
        "",
        "Use this section to compare strong-consensus performance against actual results, identify category weaknesses, and refine thresholds only after a meaningful sample has accumulated.",
        "",
        f"_Generated by Outcome Resolution & EOD Reporting v{ENGINE_VERSION}_",
    ])
    return "\n".join(lines)


def store_daily_report(
    connection: sqlite3.Connection,
    report_date: str,
    markdown: str,
    data: dict[str, Any],
) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"polymarket_daily_report_{report_date}.md"
    report_path.write_text(markdown, encoding="utf-8")

    checksum = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    connection.execute(
        """
        INSERT INTO daily_intelligence_reports (
            report_date, report_type, report_checksum,
            summary_json, report_markdown, report_path,
            engine_version, generated_at, updated_at
        ) VALUES (?, 'END_OF_DAY', ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_date, report_type) DO UPDATE SET
            report_checksum=excluded.report_checksum,
            summary_json=excluded.summary_json,
            report_markdown=excluded.report_markdown,
            report_path=excluded.report_path,
            engine_version=excluded.engine_version,
            generated_at=excluded.generated_at,
            updated_at=excluded.updated_at
        """,
        (
            report_date,
            checksum,
            json.dumps(data, sort_keys=True),
            markdown,
            str(report_path),
            ENGINE_VERSION,
            utc_now(),
            utc_now(),
        ),
    )
    return report_path


def publish_report_event(
    connection: sqlite3.Connection,
    report_date: str,
    report_path: Path,
    data: dict[str, Any],
) -> None:
    columns = table_columns(connection, "platform_events")
    required = {
        "event_id", "event_type", "source_engine", "source_version",
        "aggregate_type", "aggregate_id", "payload_json", "occurred_at",
        "stored_at", "deduplication_key", "status"
    }
    if not required.issubset(columns):
        return

    event_id = hashlib.sha256(
        f"DailyIntelligenceReportGenerated:{report_date}".encode()
    ).hexdigest()
    payload = json.dumps({
        "report_date": report_date,
        "report_path": str(report_path),
        "summary": data["summary"],
    }, sort_keys=True)
    now = utc_now()
    connection.execute(
        """
        INSERT OR IGNORE INTO platform_events (
            event_id, event_type, source_engine, source_version,
            aggregate_type, aggregate_id, payload_json, occurred_at,
            stored_at, deduplication_key, status, processing_attempts
        ) VALUES (?, 'DailyIntelligenceReportGenerated', ?, ?, 'report', ?, ?, ?, ?, ?, 'PENDING', 0)
        """,
        (
            event_id,
            "outcome_resolution_eod_reporting_v1",
            ENGINE_VERSION,
            report_date,
            payload,
            now,
            now,
            event_id,
        ),
    )


def main() -> int:
    report_date = (
        sys.argv[1]
        if len(sys.argv) > 1
        else datetime.now(UTC).date().isoformat()
    )

    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        require_schema(connection)
        ensure_schema(connection)

        settled = settle_signal_results(connection)
        data = fetch_daily_summary(connection, report_date)
        markdown = build_markdown_report(data)
        report_path = store_daily_report(
            connection, report_date, markdown, data
        )
        publish_report_event(
            connection, report_date, report_path, data
        )
        connection.commit()

        print("=" * 96)
        print(f"OUTCOME RESOLUTION & EOD REPORTING v{ENGINE_VERSION}")
        print("=" * 96)
        print(f"Report date:               {report_date}")
        print(f"Signals settled:           {settled:,}")
        print(f"Resolved signals in report:{int(data['summary'].get('total_resolved') or 0):>10,}")
        print(f"Actionable hit rate:       {safe_rate(data['summary'].get('hit_rate'))}")
        print(f"Report written to:         {report_path}")
        print("=" * 96)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
