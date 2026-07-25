"""Tests for ComponentDefinition."""

from __future__ import annotations

import unittest

from tools.pdk.models.component import (
    ComponentDefinition,
    ComponentDefinitionError,
)


class ComponentDefinitionTests(unittest.TestCase):
    def test_component_is_created(self) -> None:
        component = ComponentDefinition(
            name="scheduler",
            component_type="runtime",
            version="0.13.0",
            class_name="Scheduler",
            methods=("start", "stop"),
            dependencies=("registry", "runner"),
        )

        self.assertEqual(
            component.sprint_name,
            "runtime_scheduler_0_13_0",
        )

    def test_name_is_normalized(self) -> None:
        component = ComponentDefinition(
            name="market-scanner",
            component_type="runtime",
            version="1.0.0",
            class_name="MarketScanner",
        )

        self.assertEqual(
            component.name,
            "market_scanner",
        )

    def test_invalid_version_is_rejected(self) -> None:
        with self.assertRaises(
            ComponentDefinitionError
        ):
            ComponentDefinition(
                name="scheduler",
                component_type="runtime",
                version="0.13",
                class_name="Scheduler",
            )

    def test_template_values_are_created(self) -> None:
        component = ComponentDefinition(
            name="scheduler",
            component_type="runtime",
            version="0.13.0",
            class_name="Scheduler",
        )

        self.assertEqual(
            component.template_values()["class_name"],
            "Scheduler",
        )


if __name__ == "__main__":
    unittest.main()