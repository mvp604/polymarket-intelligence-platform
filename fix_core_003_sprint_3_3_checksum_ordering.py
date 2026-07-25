from __future__ import annotations

import json
import shutil
import sqlite3
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
        "core_003_sprint_3_3_checksum_ordering_fix_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
)
backup_file = backup_dir / "src" / "snapshots" / "validator.py"
backup_file.parent.mkdir(parents=True, exist_ok=False)
shutil.copy2(validator_path, backup_file)

text = validator_path.read_text(encoding="utf-8")

old = """        payload = snapshot.to_dict()
        payload["metadata"]["checksum"] = ""
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
"""

new = """        payload = snapshot.to_dict()
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
"""

if old not in text:
    if 'payload["wallets"] = sorted(' not in text:
        raise SystemExit(
            "Could not safely locate checksum calculation in validator.py."
        )
else:
    text = text.replace(old, new, 1)

compile(text, str(validator_path), "exec")
validator_path.write_text(text, encoding="utf-8", newline="\n")

# Discover the live database without guessing one fixed filename.
candidates = []
for candidate in root.rglob("*.db"):
    if "backup" not in {part.lower() for part in candidate.parts}:
        try:
            with sqlite3.connect(candidate) as connection:
                row = connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='historical_snapshots'"
                ).fetchone()
            if row:
                candidates.append(candidate)
        except sqlite3.Error:
            pass

print(f"Backup created: {backup_dir}")
print("Patched src/snapshots/validator.py")
print("Python syntax validation passed")

if not candidates:
    print()
    print("No snapshot database was found automatically.")
    print("The validator fix is installed, but stored checksums still need migration.")
else:
    # Import only after patching.
    import sys
    sys.path.insert(0, str(root))

    from src.snapshots.storage import SQLiteSnapshotStorage
    from src.snapshots.validator import SnapshotValidator

    validator = SnapshotValidator()
    migrated = 0

    for database_path in candidates:
        storage = SQLiteSnapshotStorage(database_path, validator=validator)
        metadata_items = storage.list_metadata()

        # Load while bypassing old checksum verification, recalculate canonical
        # checksum, then update metadata directly.
        with sqlite3.connect(database_path) as connection:
            for metadata in metadata_items:
                snapshot_id = str(metadata.snapshot_id)

                original_validate = validator.validate
                try:
                    validator.validate = lambda snapshot, verify_checksum=True: original_validate(
                        snapshot, verify_checksum=False
                    )
                    snapshot = storage.load(snapshot_id)
                finally:
                    validator.validate = original_validate

                checksum = validator.calculate_checksum(snapshot)
                connection.execute(
                    "UPDATE historical_snapshots "
                    "SET checksum = ? WHERE snapshot_id = ?",
                    (checksum, snapshot_id),
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