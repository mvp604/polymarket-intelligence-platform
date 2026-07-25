from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from .exceptions import SnapshotIntegrityError, SnapshotValidationError
from .models import Snapshot


class SnapshotValidator:
    def validate(
        self,
        snapshot: Snapshot,
        *,
        verify_checksum: bool = True,
    ) -> None:
        snapshot.validate_counts()
        self._validate_unique_wallet_positions(snapshot)
        self._validate_unique_markets(snapshot)
        self._validate_consensus_markets(snapshot)

        if verify_checksum:
            expected = self.calculate_checksum(snapshot)
            if snapshot.metadata.checksum != expected:
                raise SnapshotIntegrityError(
                    "snapshot checksum mismatch: "
                    f"metadata={snapshot.metadata.checksum}, "
                    f"calculated={expected}"
                )

    def calculate_checksum(self, snapshot: Snapshot) -> str:
        payload = snapshot.to_dict()
        payload["metadata"]["checksum"] = ""

        payload["wallets"] = sorted(
            payload.get("wallets", []),
            key=lambda item: (
                str(item.get("wallet_id", "")),
                str(item.get("market_id", "")),
                str(item.get("outcome", "")),
            ),
        )
        payload["markets"] = sorted(
            payload.get("markets", []),
            key=lambda item: str(item.get("market_id", "")),
        )
        payload["consensus"] = sorted(
            payload.get("consensus", []),
            key=lambda item: (
                str(item.get("market_id", "")),
                str(item.get("outcome", "")),
            ),
        )

        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def with_checksum(self, snapshot: Snapshot) -> Snapshot:
        checksum = self.calculate_checksum(snapshot)
        metadata = replace(snapshot.metadata, checksum=checksum)
        return replace(snapshot, metadata=metadata)

    @staticmethod
    def _validate_unique_wallet_positions(snapshot: Snapshot) -> None:
        seen: set[tuple[str, str, str]] = set()
        for item in snapshot.wallets:
            key = (str(item.wallet_id), str(item.market_id), item.outcome)
            if key in seen:
                raise SnapshotValidationError(
                    "duplicate wallet position: " + "|".join(key)
                )
            seen.add(key)

    @staticmethod
    def _validate_unique_markets(snapshot: Snapshot) -> None:
        seen: set[str] = set()
        for item in snapshot.markets:
            market_id = str(item.market_id)
            if market_id in seen:
                raise SnapshotValidationError(
                    f"duplicate market_id: {market_id}"
                )
            seen.add(market_id)

    @staticmethod
    def _validate_consensus_markets(snapshot: Snapshot) -> None:
        market_ids = {str(item.market_id) for item in snapshot.markets}
        for item in snapshot.consensus:
            if market_ids and str(item.market_id) not in market_ids:
                raise SnapshotValidationError(
                    f"consensus references unknown market: {item.market_id}"
                )
