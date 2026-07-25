from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.outcome_resolution_schema_v2 import (
    DATABASE_PATH,
    ensure_schema,
    object_exists,
)

OBJECTS = {
    "table": (
        "market_resolutions",
        "resolved_signal_results",
        "daily_intelligence_reports",
    ),
    "view": (
        "resolved_signal_performance",
        "daily_signal_performance",
        "weekly_signal_performance",
        "monthly_signal_performance",
        "signal_grade_performance",
        "category_signal_performance",
    ),
}


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    failures = 0
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        repairs = ensure_schema(connection)
        connection.commit()

        print("=" * 100)
        print("OUTCOME RESOLUTION & REPORTING v2.1 HEALTH")
        print("=" * 100)
        for object_type, names in OBJECTS.items():
            for name in names:
                healthy = object_exists(connection, object_type, name)
                failures += int(not healthy)
                print(f"{name:<68} {'OK' if healthy else 'MISSING'}")

        row = connection.execute(
            """
            SELECT
                COUNT(*) total,
                SUM(CASE WHEN evaluation='HIT' THEN 1 ELSE 0 END) hits,
                SUM(CASE WHEN evaluation='MISS' THEN 1 ELSE 0 END) misses,
                AVG(CASE WHEN evaluation IN ('HIT','MISS') THEN hit_value END) hit_rate
            FROM resolved_signal_results
            """
        ).fetchone()

        print("-" * 100)
        print(f"{'Schema repairs this run':<68} {len(repairs):,}")
        print(f"{'Resolved signal results':<68} {int(row['total'] or 0):,}")
        print(f"{'Hits':<68} {int(row['hits'] or 0):,}")
        print(f"{'Misses':<68} {int(row['misses'] or 0):,}")
        print(
            f"{'Actionable hit rate':<68} "
            f"{float(row['hit_rate'] or 0) * 100:.2f}%"
        )
        print("=" * 100)
        print(
            "OVERALL STATUS: "
            + ("HEALTHY" if failures == 0 else "ATTENTION REQUIRED")
        )
        print("=" * 100)

    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
