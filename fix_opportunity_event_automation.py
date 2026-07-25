from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path.cwd()
DB_PATH = ROOT / "database" / "polymarket.db"
BACKUP_DIR = ROOT / "database" / "backups"
TABLE = "opportunity_intelligence_v2"


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def get_columns(conn: sqlite3.Connection) -> set[str]:
    return {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({q(TABLE)})").fetchall()
    }


def first_existing(columns: set[str], *names: str) -> str | None:
    for name in names:
        if name in columns:
            return name
    return None


def new_expr(column: str | None, fallback: str = "NULL") -> str:
    return f"NEW.{q(column)}" if column else fallback


def old_expr(column: str | None, fallback: str = "NULL") -> str:
    return f"OLD.{q(column)}" if column else fallback


def cast_text(expr: str) -> str:
    return f"COALESCE(CAST({expr} AS TEXT), '')"


def changed(old: str, new: str) -> str:
    return f"{cast_text(old)} <> {cast_text(new)}"


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"polymarket_before_event_update_fix_{stamp}.db"
    shutil.copy2(DB_PATH, backup)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        columns = get_columns(conn)

        required = {"opportunity_id", "market_id", "title", "outcome", "opportunity_score", "opportunity_grade"}
        missing = required - columns
        if missing:
            raise RuntimeError(f"Required columns missing from {TABLE}: {sorted(missing)}")

        id_col = "opportunity_id"
        market_col = "market_id"
        title_col = "title"
        outcome_col = "outcome"
        score_col = "opportunity_score"
        grade_col = "opportunity_grade"
        decision_col = first_existing(columns, "decision", "recommended_action", "action")
        timing_col = first_existing(columns, "timing", "timing_label", "timing_classification")
        wallet_col = first_existing(columns, "wallet_count", "matching_wallets")
        elite_col = first_existing(columns, "elite_wallet_count", "elite_count")
        capital_col = first_existing(columns, "combined_value", "capital", "total_capital")
        state_checksum_col = first_existing(columns, "state_checksum")

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS event_backfill_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backfill_name TEXT NOT NULL UNIQUE,
                source_table TEXT NOT NULL,
                rows_seen INTEGER NOT NULL,
                events_inserted INTEGER NOT NULL,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_platform_events_opportunity_type
                ON platform_events(event_type, aggregate_type, aggregate_id);
            """
        )

        insert_trigger = f"trg_{TABLE}_publish_opportunity_created"
        update_trigger = f"trg_{TABLE}_publish_opportunity_updated"

        conn.execute(f"DROP TRIGGER IF EXISTS {q(insert_trigger)}")
        conn.execute(f"DROP TRIGGER IF EXISTS {q(update_trigger)}")

        aggregate_new = f"CAST(NEW.{q(id_col)} AS TEXT)"
        aggregate_old = f"CAST(OLD.{q(id_col)} AS TEXT)"

        payload_new = f"""json_object(
            'opportunity_id', {aggregate_new},
            'market_id', {new_expr(market_col)},
            'title', {new_expr(title_col)},
            'outcome', {new_expr(outcome_col)},
            'score', {new_expr(score_col)},
            'grade', {new_expr(grade_col)},
            'decision', {new_expr(decision_col)},
            'timing', {new_expr(timing_col)},
            'wallet_count', {new_expr(wallet_col)},
            'elite_wallet_count', {new_expr(elite_col)},
            'combined_value', {new_expr(capital_col)},
            'source_table', '{TABLE}'
        )"""

        state_key_new_parts = [
            cast_text(new_expr(score_col)),
            cast_text(new_expr(grade_col)),
            cast_text(new_expr(decision_col)),
            cast_text(new_expr(timing_col)),
            cast_text(new_expr(wallet_col)),
            cast_text(new_expr(elite_col)),
            cast_text(new_expr(capital_col)),
            cast_text(new_expr(state_checksum_col)),
        ]
        state_key_new = " || '|' || ".join(state_key_new_parts)

        insert_sql = f"""
        CREATE TRIGGER {q(insert_trigger)}
        AFTER INSERT ON {q(TABLE)}
        BEGIN
            INSERT OR IGNORE INTO platform_events (
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
            VALUES (
                lower(hex(randomblob(4))) || '-' ||
                lower(hex(randomblob(2))) || '-' ||
                '4' || substr(lower(hex(randomblob(2))), 2) || '-' ||
                substr('89ab', abs(random()) % 4 + 1, 1) ||
                substr(lower(hex(randomblob(2))), 2) || '-' ||
                lower(hex(randomblob(6))),
                'OpportunityCreated',
                'sqlite_opportunity_trigger',
                '1.1.0',
                'opportunity',
                {aggregate_new},
                {payload_new},
                strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                NULL,
                NULL,
                'OpportunityCreated:{TABLE}:' || {aggregate_new} || ':' || ({state_key_new}),
                'PENDING'
            );
        END;
        """

        change_conditions = [
            changed(old_expr(score_col), new_expr(score_col)),
            changed(old_expr(grade_col), new_expr(grade_col)),
        ]
        for optional_col in [decision_col, timing_col, wallet_col, elite_col, capital_col, state_checksum_col]:
            if optional_col:
                change_conditions.append(changed(old_expr(optional_col), new_expr(optional_col)))

        when_clause = " OR\n            ".join(change_conditions)

        update_sql = f"""
        CREATE TRIGGER {q(update_trigger)}
        AFTER UPDATE ON {q(TABLE)}
        WHEN
            {when_clause}
        BEGIN
            INSERT OR IGNORE INTO platform_events (
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
            VALUES (
                lower(hex(randomblob(4))) || '-' ||
                lower(hex(randomblob(2))) || '-' ||
                '4' || substr(lower(hex(randomblob(2))), 2) || '-' ||
                substr('89ab', abs(random()) % 4 + 1, 1) ||
                substr(lower(hex(randomblob(2))), 2) || '-' ||
                lower(hex(randomblob(6))),
                'OpportunityUpdated',
                'sqlite_opportunity_trigger',
                '1.1.0',
                'opportunity',
                {aggregate_new},
                {payload_new},
                strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                NULL,
                NULL,
                'OpportunityUpdated:{TABLE}:' || {aggregate_new} || ':' || ({state_key_new}),
                'PENDING'
            );
        END;
        """

        conn.executescript(insert_sql)
        conn.executescript(update_sql)

        # Allow the existing consumer to process both created and updated events.
        consumer_path = ROOT / "src" / "process_platform_events.py"
        if consumer_path.exists():
            text = consumer_path.read_text(encoding="utf-8")
            old_filter = "WHERE e.event_type = 'OpportunityCreated'"
            new_filter = "WHERE e.event_type IN ('OpportunityCreated', 'OpportunityUpdated')"
            if old_filter in text:
                consumer_path.write_text(
                    text.replace(old_filter, new_filter),
                    encoding="utf-8",
                )

        # Backfill one current-state event per opportunity exactly once.
        backfill_name = "opportunity_intelligence_v2_current_state_v1"
        prior = conn.execute(
            "SELECT 1 FROM event_backfill_runs WHERE backfill_name = ?",
            (backfill_name,),
        ).fetchone()

        total_rows = conn.execute(f"SELECT COUNT(*) FROM {q(TABLE)}").fetchone()[0]
        before_events = conn.total_changes

        if not prior:
            backfill_sql = f"""
            INSERT OR IGNORE INTO platform_events (
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
            SELECT
                lower(hex(randomblob(4))) || '-' ||
                lower(hex(randomblob(2))) || '-' ||
                '4' || substr(lower(hex(randomblob(2))), 2) || '-' ||
                substr('89ab', abs(random()) % 4 + 1, 1) ||
                substr(lower(hex(randomblob(2))), 2) || '-' ||
                lower(hex(randomblob(6))),
                'OpportunityCreated',
                'opportunity_backfill',
                '1.0.0',
                'opportunity',
                CAST({q(id_col)} AS TEXT),
                json_object(
                    'opportunity_id', CAST({q(id_col)} AS TEXT),
                    'market_id', {q(market_col)},
                    'title', {q(title_col)},
                    'outcome', {q(outcome_col)},
                    'score', {q(score_col)},
                    'grade', {q(grade_col)},
                    'decision', {q(decision_col) if decision_col else 'NULL'},
                    'timing', {q(timing_col) if timing_col else 'NULL'},
                    'wallet_count', {q(wallet_col) if wallet_col else 'NULL'},
                    'elite_wallet_count', {q(elite_col) if elite_col else 'NULL'},
                    'combined_value', {q(capital_col) if capital_col else 'NULL'},
                    'source_table', '{TABLE}',
                    'backfilled', 1
                ),
                strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                NULL,
                NULL,
                'OpportunityBackfill:{TABLE}:' || CAST({q(id_col)} AS TEXT),
                'PENDING'
            FROM {q(TABLE)};
            """
            conn.execute(backfill_sql)
            inserted = conn.total_changes - before_events

            conn.execute(
                """
                INSERT INTO event_backfill_runs (
                    backfill_name,
                    source_table,
                    rows_seen,
                    events_inserted
                )
                VALUES (?, ?, ?, ?)
                """,
                (backfill_name, TABLE, total_rows, inserted),
            )
        else:
            inserted = 0

        conn.commit()

        trigger_rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'trigger'
              AND tbl_name = ?
              AND name LIKE '%publish_opportunity%'
            ORDER BY name
            """,
            (TABLE,),
        ).fetchall()

        pending = conn.execute(
            """
            SELECT COUNT(*)
            FROM platform_events
            WHERE status = 'PENDING'
              AND event_type IN ('OpportunityCreated', 'OpportunityUpdated')
            """
        ).fetchone()[0]

        print("=" * 78)
        print("OPPORTUNITY EVENT INTEGRATION FIX COMPLETE")
        print("=" * 78)
        print(f"Backup: {backup}")
        print(f"Source table: {TABLE}")
        print(f"Current opportunity rows: {total_rows:,}")
        print(f"Current-state events backfilled now: {inserted:,}")
        print(f"Pending opportunity events: {pending:,}")
        print("Installed triggers:")
        for row in trigger_rows:
            print(f"  {row['name']}")
        print()
        print("Meaningful future INSERTS create OpportunityCreated events.")
        print("Meaningful future UPDATES create OpportunityUpdated events.")
        print("Unchanged reruns create no duplicate events.")
        print()
        print("Run next:")
        print("  python src/process_platform_events.py")
        print("  python src/event_foundation_health.py")
        print("=" * 78)

    except Exception:
        conn.rollback()
        print(f"Installation failed. Backup is available at: {backup}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
