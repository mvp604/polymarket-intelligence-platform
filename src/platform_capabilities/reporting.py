from __future__ import annotations

import json
from pathlib import Path

from .models import HealthStatus


def print_capabilities(registry) -> None:
    print("Platform Capabilities")
    print("=" * 72)
    for capability in registry.list():
        state = "enabled" if capability.enabled else "disabled"
        print(f"{capability.capability_id:<38} {capability.version:<10} {state}")
        print(f"  {capability.name}: {capability.description}")
        if capability.dependencies:
            print(f"  depends on: {', '.join(capability.dependencies)}")
        if capability.provides:
            print(f"  provides: {', '.join(capability.provides)}")


def print_health(registry) -> int:
    print("Platform Health")
    print("=" * 72)
    failures = 0
    for capability_id, checks in registry.run_health_checks().items():
        print(capability_id)
        if not checks:
            print("  [UNKNOWN] No checks registered")
        for check in checks:
            print(f"  [{check.status.value.upper():<9}] {check.name}: {check.message}")
            failures += int(check.status == HealthStatus.UNHEALTHY)
    print("-" * 72)
    print(f"Overall: {registry.overall_status().value.upper()}")
    return 1 if failures else 0


def write_json_report(registry, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = registry.to_dict()
    payload["health"] = {cid: [{"name": r.name, "status": r.status.value, "message": r.message, "details": dict(r.details)} for r in results] for cid, results in registry.run_health_checks().items()}
    payload["overall_status"] = registry.overall_status().value
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination
