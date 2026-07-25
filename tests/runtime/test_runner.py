"""Tests for sequential runtime execution."""

from __future__ import annotations

import logging
import unittest
from dataclasses import FrozenInstanceError

from src.runtime import (
    DependencyGraph,
    Engine,
    EngineRegistry,
    EngineStatus,
    ErrorPolicy,
    Planner,
    PlatformContext,
    Runner,
)


class RootEngine(Engine):
    name = "root"

    def execute(
        self,
        context: PlatformContext,
    ) -> str:
        context.shared_state.setdefault(
            "order",
            [],
        ).append(self.name)

        return "root-output"


class FailingEngine(Engine):
    name = "failing"
    dependencies = ("root",)

    def execute(
        self,
        context: PlatformContext,
    ) -> None:
        context.shared_state.setdefault(
            "order",
            [],
        ).append(self.name)

        raise RuntimeError(
            "expected failure"
        )


class DependentEngine(Engine):
    name = "dependent"
    dependencies = ("failing",)

    def execute(
        self,
        context: PlatformContext,
    ) -> str:
        context.shared_state.setdefault(
            "order",
            [],
        ).append(self.name)

        return "dependent-output"


class IndependentEngine(Engine):
    name = "independent"

    def execute(
        self,
        context: PlatformContext,
    ) -> str:
        context.shared_state.setdefault(
            "order",
            [],
        ).append(self.name)

        return "independent-output"


class RunnerTests(unittest.TestCase):
    def build_context(
        self,
    ) -> PlatformContext:
        return PlatformContext(
            configuration={},
            logger=logging.getLogger(
                "runner-tests"
            ),
        )

    def build_runtime(
        self,
        *engines: Engine,
    ):
        registry = EngineRegistry()

        for engine in engines:
            registry.register(engine)

        graph = DependencyGraph.build(
            registry
        )

        plan = Planner().plan(graph)

        return registry, plan

    def test_successful_execution(
        self,
    ) -> None:
        registry, plan = self.build_runtime(
            RootEngine()
        )

        report = Runner().run(
            plan,
            registry,
            self.build_context(),
        )

        self.assertTrue(report.success)

        self.assertEqual(
            report.require("root").output,
            "root-output",
        )

    def test_continue_runs_dependents(
        self,
    ) -> None:
        registry, plan = self.build_runtime(
            DependentEngine(),
            FailingEngine(),
            RootEngine(),
        )

        context = self.build_context()

        report = Runner().run(
            plan,
            registry,
            context,
            error_policy=(
                ErrorPolicy.CONTINUE
            ),
        )

        self.assertEqual(
            report.require(
                "failing"
            ).status,
            EngineStatus.FAILED,
        )

        self.assertEqual(
            report.require(
                "dependent"
            ).status,
            EngineStatus.SUCCESS,
        )

        self.assertEqual(
            context.shared_state["order"],
            [
                "root",
                "failing",
                "dependent",
            ],
        )

    def test_skip_dependents_policy(
        self,
    ) -> None:
        registry, plan = self.build_runtime(
            IndependentEngine(),
            DependentEngine(),
            FailingEngine(),
            RootEngine(),
        )

        report = Runner().run(
            plan,
            registry,
            self.build_context(),
            error_policy=(
                ErrorPolicy.SKIP_DEPENDENTS
            ),
        )

        self.assertEqual(
            report.require(
                "dependent"
            ).status,
            EngineStatus.SKIPPED,
        )

        self.assertEqual(
            report.require(
                "independent"
            ).status,
            EngineStatus.SUCCESS,
        )

    def test_strict_policy(
        self,
    ) -> None:
        registry, plan = self.build_runtime(
            DependentEngine(),
            FailingEngine(),
            RootEngine(),
        )

        report = Runner().run(
            plan,
            registry,
            self.build_context(),
            error_policy=ErrorPolicy.STRICT,
        )

        self.assertEqual(
            report.require(
                "failing"
            ).status,
            EngineStatus.FAILED,
        )

        self.assertEqual(
            report.require(
                "dependent"
            ).status,
            EngineStatus.SKIPPED,
        )

    def test_failure_details(
        self,
    ) -> None:
        registry, plan = self.build_runtime(
            FailingEngine(),
            RootEngine(),
        )

        report = Runner().run(
            plan,
            registry,
            self.build_context(),
            error_policy=(
                ErrorPolicy.CONTINUE
            ),
        )

        result = report.require(
            "failing"
        )

        self.assertEqual(
            result.error_type,
            "RuntimeError",
        )

        self.assertEqual(
            result.error_message,
            "expected failure",
        )

    def test_empty_plan(
        self,
    ) -> None:
        registry = EngineRegistry()

        plan = Planner().plan(
            DependencyGraph.build(
                registry
            )
        )

        report = Runner().run(
            plan,
            registry,
            self.build_context(),
        )

        self.assertTrue(report.success)

        self.assertEqual(
            report.visualize(),
            "<empty runtime report>",
        )

    def test_report_is_immutable(
        self,
    ) -> None:
        registry, plan = self.build_runtime(
            RootEngine()
        )

        report = Runner().run(
            plan,
            registry,
            self.build_context(),
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            report.duration_seconds = 0.0

    def test_missing_registry_engine(
        self,
    ) -> None:
        _, plan = self.build_runtime(
            RootEngine()
        )

        with self.assertRaisesRegex(
            KeyError,
            "unavailable in the enabled registry",
        ):
            Runner().run(
                plan,
                EngineRegistry(),
                self.build_context(),
            )

    def test_invalid_error_policy(
        self,
    ) -> None:
        registry, plan = self.build_runtime(
            RootEngine()
        )

        with self.assertRaisesRegex(
            ValueError,
            "Unsupported error policy",
        ):
            Runner().run(
                plan,
                registry,
                self.build_context(),
                error_policy="invalid",
            )


if __name__ == "__main__":
    unittest.main()