from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT_MARKERS = ("src", "tests", "manage.py")

FILES = {
"src/snapshots/__init__.py": """from .exceptions import (\n    SnapshotError,\n    SnapshotIntegrityError,\n    SnapshotReplayError,\n    SnapshotStorageError,\n    SnapshotValidationError,\n)\nfrom .models import (\n    Snapshot,\n    SnapshotConsensus,\n    SnapshotMarket,\n    SnapshotMetadata,\n    SnapshotWallet,\n)\nfrom .types import MarketId, SnapshotId, WalletId\n\n__all__ = [\n    \"MarketId\",\n    \"Snapshot\",\n    \"SnapshotConsensus\",\n    \"SnapshotError\",\n    \"SnapshotId\",\n    \"SnapshotIntegrityError\",\n    \"SnapshotMarket\",\n    \"SnapshotMetadata\",\n    \"SnapshotReplayError\",\n    \"SnapshotStorageError\",\n    \"SnapshotValidationError\",\n    \"SnapshotWallet\",\n    \"WalletId\",\n]\n""",
"src/snapshots/exceptions.py": """class SnapshotError(Exception):\n    \"\"\"Base error for the snapshot subsystem.\"\"\"\n\n\nclass SnapshotValidationError(SnapshotError):\n    \"\"\"Raised when a snapshot or snapshot component is invalid.\"\"\"\n\n\nclass SnapshotStorageError(SnapshotError):\n    \"\"\"Raised when snapshot persistence fails.\"\"\"\n\n\nclass SnapshotReplayError(SnapshotError):\n    \"\"\"Raised when historical replay cannot be completed.\"\"\"\n\n\nclass SnapshotIntegrityError(SnapshotError):\n    \"\"\"Raised when snapshot integrity verification fails.\"\"\"\n""",
"src/snapshots/types.py": """from typing import NewType\n\nSnapshotId = NewType(\"SnapshotId\", str)\nWalletId = NewType(\"WalletId\", str)\nMarketId = NewType(\"MarketId\", str)\n""",
"src/snapshots/models.py": """from __future__ import annotations\n\nfrom dataclasses import asdict, dataclass\nfrom datetime import datetime, timezone\nfrom decimal import Decimal\nfrom typing import Any, Mapping, Sequence\n\nfrom .exceptions import SnapshotValidationError\nfrom .types import MarketId, SnapshotId, WalletId\n\n\ndef _require_text(value: str, field_name: str) -> str:\n    cleaned = value.strip()\n    if not cleaned:\n        raise SnapshotValidationError(f\"{field_name} must not be empty\")\n    return cleaned\n\n\ndef _require_utc(value: datetime, field_name: str) -> datetime:\n    if value.tzinfo is None or value.utcoffset() is None:\n        raise SnapshotValidationError(f\"{field_name} must be timezone-aware\")\n    return value.astimezone(timezone.utc)\n\n\ndef _require_non_negative(value: Decimal, field_name: str) -> Decimal:\n    if value < 0:\n        raise SnapshotValidationError(f\"{field_name} must be non-negative\")\n    return value\n\n\n@dataclass(frozen=True, slots=True)\nclass SnapshotMetadata:\n    snapshot_id: SnapshotId\n    created_at: datetime\n    schema_version: str\n    platform_version: str\n    wallet_count: int\n    market_count: int\n    consensus_count: int\n    checksum: str\n\n    def __post_init__(self) -> None:\n        object.__setattr__(self, \"snapshot_id\", SnapshotId(_require_text(str(self.snapshot_id), \"snapshot_id\")))\n        object.__setattr__(self, \"created_at\", _require_utc(self.created_at, \"created_at\"))\n        object.__setattr__(self, \"schema_version\", _require_text(self.schema_version, \"schema_version\"))\n        object.__setattr__(self, \"platform_version\", _require_text(self.platform_version, \"platform_version\"))\n        object.__setattr__(self, \"checksum\", _require_text(self.checksum, \"checksum\"))\n        for field_name in (\"wallet_count\", \"market_count\", \"consensus_count\"):\n            if getattr(self, field_name) < 0:\n                raise SnapshotValidationError(f\"{field_name} must be non-negative\")\n\n    def to_dict(self) -> dict[str, Any]:\n        result = asdict(self)\n        result[\"snapshot_id\"] = str(self.snapshot_id)\n        result[\"created_at\"] = self.created_at.isoformat()\n        return result\n\n\n@dataclass(frozen=True, slots=True)\nclass SnapshotWallet:\n    wallet_id: WalletId\n    market_id: MarketId\n    outcome: str\n    shares: Decimal\n    average_price: Decimal\n    current_price: Decimal\n    current_value: Decimal\n    cash_pnl: Decimal\n    percent_pnl: Decimal\n\n    def __post_init__(self) -> None:\n        object.__setattr__(self, \"wallet_id\", WalletId(_require_text(str(self.wallet_id), \"wallet_id\")))\n        object.__setattr__(self, \"market_id\", MarketId(_require_text(str(self.market_id), \"market_id\")))\n        object.__setattr__(self, \"outcome\", _require_text(self.outcome, \"outcome\"))\n        object.__setattr__(self, \"shares\", _require_non_negative(self.shares, \"shares\"))\n        object.__setattr__(self, \"average_price\", _require_non_negative(self.average_price, \"average_price\"))\n        object.__setattr__(self, \"current_price\", _require_non_negative(self.current_price, \"current_price\"))\n        object.__setattr__(self, \"current_value\", _require_non_negative(self.current_value, \"current_value\"))\n\n\n@dataclass(frozen=True, slots=True)\nclass SnapshotMarket:\n    market_id: MarketId\n    title: str\n    category: str\n    status: str\n    yes_price: Decimal | None = None\n    no_price: Decimal | None = None\n\n    def __post_init__(self) -> None:\n        object.__setattr__(self, \"market_id\", MarketId(_require_text(str(self.market_id), \"market_id\")))\n        object.__setattr__(self, \"title\", _require_text(self.title, \"title\"))\n        object.__setattr__(self, \"category\", _require_text(self.category, \"category\"))\n        object.__setattr__(self, \"status\", _require_text(self.status, \"status\"))\n        for field_name in (\"yes_price\", \"no_price\"):\n            value = getattr(self, field_name)\n            if value is not None and (value < 0 or value > 1):\n                raise SnapshotValidationError(f\"{field_name} must be between 0 and 1\")\n\n\n@dataclass(frozen=True, slots=True)\nclass SnapshotConsensus:\n    market_id: MarketId\n    outcome: str\n    wallet_count: int\n    combined_shares: Decimal\n    combined_value: Decimal\n    combined_pnl: Decimal\n    conviction_score: Decimal\n    conviction_grade: str\n\n    def __post_init__(self) -> None:\n        object.__setattr__(self, \"market_id\", MarketId(_require_text(str(self.market_id), \"market_id\")))\n        object.__setattr__(self, \"outcome\", _require_text(self.outcome, \"outcome\"))\n        object.__setattr__(self, \"conviction_grade\", _require_text(self.conviction_grade, \"conviction_grade\"))\n        if self.wallet_count < 0:\n            raise SnapshotValidationError(\"wallet_count must be non-negative\")\n        object.__setattr__(self, \"combined_shares\", _require_non_negative(self.combined_shares, \"combined_shares\"))\n        object.__setattr__(self, \"combined_value\", _require_non_negative(self.combined_value, \"combined_value\"))\n        if self.conviction_score < 0 or self.conviction_score > 100:\n            raise SnapshotValidationError(\"conviction_score must be between 0 and 100\")\n\n\n@dataclass(frozen=True, slots=True)\nclass Snapshot:\n    metadata: SnapshotMetadata\n    wallets: tuple[SnapshotWallet, ...]\n    markets: tuple[SnapshotMarket, ...]\n    consensus: tuple[SnapshotConsensus, ...]\n    attributes: Mapping[str, Any]\n\n    @classmethod\n    def create(cls, *, metadata: SnapshotMetadata, wallets: Sequence[SnapshotWallet] = (), markets: Sequence[SnapshotMarket] = (), consensus: Sequence[SnapshotConsensus] = (), attributes: Mapping[str, Any] | None = None) -> \"Snapshot\":\n        snapshot = cls(metadata=metadata, wallets=tuple(wallets), markets=tuple(markets), consensus=tuple(consensus), attributes=dict(attributes or {}))\n        snapshot.validate_counts()\n        return snapshot\n\n    def validate_counts(self) -> None:\n        expected = (\n            (self.metadata.wallet_count, len(self.wallets), \"wallet_count\"),\n            (self.metadata.market_count, len(self.markets), \"market_count\"),\n            (self.metadata.consensus_count, len(self.consensus), \"consensus_count\"),\n        )\n        for declared, actual, field_name in expected:\n            if declared != actual:\n                raise SnapshotValidationError(f\"{field_name} mismatch: metadata={declared}, actual={actual}\")\n\n    def to_dict(self) -> dict[str, Any]:\n        def normalize(value: Any) -> Any:\n            if isinstance(value, Decimal):\n                return str(value)\n            if isinstance(value, datetime):\n                return value.isoformat()\n            if isinstance(value, dict):\n                return {key: normalize(item) for key, item in value.items()}\n            if isinstance(value, (list, tuple)):\n                return [normalize(item) for item in value]\n            return value\n\n        payload = {\n            \"metadata\": self.metadata.to_dict(),\n            \"wallets\": [asdict(item) for item in self.wallets],\n            \"markets\": [asdict(item) for item in self.markets],\n            \"consensus\": [asdict(item) for item in self.consensus],\n            \"attributes\": dict(self.attributes),\n        }\n        return normalize(payload)\n""",
"tests/snapshots/test_models.py": """from dataclasses import FrozenInstanceError\nfrom datetime import datetime, timezone\nfrom decimal import Decimal\n\nimport pytest\n\nfrom src.snapshots import Snapshot, SnapshotConsensus, SnapshotMetadata, SnapshotValidationError, SnapshotWallet\n\n\ndef metadata(**overrides):\n    values = {\n        \"snapshot_id\": \"snap-001\",\n        \"created_at\": datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc),\n        \"schema_version\": \"1.0\",\n        \"platform_version\": \"0.1\",\n        \"wallet_count\": 1,\n        \"market_count\": 0,\n        \"consensus_count\": 1,\n        \"checksum\": \"abc123\",\n    }\n    values.update(overrides)\n    return SnapshotMetadata(**values)\n\n\ndef wallet():\n    return SnapshotWallet(\n        wallet_id=\"0xabc\", market_id=\"market-1\", outcome=\"YES\",\n        shares=Decimal(\"10\"), average_price=Decimal(\"0.40\"),\n        current_price=Decimal(\"0.55\"), current_value=Decimal(\"5.50\"),\n        cash_pnl=Decimal(\"1.50\"), percent_pnl=Decimal(\"37.5\"),\n    )\n\n\ndef consensus():\n    return SnapshotConsensus(\n        market_id=\"market-1\", outcome=\"YES\", wallet_count=1,\n        combined_shares=Decimal(\"10\"), combined_value=Decimal(\"5.50\"),\n        combined_pnl=Decimal(\"1.50\"), conviction_score=Decimal(\"82.5\"),\n        conviction_grade=\"A\",\n    )\n\n\ndef test_snapshot_metadata_normalizes_timestamp_to_utc():\n    assert metadata().created_at.tzinfo == timezone.utc\n\n\ndef test_snapshot_metadata_is_immutable():\n    item = metadata()\n    with pytest.raises(FrozenInstanceError):\n        item.checksum = \"changed\"\n\n\ndef test_snapshot_create_validates_declared_counts():\n    item = Snapshot.create(metadata=metadata(), wallets=[wallet()], consensus=[consensus()])\n    assert item.metadata.snapshot_id == \"snap-001\"\n    assert len(item.wallets) == 1\n\n\ndef test_snapshot_rejects_count_mismatch():\n    with pytest.raises(SnapshotValidationError, match=\"wallet_count mismatch\"):\n        Snapshot.create(metadata=metadata(wallet_count=2), wallets=[wallet()], consensus=[consensus()])\n\n\ndef test_snapshot_serialization_converts_decimal_and_datetime():\n    item = Snapshot.create(metadata=metadata(), wallets=[wallet()], consensus=[consensus()], attributes={\"source\": \"test\"})\n    payload = item.to_dict()\n    assert payload[\"metadata\"][\"created_at\"].endswith(\"+00:00\")\n    assert payload[\"wallets\"][0][\"shares\"] == \"10\"\n\n\ndef test_metadata_rejects_naive_datetime():\n    with pytest.raises(SnapshotValidationError, match=\"timezone-aware\"):\n        metadata(created_at=datetime(2026, 7, 24, 12, 0))\n\n\ndef test_consensus_score_must_be_in_range():\n    with pytest.raises(SnapshotValidationError, match=\"between 0 and 100\"):\n        SnapshotConsensus(\n            market_id=\"market-1\", outcome=\"YES\", wallet_count=1,\n            combined_shares=Decimal(\"10\"), combined_value=Decimal(\"5\"),\n            combined_pnl=Decimal(\"0\"), conviction_score=Decimal(\"101\"),\n            conviction_grade=\"A\",\n        )\n""",
"tests/snapshots/test_exceptions.py": """from src.snapshots import SnapshotError, SnapshotIntegrityError, SnapshotReplayError, SnapshotStorageError, SnapshotValidationError\n\n\ndef test_snapshot_exception_hierarchy():\n    assert issubclass(SnapshotValidationError, SnapshotError)\n    assert issubclass(SnapshotStorageError, SnapshotError)\n    assert issubclass(SnapshotReplayError, SnapshotError)\n    assert issubclass(SnapshotIntegrityError, SnapshotError)\n""",
"docs/CORE-003-SPRINT-3.2-PHASE-1.md": """# CORE-003 Sprint 3.2 — Phase 1\n\n## Historical Snapshot Domain Layer\n\nImplemented:\n\n- Immutable snapshot aggregate\n- Snapshot metadata model\n- Wallet, market, and consensus state models\n- Snapshot-specific exception hierarchy\n- Typed identifiers\n- UTC and count validation\n- Serialization support\n- Unit tests\n\nNext: loader, validator service, SQLite storage, index, and replay iterator.\n""",
}


