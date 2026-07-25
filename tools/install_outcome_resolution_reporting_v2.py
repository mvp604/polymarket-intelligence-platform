from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.outcome_resolution_schema_v2 import DATABASE_PATH, ensure_schema


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    with sqlite3.connect(DATABASE_PATH) as connection:
        repairs = ensure_schema(connection)
        connection.commit()

    print("Outcome Resolution & Reporting v2 schema installed.")
    if repairs:
        print("Repaired missing columns:")
        for repair in repairs:
            print(f"  - {repair}")
    else:
        print("No schema repairs were required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
