import unittest

from src.config import SETTINGS


class SettingsTests(unittest.TestCase):

    def test_database(self):
        self.assertEqual(
            SETTINGS.database.connection_string,
            "database\\polymarket.db",
        )

    def test_runtime(self):
        self.assertTrue(
            SETTINGS.runtime.debug
        )

    def test_api(self):
        self.assertEqual(
            SETTINGS.api.gamma.base_url,
            "https://gamma-api.polymarket.com",
        )

    def test_thresholds(self):
        self.assertEqual(
            SETTINGS.thresholds.minimum_position_value,
            500.0,
        )


if __name__ == "__main__":
    unittest.main()
