from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "automation" / "platform_automation.json"
    database_path = project_root / "database" / "polymarket.db"

    errors: list[str] = []
    warnings: list[str] = []

    print("=" * 92)
    print("POLYMARKET PLATFORM PRE-FLIGHT CHECK")
    print("=" * 92)

    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        print(f"Config: OK | {config_path}")
    except Exception as exc:
        errors.append(f"Config load failed: {exc}")
        config = {}

    steps = config.get("steps", [])
    print(f"Configured steps: {len(steps)}")

    seen_names: set[str] = set()

    for index, step in enumerate(steps, start=1):
        name = str(step.get("name", f"step_{index}"))
        module = step.get("module")
        required = bool(step.get("required", True))

        if name in seen_names:
            warnings.append(f"Duplicate step name: {name}")
        seen_names.add(name)

        if not module:
            warnings.append(f"{name}: no module configured")
            continue

        if importlib.util.find_spec(str(module)) is None:
            message = f"{name}: module not found: {module}"
            if required:
                errors.append(message)
            else:
                warnings.append(message)
        else:
            print(f"[OK] {name:<30} {module}")

    if not database_path.exists():
        errors.append(f"Database not found: {database_path}")
    else:
        try:
            with sqlite3.connect(database_path) as connection:
                result = connection.execute("PRAGMA integrity_check").fetchone()
            status = result[0] if result else "unknown"
            print(f"Database integrity: {status}")
            if status != "ok":
                errors.append(f"Database integrity failed: {status}")
        except Exception as exc:
            errors.append(f"Database check failed: {exc}")

    print("-" * 92)

    if warnings:
        print("WARNINGS")
        for item in warnings:
            print(f"  - {item}")

    if errors:
        print("ERRORS")
        for item in errors:
            print(f"  - {item}")
        print("=" * 92)
        print("PRE-FLIGHT STATUS: FAILED")
        return 1

    print("=" * 92)
    print("PRE-FLIGHT STATUS: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())