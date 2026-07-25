import unittest

from src.runtime import EngineProtocol, EngineRegistry


class DummyEngine:
    def run(self, settings, context):
        pass


class EngineRegistryTests(unittest.TestCase):

    def test_register_engine(self):
        registry = EngineRegistry()
        engine = DummyEngine()

        registry.register(engine)

        self.assertEqual(len(registry), 1)

    def test_iteration_order(self):
        registry = EngineRegistry()

        first = DummyEngine()
        second = DummyEngine()

        registry.register(first)
        registry.register(second)

        engines = tuple(registry)

        self.assertIs(engines[0], first)
        self.assertIs(engines[1], second)

    def test_duplicate_registration(self):
        registry = EngineRegistry()
        engine = DummyEngine()

        registry.register(engine)

        with self.assertRaises(ValueError):
            registry.register(engine)

    def test_engine_protocol(self):
        engine = DummyEngine()

        self.assertIsInstance(
            engine,
            EngineProtocol,
        )


if __name__ == "__main__":
    unittest.main()
