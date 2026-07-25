from __future__ import annotations

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
