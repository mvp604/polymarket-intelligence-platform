from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
DB_PATH = ROOT / 'database' / 'polymarket.db'
BACKUP_DIR = ROOT / 'database' / 'backups'
CONSUMER_PATH = ROOT / 'src' / 'process_platform_events.py'
HEALTH_PATH = ROOT / 'src' / 'event_foundation_health.py'
CONSUMER_NAME = 'alert_decision_service_v1'

CONSUMER_CODE = r"""from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DATABASE_PATH = Path('database') / 'polymarket.db'
CONSUMER_NAME = 'alert_decision_service_v1'


def normalize(value: object) -> str:
    return str(value or '').strip().upper()


def decision_for(payload: dict) -> tuple[str, str]:
    engine_decision = normalize(payload.get('decision'))
    grade = normalize(payload.get('grade') or payload.get('confidence_grade'))

    raw_score = payload.get('score')
    try:
        score = float(raw_score) if raw_score is not None else None
    except (TypeError, ValueError):
        score = None

    if engine_decision in {'ACTIONABLE', 'ALERT', 'PLAY', 'BET'}:
        return 'ALERT_REVIEW', f'Opportunity Engine decision is {engine_decision}; operator review required before external alerting.'

    if engine_decision in {'MONITOR', 'WATCHLIST'}:
        return 'DASHBOARD', f'Opportunity Engine decision is {engine_decision}; display and monitor without external alerting.'

    if engine_decision == 'PASS':
        return 'HOLD', 'Opportunity Engine decision is PASS; no alert or dashboard escalation.'

    if grade in {'S+', 'S', 'HIGH', 'ELITE', 'A+'} or (score is not None and score >= 85):
        return 'ALERT_REVIEW', 'Legacy/test event meets the high-score or elite-grade review threshold.'

    if grade in {'A', 'B+', 'MEDIUM'} or (score is not None and score >= 70):
        return 'DASHBOARD', 'Legacy/test event meets the dashboard monitoring threshold.'

    return 'HOLD', 'Evidence is below current monitoring and alert-review thresholds.'


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    connection.execute(
        '''
        INSERT INTO event_consumers (consumer_name, description)
        VALUES (?, ?)
        ON CONFLICT(consumer_name) DO UPDATE SET
            description = excluded.description,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (
            CONSUMER_NAME,
            'Classifies OpportunityCreated and OpportunityUpdated events using the Opportunity Engine decision first.',
        ),
    )

    events = connection.execute(
        '''
        SELECT e.event_id, e.aggregate_id, e.payload_json
        FROM platform_events AS e
        LEFT JOIN event_consumer_receipts AS r
          ON r.event_id = e.event_id
         AND r.consumer_name = ?
        WHERE e.event_type IN ('OpportunityCreated', 'OpportunityUpdated')
          AND r.id IS NULL
        ORDER BY e.id ASC
        ''',
        (CONSUMER_NAME,),
    ).fetchall()

    processed = 0

    for event in events:
        payload = json.loads(event['payload_json'])
        decision, rationale = decision_for(payload)
        score = payload.get('score')
        grade = payload.get('grade') or payload.get('confidence_grade')

        connection.execute(
            '''
            INSERT INTO alert_decisions (
                event_id, opportunity_id, market_id, decision, score, grade, rationale
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                opportunity_id = excluded.opportunity_id,
                market_id = excluded.market_id,
                decision = excluded.decision,
                score = excluded.score,
                grade = excluded.grade,
                rationale = excluded.rationale
            ''',
            (
                event['event_id'],
                str(payload.get('opportunity_id') or event['aggregate_id']),
                payload.get('market_id'),
                decision,
                score,
                grade,
                rationale,
            ),
        )

        connection.execute(
            '''
            INSERT INTO event_consumer_receipts (
                consumer_name, event_id, result_json
            )
            VALUES (?, ?, ?)
            ON CONFLICT(consumer_name, event_id) DO UPDATE SET
                processed_at = CURRENT_TIMESTAMP,
                result_json = excluded.result_json
            ''',
            (
                CONSUMER_NAME,
                event['event_id'],
                json.dumps({'decision': decision, 'rationale': rationale}, sort_keys=True),
            ),
        )

        connection.execute(
            '''
            UPDATE platform_events
            SET status = 'PROCESSED',
                processed_at = COALESCE(processed_at, CURRENT_TIMESTAMP),
                error_message = NULL
            WHERE event_id = ?
            ''',
            (event['event_id'],),
        )
        processed += 1

    connection.execute(
        '''
        UPDATE event_consumers
        SET last_run_at = CURRENT_TIMESTAMP,
            last_success_at = CURRENT_TIMESTAMP,
            last_error = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE consumer_name = ?
        ''',
        (CONSUMER_NAME,),
    )

    connection.commit()

    totals = connection.execute(
        '''
        SELECT decision, COUNT(*) AS total
        FROM alert_decisions
        GROUP BY decision
        ORDER BY decision
        '''
    ).fetchall()

    print('=' * 70)
    print('ALERT DECISION SERVICE')
    print('=' * 70)
    print(f'New events processed: {processed}')
    for row in totals:
        print(f"{row['decision']}: {row['total']}")
    print('=' * 70)

    connection.close()


if __name__ == '__main__':
    main()
"""


