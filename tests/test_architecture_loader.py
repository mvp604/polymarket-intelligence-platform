from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from architecture_loader import (
    load_architecture_configuration,
)


class ArchitectureLoaderTests(unittest.TestCase):
    def test_project_configuration(self) -> None:
        configuration = load_architecture_configuration(
            PROJECT_ROOT
            / "config"
            / "architecture"
        )

        self.assertEqual(
            configuration.schema_version,
            "1.0",
        )

        self.assertEqual(
            configuration.architecture_version,
            "0.6.0",
        )

        self.assertEqual(
            len(configuration.services),
            10,
        )

        self.assertEqual(
            len(configuration.engines),
            9,
        )

        service_names = {
            service.name.value
            for service in configuration.services
        }

        engine_names = {
            engine.name
            for engine in configuration.engines
        }

        engine_modules = {
            engine.module
            for engine in configuration.engines
        }

        self.assertEqual(
            len(service_names),
            10,
        )

        self.assertEqual(
            len(engine_names),
            9,
        )

        self.assertEqual(
            len(engine_modules),
            9,
        )


if __name__ == "__main__":
    unittest.main()
