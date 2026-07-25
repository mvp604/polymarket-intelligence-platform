from __future__ import annotations

from .context import RuntimeContext
from .pipeline import ExecutionPipeline


class LifecycleManager:
    """
    Coordinates application startup, execution,
    and shutdown.
    """

    def __init__(
        self,
        pipeline: ExecutionPipeline,
    ) -> None:
        self._pipeline = pipeline

    def run(
        self,
        context: RuntimeContext,
    ) -> list[object | None]:
        return self._pipeline.run(context)
