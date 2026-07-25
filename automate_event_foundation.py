from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path.cwd()
SRC_DIR = PROJECT_ROOT / "src"
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
BACKUP_DIR = PROJECT_ROOT / "database" / "backups"

EXCLUDED_TABLES = {
    "platform_events",
    "event_consumers",
    "event_consumer_failures",
    "event_consumer_receipts",
    "alert_decisions",
    "sqlite_sequence",
}


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def backup_database() -> Path:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = BACKUP_DIR / f"polymarket_before_event_integration_{timestamp}.db"
    shutil.copy2(DATABASE_PATH, destination)
    return destination


def load_event_module():
    sys.path.insert(0, str(SRC_DIR))
    try:
        from platform_events import create_event_tables
    except ImportError as exc:
        raise RuntimeError(
            "Could not import src/platform_events.py. Run this installer from the project root."
        ) from exc
    return create_event_tables


def find_column(column_names: set[str], aliases: list[str]) -> str | None:
    lowered = {name.lower(): name for name in column_names}
    for alias in aliases:
        if alias.lower() in lowered:
            return lowered[alias.lower()]
    return None


def discover_opportunity_table(connection: sqlite3.Connection):
    tables = [
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        if row["name"] not in EXCLUDED_TABLES
    ]

    candidates = []
    for table in tables:
        columns = connection.execute(
            f"PRAGMA table_info({quote_identifier(table)})"
        ).fetchall()
        names = {row["name"] for row in columns}
        lower_table = table.lower()

        mapping = {
            "id": find_column(names, ["opportunity_id", "id"]),
            "market_id": find_column(names, ["market_id", "condition_id", "token_id"]),
            "title": find_column(names, ["title", "market_title", "question"]),
            "outcome": find_column(names, ["outcome", "side", "position_outcome"]),
            "score": find_column(names, ["opportunity_score", "score", "conviction_score", "confidence_score"]),
            "grade": find_column(names, ["opportunity_grade", "grade", "conviction_grade", "confidence_grade", "tier"]),
            "wallet_count": find_column(names, ["wallet_count", "matching_wallets", "elite_wallet_count"]),
            "combined_value": find_column(names, ["combined_value", "total_value", "capital", "capital_value"]),
        }

        score = 0
        if "opportunit" in lower_table:
            score += 8
        if mapping["market_id"]:
            score += 4
        if mapping["score"]:
            score += 4
        if mapping["outcome"]:
            score += 2
        if mapping["grade"]:
            score += 2
        if mapping["title"]:
            score += 1
        if mapping["id"]:
            score += 1
        if "history" in lower_table:
            score -= 2
        if "outcome" in lower_table or "evaluation" in lower_table:
            score -= 3

        if score >= 8:
            candidates.append((score, table, mapping))

    if not candidates:
        raise RuntimeError(
            "No production opportunity table could be identified safely. No trigger was installed."
        )

    candidates.sort(key=lambda item: (-item[0], item[1]))
    _, best_table, best_mapping = candidates[0]
    return best_table, best_mapping, [(score, table) for score, table, _ in candidates]


def sql_value(column: str | None, fallback: str = "NULL") -> str:
    return f"NEW.{quote_identifier(column)}" if column else fallback


def install_schema(connection: sqlite3.Connection, create_event_tables) -> None:
    create_event_tables(connection)
    connection.executescript(
        '''
        CREATE TABLE IF NOT EXISTS event_consumer_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consumer_name TEXT NOT NULL,
            event_id TEXT NOT NULL,
            processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            result_json TEXT,
            UNIQUE (consumer_name, event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_event_consumer_receipts_event
            ON event_consumer_receipts(event_id);

        CREATE TABLE IF NOT EXISTS alert_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            opportunity_id TEXT NOT NULL,
            market_id TEXT,
            decision TEXT NOT NULL CHECK (decision IN ('HOLD', 'DASHBOARD', 'ALERT_REVIEW')),
            score REAL,
            grade TEXT,
            rationale TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIEW IF NOT EXISTS platform_event_health AS
        SELECT
            COUNT(*) AS total_events,
            SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending_events,
            SUM(CASE WHEN status = 'PROCESSING' THEN 1 ELSE 0 END) AS processing_events,
            SUM(CASE WHEN status = 'PROCESSED' THEN 1 ELSE 0 END) AS processed_events,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_events,
            MAX(occurred_at) AS latest_event_at
        FROM platform_events;
        '''
    )
    connection.commit()


