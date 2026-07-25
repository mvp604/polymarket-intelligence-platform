"""Immutable execution planning for runtime engines."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .dependency_graph import DependencyGraph


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    """One engine scheduled in a dependency-safe execution plan."""

    engine_name: str
    layer_index: int
    dependencies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Immutable execution plan produced from a dependency graph."""

    steps: tuple[ExecutionStep, ...]
    layers: tuple[tuple[str, ...], ...]
    _steps_by_name: Mapping[str, ExecutionStep]

    @classmethod
    def build(
        cls,
        *,
        steps: tuple[ExecutionStep, ...],
        layers: tuple[tuple[str, ...], ...],
    ) -> "ExecutionPlan":
        """Create and validate an immutable execution plan."""

        steps_by_name = {
            step.engine_name: step
            for step in steps
        }

        if len(steps_by_name) != len(steps):
            raise ValueError(
                "Execution plan contains duplicate engine names."
            )

        flattened_layers = tuple(
            engine_name
            for layer in layers
            for engine_name in layer
        )

        step_names = tuple(
            step.engine_name
            for step in steps
        )

        if flattened_layers != step_names:
            raise ValueError(
                "Execution plan steps must match the flattened "
                "layer order."
            )

        for expected_layer_index, layer in enumerate(layers):
            if not layer:
                raise ValueError(
                    "Execution plan layers cannot be empty."
                )

            if tuple(sorted(layer)) != layer:
                raise ValueError(
                    "Execution plan layers must use deterministic "
                    "ordering."
                )

            for engine_name in layer:
                step = steps_by_name[engine_name]

                if step.layer_index != expected_layer_index:
                    raise ValueError(
                        "Execution step layer index does not match "
                        f"its layer: {engine_name}"
                    )

        return cls(
            steps=steps,
            layers=layers,
            _steps_by_name=MappingProxyType(steps_by_name),
        )

    @property
    def engine_names(self) -> tuple[str, ...]:
        """Return dependency-first engine execution order."""

        return tuple(
            step.engine_name
            for step in self.steps
        )

    def contains(self, engine_name: str) -> bool:
        """Return whether an engine is present in the plan."""

        normalized = self._normalize_name(engine_name)
        return normalized in self._steps_by_name

    def require(self, engine_name: str) -> ExecutionStep:
        """Return an execution step or raise a descriptive error."""

        normalized = self._normalize_name(engine_name)

        try:
            return self._steps_by_name[normalized]
        except KeyError as error:
            raise KeyError(
                "Engine is not present in the execution plan: "
                f"{normalized}"
            ) from error

    def layer(self, layer_index: int) -> tuple[str, ...]:
        """Return one dependency-safe execution layer."""

        if not isinstance(layer_index, int):
            raise TypeError(
                "layer_index must be an integer."
            )

        try:
            return self.layers[layer_index]
        except IndexError as error:
            raise IndexError(
                "Execution plan layer does not exist: "
                f"{layer_index}"
            ) from error

    def visualize(self) -> str:
        """Return a deterministic plan representation."""

        if not self.layers:
            return "<empty execution plan>"

        return "\n".join(
            f"Layer {layer_index}: {', '.join(layer)}"
            for layer_index, layer in enumerate(self.layers)
        )

    @staticmethod
    def _normalize_name(value: str) -> str:
        if not isinstance(value, str):
            raise TypeError(
                "Engine names must be strings."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Engine names cannot be empty."
            )

        return normalized


class Planner:
    """Create execution plans from dependency graphs."""

    def plan(
        self,
        graph: DependencyGraph,
    ) -> ExecutionPlan:
        """Produce a deterministic dependency-first plan."""

        if not isinstance(graph, DependencyGraph):
            raise TypeError(
                "graph must be a DependencyGraph."
            )

        graph.validate()
        layers = graph.execution_layers()

        steps = tuple(
            ExecutionStep(
                engine_name=engine_name,
                layer_index=layer_index,
                dependencies=graph.dependencies(engine_name),
            )
            for layer_index, layer in enumerate(layers)
            for engine_name in layer
        )

        return ExecutionPlan.build(
            steps=steps,
            layers=layers,
        )