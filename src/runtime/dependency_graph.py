"""Deterministic dependency analysis for registered runtime engines."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from .registry import EngineRegistry


class GraphValidationError(RuntimeError):
    """Raised when a runtime dependency graph is invalid."""


class MissingDependencyError(GraphValidationError):
    """Raised when an engine depends on an unavailable engine."""

    def __init__(
        self,
        engine_name: str,
        missing_dependencies: tuple[str, ...],
    ) -> None:
        self.engine_name = engine_name
        self.missing_dependencies = missing_dependencies

        dependencies = ", ".join(missing_dependencies)

        super().__init__(
            f"Engine '{engine_name}' has missing or disabled "
            f"dependencies: {dependencies}"
        )


class DependencyCycleError(GraphValidationError):
    """Raised when engine dependencies contain a cycle."""

    def __init__(self, engine_names: tuple[str, ...]) -> None:
        self.engine_names = engine_names

        cycle_members = ", ".join(engine_names)

        super().__init__(
            f"Dependency cycle detected involving: {cycle_members}"
        )


@dataclass(frozen=True, slots=True)
class DependencyNode:
    """Immutable dependency information for one runtime engine."""

    name: str
    dependencies: tuple[str, ...]
    dependents: tuple[str, ...]


class DependencyGraph:
    """Immutable directed graph of enabled runtime engines.

    Edges point from a dependency to the engine that requires it.

    For example, when ``consensus`` depends on ``wallet_tracker``:

        wallet_tracker -> consensus
    """

    def __init__(
        self,
        nodes: Mapping[str, DependencyNode] | None = None,
    ) -> None:
        normalized_nodes = dict(sorted((nodes or {}).items()))

        self._nodes: Mapping[str, DependencyNode] = MappingProxyType(
            normalized_nodes
        )

    @classmethod
    def build(cls, registry: EngineRegistry) -> DependencyGraph:
        """Build and validate a graph from enabled engine registrations."""

        registrations = tuple(registry.enabled())
        registrations_by_name: dict[str, object] = {}

        for registration in registrations:
            name = cls._normalize_name(registration.name)

            if name in registrations_by_name:
                raise GraphValidationError(
                    f"Duplicate engine registration in graph: {name}"
                )

            registrations_by_name[name] = registration

        dependency_map: dict[str, tuple[str, ...]] = {}

        for name, registration in registrations_by_name.items():
            raw_dependencies = tuple(registration.dependencies)
            dependencies = tuple(
                cls._normalize_name(dependency)
                for dependency in raw_dependencies
            )

            if len(dependencies) != len(set(dependencies)):
                raise GraphValidationError(
                    f"Engine '{name}' declares duplicate dependencies."
                )

            if name in dependencies:
                raise GraphValidationError(
                    f"Engine '{name}' cannot depend on itself."
                )

            missing_dependencies = tuple(
                sorted(
                    dependency
                    for dependency in dependencies
                    if dependency not in registrations_by_name
                )
            )

            if missing_dependencies:
                raise MissingDependencyError(
                    name,
                    missing_dependencies,
                )

            dependency_map[name] = tuple(sorted(dependencies))

        dependent_map: dict[str, list[str]] = {
            name: []
            for name in registrations_by_name
        }

        for engine_name, dependencies in dependency_map.items():
            for dependency in dependencies:
                dependent_map[dependency].append(engine_name)

        nodes = {
            name: DependencyNode(
                name=name,
                dependencies=dependency_map[name],
                dependents=tuple(sorted(dependent_map[name])),
            )
            for name in sorted(registrations_by_name)
        }

        graph = cls(nodes)
        graph.validate()

        return graph

    @property
    def nodes(self) -> Mapping[str, DependencyNode]:
        """Return the immutable node mapping."""

        return self._nodes

    def names(self) -> tuple[str, ...]:
        """Return all graph node names in deterministic order."""

        return tuple(self._nodes)

    def contains(self, engine_name: str) -> bool:
        """Return whether an engine exists in the graph."""

        return self._normalize_name(engine_name) in self._nodes

    def require(self, engine_name: str) -> DependencyNode:
        """Return a node or raise a descriptive KeyError."""

        name = self._normalize_name(engine_name)

        try:
            return self._nodes[name]
        except KeyError as error:
            raise KeyError(
                f"Engine is not present in the dependency graph: {name}"
            ) from error

    def dependencies(self, engine_name: str) -> tuple[str, ...]:
        """Return the engine's direct dependencies."""

        return self.require(engine_name).dependencies

    def dependents(self, engine_name: str) -> tuple[str, ...]:
        """Return engines that directly depend on the requested engine."""

        return self.require(engine_name).dependents

    def transitive_dependencies(
        self,
        engine_name: str,
    ) -> tuple[str, ...]:
        """Return all direct and indirect dependencies."""

        start = self.require(engine_name)
        discovered: set[str] = set()
        pending = list(start.dependencies)

        while pending:
            dependency = pending.pop()

            if dependency in discovered:
                continue

            discovered.add(dependency)
            pending.extend(self._nodes[dependency].dependencies)

        return tuple(sorted(discovered))

    def transitive_dependents(
        self,
        engine_name: str,
    ) -> tuple[str, ...]:
        """Return all direct and indirect dependents."""

        start = self.require(engine_name)
        discovered: set[str] = set()
        pending = list(start.dependents)

        while pending:
            dependent = pending.pop()

            if dependent in discovered:
                continue

            discovered.add(dependent)
            pending.extend(self._nodes[dependent].dependents)

        return tuple(sorted(discovered))

    def execution_order(self) -> tuple[str, ...]:
        """Return deterministic dependency-first execution order.

        Kahn's topological-sort algorithm is used with a priority queue
        so multiple valid orders always resolve alphabetically.
        """

        indegree = {
            name: len(node.dependencies)
            for name, node in self._nodes.items()
        }

        ready = [
            name
            for name, dependency_count in indegree.items()
            if dependency_count == 0
        ]
        heapq.heapify(ready)

        ordered: list[str] = []

        while ready:
            current = heapq.heappop(ready)
            ordered.append(current)

            for dependent in self._nodes[current].dependents:
                indegree[dependent] -= 1

                if indegree[dependent] == 0:
                    heapq.heappush(ready, dependent)

        if len(ordered) != len(self._nodes):
            unresolved = tuple(
                sorted(
                    name
                    for name, dependency_count in indegree.items()
                    if dependency_count > 0
                )
            )

            raise DependencyCycleError(unresolved)

        return tuple(ordered)

    def execution_layers(self) -> tuple[tuple[str, ...], ...]:
        """Return dependency-safe layers that may run in parallel."""

        indegree = {
            name: len(node.dependencies)
            for name, node in self._nodes.items()
        }

        current_layer = tuple(
            sorted(
                name
                for name, dependency_count in indegree.items()
                if dependency_count == 0
            )
        )

        layers: list[tuple[str, ...]] = []
        processed_count = 0

        while current_layer:
            layers.append(current_layer)
            processed_count += len(current_layer)

            next_layer: list[str] = []

            for current in current_layer:
                for dependent in self._nodes[current].dependents:
                    indegree[dependent] -= 1

                    if indegree[dependent] == 0:
                        next_layer.append(dependent)

            current_layer = tuple(sorted(next_layer))

        if processed_count != len(self._nodes):
            unresolved = tuple(
                sorted(
                    name
                    for name, dependency_count in indegree.items()
                    if dependency_count > 0
                )
            )

            raise DependencyCycleError(unresolved)

        return tuple(layers)

    def validate(self) -> None:
        """Validate internal graph consistency and acyclicity."""

        for name, node in self._nodes.items():
            if node.name != name:
                raise GraphValidationError(
                    f"Node key '{name}' does not match node name "
                    f"'{node.name}'."
                )

            if len(node.dependencies) != len(set(node.dependencies)):
                raise GraphValidationError(
                    f"Engine '{name}' has duplicate dependencies."
                )

            if len(node.dependents) != len(set(node.dependents)):
                raise GraphValidationError(
                    f"Engine '{name}' has duplicate dependents."
                )

            if name in node.dependencies:
                raise GraphValidationError(
                    f"Engine '{name}' cannot depend on itself."
                )

            missing_dependencies = tuple(
                sorted(
                    dependency
                    for dependency in node.dependencies
                    if dependency not in self._nodes
                )
            )

            if missing_dependencies:
                raise MissingDependencyError(
                    name,
                    missing_dependencies,
                )

            for dependency in node.dependencies:
                if name not in self._nodes[dependency].dependents:
                    raise GraphValidationError(
                        f"Dependency relationship is inconsistent: "
                        f"'{dependency}' does not list '{name}' "
                        f"as a dependent."
                    )

            for dependent in node.dependents:
                if dependent not in self._nodes:
                    raise GraphValidationError(
                        f"Engine '{name}' references missing dependent "
                        f"'{dependent}'."
                    )

                if name not in self._nodes[dependent].dependencies:
                    raise GraphValidationError(
                        f"Dependent relationship is inconsistent: "
                        f"'{dependent}' does not list '{name}' "
                        f"as a dependency."
                    )

        self.execution_order()

    def has_cycles(self) -> bool:
        """Return whether the graph contains a dependency cycle."""

        try:
            self.execution_order()
        except DependencyCycleError:
            return True

        return False

    def visualize(self) -> str:
        """Return a deterministic human-readable graph representation."""

        if not self._nodes:
            return "<empty dependency graph>"

        lines: list[str] = []

        for name, node in self._nodes.items():
            if node.dependencies:
                dependencies = ", ".join(node.dependencies)
                lines.append(f"{name} <- {dependencies}")
            else:
                lines.append(f"{name} <- <root>")

        return "\n".join(lines)

    @staticmethod
    def _normalize_name(value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("Engine names must be strings.")

        normalized = value.strip()

        if not normalized:
            raise ValueError("Engine names cannot be empty.")

        return normalized