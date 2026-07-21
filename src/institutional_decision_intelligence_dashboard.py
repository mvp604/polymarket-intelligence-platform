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
from typing import Any


ENGINE_VERSION = "1.0"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "database" / "polymarket.db"
DEFAULT_REPORT_DIRECTORY = ROOT / "reports" / "decision_intelligence_dashboard"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return clean_text(value).lower() in {"1", "true", "yes", "y"}


def parse_json(value: Any, default: Any) -> Any:
    text = clean_text(value)
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


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def latest_diagnostic_run_id(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        """
        SELECT run_id
        FROM institutional_decision_diagnostic_runs
        WHERE status = 'SUCCESS'
        ORDER BY completed_at DESC, started_at DESC
        LIMIT 1
        """
    ).fetchone()
    return clean_text(row["run_id"]) if row else ""


def load_rows(
    connection: sqlite3.Connection,
    latest_only: bool,
    row_limit: int,
) -> tuple[list[sqlite3.Row], str]:
    run_id = latest_diagnostic_run_id(connection) if latest_only else ""

    where_clause = ""
    params: list[Any] = []

    if run_id:
        where_clause = "WHERE d.run_id = ?"
        params.append(run_id)

    limit_clause = ""
    if row_limit > 0:
        limit_clause = "LIMIT ?"
        params.append(row_limit)

    query = f"""
        SELECT
            d.opportunity_key,
            d.market_id,
            d.title,
            d.outcome,
            d.current_action,
            d.decision_grade,
            d.decision_score,
            d.actionability_score,
            d.confidence,
            d.entry_quality_score,
            d.market_structure_score,
            d.trust_quality_score,
            d.data_quality_score,
            d.wallet_count,
            d.elite_wallet_count,
            d.supporting_wallet_count,
            d.trusted_wallet_count,
            d.hard_veto,
            d.buy_requirements_passed,
            d.buy_requirements_failed,
            d.watch_requirements_passed,
            d.watch_requirements_failed,
            d.buy_gap_score,
            d.watch_gap_score,
            d.nearest_upgrade,
            d.upgrade_difficulty,
            d.primary_blocker,
            d.secondary_blocker,
            d.blocker_category,
            d.failed_buy_requirements_json,
            d.failed_watch_requirements_json,
            d.veto_reasons_json,
            d.positive_reasons_json,
            d.risk_flags_json,
            d.upgrade_actions_json,
            d.diagnostic_summary,
            d.source_calculated_at,
            d.diagnosed_at,
            d.run_id,

            i.market_type,
            i.confidence_grade,
            i.master_quality_score,
            i.consensus_quality_score,
            i.wallet_quality_score,
            i.weighted_trust_score,
            i.trust_confidence,
            i.average_consensus_multiplier,
            i.combined_current_value,
            i.chase_risk_score,
            i.conflict_ratio,
            i.reversal_score,
            i.weakening_score,
            i.edge_remaining_score,
            i.lifecycle_status,
            i.seconds_to_start,
            i.data_completeness_score,
            i.source_coverage_score,
            i.data_confidence,
            i.canonical_match,
            i.is_tradable,
            i.polymarket_url,
            i.liquidity,
            i.volume,
            i.methodology_version,

            m.master_score,
            m.master_grade,
            m.master_tier,
            m.recommendation AS master_recommendation,
            m.opportunity_score,
            m.institutional_score,
            m.evolution_score,
            m.closing_line_score,
            m.price_action_score,
            m.timing_score,
            m.consensus_strength,
            m.strengthening_score,
            m.net_value_change,
            m.clv_score,
            m.steam_score,
            m.volatility_score,
            m.portfolio_independence_score,
            m.remaining_upside,
            m.total_penalty,

            f.fusion_score,
            f.fusion_grade,
            f.confidence_tier,
            f.signal_strength,
            f.recommendation AS fusion_recommendation,
            f.agreeing_wallets,
            f.elite_wallets,
            f.effective_wallets,
            f.mapping_quality_score,
            f.source_count AS fusion_source_count

        FROM institutional_decision_diagnostics AS d
        LEFT JOIN institutional_decisions AS i
            ON i.opportunity_key = d.opportunity_key
        LEFT JOIN master_opportunities AS m
            ON m.opportunity_key = d.opportunity_key
        LEFT JOIN signal_fusion_scores AS f
            ON f.opportunity_key = d.opportunity_key
        {where_clause}
        ORDER BY
            CASE d.nearest_upgrade
                WHEN 'BUY_READY' THEN 0
                WHEN 'NEAR_BUY' THEN 1
                WHEN 'WATCH_READY' THEN 2
                WHEN 'NEAR_WATCH' THEN 3
                WHEN 'VETO_BLOCKED' THEN 5
                ELSE 4
            END,
            d.buy_requirements_failed ASC,
            d.buy_gap_score ASC,
            d.decision_score DESC
        {limit_clause}
    """

    return connection.execute(query, params).fetchall(), run_id


