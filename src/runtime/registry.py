from __future__ import annotations

from typing import Iterator

from .protocol import EngineProtocol


class EngineRegistry:
    """
    Registry for runtime engines.

    Engines are executed in the order they are registered.
    """

    def __init__(self) -> None:
        self._engines: list[EngineProtocol] = []

    def register(
        self,
        engine: EngineProtocol,
    ) -> None:
        if engine in self._engines:
            raise ValueError("Engine already registered.")

        self._engines.append(engine)

    def engines(self) -> tuple[EngineProtocol, ...]:
        return tuple(self._engines)

    def __iter__(self) -> Iterator[EngineProtocol]:
        return iter(self._engines)

    def __len__(self) -> int:
        return len(self._engines)
