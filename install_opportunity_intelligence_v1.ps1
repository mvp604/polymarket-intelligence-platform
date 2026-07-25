param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    $Encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $Encoding)
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$SrcDir = Join-Path $ProjectRoot "src"
$AutomationDir = Join-Path $ProjectRoot "automation"
$MigrationDir = Join-Path $ProjectRoot "database\migrations"
$ConfigPath = Join-Path $AutomationDir "platform_automation.json"

foreach ($Dir in @($SrcDir, $AutomationDir, $MigrationDir)) {
    if (-not (Test-Path $Dir)) {
        throw "Required directory not found: $Dir"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $AutomationDir "backups\opportunity_intelligence_$Timestamp"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

$FilesToBackup = @(
    $ConfigPath,
    (Join-Path $SrcDir "intelligence_warehouse_engine.py"),
    (Join-Path $SrcDir "opportunity_intelligence_engine.py"),
    (Join-Path $MigrationDir "003_opportunity_intelligence.sql")
)

foreach ($File in $FilesToBackup) {
    if (Test-Path $File) {
        Copy-Item $File (Join-Path $BackupDir ([System.IO.Path]::GetFileName($File))) -Force
    }
}

$MigrationPath = Join-Path $MigrationDir "003_opportunity_intelligence.sql"
$Migration = @'
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS opportunity_engine_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    source_table TEXT,
    markets_reviewed INTEGER NOT NULL DEFAULT 0,
    scores_inserted INTEGER NOT NULL DEFAULT 0,
    scores_updated INTEGER NOT NULL DEFAULT 0,
    actionable_count INTEGER NOT NULL DEFAULT 0,
    watchlist_count INTEGER NOT NULL DEFAULT 0,
    pass_count INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS opportunity_scores (
    market_id TEXT PRIMARY KEY,
    question TEXT,
    category TEXT,
    selected_outcome TEXT,
    current_price REAL,
    opportunity_score REAL NOT NULL,
    confidence_score REAL NOT NULL,
    wallet_component REAL NOT NULL,
    consensus_component REAL NOT NULL,
    health_component REAL NOT NULL,
    liquidity_component REAL NOT NULL,
    momentum_component REAL NOT NULL,
    risk_penalty REAL NOT NULL,
    data_quality_score REAL NOT NULL,
    recommendation TEXT NOT NULL,
    signal_grade TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    explanation_json TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_updated_at TEXT,
    calculated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunity_score_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    opportunity_score REAL NOT NULL,
    confidence_score REAL NOT NULL,
    recommendation TEXT NOT NULL,
    signal_grade TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES opportunity_engine_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_opportunity_score_rank
    ON opportunity_scores(opportunity_score DESC, confidence_score DESC);

CREATE INDEX IF NOT EXISTS idx_opportunity_recommendation
    ON opportunity_scores(recommendation, signal_grade, risk_level);

CREATE INDEX IF NOT EXISTS idx_opportunity_history_market
    ON opportunity_score_history(market_id, calculated_at DESC);

CREATE VIEW IF NOT EXISTS opportunity_daily_board AS
SELECT
    market_id,
    question,
    category,
    selected_outcome,
    current_price,
    opportunity_score,
    confidence_score,
    recommendation,
    signal_grade,
    risk_level,
    explanation_json,
    calculated_at
FROM opportunity_scores
WHERE recommendation IN ('ACTIONABLE', 'WATCHLIST')
ORDER BY
    CASE recommendation WHEN 'ACTIONABLE' THEN 0 ELSE 1 END,
    opportunity_score DESC,
    confidence_score DESC,
    risk_level ASC;
'@
Write-Utf8NoBom -Path $MigrationPath -Content $Migration

$EnginePath = Join-Path $SrcDir "opportunity_intelligence_engine.py"
$Engine = @'
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def table_names(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    ]


def columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    ]


def row_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def column_map(available: Iterable[str]) -> dict[str, str]:
    return {normalize(name): name for name in available}


def find_column(available: Iterable[str], candidates: Iterable[str]) -> str | None:
    lookup = column_map(available)
    for candidate in candidates:
        found = lookup.get(normalize(candidate))
        if found:
            return found
    return None


def row_value(
    row: sqlite3.Row,
    available: list[str],
    candidates: Iterable[str],
) -> Any:
    column = find_column(available, candidates)
    return row[column] if column else None


def discover_feature_source(
    connection: sqlite3.Connection,
) -> tuple[str, list[str], int]:
    candidates: list[tuple[int, int, str, list[str]]] = []

    required_groups = (
        ("market_id", "condition_id", "token_id", "id", "slug"),
        ("opportunity_score", "opportunity", "health_score", "market_health"),
    )

    preferred_names = {
        "market_features": 50,
        "market_feature_profiles": 50,
        "market_feature_current": 50,
        "feature_profiles": 40,
        "features": 30,
        "intelligence_markets": 20,
    }

    for table in table_names(connection):
        available = columns(connection, table)
        has_id = find_column(available, required_groups[0]) is not None
        has_feature = find_column(available, required_groups[1]) is not None
        if not (has_id and has_feature):
            continue

        count = row_count(connection, table)
        richness = sum(
            find_column(
                available,
                group,
            )
            is not None
            for group in (
                ("question", "title", "market_question"),
                ("opportunity_score", "opportunity"),
                ("health_score", "market_health", "health"),
                ("risk_score", "risk"),
                ("wallet_score", "wallet_feature_score"),
                ("consensus_score", "conviction_score"),
                ("liquidity", "liquidity_num"),
                ("volume", "volume_num"),
                ("spread", "current_spread"),
                ("momentum_score", "price_momentum", "momentum"),
            )
        )
        priority = preferred_names.get(table, 0) + richness
        candidates.append((count, priority, table, available))

    if not candidates:
        raise RuntimeError(
            "No compatible feature table found. Expected a table containing "
            "a market identifier and feature-score columns."
        )

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    count, _, table, available = candidates[0]
    return table, available, count


def normalize_score(value: Any, default: float = 0.0) -> float:
    number = as_float(value)
    if number is None:
        return default
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return clamp(number)


def liquidity_quality(liquidity: float | None, volume: float | None, spread: float | None) -> float:
    liquidity_part = 0.0
    volume_part = 0.0
    spread_part = 50.0

    if liquidity is not None and liquidity > 0:
        liquidity_part = clamp(math.log10(liquidity + 1) / 6.0 * 100.0)

    if volume is not None and volume > 0:
        volume_part = clamp(math.log10(volume + 1) / 8.0 * 100.0)

    if spread is not None:
        normalized_spread = spread * 100.0 if 0 <= spread <= 1 else spread
        spread_part = clamp(100.0 - normalized_spread * 5.0)

    return clamp(liquidity_part * 0.45 + volume_part * 0.30 + spread_part * 0.25)


def derive_momentum(row: sqlite3.Row, available: list[str]) -> float:
    direct = row_value(
        row,
        available,
        ("momentum_score", "price_momentum_score", "momentum"),
    )
    if direct is not None:
        return normalize_score(direct, 50.0)

    changes = []
    for candidates in (
        ("price_change_1h", "price_delta_1h"),
        ("price_change_6h", "price_delta_6h"),
        ("price_change_24h", "price_delta_24h"),
        ("liquidity_change", "liquidity_delta"),
        ("volume_change", "volume_delta"),
    ):
        number = as_float(row_value(row, available, candidates))
        if number is not None:
            changes.append(number)

    if not changes:
        return 50.0

    magnitude = sum(abs(value) for value in changes) / len(changes)
    if magnitude <= 1.0:
        magnitude *= 100.0
    return clamp(50.0 + min(magnitude, 50.0))


def signal_grade(score: float, confidence: float) -> str:
    conservative = min(score, confidence)
    if conservative >= 90:
        return "S+"
    if conservative >= 84:
        return "S"
    if conservative >= 78:
        return "A+"
    if conservative >= 72:
        return "A"
    if conservative >= 66:
        return "B"
    if conservative >= 60:
        return "C+"
    return "PASS"


def recommendation(score: float, confidence: float, risk: float) -> str:
    if score >= 78 and confidence >= 65 and risk <= 45:
        return "ACTIONABLE"
    if score >= 65 and confidence >= 50 and risk <= 60:
        return "WATCHLIST"
    return "PASS"


def risk_level(risk: float) -> str:
    if risk <= 20:
        return "LOW"
    if risk <= 40:
        return "MODERATE"
    if risk <= 60:
        return "ELEVATED"
    return "HIGH"


def explanation(
    wallet: float,
    consensus: float,
    health: float,
    liquidity: float,
    momentum: float,
    risk: float,
    quality: float,
) -> str:
    factors = {
        "wallet_intelligence": round(wallet, 2),
        "consensus_strength": round(consensus, 2),
        "market_health": round(health, 2),
        "liquidity_quality": round(liquidity, 2),
        "momentum": round(momentum, 2),
        "risk": round(risk, 2),
        "data_quality": round(quality, 2),
    }

    positives = [
        (name, value)
        for name, value in factors.items()
        if name not in {"risk", "data_quality"} and value >= 65
    ]
    positives.sort(key=lambda item: item[1], reverse=True)

    concerns = []
    if risk > 45:
        concerns.append("elevated_risk")
    if quality < 50:
        concerns.append("limited_data_quality")
    if liquidity < 40:
        concerns.append("weak_market_depth")
    if consensus < 40:
        concerns.append("weak_consensus")
    if wallet < 40:
        concerns.append("weak_wallet_support")

    payload = {
        "primary_drivers": [name for name, _ in positives[:4]],
        "concerns": concerns,
        "components": factors,
        "model_version": VERSION,
        "weights": {
            "wallet": 0.30,
            "consensus": 0.20,
            "health": 0.15,
            "liquidity": 0.15,
            "momentum": 0.10,
            "data_quality": 0.10,
            "risk_penalty_max": 15.0,
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def apply_schema(connection: sqlite3.Connection) -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "database"
        / "migrations"
        / "003_opportunity_intelligence.sql"
    )
    if not migration.exists():
        raise FileNotFoundError(f"Migration not found: {migration}")
    connection.executescript(migration.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank Polymarket opportunities.")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "database" / "polymarket.db",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    database_path = args.database.resolve()
    started_at = utc_now()
    run_id = (
        f"opportunity:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:"
        f"{uuid.uuid4().hex[:8]}"
    )
    warnings: list[str] = []

    print("=" * 124)
    print(f"OPPORTUNITY INTELLIGENCE ENGINE v{VERSION}")
    print("=" * 124)
    print(f"Run ID:   {run_id}")
    print(f"Database: {database_path}")

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        apply_schema(connection)

        source_table, available, source_count = discover_feature_source(connection)
        print(f"Source:   {source_table} ({source_count:,} rows)")

        connection.execute(
            """
            INSERT INTO opportunity_engine_runs (
                run_id, started_at, status, source_table
            )
            VALUES (?, ?, 'RUNNING', ?)
            """,
            (run_id, started_at, source_table),
        )
        connection.commit()

        market_id_column = find_column(
            available,
            ("market_id", "condition_id", "token_id", "id", "slug"),
        )
        if not market_id_column:
            raise RuntimeError("Selected source table has no market identifier.")

        sql = f'SELECT * FROM "{source_table}"'
        if args.limit:
            sql += f" LIMIT {int(args.limit)}"

        inserted = 0
        updated = 0
        actionable = 0
        watchlist = 0
        passed = 0
        reviewed = 0
        calculated_at = utc_now()

        try:
            cursor = connection.execute(sql)

            for row in cursor:
                market_id = as_text(row[market_id_column])
                if not market_id:
                    continue

                wallet = normalize_score(
                    row_value(row, available, ("wallet_score", "wallet_feature_score")),
                    0.0,
                )
                consensus = normalize_score(
                    row_value(
                        row,
                        available,
                        ("consensus_score", "conviction_score", "consensus_strength"),
                    ),
                    0.0,
                )
                health = normalize_score(
                    row_value(row, available, ("health_score", "market_health", "health")),
                    50.0,
                )
                risk = normalize_score(
                    row_value(row, available, ("risk_score", "risk")),
                    50.0,
                )

                liquidity_value = as_float(
                    row_value(row, available, ("liquidity", "liquidity_num"))
                )
                volume_value = as_float(
                    row_value(row, available, ("volume", "volume_num"))
                )
                spread_value = as_float(
                    row_value(row, available, ("spread", "current_spread"))
                )
                liquidity = liquidity_quality(
                    liquidity_value,
                    volume_value,
                    spread_value,
                )
                momentum = derive_momentum(row, available)

                present = sum(
                    value is not None
                    for value in (
                        row_value(row, available, ("wallet_score", "wallet_feature_score")),
                        row_value(row, available, ("consensus_score", "conviction_score")),
                        row_value(row, available, ("health_score", "market_health")),
                        row_value(row, available, ("risk_score", "risk")),
                        liquidity_value,
                        volume_value,
                        spread_value,
                    )
                )
                quality = clamp(present / 7.0 * 100.0)

                base_score = (
                    wallet * 0.30
                    + consensus * 0.20
                    + health * 0.15
                    + liquidity * 0.15
                    + momentum * 0.10
                    + quality * 0.10
                )
                penalty = clamp(risk / 100.0 * 15.0, 0.0, 15.0)
                score = clamp(base_score - penalty)

                confidence = clamp(
                    quality * 0.40
                    + min(wallet, consensus) * 0.20
                    + health * 0.20
                    + liquidity * 0.20
                )

                grade = signal_grade(score, confidence)
                rec = recommendation(score, confidence, risk)
                level = risk_level(risk)

                if rec == "ACTIONABLE":
                    actionable += 1
                elif rec == "WATCHLIST":
                    watchlist += 1
                else:
                    passed += 1

                question = as_text(
                    row_value(row, available, ("question", "title", "market_question"))
                )
                category = as_text(
                    row_value(row, available, ("category", "market_category", "sport", "tag"))
                )
                outcome = as_text(
                    row_value(row, available, ("outcome", "selected_outcome"))
                )
                current_price = as_float(
                    row_value(
                        row,
                        available,
                        ("current_price", "yes_price", "price", "last_price"),
                    )
                )
                source_updated_at = as_text(
                    row_value(
                        row,
                        available,
                        ("updated_at", "calculated_at", "snapshot_at"),
                    )
                )
                explain = explanation(
                    wallet,
                    consensus,
                    health,
                    liquidity,
                    momentum,
                    risk,
                    quality,
                )

                existed = connection.execute(
                    "SELECT 1 FROM opportunity_scores WHERE market_id = ?",
                    (market_id,),
                ).fetchone()

                connection.execute(
                    """
                    INSERT INTO opportunity_scores (
                        market_id,
                        question,
                        category,
                        selected_outcome,
                        current_price,
                        opportunity_score,
                        confidence_score,
                        wallet_component,
                        consensus_component,
                        health_component,
                        liquidity_component,
                        momentum_component,
                        risk_penalty,
                        data_quality_score,
                        recommendation,
                        signal_grade,
                        risk_level,
                        explanation_json,
                        source_table,
                        source_updated_at,
                        calculated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(market_id) DO UPDATE SET
                        question = excluded.question,
                        category = excluded.category,
                        selected_outcome = excluded.selected_outcome,
                        current_price = excluded.current_price,
                        opportunity_score = excluded.opportunity_score,
                        confidence_score = excluded.confidence_score,
                        wallet_component = excluded.wallet_component,
                        consensus_component = excluded.consensus_component,
                        health_component = excluded.health_component,
                        liquidity_component = excluded.liquidity_component,
                        momentum_component = excluded.momentum_component,
                        risk_penalty = excluded.risk_penalty,
                        data_quality_score = excluded.data_quality_score,
                        recommendation = excluded.recommendation,
                        signal_grade = excluded.signal_grade,
                        risk_level = excluded.risk_level,
                        explanation_json = excluded.explanation_json,
                        source_table = excluded.source_table,
                        source_updated_at = excluded.source_updated_at,
                        calculated_at = excluded.calculated_at
                    """,
                    (
                        market_id,
                        question,
                        category,
                        outcome,
                        current_price,
                        score,
                        confidence,
                        wallet,
                        consensus,
                        health,
                        liquidity,
                        momentum,
                        penalty,
                        quality,
                        rec,
                        grade,
                        level,
                        explain,
                        source_table,
                        source_updated_at,
                        calculated_at,
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO opportunity_score_history (
                        run_id,
                        market_id,
                        opportunity_score,
                        confidence_score,
                        recommendation,
                        signal_grade,
                        risk_level,
                        calculated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        market_id,
                        score,
                        confidence,
                        rec,
                        grade,
                        level,
                        calculated_at,
                    ),
                )

                if existed:
                    updated += 1
                else:
                    inserted += 1

                reviewed += 1
                if reviewed % 5000 == 0:
                    print(
                        f"Processed {reviewed:,} markets | "
                        f"actionable={actionable:,} | watchlist={watchlist:,}"
                    )

            connection.execute(
                """
                UPDATE opportunity_engine_runs
                SET completed_at = ?,
                    status = 'SUCCESS',
                    markets_reviewed = ?,
                    scores_inserted = ?,
                    scores_updated = ?,
                    actionable_count = ?,
                    watchlist_count = ?,
                    pass_count = ?,
                    warnings_json = ?
                WHERE run_id = ?
                """,
                (
                    utc_now(),
                    reviewed,
                    inserted,
                    updated,
                    actionable,
                    watchlist,
                    passed,
                    json.dumps(warnings),
                    run_id,
                ),
            )
            connection.commit()

        except Exception as exc:
            connection.rollback()
            connection.execute(
                """
                UPDATE opportunity_engine_runs
                SET completed_at = ?,
                    status = 'FAILED',
                    markets_reviewed = ?,
                    warnings_json = ?,
                    error_message = ?
                WHERE run_id = ?
                """,
                (utc_now(), reviewed, json.dumps(warnings), str(exc), run_id),
            )
            connection.commit()
            raise

        print()
        print("TOP OPPORTUNITY BOARD")
        print("-" * 124)
        top_rows = connection.execute(
            """
            SELECT
                question,
                market_id,
                selected_outcome,
                opportunity_score,
                confidence_score,
                recommendation,
                signal_grade,
                risk_level
            FROM opportunity_scores
            ORDER BY opportunity_score DESC, confidence_score DESC
            LIMIT 25
            """
        ).fetchall()

        for index, row in enumerate(top_rows, start=1):
            label = (row["question"] or row["market_id"] or "")[:72]
            outcome = (row["selected_outcome"] or "-")[:14]
            print(
                f"{index:>2}. {row['signal_grade']:<4} "
                f"{row['recommendation']:<10} "
                f"Score={row['opportunity_score']:>6.2f} "
                f"Conf={row['confidence_score']:>6.2f} "
                f"Risk={row['risk_level']:<8} "
                f"{outcome:<14} | {label}"
            )

        print()
        print("OPPORTUNITY INTELLIGENCE HEALTH SUMMARY")
        print("-" * 124)
        print("Status:             SUCCESS")
        print(f"Source table:       {source_table}")
        print(f"Source rows:        {source_count:,}")
        print(f"Markets reviewed:   {reviewed:,}")
        print(f"Scores inserted:    {inserted:,}")
        print(f"Scores updated:     {updated:,}")
        print(f"Actionable:         {actionable:,}")
        print(f"Watchlist:          {watchlist:,}")
        print(f"Pass:               {passed:,}")
        print(f"Warnings:           {len(warnings):,}")
        print("=" * 124)
        print("OPPORTUNITY INTELLIGENCE COMPLETE")
        print("=" * 124)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@
Write-Utf8NoBom -Path $EnginePath -Content $Engine

python -m py_compile $EnginePath
if ($LASTEXITCODE -ne 0) {
    throw "Opportunity Intelligence Engine failed Python compilation."
}

if (Test-Path $ConfigPath) {
    $Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
    $Existing = @($Config.steps | Where-Object {
        $_.name -eq "opportunity_intelligence" -or
        $_.module -eq "src.opportunity_intelligence_engine"
    })

    if ($Existing.Count -eq 0) {
        $NewStep = [pscustomobject]@{
            name = "opportunity_intelligence"
            module = "src.opportunity_intelligence_engine"
            required = $true
            enabled = $true
        }

        $Steps = [System.Collections.ArrayList]@($Config.steps)
        $WarehouseIndex = -1

        for ($Index = 0; $Index -lt $Steps.Count; $Index++) {
            if ($Steps[$Index].name -eq "intelligence_warehouse") {
                $WarehouseIndex = $Index
                break
            }
        }

        if ($WarehouseIndex -ge 0) {
            $Steps.Insert($WarehouseIndex + 1, $NewStep)
        }
        else {
            [void]$Steps.Add($NewStep)
        }

        $Config.steps = $Steps
        Write-Utf8NoBom -Path $ConfigPath -Content ($Config | ConvertTo-Json -Depth 30)
        Write-Host "Added opportunity_intelligence after intelligence_warehouse."
    }
    else {
        Write-Host "opportunity_intelligence is already configured."
    }

    python -c "import json, pathlib; json.loads(pathlib.Path(r'$ConfigPath').read_text(encoding='utf-8-sig')); print('CONFIG JSON: OK')"
    if ($LASTEXITCODE -ne 0) {
        throw "platform_automation.json is invalid."
    }
}

Write-Host ""
Write-Host "OPPORTUNITY INTELLIGENCE v1 INSTALLED"
Write-Host "Backup:    $BackupDir"
Write-Host "Migration: $MigrationPath"
Write-Host "Engine:    $EnginePath"
Write-Host ""
Write-Host "Run direct test:"
Write-Host "  python -m src.opportunity_intelligence_engine"
Write-Host ""
Write-Host "Run automation stage:"
Write-Host "  .\automation\run_platform.ps1 --only opportunity_intelligence"
Write-Host ""
Write-Host "Run full platform:"
Write-Host "  .\automation\run_platform.ps1"