def find_root() -> Path:
    root = Path.cwd().resolve()
    missing = [name for name in ROOT_MARKERS if not (root / name).exists()]
    if missing:
        raise SystemExit("Run from project root. Missing: " + ", ".join(missing))
    return root


def create_backup(root: Path) -> Path:
    destination = root / "backups" / (
        "core_003_sprint_3_2_phase_1_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    destination.mkdir(parents=True, exist_ok=False)
    for relative in list(FILES) + ["CURRENT_SPRINT.md", "PROJECT_STATUS.md", "NEXT_TASK.md", "CHANGELOG.md"]:
        source = root / relative
        if source.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return destination


def write_files(root: Path) -> None:
    for relative, content in FILES.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        print(f"Installed {relative}")


def update_docs(root: Path) -> None:
    (root / "CURRENT_SPRINT.md").write_text(
        "# Current Sprint\n\nCORE-003 Sprint 3.2 — Historical Snapshot Framework\nPhase 1: Implemented; awaiting validation\n",
        encoding="utf-8", newline="\n"
    )
    (root / "NEXT_TASK.md").write_text(
        "# Next Task\n\nValidate Sprint 3.2 Phase 1, then build loader, validator, storage, index, and replay.\n",
        encoding="utf-8", newline="\n"
    )
    status = root / "PROJECT_STATUS.md"
    existing = status.read_text(encoding="utf-8") if status.exists() else "# Project Status\n"
    line = "- CORE-003 Sprint 3.2 Phase 1 Snapshot Domain Layer: Implemented; awaiting validation"
    if line not in existing:
        status.write_text(existing.rstrip() + "\n" + line + "\n", encoding="utf-8", newline="\n")
    changelog = root / "CHANGELOG.md"
    existing = changelog.read_text(encoding="utf-8") if changelog.exists() else "# Changelog\n"
    marker = "## CORE-003 Sprint 3.2 Phase 1"
    if marker not in existing:
        existing = existing.rstrip() + "\n\n" + marker + "\n\n- Added immutable snapshot domain models.\n- Added snapshot exceptions and typed identifiers.\n- Added validation, serialization, and tests.\n"
        changelog.write_text(existing, encoding="utf-8", newline="\n")
    print("Updated project documentation")


def main() -> int:
    root = find_root()
    print(f"Backup created: {create_backup(root)}")
    write_files(root)
    update_docs(root)
    print("\nCORE-003 Sprint 3.2 Phase 1 installed.")
    print("Run:")
    print("  python manage.py test")
    print("  python -m pytest tests/snapshots -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())