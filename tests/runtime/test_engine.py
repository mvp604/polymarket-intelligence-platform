from __future__ import annotations

import logging
import unittest

from src.config import SETTINGS, Settings
from src.runtime.context import RuntimeContext
from src.runtime.engine import Engine


class ExampleEngine(Engine):
    name = "example_engine"
    version = "1.2.0"
    description = "Test runtime engine."
    capabilities = frozenset({"testing"})

    def run(
        self,
        settings: Settings,
        context: RuntimeContext,
    ) -> str:
        context.metadata["example_ran"] = True
        return "completed"


class EngineContractTests(unittest.TestCase):

    def test_engine_runs_with_runtime_context(self) -> None:
        context = RuntimeContext(
            settings=SETTINGS,
            logger=logging.getLogger("engine-tests"),
        )

        result = ExampleEngine().run(
            SETTINGS,
            context,
        )

        self.assertEqual(result, "completed")
        self.assertTrue(context.metadata["example_ran"])

    def test_engine_cannot_be_instantiated_without_run(self) -> None:
        class InvalidEngine(Engine):
            name = "invalid"

        with self.assertRaises(TypeError):
            InvalidEngine()


if __name__ == "__main__":
    unittest.main()
