from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable

try:
    from wallet_intelligence_source import (
        WalletPositionObservation,
        WalletSourceResult,
    )
except ImportError:
    from src.wallet_intelligence_source import (
        WalletPositionObservation,
        WalletSourceResult,
    )


def rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


@dataclass(frozen=True, slots=True)
class WalletRawMetrics:
    """
    Objective wallet measurements.

    This model intentionally contains no percentile ranks, intelligence
    grades, tiers, or opinions about wallet quality.
    """

    wallet: str

    source_name: str
    source_run_id: str
    source_observed_at: str

    positions_observed: int
    markets_tracked: int
    confidence_observations: int

    total_current_value: float
    total_invested: float

    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    roi: float

    average_position_value: float
    median_position_value: float
    largest_position_value: float
    concentration_ratio: float

    average_entry_price: float
    average_current_price: float
    weighted_entry_edge: float

    positive_positions: int
    negative_positions: int
    neutral_positions: int
    observed_win_rate: float

    average_percent_pnl: float
    pnl_volatility: float

    total_shares: float
    total_bought: float

    first_seen_at: str
    last_seen_at: str

    source_duplicates_removed: int
    duplicate_positions_removed: int


class WalletMetricsEngine:
    """
    Convert one standardized wallet source result into raw metrics.

    The engine is intentionally independent of SQLite, APIs, rankings,
    percentiles, intelligence scores, and persistence.
    """

    def calculate(
        self,
        source: WalletSourceResult,
    ) -> WalletRawMetrics:
        positions, duplicate_positions_removed = self._deduplicate(
            source.positions
        )

        if not positions:
            return self._empty_metrics(source)

        values = [
            max(0.0, float(position.current_value))
            for position in positions
        ]
        shares = [
            max(0.0, float(position.shares))
            for position in positions
        ]
        total_bought_values = [
            max(0.0, float(position.total_bought))
            for position in positions
        ]

        unrealized_pnls = [
            float(position.cash_pnl)
            for position in positions
        ]
        realized_pnls = [
            float(position.realized_pnl)
            for position in positions
        ]
        combined_position_pnls = [
            float(position.cash_pnl)
            + float(position.realized_pnl)
            for position in positions
        ]

        percent_pnls = [
            float(position.percent_pnl)
            for position in positions
        ]

        entry_prices = [
            float(position.average_price)
            for position in positions
            if float(position.average_price) > 0
        ]
        current_prices = [
            float(position.current_price)
            for position in positions
            if float(position.current_price) > 0
        ]

        total_current_value = sum(values)
        reported_total_bought = sum(total_bought_values)

        unrealized_pnl = sum(unrealized_pnls)
        realized_pnl = sum(realized_pnls)
        total_pnl = unrealized_pnl + realized_pnl

        # The collector's total_bought field is preferred because it
        # represents reported capital deployed. Legacy rows may not contain
        # it, so current value minus unrealized PnL is used as a fallback.
        fallback_invested = max(
            total_current_value - unrealized_pnl,
            0.0,
        )
        total_invested = (
            reported_total_bought
            if reported_total_bought > 0
            else fallback_invested
        )

        roi = (
            total_pnl / total_invested
            if total_invested > 0
            else 0.0
        )

        average_position_value = statistics.mean(values)
        median_position_value = statistics.median(values)
        largest_position_value = max(values)

        concentration_ratio = (
            largest_position_value / total_current_value
            if total_current_value > 0
            else 0.0
        )

        average_entry_price = (
            statistics.mean(entry_prices)
            if entry_prices
            else 0.0
        )
        average_current_price = (
            statistics.mean(current_prices)
            if current_prices
            else 0.0
        )

        weighted_entry_edge = self._weighted_entry_edge(
            positions
        )

        positive_positions = sum(
            1
            for pnl in combined_position_pnls
            if pnl > 0
        )
        negative_positions = sum(
            1
            for pnl in combined_position_pnls
            if pnl < 0
        )
        neutral_positions = (
            len(combined_position_pnls)
            - positive_positions
            - negative_positions
        )

        decisive_positions = (
            positive_positions + negative_positions
        )
        observed_win_rate = (
            positive_positions / decisive_positions
            if decisive_positions > 0
            else 0.0
        )

        average_percent_pnl = (
            statistics.mean(percent_pnls)
            if percent_pnls
            else 0.0
        )
        pnl_volatility = (
            statistics.pstdev(percent_pnls)
            if len(percent_pnls) >= 2
            else 0.0
        )

        market_ids = {
            position.market_id.strip().lower()
            for position in positions
            if position.market_id.strip()
        }

        observed_times = sorted(
            position.observed_at
            for position in positions
            if position.observed_at
        )

        first_seen_at = (
            observed_times[0]
            if observed_times
            else source.observed_at
        )
        last_seen_at = (
            observed_times[-1]
            if observed_times
            else source.observed_at
        )

        return WalletRawMetrics(
            wallet=source.wallet,
            source_name=source.source_name,
            source_run_id=source.source_run_id,
            source_observed_at=source.observed_at,
            positions_observed=len(positions),
            markets_tracked=len(market_ids),
            confidence_observations=len(positions),
            total_current_value=rounded(
                total_current_value,
                2,
            ),
            total_invested=rounded(
                total_invested,
                2,
            ),
            realized_pnl=rounded(
                realized_pnl,
                2,
            ),
            unrealized_pnl=rounded(
                unrealized_pnl,
                2,
            ),
            total_pnl=rounded(
                total_pnl,
                2,
            ),
            roi=rounded(roi),
            average_position_value=rounded(
                average_position_value,
                2,
            ),
            median_position_value=rounded(
                median_position_value,
                2,
            ),
            largest_position_value=rounded(
                largest_position_value,
                2,
            ),
            concentration_ratio=rounded(
                concentration_ratio
            ),
            average_entry_price=rounded(
                average_entry_price
            ),
            average_current_price=rounded(
                average_current_price
            ),
            weighted_entry_edge=rounded(
                weighted_entry_edge
            ),
            positive_positions=positive_positions,
            negative_positions=negative_positions,
            neutral_positions=neutral_positions,
            observed_win_rate=rounded(
                observed_win_rate
            ),
            average_percent_pnl=rounded(
                average_percent_pnl
            ),
            pnl_volatility=rounded(
                pnl_volatility
            ),
            total_shares=rounded(
                sum(shares),
                6,
            ),
            total_bought=rounded(
                reported_total_bought,
                2,
            ),
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            source_duplicates_removed=(
                source.duplicate_rows_removed
            ),
            duplicate_positions_removed=(
                duplicate_positions_removed
            ),
        )

    @staticmethod
    def _weighted_entry_edge(
        positions: Iterable[WalletPositionObservation],
    ) -> float:
        numerator = 0.0
        denominator = 0.0

        for position in positions:
            entry_price = float(position.average_price)
            current_price = float(position.current_price)
            current_value = max(
                float(position.current_value),
                0.0,
            )

            if (
                entry_price <= 0
                or current_price <= 0
                or current_value <= 0
            ):
                continue

            numerator += (
                current_price - entry_price
            ) * current_value
            denominator += current_value

        return (
            numerator / denominator
            if denominator > 0
            else 0.0
        )

    @staticmethod
    def _deduplicate(
        positions: Iterable[WalletPositionObservation],
    ) -> tuple[
        list[WalletPositionObservation],
        int,
    ]:
        """
        Defensive deduplication.

        The source adapter already removes duplicate identities, but this
        protects the metrics engine when it is called directly by tests,
        future adapters, or imported data sources.
        """
        by_identity: dict[
            tuple[str, ...],
            WalletPositionObservation,
        ] = {}
        total_rows = 0

        for position in positions:
            total_rows += 1
            by_identity[position.identity_key] = position

        deduplicated = sorted(
            by_identity.values(),
            key=lambda position: (
                position.market_id,
                position.outcome_index
                if position.outcome_index is not None
                else -1,
                position.outcome,
                position.asset,
            ),
        )

        return (
            deduplicated,
            total_rows - len(deduplicated),
        )

    @staticmethod
    def _empty_metrics(
        source: WalletSourceResult,
    ) -> WalletRawMetrics:
        return WalletRawMetrics(
            wallet=source.wallet,
            source_name=source.source_name,
            source_run_id=source.source_run_id,
            source_observed_at=source.observed_at,
            positions_observed=0,
            markets_tracked=0,
            confidence_observations=0,
            total_current_value=0.0,
            total_invested=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_pnl=0.0,
            roi=0.0,
            average_position_value=0.0,
            median_position_value=0.0,
            largest_position_value=0.0,
            concentration_ratio=0.0,
            average_entry_price=0.0,
            average_current_price=0.0,
            weighted_entry_edge=0.0,
            positive_positions=0,
            negative_positions=0,
            neutral_positions=0,
            observed_win_rate=0.0,
            average_percent_pnl=0.0,
            pnl_volatility=0.0,
            total_shares=0.0,
            total_bought=0.0,
            first_seen_at=source.observed_at,
            last_seen_at=source.observed_at,
            source_duplicates_removed=(
                source.duplicate_rows_removed
            ),
            duplicate_positions_removed=0,
        )