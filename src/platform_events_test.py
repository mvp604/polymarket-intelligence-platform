from __future__ import annotations

import sqlite3

try:
    from database import DATABASE_PATH
except ImportError:
    DATABASE_PATH = "database/polymarket.db"

from event_types import OPPORTUNITY_CREATED
from platform_events import (
    PlatformEvent,
    build_deduplication_key,
    create_event_tables,
    get_pending_events,
    mark_event_processed,
    publish_event,
)


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)

    create_event_tables(connection)

    deduplication_key = build_deduplication_key(
        event_type=OPPORTUNITY_CREATED,
        aggregate_type="opportunity",
        aggregate_id="verification-opportunity-001",
        state_value={
            "score": 84,
            "outcome": "YES",
            "market_id": "verification-market-001",
        },
    )

    event = PlatformEvent.create(
        event_type=OPPORTUNITY_CREATED,
        source_engine="platform_events_test",
        source_version="1.0.0",
        aggregate_type="opportunity",
        aggregate_id="verification-opportunity-001",
        payload={
            "market_id": "verification-market-001",
            "title": "Platform Event Verification",
            "outcome": "YES",
            "score": 84,
            "confidence_grade": "HIGH",
        },
        deduplication_key=deduplication_key,
    )

    first_insert = publish_event(connection, event)

    duplicate_event = PlatformEvent.create(
        event_type=OPPORTUNITY_CREATED,
        source_engine="platform_events_test",
        source_version="1.0.0",
        aggregate_type="opportunity",
        aggregate_id="verification-opportunity-001",
        payload=event.payload,
        deduplication_key=deduplication_key,
    )

    second_insert = publish_event(
        connection,
        duplicate_event,
    )

    pending_events = get_pending_events(
        connection,
        event_types=[OPPORTUNITY_CREATED],
        limit=10,
    )

    print()
    print("=" * 70)
    print("PLATFORM EVENT FOUNDATION VERIFICATION")
    print("=" * 70)
    print(f"Database: {DATABASE_PATH}")
    print(f"First insert accepted: {first_insert}")
    print(f"Duplicate insert accepted: {second_insert}")
    print(f"Matching pending events: {len(pending_events)}")

    if pending_events:
        event_record = pending_events[0]

        print()
        print("Latest pending event:")
        print(f"  Event ID: {event_record['event_id']}")
        print(f"  Type: {event_record['event_type']}")
        print(f"  Source: {event_record['source_engine']}")
        print(f"  Aggregate: {event_record['aggregate_type']}")
        print(f"  Aggregate ID: {event_record['aggregate_id']}")
        print(f"  Payload: {event_record['payload']}")

        mark_event_processed(
            connection,
            event_record["event_id"],
        )

        print()
        print("Event marked as processed.")

    print()
    print("Expected:")
    print("  First insert accepted: True")
    print("  Duplicate insert accepted: False")
    print("  Matching pending events: 1")
    print("=" * 70)

    connection.close()


if __name__ == "__main__":
    main()