from __future__ import annotations


REGISTRY_NAME = "classification_v2_registry"
REGISTRY_VERSION = "1.2.0"
REGISTRY_SCHEMA_VERSION = "1"
REGISTRY_LOADER_TYPE = "plugin_discovery"


def registry_metadata() -> dict[str, str]:
    return {
        "registry_name": REGISTRY_NAME,
        "registry_version": REGISTRY_VERSION,
        "registry_schema_version": (
            REGISTRY_SCHEMA_VERSION
        ),
        "registry_loader_type": (
            REGISTRY_LOADER_TYPE
        ),
    }
