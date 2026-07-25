from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from src.institutional_intelligence_engine import (
    InstitutionalIntelligenceEngine,
)


class InstitutionalEngineTests(unittest.TestCase):

    def test_empty_wallet_list(self) -> None:

        source = MagicMock()
        source.available_wallets.return_value = []

        metrics = MagicMock()
        scoring = MagicMock()

        scoring.score_population.return_value = []

        engine = InstitutionalIntelligenceEngine(
            source=source,
            metrics_engine=metrics,
            scoring_engine=scoring,
        )

        report = engine.run()

        self.assertEqual(
            report.summary.wallets_requested,
            0,
        )

        self.assertEqual(
            report.summary.wallets_loaded,
            0,
        )

        self.assertEqual(
            len(report.profiles),
            0,
        )

    def test_skipped_wallet(self) -> None:

        source = MagicMock()

        source.available_wallets.return_value = [
            "wallet1"
        ]

        source.load_wallet.return_value = None

        metrics = MagicMock()

        scoring = MagicMock()

        scoring.score_population.return_value = []

        engine = InstitutionalIntelligenceEngine(
            source=source,
            metrics_engine=metrics,
            scoring_engine=scoring,
        )

        report = engine.run()

        self.assertEqual(
            report.summary.wallets_skipped,
            1,
        )

    def test_metrics_engine_called(self) -> None:

        source = MagicMock()

        source.available_wallets.return_value = [
            "wallet1"
        ]

        fake_wallet = object()

        source.load_wallet.return_value = fake_wallet

        metrics = MagicMock()

        fake_metrics = MagicMock()

        fake_metrics.wallet = "wallet1"
        fake_metrics.source_name = "production"

        metrics.calculate.return_value = fake_metrics

        scoring = MagicMock()

        fake_score = MagicMock()

        fake_score.wallet = "wallet1"

        scoring.score_population.return_value = [
            fake_score
        ]

        engine = InstitutionalIntelligenceEngine(
            source=source,
            metrics_engine=metrics,
            scoring_engine=scoring,
        )

        report = engine.run()

        metrics.calculate.assert_called_once()

        self.assertEqual(
            len(report.profiles),
            1,
        )


if __name__ == "__main__":
    unittest.main()
