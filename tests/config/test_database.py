from pathlib import Path
import unittest

from src.config.database import (
    DATABASE_SETTINGS,
    DatabaseSettings,
)


class DatabaseSettingsTests(unittest.TestCase):

    def test_default_path(self):

        self.assertEqual(
            DATABASE_SETTINGS.sqlite_path,
            Path("database") / "polymarket.db",
        )

    def test_connection_string(self):

        settings = DatabaseSettings(
            sqlite_path=Path("abc.db")
        )

        self.assertEqual(
            settings.connection_string,
            "abc.db",
        )

    def test_foreign_keys_enabled(self):

        self.assertTrue(
            DATABASE_SETTINGS.enable_foreign_keys
        )


if __name__ == "__main__":
    unittest.main()
