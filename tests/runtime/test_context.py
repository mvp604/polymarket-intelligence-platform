import unittest

from src.config import SETTINGS
from src.runtime import RuntimeContext


class RuntimeContextTests(unittest.TestCase):

    def test_settings_reference(self):
        context = RuntimeContext(settings=SETTINGS)

        self.assertIs(context.settings, SETTINGS)

    def test_default_dictionaries(self):
        context = RuntimeContext(settings=SETTINGS)

        self.assertEqual(context.repositories, {})
        self.assertEqual(context.api_clients, {})
        self.assertEqual(context.services, {})
        self.assertEqual(context.cache, {})
        self.assertEqual(context.metadata, {})

    def test_logger_defaults_to_none(self):
        context = RuntimeContext(settings=SETTINGS)

        self.assertIsNone(context.logger)


if __name__ == "__main__":
    unittest.main()
