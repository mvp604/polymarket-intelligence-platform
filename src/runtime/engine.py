"""Standard runtime engine contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from src.config import Settings

from .context import RuntimeContext


class Engine(ABC):
    """
    Base class implemented by every engine in the platform.

    Every engine receives immutable platform Settings and the shared
    RuntimeContext. Engines must not mutate Settings.
    """

    name: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    description: ClassVar[str] = ""
    dependencies: ClassVar[tuple[str, ...]] = ()
    capabilities: ClassVar[frozenset[str]] = frozenset()
    enabled: ClassVar[bool] = True

    @abstractmethod
    def run(
        self,
        settings: Settings,
        context: RuntimeContext,
    ) -> Any:
        """Execute this engine."""
        raise NotImplementedError
