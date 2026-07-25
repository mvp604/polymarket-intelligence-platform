from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT_MARKERS = ("src", "tests", "manage.py")

FILES = {
"src/platform_capabilities/__init__.py": '''from .models import Capability, HealthCheckResult, HealthStatus
from .registry import CapabilityRegistry

__all__ = ["Capability", "CapabilityRegistry", "HealthCheckResult", "HealthStatus"]
''',
"src/platform_capabilities/models.py": '''from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Sequence


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    name: str
    status: HealthStatus
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)


HealthCheck = Callable[[], HealthCheckResult]


@dataclass(frozen=True, slots=True)
class Capability:
    capability_id: str
    name: str
    version: str
    description: str
    provides: Sequence[str] = field(default_factory=tuple)
    dependencies: Sequence[str] = field(default_factory=tuple)
    health_checks: Sequence[HealthCheck] = field(default_factory=tuple)
    enabled: bool = True

    def validate(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id cannot be empty")
        if not self.name.strip():
            raise ValueError("name cannot be empty")
        if not self.version.strip():
            raise ValueError("version cannot be empty")
''',
"src/platform_capabilities/checks.py": '''from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import HealthCheckResult, HealthStatus


def directory_exists(name: str, path: Path):
    def check() -> HealthCheckResult:
        if path.is_dir():
            return HealthCheckResult(name, HealthStatus.HEALTHY, f"Directory exists: {path}")
        return HealthCheckResult(name, HealthStatus.UNHEALTHY, f"Missing directory: {path}")
    return check


def file_exists(name: str, path: Path):
    def check() -> HealthCheckResult:
        if path.is_file():
            return HealthCheckResult(name, HealthStatus.HEALTHY, f"File exists: {path}")
        return HealthCheckResult(name, HealthStatus.UNHEALTHY, f"Missing file: {path}")
    return check


def sqlite_database_accessible(name: str, path: Path):
    def check() -> HealthCheckResult:
        if not path.is_file():
            return HealthCheckResult(name, HealthStatus.DEGRADED, f"Database file not found: {path}")
        try:
            with sqlite3.connect(path) as connection:
                connection.execute("SELECT 1").fetchone()
            return HealthCheckResult(name, HealthStatus.HEALTHY, f"SQLite accessible: {path}")
        except sqlite3.Error as exc:
            return HealthCheckResult(name, HealthStatus.UNHEALTHY, f"SQLite error: {exc}")
    return check
''',
"src/platform_capabilities/registry.py": '''from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict

from .models import Capability, HealthCheckResult, HealthStatus


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability, *, replace: bool = False) -> None:
        capability.validate()
        if capability.capability_id in self._capabilities and not replace:
            raise ValueError(f"Capability already registered: {capability.capability_id}")
        self._capabilities[capability.capability_id] = capability

    def get(self, capability_id: str) -> Capability:
        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise KeyError(f"Unknown capability: {capability_id}") from exc

    def list(self, *, enabled_only: bool = False) -> tuple[Capability, ...]:
        values = self._capabilities.values()
        if enabled_only:
            values = (item for item in values if item.enabled)
        return tuple(sorted(values, key=lambda item: item.capability_id))

    def validate_dependencies(self) -> dict[str, tuple[str, ...]]:
        installed = set(self._capabilities)
        missing = {}
        for capability in self.list(enabled_only=True):
            unresolved = tuple(d for d in capability.dependencies if d not in installed)
            if unresolved:
                missing[capability.capability_id] = unresolved
        return missing

    def dependency_order(self) -> tuple[str, ...]:
        missing = self.validate_dependencies()
        if missing:
            detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in missing.items())
            raise RuntimeError(f"Missing dependencies: {detail}")
        graph = {item.capability_id: set(item.dependencies) for item in self.list(enabled_only=True)}
        reverse = defaultdict(set)
        indegree = {node: len(deps) for node, deps in graph.items()}
        for node, deps in graph.items():
            for dep in deps:
                reverse[dep].add(node)
        ready = sorted(node for node, degree in indegree.items() if degree == 0)
        order = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for dependent in sorted(reverse[node]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort()
        if len(order) != len(graph):
            cyclic = sorted(node for node, degree in indegree.items() if degree > 0)
            raise RuntimeError(f"Dependency cycle detected: {', '.join(cyclic)}")
        return tuple(order)

    def run_health_checks(self) -> dict[str, tuple[HealthCheckResult, ...]]:
        results = {}
        for capability_id in self.dependency_order():
            capability = self.get(capability_id)
            checks = []
            for check in capability.health_checks:
                try:
                    checks.append(check())
                except Exception as exc:
                    checks.append(HealthCheckResult(getattr(check, "__name__", "health_check"), HealthStatus.UNHEALTHY, f"Unhandled error: {exc}"))
            results[capability_id] = tuple(checks)
        return results

    def overall_status(self) -> HealthStatus:
        statuses = [r.status for values in self.run_health_checks().values() for r in values]
        if not statuses:
            return HealthStatus.UNKNOWN
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def to_dict(self) -> dict:
        capabilities = []
        for capability in self.list():
            data = asdict(capability)
            data.pop("health_checks", None)
            capabilities.append(data)
        return {"capabilities": capabilities, "missing_dependencies": self.validate_dependencies()}
''',
"src/platform_capabilities/builtin.py": '''from __future__ import annotations

from pathlib import Path

from .checks import directory_exists, file_exists, sqlite_database_accessible
from .models import Capability
from .registry import CapabilityRegistry


def _find_database(root: Path) -> Path:
    preferred = root / "database" / "polymarket.db"
    if preferred.exists():
        return preferred
    matches = sorted((root / "database").glob("*.db"))
    return matches[0] if matches else preferred


def build_registry(root: Path) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    database_path = _find_database(root)
    registry.register(Capability("project.foundation", "Project Foundation", "0.1.0", "Core repository layout and management entry point.", ("repository_layout", "project_management"), health_checks=(directory_exists("source_directory", root / "src"), directory_exists("tests_directory", root / "tests"), file_exists("manage_entrypoint", root / "manage.py"))))
    registry.register(Capability("storage.sqlite", "SQLite Storage", "0.1.0", "Persistent local storage.", ("database", "historical_storage"), ("project.foundation",), (directory_exists("database_directory", root / "database"), sqlite_database_accessible("sqlite_database", database_path))))
    registry.register(Capability("intelligence.classification", "Market Classification", "2.0.0", "Market taxonomy and league detection.", ("market_classification", "league_detection"), ("project.foundation",), (directory_exists("classification_source", root / "src"),)))
    registry.register(Capability("intelligence.wallets", "Wallet Intelligence", "1.0.0", "Wallet profiling and rankings.", ("wallet_profiling", "wallet_rankings"), ("storage.sqlite", "intelligence.classification"), (directory_exists("wallet_source", root / "src"),)))
    registry.register(Capability("intelligence.consensus", "Consensus and Conviction", "1.0.0", "Weighted consensus and conviction scoring.", ("consensus_scoring", "conviction_scoring"), ("storage.sqlite", "intelligence.wallets"), (directory_exists("consensus_source", root / "src"),)))
    registry.register(Capability("platform.runtime", "Platform Runtime", "1.0.0", "Runtime orchestration.", ("runtime", "orchestration"), ("project.foundation",), (directory_exists("runtime_directory", root / "runtime"),)))
    registry.register(Capability("platform.capability_registry", "Platform Capability Registry", "0.1.0", "Capability discovery, dependency validation, and health reporting.", ("capability_registry", "dependency_validation", "health_reporting"), ("project.foundation",), (file_exists("registry_module", root / "src" / "platform_capabilities" / "registry.py"),)))
    return registry
''',
"src/platform_capabilities/reporting.py": '''from __future__ import annotations

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
''',
"tests/test_platform_capabilities.py": '''from pathlib import Path

import pytest

from src.platform_capabilities.builtin import build_registry
from src.platform_capabilities.models import Capability
from src.platform_capabilities.registry import CapabilityRegistry


def test_duplicate_rejected() -> None:
    registry = CapabilityRegistry()
    capability = Capability("example", "Example", "1.0.0", "Example")
    registry.register(capability)
    with pytest.raises(ValueError):
        registry.register(capability)


def test_missing_dependency_reported() -> None:
    registry = CapabilityRegistry()
    registry.register(Capability("dependent", "Dependent", "1.0.0", "Needs dependency", dependencies=("missing",)))
    assert registry.validate_dependencies() == {"dependent": ("missing",)}


def test_dependency_order() -> None:
    registry = CapabilityRegistry()
    registry.register(Capability("base", "Base", "1.0.0", "Base"))
    registry.register(Capability("child", "Child", "1.0.0", "Child", dependencies=("base",)))
    assert registry.dependency_order() == ("base", "child")


def test_builtin_registry(tmp_path: Path) -> None:
    for directory in ("src", "tests", "database", "runtime"):
        (tmp_path / directory).mkdir()
    (tmp_path / "manage.py").write_text("# test", encoding="utf-8")
    package = tmp_path / "src" / "platform_capabilities"
    package.mkdir()
    (package / "registry.py").write_text("# test", encoding="utf-8")
    ids = {item.capability_id for item in build_registry(tmp_path).list()}
    assert "platform.capability_registry" in ids
''',
"docs/CORE-003-SPRINT-3.0.md": '''# CORE-003 — Sprint 3.0\n\n## Platform Capability Registry\n\nStatus: Implemented\n\nProvides capability registration, dependency validation, health checks, JSON diagnostics, tests, and `manage.py` integration.\n\n## Commands\n\n```powershell\npython manage.py features\npython manage.py health\npython manage.py doctor\npython manage.py test\n```\n'''
}

