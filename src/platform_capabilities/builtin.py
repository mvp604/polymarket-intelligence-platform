from __future__ import annotations

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
