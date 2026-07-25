from __future__ import annotations

from .context import RuntimeContext
from .registry import EngineRegistry


class ExecutionPipeline:
    """
    Executes registered engines in deterministic order.
    """

    def __init__(
        self,
        registry: EngineRegistry,
    ) -> None:
        self._registry = registry

    def run(
        self,
        context: RuntimeContext,
    ) -> list[object | None]:
        results: list[object | None] = []

        for engine in self._registry:
            results.append(
                engine.run(
                    context.settings,
                    context,
                )
            )

        return results
