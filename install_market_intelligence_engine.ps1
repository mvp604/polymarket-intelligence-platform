$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$srcDir = Join-Path $root "src"
$reportDir = Join-Path $root "reports\market_intelligence"

New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$enginePath = Join-Path $srcDir "market_intelligence_engine.py"
$runnerPath = Join-Path $root "run_market_intelligence.ps1"
$manifestPath = Join-Path $srcDir "market_intelligence.manifest.json"

$engineCode = @'
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import sqlite3
import statistics
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT / "database" / "polymarket.db"
REPORT_DIR = ROOT / "reports" / "market_intelligence"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    }


def grade(score: float) -> str:
    if score >= 92:
        return "S"
    if score >= 85:
        return "A+"
    if score >= 78:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 62:
        return "B"
    if score >= 52:
        return "C"
    return "PASS"


def trend_label(value: float, tolerance: float = 0.005) -> str:
    if value > tolerance:
        return "RISING"
    if value < -tolerance:
        return "FALLING"
    return "STABLE"


@dataclass
class MarketSignal:
    market_id: str
    title: str
    outcome: str
    latest_scanned_at: str
    observations: int
    wallet_count: int
    combined_value: float
    combined_pnl: float
    average_entry_price: float
    average_current_price: float
    observed_price_move: float
    conviction_score: float
    conviction_trend: float
    price_trend: float
    value_trend: float
    wallet_trend: float
    agreement_score: float
    momentum_score: float
    persistence_score: float
    value_quality_score: float
    risk_penalty: float
    opportunity_score: float
    opportunity_grade: str
    state: str
    reasons: str


def fetch_consensus_groups(
    connection: sqlite3.Connection,
    history_limit: int,
) -> list[list[sqlite3.Row]]:
    if not table_exists(connection, "consensus_history"):
        return []

    columns = table_columns(connection, "consensus_history")
    required = {"market_id", "title", "outcome", "scanned_at"}
    if not required.issubset(columns):
        return []

    selectable = [
        "market_id",
        "title",
        "outcome",
        "wallet_count",
        "combined_value",
        "combined_pnl",
        "conviction_score",
        "average_entry_price",
        "average_current_price",
        "observed_price_move",
        "scanned_at",
    ]
    select_sql = ", ".join(
        column if column in columns else f"NULL AS {column}"
        for column in selectable
    )

    rows = connection.execute(
        f"""
        SELECT {select_sql}
        FROM consensus_history
        WHERE market_id IS NOT NULL
          AND outcome IS NOT NULL
        ORDER BY market_id, outcome, scanned_at DESC
        """
    ).fetchall()

    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        key = (str(row["market_id"]), str(row["outcome"]))
        group = groups.setdefault(key, [])
        if len(group) < history_limit:
            group.append(row)

    return list(groups.values())


