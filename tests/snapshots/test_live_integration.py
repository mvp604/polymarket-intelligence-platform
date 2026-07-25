from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.snapshots.exceptions import SnapshotStorageError
from src.snapshots.live_adapter import LiveSnapshotAdapter
from src.snapshots.service import LiveSnapshotService
from src.snapshots.storage import SQLiteSnapshotStorage


def build_live_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE wallet_scans (
                id INTEGER PRIMARY KEY,
                wallet TEXT NOT NULL,
                scanned_at TEXT NOT NULL
            );

            CREATE TABLE positions (
                id INTEGER PRIMARY KEY,
                scan_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                shares REAL NOT NULL,
                average_price REAL NOT NULL,
                current_price REAL NOT NULL,
                current_value REAL NOT NULL,
                cash_pnl REAL NOT NULL,
                percent_pnl REAL NOT NULL
            );

            CREATE TABLE consensus_history (
                id INTEGER PRIMARY KEY,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                wallet_count INTEGER NOT NULL,
                combined_shares REAL NOT NULL,
                combined_value REAL NOT NULL,
                combined_pnl REAL NOT NULL,
                conviction_score REAL NOT NULL,
                conviction_grade TEXT NOT NULL,
                average_entry_price REAL,
                average_current_price REAL,
                observed_price_move REAL,
                scanned_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO wallet_scans VALUES (1, '0xabc', '2026-07-24T12:00:00+00:00')"
        )
        connection.execute(
            """
            INSERT INTO positions VALUES (
                1, 1, '0xabc', 'market-1', 'Example market', 'YES',
                10, 0.4, 0.55, 5.5, 1.5, 37.5
            )
            """
        )
        connection.execute(
            """
            INSERT INTO consensus_history VALUES (
                1, 'market-1', 'Example market', 'YES', 1,
                10, 5.5, 1.5, 82.5, 'A', 0.4, 0.55, 0.15,
                '2026-07-24T12:00:00+00:00'
            )
            """
        )


def test_live_adapter_reads_current_state(tmp_path):
    database = tmp_path / "live.db"
    build_live_database(database)
    adapter = LiveSnapshotAdapter(database)

    wallets = adapter.load_wallets()
    markets = adapter.load_markets(wallets)
    consensus = adapter.load_consensus()

    assert len(wallets) == 1
    assert len(markets) == 1
    assert markets[0].title == "Example market"
    assert len(consensus) == 1


def test_live_service_creates_persisted_snapshot(tmp_path):
    database = tmp_path / "live.db"
    build_live_database(database)

    snapshot = LiveSnapshotService(database).create()
    restored = SQLiteSnapshotStorage(database).load(
        str(snapshot.metadata.snapshot_id)
    )

    assert restored.metadata.wallet_count == 1
    assert restored.metadata.market_count == 1
    assert restored.metadata.consensus_count == 1
    assert restored.attributes["capture_mode"] == "live"


def test_duplicate_source_state_is_rejected(tmp_path):
    database = tmp_path / "live.db"
    build_live_database(database)
    service = LiveSnapshotService(database)
    service.create()

    with pytest.raises(SnapshotStorageError, match="already exists"):
        service.create()


def test_force_creates_diagnostic_duplicate(tmp_path):
    database = tmp_path / "live.db"
    build_live_database(database)
    service = LiveSnapshotService(database)
    first = service.create()
    second = service.create(force=True)

    assert first.metadata.snapshot_id != second.metadata.snapshot_id
    assert len(SQLiteSnapshotStorage(database).list_metadata()) == 2
