from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


import architecture_registry


class ConfigurationDrivenRegistryTests(
    unittest.TestCase
):
    def test_registry_loads_json_configuration(
        self,
    ) -> None:
        registry = (
            architecture_registry
            .build_default_registry(
                PROJECT_ROOT
                / "config"
                / "architecture"
            )
        )

        self.assertEqual(
            architecture_registry
            .ARCHITECTURE_CONFIGURATION_SOURCE,
            "JSON configuration",
        )

        self.assertIsNone(
            architecture_registry
            .ARCHITECTURE_CONFIGURATION_ERROR
        )

        self.assertEqual(
            len(registry.services()),
            10,
        )
        self.assertEqual(
            len(registry.engines()),
            9,
        )
        self.assertEqual(
            len(registry.tables()),
            9,
        )
        self.assertEqual(
            len(registry.contracts()),
            1,
        )

    def test_missing_configuration_uses_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = (
                architecture_registry
                .build_default_registry(
                    Path(directory)
                    / "missing-architecture"
                )
            )

        self.assertEqual(
            architecture_registry
            .ARCHITECTURE_CONFIGURATION_SOURCE,
            "Built-in defaults (fallback)",
        )

        self.assertIsNotNone(
            architecture_registry
            .ARCHITECTURE_CONFIGURATION_ERROR
        )

        self.assertEqual(
            len(registry.services()),
            10,
        )
        self.assertEqual(
            len(registry.engines()),
            9,
        )
        self.assertEqual(
            len(registry.tables()),
            9,
        )
        self.assertEqual(
            len(registry.contracts()),
            1,
        )

    def test_json_and_fallback_match(
        self,
    ) -> None:
        json_registry = (
            architecture_registry
            .build_default_registry(
                PROJECT_ROOT
                / "config"
                / "architecture"
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            fallback_registry = (
                architecture_registry
                .build_default_registry(
                    Path(directory) / "missing"
                )
            )

        json_services = {
            service.name.value
            for service in json_registry.services()
        }

        fallback_services = {
            service.name.value
            for service in fallback_registry.services()
        }

        json_engines = {
            engine.name
            for engine in json_registry.engines()
        }

        fallback_engines = {
            engine.name
            for engine in fallback_registry.engines()
        }

        self.assertEqual(
            json_services,
            fallback_services,
        )

        self.assertEqual(
            json_engines,
            fallback_engines,
        )


if __name__ == "__main__":
    unittest.main()
