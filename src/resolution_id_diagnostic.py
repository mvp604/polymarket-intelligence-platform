from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path('database/polymarket.db')


def columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()]


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    print('=' * 130)
    print('RESOLUTION ID MAPPING DIAGNOSTIC')
    print('=' * 130)
    print(f'Database: {DB_PATH.resolve()}')

    for table in ['market_consensus', 'signal_ledger', 'market_resolutions', 'consensus_market_resolutions']:
        print('\n' + table)
        print('-' * 130)
        if not table_exists(connection, table):
            print('MISSING')
            continue
        cols = columns(connection, table)
        count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        print(f'Rows: {count}')
        print('Columns:')
        print(', '.join(cols))

    if not table_exists(connection, 'signal_ledger'):
        connection.close()
        return

    signals = connection.execute(
        '''
        SELECT signal_key, condition_id, event_id, market_title, recommended_outcome
        FROM signal_ledger
        ORDER BY signal_date, signal_key
        '''
    ).fetchall()

    print('\nSIGNAL IDENTIFIERS')
    print('-' * 130)
    for row in signals:
        cid = str(row['condition_id'] or '')
        print(
            f"{cid[:72]:<72} len={len(cid):<3} "
            f"event={str(row['event_id'] or '')[:18]:<18} | {row['market_title']}"
        )

    if table_exists(connection, 'market_resolutions'):
        legacy_cols = columns(connection, 'market_resolutions')
        candidate_id_cols = [
            name for name in legacy_cols
            if name.lower() in {
                'condition_id', 'conditionid', 'market_id', 'marketid',
                'token_id', 'clob_token_id', 'gamma_market_id', 'id'
            }
        ]
        candidate_title_cols = [
            name for name in legacy_cols
            if name.lower() in {'market_title', 'title', 'question', 'market_question'}
        ]

        print('\nLEGACY TABLE MATCH TEST')
        print('-' * 130)
        print(f'Candidate ID columns: {candidate_id_cols or "NONE"}')
        print(f'Candidate title columns: {candidate_title_cols or "NONE"}')

        for id_col in candidate_id_cols:
            matched = connection.execute(
                f'''
                SELECT COUNT(DISTINCT sl.condition_id)
                FROM signal_ledger sl
                JOIN market_resolutions mr
                  ON LOWER(CAST(mr."{id_col}" AS TEXT)) = LOWER(sl.condition_id)
                '''
            ).fetchone()[0]
            print(f'Exact matches through {id_col}: {matched}/{len(signals)}')

        if candidate_title_cols:
            title_col = candidate_title_cols[0]
            matched = connection.execute(
                f'''
                SELECT COUNT(DISTINCT sl.signal_key)
                FROM signal_ledger sl
                JOIN market_resolutions mr
                  ON LOWER(TRIM(CAST(mr."{title_col}" AS TEXT))) = LOWER(TRIM(sl.market_title))
                '''
            ).fetchone()[0]
            print(f'Exact title matches through {title_col}: {matched}/{len(signals)}')

            print('\nSAMPLE TITLE MATCHES')
            rows = connection.execute(
                f'''
                SELECT sl.market_title, sl.condition_id, mr.*
                FROM signal_ledger sl
                JOIN market_resolutions mr
                  ON LOWER(TRIM(CAST(mr."{title_col}" AS TEXT))) = LOWER(TRIM(sl.market_title))
                LIMIT 5
                '''
            ).fetchall()
            if not rows:
                print('No exact title matches.')
            else:
                for row in rows:
                    print(dict(row))

    print('\nINTERPRETATION')
    print('-' * 130)
    print('If every exact ID match is 0, signal_ledger.condition_id is not aligned with the legacy resolution identifier.')
    print('If title matches exist, the next engine patch can safely map title/event records to the official condition ID.')
    print('If neither ID nor title matches exist, the collector must persist Gamma conditionId/slug when markets are first ingested.')

    connection.close()


if __name__ == '__main__':
    main()