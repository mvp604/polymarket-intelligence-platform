from __future__ import annotations

import importlib
import pkgutil
from collections import defaultdict
from pathlib import Path
from types import ModuleType

from .metadata import registry_metadata
from .models import RegistryRule


_EXCLUDED_MODULES: frozenset[str] = frozenset(
    {
        "__init__",
        "loader",
        "metadata",
        "models",
    }
)


def discover_plugin_names() -> tuple[str, ...]:
    registry_path = Path(__file__).resolve().parent

    names = []

    for module_info in pkgutil.iter_modules(
        [str(registry_path)]
    ):
        name = module_info.name

        if name in _EXCLUDED_MODULES:
            continue

        if name.startswith("_"):
            continue

        names.append(name)

    return tuple(sorted(names))


def import_plugin(
    plugin_name: str,
) -> ModuleType:
    return importlib.import_module(
        f"{__package__}.{plugin_name}"
    )


def extract_plugin_rules(
    module: ModuleType,
) -> tuple[RegistryRule, ...]:
    if not hasattr(module, "RULES"):
        return ()

    raw_rules = getattr(module, "RULES")

    if not isinstance(raw_rules, (tuple, list)):
        raise TypeError(
            f"{module.__name__}.RULES must be "
            "a tuple or list"
        )

    rules: list[RegistryRule] = []

    for index, rule in enumerate(raw_rules):
        if not isinstance(rule, RegistryRule):
            raise TypeError(
                f"{module.__name__}.RULES[{index}] "
                "is not a RegistryRule"
            )

        rules.append(rule)

    return tuple(rules)


def load_plugins(
) -> tuple[
    tuple[RegistryRule, ...],
    dict[str, int],
]:
    rules: list[RegistryRule] = []
    sources: dict[str, int] = {}

    for plugin_name in discover_plugin_names():
        module = import_plugin(plugin_name)
        plugin_rules = extract_plugin_rules(module)

        if not plugin_rules:
            continue

        sources[plugin_name] = len(plugin_rules)
        rules.extend(plugin_rules)

    return tuple(rules), sources


def validate_registry(
    rules: tuple[RegistryRule, ...],
) -> None:
    seen_ids: dict[str, RegistryRule] = {}

    for rule in rules:
        rule.validate()

        if rule.rule_id in seen_ids:
            previous = seen_ids[rule.rule_id]

            raise ValueError(
                "Duplicate rule_id detected: "
                f"{rule.rule_id}. Values: "
                f"{previous.value!r} and "
                f"{rule.value!r}"
            )

        seen_ids[rule.rule_id] = rule


_ALL_RULES, _PLUGIN_SOURCES = load_plugins()

validate_registry(_ALL_RULES)


def get_registry() -> tuple[RegistryRule, ...]:
    return _ALL_RULES


def get_rules(
    rule_type: str,
) -> tuple[RegistryRule, ...]:
    normalized = rule_type.strip().lower()

    return tuple(
        rule
        for rule in _ALL_RULES
        if rule.rule_type.lower() == normalized
    )


def registry_sources() -> dict[str, int]:
    return dict(_PLUGIN_SOURCES)


def registry_summary() -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)

    for rule in _ALL_RULES:
        counts[rule.rule_type] += 1

    counts["total"] = len(_ALL_RULES)

    return dict(counts)


def registry_manifest() -> dict[str, object]:
    summary = registry_summary()
    sources = registry_sources()

    return {
        **registry_metadata(),
        "rule_counts": summary,
        "rule_types": sorted(
            rule_type
            for rule_type in summary
            if rule_type != "total"
        ),
        "plugin_count": len(sources),
        "plugins": sources,
    }
