from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
BACKUP_DIR = PROJECT_ROOT / "database" / "backups"


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    destination = BACKUP_DIR / f"polymarket_pre_compatibility_{stamp}.db"

    with sqlite3.connect(DATABASE_PATH) as source:
        with sqlite3.connect(destination) as target:
            source.backup(target)

    print(f"Database backup created: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
