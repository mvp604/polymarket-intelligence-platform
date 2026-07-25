from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.outcome_resolution_schema_v2 import (  # noqa: E402
    DATABASE_PATH,
    ensure_schema,
    object_exists,
    table_columns,
)

REPORT_DIR = PROJECT_ROOT / "reports" / "performance"
ENGINE_VERSION = "2.1.0"


@dataclass(frozen=True)
class ResolutionRecord:
    market_id: str
    outcome: str
    final_result: str
    resolved_value: float | None
    resolution_status: str
    source: str
    resolved_at: str | None
    notes: str | None = None


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize_result(value: str) -> str:
    aliases = {
        "WIN": "WIN", "WON": "WIN", "YES": "WIN",
        "TRUE": "WIN", "1": "WIN",
        "LOSS": "LOSS", "LOST": "LOSS", "NO": "LOSS",
        "FALSE": "LOSS", "0": "LOSS",
        "VOID": "VOID", "PUSH": "VOID",
        "CANCELLED": "VOID", "CANCELED": "VOID",
        "UNRESOLVED": "UNRESOLVED", "PENDING": "UNRESOLVED",
    }
    return aliases.get((value or "").strip().upper(), "UNRESOLVED")


def grade_signal_outcome(
    signal_status: str,
    signal_grade: str,
    final_result: str,
) -> tuple[str, float | None]:
    result = normalize_result(final_result)
    if result == "VOID":
        return "VOID", None
    if result == "UNRESOLVED":
        return "PENDING", None

    actionable = (
        signal_status in {
            "STRONG_ELITE_CONSENSUS",
            "SMART_MONEY_WATCH",
        }
        and signal_grade in {"S+", "S", "A", "B"}
    )
    if not actionable:
        return "NO_ACTION", None
    return ("HIT", 1.0) if result == "WIN" else ("MISS", 0.0)


def resolution_checksum(record: ResolutionRecord) -> str:
    payload = json.dumps(asdict(record), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def upsert_resolution(
    connection: sqlite3.Connection,
    record: ResolutionRecord,
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO market_resolutions (
            market_id, outcome, final_result, resolved_value,
            resolution_status, resolution_source, resolved_at,
            notes, resolution_checksum, engine_version,
            created_at, updated_at
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
            record.resolution_status.upper(),
            record.source,
            record.resolved_at,
            record.notes,
            resolution_checksum(record),
            ENGINE_VERSION,
            now,
            now,
        ),
    )


def settle_signals(connection: sqlite3.Connection) -> int:
    if not object_exists(connection, "table", "smart_money_market_signals"):
        return 0

    rows = connection.execute(
        """
        SELECT
            s.market_id, s.title, s.outcome, s.category,
            s.heat_score, s.signal_grade, s.signal_status,
            s.combined_capital, s.wallet_count,
            s.elite_wallet_count, s.last_observed_at,
            r.final_result, r.resolved_value,
            r.resolution_source, r.resolved_at
        FROM smart_money_market_signals s
        JOIN market_resolutions r
          ON r.market_id=s.market_id
         AND r.outcome=s.outcome
        WHERE UPPER(r.resolution_status)='FINAL'
        """
    ).fetchall()

    now = utc_now()
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
                row["market_id"], row["title"], row["outcome"],
                row["category"], row["heat_score"], row["signal_grade"],
                row["signal_status"], row["combined_capital"],
                row["wallet_count"], row["elite_wallet_count"],
                row["final_result"], row["resolved_value"],
                evaluation, hit_value, row["resolution_source"],
                row["last_observed_at"], row["resolved_at"],
                ENGINE_VERSION, now, now,
            ),
        )
    return len(rows)


