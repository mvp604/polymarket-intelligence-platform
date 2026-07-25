from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path.cwd().resolve()
validator_path = root / "src" / "snapshots" / "validator.py"

if not validator_path.exists():
    raise SystemExit(
        "Run this script from the project root. "
        "Missing src/snapshots/validator.py"
    )

backup_dir = (
    root
    / "backups"
    / (
        "core_003_sprint_3_3_checksum_ordering_fix_v2_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
)
backup_file = backup_dir / "src" / "snapshots" / "validator.py"
backup_file.parent.mkdir(parents=True, exist_ok=False)
shutil.copy2(validator_path, backup_file)

validator_source = 'from __future__ import annotations\n\nimport hashlib\nimport json\nfrom dataclasses import replace\n\nfrom .exceptions import SnapshotIntegrityError, SnapshotValidationError\nfrom .models import Snapshot\n\n\nclass SnapshotValidator:\n    def validate(\n        self,\n        snapshot: Snapshot,\n        *,\n        verify_checksum: bool = True,\n    ) -> None:\n        snapshot.validate_counts()\n        self._validate_unique_wallet_positions(snapshot)\n        self._validate_unique_markets(snapshot)\n        self._validate_consensus_markets(snapshot)\n\n        if verify_checksum:\n            expected = self.calculate_checksum(snapshot)\n            if snapshot.metadata.checksum != expected:\n                raise SnapshotIntegrityError(\n                    "snapshot checksum mismatch: "\n                    f"metadata={snapshot.metadata.checksum}, "\n                    f"calculated={expected}"\n                )\n\n    def calculate_checksum(self, snapshot: Snapshot) -> str:\n        payload = snapshot.to_dict()\n        payload["metadata"]["checksum"] = ""\n\n        payload["wallets"] = sorted(\n            payload.get("wallets", []),\n            key=lambda item: (\n                str(item.get("wallet_id", "")),\n                str(item.get("market_id", "")),\n                str(item.get("outcome", "")),\n            ),\n        )\n        payload["markets"] = sorted(\n            payload.get("markets", []),\n            key=lambda item: str(item.get("market_id", "")),\n        )\n        payload["consensus"] = sorted(\n            payload.get("consensus", []),\n            key=lambda item: (\n                str(item.get("market_id", "")),\n                str(item.get("outcome", "")),\n            ),\n        )\n\n        encoded = json.dumps(\n            payload,\n            sort_keys=True,\n            separators=(",", ":"),\n            ensure_ascii=False,\n        ).encode("utf-8")\n        return hashlib.sha256(encoded).hexdigest()\n\n    def with_checksum(self, snapshot: Snapshot) -> Snapshot:\n        checksum = self.calculate_checksum(snapshot)\n        metadata = replace(snapshot.metadata, checksum=checksum)\n        return replace(snapshot, metadata=metadata)\n\n    @staticmethod\n    def _validate_unique_wallet_positions(snapshot: Snapshot) -> None:\n        seen: set[tuple[str, str, str]] = set()\n        for item in snapshot.wallets:\n            key = (str(item.wallet_id), str(item.market_id), item.outcome)\n            if key in seen:\n                raise SnapshotValidationError(\n                    "duplicate wallet position: " + "|".join(key)\n                )\n            seen.add(key)\n\n    @staticmethod\n    def _validate_unique_markets(snapshot: Snapshot) -> None:\n        seen: set[str] = set()\n        for item in snapshot.markets:\n            market_id = str(item.market_id)\n            if market_id in seen:\n                raise SnapshotValidationError(\n                    f"duplicate market_id: {market_id}"\n                )\n            seen.add(market_id)\n\n    @staticmethod\n    def _validate_consensus_markets(snapshot: Snapshot) -> None:\n        market_ids = {str(item.market_id) for item in snapshot.markets}\n        for item in snapshot.consensus:\n            if market_ids and str(item.market_id) not in market_ids:\n                raise SnapshotValidationError(\n                    f"consensus references unknown market: {item.market_id}"\n                )\n'
compile(validator_source, str(validator_path), "exec")
validator_path.write_text(
    validator_source,
    encoding="utf-8",
    newline="\n",
)

database_paths = []
for candidate in root.rglob("*.db"):
    if any(part.lower() == "backups" for part in candidate.parts):
        continue
    try:
        with sqlite3.connect(candidate) as connection:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='historical_snapshots'"
            ).fetchone()
        if exists:
            database_paths.append(candidate)
    except sqlite3.Error:
        continue

print(f"Backup created: {backup_dir}")
print("Replaced src/snapshots/validator.py")
print("Python syntax validation passed")

if not database_paths:
    print("No database containing historical_snapshots was found.")
    print("Validator was fixed, but existing checksum migration was skipped.")
else:
    sys.path.insert(0, str(root))

    from src.snapshots.storage import SQLiteSnapshotStorage
    from src.snapshots.validator import SnapshotValidator

    migrated = 0

    for database_path in database_paths:
        validator = SnapshotValidator()
        storage = SQLiteSnapshotStorage(
            database_path,
            validator=validator,
        )

        metadata_items = storage.list_metadata()
        original_validate = validator.validate

        def validate_without_checksum(snapshot, *, verify_checksum=True):
            return original_validate(snapshot, verify_checksum=False)

        validator.validate = validate_without_checksum

        snapshots = []
        try:
            for metadata in metadata_items:
                snapshots.append(
                    storage.load(str(metadata.snapshot_id))
                )
        finally:
            validator.validate = original_validate

        with sqlite3.connect(database_path) as connection:
            for snapshot in snapshots:
                checksum = validator.calculate_checksum(snapshot)
                connection.execute(
                    "UPDATE historical_snapshots "
                    "SET checksum = ? WHERE snapshot_id = ?",
                    (
                        checksum,
                        str(snapshot.metadata.snapshot_id),
                    ),
                )
                migrated += 1
            connection.commit()

        print(f"Migrated checksums in: {database_path}")

    print(f"Historical snapshots migrated: {migrated}")

print()
print("Run:")
print("  python manage.py test")
print("  python -m pytest tests/snapshots -q")
print("  python snapshot_manage.py list")
print("  python snapshot_manage.py inspect live-428f01dc002d21b8345fefed")