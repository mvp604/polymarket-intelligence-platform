param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$DatabasePath = Join-Path $ProjectRoot "database\polymarket.db"
$EnginePath = Join-Path $ProjectRoot "src\historical_timeline_engine.py"
$RunnerPath = Join-Path $ProjectRoot "automation\run_historical_timeline.ps1"
$BackupRoot = Join-Path $ProjectRoot "automation\backups"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $BackupRoot "historical_timeline_v1_1_hotfix_$Timestamp"

foreach ($Required in @($DatabasePath, $EnginePath, $RunnerPath)) {
    if (-not (Test-Path $Required)) {
        throw "Required project item not found: $Required"
    }
}

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $DatabasePath (Join-Path $BackupDir "polymarket.db") -Force
Copy-Item $EnginePath (Join-Path $BackupDir "historical_timeline_engine.py") -Force
Copy-Item $RunnerPath (Join-Path $BackupDir "run_historical_timeline.ps1") -Force

$MigrationPath = Join-Path $BackupDir "migrate_cluster_evolution_v1_1.py"

$Migration = @'
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


def checksum(row: sqlite3.Row) -> str:
    state = {
        "smart_money_score": round(float(row["smart_money_score"]), 6),
        "recommendation": row["recommendation"],
        "signal_grade": row["signal_grade"],
        "wallet_count": row["wallet_count"],
        "elite_wallet_count": row["elite_wallet_count"],
        "combined_capital": round(float(row["combined_capital"]), 6),
        "entry_window_minutes": row["entry_window_minutes"],
        "timing_status": row["timing_status"],
    }
    body = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


with sqlite3.connect(DATABASE_PATH) as connection:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    if "cluster_evolution" not in tables:
        raise RuntimeError("cluster_evolution table was not found.")

    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(cluster_evolution)"
        )
    }

    if "state_checksum" not in columns:
        connection.execute(
            "ALTER TABLE cluster_evolution ADD COLUMN state_checksum TEXT"
        )

    rows = connection.execute(
        """
        SELECT
            id,
            smart_money_score,
            recommendation,
            signal_grade,
            wallet_count,
            elite_wallet_count,
            combined_capital,
            entry_window_minutes,
            timing_status
        FROM cluster_evolution
        ORDER BY id
        """
    ).fetchall()

    for row in rows:
        connection.execute(
            """
            UPDATE cluster_evolution
            SET state_checksum=?
            WHERE id=?
            """,
            (checksum(row), row["id"]),
        )

    connection.execute(
        """
        DELETE FROM cluster_evolution
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM cluster_evolution
            GROUP BY cluster_id, state_checksum
        )
        """
    )

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_cluster_evolution_state
        ON cluster_evolution(cluster_id, state_checksum)
        """
    )

    connection.execute(
        """
        UPDATE historical_timeline_runs
        SET
            status='FAILED',
            completed_at=COALESCE(completed_at, ?),
            warnings_json='["v1.1 schema migration was missing; repaired by hotfix."]'
        WHERE status='RUNNING'
          AND engine_version='1.1.0'
        """,
        (datetime.now(UTC).isoformat(timespec="seconds"),),
    )

    connection.commit()

    remaining = connection.execute(
        "SELECT COUNT(*) FROM cluster_evolution"
    ).fetchone()[0]

print(f"cluster_evolution migration complete. Preserved rows: {remaining:,}")
'@

[System.IO.File]::WriteAllText(
    $MigrationPath,
    $Migration,
    (New-Object System.Text.UTF8Encoding($false))
)

Write-Host ""
Write-Host "Applying Historical Timeline v1.1 schema migration..."
python $MigrationPath
if ($LASTEXITCODE -ne 0) {
    throw "Schema migration failed. Backup: $BackupDir"
}

python -m py_compile $EnginePath
if ($LASTEXITCODE -ne 0) {
    throw "Historical Timeline Engine compilation failed. Backup: $BackupDir"
}

Write-Host ""
Write-Host "Re-running Historical Timeline Engine v1.1..."
Push-Location $ProjectRoot
try {
    python -m src.historical_timeline_engine
    if ($LASTEXITCODE -ne 0) {
        throw "Historical Timeline Engine v1.1 failed after migration. Backup: $BackupDir"
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "HISTORICAL TIMELINE v1.1 HOTFIX COMPLETE"
Write-Host "Database migration: SUCCESS"
Write-Host "Change-only cluster index: SUCCESS"
Write-Host "Backup: $BackupDir"
Write-Host ""
Write-Host "Repeatability test:"
Write-Host "  .\automation\run_historical_timeline.ps1"
