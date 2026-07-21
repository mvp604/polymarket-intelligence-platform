from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INVENTORY_FILE = (
    PROJECT_ROOT
    / "reports"
    / "architecture"
    / "operational_module_inventory.json"
)

REGISTRY_FILE = (
    PROJECT_ROOT
    / "config"
    / "operations"
    / "production_registry.draft.json"
)

REVIEW_FILE = (
    PROJECT_ROOT
    / "reports"
    / "operations"
    / "production_registry_review.txt"
)


PRODUCTION_CANDIDATE_NAMES = {
    "architecture_loader.py",
    "architecture_registry.py",
    "canonical_market_identity_engine.py",
    "continuous_master_pipeline.py",
    "institutional_consensus_engine.py",
    "institutional_decision_engine.py",
    "institutional_learning_engine.py",
    "institutional_learning_outcome_engine.py",
    "market_resolution_engine.py",
    "market_status_engine.py",
    "model_evaluation_calibration_engine.py",
    "official_wallet_activity_engine.py",
    "opportunity_ranking_engine.py",
    "position_evolution_engine.py",
    "price_history_engine.py",
    "run_platform.py",
    "signal_fusion_engine.py",
    "smart_money_flow_engine.py",
    "wallet_performance_engine.py",
    "wallet_rating_engine.py",
    "wallet_tracker.py",
}


BACKUP_PATTERNS = (
    r"_backup(?:_|\.py)",
    r"_baseline(?:_|\.py)",
    r"_before_",
    r"_v\d+_backup",
    r"backup_\d{8}",
)


DIAGNOSTIC_PATTERNS = (
    "audit",
    "diagnostic",
    "inspect_",
    "validation_gate",
    "validator",
    "coverage",
    "failure_analysis",
)


MIGRATION_PATTERNS = (
    "migrate_",
    "migration",
    "backfill",
    "reconciliation",
    "synchronizer",
)


DASHBOARD_PATTERNS = (
    "dashboard",
    "pages\\",
    "pages/",
)


EXPERIMENTAL_PATTERNS = (
    "test_",
    "_v2.py",
    "_v3.py",
    "experimental",
    "prototype",
    "research",
)


OPERATIONAL_CLASSIFICATIONS = {
    "INGESTION",
    "MARKET_INTELLIGENCE",
    "WALLET_INTELLIGENCE",
    "DECISION",
    "LEARNING",
    "ORCHESTRATION",
    "DELIVERY",
    "DATA",
}


DEFAULT_TIMEOUT_SECONDS = {
    "INGESTION": 300,
    "MARKET_INTELLIGENCE": 180,
    "WALLET_INTELLIGENCE": 300,
    "DECISION": 120,
    "LEARNING": 300,
    "ORCHESTRATION": 600,
    "DELIVERY": 60,
    "DATA": 180,
    "EXECUTABLE_UNKNOWN": 120,
    "LIBRARY": 0,
    "SYNTAX_ERROR": 0,
}


