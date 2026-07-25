from __future__ import annotations

import sqlite3
from datetime import datetime


VERSION = "0005"
NAME = "consensus_intelligence_v1_0_1"


RUNS_COLUMNS = {
    "run_id",
    "started_at",
    "completed_at",
    "status",
    "engine_version",
    "database_path",
    "markets_reviewed",
    "eligible_markets",
    "consensus_inserted",
    "consensus_updated",
    "signals_created",
    "passes",
    "errors",
    "runtime_seconds",
    "error_message",
    "created_at",
    "updated_at",
}

CURRENT_COLUMNS = {
    "condition_id",
    "question",
    "category",
    "sport",
    "league",
    "active",
    "closed",
    "resolved",
    "yes_price",
    "no_price",
    "liquidity",
    "volume",
    "spread",
    "wallet_count",
    "elite_wallet_count",
    "average_wallet_roi",
    "wallet_confidence_score",
    "market_health_score",
    "risk_score",
    "price_momentum_score",
    "opportunity_base_score",
    "consensus_side",
    "agreement_score",
    "conviction_score",
    "smart_money_density",
    "consensus_momentum",
    "final_consensus_score",
    "confidence_grade",
    "signal_status",
    "signal_reason",
    "source_feature_calculated_at",
    "source_run_id",
    "calculated_at",
    "created_at",
    "updated_at",
}

HISTORY_COLUMNS = {
    "history_id",
    "condition_id",
    "consensus_side",
    "agreement_score",
    "conviction_score",
    "smart_money_density",
    "consensus_momentum",
    "final_consensus_score",
    "confidence_grade",
    "signal_status",
    "wallet_count",
    "elite_wallet_count",
    "yes_price",
    "source_run_id",
    "calculated_at",
    "created_at",
}


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    ).fetchone() is not None


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not table_exists(connection, table_name):
        return set()

    return {
        str(row[1])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def unique_legacy_name(
    connection: sqlite3.Connection,
    table_name: str,
) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = f"{table_name}_legacy_{stamp}"
    counter = 1

    while table_exists(connection, candidate):
        counter += 1
        candidate = f"{table_name}_legacy_{stamp}_{counter}"

    return candidate


def preserve_if_incompatible(
    connection: sqlite3.Connection,
    table_name: str,
    required_columns: set[str],
) -> None:
    if not table_exists(connection, table_name):
        return

    existing = table_columns(connection, table_name)
    if required_columns.issubset(existing):
        return

    legacy_name = unique_legacy_name(connection, table_name)
    connection.execute(
        f'ALTER TABLE "{table_name}" RENAME TO "{legacy_name}"'
    )


def upgrade(connection: sqlite3.Connection) -> None:
    preserve_if_incompatible(
        connection,
        "consensus_intelligence_runs",
        RUNS_COLUMNS,
    )
    preserve_if_incompatible(
        connection,
        "consensus_intelligence_current",
        CURRENT_COLUMNS,
    )
    preserve_if_incompatible(
        connection,
        "consensus_intelligence_history",
        HISTORY_COLUMNS,
    )

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS consensus_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            database_path TEXT NOT NULL,
            markets_reviewed INTEGER NOT NULL DEFAULT 0,
            eligible_markets INTEGER NOT NULL DEFAULT 0,
            consensus_inserted INTEGER NOT NULL DEFAULT 0,
            consensus_updated INTEGER NOT NULL DEFAULT 0,
            signals_created INTEGER NOT NULL DEFAULT 0,
            passes INTEGER NOT NULL DEFAULT 0,
            errors INTEGER NOT NULL DEFAULT 0,
            runtime_seconds REAL NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS consensus_intelligence_current (
            condition_id TEXT PRIMARY KEY,
            question TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            sport TEXT NOT NULL DEFAULT '',
            league TEXT NOT NULL DEFAULT '',

            active INTEGER NOT NULL DEFAULT 0,
            closed INTEGER NOT NULL DEFAULT 0,
            resolved INTEGER NOT NULL DEFAULT 0,

            yes_price REAL,
            no_price REAL,
            liquidity REAL,
            volume REAL,
            spread REAL,

            wallet_count INTEGER NOT NULL DEFAULT 0,
            elite_wallet_count INTEGER NOT NULL DEFAULT 0,
            average_wallet_roi REAL,
            wallet_confidence_score REAL NOT NULL DEFAULT 0,

            market_health_score REAL NOT NULL DEFAULT 0,
            risk_score REAL NOT NULL DEFAULT 100,
            price_momentum_score REAL NOT NULL DEFAULT 50,
            opportunity_base_score REAL NOT NULL DEFAULT 0,

            consensus_side TEXT NOT NULL DEFAULT 'PASS',
            agreement_score REAL NOT NULL DEFAULT 0,
            conviction_score REAL NOT NULL DEFAULT 0,
            smart_money_density REAL NOT NULL DEFAULT 0,
            consensus_momentum REAL NOT NULL DEFAULT 50,
            final_consensus_score REAL NOT NULL DEFAULT 0,
            confidence_grade TEXT NOT NULL DEFAULT 'D',
            signal_status TEXT NOT NULL DEFAULT 'PASS',
            signal_reason TEXT NOT NULL DEFAULT '',

            source_feature_calculated_at TEXT NOT NULL DEFAULT '',
            source_run_id TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY(condition_id)
                REFERENCES market_catalog(condition_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS consensus_intelligence_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_id TEXT NOT NULL,
            consensus_side TEXT NOT NULL,
            agreement_score REAL NOT NULL,
            conviction_score REAL NOT NULL,
            smart_money_density REAL NOT NULL,
            consensus_momentum REAL NOT NULL,
            final_consensus_score REAL NOT NULL,
            confidence_grade TEXT NOT NULL,
            signal_status TEXT NOT NULL,
            wallet_count INTEGER NOT NULL,
            elite_wallet_count INTEGER NOT NULL,
            yes_price REAL,
            source_run_id TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(condition_id, source_run_id),
            FOREIGN KEY(condition_id)
                REFERENCES market_catalog(condition_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_consensus_current_score
            ON consensus_intelligence_current(
                signal_status,
                final_consensus_score DESC,
                risk_score ASC
            );

        CREATE INDEX IF NOT EXISTS idx_consensus_history_market_time
            ON consensus_intelligence_history(
                condition_id,
                calculated_at DESC
            );
        """
    )
