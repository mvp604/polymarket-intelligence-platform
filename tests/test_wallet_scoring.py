from __future__ import annotations

import unittest
from dataclasses import replace

from src.wallet_metrics import WalletRawMetrics
from src.wallet_scoring import (
    SCORE_MODEL_VERSION,
    WalletScore,
    WalletScoringEngine,
    grade_from_score,
    percentile_score,
)


WALLET_1 = "0x1111111111111111111111111111111111111111"
WALLET_2 = "0x2222222222222222222222222222222222222222"
WALLET_3 = "0x3333333333333333333333333333333333333333"


def metrics(
    wallet: str,
    *,
    positions_observed: int = 10,
    markets_tracked: int = 8,
    total_current_value: float = 1000.0,
    total_invested: float = 800.0,
    total_pnl: float = 200.0,
    roi: float = 0.25,
    average_position_value: float = 100.0,
    median_position_value: float = 75.0,
    largest_position_value: float = 250.0,
    concentration_ratio: float = 0.25,
    weighted_entry_edge: float = 0.10,
    observed_win_rate: float = 0.70,
    pnl_volatility: float = 20.0,
) -> WalletRawMetrics:
    return WalletRawMetrics(
        wallet=wallet,
        source_name="production",
        source_run_id="run-1",
        source_observed_at="2026-07-22T10:00:00+00:00",
        positions_observed=positions_observed,
        markets_tracked=markets_tracked,
        confidence_observations=positions_observed,
        total_current_value=total_current_value,
        total_invested=total_invested,
        realized_pnl=50.0,
        unrealized_pnl=total_pnl - 50.0,
        total_pnl=total_pnl,
        roi=roi,
        average_position_value=average_position_value,
        median_position_value=median_position_value,
        largest_position_value=largest_position_value,
        concentration_ratio=concentration_ratio,
        average_entry_price=0.40,
        average_current_price=0.50,
        weighted_entry_edge=weighted_entry_edge,
        positive_positions=7,
        negative_positions=3,
        neutral_positions=0,
        observed_win_rate=observed_win_rate,
        average_percent_pnl=15.0,
        pnl_volatility=pnl_volatility,
        total_shares=2000.0,
        total_bought=total_invested,
        first_seen_at="2026-07-20T10:00:00+00:00",
        last_seen_at="2026-07-22T10:00:00+00:00",
        source_duplicates_removed=0,
        duplicate_positions_removed=0,
    )


class PercentileScoreTests(unittest.TestCase):
    def test_higher_value_receives_higher_percentile(self) -> None:
        population = [1.0, 2.0, 3.0, 4.0]

        self.assertGreater(
            percentile_score(4.0, population),
            percentile_score(1.0, population),
        )

    def test_lower_value_can_be_better(self) -> None:
        population = [1.0, 2.0, 3.0, 4.0]

        self.assertGreater(
            percentile_score(
                1.0,
                population,
                higher_is_better=False,
            ),
            percentile_score(
                4.0,
                population,
                higher_is_better=False,
            ),
        )

    def test_empty_population_returns_neutral_score(self) -> None:
        self.assertEqual(percentile_score(10.0, []), 50.0)


class GradeTests(unittest.TestCase):
    def test_low_confidence_is_provisional(self) -> None:
        self.assertEqual(
            grade_from_score(95.0, confidence_score=20.0),
            "PROVISIONAL",
        )

    def test_documented_grade_boundaries(self) -> None:
        self.assertEqual(grade_from_score(92.0, 80.0), "S")
        self.assertEqual(grade_from_score(85.0, 80.0), "A+")
        self.assertEqual(grade_from_score(78.0, 80.0), "A")
        self.assertEqual(grade_from_score(70.0, 80.0), "B+")
        self.assertEqual(grade_from_score(62.0, 80.0), "B")
        self.assertEqual(grade_from_score(52.0, 80.0), "C")
        self.assertEqual(grade_from_score(40.0, 80.0), "D")


class WalletScoringEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = WalletScoringEngine()

    def test_empty_population_returns_empty_results(self) -> None:
        self.assertEqual(self.engine.score_population([]), [])

    def test_single_wallet_produces_score(self) -> None:
        result = self.engine.score_population(
            [metrics(WALLET_1)]
        )

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], WalletScore)
        self.assertEqual(result[0].wallet, WALLET_1)
        self.assertEqual(
            result[0].model_version,
            SCORE_MODEL_VERSION,
        )

    def test_all_component_scores_are_bounded(self) -> None:
        result = self.engine.score_population(
            [
                metrics(WALLET_1),
                metrics(
                    WALLET_2,
                    roi=-0.10,
                    total_pnl=-100.0,
                    weighted_entry_edge=-0.05,
                ),
            ]
        )

        for score in result:
            for value in (
                score.performance_score,
                score.timing_score,
                score.consistency_score,
                score.risk_score,
                score.conviction_score,
                score.confidence_score,
                score.overall_score,
            ):
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 100.0)

    def test_stronger_wallet_ranks_above_weaker_wallet(self) -> None:
        strong = metrics(
            WALLET_1,
            positions_observed=40,
            markets_tracked=30,
            total_current_value=5000.0,
            total_pnl=1500.0,
            roi=0.40,
            average_position_value=250.0,
            largest_position_value=700.0,
            concentration_ratio=0.14,
            weighted_entry_edge=0.18,
            observed_win_rate=0.82,
            pnl_volatility=8.0,
        )
        weak = metrics(
            WALLET_2,
            positions_observed=4,
            markets_tracked=2,
            total_current_value=300.0,
            total_pnl=-75.0,
            roi=-0.20,
            average_position_value=75.0,
            largest_position_value=250.0,
            concentration_ratio=0.83,
            weighted_entry_edge=-0.08,
            observed_win_rate=0.25,
            pnl_volatility=50.0,
        )

        result = self.engine.score_population([weak, strong])

        self.assertEqual(result[0].wallet, WALLET_1)
        self.assertGreater(
            result[0].overall_score,
            result[1].overall_score,
        )

    def test_low_history_wallet_is_provisional(self) -> None:
        shallow = metrics(
            WALLET_1,
            positions_observed=0,
            markets_tracked=0,
        )

        result = self.engine.score_population([shallow])

        self.assertEqual(result[0].overall_grade, "PROVISIONAL")

    def test_high_concentration_creates_risk_note(self) -> None:
        concentrated = metrics(
            WALLET_1,
            concentration_ratio=0.80,
        )

        result = self.engine.score_population([concentrated])

        self.assertIn(
            "high position concentration",
            result[0].notes,
        )

    def test_positive_roi_and_edge_create_explanations(self) -> None:
        result = self.engine.score_population(
            [
                metrics(WALLET_1),
                metrics(
                    WALLET_2,
                    roi=-0.10,
                    weighted_entry_edge=-0.05,
                ),
            ]
        )

        score = next(
            item for item in result
            if item.wallet == WALLET_1
        )

        self.assertIn("positive observed ROI", score.notes)
        self.assertIn(
            "positive observed entry edge",
            score.notes,
        )

    def test_results_are_deterministic(self) -> None:
        population = [
            metrics(WALLET_1),
            metrics(
                WALLET_2,
                roi=0.10,
                total_pnl=100.0,
            ),
            metrics(
                WALLET_3,
                roi=-0.05,
                total_pnl=-50.0,
            ),
        ]

        first = self.engine.score_population(population)
        second = self.engine.score_population(population)

        self.assertEqual(first, second)

    def test_input_metrics_are_not_modified(self) -> None:
        original = metrics(WALLET_1)
        comparison = replace(original)

        self.engine.score_population([original])

        self.assertEqual(original, comparison)


if __name__ == "__main__":
    unittest.main()