def install_trigger(connection, table, mapping):
    trigger_name = f"trg_{table}_publish_opportunity_created"
    q_trigger = quote_identifier(trigger_name)
    q_table = quote_identifier(table)
    aggregate_expr = (
        f"CAST({sql_value(mapping['id'])} AS TEXT)"
        if mapping["id"]
        else "CAST(NEW.rowid AS TEXT)"
    )

    trigger_sql = f'''
    CREATE TRIGGER {q_trigger}
    AFTER INSERT ON {q_table}
    BEGIN
        INSERT OR IGNORE INTO platform_events (
            event_id, event_type, source_engine, source_version,
            aggregate_type, aggregate_id, payload_json, occurred_at,
            correlation_id, causation_id, deduplication_key, status
        )
        VALUES (
            lower(hex(randomblob(4))) || '-' ||
            lower(hex(randomblob(2))) || '-' ||
            '4' || substr(lower(hex(randomblob(2))), 2) || '-' ||
            substr('89ab', abs(random()) % 4 + 1, 1) ||
            substr(lower(hex(randomblob(2))), 2) || '-' ||
            lower(hex(randomblob(6))),
            'OpportunityCreated',
            'sqlite_opportunity_trigger',
            '1.0.0',
            'opportunity',
            {aggregate_expr},
            json_object(
                'opportunity_id', {aggregate_expr},
                'market_id', {sql_value(mapping['market_id'])},
                'title', {sql_value(mapping['title'])},
                'outcome', {sql_value(mapping['outcome'])},
                'score', {sql_value(mapping['score'])},
                'grade', {sql_value(mapping['grade'])},
                'wallet_count', {sql_value(mapping['wallet_count'])},
                'combined_value', {sql_value(mapping['combined_value'])},
                'source_table', {json.dumps(table)}
            ),
            strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            NULL,
            NULL,
            'OpportunityCreated:' || {json.dumps(table)} || ':' || {aggregate_expr},
            'PENDING'
        );
    END;
    '''

    connection.execute(f"DROP TRIGGER IF EXISTS {q_trigger}")
    connection.executescript(trigger_sql)
    connection.commit()
    return trigger_name


def write_consumer() -> Path:
    path = SRC_DIR / "process_platform_events.py"
    content = r'''from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DATABASE_PATH = Path("database") / "polymarket.db"
CONSUMER_NAME = "alert_decision_service_v1"


def decision_for(payload: dict) -> tuple[str, str]:
    raw_score = payload.get("score")
    try:
        score = float(raw_score) if raw_score is not None else None
    except (TypeError, ValueError):
        score = None

    grade = str(payload.get("grade") or payload.get("confidence_grade") or "").strip().upper()

    if (score is not None and score >= 85) or grade in {"S+", "S", "HIGH", "ELITE", "A+"}:
        return "ALERT_REVIEW", "High score or elite grade; operator review required before external alerting."
    if (score is not None and score >= 75) or grade in {"A", "B+", "MEDIUM"}:
        return "DASHBOARD", "Meets dashboard threshold but not the external-alert review threshold."
    return "HOLD", "Evidence is below the current dashboard and alert-review thresholds."


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        INSERT INTO event_consumers (consumer_name, description)
        VALUES (?, ?)
        ON CONFLICT(consumer_name) DO UPDATE SET
            description = excluded.description,
            updated_at = CURRENT_TIMESTAMP
        """,
        (CONSUMER_NAME, "Classifies OpportunityCreated events without sending external alerts."),
    )

    events = connection.execute(
        """
        SELECT e.event_id, e.aggregate_id, e.payload_json
        FROM platform_events AS e
        LEFT JOIN event_consumer_receipts AS r
          ON r.event_id = e.event_id
         AND r.consumer_name = ?
        WHERE e.event_type = 'OpportunityCreated'
          AND r.id IS NULL
        ORDER BY e.id ASC
        """,
        (CONSUMER_NAME,),
    ).fetchall()

    processed = 0
    for event in events:
        payload = json.loads(event["payload_json"])
        decision, rationale = decision_for(payload)
        score = payload.get("score")
        grade = payload.get("grade") or payload.get("confidence_grade")

        connection.execute(
            """
            INSERT OR IGNORE INTO alert_decisions (
                event_id, opportunity_id, market_id, decision, score, grade, rationale
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                str(payload.get("opportunity_id") or event["aggregate_id"]),
                payload.get("market_id"),
                decision,
                score,
                grade,
                rationale,
            ),
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO event_consumer_receipts (
                consumer_name, event_id, result_json
            ) VALUES (?, ?, ?)
            """,
            (
                CONSUMER_NAME,
                event["event_id"],
                json.dumps({"decision": decision, "rationale": rationale}, sort_keys=True),
            ),
        )

        connection.execute(
            """
            UPDATE platform_events
            SET status='PROCESSED',
                processed_at=COALESCE(processed_at, CURRENT_TIMESTAMP),
                error_message=NULL
            WHERE event_id=?
            """,
            (event["event_id"],),
        )
        processed += 1

    connection.execute(
        """
        UPDATE event_consumers
        SET last_run_at=CURRENT_TIMESTAMP,
            last_success_at=CURRENT_TIMESTAMP,
            last_error=NULL,
            updated_at=CURRENT_TIMESTAMP
        WHERE consumer_name=?
        """,
        (CONSUMER_NAME,),
    )
    connection.commit()

    totals = connection.execute(
        "SELECT decision, COUNT(*) AS total FROM alert_decisions GROUP BY decision ORDER BY decision"
    ).fetchall()

    print("=" * 70)
    print("ALERT DECISION SERVICE")
    print("=" * 70)
    print(f"New events processed: {processed}")
    for row in totals:
        print(f"{row['decision']}: {row['total']}")
    print("=" * 70)
    connection.close()


if __name__ == "__main__":
    main()
'''
    path.write_text(content, encoding="utf-8")
    return path


