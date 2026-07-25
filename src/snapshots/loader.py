from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .models import (
    Snapshot,
    SnapshotConsensus,
    SnapshotMarket,
    SnapshotMetadata,
    SnapshotWallet,
)
from .types import SnapshotId
from .validator import SnapshotValidator


class SnapshotLoader:
    def __init__(
        self,
        *,
        schema_version: str = "1.0",
        platform_version: str = "0.1",
        validator: SnapshotValidator | None = None,
    ) -> None:
        self.schema_version = schema_version
        self.platform_version = platform_version
        self.validator = validator or SnapshotValidator()

    def build(
        self,
        *,
        wallets: Sequence[SnapshotWallet] = (),
        markets: Sequence[SnapshotMarket] = (),
        consensus: Sequence[SnapshotConsensus] = (),
        attributes: Mapping[str, Any] | None = None,
        snapshot_id: str | None = None,
        created_at: datetime | None = None,
    ) -> Snapshot:
        metadata = SnapshotMetadata(
            snapshot_id=SnapshotId(snapshot_id or f"snap-{uuid4().hex}"),
            created_at=created_at or datetime.now(timezone.utc),
            schema_version=self.schema_version,
            platform_version=self.platform_version,
            wallet_count=len(wallets),
            market_count=len(markets),
            consensus_count=len(consensus),
            checksum="pending",
        )
        snapshot = Snapshot.create(
            metadata=metadata,
            wallets=wallets,
            markets=markets,
            consensus=consensus,
            attributes=attributes,
        )
        snapshot = self.validator.with_checksum(snapshot)
        self.validator.validate(snapshot)
        return snapshot
