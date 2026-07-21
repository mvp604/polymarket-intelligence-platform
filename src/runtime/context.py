"""Shared dependency container for platform engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import Logger
from typing import Any, MutableMapping

from .state import RuntimeState


@dataclass(slots=True)
class PlatformContext:
    """Shared services and state provided to every runtime engine."""

    configuration: MutableMapping[str, Any]
    logger: Logger
    runtime_state: RuntimeState = field(default_factory=RuntimeState)

    database: Any = None
    architecture_registry: Any = None
    production_registry: Any = None
    metrics: Any = None
    cache: Any = None
    scheduler: Any = None
    http_session: Any = None
    event_bus: Any = None
    ai: Any = None

    shared_state: MutableMapping[str, Any] = field(
        default_factory=dict
    )

    def require(self, service_name: str) -> Any:
        """Return a configured service or raise a clear error."""

        normalized = service_name.strip()

        if not normalized:
            raise ValueError("service_name cannot be empty.")

        if not hasattr(self, normalized):
            raise KeyError(
                f"Unknown context service: {normalized}"
            )

        service = getattr(self, normalized)

        if service is None:
            raise RuntimeError(
                "Required context service is not configured: "
                f"{normalized}"
            )

        return service

    def get_config(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Return a top-level configuration value."""

        normalized = key.strip()

        if not normalized:
            raise ValueError(
                "configuration key cannot be empty."
            )

        return self.configuration.get(normalized, default)

    def set_shared(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Store a shared runtime value."""

        normalized = key.strip()

        if not normalized:
            raise ValueError(
                "shared-state key cannot be empty."
            )

        self.shared_state[normalized] = value

    def get_shared(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Read a shared runtime value."""

        normalized = key.strip()

        if not normalized:
            raise ValueError(
                "shared-state key cannot be empty."
            )

        return self.shared_state.get(normalized, default)
