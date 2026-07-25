from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThresholdSettings:
    """
    Platform intelligence thresholds.

    These values define the minimum requirements for
    wallet qualification, consensus, conviction,
    and opportunity ranking.
    """

    minimum_position_value: float = 500.0
    minimum_wallet_score: float = 70.0
    minimum_agreeing_wallets: int = 2
    minimum_conviction_score: float = 75.0
    minimum_confidence_score: float = 80.0
    elite_wallet_percentile: float = 95.0


THRESHOLD_SETTINGS = ThresholdSettings()
