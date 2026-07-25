from __future__ import annotations

import csv
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from src.outcome_resolution_eod_reporting_v1 import (
    ResolutionRecord,
    ensure_schema,
    upsert_resolution,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python tools/import_market_resolutions.py path/to/resolutions.csv",
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
                "market_id",
                "outcome",
                "final_result",
                "resolution_status",
                "resolution_source",
                "resolved_at",
            }
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise RuntimeError(
                    "Missing CSV columns: " + ", ".join(sorted(missing))
                )

            for row in reader:
                resolved_value = row.get("resolved_value")
                record = ResolutionRecord(
                    market_id=row["market_id"].strip(),
                    outcome=row["outcome"].strip(),
                    final_result=row["final_result"].strip(),
                    resolved_value=(
                        float(resolved_value)
                        if resolved_value not in (None, "")
                        else None
                    ),
                    resolution_status=row["resolution_status"].strip(),
                    source=row["resolution_source"].strip(),
                    resolved_at=row["resolved_at"].strip(),
                    notes=(row.get("notes") or "").strip() or None,
                )
                upsert_resolution(connection, record)
                imported += 1

        connection.commit()

    print(f"Imported or updated {imported:,} market resolutions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
