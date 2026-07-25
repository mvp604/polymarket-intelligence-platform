from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


EVENT_STATUS_PENDING = "PENDING"
EVENT_STATUS_PROCESSING = "PROCESSING"
EVENT_STATUS_PROCESSED = "PROCESSED"
EVENT_STATUS_FAILED = "FAILED"


@dataclass(frozen=True)
class PlatformEvent:
    """
    Immutable event produced by a platform engine.

    Every meaningful change in the platform can be represented as an event.
    """

    event_id: str
    event_type: str
    source_engine: str
    source_version: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    occurred_at: str
    correlation_id: str | None = None
    causation_id: str | None = None
    deduplication_key: str | None = None

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        source_engine: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        source_version: str = "1.0.0",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        deduplication_key: str | None = None,
    ) -> "PlatformEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source_engine=source_engine,
            source_version=source_version,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            payload=payload,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id,
            causation_id=causation_id,
            deduplication_key=deduplication_key,
        )


def create_event_tables(connection: sqlite3.Connection) -> None:
    """
    Create the event-store tables and supporting indexes.

    Safe to run more than once.
    """

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS platform_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,

            source_engine TEXT NOT NULL,
            source_version TEXT NOT NULL,

            aggregate_type TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,

            payload_json TEXT NOT NULL,

            occurred_at TEXT NOT NULL,
            stored_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            correlation_id TEXT,
            causation_id TEXT,

            deduplication_key TEXT UNIQUE,

            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK (
                    status IN (
                        'PENDING',
                        'PROCESSING',
                        'PROCESSED',
                        'FAILED'
                    )
                ),

            processing_attempts INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            processed_at TEXT,
            error_message TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_platform_events_type
            ON platform_events(event_type);

        CREATE INDEX IF NOT EXISTS idx_platform_events_status
            ON platform_events(status);

        CREATE INDEX IF NOT EXISTS idx_platform_events_occurred
            ON platform_events(occurred_at);

        CREATE INDEX IF NOT EXISTS idx_platform_events_aggregate
            ON platform_events(
                aggregate_type,
                aggregate_id
            );

        CREATE INDEX IF NOT EXISTS idx_platform_events_source
            ON platform_events(
                source_engine,
                occurred_at
            );

        CREATE INDEX IF NOT EXISTS idx_platform_events_correlation
            ON platform_events(correlation_id);

        CREATE TABLE IF NOT EXISTS event_consumers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            consumer_name TEXT NOT NULL UNIQUE,
            description TEXT,

            is_enabled INTEGER NOT NULL DEFAULT 1,

            last_processed_event_row_id INTEGER NOT NULL DEFAULT 0,
            last_run_at TEXT,
            last_success_at TEXT,
            last_error TEXT,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS event_consumer_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            consumer_name TEXT NOT NULL,
            event_id TEXT NOT NULL,
            event_type TEXT NOT NULL,

            attempt_number INTEGER NOT NULL,
            error_message TEXT NOT NULL,

            failed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,

            UNIQUE (
                consumer_name,
                event_id,
                attempt_number
            )
        );

        CREATE INDEX IF NOT EXISTS idx_event_consumer_failures_open
            ON event_consumer_failures(
                consumer_name,
                resolved_at
            );
        """
    )

    connection.commit()


def build_deduplication_key(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    state_value: Any,
) -> str:
    """
    Produce a deterministic key for an event representing a particular state.

    The same event state will always produce the same key.
    """

    canonical_value = json.dumps(
        state_value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    raw_key = "|".join(
        [
            event_type,
            aggregate_type,
            str(aggregate_id),
            canonical_value,
        ]
    )

    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def publish_event(
    connection: sqlite3.Connection,
    event: PlatformEvent,
) -> bool:
    """
    Store an event.

    Returns:
        True when a new event was inserted.
        False when its deduplication key already exists.
    """

    create_event_tables(connection)

    try:
        connection.execute(
            """
            INSERT INTO platform_events (
                event_id,
                event_type,
                source_engine,
                source_version,
                aggregate_type,
                aggregate_id,
                payload_json,
                occurred_at,
                correlation_id,
                causation_id,
                deduplication_key,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.source_engine,
                event.source_version,
                event.aggregate_type,
                event.aggregate_id,
                json.dumps(
                    event.payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
                event.occurred_at,
                event.correlation_id,
                event.causation_id,
                event.deduplication_key,
                EVENT_STATUS_PENDING,
            ),
        )

        connection.commit()
        return True

    except sqlite3.IntegrityError as error:
        error_text = str(error).lower()

        if (
            "deduplication_key" in error_text
            or "platform_events.event_id" in error_text
        ):
            connection.rollback()
            return False

        connection.rollback()
        raise


