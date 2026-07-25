from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "reports" / "repository_compatibility.json"
CAPABILITIES_PATH = PROJECT_ROOT / "config" / "engine_capabilities.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not REPORT_PATH.exists():
        print(
            "Run repository discovery first: "
            "python src/repository_schema_discovery.py",
            file=sys.stderr,
        )
        return 1
    if not CAPABILITIES_PATH.exists():
        print(
            f"Capabilities file missing: {CAPABILITIES_PATH}",
            file=sys.stderr,
        )
        return 1

    report = load_json(REPORT_PATH)
    capabilities = load_json(CAPABILITIES_PATH)
    failures = 0

    print("=" * 96)
    print("ENGINE CAPABILITY VALIDATOR")
    print("=" * 96)

    for engine_name, requirements in capabilities["engines"].items():
        missing_tables: list[str] = []
        missing_columns: list[str] = []
        missing_views: list[str] = []

        for table_name, required_columns in requirements.get(
            "tables", {}
        ).items():
            table = report["tables"].get(table_name)
            if not table:
                missing_tables.append(table_name)
                continue
            available = {
                column["name"] for column in table["columns"]
            }
            for column in required_columns:
                if column not in available:
                    missing_columns.append(
                        f"{table_name}.{column}"
                    )

        for view_name in requirements.get("views", []):
            if view_name not in report["views"]:
                missing_views.append(view_name)

        healthy = not (
            missing_tables or missing_columns or missing_views
        )
        failures += int(not healthy)

        print(f"{engine_name:<44} {'READY' if healthy else 'BLOCKED'}")
        if missing_tables:
            print("  missing tables: " + ", ".join(missing_tables))
        if missing_columns:
            print("  missing columns: " + ", ".join(missing_columns))
        if missing_views:
            print("  missing views: " + ", ".join(missing_views))

    print("=" * 96)
    print(
        "OVERALL STATUS: "
        + ("READY" if failures == 0 else "COMPATIBILITY WORK REQUIRED")
    )
    print("=" * 96)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
