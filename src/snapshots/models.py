from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from .exceptions import SnapshotValidationError
from .types import MarketId, SnapshotId, WalletId


def _require_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise SnapshotValidationError(f"{field_name} must not be empty")
    return cleaned


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SnapshotValidationError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _require_non_negative(value: Decimal, field_name: str) -> Decimal:
    if value < 0:
        raise SnapshotValidationError(f"{field_name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class SnapshotMetadata:
    snapshot_id: SnapshotId
    created_at: datetime
    schema_version: str
    platform_version: str
    wallet_count: int
    market_count: int
    consensus_count: int
    checksum: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", SnapshotId(_require_text(str(self.snapshot_id), "snapshot_id")))
        object.__setattr__(self, "created_at", _require_utc(self.created_at, "created_at"))
        object.__setattr__(self, "schema_version", _require_text(self.schema_version, "schema_version"))
        object.__setattr__(self, "platform_version", _require_text(self.platform_version, "platform_version"))
        object.__setattr__(self, "checksum", _require_text(self.checksum, "checksum"))
        for field_name in ("wallet_count", "market_count", "consensus_count"):
            if getattr(self, field_name) < 0:
                raise SnapshotValidationError(f"{field_name} must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["snapshot_id"] = str(self.snapshot_id)
        result["created_at"] = self.created_at.isoformat()
        return result


@dataclass(frozen=True, slots=True)
class SnapshotWallet:
    wallet_id: WalletId
    market_id: MarketId
    outcome: str
    shares: Decimal
    average_price: Decimal
    current_price: Decimal
    current_value: Decimal
    cash_pnl: Decimal
    percent_pnl: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "wallet_id", WalletId(_require_text(str(self.wallet_id), "wallet_id")))
        object.__setattr__(self, "market_id", MarketId(_require_text(str(self.market_id), "market_id")))
        object.__setattr__(self, "outcome", _require_text(self.outcome, "outcome"))
        object.__setattr__(self, "shares", _require_non_negative(self.shares, "shares"))
        object.__setattr__(self, "average_price", _require_non_negative(self.average_price, "average_price"))
        object.__setattr__(self, "current_price", _require_non_negative(self.current_price, "current_price"))
        object.__setattr__(self, "current_value", _require_non_negative(self.current_value, "current_value"))


@dataclass(frozen=True, slots=True)
class SnapshotMarket:
    market_id: MarketId
    title: str
    category: str
    status: str
    yes_price: Decimal | None = None
    no_price: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "market_id", MarketId(_require_text(str(self.market_id), "market_id")))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(self, "category", _require_text(self.category, "category"))
        object.__setattr__(self, "status", _require_text(self.status, "status"))
        for field_name in ("yes_price", "no_price"):
            value = getattr(self, field_name)
            if value is not None and (value < 0 or value > 1):
                raise SnapshotValidationError(f"{field_name} must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SnapshotConsensus:
    market_id: MarketId
    outcome: str
    wallet_count: int
    combined_shares: Decimal
    combined_value: Decimal
    combined_pnl: Decimal
    conviction_score: Decimal
    conviction_grade: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "market_id", MarketId(_require_text(str(self.market_id), "market_id")))
        object.__setattr__(self, "outcome", _require_text(self.outcome, "outcome"))
        object.__setattr__(self, "conviction_grade", _require_text(self.conviction_grade, "conviction_grade"))
        if self.wallet_count < 0:
            raise SnapshotValidationError("wallet_count must be non-negative")
        object.__setattr__(self, "combined_shares", _require_non_negative(self.combined_shares, "combined_shares"))
        object.__setattr__(self, "combined_value", _require_non_negative(self.combined_value, "combined_value"))
        if self.conviction_score < 0 or self.conviction_score > 100:
            raise SnapshotValidationError("conviction_score must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class Snapshot:
    metadata: SnapshotMetadata
    wallets: tuple[SnapshotWallet, ...]
    markets: tuple[SnapshotMarket, ...]
    consensus: tuple[SnapshotConsensus, ...]
    attributes: Mapping[str, Any]

    @classmethod
    def create(cls, *, metadata: SnapshotMetadata, wallets: Sequence[SnapshotWallet] = (), markets: Sequence[SnapshotMarket] = (), consensus: Sequence[SnapshotConsensus] = (), attributes: Mapping[str, Any] | None = None) -> "Snapshot":
        snapshot = cls(metadata=metadata, wallets=tuple(wallets), markets=tuple(markets), consensus=tuple(consensus), attributes=dict(attributes or {}))
        snapshot.validate_counts()
        return snapshot

    def validate_counts(self) -> None:
        expected = (
            (self.metadata.wallet_count, len(self.wallets), "wallet_count"),
            (self.metadata.market_count, len(self.markets), "market_count"),
            (self.metadata.consensus_count, len(self.consensus), "consensus_count"),
        )
        for declared, actual, field_name in expected:
            if declared != actual:
                raise SnapshotValidationError(f"{field_name} mismatch: metadata={declared}, actual={actual}")

    def to_dict(self) -> dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [normalize(item) for item in value]
            return value

        payload = {
            "metadata": self.metadata.to_dict(),
            "wallets": [asdict(item) for item in self.wallets],
            "markets": [asdict(item) for item in self.markets],
            "consensus": [asdict(item) for item in self.consensus],
            "attributes": dict(self.attributes),
        }
        return normalize(payload)