def publish_events(
    connection: sqlite3.Connection,
    events: Iterable[PlatformEvent],
) -> tuple[int, int]:
    """
    Publish multiple events.

    Returns:
        (inserted_count, duplicate_count)
    """

    inserted_count = 0
    duplicate_count = 0

    for event in events:
        inserted = publish_event(connection, event)

        if inserted:
            inserted_count += 1
        else:
            duplicate_count += 1

    return inserted_count, duplicate_count


def get_pending_events(
    connection: sqlite3.Connection,
    *,
    event_types: list[str] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Read pending events in chronological order.
    """

    connection.row_factory = sqlite3.Row

    parameters: list[Any] = []
    event_filter = ""

    if event_types:
        placeholders = ",".join("?" for _ in event_types)
        event_filter = f"AND event_type IN ({placeholders})"
        parameters.extend(event_types)

    parameters.append(limit)

    rows = connection.execute(
        f"""
        SELECT
            id,
            event_id,
            event_type,
            source_engine,
            source_version,
            aggregate_type,
            aggregate_id,
            payload_json,
            occurred_at,
            stored_at,
            correlation_id,
            causation_id,
            deduplication_key,
            status,
            processing_attempts,
            last_attempt_at,
            processed_at,
            error_message
        FROM platform_events
        WHERE status IN ('PENDING', 'FAILED')
        {event_filter}
        ORDER BY id ASC
        LIMIT ?
        """,
        parameters,
    ).fetchall()

    results: list[dict[str, Any]] = []

    for row in rows:
        event_record = dict(row)
        event_record["payload"] = json.loads(
            event_record.pop("payload_json")
        )
        results.append(event_record)

    return results


def mark_event_processing(
    connection: sqlite3.Connection,
    event_id: str,
) -> None:
    connection.execute(
        """
        UPDATE platform_events
        SET
            status = ?,
            processing_attempts = processing_attempts + 1,
            last_attempt_at = CURRENT_TIMESTAMP,
            error_message = NULL
        WHERE event_id = ?
        """,
        (
            EVENT_STATUS_PROCESSING,
            event_id,
        ),
    )

    connection.commit()


def mark_event_processed(
    connection: sqlite3.Connection,
    event_id: str,
) -> None:
    connection.execute(
        """
        UPDATE platform_events
        SET
            status = ?,
            processed_at = CURRENT_TIMESTAMP,
            error_message = NULL
        WHERE event_id = ?
        """,
        (
            EVENT_STATUS_PROCESSED,
            event_id,
        ),
    )

    connection.commit()


def mark_event_failed(
    connection: sqlite3.Connection,
    event_id: str,
    error_message: str,
) -> None:
    connection.execute(
        """
        UPDATE platform_events
        SET
            status = ?,
            error_message = ?
        WHERE event_id = ?
        """,
        (
            EVENT_STATUS_FAILED,
            error_message[:4000],
            event_id,
        ),
    )

    connection.commit()


def register_consumer(
    connection: sqlite3.Connection,
    *,
    consumer_name: str,
    description: str | None = None,
) -> None:
    create_event_tables(connection)

    connection.execute(
        """
        INSERT INTO event_consumers (
            consumer_name,
            description
        )
        VALUES (?, ?)
        ON CONFLICT(consumer_name) DO UPDATE SET
            description = COALESCE(
                excluded.description,
                event_consumers.description
            ),
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            consumer_name,
            description,
        ),
    )

    connection.commit()


def event_to_dict(event: PlatformEvent) -> dict[str, Any]:
    return asdict(event)