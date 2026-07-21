from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

JSON_REPORT = (
    PROJECT_ROOT
    / "reports"
    / "architecture"
    / "operational_module_inventory.json"
)

TEXT_REPORT = (
    PROJECT_ROOT
    / "reports"
    / "architecture"
    / "operational_module_inventory.txt"
)


ENTRY_POINT_NAMES = {
    "main",
    "run",
    "execute",
    "start",
    "scan",
    "process",
    "build",
    "refresh",
    "update",
    "run_once",
    "run_cycle",
    "run_pipeline",
}

DATABASE_NAMES = {
    "sqlite3",
    "sqlalchemy",
    "database",
    "db",
}

NETWORK_NAMES = {
    "requests",
    "httpx",
    "aiohttp",
    "websocket",
    "websockets",
}

TELEGRAM_NAMES = {
    "telegram",
    "telebot",
    "aiogram",
}

SCHEDULER_NAMES = {
    "schedule",
    "apscheduler",
    "time",
    "asyncio",
}


@dataclass
class ModuleInventory:
    module: str
    path: str
    syntax_valid: bool
    syntax_error: str | None
    functions: list[str]
    classes: list[str]
    likely_entry_points: list[str]
    has_main_guard: bool
    imports: list[str]
    database_related: bool
    network_related: bool
    telegram_related: bool
    scheduler_related: bool
    contains_infinite_loop: bool
    classification: str


def root_import_name(node: ast.AST) -> list[str]:
    names: list[str] = []

    if isinstance(node, ast.Import):
        for alias in node.names:
            names.append(alias.name.split(".")[0])

    elif isinstance(node, ast.ImportFrom):
        if node.module:
            names.append(node.module.split(".")[0])

    return names


