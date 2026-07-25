import unittest

from src.config.thresholds import (
    THRESHOLD_SETTINGS,
    ThresholdSettings,
)


class ThresholdSettingsTests(unittest.TestCase):

    def test_defaults(self):
        self.assertEqual(
            THRESHOLD_SETTINGS.minimum_position_value,
            500.0,
        )

        self.assertEqual(
            THRESHOLD_SETTINGS.minimum_wallet_score,
            70.0,
        )

        self.assertEqual(
            THRESHOLD_SETTINGS.minimum_agreeing_wallets,
            2,
        )

        self.assertEqual(
            THRESHOLD_SETTINGS.minimum_conviction_score,
            75.0,
        )

        self.assertEqual(
            THRESHOLD_SETTINGS.minimum_confidence_score,
            80.0,
        )

        self.assertEqual(
            THRESHOLD_SETTINGS.elite_wallet_percentile,
            95.0,
        )

    def test_custom_thresholds(self):
        settings = ThresholdSettings(
            minimum_position_value=1000.0,
            minimum_wallet_score=90.0,
            minimum_agreeing_wallets=5,
            minimum_conviction_score=88.0,
            minimum_confidence_score=92.0,
            elite_wallet_percentile=99.0,
        )

        self.assertEqual(settings.minimum_position_value, 1000.0)
        self.assertEqual(settings.minimum_wallet_score, 90.0)
        self.assertEqual(settings.minimum_agreeing_wallets, 5)
        self.assertEqual(settings.minimum_conviction_score, 88.0)
        self.assertEqual(settings.minimum_confidence_score, 92.0)
        self.assertEqual(settings.elite_wallet_percentile, 99.0)


if __name__ == "__main__":
    unittest.main()
