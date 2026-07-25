from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Sequence


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    name: str
    status: HealthStatus
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)


HealthCheck = Callable[[], HealthCheckResult]


@dataclass(frozen=True, slots=True)
class Capability:
    capability_id: str
    name: str
    version: str
    description: str
    provides: Sequence[str] = field(default_factory=tuple)
    dependencies: Sequence[str] = field(default_factory=tuple)
    health_checks: Sequence[HealthCheck] = field(default_factory=tuple)
    enabled: bool = True

    def validate(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id cannot be empty")
        if not self.name.strip():
            raise ValueError("name cannot be empty")
        if not self.version.strip():
            raise ValueError("version cannot be empty")
