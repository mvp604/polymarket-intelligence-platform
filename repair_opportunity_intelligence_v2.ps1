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
$DatabasePath = Join-Path $ProjectRoot "database\polymarket.db"
$EnginePath = Join-Path $SrcDir "opportunity_intelligence_engine.py"
$LockPath = Join-Path $ProjectRoot "logs\automation\platform.lock"

foreach ($Required in @($SrcDir, $AutomationDir, $DatabasePath, $EnginePath)) {
    if (-not (Test-Path $Required)) {
        throw "Required project item not found: $Required"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $AutomationDir "backups\opportunity_engine_v2_$Timestamp"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

Copy-Item $DatabasePath (Join-Path $BackupDir "polymarket.db") -Force
Copy-Item $EnginePath (Join-Path $BackupDir "opportunity_intelligence_engine.py") -Force

$PatchPath = Join-Path $SrcDir "repair_opportunity_engine_v2.py"

$PatchCode = @'
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_PATH = PROJECT_ROOT / "src" / "opportunity_intelligence_engine.py"

OUTPUT_TABLES = {
    "opportunity_engine_runs",
    "opportunity_scores",
    "opportunity_score_history",
    "intelligence_wallets",
    "intelligence_markets",
    "intelligence_signals",
}


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def table_info(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return connection.execute(f'PRAGMA table_info("{table}")').fetchall()


def has_unique_market_id(connection: sqlite3.Connection) -> bool:
    info = table_info(connection, "opportunity_scores")
    for row in info:
        if str(row[1]) == "market_id" and int(row[5]) > 0:
            return True

    for index_row in connection.execute(
        'PRAGMA index_list("opportunity_scores")'
    ).fetchall():
        if not bool(index_row[2]):
            continue
        index_name = str(index_row[1])
        cols = [
            str(row[2])
            for row in connection.execute(
                f'PRAGMA index_info("{index_name}")'
            ).fetchall()
        ]
        if cols == ["market_id"]:
            return True
    return False


def rebuild_scores_table(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "opportunity_scores"):
        return

    if has_unique_market_id(connection):
        print("SUCCESS: opportunity_scores.market_id is already unique")
        return

    print("REPAIR: Rebuilding opportunity_scores with market_id PRIMARY KEY")

    connection.execute("DROP VIEW IF EXISTS opportunity_daily_board")
    connection.execute("DROP TABLE IF EXISTS opportunity_scores_v2")

    connection.execute(
        """
        CREATE TABLE opportunity_scores_v2 (
            market_id TEXT PRIMARY KEY,
            question TEXT,
            category TEXT,
            selected_outcome TEXT,
            current_price REAL,
            opportunity_score REAL NOT NULL DEFAULT 0,
            confidence_score REAL NOT NULL DEFAULT 0,
            wallet_component REAL NOT NULL DEFAULT 0,
            consensus_component REAL NOT NULL DEFAULT 0,
            health_component REAL NOT NULL DEFAULT 0,
            liquidity_component REAL NOT NULL DEFAULT 0,
            momentum_component REAL NOT NULL DEFAULT 0,
            risk_penalty REAL NOT NULL DEFAULT 0,
            data_quality_score REAL NOT NULL DEFAULT 0,
            recommendation TEXT NOT NULL DEFAULT 'PASS',
            signal_grade TEXT NOT NULL DEFAULT 'PASS',
            risk_level TEXT NOT NULL DEFAULT 'HIGH',
            explanation_json TEXT NOT NULL DEFAULT '{}',
            source_table TEXT NOT NULL DEFAULT '',
            source_updated_at TEXT,
            calculated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )

    old_columns = {str(row[1]) for row in table_info(connection, "opportunity_scores")}
    new_columns = {str(row[1]) for row in table_info(connection, "opportunity_scores_v2")}
    shared = [
        column
        for column in new_columns
        if column in old_columns
    ]

    if "market_id" in shared:
        quoted = ", ".join(f'"{column}"' for column in shared)
        connection.execute(
            f"""
            INSERT OR REPLACE INTO opportunity_scores_v2 ({quoted})
            SELECT {quoted}
            FROM opportunity_scores
            WHERE market_id IS NOT NULL
              AND TRIM(CAST(market_id AS TEXT)) <> ''
            ORDER BY rowid
            """
        )

    connection.execute("DROP TABLE opportunity_scores")
    connection.execute("ALTER TABLE opportunity_scores_v2 RENAME TO opportunity_scores")

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunity_score_rank
        ON opportunity_scores(opportunity_score DESC, confidence_score DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunity_recommendation
        ON opportunity_scores(recommendation, signal_grade, risk_level)
        """
    )
    connection.execute(
        """
        CREATE VIEW opportunity_daily_board AS
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
            risk_level ASC
        """
    )

    if not has_unique_market_id(connection):
        raise RuntimeError("Failed to create unique market_id constraint.")

    print("SUCCESS: opportunity_scores rebuilt with primary key")


def patch_engine_source_discovery() -> None:
    text = ENGINE_PATH.read_text(encoding="utf-8-sig")

    old_loop = "    for table in table_names(connection):\n        available = columns(connection, table)"
    new_loop = """    excluded_tables = {
        "opportunity_engine_runs",
        "opportunity_scores",
        "opportunity_score_history",
        "intelligence_wallets",
        "intelligence_markets",
        "intelligence_signals",
    }

    for table in table_names(connection):
        if table in excluded_tables:
            continue

        available = columns(connection, table)"""

    if old_loop in text:
        text = text.replace(old_loop, new_loop, 1)
    elif '"opportunity_score_history"' not in text:
        raise RuntimeError(
            "Could not locate the source-discovery loop in opportunity_intelligence_engine.py"
        )

    old_required = """    required_groups = (
        ("market_id", "condition_id", "token_id", "id", "slug"),
        ("opportunity_score", "opportunity", "health_score", "market_health"),
    )"""
    new_required = """    required_groups = (
        ("market_id", "condition_id", "token_id", "id", "slug"),
        ("opportunity_score", "opportunity", "health_score", "market_health"),
    )"""

    text = text.replace(old_required, new_required, 1)

    ENGINE_PATH.write_text(text, encoding="utf-8")
    print("SUCCESS: Output/history tables excluded from source discovery")


def show_feature_candidates(connection: sqlite3.Connection) -> None:
    print()
    print("FEATURE SOURCE CANDIDATES")
    print("-" * 108)

    candidates = []
    for row in connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall():
        table = str(row[0])
        if table in OUTPUT_TABLES:
            continue

        cols = {str(item[1]).lower() for item in table_info(connection, table)}
        has_id = bool(
            cols.intersection(
                {"market_id", "condition_id", "token_id", "id", "slug"}
            )
        )
        has_score = bool(
            cols.intersection(
                {
                    "opportunity_score",
                    "opportunity",
                    "health_score",
                    "market_health",
                }
            )
        )
        if has_id and has_score:
            count = int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
            candidates.append((count, table))

    candidates.sort(reverse=True)
    for count, table in candidates[:10]:
        print(f"{count:>10,} rows | {table}")

    if not candidates:
        raise RuntimeError("No valid feature source table remains after exclusions.")

    if candidates[0][0] < 10000:
        print(
            "WARNING: Largest feature source has fewer than 10,000 rows. "
            "The engine may still not be selecting the intended feature table."
        )


def main() -> int:
    print("=" * 108)
    print("OPPORTUNITY INTELLIGENCE ENGINE V2 REPAIR")
    print("=" * 108)
    print(f"Database: {DATABASE_PATH}")
    print(f"Engine:   {ENGINE_PATH}")

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("PRAGMA busy_timeout = 30000")

        rebuild_scores_table(connection)
        show_feature_candidates(connection)
        connection.commit()

    patch_engine_source_discovery()

    print("=" * 108)
    print("V2 REPAIR COMPLETE")
    print("=" * 108)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@

Write-Utf8NoBom -Path $PatchPath -Content $PatchCode

python -m py_compile $PatchPath
if ($LASTEXITCODE -ne 0) {
    throw "V2 repair module failed Python compilation."
}

Write-Host ""
Write-Host "Checking automation lock..."

if (Test-Path $LockPath) {
    $LockText = Get-Content $LockPath -Raw
    $PidMatch = [regex]::Match($LockText, 'PID=(\d+)|"pid"\s*:\s*(\d+)')
    $LockPid = $null

    if ($PidMatch.Success) {
        if ($PidMatch.Groups[1].Value) {
            $LockPid = [int]$PidMatch.Groups[1].Value
        }
        elseif ($PidMatch.Groups[2].Value) {
            $LockPid = [int]$PidMatch.Groups[2].Value
        }
    }

    $ProcessActive = $false
    if ($LockPid) {
        $ProcessActive = $null -ne (Get-Process -Id $LockPid -ErrorAction SilentlyContinue)
    }

    if ($ProcessActive) {
        throw "Platform automation is still active under PID $LockPid. Stop it before applying this repair."
    }

    Remove-Item $LockPath -Force
    Write-Host "Removed stale platform.lock."
}
else {
    Write-Host "No automation lock found."
}

Write-Host ""
Write-Host "Applying Opportunity Engine v2 repair..."
python -m src.repair_opportunity_engine_v2
if ($LASTEXITCODE -ne 0) {
    throw "Opportunity Engine v2 repair failed. Backup: $BackupDir"
}

python -m py_compile $EnginePath
if ($LASTEXITCODE -ne 0) {
    throw "Patched Opportunity Intelligence Engine failed compilation."
}

Write-Host ""
Write-Host "Running Opportunity Intelligence Engine..."
python -m src.opportunity_intelligence_engine
if ($LASTEXITCODE -ne 0) {
    throw "Opportunity Intelligence Engine failed after v2 repair. Backup: $BackupDir"
}

Write-Host ""
Write-Host "OPPORTUNITY INTELLIGENCE V2 REPAIR SUCCESSFUL"
Write-Host "Backup: $BackupDir"
Write-Host ""
Write-Host "Next command:"
Write-Host "  .\automation\run_platform.ps1 --only opportunity_intelligence"
