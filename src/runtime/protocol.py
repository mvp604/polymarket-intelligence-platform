from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.config import Settings
from src.runtime.context import RuntimeContext


@runtime_checkable
class EngineProtocol(Protocol):
    """
    Common interface implemented by every engine.
    """

    def run(
        self,
        settings: Settings,
        context: RuntimeContext,
    ) -> object | None:
        ...
