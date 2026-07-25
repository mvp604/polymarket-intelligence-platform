from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

HEALTH_MODULES = (
    "src.elite_wallet_intelligence_health",
    "src.opportunity_enrichment_health",
    "src.institutional_review_health",
)


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    failures = 0
    with sqlite3.connect(DATABASE_PATH) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        pending_events = 0
        failed_events = 0
        if table_exists(connection, "platform_events"):
            pending_events = connection.execute(
                "SELECT COUNT(*) FROM platform_events WHERE status='PENDING'"
            ).fetchone()[0]
            failed_events = connection.execute(
                "SELECT COUNT(*) FROM platform_events WHERE status='FAILED'"
            ).fetchone()[0]

        migrations = 0
        if table_exists(connection, "schema_migrations"):
            migrations = connection.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE status='SUCCESS'"
            ).fetchone()[0]

    print("=" * 80)
    print("POLYMARKET INTELLIGENCE PLATFORM HEALTH")
    print("=" * 80)
    print(f"{'Database integrity':<45} {integrity}")
    print(f"{'Applied migrations':<45} {migrations:,}")
    print(f"{'Pending platform events':<45} {pending_events:,}")
    print(f"{'Failed platform events':<45} {failed_events:,}")
    print("-" * 80)

    if integrity != "ok" or failed_events:
        failures += 1

    for module in HEALTH_MODULES:
        result = subprocess.run(
            [sys.executable, "-m", module],
            cwd=PROJECT_ROOT,
            check=False,
        )
        failures += int(result.returncode != 0)

    print("=" * 80)
    print(
        "OVERALL STATUS: "
        + ("HEALTHY" if failures == 0 else "ATTENTION REQUIRED")
    )
    print("=" * 80)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
