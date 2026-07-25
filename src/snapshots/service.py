from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .exceptions import SnapshotStorageError
from .live_adapter import LiveSnapshotAdapter
from .loader import SnapshotLoader
from .models import Snapshot, SnapshotMarket
from .storage import SQLiteSnapshotStorage


class LiveSnapshotService:
    """Creates persisted historical snapshots from the live platform database."""

    def __init__(
        self,
        source_database: str | Path,
        snapshot_database: str | Path | None = None,
        *,
        schema_version: str = "1.0",
        platform_version: str = "0.1",
    ) -> None:
        self.source_database = Path(source_database)
        self.snapshot_database = Path(snapshot_database or source_database)
        self.adapter = LiveSnapshotAdapter(self.source_database)
        self.loader = SnapshotLoader(
            schema_version=schema_version,
            platform_version=platform_version,
        )
        self.storage = SQLiteSnapshotStorage(self.snapshot_database)

    def create(self, *, force: bool = False) -> Snapshot:
        fingerprint = self.adapter.source_fingerprint()
        snapshot_id = self._snapshot_id(fingerprint)

        existing = self._find_existing(snapshot_id)
        if existing is not None and not force:
            raise SnapshotStorageError(
                "snapshot already exists for the latest source state: "
                f"{snapshot_id}. Use force=True only for diagnostics."
            )
        if existing is not None and force:
            snapshot_id = self._snapshot_id(
                fingerprint + "|forced=" + datetime.now(timezone.utc).isoformat()
            )

        wallets = self.adapter.load_wallets()
        markets = self.adapter.load_markets(wallets)
        consensus = self.adapter.load_consensus()

        known_market_ids = {str(item.market_id) for item in markets}
        consensus_only_markets = []
        for item in consensus:
            market_id = str(item.market_id)
            if market_id not in known_market_ids:
                consensus_only_markets.append(
                    SnapshotMarket(
                        market_id=item.market_id,
                        title=f"Market {market_id}",
                        category="unknown",
                        status="active",
                        yes_price=None,
                        no_price=None,
                    )
                )
                known_market_ids.add(market_id)

        if consensus_only_markets:
            markets = tuple(markets) + tuple(consensus_only_markets)

        snapshot = self.loader.build(
            snapshot_id=snapshot_id,
            wallets=wallets,
            markets=markets,
            consensus=consensus,
            attributes={
                "source_database": str(self.source_database),
                "source_fingerprint": fingerprint,
                "capture_mode": "live",
            },
        )
        self.storage.save(snapshot)
        return snapshot

    def _find_existing(self, snapshot_id: str):
        return next(
            (
                item
                for item in self.storage.list_metadata()
                if str(item.snapshot_id) == snapshot_id
            ),
            None,
        )

    @staticmethod
    def _snapshot_id(fingerprint: str) -> str:
        digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]
        return f"live-{digest}"
