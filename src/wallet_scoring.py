from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    from wallet_metrics import WalletRawMetrics
except ImportError:
    from src.wallet_metrics import WalletRawMetrics


SCORE_MODEL_NAME = "wallet-cross-sectional"
SCORE_MODEL_VERSION = "1.0.0"

PROVISIONAL_CONFIDENCE_THRESHOLD = 25.0


def clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:
    return max(low, min(high, float(value)))


def rounded(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def percentile_score(
    value: float,
    population: Sequence[float],
    higher_is_better: bool = True,
) -> float:
    """
    Return a midpoint percentile rank from 0 to 100.

    Equal values receive the midpoint of their shared percentile range.
    """
    if not population:
        return 50.0

    ordered = sorted(float(item) for item in population)
    target = float(value)

    below = sum(1 for item in ordered if item < target)
    equal = sum(1 for item in ordered if item == target)

    percentile = (
        (below + 0.5 * equal)
        / len(ordered)
        * 100.0
    )

    if higher_is_better:
        return clamp(percentile)

    return clamp(100.0 - percentile)


def grade_from_score(
    score: float,
    confidence_score: float,
) -> str:
    if confidence_score < PROVISIONAL_CONFIDENCE_THRESHOLD:
        return "PROVISIONAL"
    if score >= 92:
        return "S"
    if score >= 85:
        return "A+"
    if score >= 78:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 62:
        return "B"
    if score >= 52:
        return "C"
    return "D"


@dataclass(frozen=True, slots=True)
class WalletScore:
    wallet: str

    model_name: str
    model_version: str

    performance_score: float
    timing_score: float
    consistency_score: float
    risk_score: float
    conviction_score: float
    confidence_score: float

    overall_score: float
    overall_grade: str
    rank: int

    notes: str


class WalletScoringEngine:
    """
    Versioned cross-sectional scoring model.

    This engine consumes objective WalletRawMetrics and produces comparative
    intelligence scores. It does not access SQLite, APIs, or raw snapshots.
    """

    def score_population(
        self,
        metrics_population: Iterable[WalletRawMetrics],
    ) -> list[WalletScore]:
        population = list(metrics_population)

        if not population:
            return []

        positions = [
            float(item.positions_observed)
            for item in population
        ]
        markets = [
            float(item.markets_tracked)
            for item in population
        ]
        total_values = [
            float(item.total_current_value)
            for item in population
        ]
        average_values = [
            float(item.average_position_value)
            for item in population
        ]
        largest_values = [
            float(item.largest_position_value)
            for item in population
        ]
        rois = [
            float(item.roi)
            for item in population
        ]
        pnls = [
            float(item.total_pnl)
            for item in population
        ]
        entry_edges = [
            float(item.weighted_entry_edge)
            for item in population
        ]
        win_rates = [
            float(item.observed_win_rate)
            for item in population
        ]
        concentrations = [
            float(item.concentration_ratio)
            for item in population
        ]
        volatilities = [
            float(item.pnl_volatility)
            for item in population
        ]

        provisional_results: list[WalletScore] = []

        for item in population:
            confidence_score = self._confidence_score(
                item,
                positions,
                markets,
            )

            conviction_score = clamp(
                0.45
                * percentile_score(
                    item.average_position_value,
                    average_values,
                )
                + 0.35
                * percentile_score(
                    item.largest_position_value,
                    largest_values,
                )
                + 0.20
                * percentile_score(
                    item.total_current_value,
                    total_values,
                )
            )

            consistency_score = clamp(
                0.50
                * percentile_score(
                    item.observed_win_rate,
                    win_rates,
                )
                + 0.30
                * percentile_score(
                    item.pnl_volatility,
                    volatilities,
                    higher_is_better=False,
                )
                + 0.20
                * percentile_score(
                    item.roi,
                    rois,
                )
            )

            risk_score = clamp(
                0.50
                * percentile_score(
                    item.concentration_ratio,
                    concentrations,
                    higher_is_better=False,
                )
                + 0.30
                * percentile_score(
                    item.pnl_volatility,
                    volatilities,
                    higher_is_better=False,
                )
                + 0.20
                * percentile_score(
                    item.markets_tracked,
                    markets,
                )
            )

            timing_score = clamp(
                0.70
                * percentile_score(
                    item.weighted_entry_edge,
                    entry_edges,
                )
                + 0.30
                * percentile_score(
                    item.roi,
                    rois,
                )
            )

            performance_score = clamp(
                0.55
                * percentile_score(
                    item.roi,
                    rois,
                )
                + 0.25
                * percentile_score(
                    item.total_pnl,
                    pnls,
                )
                + 0.20
                * percentile_score(
                    item.weighted_entry_edge,
                    entry_edges,
                )
            )

            # Version 1 omits recent-form because the standardized metrics
            # layer does not yet provide a defensible historical time window.
            # The remaining legacy weights are normalized to sum to 1.0.
            overall_score = clamp(
                0.272727 * performance_score
                + 0.193182 * timing_score
                + 0.181818 * consistency_score
                + 0.159091 * risk_score
                + 0.102273 * conviction_score
                + 0.090909 * confidence_score
            )

            notes = self._build_notes(
                item=item,
                confidence_score=confidence_score,
            )

            provisional_results.append(
                WalletScore(
                    wallet=item.wallet,
                    model_name=SCORE_MODEL_NAME,
                    model_version=SCORE_MODEL_VERSION,
                    performance_score=rounded(
                        performance_score
                    ),
                    timing_score=rounded(timing_score),
                    consistency_score=rounded(
                        consistency_score
                    ),
                    risk_score=rounded(risk_score),
                    conviction_score=rounded(
                        conviction_score
                    ),
                    confidence_score=rounded(
                        confidence_score
                    ),
                    overall_score=rounded(overall_score),
                    overall_grade=grade_from_score(
                        overall_score,
                        confidence_score,
                    ),
                    rank=0,
                    notes="; ".join(notes),
                )
            )

        provisional_results.sort(
            key=lambda item: (
                item.overall_score,
                item.confidence_score,
                item.performance_score,
                item.wallet,
            ),
            reverse=True,
        )

        return [
            WalletScore(
                wallet=item.wallet,
                model_name=item.model_name,
                model_version=item.model_version,
                performance_score=item.performance_score,
                timing_score=item.timing_score,
                consistency_score=item.consistency_score,
                risk_score=item.risk_score,
                conviction_score=item.conviction_score,
                confidence_score=item.confidence_score,
                overall_score=item.overall_score,
                overall_grade=item.overall_grade,
                rank=rank,
                notes=item.notes,
            )
            for rank, item in enumerate(
                provisional_results,
                start=1,
            )
        ]

    @staticmethod
    def _confidence_score(
        item: WalletRawMetrics,
        position_population: Sequence[float],
        market_population: Sequence[float],
    ) -> float:
        data_depth = clamp(
            35.0 * math.log1p(
                max(item.confidence_observations, 0)
            )
            + 15.0 * math.log1p(
                max(item.markets_tracked, 0)
            )
        )

        return clamp(
            0.55 * data_depth
            + 0.25
            * percentile_score(
                item.positions_observed,
                position_population,
            )
            + 0.20
            * percentile_score(
                item.markets_tracked,
                market_population,
            )
        )

    @staticmethod
    def _build_notes(
        *,
        item: WalletRawMetrics,
        confidence_score: float,
    ) -> list[str]:
        notes: list[str] = []

        if confidence_score < PROVISIONAL_CONFIDENCE_THRESHOLD:
            notes.append(
                "insufficient history for a stable rating"
            )

        if item.concentration_ratio > 0.70:
            notes.append("high position concentration")

        if item.weighted_entry_edge > 0:
            notes.append("positive observed entry edge")
        elif item.weighted_entry_edge < 0:
            notes.append("negative observed entry edge")

        if item.roi > 0:
            notes.append("positive observed ROI")
        elif item.roi < 0:
            notes.append("negative observed ROI")

        if item.source_name == "legacy":
            notes.append("legacy source fallback used")

        if (
            item.source_duplicates_removed > 0
            or item.duplicate_positions_removed > 0
        ):
            notes.append("duplicate source rows removed")

        if not notes:
            notes.append("neutral observed profile")

        return notes