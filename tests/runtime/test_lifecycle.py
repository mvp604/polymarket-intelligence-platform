import unittest

from src.config import SETTINGS
from src.runtime import (
    EngineRegistry,
    ExecutionPipeline,
    LifecycleManager,
    RuntimeContext,
)


class DummyEngine:
    def run(self, settings, context):
        return "ok"


class LifecycleManagerTests(unittest.TestCase):

    def test_pipeline_execution(self):
        registry = EngineRegistry()
        registry.register(DummyEngine())

        pipeline = ExecutionPipeline(registry)
        lifecycle = LifecycleManager(pipeline)

        context = RuntimeContext(settings=SETTINGS)

        results = lifecycle.run(context)

        self.assertEqual(results, ["ok"])


if __name__ == "__main__":
    unittest.main()
