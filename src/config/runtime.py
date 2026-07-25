from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    """
    Runtime configuration for the platform.
    """

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    enable_cache: bool = True
    max_workers: int = 4
    scan_interval_seconds: int = 300


RUNTIME_SETTINGS = RuntimeSettings()
