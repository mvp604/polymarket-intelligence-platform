import unittest

from src.config import SETTINGS
from src.runtime import (
    EngineRegistry,
    ExecutionPipeline,
    RuntimeContext,
)


class FirstEngine:
    def run(self, settings, context):
        return "first"


class SecondEngine:
    def run(self, settings, context):
        return "second"


class ExecutionPipelineTests(unittest.TestCase):

    def test_execution_order(self):
        registry = EngineRegistry()

        registry.register(FirstEngine())
        registry.register(SecondEngine())

        pipeline = ExecutionPipeline(registry)

        context = RuntimeContext(
            settings=SETTINGS,
        )

        results = pipeline.run(context)

        self.assertEqual(
            results,
            [
                "first",
                "second",
            ],
        )


if __name__ == "__main__":
    unittest.main()