MANAGE = '''from __future__ import annotations

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
        "README.md": "# Polymarket Intelligence Platform\\n",
        "ROADMAP.md": "# Roadmap\\n\\n- CORE-001: Complete\\n- CORE-002: Complete\\n- CORE-003: Active\\n",
        "CURRENT_SPRINT.md": "# Current Sprint\\n\\nCORE-003 Sprint 3.1 — Historical Snapshot Loader\\n",
        "PROJECT_STATUS.md": "# Project Status\\n\\nCORE-003 is active.\\n",
        "NEXT_TASK.md": "# Next Task\\n\\nCORE-003 Sprint 3.1 — Historical Snapshot Loader\\n",
        "ARCHITECTURE.md": "# Architecture\\n\\nSee docs/CORE-003-SPRINT-3.0.md.\\n",
        "DECISIONS.md": "# Decisions\\n\\nCapability Registry adopted.\\n",
        "CHANGELOG.md": "# Changelog\\n",
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
    return subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=False).returncode


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
'''


def main() -> int:
    root = Path.cwd().resolve()
    missing = [marker for marker in ROOT_MARKERS if not (root / marker).exists()]
    if missing:
        print("ERROR: Run this installer from the project root.")
        print("Missing:", ", ".join(missing))
        return 1

    backup = root / "backups" / ("core_003_sprint_3_0_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    backup.mkdir(parents=True, exist_ok=False)
    for relative in ["manage.py", *FILES.keys()]:
        source = root / relative
        if source.is_file():
            target = backup / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print(f"Backup created: {backup}")

    for relative, content in FILES.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        print(f"Installed {relative}")

    (root / "manage.py").write_text(MANAGE, encoding="utf-8", newline="\n")
    print("Installed manage.py")

    updates = {
        "CURRENT_SPRINT.md": "# Current Sprint\n\nCORE-003 Sprint 3.1 — Historical Snapshot Loader\n",
        "PROJECT_STATUS.md": "# Project Status\n\n- CORE-001: Complete\n- CORE-002: Complete\n- CORE-003: Active\n- Sprint 3.0 Platform Capability Registry: Implemented\n",
        "NEXT_TASK.md": "# Next Task\n\nBuild CORE-003 Sprint 3.1 — Historical Snapshot Loader.\n",
    }
    for name, content in updates.items():
        (root / name).write_text(content, encoding="utf-8", newline="\n")
        print(f"Updated {name}")

    changelog = root / "CHANGELOG.md"
    existing = changelog.read_text(encoding="utf-8") if changelog.exists() else "# Changelog\n"
    if "## CORE-003 Sprint 3.0" not in existing:
        changelog.write_text(existing.rstrip() + "\n\n## CORE-003 Sprint 3.0\n\n- Added Platform Capability Registry.\n- Added dependency validation and health checks.\n- Added features, health, doctor, and test commands.\n", encoding="utf-8", newline="\n")

    print("\nCORE-003 Sprint 3.0 installed.")
    print("Run:")
    print("  python manage.py features")
    print("  python manage.py health")
    print("  python manage.py test")
    print("  python manage.py doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())