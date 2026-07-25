from __future__ import annotations

from typing import Any


class ServiceContainer:
    """
    Simple dependency injection container.

    Services are registered once and resolved by type.
    """

    def __init__(self) -> None:
        self._services: dict[type[Any], Any] = {}

    def register(
        self,
        service_type: type[Any],
        instance: Any,
    ) -> None:
        self._services[service_type] = instance

    def resolve(
        self,
        service_type: type[Any],
    ) -> Any:
        return self._services[service_type]

    def contains(
        self,
        service_type: type[Any],
    ) -> bool:
        return service_type in self._services
