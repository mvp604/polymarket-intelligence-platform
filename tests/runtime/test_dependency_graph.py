from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Iterable

from src.runtime.dependency_graph import (
    DependencyCycleError,
    DependencyGraph,
    DependencyNode,
    GraphValidationError,
    MissingDependencyError,
)


@dataclass(frozen=True, slots=True)
class RegistrationStub:
    name: str
    dependencies: tuple[str, ...] = ()
    enabled: bool = True


class RegistryStub:
    def __init__(
        self,
        registrations: Iterable[RegistrationStub] = (),
    ) -> None:
        self._registrations = tuple(registrations)

    def enabled(self) -> tuple[RegistrationStub, ...]:
        return tuple(
            registration
            for registration in self._registrations
            if registration.enabled
        )


def build_graph(
    *registrations: RegistrationStub,
) -> DependencyGraph:
    return DependencyGraph.build(RegistryStub(registrations))


class DependencyGraphBuildTests(unittest.TestCase):
    def test_empty_registry_builds_empty_graph(self) -> None:
        graph = build_graph()

        self.assertEqual(graph.names(), ())
        self.assertEqual(graph.execution_order(), ())
        self.assertEqual(graph.execution_layers(), ())
        self.assertFalse(graph.has_cycles())
        self.assertEqual(
            graph.visualize(),
            "<empty dependency graph>",
        )

    def test_single_engine_is_root(self) -> None:
        graph = build_graph(
            RegistrationStub("database"),
        )

        self.assertEqual(graph.names(), ("database",))
        self.assertEqual(graph.execution_order(), ("database",))
        self.assertEqual(
            graph.execution_layers(),
            (("database",),),
        )
        self.assertEqual(graph.dependencies("database"), ())
        self.assertEqual(graph.dependents("database"), ())

    def test_linear_chain_orders_dependencies_first(self) -> None:
        graph = build_graph(
            RegistrationStub("reporting", ("consensus",)),
            RegistrationStub("database"),
            RegistrationStub("consensus", ("wallet_tracker",)),
            RegistrationStub("wallet_tracker", ("database",)),
        )

        self.assertEqual(
            graph.execution_order(),
            (
                "database",
                "wallet_tracker",
                "consensus",
                "reporting",
            ),
        )

        self.assertEqual(
            graph.execution_layers(),
            (
                ("database",),
                ("wallet_tracker",),
                ("consensus",),
                ("reporting",),
            ),
        )

    def test_branching_graph_creates_parallel_layer(self) -> None:
        graph = build_graph(
            RegistrationStub("database"),
            RegistrationStub("market_data", ("database",)),
            RegistrationStub("wallet_tracker", ("database",)),
            RegistrationStub(
                "consensus",
                ("market_data", "wallet_tracker"),
            ),
        )

        self.assertEqual(
            graph.execution_layers(),
            (
                ("database",),
                ("market_data", "wallet_tracker"),
                ("consensus",),
            ),
        )

    def test_diamond_graph_is_supported(self) -> None:
        graph = build_graph(
            RegistrationStub("root"),
            RegistrationStub("left", ("root",)),
            RegistrationStub("right", ("root",)),
            RegistrationStub("final", ("left", "right")),
        )

        self.assertEqual(
            graph.execution_layers(),
            (
                ("root",),
                ("left", "right"),
                ("final",),
            ),
        )

        self.assertEqual(
            graph.dependencies("final"),
            ("left", "right"),
        )

        self.assertEqual(
            graph.dependents("root"),
            ("left", "right"),
        )

    def test_multiple_roots_are_ordered_deterministically(self) -> None:
        graph = build_graph(
            RegistrationStub("zeta"),
            RegistrationStub("alpha"),
            RegistrationStub("middle"),
        )

        self.assertEqual(
            graph.execution_order(),
            ("alpha", "middle", "zeta"),
        )

        self.assertEqual(
            graph.execution_layers(),
            (("alpha", "middle", "zeta"),),
        )

    def test_disconnected_components_are_supported(self) -> None:
        graph = build_graph(
            RegistrationStub("database"),
            RegistrationStub("wallet_tracker", ("database",)),
            RegistrationStub("configuration"),
            RegistrationStub("logging", ("configuration",)),
        )

        order = graph.execution_order()

        self.assertLess(
            order.index("database"),
            order.index("wallet_tracker"),
        )
        self.assertLess(
            order.index("configuration"),
            order.index("logging"),
        )

        self.assertEqual(
            graph.execution_layers(),
            (
                ("configuration", "database"),
                ("logging", "wallet_tracker"),
            ),
        )

    def test_disabled_engines_are_excluded(self) -> None:
        graph = build_graph(
            RegistrationStub("database"),
            RegistrationStub("disabled_engine", enabled=False),
        )

        self.assertEqual(graph.names(), ("database",))
        self.assertFalse(graph.contains("disabled_engine"))

    def test_dependency_on_disabled_engine_is_rejected(self) -> None:
        with self.assertRaises(MissingDependencyError) as context:
            build_graph(
                RegistrationStub("database", enabled=False),
                RegistrationStub("wallet_tracker", ("database",)),
            )

        self.assertEqual(
            context.exception.engine_name,
            "wallet_tracker",
        )
        self.assertEqual(
            context.exception.missing_dependencies,
            ("database",),
        )

    def test_missing_dependency_is_rejected(self) -> None:
        with self.assertRaises(MissingDependencyError) as context:
            build_graph(
                RegistrationStub(
                    "consensus",
                    ("wallet_tracker", "market_data"),
                ),
            )

        self.assertEqual(
            context.exception.missing_dependencies,
            ("market_data", "wallet_tracker"),
        )

    def test_self_dependency_is_rejected(self) -> None:
        with self.assertRaises(GraphValidationError):
            build_graph(
                RegistrationStub("database", ("database",)),
            )

    def test_duplicate_dependencies_are_rejected(self) -> None:
        with self.assertRaises(GraphValidationError):
            build_graph(
                RegistrationStub("database"),
                RegistrationStub(
                    "wallet_tracker",
                    ("database", "database"),
                ),
            )

    def test_duplicate_registrations_are_rejected(self) -> None:
        with self.assertRaises(GraphValidationError):
            build_graph(
                RegistrationStub("database"),
                RegistrationStub("database"),
            )


class DependencyGraphQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = build_graph(
            RegistrationStub("database"),
            RegistrationStub("market_data", ("database",)),
            RegistrationStub("wallet_tracker", ("database",)),
            RegistrationStub(
                "consensus",
                ("market_data", "wallet_tracker"),
            ),
            RegistrationStub("reporting", ("consensus",)),
        )

    def test_contains_normalizes_surrounding_whitespace(self) -> None:
        self.assertTrue(self.graph.contains(" database "))

    def test_require_returns_dependency_node(self) -> None:
        node = self.graph.require("consensus")

        self.assertIsInstance(node, DependencyNode)
        self.assertEqual(node.name, "consensus")

    def test_require_rejects_unknown_engine(self) -> None:
        with self.assertRaisesRegex(
            KeyError,
            "not present in the dependency graph",
        ):
            self.graph.require("unknown")

    def test_transitive_dependencies(self) -> None:
        self.assertEqual(
            self.graph.transitive_dependencies("reporting"),
            (
                "consensus",
                "database",
                "market_data",
                "wallet_tracker",
            ),
        )

    def test_transitive_dependents(self) -> None:
        self.assertEqual(
            self.graph.transitive_dependents("database"),
            (
                "consensus",
                "market_data",
                "reporting",
                "wallet_tracker",
            ),
        )

    def test_visualization_is_deterministic(self) -> None:
        self.assertEqual(
            self.graph.visualize(),
            "\n".join(
                (
                    "consensus <- market_data, wallet_tracker",
                    "database <- <root>",
                    "market_data <- database",
                    "reporting <- consensus",
                    "wallet_tracker <- database",
                )
            ),
        )

    def test_nodes_mapping_is_immutable(self) -> None:
        with self.assertRaises(TypeError):
            self.graph.nodes["new"] = DependencyNode(
                name="new",
                dependencies=(),
                dependents=(),
            )


class DependencyGraphCycleTests(unittest.TestCase):
    def test_cycle_is_detected_during_build(self) -> None:
        with self.assertRaises(DependencyCycleError) as context:
            build_graph(
                RegistrationStub("alpha", ("charlie",)),
                RegistrationStub("bravo", ("alpha",)),
                RegistrationStub("charlie", ("bravo",)),
            )

        self.assertEqual(
            context.exception.engine_names,
            ("alpha", "bravo", "charlie"),
        )

    def test_has_cycles_reports_true_for_manual_cycle(self) -> None:
        graph = DependencyGraph(
            {
                "alpha": DependencyNode(
                    name="alpha",
                    dependencies=("bravo",),
                    dependents=("bravo",),
                ),
                "bravo": DependencyNode(
                    name="bravo",
                    dependencies=("alpha",),
                    dependents=("alpha",),
                ),
            }
        )

        self.assertTrue(graph.has_cycles())

        with self.assertRaises(DependencyCycleError):
            graph.execution_layers()

    def test_validate_rejects_inconsistent_relationship(self) -> None:
        graph = DependencyGraph(
            {
                "database": DependencyNode(
                    name="database",
                    dependencies=(),
                    dependents=(),
                ),
                "wallet_tracker": DependencyNode(
                    name="wallet_tracker",
                    dependencies=("database",),
                    dependents=(),
                ),
            }
        )

        with self.assertRaisesRegex(
            GraphValidationError,
            "does not list 'wallet_tracker' as a dependent",
        ):
            graph.validate()


class DependencyGraphDeterminismTests(unittest.TestCase):
    def test_repeated_builds_produce_same_order(self) -> None:
        registrations = (
            RegistrationStub("dashboard", ("reporting",)),
            RegistrationStub("database"),
            RegistrationStub("wallet_tracker", ("database",)),
            RegistrationStub("market_data", ("database",)),
            RegistrationStub(
                "consensus",
                ("wallet_tracker", "market_data"),
            ),
            RegistrationStub("reporting", ("consensus",)),
        )

        expected = build_graph(*registrations).execution_order()

        for _ in range(20):
            graph = build_graph(*reversed(registrations))

            self.assertEqual(
                graph.execution_order(),
                expected,
            )


if __name__ == "__main__":
    unittest.main()