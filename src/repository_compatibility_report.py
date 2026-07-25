from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "reports" / "repository_compatibility.json"


def main() -> int:
    if not REPORT_PATH.exists():
        print(
            "Compatibility report not found. Run: "
            "python src/repository_schema_discovery.py",
            file=sys.stderr,
        )
        return 1

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    compatibility = report["compatibility"]

    print("=" * 88)
    print("REPOSITORY COMPATIBILITY REPORT")
    print("=" * 88)

    for table, status in compatibility["known_tables"].items():
        print()
        print(table)
        print("-" * len(table))
        print(f"Exists: {status['exists']}")
        if status["exists"]:
            for column in status["columns"]:
                print(f"  - {column}")

    print()
    print("LEGACY / BACKUP OBJECTS")
    print("-" * 88)
    legacy = compatibility["legacy_or_backup_objects"]
    if legacy:
        for name in legacy:
            print(f"  - {name}")
    else:
        print("  None")

    print()
    print("WARNINGS")
    print("-" * 88)
    warnings = compatibility["warnings"]
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  None")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