def build_record(row: sqlite3.Row) -> dict[str, Any]:
    failed_buy = parse_json(row["failed_buy_requirements_json"], [])
    failed_watch = parse_json(row["failed_watch_requirements_json"], [])
    veto_reasons = parse_json(row["veto_reasons_json"], [])
    positive_reasons = parse_json(row["positive_reasons_json"], [])
    risk_flags = parse_json(row["risk_flags_json"], [])
    upgrade_actions = parse_json(row["upgrade_actions_json"], [])

    return {
        key: row[key]
        for key in row.keys()
    } | {
        "hard_veto": safe_bool(row["hard_veto"]),
        "buy_requirements_passed": safe_int(row["buy_requirements_passed"]),
        "buy_requirements_failed": safe_int(row["buy_requirements_failed"]),
        "watch_requirements_passed": safe_int(row["watch_requirements_passed"]),
        "watch_requirements_failed": safe_int(row["watch_requirements_failed"]),
        "failed_buy_requirements": failed_buy,
        "failed_watch_requirements": failed_watch,
        "veto_reasons": veto_reasons,
        "positive_reasons": positive_reasons,
        "risk_flags": risk_flags,
        "upgrade_actions": upgrade_actions,
        "buy_ready": clean_text(row["nearest_upgrade"]).upper() == "BUY_READY",
        "near_buy": clean_text(row["nearest_upgrade"]).upper() == "NEAR_BUY",
        "watch_ready": clean_text(row["nearest_upgrade"]).upper() == "WATCH_READY",
        "veto_blocked": clean_text(row["nearest_upgrade"]).upper() == "VETO_BLOCKED",
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    primary = Counter()
    secondary = Counter()
    categories = Counter()
    actions = Counter()
    upgrades = Counter()
    profiles = Counter()
    failed_requirements = Counter()
    veto_reasons = Counter()
    risk_flags = Counter()

    for record in records:
        primary_blocker = clean_text(record.get("primary_blocker"))
        secondary_blocker = clean_text(record.get("secondary_blocker"))
        blocker_category = clean_text(record.get("blocker_category"))
        action = clean_text(record.get("current_action")).upper() or "UNKNOWN"
        upgrade = clean_text(record.get("nearest_upgrade")).upper() or "UNKNOWN"
        market_type = clean_text(record.get("market_type")).upper() or "UNKNOWN"

        if primary_blocker:
            primary[primary_blocker] += 1
        if secondary_blocker:
            secondary[secondary_blocker] += 1
        if blocker_category:
            categories[blocker_category] += 1

        actions[action] += 1
        upgrades[upgrade] += 1
        profiles[market_type] += 1

        for item in record.get("failed_buy_requirements", []):
            if isinstance(item, dict):
                name = (
                    clean_text(item.get("requirement"))
                    or clean_text(item.get("field"))
                    or clean_text(item.get("name"))
                )
            else:
                name = clean_text(item)
            if name:
                failed_requirements[name] += 1

        for item in record.get("veto_reasons", []):
            veto_reasons[clean_text(item)] += 1

        for item in record.get("risk_flags", []):
            risk_flags[clean_text(item)] += 1

    return {
        "generated_at": utc_now().isoformat(timespec="seconds"),
        "records_analyzed": len(records),
        "buy_ready_count": sum(bool(r["buy_ready"]) for r in records),
        "near_buy_count": sum(bool(r["near_buy"]) for r in records),
        "watch_ready_count": sum(bool(r["watch_ready"]) for r in records),
        "veto_blocked_count": sum(bool(r["veto_blocked"]) for r in records),
        "primary_blockers": dict(primary.most_common()),
        "secondary_blockers": dict(secondary.most_common()),
        "blocker_categories": dict(categories.most_common()),
        "current_actions": dict(actions.most_common()),
        "nearest_upgrades": dict(upgrades.most_common()),
        "market_types": dict(profiles.most_common()),
        "failed_buy_requirements": dict(failed_requirements.most_common()),
        "veto_reasons": dict(veto_reasons.most_common()),
        "risk_flags": dict(risk_flags.most_common()),
    }


def flat_record(record: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
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

    flattened = [flat_record(record) for record in records]
    fields = sorted({key for row in flattened for key in row})

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(flattened)


def fmt(value: Any, decimals: int = 1) -> str:
    number = safe_float(value)
    return "—" if number is None else f"{number:.{decimals}f}"


def write_text(
    path: Path,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
    metadata: dict[str, Any],
    top_limit: int,
) -> None:
    lines = [
        "=" * 120,
        "INSTITUTIONAL DECISION INTELLIGENCE DASHBOARD",
        "=" * 120,
        f"Engine version:       {ENGINE_VERSION}",
        f"Generated at:         {summary['generated_at']}",
        f"Diagnostic run ID:    {metadata['diagnostic_run_id'] or 'ALL RUNS'}",
        f"Records analyzed:     {summary['records_analyzed']}",
        f"BUY ready:            {summary['buy_ready_count']}",
        f"Near BUY:             {summary['near_buy_count']}",
        f"WATCH ready:          {summary['watch_ready_count']}",
        f"Veto blocked:         {summary['veto_blocked_count']}",
        "",
        "PRIMARY BLOCKERS",
        "-" * 120,
    ]

    if summary["primary_blockers"]:
        for name, count in summary["primary_blockers"].items():
            lines.append(f"{name:<50} {count:>8}")
    else:
        lines.append("No primary blockers found.")

    lines += ["", "FAILED BUY REQUIREMENTS", "-" * 120]
    if summary["failed_buy_requirements"]:
        for name, count in summary["failed_buy_requirements"].items():
            lines.append(f"{name:<50} {count:>8}")
    else:
        lines.append("No parsed failed BUY requirements found.")

    prioritized = sorted(
        records,
        key=lambda r: (
            0 if r["buy_ready"] else 1 if r["near_buy"] else 2,
            safe_int(r.get("buy_requirements_failed")),
            safe_float(r.get("buy_gap_score")) if safe_float(r.get("buy_gap_score")) is not None else 9999,
            -(safe_float(r.get("decision_score")) or 0),
        ),
    )

    lines += ["", "TOP DECISION OPPORTUNITIES", "-" * 120]

    for index, record in enumerate(prioritized[:top_limit], start=1):
        title = clean_text(record.get("title")) or clean_text(record.get("market_id"))
        lines += [
            f"[{index}] {title}",
            f"    Outcome:              {clean_text(record.get('outcome'))}",
            f"    Current action:       {clean_text(record.get('current_action'))}",
            f"    Nearest upgrade:      {clean_text(record.get('nearest_upgrade'))}",
            f"    Upgrade difficulty:   {clean_text(record.get('upgrade_difficulty'))}",
            f"    Decision score:       {fmt(record.get('decision_score'))}",
            f"    Confidence:           {fmt(record.get('confidence'))}",
            f"    Actionability:        {fmt(record.get('actionability_score'))}",
            f"    Entry quality:        {fmt(record.get('entry_quality_score'))}",
            f"    Structure:            {fmt(record.get('market_structure_score'))}",
            f"    Trust:                {fmt(record.get('trust_quality_score'))}",
            f"    Data quality:         {fmt(record.get('data_quality_score'))}",
            f"    Wallets:              {safe_int(record.get('wallet_count'))}",
            f"    BUY failed:           {safe_int(record.get('buy_requirements_failed'))}",
            f"    BUY gap:              {fmt(record.get('buy_gap_score'), 2)}",
            f"    Primary blocker:      {clean_text(record.get('primary_blocker'))}",
            f"    Secondary blocker:    {clean_text(record.get('secondary_blocker'))}",
            f"    Hard veto:            {bool(record.get('hard_veto'))}",
            f"    Summary:              {clean_text(record.get('diagnostic_summary'))}",
            f"    URL:                  {clean_text(record.get('polymarket_url'))}",
            "",
        ]

    lines += [
        "=" * 120,
        "Database modified: NO",
        "Decision logic modified: NO",
        "Thresholds modified: NO",
        "Reports saved: YES",
        "=" * 120,
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def html_list(items: Any) -> str:
    if not items:
        return "<span class='muted'>None</span>"
    if not isinstance(items, list):
        items = [items]
    rendered = "".join(f"<li>{html.escape(clean_text(item))}</li>" for item in items)
    return f"<ul>{rendered}</ul>"


def write_html(
    path: Path,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    cards = []
    for record in records:
        title = html.escape(clean_text(record.get("title")) or "<untitled>")
        outcome = html.escape(clean_text(record.get("outcome")))
        action = html.escape(clean_text(record.get("current_action")))
        upgrade = html.escape(clean_text(record.get("nearest_upgrade")))
        blocker = html.escape(clean_text(record.get("primary_blocker")))
        url = clean_text(record.get("polymarket_url"))
        link = f"<a href='{html.escape(url)}' target='_blank'>Open market</a>" if url else ""

        cards.append(
            f"""
            <section class="card">
              <div class="card-head">
                <div>
                  <h2>{title}</h2>
                  <div class="muted">{outcome}</div>
                </div>
                <div class="badge">{action}</div>
              </div>

              <div class="grid">
                <div><span>Nearest upgrade</span><strong>{upgrade}</strong></div>
                <div><span>Decision score</span><strong>{fmt(record.get('decision_score'))}</strong></div>
                <div><span>Confidence</span><strong>{fmt(record.get('confidence'))}</strong></div>
                <div><span>BUY gap</span><strong>{fmt(record.get('buy_gap_score'), 2)}</strong></div>
                <div><span>Failed BUY rules</span><strong>{safe_int(record.get('buy_requirements_failed'))}</strong></div>
                <div><span>Wallets</span><strong>{safe_int(record.get('wallet_count'))}</strong></div>
              </div>

              <p><b>Primary blocker:</b> {blocker or 'None'}</p>
              <p><b>Secondary blocker:</b> {html.escape(clean_text(record.get('secondary_blocker'))) or 'None'}</p>
              <p><b>Diagnostic:</b> {html.escape(clean_text(record.get('diagnostic_summary')))}</p>

              <details>
                <summary>Failed BUY requirements</summary>
                {html_list(record.get('failed_buy_requirements'))}
              </details>

              <details>
                <summary>Upgrade actions</summary>
                {html_list(record.get('upgrade_actions'))}
              </details>

              <details>
                <summary>Risk flags</summary>
                {html_list(record.get('risk_flags'))}
              </details>

              <div class="link">{link}</div>
            </section>
            """
        )

    blocker_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{count}</td></tr>"
        for name, count in summary["primary_blockers"].items()
    ) or "<tr><td colspan='2'>No blockers</td></tr>"

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Institutional Decision Intelligence Dashboard</title>
<style>
body {{
  font-family: Arial, sans-serif;
  margin: 0;
  background: #f4f6f8;
  color: #1d2430;
}}
header {{
  background: #111827;
  color: white;
  padding: 28px;
}}
main {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}}
.summary {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}}
.metric, .card {{
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0,0,0,.06);
}}
.metric {{
  padding: 18px;
}}
.metric strong {{
  font-size: 28px;
  display: block;
}}
.card {{
  padding: 20px;
  margin-bottom: 16px;
}}
.card-head {{
  display: flex;
  justify-content: space-between;
  gap: 16px;
}}
.card h2 {{
  margin: 0 0 4px;
}}
.badge {{
  background: #e5e7eb;
  border-radius: 999px;
  padding: 8px 12px;
  height: fit-content;
  font-weight: bold;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
  gap: 10px;
  margin: 16px 0;
}}
.grid div {{
  background: #f8fafc;
  padding: 10px;
  border-radius: 8px;
}}
.grid span {{
  display: block;
  color: #64748b;
  font-size: 12px;
}}
.grid strong {{
  font-size: 18px;
}}
.muted {{
  color: #64748b;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  background: white;
  margin-bottom: 24px;
}}
th, td {{
  text-align: left;
  padding: 10px;
  border-bottom: 1px solid #e5e7eb;
}}
details {{
  margin: 10px 0;
}}
.link {{
  margin-top: 12px;
}}
a {{
  color: #2563eb;
}}
</style>
</head>
<body>
<header>
  <h1>Institutional Decision Intelligence Dashboard</h1>
  <div>Run ID: {html.escape(metadata['diagnostic_run_id'] or 'ALL RUNS')}</div>
  <div>Generated: {html.escape(summary['generated_at'])}</div>