def patch_health_check() -> None:
    text = HEALTH_PATH.read_text(encoding='utf-8')
    text = text.replace(
        "AND name LIKE 'trg_%_publish_opportunity_created'",
        "AND name LIKE 'trg_%_publish_opportunity_%'",
    )
    HEALTH_PATH.write_text(text, encoding='utf-8')


def main() -> None:
    for path in (DB_PATH, CONSUMER_PATH, HEALTH_PATH):
        if not path.exists():
            raise FileNotFoundError(f'Not found: {path}')

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    db_backup = BACKUP_DIR / f'polymarket_before_decision_alignment_{stamp}.db'
    consumer_backup = CONSUMER_PATH.with_suffix(f'.py.backup_{stamp}')
    health_backup = HEALTH_PATH.with_suffix(f'.py.backup_{stamp}')

    shutil.copy2(DB_PATH, db_backup)
    shutil.copy2(CONSUMER_PATH, consumer_backup)
    shutil.copy2(HEALTH_PATH, health_backup)

    CONSUMER_PATH.write_text(CONSUMER_CODE, encoding='utf-8')
    patch_health_check()

    connection = sqlite3.connect(DB_PATH)
    try:
        ids = [
            row[0]
            for row in connection.execute(
                '''
                SELECT event_id
                FROM platform_events
                WHERE event_type IN ('OpportunityCreated', 'OpportunityUpdated')
                  AND source_engine != 'platform_events_test'
                '''
            ).fetchall()
        ]

        for start in range(0, len(ids), 900):
            batch = ids[start:start + 900]
            if not batch:
                continue
            placeholders = ','.join('?' for _ in batch)
            connection.execute(
                f'''DELETE FROM event_consumer_receipts
                    WHERE consumer_name = ?
                      AND event_id IN ({placeholders})''',
                [CONSUMER_NAME, *batch],
            )
            connection.execute(
                f'''DELETE FROM alert_decisions
                    WHERE event_id IN ({placeholders})''',
                batch,
            )

        connection.commit()

        print('=' * 78)
        print('ALERT DECISION ALIGNMENT COMPLETE')
        print('=' * 78)
        print(f'Database backup: {db_backup}')
        print(f'Consumer backup: {consumer_backup}')
        print(f'Health-check backup: {health_backup}')
        print(f'Production events queued for reprocessing: {len(ids):,}')
        print()
        print('Classification authority:')
        print('  ACTIONABLE / ALERT / PLAY -> ALERT_REVIEW')
        print('  MONITOR / WATCHLIST       -> DASHBOARD')
        print('  PASS                      -> HOLD')
        print('  Missing decision          -> score/grade fallback')
        print()
        print('Run next:')
        print('  python src/process_platform_events.py')
        print('  python src/event_foundation_health.py')
        print('=' * 78)

    except Exception:
        connection.rollback()
        shutil.copy2(consumer_backup, CONSUMER_PATH)
        shutil.copy2(health_backup, HEALTH_PATH)
        print(f'Alignment failed. Database backup: {db_backup}')
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    main()
