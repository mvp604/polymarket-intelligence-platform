from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


def exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        if not exists(connection, "platform_events"):
            print("platform_events table is missing.", file=sys.stderr)
            return 1

        totals = connection.execute(
            """
            SELECT event_type, status, COUNT(*) AS total
            FROM platform_events
            GROUP BY event_type, status
            ORDER BY event_type, status
            """
        ).fetchall()

        consumers = []
        if exists(connection, "event_consumers"):
            consumers = connection.execute(
                """
                SELECT consumer_name, enabled, last_run_at,
                       last_successful_run_at, last_error
                FROM event_consumers
                ORDER BY consumer_name
                """
            ).fetchall()

        print("=" * 92)
        print("EVENT BUS INSPECTOR")
        print("=" * 92)
        print(f"{'EVENT TYPE':<38} {'STATUS':<15} {'COUNT':>12}")
        print("-" * 92)
        for row in totals:
            print(
                f"{row['event_type']:<38} "
                f"{row['status']:<15} "
                f"{row['total']:>12,}"
            )

        print()
        print("CONSUMERS")
        print("-" * 92)
        if not consumers:
            print("No registered consumers found.")
        for row in consumers:
            state = "ENABLED" if row["enabled"] else "DISABLED"
            print(
                f"{row['consumer_name']:<38} {state:<10} "
                f"last success: {row['last_successful_run_at'] or 'NEVER'} "
                f"error: {row['last_error'] or 'NONE'}"
            )
        print("=" * 92)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
