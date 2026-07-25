from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

OBJECTS = {
    "table": (
        "market_resolutions",
        "resolved_signal_results",
        "daily_intelligence_reports",
    ),
    "view": (
        "resolved_signal_performance",
        "daily_signal_performance",
        "signal_grade_performance",
        "category_signal_performance",
    ),
}


def exists(connection: sqlite3.Connection, kind: str, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type=? AND name=?",
        (kind, name),
    ).fetchone() is not None


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    failures = 0
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        print("=" * 96)
        print("OUTCOME RESOLUTION & EOD REPORTING v1 HEALTH")
        print("=" * 96)

        for kind, names in OBJECTS.items():
            for name in names:
                healthy = exists(connection, kind, name)
                failures += int(not healthy)
                print(f"{name:<62} {'OK' if healthy else 'MISSING'}")

        if exists(connection, "table", "resolved_signal_results"):
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) AS hits,
                    SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) AS misses,
                    AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) AS hit_rate
                FROM resolved_signal_results
                """
            ).fetchone()
            print("-" * 96)
            print(f"{'Resolved signal results':<62} {int(row['total'] or 0):,}")
            print(f"{'Hits':<62} {int(row['hits'] or 0):,}")
            print(f"{'Misses':<62} {int(row['misses'] or 0):,}")
            rate = float(row["hit_rate"] or 0) * 100
            print(f"{'Actionable hit rate':<62} {rate:.2f}%")

        print("=" * 96)
        print("OVERALL STATUS: " + ("HEALTHY" if failures == 0 else "ATTENTION REQUIRED"))
        print("=" * 96)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
