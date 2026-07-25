from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
CONSUMER_NAME = "institutional_review_engine_v1"

REQUIRED_TABLES = (
    "institutional_review_runs",
    "institutional_reviews",
    "event_consumer_receipts",
    "platform_events",
    "event_consumers",
)
REQUIRED_VIEWS = (
    "current_institutional_reviews",
    "ranked_institutional_reviews",
)


def exists(
    connection: sqlite3.Connection,
    object_type: str,
    name: str,
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type=? AND name=?",
            (object_type, name),
        ).fetchone()
        is not None
    )


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    healthy = True

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        print("=" * 78)
        print("INSTITUTIONAL REVIEW HEALTH")
        print("=" * 78)

        for table in REQUIRED_TABLES:
            ok = exists(connection, "table", table)
            healthy &= ok
            print(f"{table:<40} {'OK' if ok else 'MISSING'}")

        for view in REQUIRED_VIEWS:
            ok = exists(connection, "view", view)
            healthy &= ok
            print(f"{view:<40} {'OK' if ok else 'MISSING'}")

        if exists(connection, "table", "institutional_reviews"):
            total = connection.execute(
                "SELECT COUNT(*) FROM institutional_reviews"
            ).fetchone()[0]
            current = connection.execute(
                "SELECT COUNT(*) FROM current_institutional_reviews"
            ).fetchone()[0]
            duplicates = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT
                        opportunity_id,
                        source_state_checksum,
                        model_version,
                        COUNT(*) AS total
                    FROM institutional_reviews
                    GROUP BY
                        opportunity_id,
                        source_state_checksum,
                        model_version
                    HAVING total > 1
                )
                """
            ).fetchone()[0]

            print(f"{'Total immutable reviews':<40} {total:,}")
            print(f"{'Current opportunity reviews':<40} {current:,}")
            print(f"{'Duplicate review states':<40} {duplicates:,}")
            healthy &= duplicates == 0

        consumer = connection.execute(
            """
            SELECT
                is_enabled, last_run_at, last_success_at, last_error
            FROM event_consumers
            WHERE consumer_name=?
            """,
            (CONSUMER_NAME,),
        ).fetchone()

        print(
            f"{'Consumer registered':<40} "
            f"{'YES' if consumer else 'NO'}"
        )
        healthy &= consumer is not None

        if consumer:
            print(f"{'Consumer enabled':<40} {bool(consumer['is_enabled'])}")
            print(f"{'Last run':<40} {consumer['last_run_at'] or 'NEVER'}")
            print(
                f"{'Last successful run':<40} "
                f"{consumer['last_success_at'] or 'NEVER'}"
            )
            print(
                f"{'Last error':<40} "
                f"{consumer['last_error'] or 'NONE'}"
            )
            healthy &= bool(consumer["is_enabled"])
            healthy &= consumer["last_error"] in (None, "")

        pending = connection.execute(
            """
            SELECT COUNT(*)
            FROM platform_events AS e
            LEFT JOIN event_consumer_receipts AS r
              ON r.event_id=e.event_id
             AND r.consumer_name=?
            WHERE e.event_type IN (
                'OpportunityCreated',
                'OpportunityUpdated'
            )
              AND r.id IS NULL
            """,
            (CONSUMER_NAME,),
        ).fetchone()[0]
        print(f"{'Unreviewed opportunity events':<40} {pending:,}")

        decisions = []

        if exists(
            connection,
            "view",
            "current_institutional_reviews",
        ):
            decisions = connection.execute(
                """
                SELECT institutional_decision, COUNT(*) AS total
                FROM current_institutional_reviews
                GROUP BY institutional_decision
                ORDER BY institutional_decision
                """
            ).fetchall()

        if decisions:
            print("-" * 78)
            print("CURRENT DECISIONS")
            for row in decisions:
                print(
                    f"{row['institutional_decision']:<40} "
                    f"{row['total']:,}"
                )

        latest_run = connection.execute(
            """
            SELECT *
            FROM institutional_review_runs
            ORDER BY started_at DESC
            LIMIT 1
            """
        ).fetchone()

        if latest_run:
            print("-" * 78)
            print("LATEST RUN")
            for key in (
                "run_id",
                "status",
                "source_events_read",
                "reviews_created",
                "reviews_skipped",
                "events_published",
                "error_message",
            ):
                value = latest_run[key]
                if key == "error_message" and value:
                    try:
                        value = json.loads(value)
                    except (TypeError, json.JSONDecodeError):
                        pass
                print(f"{key:<40} {value}")

    print("=" * 78)
    print(f"OVERALL STATUS: {'HEALTHY' if healthy else 'ATTENTION REQUIRED'}")
    print("=" * 78)
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
