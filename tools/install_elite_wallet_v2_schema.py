from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
SQL_PATH = PROJECT_ROOT / "migrations" / "elite_wallet_v2_supporting_schema.sql"


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1
    if not SQL_PATH.exists():
        print(f"Migration SQL not found: {SQL_PATH}", file=sys.stderr)
        return 1

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.executescript(SQL_PATH.read_text(encoding="utf-8"))
        connection.commit()

    print("Elite Wallet Intelligence v2 supporting schema installed.")
    print("Existing elite_wallet_profiles was preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
