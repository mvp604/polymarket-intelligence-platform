from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.outcome_resolution_reporting_v2 import (
    ResolutionRecord,
    upsert_resolution,
)
from src.outcome_resolution_schema_v2 import (
    DATABASE_PATH,
    ensure_schema,
)


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python tools/import_market_resolutions_v2.py "
            "path/to/resolutions.csv",
            file=sys.stderr,
        )
        return 1

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"File not found: {csv_path}", file=sys.stderr)
        return 1

    imported = 0
    with sqlite3.connect(DATABASE_PATH) as connection:
        ensure_schema(connection)
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "market_id", "outcome", "final_result",
                "resolution_status", "resolution_source",
            }
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise RuntimeError(
                    "Missing CSV columns: " + ", ".join(sorted(missing))
                )

            for row in reader:
                value = (row.get("resolved_value") or "").strip()
                record = ResolutionRecord(
                    market_id=row["market_id"].strip(),
                    outcome=row["outcome"].strip(),
                    final_result=row["final_result"].strip(),
                    resolved_value=float(value) if value else None,
                    resolution_status=row["resolution_status"].strip(),
                    source=row["resolution_source"].strip(),
                    resolved_at=(row.get("resolved_at") or "").strip() or None,
                    notes=(row.get("notes") or "").strip() or None,
                )
                upsert_resolution(connection, record)
                imported += 1
        connection.commit()

    print(f"Imported or updated {imported:,} market resolutions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
