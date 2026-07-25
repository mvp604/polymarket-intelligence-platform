from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

REQUIRED_TABLES = (
    "opportunity_enrichment_runs",
    "opportunity_enrichment_current",
    "opportunity_enrichment_history",
)
REQUIRED_VIEWS = ("ranked_opportunity_enrichment",)


def exists(connection: sqlite3.Connection, kind: str, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type=? AND name=?",
        (kind, name),
    ).fetchone() is not None


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    healthy = True
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        print("=" * 80)
        print("OPPORTUNITY ENRICHMENT HEALTH")
        print("=" * 80)

        for table in REQUIRED_TABLES:
            ok = exists(connection, "table", table)
            healthy &= ok
            print(f"{table:<45} {'OK' if ok else 'MISSING'}")

        for view in REQUIRED_VIEWS:
            ok = exists(connection, "view", view)
            healthy &= ok
            print(f"{view:<45} {'OK' if ok else 'MISSING'}")

        if exists(connection, "table", "opportunity_enrichment_current"):
            total = connection.execute(
                "SELECT COUNT(*) FROM opportunity_enrichment_current"
            ).fetchone()[0]
            history = connection.execute(
                "SELECT COUNT(*) FROM opportunity_enrichment_history"
            ).fetchone()[0]
            duplicates = connection.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT opportunity_id, enrichment_checksum, COUNT(*) n
                    FROM opportunity_enrichment_history
                    GROUP BY opportunity_id, enrichment_checksum
                    HAVING n > 1
                )
                """
            ).fetchone()[0]
            avg_complete = connection.execute(
                """
                SELECT AVG(data_completeness_score)
                FROM opportunity_enrichment_current
                """
            ).fetchone()[0] or 0
            capitalized = connection.execute(
                """
                SELECT COUNT(*)
                FROM opportunity_enrichment_current
                WHERE combined_capital > 0
                """
            ).fetchone()[0]

            print(f"{'Current enrichments':<45} {total:,}")
            print(f"{'Historical enrichments':<45} {history:,}")
            print(f"{'Duplicate enrichment states':<45} {duplicates:,}")
            print(f"{'Average completeness':<45} {avg_complete:.2f}")
            print(f"{'Rows with capital data':<45} {capitalized:,}")
            healthy &= duplicates == 0

        pending = connection.execute(
            """
            SELECT COUNT(*)
            FROM platform_events
            WHERE event_type='OpportunityEnriched'
              AND status IN ('PENDING', 'FAILED')
            """
        ).fetchone()[0]
        print(f"{'Pending enrichment events':<45} {pending:,}")

        latest = None
        if exists(connection, "table", "opportunity_enrichment_runs"):
            latest = connection.execute(
                """
                SELECT *
                FROM opportunity_enrichment_runs
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()
        if latest:
            print("-" * 80)
            print(f"{'Latest run status':<45} {latest['status']}")
            print(f"{'Opportunities read':<45} {latest['opportunities_read']:,}")
            print(f"{'Created':<45} {latest['enrichments_created']:,}")
            print(f"{'Updated':<45} {latest['enrichments_updated']:,}")
            print(f"{'Events published':<45} {latest['events_published']:,}")
            print(f"{'Error':<45} {latest['error_message'] or 'NONE'}")
            healthy &= latest["status"] == "SUCCESS"

    print("=" * 80)
    print(f"OVERALL STATUS: {'HEALTHY' if healthy else 'ATTENTION REQUIRED'}")
    print("=" * 80)
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
