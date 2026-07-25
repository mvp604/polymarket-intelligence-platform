"""Tests for immutable runtime execution planning."""

from __future__ import annotations

import unittest

from src.runtime import (
    DependencyGraph,
    Engine,
    EngineRegistry,
    ExecutionPlan,
    Planner,
)
from src.runtime.context import PlatformContext


class RootEngine(Engine):
    name = "root"

    def execute(
        self,
        context: PlatformContext,
    ) -> str:
        return self.name


class AlphaEngine(Engine):
    name = "alpha"
    dependencies = ("root",)

    def execute(
        self,
        context: PlatformContext,
    ) -> str:
        return self.name


class BetaEngine(Engine):
    name = "beta"
    dependencies = ("root",)

    def execute(
        self,
        context: PlatformContext,
    ) -> str:
        return self.name


class FinalEngine(Engine):
    name = "final"
    dependencies = ("alpha", "beta")

    def execute(
        self,
        context: PlatformContext,
    ) -> str:
        return self.name


class PlannerTests(unittest.TestCase):
    def build_graph(self) -> DependencyGraph:
        registry = EngineRegistry()

        registry.register(FinalEngine())
        registry.register(BetaEngine())
        registry.register(RootEngine())
        registry.register(AlphaEngine())

        return DependencyGraph.build(registry)

    def test_dependency_safe_layers(self) -> None:
        plan = Planner().plan(self.build_graph())

        self.assertEqual(
            plan.layers,
            (
                ("root",),
                ("alpha", "beta"),
                ("final",),
            ),
        )

    def test_dependency_first_execution_order(self) -> None:
        plan = Planner().plan(self.build_graph())

        self.assertEqual(
            plan.engine_names,
            (
                "root",
                "alpha",
                "beta",
                "final",
            ),
        )

    def test_direct_dependencies_are_preserved(self) -> None:
        plan = Planner().plan(self.build_graph())

        self.assertEqual(
            plan.require("root").dependencies,
            (),
        )

        self.assertEqual(
            plan.require("alpha").dependencies,
            ("root",),
        )

        self.assertEqual(
            plan.require("final").dependencies,
            ("alpha", "beta"),
        )

    def test_layer_indexes_are_recorded(self) -> None:
        plan = Planner().plan(self.build_graph())

        self.assertEqual(
            plan.require("root").layer_index,
            0,
        )

        self.assertEqual(
            plan.require("alpha").layer_index,
            1,
        )

        self.assertEqual(
            plan.require("beta").layer_index,
            1,
        )

        self.assertEqual(
            plan.require("final").layer_index,
            2,
        )

    def test_plan_is_immutable(self) -> None:
        plan = Planner().plan(self.build_graph())

        with self.assertRaises(AttributeError):
            plan.steps = ()

    def test_contains_normalizes_whitespace(self) -> None:
        plan = Planner().plan(self.build_graph())

        self.assertTrue(
            plan.contains(" alpha ")
        )

        self.assertFalse(
            plan.contains("missing")
        )

    def test_missing_engine_is_rejected(self) -> None:
        plan = Planner().plan(self.build_graph())

        with self.assertRaisesRegex(
            KeyError,
            "not present in the execution plan",
        ):
            plan.require("missing")

    def test_invalid_layer_type_is_rejected(self) -> None:
        plan = Planner().plan(self.build_graph())

        with self.assertRaisesRegex(
            TypeError,
            "layer_index must be an integer",
        ):
            plan.layer("1")

    def test_missing_layer_is_rejected(self) -> None:
        plan = Planner().plan(self.build_graph())

        with self.assertRaisesRegex(
            IndexError,
            "layer does not exist: 99",
        ):
            plan.layer(99)

    def test_visualization_is_deterministic(self) -> None:
        plan = Planner().plan(self.build_graph())

        self.assertEqual(
            plan.visualize(),
            "Layer 0: root\n"
            "Layer 1: alpha, beta\n"
            "Layer 2: final",
        )

    def test_empty_graph_creates_empty_plan(self) -> None:
        plan = Planner().plan(
            DependencyGraph()
        )

        self.assertEqual(plan.steps, ())
        self.assertEqual(plan.layers, ())

        self.assertEqual(
            plan.visualize(),
            "<empty execution plan>",
        )

    def test_non_graph_object_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            TypeError,
            "graph must be a DependencyGraph",
        ):
            Planner().plan(object())

    def test_duplicate_steps_are_rejected(self) -> None:
        valid_plan = Planner().plan(
            self.build_graph()
        )

        duplicate = valid_plan.steps[0]

        with self.assertRaisesRegex(
            ValueError,
            "duplicate engine names",
        ):
            ExecutionPlan.build(
                steps=(
                    duplicate,
                    duplicate,
                ),
                layers=(
                    ("root", "root"),
                ),
            )


if __name__ == "__main__":
    unittest.main()