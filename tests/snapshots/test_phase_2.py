from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.snapshots import (
    SnapshotConsensus,
    SnapshotIntegrityError,
    SnapshotMarket,
    SnapshotStorageError,
    SnapshotValidationError,
    SnapshotWallet,
)
from src.snapshots.index import SnapshotIndex
from src.snapshots.loader import SnapshotLoader
from src.snapshots.replay import SnapshotReplay
from src.snapshots.storage import SQLiteSnapshotStorage
from src.snapshots.validator import SnapshotValidator


def wallet(wallet_id: str = "0xabc") -> SnapshotWallet:
    return SnapshotWallet(
        wallet_id=wallet_id,
        market_id="market-1",
        outcome="YES",
        shares=Decimal("10"),
        average_price=Decimal("0.40"),
        current_price=Decimal("0.55"),
        current_value=Decimal("5.50"),
        cash_pnl=Decimal("1.50"),
        percent_pnl=Decimal("37.5"),
    )


def market() -> SnapshotMarket:
    return SnapshotMarket(
        market_id="market-1",
        title="Example market",
        category="sports",
        status="active",
        yes_price=Decimal("0.55"),
        no_price=Decimal("0.45"),
    )


def consensus() -> SnapshotConsensus:
    return SnapshotConsensus(
        market_id="market-1",
        outcome="YES",
        wallet_count=1,
        combined_shares=Decimal("10"),
        combined_value=Decimal("5.50"),
        combined_pnl=Decimal("1.50"),
        conviction_score=Decimal("82.5"),
        conviction_grade="A",
    )


def build_snapshot(
    snapshot_id: str = "snap-001",
    created_at: datetime | None = None,
):
    return SnapshotLoader().build(
        snapshot_id=snapshot_id,
        created_at=created_at or datetime(2026, 7, 24, 12, tzinfo=timezone.utc),
        wallets=[wallet()],
        markets=[market()],
        consensus=[consensus()],
        attributes={"source": "unit-test"},
    )


def test_loader_builds_valid_checksum():
    snapshot = build_snapshot()
    assert len(snapshot.metadata.checksum) == 64
    SnapshotValidator().validate(snapshot)


def test_loader_rejects_duplicate_wallet_position():
    with pytest.raises(SnapshotValidationError, match="duplicate wallet position"):
        SnapshotLoader().build(
            snapshot_id="snap-duplicate",
            wallets=[wallet(), wallet()],
            markets=[market()],
            consensus=[consensus()],
        )


def test_loader_rejects_unknown_consensus_market():
    unknown = SnapshotConsensus(
        market_id="market-unknown",
        outcome="YES",
        wallet_count=1,
        combined_shares=Decimal("1"),
        combined_value=Decimal("1"),
        combined_pnl=Decimal("0"),
        conviction_score=Decimal("50"),
        conviction_grade="B",
    )
    with pytest.raises(SnapshotValidationError, match="unknown market"):
        SnapshotLoader().build(
            snapshot_id="snap-orphan",
            wallets=[wallet()],
            markets=[market()],
            consensus=[unknown],
        )


def test_storage_round_trip(tmp_path):
    storage = SQLiteSnapshotStorage(tmp_path / "snapshots.db")
    original = build_snapshot()
    storage.save(original)
    restored = storage.load("snap-001")
    assert restored.to_dict() == original.to_dict()


def test_storage_rejects_duplicate_snapshot(tmp_path):
    storage = SQLiteSnapshotStorage(tmp_path / "snapshots.db")
    snapshot = build_snapshot()
    storage.save(snapshot)
    with pytest.raises(SnapshotStorageError, match="already exists"):
        storage.save(snapshot)


def test_index_latest_and_find(tmp_path):
    storage = SQLiteSnapshotStorage(tmp_path / "snapshots.db")
    first = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
    second = first + timedelta(hours=1)
    storage.save(build_snapshot("snap-1", first))
    storage.save(build_snapshot("snap-2", second))
    index = SnapshotIndex(storage)
    assert str(index.latest().snapshot_id) == "snap-2"
    assert str(index.find("snap-1").snapshot_id) == "snap-1"


def test_replay_is_chronological(tmp_path):
    storage = SQLiteSnapshotStorage(tmp_path / "snapshots.db")
    first = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
    second = first + timedelta(hours=1)
    storage.save(build_snapshot("snap-2", second))
    storage.save(build_snapshot("snap-1", first))
    ids = [str(item.metadata.snapshot_id) for item in SnapshotReplay(storage).iterate()]
    assert ids == ["snap-1", "snap-2"]


def test_checksum_tampering_is_detected():
    snapshot = build_snapshot()
    object.__setattr__(snapshot.metadata, "checksum", "invalid")
    with pytest.raises(SnapshotIntegrityError, match="checksum mismatch"):
        SnapshotValidator().validate(snapshot)
