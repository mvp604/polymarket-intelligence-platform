from __future__ import annotations

import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
MIGRATION_PATH = (
    PROJECT_ROOT
    / "database"
    / "migrations"
    / "006_elite_wallet_intelligence.sql"
)

REQUIRED_COLUMNS = {
    "wallet",
    "profile_checksum",
    "wallet_score",
    "wallet_grade",
    "elite_status",
    "total_positions",
    "resolved_positions",
    "winning_positions",
    "losing_positions",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "deployed_capital",
    "roi_percent",
    "hit_rate",
    "consistency_score",
    "conviction_score",
    "sizing_discipline_score",
    "specialization_score",
    "activity_score",
    "data_quality_score",
    "primary_category",
    "category_count",
    "average_position_value",
    "largest_position_value",
    "model_version",
    "first_profiled_at",
    "last_profiled_at",
    "last_run_id",
    "evidence_json",
}


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    }


def safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe identifier: {value}")
    return value


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1
    if not MIGRATION_PATH.exists():
        print(f"ERROR: Migration not found: {MIGRATION_PATH}", file=sys.stderr)
        return 1

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        existing = (
            columns(connection, "elite_wallet_profiles")
            if table_exists(connection, "elite_wallet_profiles")
            else set()
        )
        missing = REQUIRED_COLUMNS - existing

        if not existing:
            print("No partial elite wallet table found. Repair not required.")
            return 0

        if not missing:
            print("Elite wallet schema already has the required columns.")
            return 0

        suffix = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        legacy_name = safe_identifier(f"elite_wallet_profiles_legacy_{suffix}")

        print("Partial/incompatible elite wallet schema detected.")
        print(f"Missing columns: {', '.join(sorted(missing))}")
        print(f"Preserving old table as: {legacy_name}")

        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                f'ALTER TABLE "elite_wallet_profiles" '
                f'RENAME TO "{legacy_name}"'
            )
            connection.execute("DROP VIEW IF EXISTS ranked_elite_wallets")
            connection.execute(
                "DROP VIEW IF EXISTS ranked_elite_wallet_categories"
            )
            connection.execute(
                "DROP TABLE IF EXISTS elite_wallet_profile_history"
            )
            connection.execute(
                "DROP TABLE IF EXISTS elite_wallet_category_profiles"
            )
            if table_exists(connection, "schema_migrations"):
                connection.execute(
                    "DELETE FROM schema_migrations "
                    "WHERE migration_id='006_elite_wallet_intelligence'"
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    print("Repair completed. Run: python src/migration_runner.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
