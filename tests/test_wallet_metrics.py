from __future__ import annotations

import unittest

from src.wallet_intelligence_source import (
    WalletPositionObservation,
    WalletSourceResult,
)
from src.wallet_metrics import (
    WalletMetricsEngine,
    WalletRawMetrics,
)


WALLET = "0x1111111111111111111111111111111111111111"


def position(
    *,
    market_id: str,
    asset: str,
    outcome: str = "Yes",
    outcome_index: int | None = 0,
    shares: float = 100.0,
    average_price: float = 0.40,
    current_price: float = 0.60,
    current_value: float = 60.0,
    cash_pnl: float = 20.0,
    percent_pnl: float = 50.0,
    realized_pnl: float = 0.0,
    total_bought: float = 40.0,
    observed_at: str = "2026-07-22T10:00:00+00:00",
) -> WalletPositionObservation:
    return WalletPositionObservation(
        wallet=WALLET,
        market_id=market_id,
        title=f"Market {market_id}",
        outcome=outcome,
        outcome_index=outcome_index,
        asset=asset,
        shares=shares,
        average_price=average_price,
        current_price=current_price,
        current_value=current_value,
        cash_pnl=cash_pnl,
        percent_pnl=percent_pnl,
        realized_pnl=realized_pnl,
        total_bought=total_bought,
        observed_at=observed_at,
        source_run_id="run-1",
        source_name="production",
    )


def source_result(
    positions: tuple[WalletPositionObservation, ...],
    *,
    source_name: str = "production",
    duplicate_rows_removed: int = 0,
) -> WalletSourceResult:
    return WalletSourceResult(
        wallet=WALLET,
        source_name=source_name,
        source_run_id="run-1",
        observed_at="2026-07-22T10:00:00+00:00",
        positions=positions,
        duplicate_rows_removed=duplicate_rows_removed,
    )


class WalletMetricsEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = WalletMetricsEngine()

    def test_empty_wallet_returns_zeroed_metrics(self) -> None:
        result = source_result(())

        metrics = self.engine.calculate(result)

        self.assertIsInstance(metrics, WalletRawMetrics)
        self.assertEqual(metrics.wallet, WALLET)
        self.assertEqual(metrics.positions_observed, 0)
        self.assertEqual(metrics.markets_tracked, 0)
        self.assertEqual(metrics.realized_pnl, 0.0)
        self.assertEqual(metrics.unrealized_pnl, 0.0)
        self.assertEqual(metrics.total_pnl, 0.0)
        self.assertEqual(metrics.roi, 0.0)
        self.assertEqual(metrics.concentration_ratio, 0.0)
        self.assertEqual(metrics.observed_win_rate, 0.0)
        self.assertEqual(metrics.confidence_observations, 0)

    def test_realized_and_unrealized_pnl_remain_separate(self) -> None:
        result = source_result(
            (
                position(
                    market_id="market-1",
                    asset="asset-1",
                    cash_pnl=25.0,
                    realized_pnl=10.0,
                ),
                position(
                    market_id="market-2",
                    asset="asset-2",
                    cash_pnl=-5.0,
                    realized_pnl=3.0,
                ),
            )
        )

        metrics = self.engine.calculate(result)

        self.assertEqual(metrics.unrealized_pnl, 20.0)
        self.assertEqual(metrics.realized_pnl, 13.0)
        self.assertEqual(metrics.total_pnl, 33.0)

    def test_roi_uses_total_bought_as_invested_capital(self) -> None:
        result = source_result(
            (
                position(
                    market_id="market-1",
                    asset="asset-1",
                    cash_pnl=20.0,
                    realized_pnl=10.0,
                    total_bought=100.0,
                ),
                position(
                    market_id="market-2",
                    asset="asset-2",
                    cash_pnl=10.0,
                    realized_pnl=0.0,
                    total_bought=100.0,
                ),
            )
        )

        metrics = self.engine.calculate(result)

        self.assertEqual(metrics.total_invested, 200.0)
        self.assertAlmostEqual(metrics.roi, 0.20)

    def test_roi_falls_back_when_total_bought_is_missing(self) -> None:
        result = source_result(
            (
                position(
                    market_id="market-1",
                    asset="asset-1",
                    current_value=120.0,
                    cash_pnl=20.0,
                    realized_pnl=0.0,
                    total_bought=0.0,
                ),
            )
        )

        metrics = self.engine.calculate(result)

        self.assertEqual(metrics.total_invested, 100.0)
        self.assertAlmostEqual(metrics.roi, 0.20)

    def test_concentration_ratio_is_largest_position_share(self) -> None:
        result = source_result(
            (
                position(
                    market_id="market-1",
                    asset="asset-1",
                    current_value=75.0,
                ),
                position(
                    market_id="market-2",
                    asset="asset-2",
                    current_value=25.0,
                ),
            )
        )

        metrics = self.engine.calculate(result)

        self.assertEqual(metrics.total_current_value, 100.0)
        self.assertEqual(metrics.largest_position_value, 75.0)
        self.assertAlmostEqual(metrics.concentration_ratio, 0.75)

    def test_position_outcomes_determine_observed_win_rate(self) -> None:
        result = source_result(
            (
                position(
                    market_id="market-1",
                    asset="asset-1",
                    cash_pnl=15.0,
                    realized_pnl=0.0,
                ),
                position(
                    market_id="market-2",
                    asset="asset-2",
                    cash_pnl=-5.0,
                    realized_pnl=0.0,
                ),
                position(
                    market_id="market-3",
                    asset="asset-3",
                    cash_pnl=0.0,
                    realized_pnl=0.0,
                ),
            )
        )

        metrics = self.engine.calculate(result)

        self.assertEqual(metrics.positive_positions, 1)
        self.assertEqual(metrics.negative_positions, 1)
        self.assertEqual(metrics.neutral_positions, 1)
        self.assertAlmostEqual(metrics.observed_win_rate, 0.50)

    def test_weighted_entry_edge_uses_position_value(self) -> None:
        result = source_result(
            (
                position(
                    market_id="market-1",
                    asset="asset-1",
                    average_price=0.40,
                    current_price=0.60,
                    current_value=75.0,
                ),
                position(
                    market_id="market-2",
                    asset="asset-2",
                    average_price=0.50,
                    current_price=0.40,
                    current_value=25.0,
                ),
            )
        )

        metrics = self.engine.calculate(result)

        expected = ((0.20 * 75.0) + (-0.10 * 25.0)) / 100.0
        self.assertAlmostEqual(metrics.weighted_entry_edge, expected)

    def test_duplicate_positions_are_defensively_removed(self) -> None:
        original = position(
            market_id="market-1",
            asset="asset-1",
            current_value=50.0,
            cash_pnl=5.0,
        )
        replacement = position(
            market_id="market-1",
            asset="asset-1",
            current_value=80.0,
            cash_pnl=20.0,
        )

        result = source_result((original, replacement))

        metrics = self.engine.calculate(result)

        self.assertEqual(metrics.positions_observed, 1)
        self.assertEqual(metrics.total_current_value, 80.0)
        self.assertEqual(metrics.unrealized_pnl, 20.0)
        self.assertEqual(metrics.duplicate_positions_removed, 1)

    def test_unique_market_count_does_not_count_outcomes_twice(self) -> None:
        result = source_result(
            (
                position(
                    market_id="market-1",
                    asset="asset-yes",
                    outcome="Yes",
                    outcome_index=0,
                ),
                position(
                    market_id="market-1",
                    asset="asset-no",
                    outcome="No",
                    outcome_index=1,
                ),
                position(
                    market_id="market-2",
                    asset="asset-2",
                ),
            )
        )

        metrics = self.engine.calculate(result)

        self.assertEqual(metrics.positions_observed, 3)
        self.assertEqual(metrics.markets_tracked, 2)

    def test_first_and_last_seen_are_calculated_from_observations(self) -> None:
        result = source_result(
            (
                position(
                    market_id="market-1",
                    asset="asset-1",
                    observed_at="2026-07-20T10:00:00+00:00",
                ),
                position(
                    market_id="market-2",
                    asset="asset-2",
                    observed_at="2026-07-22T10:00:00+00:00",
                ),
            )
        )

        metrics = self.engine.calculate(result)

        self.assertEqual(
            metrics.first_seen_at,
            "2026-07-20T10:00:00+00:00",
        )
        self.assertEqual(
            metrics.last_seen_at,
            "2026-07-22T10:00:00+00:00",
        )

    def test_metrics_are_deterministic(self) -> None:
        result = source_result(
            (
                position(
                    market_id="market-1",
                    asset="asset-1",
                ),
                position(
                    market_id="market-2",
                    asset="asset-2",
                    current_value=25.0,
                    cash_pnl=-5.0,
                ),
            )
        )

        first = self.engine.calculate(result)
        second = self.engine.calculate(result)

        self.assertEqual(first, second)

    def test_source_metadata_is_preserved(self) -> None:
        result = source_result(
            (position(market_id="market-1", asset="asset-1"),),
            source_name="legacy",
            duplicate_rows_removed=2,
        )

        metrics = self.engine.calculate(result)

        self.assertEqual(metrics.source_name, "legacy")
        self.assertEqual(metrics.source_run_id, "run-1")
        self.assertEqual(metrics.source_duplicates_removed, 2)


if __name__ == "__main__":
    unittest.main()