def compute_signal(rows: list[sqlite3.Row]) -> MarketSignal:
    latest = rows[0]
    chronological = list(reversed(rows))

    wallet_counts = [safe_float(row["wallet_count"]) for row in chronological]
    values = [safe_float(row["combined_value"]) for row in chronological]
    pnls = [safe_float(row["combined_pnl"]) for row in chronological]
    convictions = [safe_float(row["conviction_score"]) for row in chronological]
    current_prices = [safe_float(row["average_current_price"]) for row in chronological]
    observed_moves = [safe_float(row["observed_price_move"]) for row in chronological]

    latest_wallets = safe_int(latest["wallet_count"])
    latest_value = safe_float(latest["combined_value"])
    latest_pnl = safe_float(latest["combined_pnl"])
    latest_conviction = safe_float(latest["conviction_score"])
    latest_current_price = safe_float(latest["average_current_price"])
    latest_entry_price = safe_float(latest["average_entry_price"])
    latest_move = safe_float(latest["observed_price_move"])

    def delta(series: list[float]) -> float:
        return series[-1] - series[0] if len(series) >= 2 else 0.0

    conviction_trend = delta(convictions)
    price_trend = delta(current_prices)
    value_trend = delta(values)
    wallet_trend = delta(wallet_counts)

    agreement_score = clamp(
        18.0 * math.log1p(max(latest_wallets, 0))
        + 0.55 * latest_conviction
    )

    movement_basis = latest_move if latest_move != 0 else price_trend
    momentum_score = clamp(
        50.0
        + 500.0 * movement_basis
        + 1.5 * conviction_trend
    )

    persistence_score = clamp(
        25.0
        + min(len(rows), 8) * 8.0
        + (8.0 if conviction_trend >= 0 else -8.0)
        + (8.0 if wallet_trend >= 0 else -8.0)
    )

    value_log = math.log10(max(latest_value, 1.0))
    pnl_ratio = latest_pnl / latest_value if latest_value > 0 else 0.0
    value_quality_score = clamp(
        12.0 * value_log
        + 220.0 * pnl_ratio
        + (8.0 if value_trend >= 0 else -8.0)
    )

    risk_penalty = 0.0
    if latest_wallets < 2:
        risk_penalty += 18.0
    if len(rows) < 2:
        risk_penalty += 12.0
    if latest_current_price <= 0.01 or latest_current_price >= 0.99:
        risk_penalty += 8.0
    if conviction_trend < -5:
        risk_penalty += min(abs(conviction_trend), 20.0)
    if value_trend < 0:
        risk_penalty += 7.0
    if latest_pnl < 0:
        risk_penalty += min(15.0, abs(pnl_ratio) * 100.0)

    opportunity_score = clamp(
        0.34 * agreement_score
        + 0.22 * momentum_score
        + 0.20 * persistence_score
        + 0.24 * value_quality_score
        - risk_penalty
    )

    state_parts = [
        trend_label(conviction_trend, 1.0),
        trend_label(price_trend, 0.01),
    ]
    state = " / ".join(state_parts)

    reasons: list[str] = []
    if latest_wallets >= 3:
        reasons.append(f"{latest_wallets} agreeing wallets")
    elif latest_wallets == 2:
        reasons.append("minimum multi-wallet agreement")
    else:
        reasons.append("single-wallet concentration")

    if conviction_trend > 2:
        reasons.append("conviction improving")
    elif conviction_trend < -2:
        reasons.append("conviction weakening")
    else:
        reasons.append("conviction stable")

    if value_trend > 0:
        reasons.append("tracked value increasing")
    elif value_trend < 0:
        reasons.append("tracked value decreasing")

    if movement_basis > 0.01:
        reasons.append("positive price momentum")
    elif movement_basis < -0.01:
        reasons.append("negative price momentum")

    if len(rows) >= 3:
        reasons.append(f"persistent across {len(rows)} snapshots")
    else:
        reasons.append("limited history")

    if risk_penalty >= 20:
        reasons.append("material risk penalties")

    return MarketSignal(
        market_id=str(latest["market_id"]),
        title=str(latest["title"] or ""),
        outcome=str(latest["outcome"] or ""),
        latest_scanned_at=str(latest["scanned_at"] or ""),
        observations=len(rows),
        wallet_count=latest_wallets,
        combined_value=round(latest_value, 2),
        combined_pnl=round(latest_pnl, 2),
        average_entry_price=round(latest_entry_price, 6),
        average_current_price=round(latest_current_price, 6),
        observed_price_move=round(latest_move, 6),
        conviction_score=round(latest_conviction, 2),
        conviction_trend=round(conviction_trend, 2),
        price_trend=round(price_trend, 6),
        value_trend=round(value_trend, 2),
        wallet_trend=round(wallet_trend, 2),
        agreement_score=round(agreement_score, 2),
        momentum_score=round(momentum_score, 2),
        persistence_score=round(persistence_score, 2),
        value_quality_score=round(value_quality_score, 2),
        risk_penalty=round(risk_penalty, 2),
        opportunity_score=round(opportunity_score, 2),
        opportunity_grade=grade(opportunity_score),
        state=state,
        reasons="; ".join(reasons),
    )


