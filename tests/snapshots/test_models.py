from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.snapshots import Snapshot, SnapshotConsensus, SnapshotMetadata, SnapshotValidationError, SnapshotWallet


def metadata(**overrides):
    values = {
        "snapshot_id": "snap-001",
        "created_at": datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc),
        "schema_version": "1.0",
        "platform_version": "0.1",
        "wallet_count": 1,
        "market_count": 0,
        "consensus_count": 1,
        "checksum": "abc123",
    }
    values.update(overrides)
    return SnapshotMetadata(**values)


def wallet():
    return SnapshotWallet(
        wallet_id="0xabc", market_id="market-1", outcome="YES",
        shares=Decimal("10"), average_price=Decimal("0.40"),
        current_price=Decimal("0.55"), current_value=Decimal("5.50"),
        cash_pnl=Decimal("1.50"), percent_pnl=Decimal("37.5"),
    )


def consensus():
    return SnapshotConsensus(
        market_id="market-1", outcome="YES", wallet_count=1,
        combined_shares=Decimal("10"), combined_value=Decimal("5.50"),
        combined_pnl=Decimal("1.50"), conviction_score=Decimal("82.5"),
        conviction_grade="A",
    )


def test_snapshot_metadata_normalizes_timestamp_to_utc():
    assert metadata().created_at.tzinfo == timezone.utc


def test_snapshot_metadata_is_immutable():
    item = metadata()
    with pytest.raises(FrozenInstanceError):
        item.checksum = "changed"


def test_snapshot_create_validates_declared_counts():
    item = Snapshot.create(metadata=metadata(), wallets=[wallet()], consensus=[consensus()])
    assert item.metadata.snapshot_id == "snap-001"
    assert len(item.wallets) == 1


def test_snapshot_rejects_count_mismatch():
    with pytest.raises(SnapshotValidationError, match="wallet_count mismatch"):
        Snapshot.create(metadata=metadata(wallet_count=2), wallets=[wallet()], consensus=[consensus()])


def test_snapshot_serialization_converts_decimal_and_datetime():
    item = Snapshot.create(metadata=metadata(), wallets=[wallet()], consensus=[consensus()], attributes={"source": "test"})
    payload = item.to_dict()
    assert payload["metadata"]["created_at"].endswith("+00:00")
    assert payload["wallets"][0]["shares"] == "10"


def test_metadata_rejects_naive_datetime():
    with pytest.raises(SnapshotValidationError, match="timezone-aware"):
        metadata(created_at=datetime(2026, 7, 24, 12, 0))


def test_consensus_score_must_be_in_range():
    with pytest.raises(SnapshotValidationError, match="between 0 and 100"):
        SnapshotConsensus(
            market_id="market-1", outcome="YES", wallet_count=1,
            combined_shares=Decimal("10"), combined_value=Decimal("5"),
            combined_pnl=Decimal("0"), conviction_score=Decimal("101"),
            conviction_grade="A",
        )
