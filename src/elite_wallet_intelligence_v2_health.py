from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

REQUIRED_TABLES = (
    "elite_wallet_profiles",
    "elite_wallet_profile_history",
    "elite_wallet_category_profiles",
)
REQUIRED_VIEWS = (
    "ranked_elite_wallets",
    "ranked_elite_wallet_categories",
    "elite_wallet_trends",
)


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
        print("=" * 88)
        print("ELITE WALLET INTELLIGENCE v2 HEALTH")
        print("=" * 88)

        for table in REQUIRED_TABLES:
            healthy = exists(connection, "table", table)
            failures += int(not healthy)
            print(f"{table:<52} {'OK' if healthy else 'MISSING'}")

        for view in REQUIRED_VIEWS:
            healthy = exists(connection, "view", view)
            failures += int(not healthy)
            print(f"{view:<52} {'OK' if healthy else 'MISSING'}")

        if exists(connection, "table", "elite_wallet_profiles"):
            metrics = connection.execute(
                """
                SELECT COUNT(*) total,
                       SUM(CASE WHEN elite_eligible=1 THEN 1 ELSE 0 END) elite,
                       SUM(CASE WHEN consensus_eligible=1 THEN 1 ELSE 0 END) consensus,
                       AVG(confidence_adjusted_score) average_score
                FROM elite_wallet_profiles
                """
            ).fetchone()
            print("-" * 88)
            print(f"{'Profiles':<52} {int(metrics['total'] or 0):,}")
            print(f"{'Elite eligible':<52} {int(metrics['elite'] or 0):,}")
            print(f"{'Consensus eligible':<52} {int(metrics['consensus'] or 0):,}")
            print(f"{'Average confidence-adjusted score':<52} {float(metrics['average_score'] or 0):.2f}")

        print("=" * 88)
        print("OVERALL STATUS: " + ("HEALTHY" if failures == 0 else "ATTENTION REQUIRED"))
        print("=" * 88)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
