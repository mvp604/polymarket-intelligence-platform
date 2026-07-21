$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$srcDir = Join-Path $root "src"
$reportDir = Join-Path $root "reports\elite_wallet_database"
$databasePath = Join-Path $root "database\polymarket.db"
$backupDir = Join-Path $root "database\backups"

New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

if (-not (Test-Path $databasePath)) {
    throw "Database not found: $databasePath"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$databaseBackup = Join-Path $backupDir "polymarket_before_elite_wallet_database_$timestamp.db"
Copy-Item $databasePath $databaseBackup -Force

$enginePath = Join-Path $srcDir "elite_wallet_intelligence_database.py"
$runnerPath = Join-Path $root "run_elite_wallet_database.ps1"
$manifestPath = Join-Path $srcDir "elite_wallet_database.manifest.json"

$engineCode = @'
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT / "database" / "polymarket.db"
REPORT_DIR = ROOT / "reports" / "elite_wallet_database"
MIGRATION_ID = "2026_07_20_elite_wallet_intelligence_foundation_v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS platform_schema_migrations (
        migration_id TEXT PRIMARY KEY,
        applied_at TEXT NOT NULL,
        description TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wallet_intelligence_profiles (
        wallet TEXT PRIMARY KEY,
        first_seen_at TEXT,
        last_seen_at TEXT,
        status TEXT NOT NULL DEFAULT 'ACTIVE',

        overall_score REAL NOT NULL DEFAULT 0,
        overall_grade TEXT NOT NULL DEFAULT 'UNRATED',
        confidence_score REAL NOT NULL DEFAULT 0,
        current_rank INTEGER,

        markets_tracked INTEGER NOT NULL DEFAULT 0,
        resolved_markets INTEGER NOT NULL DEFAULT 0,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,

        win_rate REAL NOT NULL DEFAULT 0,
        realized_pnl REAL NOT NULL DEFAULT 0,
        unrealized_pnl REAL NOT NULL DEFAULT 0,
        total_pnl REAL NOT NULL DEFAULT 0,
        roi REAL NOT NULL DEFAULT 0,

        average_position_value REAL NOT NULL DEFAULT 0,
        median_position_value REAL NOT NULL DEFAULT 0,
        average_entry_price REAL NOT NULL DEFAULT 0,
        average_current_price REAL NOT NULL DEFAULT 0,
        average_entry_edge REAL NOT NULL DEFAULT 0,
        average_holding_hours REAL NOT NULL DEFAULT 0,

        timing_score REAL NOT NULL DEFAULT 0,
        conviction_score REAL NOT NULL DEFAULT 0,
        consistency_score REAL NOT NULL DEFAULT 0,
        risk_score REAL NOT NULL DEFAULT 0,
        influence_score REAL NOT NULL DEFAULT 0,
        specialization_score REAL NOT NULL DEFAULT 0,
        recent_form_score REAL NOT NULL DEFAULT 0,

        strongest_category TEXT,
        weakest_category TEXT,

        profile_version INTEGER NOT NULL DEFAULT 1,
        calculated_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wallet_category_performance (
        wallet TEXT NOT NULL,
        category TEXT NOT NULL,

        category_score REAL NOT NULL DEFAULT 0,
        category_grade TEXT NOT NULL DEFAULT 'UNRATED',
        confidence_score REAL NOT NULL DEFAULT 0,
        category_rank INTEGER,

        markets_tracked INTEGER NOT NULL DEFAULT 0,
        resolved_markets INTEGER NOT NULL DEFAULT 0,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,

        win_rate REAL NOT NULL DEFAULT 0,
        realized_pnl REAL NOT NULL DEFAULT 0,
        total_pnl REAL NOT NULL DEFAULT 0,
        roi REAL NOT NULL DEFAULT 0,

        average_position_value REAL NOT NULL DEFAULT 0,
        average_entry_edge REAL NOT NULL DEFAULT 0,
        average_holding_hours REAL NOT NULL DEFAULT 0,
        timing_score REAL NOT NULL DEFAULT 0,
        consistency_score REAL NOT NULL DEFAULT 0,
        recent_form_score REAL NOT NULL DEFAULT 0,

        first_market_at TEXT,
        last_market_at TEXT,
        calculated_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,

        PRIMARY KEY (wallet, category),
        FOREIGN KEY (wallet)
            REFERENCES wallet_intelligence_profiles(wallet)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wallet_influence_metrics (
        wallet TEXT PRIMARY KEY,

        observations INTEGER NOT NULL DEFAULT 0,
        markets_led INTEGER NOT NULL DEFAULT 0,
        followers_observed INTEGER NOT NULL DEFAULT 0,

        average_lead_minutes REAL NOT NULL DEFAULT 0,
        median_lead_minutes REAL NOT NULL DEFAULT 0,
        average_price_move_after_entry REAL NOT NULL DEFAULT 0,
        median_price_move_after_entry REAL NOT NULL DEFAULT 0,

        consensus_participation_rate REAL NOT NULL DEFAULT 0,
        consensus_lead_rate REAL NOT NULL DEFAULT 0,
        signal_success_rate REAL NOT NULL DEFAULT 0,

        influence_score REAL NOT NULL DEFAULT 0,
        confidence_score REAL NOT NULL DEFAULT 0,

        calculated_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,

        FOREIGN KEY (wallet)
            REFERENCES wallet_intelligence_profiles(wallet)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wallet_intelligence_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        wallet TEXT NOT NULL,
        category TEXT,

        overall_rank INTEGER,
        overall_score REAL NOT NULL DEFAULT 0,
        overall_grade TEXT NOT NULL DEFAULT 'UNRATED',
        category_rank INTEGER,
        category_score REAL,
        category_grade TEXT,

        confidence_score REAL NOT NULL DEFAULT 0,
        win_rate REAL NOT NULL DEFAULT 0,
        roi REAL NOT NULL DEFAULT 0,
        total_pnl REAL NOT NULL DEFAULT 0,

        timing_score REAL NOT NULL DEFAULT 0,
        conviction_score REAL NOT NULL DEFAULT 0,
        consistency_score REAL NOT NULL DEFAULT 0,
        risk_score REAL NOT NULL DEFAULT 0,
        influence_score REAL NOT NULL DEFAULT 0,
        recent_form_score REAL NOT NULL DEFAULT 0,

        metrics_json TEXT,
        snapshot_at TEXT NOT NULL,

        FOREIGN KEY (wallet)
            REFERENCES wallet_intelligence_profiles(wallet)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wallet_intelligence_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        source_rows INTEGER NOT NULL DEFAULT 0,
        wallets_seen INTEGER NOT NULL DEFAULT 0,
        wallets_profiled INTEGER NOT NULL DEFAULT 0,
        category_records INTEGER NOT NULL DEFAULT 0,
        snapshots_written INTEGER NOT NULL DEFAULT 0,
        configuration_json TEXT,
        diagnostics_json TEXT,
        error_message TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_category_classifications (
        market_id TEXT PRIMARY KEY,
        title TEXT,
        primary_category TEXT NOT NULL DEFAULT 'uncategorized',
        secondary_category TEXT,
        sport TEXT,
        league TEXT,
        event_type TEXT,
        classification_confidence REAL NOT NULL DEFAULT 0,
        classification_method TEXT,
        classified_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_wallet_profiles_rank ON wallet_intelligence_profiles(current_rank)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_profiles_score ON wallet_intelligence_profiles(overall_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_profiles_grade ON wallet_intelligence_profiles(overall_grade)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_profiles_last_seen ON wallet_intelligence_profiles(last_seen_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_category_category_score ON wallet_category_performance(category, category_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_category_wallet ON wallet_category_performance(wallet)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_wallet_time ON wallet_intelligence_snapshots(wallet, snapshot_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_category_time ON wallet_intelligence_snapshots(category, snapshot_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_run ON wallet_intelligence_snapshots(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_runs_started ON wallet_intelligence_runs(started_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_market_categories_category ON market_category_classifications(primary_category)",
    "CREATE INDEX IF NOT EXISTS idx_market_categories_sport ON market_category_classifications(sport)",
]


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def verify_integrity(connection: sqlite3.Connection) -> str:
    result = connection.execute("PRAGMA integrity_check").fetchone()
    return str(result[0]) if result else "unknown"


def seed_wallet_profiles(connection: sqlite3.Connection) -> int:
    if not table_exists(connection, "positions"):
        return 0

    columns = table_columns(connection, "positions")
    if "wallet" not in columns:
        return 0

    scanned_expression = "NULL"
    if "scan_id" in columns and table_exists(connection, "wallet_scans"):
        scan_columns = table_columns(connection, "wallet_scans")
        if {"id", "scanned_at"}.issubset(scan_columns):
            scanned_expression = "ws.scanned_at"

    if scanned_expression != "NULL":
        rows = connection.execute(
            """
            SELECT
                p.wallet,
                MIN(ws.scanned_at) AS first_seen,
                MAX(ws.scanned_at) AS last_seen,
                COUNT(*) AS positions_count,
                SUM(COALESCE(p.current_value, 0)) AS current_value,
                SUM(COALESCE(p.cash_pnl, 0)) AS cash_pnl
            FROM positions p
            LEFT JOIN wallet_scans ws ON ws.id = p.scan_id
            WHERE p.wallet IS NOT NULL
              AND TRIM(p.wallet) <> ''
            GROUP BY p.wallet
            """
        ).fetchall()
    else:
        value_expr = "COALESCE(current_value, 0)" if "current_value" in columns else "0"
        pnl_expr = "COALESCE(cash_pnl, 0)" if "cash_pnl" in columns else "0"
        rows = connection.execute(
            f"""
            SELECT
                wallet,
                NULL AS first_seen,
                NULL AS last_seen,
                COUNT(*) AS positions_count,
                SUM({value_expr}) AS current_value,
                SUM({pnl_expr}) AS cash_pnl
            FROM positions
            WHERE wallet IS NOT NULL
              AND TRIM(wallet) <> ''
            GROUP BY wallet
            """
        ).fetchall()

    now = utc_now()
    inserted = 0

    for row in rows:
        wallet = str(row[0]).strip()
        first_seen = row[1] or now
        last_seen = row[2] or now
        positions_count = int(row[3] or 0)
        current_value = float(row[4] or 0)
        cash_pnl = float(row[5] or 0)

        cursor = connection.execute(
            """
            INSERT INTO wallet_intelligence_profiles (
                wallet,
                first_seen_at,
                last_seen_at,
                markets_tracked,
                unrealized_pnl,
                total_pnl,
                average_position_value,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                first_seen_at = CASE
                    WHEN wallet_intelligence_profiles.first_seen_at IS NULL
                    THEN excluded.first_seen_at
                    ELSE wallet_intelligence_profiles.first_seen_at
                END,
                last_seen_at = CASE
                    WHEN excluded.last_seen_at > wallet_intelligence_profiles.last_seen_at
                    THEN excluded.last_seen_at
                    ELSE wallet_intelligence_profiles.last_seen_at
                END,
                markets_tracked = CASE
                    WHEN excluded.markets_tracked > wallet_intelligence_profiles.markets_tracked
                    THEN excluded.markets_tracked
                    ELSE wallet_intelligence_profiles.markets_tracked
                END,
                unrealized_pnl = excluded.unrealized_pnl,
                total_pnl = excluded.total_pnl,
                average_position_value = excluded.average_position_value,
                updated_at = excluded.updated_at
            """,
            (
                wallet,
                first_seen,
                last_seen,
                positions_count,
                cash_pnl,
                cash_pnl,
                current_value / positions_count if positions_count else 0,
                now,
                now,
            ),
        )
        if cursor.rowcount:
            inserted += 1

    return inserted


def schema_summary(connection: sqlite3.Connection) -> dict:
    required_tables = [
        "wallet_intelligence_profiles",
        "wallet_category_performance",
        "wallet_influence_metrics",
        "wallet_intelligence_snapshots",
        "wallet_intelligence_runs",
        "market_category_classifications",
    ]
    counts = {}
    for table in required_tables:
        counts[table] = (
            connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            if table_exists(connection, table)
            else None
        )

    return {
        "migration_id": MIGRATION_ID,
        "database": str(DATABASE_PATH),
        "integrity_check": verify_integrity(connection),
        "tables": counts,
        "foreign_keys_enabled": bool(
            connection.execute("PRAGMA foreign_keys").fetchone()[0]
        ),
        "generated_at": utc_now(),
    }


def install() -> dict:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(DATABASE_PATH))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")

        integrity_before = verify_integrity(connection)
        if integrity_before.lower() != "ok":
            raise RuntimeError(
                f"Database integrity check failed before migration: {integrity_before}"
            )

        with connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)

            for statement in INDEX_STATEMENTS:
                connection.execute(statement)

            seeded = seed_wallet_profiles(connection)

            connection.execute(
                """
                INSERT INTO platform_schema_migrations (
                    migration_id,
                    applied_at,
                    description
                )
                VALUES (?, ?, ?)
                ON CONFLICT(migration_id) DO UPDATE SET
                    applied_at = excluded.applied_at,
                    description = excluded.description
                """,
                (
                    MIGRATION_ID,
                    utc_now(),
                    "Elite Wallet Intelligence normalized database foundation v1",
                ),
            )

        result = schema_summary(connection)
        result["wallet_seed_operations"] = seeded
        result["database_modified"] = True
        result["destructive_changes"] = False

        report_path = REPORT_DIR / "latest_schema_report.json"
        report_path.write_text(
            json.dumps(result, indent=2),
            encoding="utf-8",
        )
        result["report"] = str(report_path)
        return result
    finally:
        connection.close()


def dry_run() -> dict:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(str(DATABASE_PATH))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        return {
            "database": str(DATABASE_PATH),
            "integrity_check": verify_integrity(connection),
            "positions_table_found": table_exists(connection, "positions"),
            "database_modified": False,
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install and verify the Elite Wallet Intelligence schema."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        result = dry_run()
    elif args.verify:
        if not DATABASE_PATH.exists():
            raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
        connection = sqlite3.connect(str(DATABASE_PATH))
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            result = schema_summary(connection)
            result["database_modified"] = False
        finally:
            connection.close()
    else:
        result = install()

    print()
    print("=" * 110)
    print("ELITE WALLET INTELLIGENCE DATABASE")
    print("=" * 110)
    for key, value in result.items():
        if key == "tables":
            print("Tables:")
            for table, count in value.items():
                print(f"  {table:<42} {count}")
        else:
            print(f"{key.replace('_', ' ').title():<30} {value}")
    print("=" * 110)


if __name__ == "__main__":
    main()

'@

$runnerCode = @'
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python .\src\elite_wallet_intelligence_database.py @args
exit $LASTEXITCODE

'@

$manifestCode = @'
{
  "id": "elite_wallet_database",
  "name": "Elite Wallet Intelligence Database",
  "version": "1.0.0",
  "runner": "run_elite_wallet_database.ps1",
  "enabled": true,
  "required": true,
  "stage": "foundation",
  "order": 40,
  "dependencies": [],
  "latest_report": "reports/elite_wallet_database/latest_schema_report.json",
  "timeout_seconds": 300
}
'@

if (Test-Path $enginePath) {
    $engineBackup = "$enginePath.backup.$timestamp"
    Copy-Item $enginePath $engineBackup -Force
    Write-Host "Existing engine backed up:"
    Write-Host $engineBackup
}

Set-Content -Path $enginePath -Value $engineCode -Encoding UTF8
Set-Content -Path $runnerPath -Value $runnerCode -Encoding UTF8
Set-Content -Path $manifestPath -Value $manifestCode -Encoding UTF8

python -m py_compile $enginePath
if ($LASTEXITCODE -ne 0) {
    throw "Compile check failed."
}

Write-Host ""
Write-Host "Database backup created:"
Write-Host $databaseBackup

Write-Host ""
Write-Host "Running pre-install dry run..."
& $runnerPath --dry-run
if ($LASTEXITCODE -ne 0) {
    throw "Pre-install dry run failed."
}

Write-Host ""
Write-Host "Installing Elite Wallet Intelligence schema..."
& $runnerPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "Schema installation failed. Restoring database backup..."
    Copy-Item $databaseBackup $databasePath -Force
    throw "Installation failed and the original database was restored."
}

Write-Host ""
Write-Host "Running post-install verification..."
& $runnerPath --verify
if ($LASTEXITCODE -ne 0) {
    Write-Host "Verification failed. Restoring database backup..."
    Copy-Item $databaseBackup $databasePath -Force
    throw "Verification failed and the original database was restored."
}

Write-Host ""
Write-Host ("=" * 110)
Write-Host "ELITE WALLET INTELLIGENCE DATABASE INSTALLED"
Write-Host ("=" * 110)
Write-Host "Migration engine: $enginePath"
Write-Host "Runner:           $runnerPath"
Write-Host "Manifest:         $manifestPath"
Write-Host "Database backup:  $databaseBackup"
Write-Host "Schema report:    $reportDir\latest_schema_report.json"
Write-Host ""
Write-Host "Run verification:"
Write-Host ".\run_elite_wallet_database.ps1 --verify"
Write-Host ""
Write-Host "Run full platform:"
Write-Host ".\run_platform.ps1"
Write-Host ""
Write-Host "Destructive changes: NO"
Write-Host ("=" * 110)