def write_healthcheck() -> Path:
    path = SRC_DIR / "event_foundation_health.py"
    content = r'''from __future__ import annotations

import sqlite3
from pathlib import Path

DATABASE_PATH = Path("database") / "polymarket.db"


def exists(connection: sqlite3.Connection, object_type: str, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type=? AND name=?",
        (object_type, name),
    ).fetchone() is not None


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    healthy = True

    print("=" * 70)
    print("PLATFORM EVENT FOUNDATION HEALTH")
    print("=" * 70)

    for table in [
        "platform_events",
        "event_consumers",
        "event_consumer_failures",
        "event_consumer_receipts",
        "alert_decisions",
    ]:
        present = exists(connection, "table", table)
        healthy = healthy and present
        print(f"{table}: {'OK' if present else 'MISSING'}")

    triggers = connection.execute(
        """
        SELECT name, tbl_name
        FROM sqlite_master
        WHERE type='trigger'
          AND name LIKE 'trg_%_publish_opportunity_created'
        ORDER BY name
        """
    ).fetchall()
    print(f"Opportunity event triggers: {len(triggers)}")
    for trigger in triggers:
        print(f"  {trigger['name']} -> {trigger['tbl_name']}")
    healthy = healthy and len(triggers) >= 1

    if exists(connection, "view", "platform_event_health"):
        health = connection.execute("SELECT * FROM platform_event_health").fetchone()
        print(f"Total events: {health['total_events'] or 0}")
        print(f"Pending: {health['pending_events'] or 0}")
        print(f"Processing: {health['processing_events'] or 0}")
        print(f"Processed: {health['processed_events'] or 0}")
        print(f"Failed: {health['failed_events'] or 0}")
        print(f"Latest event: {health['latest_event_at']}")
        healthy = healthy and (health["failed_events"] or 0) == 0
    else:
        print("platform_event_health view: MISSING")
        healthy = False

    duplicate_groups = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM (
            SELECT deduplication_key
            FROM platform_events
            WHERE deduplication_key IS NOT NULL
            GROUP BY deduplication_key
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()["total"]
    print(f"Duplicate deduplication keys: {duplicate_groups}")
    healthy = healthy and duplicate_groups == 0
    print(f"Overall status: {'HEALTHY' if healthy else 'ATTENTION REQUIRED'}")
    print("=" * 70)
    connection.close()

    if not healthy:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
'''
    path.write_text(content, encoding="utf-8")
    return path


def verify_json_support(connection: sqlite3.Connection) -> None:
    value = connection.execute("SELECT json_object('test', 1)").fetchone()[0]
    if value != '{"test":1}':
        raise RuntimeError("SQLite JSON support did not return the expected result.")


def main() -> None:
    if not SRC_DIR.exists():
        raise FileNotFoundError(f"src directory not found. Current directory: {PROJECT_ROOT}")

    backup_path = backup_database()
    create_event_tables = load_event_module()
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        verify_json_support(connection)
        install_schema(connection, create_event_tables)
        table, mapping, candidates = discover_opportunity_table(connection)
        trigger_name = install_trigger(connection, table, mapping)
        consumer_path = write_consumer()
        health_path = write_healthcheck()

        print("\n" + "=" * 76)
        print("PLATFORM EVENT AUTOMATION INSTALLATION COMPLETE")
        print("=" * 76)
        print(f"Backup created: {backup_path}")
        print(f"Opportunity table selected: {table}")
        print(f"Detection candidates: {candidates}")
        print(f"Trigger installed: {trigger_name}")
        print(f"Consumer created: {consumer_path}")
        print(f"Health check created: {health_path}")
        print("\nDetected opportunity fields:")
        for key, value in mapping.items():
            print(f"  {key}: {value or 'not available'}")
        print("\nRun these commands now:")
        print("  python src/event_foundation_health.py")
        print("  python src/process_platform_events.py")
        print("  python src/event_foundation_health.py")
        print("\nFuture opportunity inserts will automatically create OpportunityCreated events.")
        print("The consumer classifies them as HOLD, DASHBOARD, or ALERT_REVIEW.")
        print("No external Discord alert is sent at this stage.")
        print("=" * 76)
    except Exception:
        connection.rollback()
        print("\nINSTALLATION FAILED.")
        print(f"Your database backup is available at: {backup_path}")
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
