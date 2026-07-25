from __future__ import annotations

from dataclasses import dataclass

from .api import ApiSettings, API_SETTINGS
from .database import DatabaseSettings, DATABASE_SETTINGS
from .runtime import RuntimeSettings, RUNTIME_SETTINGS
from .thresholds import ThresholdSettings, THRESHOLD_SETTINGS


@dataclass(frozen=True, slots=True)
class Settings:
    """
    Root immutable configuration for the
    Polymarket Intelligence Platform.
    """

    database: DatabaseSettings
    runtime: RuntimeSettings
    api: ApiSettings
    thresholds: ThresholdSettings


SETTINGS = Settings(
    database=DATABASE_SETTINGS,
    runtime=RUNTIME_SETTINGS,
    api=API_SETTINGS,
    thresholds=THRESHOLD_SETTINGS,
)
