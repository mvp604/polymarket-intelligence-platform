from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOC_FILES = ("README.md", "ROADMAP.md", "CURRENT_SPRINT.md", "PROJECT_STATUS.md", "NEXT_TASK.md", "ARCHITECTURE.md", "DECISIONS.md", "CHANGELOG.md")


def ensure_root() -> None:
    missing = [name for name in ("src", "tests") if not (ROOT / name).exists()]
    if missing:
        raise SystemExit("Run manage.py from the project root. Missing: " + ", ".join(missing))


def command_init(_):
    ensure_root()
    defaults = {
        "README.md": "# Polymarket Intelligence Platform\n",
        "ROADMAP.md": "# Roadmap\n\n- CORE-001: Complete\n- CORE-002: Complete\n- CORE-003: Active\n",
        "CURRENT_SPRINT.md": "# Current Sprint\n\nCORE-003 Sprint 3.1 — Historical Snapshot Loader\n",
        "PROJECT_STATUS.md": "# Project Status\n\nCORE-003 is active.\n",
        "NEXT_TASK.md": "# Next Task\n\nCORE-003 Sprint 3.1 — Historical Snapshot Loader\n",
        "ARCHITECTURE.md": "# Architecture\n\nSee docs/CORE-003-SPRINT-3.0.md.\n",
        "DECISIONS.md": "# Decisions\n\nCapability Registry adopted.\n",
        "CHANGELOG.md": "# Changelog\n",
    }
    for name, content in defaults.items():
        path = ROOT / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            print(f"Created {name}")
        else:
            print(f"Kept {name}")
    print("CORE-001 COMPLETE")
    return 0


def command_status(_):
    ensure_root()
    missing = []
    for name in DOC_FILES:
        if (ROOT / name).exists():
            print(f"OK {name}")
        else:
            print(f"MISSING {name}")
            missing.append(name)
    from src.platform_capabilities.builtin import build_registry
    registry = build_registry(ROOT)
    print(f"Capabilities: {len(registry.list())}")
    print(f"Health: {registry.overall_status().value.upper()}")
    return 1 if missing else 0


def command_features(_):
    ensure_root()
    from src.platform_capabilities.builtin import build_registry
    from src.platform_capabilities.reporting import print_capabilities
    print_capabilities(build_registry(ROOT))
    return 0


def command_health(_):
    ensure_root()
    from src.platform_capabilities.builtin import build_registry
    from src.platform_capabilities.reporting import print_health
    return print_health(build_registry(ROOT))


def command_doctor(_):
    ensure_root()
    from src.platform_capabilities.builtin import build_registry
    from src.platform_capabilities.reporting import print_health, write_json_report
    registry = build_registry(ROOT)
    code = print_health(registry)
    path = write_json_report(registry, ROOT / "reports" / "platform_health.json")
    print(f"Diagnostic report: {path}")
    return code


def command_test(_):
    ensure_root()
    return subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"], cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Polymarket platform manager")
    subs = parser.add_subparsers(dest="command", required=True)
    for name, handler in {"init": command_init, "status": command_status, "features": command_features, "health": command_health, "doctor": command_doctor, "test": command_test}.items():
        command = subs.add_parser(name)
        command.set_defaults(handler=handler)
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
