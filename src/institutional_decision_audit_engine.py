from __future__ import annotations

import argparse
import csv
import html
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


ENGINE_VERSION = "1.0"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "database" / "polymarket.db"
DEFAULT_REPORT_DIRECTORY = ROOT / "reports" / "decision_audit"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return clean(value).lower() in {"1", "true", "yes", "y"}


def parse_json(value: Any, default: Any) -> Any:
    text = clean(value)
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (name,),
    ).fetchone() is not None


def columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        clean(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def latest_run_id(connection: sqlite3.Connection) -> str:
    if not table_exists(connection, "institutional_decision_diagnostic_runs"):
        return ""

    run_columns = columns(connection, "institutional_decision_diagnostic_runs")
    if "run_id" not in run_columns:
        return ""

    order_parts = []
    for candidate in ("completed_at", "started_at", "created_at"):
        if candidate in run_columns:
            order_parts.append(f'"{candidate}" DESC')

    where = ""
    if "status" in run_columns:
        where = "WHERE UPPER(COALESCE(status, '')) = 'SUCCESS'"

    order = ", ".join(order_parts) if order_parts else "rowid DESC"

    row = connection.execute(
        f"""
        SELECT run_id
        FROM institutional_decision_diagnostic_runs
        {where}
        ORDER BY {order}
        LIMIT 1
        """
    ).fetchone()

    return clean(row["run_id"]) if row else ""


def load_diagnostics(
    connection: sqlite3.Connection,
    latest_only: bool,
    row_limit: int,
) -> tuple[list[dict[str, Any]], str]:
    table = "institutional_decision_diagnostics"

    if not table_exists(connection, table):
        raise RuntimeError(f"Required table not found: {table}")

    available = columns(connection, table)
    run_id = latest_run_id(connection) if latest_only else ""

    where = ""
    params: list[Any] = []

    if run_id and "run_id" in available:
        where = 'WHERE "run_id" = ?'
        params.append(run_id)

    order_candidates = [
        candidate
        for candidate in (
            "buy_requirements_failed",
            "buy_gap_score",
            "decision_score",
        )
        if candidate in available
    ]

    order_clauses = []
    for candidate in order_candidates:
        direction = "DESC" if candidate == "decision_score" else "ASC"
        order_clauses.append(f'"{candidate}" {direction}')

    order = ", ".join(order_clauses) if order_clauses else "rowid DESC"

    limit = ""
    if row_limit > 0:
        limit = "LIMIT ?"
        params.append(row_limit)

    rows = connection.execute(
        f"""
        SELECT *
        FROM "{table}"
        {where}
        ORDER BY {order}
        {limit}
        """,
        params,
    ).fetchall()

    return [dict(row) for row in rows], run_id


def normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    failed_buy = parse_json(row.get("failed_buy_requirements_json"), [])
    failed_watch = parse_json(row.get("failed_watch_requirements_json"), [])
    veto_reasons = parse_json(row.get("veto_reasons_json"), [])
    positive_reasons = parse_json(row.get("positive_reasons_json"), [])
    risk_flags = parse_json(row.get("risk_flags_json"), [])
    upgrade_actions = parse_json(row.get("upgrade_actions_json"), [])

    record = dict(row)
    record.update(
        {
            "hard_veto": truthy(row.get("hard_veto")),
            "buy_requirements_failed": integer(row.get("buy_requirements_failed")),
            "buy_requirements_passed": integer(row.get("buy_requirements_passed")),
            "watch_requirements_failed": integer(row.get("watch_requirements_failed")),
            "watch_requirements_passed": integer(row.get("watch_requirements_passed")),
            "wallet_count": integer(row.get("wallet_count")),
            "failed_buy_requirements": failed_buy,
            "failed_watch_requirements": failed_watch,
            "veto_reasons": veto_reasons,
            "positive_reasons": positive_reasons,
            "risk_flags": risk_flags,
            "upgrade_actions": upgrade_actions,
        }
    )
    return record


def requirement_name(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("requirement", "field", "name", "rule", "metric"):
            value = clean(item.get(key))
            if value:
                return value
        return json.dumps(item, ensure_ascii=False, sort_keys=True)
    return clean(item)


def build_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    primary = Counter()
    secondary = Counter()
    categories = Counter()
    actions = Counter()
    upgrades = Counter()
    failed_buy = Counter()
    failed_watch = Counter()
    vetoes = Counter()
    risks = Counter()

    score_fields = (
        "decision_score",
        "actionability_score",
        "confidence",
        "entry_quality_score",
        "market_structure_score",
        "trust_quality_score",
        "data_quality_score",
        "buy_gap_score",
        "watch_gap_score",
    )

    score_values: dict[str, list[float]] = {field: [] for field in score_fields}

    for record in records:
        primary_blocker = clean(record.get("primary_blocker"))
        secondary_blocker = clean(record.get("secondary_blocker"))
        category = clean(record.get("blocker_category"))
        action = clean(record.get("current_action")).upper() or "UNKNOWN"
        upgrade = clean(record.get("nearest_upgrade")).upper() or "UNKNOWN"

        if primary_blocker:
            primary[primary_blocker] += 1
        if secondary_blocker:
            secondary[secondary_blocker] += 1
        if category:
            categories[category] += 1

        actions[action] += 1
        upgrades[upgrade] += 1

        for item in record.get("failed_buy_requirements", []):
            name = requirement_name(item)
            if name:
                failed_buy[name] += 1

        for item in record.get("failed_watch_requirements", []):
            name = requirement_name(item)
            if name:
                failed_watch[name] += 1

        for item in record.get("veto_reasons", []):
            name = requirement_name(item)
            if name:
                vetoes[name] += 1

        for item in record.get("risk_flags", []):
            name = requirement_name(item)
            if name:
                risks[name] += 1

        for field in score_fields:
            value = number(record.get(field))
            if value is not None:
                score_values[field].append(value)

    score_statistics = {}
    for field, values in score_values.items():
        if values:
            score_statistics[field] = {
                "count": len(values),
                "minimum": min(values),
                "average": mean(values),
                "maximum": max(values),
            }

    closest = sorted(
        records,
        key=lambda record: (
            1 if record.get("hard_veto") else 0,
            integer(record.get("buy_requirements_failed")),
            number(record.get("buy_gap_score"))
            if number(record.get("buy_gap_score")) is not None
            else 999999,
            -(number(record.get("decision_score")) or 0),
        ),
    )

    veto_free = [record for record in closest if not record.get("hard_veto")]
    blocked = [record for record in closest if record.get("hard_veto")]

    return {
        "generated_at": utc_now().isoformat(timespec="seconds"),
        "records_analyzed": len(records),
        "hard_veto_count": len(blocked),
        "veto_free_count": len(veto_free),
        "primary_blockers": dict(primary.most_common()),
        "secondary_blockers": dict(secondary.most_common()),
        "blocker_categories": dict(categories.most_common()),
        "current_actions": dict(actions.most_common()),
        "nearest_upgrades": dict(upgrades.most_common()),
        "failed_buy_requirements": dict(failed_buy.most_common()),
        "failed_watch_requirements": dict(failed_watch.most_common()),
        "veto_reasons": dict(vetoes.most_common()),
        "risk_flags": dict(risks.most_common()),
        "score_statistics": score_statistics,
        "closest_veto_free": veto_free[:25],
        "closest_overall": closest[:25],
    }


def flatten(record: dict[str, Any]) -> dict[str, Any]:
    output = {}
    for key, value in record.items():
        if isinstance(value, (list, dict)):
            output[key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            output[key] = int(value)
        else:
            output[key] = value
    return output


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        path.write_text("", encoding="utf-8-sig")
        return

    rows = [flatten(record) for record in records]
    fields = sorted({field for row in rows for field in row})

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def format_number(value: Any, decimals: int = 2) -> str:
    parsed = number(value)
    return "â€”" if parsed is None else f"{parsed:.{decimals}f}"


def write_text(
    path: Path,
    audit: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    lines = [
        "=" * 120,
        "INSTITUTIONAL DECISION AUDIT ENGINE",
        "=" * 120,
        f"Version:              {ENGINE_VERSION}",
        f"Generated:            {audit['generated_at']}",
        f"Diagnostic run ID:    {metadata['diagnostic_run_id'] or 'ALL RUNS'}",
        f"Records analyzed:     {audit['records_analyzed']}",
        f"Hard veto:            {audit['hard_veto_count']}",
        f"Veto free:            {audit['veto_free_count']}",
        "",
        "PRIMARY BLOCKERS",
        "-" * 120,
    ]

    for name, count in audit["primary_blockers"].items():
        lines.append(f"{name:<60}{count:>8}")

    lines.extend(["", "FAILED BUY REQUIREMENTS", "-" * 120])
    for name, count in audit["failed_buy_requirements"].items():
        lines.append(f"{name:<60}{count:>8}")

    lines.extend(["", "VETO REASONS", "-" * 120])
    if audit["veto_reasons"]:
        for name, count in audit["veto_reasons"].items():
            lines.append(f"{name:<60}{count:>8}")
    else:
        lines.append("No parsed veto reasons.")

    lines.extend(["", "SCORE STATISTICS", "-" * 120])
    for field, stats in audit["score_statistics"].items():
        lines.append(
            f"{field:<30}"
            f"min={stats['minimum']:.2f}  "
            f"avg={stats['average']:.2f}  "
            f"max={stats['maximum']:.2f}  "
            f"n={stats['count']}"
        )

    lines.extend(["", "CLOSEST VETO-FREE OPPORTUNITIES", "-" * 120])

    if not audit["closest_veto_free"]:
        lines.append("No veto-free opportunities found.")

    for index, record in enumerate(audit["closest_veto_free"], start=1):
        lines.extend(
            [
                f"[{index}] {clean(record.get('title')) or clean(record.get('market_id'))}",
                f"    Outcome:            {clean(record.get('outcome'))}",
                f"    Action:             {clean(record.get('current_action'))}",
                f"    Nearest upgrade:    {clean(record.get('nearest_upgrade'))}",
                f"    Decision score:     {format_number(record.get('decision_score'))}",
                f"    Confidence:         {format_number(record.get('confidence'))}",
                f"    Failed BUY rules:   {integer(record.get('buy_requirements_failed'))}",
                f"    BUY gap:            {format_number(record.get('buy_gap_score'))}",
                f"    Primary blocker:    {clean(record.get('primary_blocker'))}",
                f"    Upgrade actions:    {json.dumps(record.get('upgrade_actions', []), ensure_ascii=False)}",
                "",
            ]
        )

    lines.extend(
        [
            "=" * 120,
            "Database modified: NO",
            "Thresholds modified: NO",
            "Decision methodology modified: NO",
            "=" * 120,
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def html_table(mapping: dict[str, int], empty: str = "None") -> str:
    if not mapping:
        return f"<tr><td colspan='2'>{html.escape(empty)}</td></tr>"
    return "".join(
        f"<tr><td>{html.escape(name)}</td><td>{count}</td></tr>"
        for name, count in mapping.items()
    )


def write_html(
    path: Path,
    audit: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    opportunity_cards = []

    for record in audit["closest_veto_free"]:
        opportunity_cards.append(
            f"""
            <section class="card">
              <h3>{html.escape(clean(record.get('title')) or clean(record.get('market_id')))}</h3>
              <p class="muted">{html.escape(clean(record.get('outcome')))}</p>
              <div class="grid">
                <div><span>Action</span><strong>{html.escape(clean(record.get('current_action')))}</strong></div>
                <div><span>Nearest upgrade</span><strong>{html.escape(clean(record.get('nearest_upgrade')))}</strong></div>
                <div><span>Decision score</span><strong>{format_number(record.get('decision_score'))}</strong></div>
                <div><span>Confidence</span><strong>{format_number(record.get('confidence'))}</strong></div>
                <div><span>BUY failures</span><strong>{integer(record.get('buy_requirements_failed'))}</strong></div>
                <div><span>BUY gap</span><strong>{format_number(record.get('buy_gap_score'))}</strong></div>
              </div>
              <p><b>Primary blocker:</b> {html.escape(clean(record.get('primary_blocker')) or 'None')}</p>
              <p><b>Secondary blocker:</b> {html.escape(clean(record.get('secondary_blocker')) or 'None')}</p>
              <p><b>Suggested upgrades:</b> {html.escape(json.dumps(record.get('upgrade_actions', []), ensure_ascii=False))}</p>
            </section>
            """
        )

    score_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(field)}</td>
          <td>{stats['minimum']:.2f}</td>
          <td>{stats['average']:.2f}</td>
          <td>{stats['maximum']:.2f}</td>
          <td>{stats['count']}</td>
        </tr>
        """
        for field, stats in audit["score_statistics"].items()
    )

    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Institutional Decision Audit</title>
<style>
body {{ margin:0; font-family:Arial,sans-serif; background:#f4f6f8; color:#172033; }}
header {{ background:#111827; color:white; padding:28px; }}
main {{ max-width:1200px; margin:auto; padding:24px; }}
.metrics, .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }}
.metric, .card, table {{ background:white; border-radius:12px; box-shadow:0 2px 10px rgba(0,0,0,.06); }}
.metric {{ padding:18px; }}
.metric strong {{ display:block; font-size:28px; }}
.card {{ padding:20px; margin:16px 0; }}
.grid div {{ background:#f8fafc; border-radius:8px; padding:10px; }}
.grid span {{ display:block; font-size:12px; color:#64748b; }}
table {{ width:100%; border-collapse:collapse; margin:16px 0 28px; overflow:hidden; }}
th, td {{ text-align:left; padding:10px; border-bottom:1px solid #e5e7eb; }}
.muted {{ color:#64748b; }}
</style>
</head>
<body>
<header>
  <h1>Institutional Decision Audit Engine</h1>
  <div>Run ID: {html.escape(metadata['diagnostic_run_id'] or 'ALL RUNS')}</div>
  <div>Generated: {html.escape(audit['generated_at'])}</div>
</header>
<main>
  <section class="metrics">
    <div class="metric"><span>Analyzed</span><strong>{audit['records_analyzed']}</strong></div>
    <div class="metric"><span>Hard veto</span><strong>{audit['hard_veto_count']}</strong></div>
    <div class="metric"><span>Veto free</span><strong>{audit['veto_free_count']}</strong></div>
  </section>

  <h2>Primary blockers</h2>
  <table><thead><tr><th>Blocker</th><th>Count</th></tr></thead>
  <tbody>{html_table(audit['primary_blockers'])}</tbody></table>

  <h2>Failed BUY requirements</h2>
  <table><thead><tr><th>Requirement</th><th>Count</th></tr></thead>
  <tbody>{html_table(audit['failed_buy_requirements'])}</tbody></table>

  <h2>Veto reasons</h2>
  <table><thead><tr><th>Reason</th><th>Count</th></tr></thead>
  <tbody>{html_table(audit['veto_reasons'], 'No parsed veto reasons')}</tbody></table>

  <h2>Score statistics</h2>
  <table>
    <thead><tr><th>Metric</th><th>Minimum</th><th>Average</th><th>Maximum</th><th>Count</th></tr></thead>
    <tbody>{score_rows}</tbody>
  </table>

  <h2>Closest veto-free opportunities</h2>
  {''.join(opportunity_cards) or '<p>No veto-free opportunities found.</p>'}
</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--report-directory", default=str(DEFAULT_REPORT_DIRECTORY))
    parser.add_argument(
        "--latest-run-only",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--row-limit", type=int, default=0)
    args = parser.parse_args()

    database_path = Path(args.database).resolve()
    report_directory = Path(args.report_directory).resolve()

    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    report_directory.mkdir(parents=True, exist_ok=True)

    connection = connect(database_path)
    try:
        raw_records, run_id = load_diagnostics(
            connection,
            latest_only=bool(args.latest_run_only),
            row_limit=max(0, args.row_limit),
        )
    finally:
        connection.close()

    records = [normalize_record(row) for row in raw_records]
    audit = build_audit(records)

    metadata = {
        "engine_version": ENGINE_VERSION,
        "database_path": str(database_path),
        "diagnostic_run_id": run_id,
        "latest_run_only": bool(args.latest_run_only),
    }

    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    stem = f"institutional_decision_audit_{timestamp}"

    html_path = report_directory / f"{stem}.html"
    text_path = report_directory / f"{stem}.txt"
    json_path = report_directory / f"{stem}.json"
    csv_path = report_directory / f"{stem}.csv"

    write_html(html_path, audit, metadata)
    write_text(text_path, audit, metadata)
    write_csv(csv_path, records)
    json_path.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "audit": audit,
                "records": records,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    for latest_name, source in (
        ("latest.html", html_path),
        ("latest.txt", text_path),
        ("latest.json", json_path),
        ("latest.csv", csv_path),
    ):
        (report_directory / latest_name).write_bytes(source.read_bytes())

    print()
    print("=" * 120)
    print("INSTITUTIONAL DECISION AUDIT ENGINE")
    print("=" * 120)
    print(f"Diagnostic run ID:       {run_id or 'ALL RUNS'}")
    print(f"Records analyzed:        {audit['records_analyzed']}")
    print(f"Hard veto:               {audit['hard_veto_count']}")
    print(f"Veto free:               {audit['veto_free_count']}")
    print()
    print("TOP PRIMARY BLOCKERS")
    print("-" * 120)

    if audit["primary_blockers"]:
        for name, count in list(audit["primary_blockers"].items())[:10]:
            print(f"{name:<60}{count:>8}")
    else:
        print("No primary blockers found.")

    print()
    print("SAVED REPORTS")
    print("-" * 120)
    print(f"HTML:   {html_path}")
    print(f"TEXT:   {text_path}")
    print(f"JSON:   {json_path}")
    print(f"CSV:    {csv_path}")
    print(f"LATEST: {report_directory / 'latest.html'}")
    print()
    print("Database modified:       NO")
    print("Thresholds modified:     NO")
    print("Methodology modified:    NO")
    print("=" * 120)


if __name__ == "__main__":
    main()