def fallback_positions_summary(connection: sqlite3.Connection) -> list[MarketSignal]:
    if not table_exists(connection, "positions"):
        return []

    columns = table_columns(connection, "positions")
    required = {"market_id", "title", "outcome", "wallet"}
    if not required.issubset(columns):
        return []

    value_expression = (
        "COALESCE(current_value, 0)"
        if "current_value" in columns
        else "0"
    )
    pnl_expression = (
        "COALESCE(cash_pnl, 0)"
        if "cash_pnl" in columns
        else "0"
    )
    entry_expression = (
        "AVG(COALESCE(average_price, 0))"
        if "average_price" in columns
        else "0"
    )
    current_expression = (
        "AVG(COALESCE(current_price, 0))"
        if "current_price" in columns
        else "0"
    )

    rows = connection.execute(
        f"""
        SELECT
            market_id,
            MAX(title) AS title,
            outcome,
            COUNT(DISTINCT wallet) AS wallet_count,
            SUM({value_expression}) AS combined_value,
            SUM({pnl_expression}) AS combined_pnl,
            {entry_expression} AS average_entry_price,
            {current_expression} AS average_current_price
        FROM positions
        GROUP BY market_id, outcome
        """
    ).fetchall()

    signals: list[MarketSignal] = []
    for row in rows:
        wallets = safe_int(row["wallet_count"])
        value = safe_float(row["combined_value"])
        pnl = safe_float(row["combined_pnl"])
        current_price = safe_float(row["average_current_price"])
        entry_price = safe_float(row["average_entry_price"])
        move = current_price - entry_price

        agreement = clamp(18.0 * math.log1p(wallets))
        momentum = clamp(50.0 + 500.0 * move)
        persistence = 25.0
        value_quality = clamp(
            12.0 * math.log10(max(value, 1.0))
            + (220.0 * pnl / value if value > 0 else 0.0)
        )
        risk = 30.0 if wallets < 2 else 15.0
        opportunity = clamp(
            0.34 * agreement
            + 0.22 * momentum
            + 0.20 * persistence
            + 0.24 * value_quality
            - risk
        )

        signals.append(
            MarketSignal(
                market_id=str(row["market_id"]),
                title=str(row["title"] or ""),
                outcome=str(row["outcome"] or ""),
                latest_scanned_at="positions fallback",
                observations=1,
                wallet_count=wallets,
                combined_value=round(value, 2),
                combined_pnl=round(pnl, 2),
                average_entry_price=round(entry_price, 6),
                average_current_price=round(current_price, 6),
                observed_price_move=round(move, 6),
                conviction_score=0.0,
                conviction_trend=0.0,
                price_trend=0.0,
                value_trend=0.0,
                wallet_trend=0.0,
                agreement_score=round(agreement, 2),
                momentum_score=round(momentum, 2),
                persistence_score=round(persistence, 2),
                value_quality_score=round(value_quality, 2),
                risk_penalty=round(risk, 2),
                opportunity_score=round(opportunity, 2),
                opportunity_grade=grade(opportunity),
                state="FALLBACK / LIMITED HISTORY",
                reasons="Calculated from current positions because consensus history was unavailable.",
            )
        )

    return signals


