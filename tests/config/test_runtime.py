import unittest

from src.config.runtime import (
    Environment,
    RuntimeSettings,
    RUNTIME_SETTINGS,
)


class RuntimeSettingsTests(unittest.TestCase):

    def test_default_environment(self):
        self.assertEqual(
            RUNTIME_SETTINGS.environment,
            Environment.DEVELOPMENT,
        )

    def test_debug_enabled(self):
        self.assertTrue(
            RUNTIME_SETTINGS.debug
        )

    def test_cache_enabled(self):
        self.assertTrue(
            RUNTIME_SETTINGS.enable_cache
        )

    def test_default_workers(self):
        self.assertEqual(
            RUNTIME_SETTINGS.max_workers,
            4,
        )

    def test_default_scan_interval(self):
        self.assertEqual(
            RUNTIME_SETTINGS.scan_interval_seconds,
            300,
        )

    def test_custom_runtime_settings(self):
        settings = RuntimeSettings(
            environment=Environment.PRODUCTION,
            debug=False,
            enable_cache=False,
            max_workers=8,
            scan_interval_seconds=60,
        )

        self.assertEqual(
            settings.environment,
            Environment.PRODUCTION,
        )

        self.assertFalse(settings.debug)
        self.assertFalse(settings.enable_cache)
        self.assertEqual(settings.max_workers, 8)
        self.assertEqual(settings.scan_interval_seconds, 60)


if __name__ == "__main__":
    unittest.main()
