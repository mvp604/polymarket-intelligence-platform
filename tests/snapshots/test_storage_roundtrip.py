from decimal import Decimal

from src.snapshots.loader import SnapshotLoader
from src.snapshots.models import (
    SnapshotConsensus,
    SnapshotMarket,
    SnapshotWallet,
)
from src.snapshots.storage import SQLiteSnapshotStorage
from src.snapshots.types import MarketId, WalletId


def test_snapshot_checksum_survives_storage_round_trip(tmp_path):
    database_path = tmp_path / "snapshots.db"

    loader = SnapshotLoader()
    storage = SQLiteSnapshotStorage(database_path)

    wallet = SnapshotWallet(
        wallet_id=WalletId("wallet-1"),
        market_id=MarketId("market-1"),
        outcome="Yes",
        shares=Decimal("100.5000"),
        average_price=Decimal("0.4000"),
        current_price=Decimal("0.5500"),
        current_value=Decimal("55.2750"),
        cash_pnl=Decimal("15.0750"),
        percent_pnl=Decimal("37.5000"),
    )

    market = SnapshotMarket(
        market_id=MarketId("market-1"),
        title="Test market",
        category="sports",
        status="active",
        yes_price=Decimal("0.5500"),
        no_price=Decimal("0.4500"),
    )

    consensus = SnapshotConsensus(
        market_id=MarketId("market-1"),
        outcome="Yes",
        wallet_count=1,
        combined_shares=Decimal("100.5000"),
        combined_value=Decimal("55.2750"),
        combined_pnl=Decimal("15.0750"),
        conviction_score=Decimal("75.2500"),
        conviction_grade="A",
    )

    snapshot = loader.build(
        snapshot_id="snap-round-trip-test",
        wallets=(wallet,),
        markets=(market,),
        consensus=(consensus,),
        attributes={
            "capture_mode": "test",
            "source_database": "test.db",
            "source_fingerprint": "abc123",
        },
    )

    storage.save(snapshot)
    loaded = storage.load("snap-round-trip-test")

    assert loaded.metadata.checksum == snapshot.metadata.checksum
    assert loaded.to_dict() == snapshot.to_dict()