def contains_main_guard(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue

        try:
            expression = ast.unparse(node.test)
        except Exception:
            continue

        if "__name__" in expression and "__main__" in expression:
            return True

    return False


def contains_infinite_loop(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            if isinstance(node.test, ast.Constant):
                if node.test.value is True:
                    return True

    return False


def classify(
    module_name: str,
    entry_points: list[str],
    has_main_guard: bool,
    database_related: bool,
    network_related: bool,
    telegram_related: bool,
    scheduler_related: bool,
) -> str:
    lowered = module_name.lower()

    if telegram_related or "telegram" in lowered:
        return "DELIVERY"

    if "scheduler" in lowered or scheduler_related:
        return "ORCHESTRATION"

    if "pipeline" in lowered or "orchestrat" in lowered:
        return "ORCHESTRATION"

    if "wallet" in lowered:
        return "WALLET_INTELLIGENCE"

    if "market" in lowered:
        return "MARKET_INTELLIGENCE"

    if "decision" in lowered or "signal" in lowered:
        return "DECISION"

    if "learning" in lowered or "calibrat" in lowered:
        return "LEARNING"

    if network_related:
        return "INGESTION"

    if database_related:
        return "DATA"

    if entry_points or has_main_guard:
        return "EXECUTABLE_UNKNOWN"

    return "LIBRARY"


def inspect_module(path: Path) -> ModuleInventory:
    relative = path.relative_to(PROJECT_ROOT)
    module_name = ".".join(
        relative.with_suffix("").parts
    )

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    try:
        tree = ast.parse(content)
    except SyntaxError as error:
        return ModuleInventory(
            module=module_name,
            path=str(relative),
            syntax_valid=False,
            syntax_error=(
                f"Line {error.lineno}: {error.msg}"
            ),
            functions=[],
            classes=[],
            likely_entry_points=[],
            has_main_guard=False,
            imports=[],
            database_related=False,
            network_related=False,
            telegram_related=False,
            scheduler_related=False,
            contains_infinite_loop=False,
            classification="SYNTAX_ERROR",
        )

    functions = sorted(
        {
            node.name
            for node in ast.walk(tree)
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
        }
    )

    classes = sorted(
        {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }
    )

    imports = sorted(
        {
            name
            for node in ast.walk(tree)
            for name in root_import_name(node)
        }
    )

    entry_points = sorted(
        name
        for name in functions
        if name.lower() in ENTRY_POINT_NAMES
    )

    imports_lower = {
        item.lower()
        for item in imports
    }

    database_related = bool(
        imports_lower & DATABASE_NAMES
    ) or "database" in content.lower()

    network_related = bool(
        imports_lower & NETWORK_NAMES
    )

    telegram_related = bool(
        imports_lower & TELEGRAM_NAMES
    ) or "telegram" in content.lower()

    scheduler_related = bool(
        imports_lower & SCHEDULER_NAMES
    ) and any(
        phrase in content.lower()
        for phrase in (
            "sleep(",
            "run_pending",
            "add_job",
            "create_task",
        )
    )

    main_guard = contains_main_guard(tree)
    infinite_loop = contains_infinite_loop(tree)

    classification = classify(
        module_name=module_name,
        entry_points=entry_points,
        has_main_guard=main_guard,
        database_related=database_related,
        network_related=network_related,
        telegram_related=telegram_related,
        scheduler_related=scheduler_related,
    )

    return ModuleInventory(
        module=module_name,
        path=str(relative),
        syntax_valid=True,
        syntax_error=None,
        functions=functions,
        classes=classes,
        likely_entry_points=entry_points,
        has_main_guard=main_guard,
        imports=imports,
        database_related=database_related,
        network_related=network_related,
        telegram_related=telegram_related,
        scheduler_related=scheduler_related,
        contains_infinite_loop=infinite_loop,
        classification=classification,
    )


def main() -> None:
    modules = [
        inspect_module(path)
        for path in sorted(
            SOURCE_DIRECTORY.rglob("*.py")
        )
        if "__pycache__" not in path.parts
    ]

    payload = {
        "schema_version": "1.0",
        "module_count": len(modules),
        "syntax_errors": sum(
            not module.syntax_valid
            for module in modules
        ),
        "main_guard_modules": sum(
            module.has_main_guard
            for module in modules
        ),
        "entry_point_modules": sum(
            bool(module.likely_entry_points)
            for module in modules
        ),
        "database_related_modules": sum(
            module.database_related
            for module in modules
        ),
        "network_related_modules": sum(
            module.network_related
            for module in modules
        ),
        "telegram_related_modules": sum(
            module.telegram_related
            for module in modules
        ),
        "scheduler_related_modules": sum(
            module.scheduler_related
            for module in modules
        ),
        "infinite_loop_modules": sum(
            module.contains_infinite_loop
            for module in modules
        ),
        "modules": [
            asdict(module)
            for module in modules
        ],
    }

    JSON_REPORT.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    lines = [
        "POLYMARKET INTELLIGENCE PLATFORM",
        "OPERATIONAL MODULE INVENTORY",
        "=" * 72,
        "",
        f"Modules scanned: {payload['module_count']}",
        f"Syntax errors: {payload['syntax_errors']}",
        (
            "Modules with command-line main guards: "
            f"{payload['main_guard_modules']}"
        ),
        (
            "Modules with likely entry points: "
            f"{payload['entry_point_modules']}"
        ),
        (
            "Database-related modules: "
            f"{payload['database_related_modules']}"
        ),
        (
            "Network-related modules: "
            f"{payload['network_related_modules']}"
        ),
        (
            "Telegram-related modules: "
            f"{payload['telegram_related_modules']}"
        ),
        (
            "Scheduler-related modules: "
            f"{payload['scheduler_related_modules']}"
        ),
        (
            "Potential infinite-loop modules: "
            f"{payload['infinite_loop_modules']}"
        ),
        "",
        "EXECUTABLE OR OPERATIONAL CANDIDATES",
        "=" * 72,
    ]

    candidates = [
        module
        for module in modules
        if (
            module.has_main_guard
            or module.likely_entry_points
            or module.scheduler_related
            or module.telegram_related
        )
    ]

    for module in candidates:
        lines.extend(
            [
                "",
                module.path,
                f"  Classification: {module.classification}",
                (
                    "  Entry points: "
                    + (
                        ", ".join(
                            module.likely_entry_points
                        )
                        or "None detected"
                    )
                ),
                (
                    "  Main guard: "
                    f"{module.has_main_guard}"
                ),
                (
                    "  Database-related: "
                    f"{module.database_related}"
                ),
                (
                    "  Network-related: "
                    f"{module.network_related}"
                ),
                (
                    "  Telegram-related: "
                    f"{module.telegram_related}"
                ),
                (
                    "  Scheduler-related: "
                    f"{module.scheduler_related}"
                ),
                (
                    "  Infinite loop detected: "
                    f"{module.contains_infinite_loop}"
                ),
            ]
        )

    TEXT_REPORT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("\n".join(lines[:25]))
    print("")
    print(f"JSON report: {JSON_REPORT}")
    print(f"Text report: {TEXT_REPORT}")


if __name__ == "__main__":
    main()
