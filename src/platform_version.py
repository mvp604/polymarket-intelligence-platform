from __future__ import annotations


PLATFORM_NAME = "Polymarket Intelligence Platform"
PLATFORM_VERSION = "0.5.0"
CLASSIFICATION_ENGINE_VERSION = "2.6.0"


def version_info() -> dict[str, str]:
    return {
        "platform_name": PLATFORM_NAME,
        "platform_version": PLATFORM_VERSION,
        "classification_engine_version": (
            CLASSIFICATION_ENGINE_VERSION
        ),
    }
