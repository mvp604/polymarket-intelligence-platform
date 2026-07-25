from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

OBJECTS = {
    "table": (
        "smart_money_market_signals",
        "smart_money_signal_history",
    ),
    "view": (
        "ranked_smart_money_signals",
        "smart_money_disagreement_board",
        "smart_money_signal_trends",
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
        print("=" * 92)
        print("SMART MONEY INTELLIGENCE v1 HEALTH")
        print("=" * 92)

        for kind, names in OBJECTS.items():
            for name in names:
                healthy = exists(connection, kind, name)
                failures += int(not healthy)
                print(f"{name:<58} {'OK' if healthy else 'MISSING'}")

        if exists(connection, "table", "smart_money_market_signals"):
            row = connection.execute(
                """
                SELECT COUNT(*) total,
                       SUM(CASE WHEN signal_status='STRONG_ELITE_CONSENSUS' THEN 1 ELSE 0 END) strong_consensus,
                       SUM(CASE WHEN signal_status='ELITE_DISAGREEMENT' THEN 1 ELSE 0 END) disagreement,
                       AVG(heat_score) average_heat,
                       MAX(heat_score) maximum_heat
                FROM smart_money_market_signals
                """
            ).fetchone()
            print("-" * 92)
            print(f"{'Signals':<58} {int(row['total'] or 0):,}")
            print(f"{'Strong elite consensus':<58} {int(row['strong_consensus'] or 0):,}")
            print(f"{'Elite disagreement':<58} {int(row['disagreement'] or 0):,}")
            print(f"{'Average heat score':<58} {float(row['average_heat'] or 0):.2f}")
            print(f"{'Maximum heat score':<58} {float(row['maximum_heat'] or 0):.2f}")

        print("=" * 92)
        print("OVERALL STATUS: " + ("HEALTHY" if failures == 0 else "ATTENTION REQUIRED"))
        print("=" * 92)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