def period_bounds(
    report_type: str,
    anchor: date,
) -> tuple[datetime, datetime, str]:
    start = datetime(anchor.year, anchor.month, anchor.day, tzinfo=UTC)
    report_type = report_type.upper()
    if report_type == "DAILY":
        end = start + timedelta(days=1)
        key = anchor.isoformat()
    elif report_type == "WEEKLY":
        start = start - timedelta(days=anchor.weekday())
        end = start + timedelta(days=7)
        key = f"{start.date().isoformat()}_to_{(end - timedelta(days=1)).date().isoformat()}"
    elif report_type == "MONTHLY":
        start = datetime(anchor.year, anchor.month, 1, tzinfo=UTC)
        if anchor.month == 12:
            end = datetime(anchor.year + 1, 1, 1, tzinfo=UTC)
        else:
            end = datetime(anchor.year, anchor.month + 1, 1, tzinfo=UTC)
        key = start.strftime("%Y-%m")
    else:
        raise ValueError("report_type must be DAILY, WEEKLY, or MONTHLY")
    return start, end, key


def fetch_summary(
    connection: sqlite3.Connection,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    params = (
        start.isoformat(timespec="seconds"),
        end.isoformat(timespec="seconds"),
    )
    summary = connection.execute(
        """
        SELECT
            COUNT(*) total_resolved,
            SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) hits,
            SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) misses,
            SUM(CASE WHEN evaluation='VOID' THEN 1 ELSE 0 END) voids,
            SUM(CASE WHEN evaluation='NO_ACTION' THEN 1 ELSE 0 END) no_action,
            AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) hit_rate,
            AVG(heat_score) average_heat,
            MAX(heat_score) maximum_heat,
            SUM(combined_capital) combined_capital
        FROM resolved_signal_results
        WHERE resolved_at >= ? AND resolved_at < ?
        """,
        params,
    ).fetchone()

    def grouped(column: str) -> list[dict[str, Any]]:
        if column not in {"signal_grade", "category", "signal_status"}:
            raise ValueError("unsupported grouping")
        rows = connection.execute(
            f"""
            SELECT
                {column} grouping_value,
                COUNT(*) total,
                SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) hits,
                SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) misses,
                AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) hit_rate,
                AVG(heat_score) average_heat,
                SUM(combined_capital) combined_capital
            FROM resolved_signal_results
            WHERE resolved_at >= ? AND resolved_at < ?
            GROUP BY {column}
            ORDER BY hit_rate DESC, total DESC
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    strongest = connection.execute(
        """
        SELECT title, outcome, category, heat_score, signal_grade,
               signal_status, final_result, evaluation, combined_capital,
               wallet_count, elite_wallet_count, resolved_at
        FROM resolved_signal_results
        WHERE resolved_at >= ? AND resolved_at < ?
        ORDER BY heat_score DESC, combined_capital DESC
        LIMIT 25
        """,
        params,
    ).fetchall()

    misses = connection.execute(
        """
        SELECT title, outcome, category, heat_score, signal_grade,
               signal_status, final_result, combined_capital,
               wallet_count, elite_wallet_count, resolved_at
        FROM resolved_signal_results
        WHERE resolved_at >= ? AND resolved_at < ?
          AND evaluation='MISS'
        ORDER BY heat_score DESC, combined_capital DESC
        LIMIT 25
        """,
        params,
    ).fetchall()

    return {
        "summary": dict(summary),
        "grades": grouped("signal_grade"),
        "categories": grouped("category"),
        "statuses": grouped("signal_status"),
        "strongest": [dict(row) for row in strongest],
        "misses": [dict(row) for row in misses],
    }


def rate(value: Any) -> str:
    return "N/A" if value is None else f"{float(value) * 100:.2f}%"


def build_report(
    report_type: str,
    period_key: str,
    data: dict[str, Any],
) -> str:
    summary = data["summary"]
    lines = [
        f"# Polymarket Intelligence {report_type.title()} Performance Report",
        "",
        f"**Period:** {period_key}",
        "",
        "## Executive Summary",
        "",
        f"- Resolved signals: {int(summary.get('total_resolved') or 0):,}",
        f"- Hits: {int(summary.get('hits') or 0):,}",
        f"- Misses: {int(summary.get('misses') or 0):,}",
        f"- Voids: {int(summary.get('voids') or 0):,}",
        f"- No-action outcomes: {int(summary.get('no_action') or 0):,}",
        f"- Actionable hit rate: {rate(summary.get('hit_rate'))}",
        f"- Average heat score: {float(summary.get('average_heat') or 0):.2f}",
        f"- Maximum heat score: {float(summary.get('maximum_heat') or 0):.2f}",
        f"- Combined tracked capital: ${float(summary.get('combined_capital') or 0):,.2f}",
        "",
    ]

    for title, key in (
        ("Performance by Grade", "grades"),
        ("Performance by Category", "categories"),
        ("Performance by Signal Status", "statuses"),
    ):
        lines.extend([
            f"## {title}", "",
            "| Group | Total | Hits | Misses | Hit Rate | Avg. Heat | Capital |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for row in data[key]:
            lines.append(
                f"| {row.get('grouping_value') or 'Unknown'} "
                f"| {int(row.get('total') or 0)} "
                f"| {int(row.get('hits') or 0)} "
                f"| {int(row.get('misses') or 0)} "
                f"| {rate(row.get('hit_rate'))} "
                f"| {float(row.get('average_heat') or 0):.2f} "
                f"| ${float(row.get('combined_capital') or 0):,.2f} |"
            )
        lines.append("")

    lines.extend(["## Highest-Conviction Resolved Signals", ""])
    for index, row in enumerate(data["strongest"], start=1):
        lines.extend([
            f"### {index}. {row.get('title') or 'Untitled market'}",
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

    lines.extend(["## Highest-Conviction Misses", ""])
    if not data["misses"]:
        lines.append("No actionable misses were recorded for this period.")
    else:
        for index, row in enumerate(data["misses"], start=1):
            lines.extend([
                f"### {index}. {row.get('title') or 'Untitled market'}",
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
        "## Model Review Notes",
        "",
        "- Review the strongest misses before changing scoring thresholds.",
        "- Require meaningful sample sizes before trusting category hit rates.",
        "- Compare daily results with weekly and monthly performance to avoid overreacting.",
        "",
        f"_Generated by Outcome Resolution & Reporting v{ENGINE_VERSION}_",
    ])
    return "\n".join(lines)


def store_report(
    connection: sqlite3.Connection,
    report_type: str,
    period_key: str,
    markdown: str,
    data: dict[str, Any],
) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = (
        f"polymarket_{report_type.lower()}_report_{period_key}.md"
        .replace("/", "-")
    )
    path = REPORT_DIR / filename
    path.write_text(markdown, encoding="utf-8")

    checksum = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    now = utc_now()
    connection.execute(
        """
        INSERT INTO daily_intelligence_reports (
            report_date, report_type, report_checksum,
            summary_json, report_markdown, report_path,
            engine_version, generated_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            period_key, report_type, checksum,
            json.dumps(data, sort_keys=True),
            markdown, str(path), ENGINE_VERSION, now, now,
        ),
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-type",
        choices=("DAILY", "WEEKLY", "MONTHLY"),
        default="DAILY",
    )
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).date().isoformat(),
    )
    args = parser.parse_args()

    anchor = date.fromisoformat(args.date)
    start, end, period_key = period_bounds(args.report_type, anchor)

    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        repairs = ensure_schema(connection)
        settled = settle_signals(connection)
        data = fetch_summary(connection, start, end)
        markdown = build_report(args.report_type, period_key, data)
        path = store_report(
            connection, args.report_type, period_key, markdown, data
        )
        connection.commit()

    print("=" * 100)
    print(f"OUTCOME RESOLUTION & REPORTING v{ENGINE_VERSION}")
    print("=" * 100)
    print(f"Schema repairs applied: {len(repairs):,}")
    print(f"Signals settled:       {settled:,}")
    print(f"Report type:           {args.report_type}")
    print(f"Report period:         {period_key}")
    print(f"Report written to:     {path}")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