DEFAULT_SCHEDULE_SECONDS = {
    "INGESTION": 300,
    "MARKET_INTELLIGENCE": 300,
    "WALLET_INTELLIGENCE": 600,
    "DECISION": 300,
    "LEARNING": 3600,
    "ORCHESTRATION": 300,
    "DELIVERY": 60,
    "DATA": 900,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_path(value: str) -> str:
    return value.replace("/", "\\").lower()


def filename_from_path(value: str) -> str:
    return Path(value.replace("\\", "/")).name.lower()


def contains_pattern(
    value: str,
    patterns: tuple[str, ...],
) -> bool:
    lowered = normalized_path(value)

    return any(
        pattern.lower() in lowered
        for pattern in patterns
    )


def matches_backup_pattern(value: str) -> bool:
    lowered = normalized_path(value)

    return any(
        re.search(pattern, lowered)
        for pattern in BACKUP_PATTERNS
    )


def stable_module_id(path: str) -> str:
    digest = hashlib.sha256(
        path.encode("utf-8")
    ).hexdigest()[:12]

    name = Path(
        path.replace("\\", "/")
    ).stem.lower()

    safe_name = re.sub(
        r"[^a-z0-9]+",
        "_",
        name,
    ).strip("_")

    return f"{safe_name}_{digest}"


def determine_lifecycle(
    module: dict[str, Any],
) -> tuple[str, list[str]]:
    path = str(module["path"])
    filename = filename_from_path(path)
    syntax_valid = bool(module["syntax_valid"])
    classification = str(module["classification"])

    reasons: list[str] = []

    if not syntax_valid:
        reasons.append(
            "Module failed AST syntax parsing."
        )
        return "QUARANTINED_SYNTAX_ERROR", reasons

    if matches_backup_pattern(path):
        reasons.append(
            "Filename matches a backup or historical-version pattern."
        )
        return "BACKUP", reasons

    if contains_pattern(path, DASHBOARD_PATTERNS):
        reasons.append(
            "Module appears to be part of the dashboard or UI layer."
        )
        return "DASHBOARD", reasons

    if contains_pattern(path, MIGRATION_PATTERNS):
        reasons.append(
            "Module appears to perform migration, backfill, "
            "synchronization, or reconciliation."
        )
        return "MIGRATION", reasons

    if contains_pattern(path, DIAGNOSTIC_PATTERNS):
        reasons.append(
            "Module appears to be an audit, diagnostic, inspection, "
            "coverage, or validation utility."
        )
        return "DIAGNOSTIC", reasons

    if contains_pattern(path, EXPERIMENTAL_PATTERNS):
        reasons.append(
            "Filename suggests testing, research, experimentation, "
            "or an alternate version."
        )
        return "EXPERIMENTAL", reasons

    if filename in PRODUCTION_CANDIDATE_NAMES:
        reasons.append(
            "Module is part of the initial operational core candidate set."
        )
        return "PRODUCTION_CANDIDATE", reasons

    if classification == "LIBRARY":
        reasons.append(
            "Module has no detected executable entry point."
        )
        return "LIBRARY", reasons

    if classification in OPERATIONAL_CLASSIFICATIONS:
        reasons.append(
            "Module belongs to an operational service domain but "
            "requires manual production approval."
        )
        return "EXPERIMENTAL", reasons

    reasons.append(
        "Module role is not sufficiently clear for production approval."
    )
    return "EXPERIMENTAL", reasons


def determine_execution_mode(
    module: dict[str, Any],
    lifecycle: str,
) -> str:
    if lifecycle in {
        "BACKUP",
        "LIBRARY",
        "QUARANTINED_SYNTAX_ERROR",
        "DASHBOARD",
    }:
        return "NEVER"

    entry_points = module.get(
        "likely_entry_points",
        [],
    )

    if "run_pipeline" in entry_points:
        return "FUNCTION"

    if "run" in entry_points:
        return "FUNCTION"

    if "main" in entry_points:
        return "SUBPROCESS"

    if module.get("has_main_guard"):
        return "SUBPROCESS"

    return "MANUAL"


def determine_entry_point(
    module: dict[str, Any],
) -> str | None:
    entry_points = list(
        module.get(
            "likely_entry_points",
            [],
        )
    )

    for preferred in (
        "run_pipeline",
        "run_cycle",
        "run_once",
        "run",
        "execute",
        "scan",
        "refresh",
        "main",
    ):
        if preferred in entry_points:
            return preferred

    return None


def determine_risk_flags(
    module: dict[str, Any],
) -> list[str]:
    flags: list[str] = []

    if module.get("database_related"):
        flags.append("DATABASE_WRITE_POSSIBLE")

    if module.get("network_related"):
        flags.append("NETWORK_ACCESS_POSSIBLE")

    if module.get("telegram_related"):
        flags.append("EXTERNAL_DELIVERY_POSSIBLE")

    if module.get("scheduler_related"):
        flags.append("INTERNAL_SCHEDULING_PRESENT")

    if module.get("contains_infinite_loop"):
        flags.append("INFINITE_LOOP_DETECTED")

    if not module.get("syntax_valid"):
        flags.append("SYNTAX_ERROR")

    return flags


def build_registry_entry(
    module: dict[str, Any],
) -> dict[str, Any]:
    lifecycle, reasons = determine_lifecycle(module)
    classification = str(module["classification"])
    execution_mode = determine_execution_mode(
        module,
        lifecycle,
    )

    production_approved = False
    enabled = False

    return {
        "module_id": stable_module_id(
            str(module["path"])
        ),
        "name": Path(
            str(module["path"]).replace("\\", "/")
        ).stem,
        "path": module["path"],
        "service": classification,
        "lifecycle": lifecycle,
        "production_approved": production_approved,
        "enabled": enabled,
        "execution": {
            "mode": execution_mode,
            "entry_point": determine_entry_point(
                module
            ),
            "has_main_guard": bool(
                module.get("has_main_guard")
            ),
            "timeout_seconds": (
                DEFAULT_TIMEOUT_SECONDS.get(
                    classification,
                    120,
                )
            ),
            "working_directory": ".",
        },
        "schedule": {
            "enabled": False,
            "interval_seconds": (
                DEFAULT_SCHEDULE_SECONDS.get(
                    classification
                )
            ),
            "priority": "NORMAL",
            "allow_overlap": False,
        },
        "reliability": {
            "retry_enabled": False,
            "maximum_attempts": 1,
            "retry_delay_seconds": 30,
            "failure_policy": "STOP_DEPENDENTS",
        },
        "health": {
            "required": (
                lifecycle
                == "PRODUCTION_CANDIDATE"
            ),
            "maximum_consecutive_failures": 3,
            "stale_after_seconds": (
                DEFAULT_SCHEDULE_SECONDS.get(
                    classification,
                    900,
                )
                * 3
            ),
        },
        "dependencies": [],
        "expected_outputs": [],
        "risk_flags": determine_risk_flags(
            module
        ),
        "discovery": {
            "syntax_valid": bool(
                module.get("syntax_valid")
            ),
            "syntax_error": module.get(
                "syntax_error"
            ),
            "detected_entry_points": module.get(
                "likely_entry_points",
                [],
            ),
            "functions": module.get(
                "functions",
                [],
            ),
            "classes": module.get(
                "classes",
                [],
            ),
        },
        "review": {
            "required": True,
            "decision": "PENDING",
            "notes": reasons,
        },
    }


def load_inventory() -> dict[str, Any]:
    if not INVENTORY_FILE.exists():
        raise FileNotFoundError(
            f"Inventory file not found: "
            f"{INVENTORY_FILE}"
        )

    with INVENTORY_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    modules = payload.get("modules")

    if not isinstance(modules, list):
        raise ValueError(
            "Inventory JSON does not contain "
            "a valid modules list."
        )

    return payload


def build_review_report(
    entries: list[dict[str, Any]],
    inventory: dict[str, Any],
) -> str:
    lifecycle_counts = Counter(
        entry["lifecycle"]
        for entry in entries
    )

    service_counts = Counter(
        entry["service"]
        for entry in entries
    )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for entry in entries:
        grouped[
            entry["lifecycle"]
        ].append(entry)

    lines = [
        "POLYMARKET INTELLIGENCE PLATFORM",
        "PRODUCTION REGISTRY REVIEW",
        "=" * 78,
        "",
        "IMPORTANT",
        "-" * 78,
        (
            "This is a conservative draft. No module has been "
            "production-approved or enabled."
        ),
        (
            "Every production candidate requires manual review "
            "before orchestration."
        ),
        "",
        "INVENTORY SUMMARY",
        "-" * 78,
        (
            f"Modules discovered: "
            f"{inventory.get('module_count', len(entries))}"
        ),
        (
            f"Syntax errors reported: "
            f"{inventory.get('syntax_errors', 'Unknown')}"
        ),
        (
            f"Registry entries generated: "
            f"{len(entries)}"
        ),
        "",
        "LIFECYCLE SUMMARY",
        "-" * 78,
    ]

    for lifecycle in sorted(
        lifecycle_counts
    ):
        lines.append(
            f"{lifecycle}: "
            f"{lifecycle_counts[lifecycle]}"
        )

    lines.extend(
        [
            "",
            "SERVICE SUMMARY",
            "-" * 78,
        ]
    )

    for service in sorted(service_counts):
        lines.append(
            f"{service}: "
            f"{service_counts[service]}"
        )

    review_order = [
        "PRODUCTION_CANDIDATE",
        "QUARANTINED_SYNTAX_ERROR",
        "EXPERIMENTAL",
        "DIAGNOSTIC",
        "MIGRATION",
        "DASHBOARD",
        "BACKUP",
        "LIBRARY",
    ]

    for lifecycle in review_order:
        modules = sorted(
            grouped.get(lifecycle, []),
            key=lambda item: item["path"],
        )

        if not modules:
            continue

        lines.extend(
            [
                "",
                lifecycle,
                "=" * 78,
            ]
        )

        for entry in modules:
            lines.extend(
                [
                    "",
                    entry["path"],
                    (
                        f"  Service: "
                        f"{entry['service']}"
                    ),
                    (
                        f"  Entry point: "
                        f"{entry['execution']['entry_point']}"
                    ),
                    (
                        f"  Execution mode: "
                        f"{entry['execution']['mode']}"
                    ),
                    (
                        f"  Enabled: "
                        f"{entry['enabled']}"
                    ),
                    (
                        f"  Production approved: "
                        f"{entry['production_approved']}"
                    ),
                    (
                        "  Risk flags: "
                        + (
                            ", ".join(
                                entry["risk_flags"]
                            )
                            or "None detected"
                        )
                    ),
                ]
            )

            for note in entry[
                "review"
            ]["notes"]:
                lines.append(
                    f"  Review note: {note}"
                )

    return "\n".join(lines) + "\n"


def main() -> None:
    inventory = load_inventory()

    entries = [
        build_registry_entry(module)
        for module in inventory["modules"]
    ]

    entries.sort(
        key=lambda item: item["path"]
    )

    lifecycle_counts = Counter(
        entry["lifecycle"]
        for entry in entries
    )

    registry = {
        "schema_version": "1.0",
        "platform_version": "0.7.1",
        "registry_status": "DRAFT",
        "generated_at": utc_now(),
        "source_inventory": str(
            INVENTORY_FILE.relative_to(
                PROJECT_ROOT
            )
        ),
        "safety": {
            "default_enabled": False,
            "production_requires_manual_approval": True,
            "allow_unregistered_modules": False,
            "allow_syntax_error_modules": False,
            "allow_backup_modules": False,
            "allow_infinite_loop_modules": False,
        },
        "summary": {
            "module_count": len(entries),
            "production_candidates": (
                lifecycle_counts[
                    "PRODUCTION_CANDIDATE"
                ]
            ),
            "syntax_quarantined": (
                lifecycle_counts[
                    "QUARANTINED_SYNTAX_ERROR"
                ]
            ),
            "backup_modules": (
                lifecycle_counts["BACKUP"]
            ),
            "experimental_modules": (
                lifecycle_counts[
                    "EXPERIMENTAL"
                ]
            ),
        },
        "modules": entries,
    }

    REGISTRY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REVIEW_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REGISTRY_FILE.write_text(
        json.dumps(
            registry,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    REVIEW_FILE.write_text(
        build_review_report(
            entries,
            inventory,
        ),
        encoding="utf-8",
    )

    print(
        "Production registry draft generated."
    )
    print(
        f"Modules registered: {len(entries)}"
    )
    print(
        "Production candidates: "
        f"{registry['summary']['production_candidates']}"
    )
    print(
        "Syntax quarantined: "
        f"{registry['summary']['syntax_quarantined']}"
    )
    print(
        "Backup modules: "
        f"{registry['summary']['backup_modules']}"
    )
    print(
        "Experimental modules: "
        f"{registry['summary']['experimental_modules']}"
    )
    print("")
    print(
        f"Registry: {REGISTRY_FILE}"
    )
    print(
        f"Review report: {REVIEW_FILE}"
    )


if __name__ == "__main__":
    main()