def generate_reports(signals: list[MarketSignal], source: str) -> dict[str, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ")

    signals = sorted(
        signals,
        key=lambda item: (
            item.opportunity_score,
            item.wallet_count,
            item.combined_value,
        ),
        reverse=True,
    )

    payload = {
        "run_id": run_id,
        "generated_at": iso_now(),
        "source": source,
        "records_analyzed": len(signals),
        "methodology": {
            "read_only": True,
            "production_thresholds_modified": False,
            "score_components": [
                "wallet agreement",
                "price momentum",
                "snapshot persistence",
                "tracked value quality",
                "risk penalties",
            ],
            "warning": (
                "Opportunity scores prioritize research. They are not guarantees "
                "or automated trade instructions."
            ),
        },
        "signals": [asdict(signal) for signal in signals],
    }

    json_path = REPORT_DIR / f"market_intelligence_{run_id}.json"
    csv_path = REPORT_DIR / f"market_intelligence_{run_id}.csv"
    txt_path = REPORT_DIR / f"market_intelligence_{run_id}.txt"
    html_path = REPORT_DIR / f"market_intelligence_{run_id}.html"

    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    fieldnames = list(asdict(signals[0]).keys()) if signals else [
        field.name for field in MarketSignal.__dataclass_fields__.values()
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for signal in signals:
            writer.writerow(asdict(signal))

    lines = [
        "POLYMARKET MARKET INTELLIGENCE",
        "=" * 100,
        f"Generated: {payload['generated_at']}",
        f"Source: {source}",
        f"Records analyzed: {len(signals)}",
        "",
    ]
    for index, signal in enumerate(signals[:50], start=1):
        lines.extend(
            [
                f"{index}. [{signal.opportunity_grade}] {signal.opportunity_score:.2f} — "
                f"{signal.title} — {signal.outcome}",
                f"   Wallets: {signal.wallet_count} | Conviction: {signal.conviction_score:.2f} "
                f"| Value: ${signal.combined_value:,.2f}",
                f"   State: {signal.state}",
                f"   Reasons: {signal.reasons}",
                "",
            ]
        )
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    rows = []
    for index, signal in enumerate(signals, start=1):
        rows.append(
            f"""
            <tr>
              <td>{index}</td>
              <td><strong>{html.escape(signal.opportunity_grade)}</strong><br>{signal.opportunity_score:.2f}</td>
              <td>{html.escape(signal.title)}<br><small>{html.escape(signal.outcome)}</small></td>
              <td>{signal.wallet_count}</td>
              <td>{signal.conviction_score:.2f}<br><small>Δ {signal.conviction_trend:+.2f}</small></td>
              <td>${signal.combined_value:,.2f}<br><small>Δ ${signal.value_trend:+,.2f}</small></td>
              <td>{signal.average_current_price:.3f}<br><small>Δ {signal.price_trend:+.3f}</small></td>
              <td>{html.escape(signal.state)}</td>
              <td>{html.escape(signal.reasons)}</td>
            </tr>
            """
        )

    top = signals[:10]
    top_cards = "".join(
        f"""
        <div class="card">
          <div class="grade">{html.escape(item.opportunity_grade)} · {item.opportunity_score:.1f}</div>
          <h3>{html.escape(item.title)}</h3>
          <p><strong>{html.escape(item.outcome)}</strong></p>
          <p>{html.escape(item.reasons)}</p>
        </div>
        """
        for item in top
    ) or '<div class="card"><h3>No market signals available</h3></div>'

    html_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Intelligence</title>
<style>
body {{ margin:0; font-family:Arial,sans-serif; background:#f4f6f8; color:#172033; }}
header {{ background:#111827; color:white; padding:28px; }}
main {{ max-width:1450px; margin:auto; padding:24px; }}
.summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; }}
.card, section {{ background:white; padding:18px; border-radius:12px; box-shadow:0 2px 10px rgba(0,0,0,.06); }}
.card h3 {{ margin-bottom:6px; }}
.grade {{ font-size:22px; font-weight:bold; }}
section {{ margin-top:22px; overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; min-width:1150px; }}
th, td {{ text-align:left; padding:10px; border-bottom:1px solid #e5e7eb; vertical-align:top; }}
small {{ color:#667085; }}
.notice {{ background:#fff7ed; border-left:5px solid #f59e0b; }}
</style>
</head>
<body>
<header>
<h1>Polymarket Market Intelligence</h1>
<div>Generated: {html.escape(payload['generated_at'])}</div>
<div>Data source: {html.escape(source)} · Records: {len(signals)}</div>
</header>
<main>
<section class="notice">
<strong>Research-priority model:</strong> Scores rank markets for further review. They do not guarantee outcomes and do not modify production decision thresholds.
</section>
<h2>Highest-priority research candidates</h2>
<div class="summary">{top_cards}</div>
<section>
<h2>Complete market board</h2>
<table>
<thead>
<tr>
<th>#</th><th>Grade / Score</th><th>Market</th><th>Wallets</th>
<th>Conviction</th><th>Tracked Value</th><th>Price</th><th>State</th><th>Explanation</th>
</tr>
</thead>
<tbody>{''.join(rows)}</tbody>
</table>
</section>
</main>
</body>
</html>
""",
        encoding="utf-8",
    )

    latest = {
        "json": REPORT_DIR / "latest.json",
        "csv": REPORT_DIR / "latest.csv",
        "txt": REPORT_DIR / "latest.txt",
        "html": REPORT_DIR / "latest.html",
    }
    latest["json"].write_bytes(json_path.read_bytes())
    latest["csv"].write_bytes(csv_path.read_bytes())
    latest["txt"].write_bytes(txt_path.read_bytes())
    latest["html"].write_bytes(html_path.read_bytes())

    return {
        "json": json_path,
        "csv": csv_path,
        "txt": txt_path,
        "html": html_path,
        **{f"latest_{key}": value for key, value in latest.items()},
    }


def run(history_limit: int) -> tuple[list[MarketSignal], str]:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row

    try:
        groups = fetch_consensus_groups(connection, history_limit)
        signals = [compute_signal(group) for group in groups if group]

        if signals:
            return signals, "consensus_history"

        fallback = fallback_positions_summary(connection)
        return fallback, "positions_fallback"
    finally:
        connection.close()


def self_test() -> int:
    synthetic = [
        {
            "market_id": "demo",
            "title": "Synthetic market",
            "outcome": "Yes",
            "wallet_count": 2,
            "combined_value": 1000,
            "combined_pnl": 50,
            "conviction_score": 70,
            "average_entry_price": 0.50,
            "average_current_price": 0.55,
            "observed_price_move": 0.05,
            "scanned_at": "2026-01-01T00:00:00",
        },
        {
            "market_id": "demo",
            "title": "Synthetic market",
            "outcome": "Yes",
            "wallet_count": 3,
            "combined_value": 1500,
            "combined_pnl": 100,
            "conviction_score": 80,
            "average_entry_price": 0.50,
            "average_current_price": 0.60,
            "observed_price_move": 0.05,
            "scanned_at": "2026-01-02T00:00:00",
        },
    ]

    class FakeRow(dict):
        def __getitem__(self, key: str) -> Any:
            return self.get(key)

    signal = compute_signal([FakeRow(synthetic[1]), FakeRow(synthetic[0])])
    assert 0 <= signal.opportunity_score <= 100
    assert signal.wallet_count == 3
    assert signal.conviction_trend == 10
    assert signal.opportunity_grade
    print("Self-test passed.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-limit", type=int, default=8)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(self_test())

    if args.dry_run:
        if not DATABASE_PATH.exists():
            raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
        print(f"Dry run passed. Database found: {DATABASE_PATH}")
        print("No database or report modifications performed.")
        return

    signals, source = run(max(2, args.history_limit))
    reports = generate_reports(signals, source)

    print()
    print("=" * 110)
    print("POLYMARKET MARKET INTELLIGENCE ENGINE")
    print("=" * 110)
    print(f"Data source:             {source}")
    print(f"Markets analyzed:        {len(signals)}")
    print(f"Latest HTML:             {reports['latest_html']}")
    print(f"Latest CSV:              {reports['latest_csv']}")
    print(f"Latest JSON:             {reports['latest_json']}")
    print(f"Latest TXT:              {reports['latest_txt']}")
    print("Database modified:       NO")
    print("Production thresholds:   NOT MODIFIED")
    print("=" * 110)

    if not args.no_open and reports["latest_html"].exists():
        os.startfile(str(reports["latest_html"]))


if __name__ == "__main__":
    main()

'@

$runnerCode = @'
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python `
    .\src\market_intelligence_engine.py `
    @args

exit $LASTEXITCODE

'@

$manifestCode = @'
{
  "id": "market_intelligence",
  "name": "Market Intelligence",
  "version": "1.0.0",
  "runner": "run_market_intelligence.ps1",
  "enabled": true,
  "required": true,
  "stage": "intelligence",
  "order": 50,
  "dependencies": [],
  "latest_report": "reports/market_intelligence/latest.html",
  "timeout_seconds": 900
}
'@

if (Test-Path $enginePath) {
    $backup = "$enginePath.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
    Copy-Item $enginePath $backup
    Write-Host "Existing engine backed up:"
    Write-Host $backup
}

Set-Content -Path $enginePath -Value $engineCode -Encoding UTF8
Set-Content -Path $runnerPath -Value $runnerCode -Encoding UTF8
Set-Content -Path $manifestPath -Value $manifestCode -Encoding UTF8

python -m py_compile $enginePath
if ($LASTEXITCODE -ne 0) {
    throw "Market Intelligence Engine compile check failed."
}

Write-Host ""
Write-Host "Running engine self-test..."
& $runnerPath --self-test
if ($LASTEXITCODE -ne 0) {
    throw "Market Intelligence Engine self-test failed."
}

Write-Host ""
Write-Host "Running database-aware dry run..."
& $runnerPath --dry-run
if ($LASTEXITCODE -ne 0) {
    throw "Market Intelligence Engine dry run failed."
}

Write-Host ""
Write-Host ("=" * 110)
Write-Host "MARKET INTELLIGENCE ENGINE INSTALLED"
Write-Host ("=" * 110)
Write-Host "Engine:       $enginePath"
Write-Host "Runner:       $runnerPath"
Write-Host "Manifest:     $manifestPath"
Write-Host "Reports:      $reportDir"
Write-Host ""
Write-Host "Run this engine:"
Write-Host ".\run_market_intelligence.ps1"
Write-Host ""
Write-Host "Run the full plugin pipeline:"
Write-Host ".\run_platform.ps1"
Write-Host ""
Write-Host "Database modified:       NO"
Write-Host "Production thresholds:   NOT MODIFIED"
Write-Host ("=" * 110)