</header>
<main>
  <section class="summary">
    <div class="metric"><span>Analyzed</span><strong>{summary['records_analyzed']}</strong></div>
    <div class="metric"><span>BUY ready</span><strong>{summary['buy_ready_count']}</strong></div>
    <div class="metric"><span>Near BUY</span><strong>{summary['near_buy_count']}</strong></div>
    <div class="metric"><span>WATCH ready</span><strong>{summary['watch_ready_count']}</strong></div>
    <div class="metric"><span>Veto blocked</span><strong>{summary['veto_blocked_count']}</strong></div>
  </section>

  <h2>Primary blockers</h2>
  <table>
    <thead><tr><th>Blocker</th><th>Count</th></tr></thead>
    <tbody>{blocker_rows}</tbody>
  </table>

  <h2>Ranked opportunities</h2>
  {''.join(cards)}
</main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


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
    parser.add_argument("--top-limit", type=int, default=25)
    args = parser.parse_args()

    database_path = Path(args.database).resolve()
    report_directory = Path(args.report_directory).resolve()

    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    report_directory.mkdir(parents=True, exist_ok=True)

    connection = connect(database_path)
    try:
        required_tables = (
            "institutional_decision_diagnostics",
            "institutional_decision_diagnostic_runs",
            "institutional_decisions",
            "master_opportunities",
            "signal_fusion_scores",
        )

        missing = [name for name in required_tables if not table_exists(connection, name)]
        if missing:
            raise RuntimeError("Missing required database tables: " + ", ".join(missing))

        rows, diagnostic_run_id = load_rows(
            connection,
            latest_only=bool(args.latest_run_only),
            row_limit=max(0, args.row_limit),
        )
    finally:
        connection.close()

    records = [build_record(row) for row in rows]
    summary = summarize(records)

    metadata = {
        "engine_version": ENGINE_VERSION,
        "database_path": str(database_path),
        "diagnostic_run_id": diagnostic_run_id,
        "latest_run_only": bool(args.latest_run_only),
        "records_loaded": len(records),
    }

    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    stem = f"institutional_decision_intelligence_dashboard_{timestamp}"

    csv_path = report_directory / f"{stem}.csv"
    json_path = report_directory / f"{stem}.json"
    text_path = report_directory / f"{stem}.txt"
    html_path = report_directory / f"{stem}.html"

    write_csv(csv_path, records)
    json_path.write_text(
        json.dumps(
            {"metadata": metadata, "summary": summary, "records": records},
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    write_text(text_path, summary, records, metadata, max(0, args.top_limit))
    write_html(html_path, summary, records, metadata)

    latest_files = {
        "latest.csv": csv_path,
        "latest.json": json_path,
        "latest.txt": text_path,
        "latest.html": html_path,
    }

    for filename, source in latest_files.items():
        (report_directory / filename).write_bytes(source.read_bytes())

    print()
    print("=" * 120)
    print("INSTITUTIONAL DECISION INTELLIGENCE DASHBOARD")
    print("=" * 120)
    print(f"Diagnostic run ID:       {diagnostic_run_id or 'ALL RUNS'}")
    print(f"Records analyzed:        {summary['records_analyzed']}")
    print(f"BUY ready:               {summary['buy_ready_count']}")
    print(f"Near BUY:                {summary['near_buy_count']}")
    print(f"WATCH ready:             {summary['watch_ready_count']}")
    print(f"Veto blocked:            {summary['veto_blocked_count']}")
    print()
    print("TOP PRIMARY BLOCKERS")
    print("-" * 120)

    if summary["primary_blockers"]:
        for name, count in list(summary["primary_blockers"].items())[:10]:
            print(f"{name:<50} {count:>8}")
    else:
        print("No primary blockers found.")

    print()
    print("SAVED REPORTS")
    print("-" * 120)
    print(f"HTML:   {html_path}")
    print(f"CSV:    {csv_path}")
    print(f"JSON:   {json_path}")
    print(f"TEXT:   {text_path}")
    print(f"LATEST: {report_directory / 'latest.html'}")
    print()
    print("Database modified:       NO")
    print("Decision logic modified: NO")
    print("Thresholds modified:     NO")
    print("=" * 120)


if __name__ == "__main__":
    main()