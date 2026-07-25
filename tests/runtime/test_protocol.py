import unittest

from src.config import SETTINGS
from src.runtime import EngineProtocol, RuntimeContext


class DummyEngine:
    def run(self, settings, context):
        pass


class EngineProtocolTests(unittest.TestCase):

    def test_protocol_instance(self):
        engine = DummyEngine()

        self.assertIsInstance(
            engine,
            EngineProtocol,
        )

    def test_engine_runs(self):
        context = RuntimeContext(settings=SETTINGS)
        engine = DummyEngine()

        self.assertIsNone(
            engine.run(SETTINGS, context)
        )


if __name__ == "__main__":
    unittest.main()
