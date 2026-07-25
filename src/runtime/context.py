from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config import Settings


@dataclass(slots=True)
class RuntimeContext:
    """
    Mutable runtime context shared by all engines.

    Configuration is immutable (Settings).

    RuntimeContext contains live services that are
    constructed while the application is running.
    """

    settings: Settings

    logger: Any | None = None

    repositories: dict[str, Any] = field(default_factory=dict)

    api_clients: dict[str, Any] = field(default_factory=dict)

    services: dict[str, Any] = field(default_factory=dict)

    cache: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)
