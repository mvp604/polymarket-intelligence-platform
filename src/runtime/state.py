"""Runtime execution state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class RuntimeMode(StrEnum):
    """Supported platform runtime modes."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RuntimeState:
    """Mutable state for one platform execution run."""

    run_id: str = field(default_factory=lambda: str(uuid4()))
    started_at: datetime = field(default_factory=utc_now)
    mode: RuntimeMode = RuntimeMode.DEVELOPMENT
    active_engine: str | None = None
    completed_engines: list[str] = field(default_factory=list)
    failed_engines: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    shutdown_requested: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_active(self, engine_name: str) -> None:
        """Mark an engine as currently executing."""

        normalized = engine_name.strip()

        if not normalized:
            raise ValueError("engine_name cannot be empty.")

        self.active_engine = normalized

    def mark_completed(self, engine_name: str) -> None:
        """Record a successful engine execution."""

        normalized = engine_name.strip()

        if not normalized:
            raise ValueError("engine_name cannot be empty.")

        if normalized not in self.completed_engines:
            self.completed_engines.append(normalized)

        self.failed_engines.pop(normalized, None)

        if self.active_engine == normalized:
            self.active_engine = None

    def mark_failed(
        self,
        engine_name: str,
        error: Exception | str,
    ) -> None:
        """Record a failed engine execution."""

        normalized = engine_name.strip()

        if not normalized:
            raise ValueError("engine_name cannot be empty.")

        self.failed_engines[normalized] = str(error)

        if self.active_engine == normalized:
            self.active_engine = None

    def add_warning(self, warning: str) -> None:
        """Add a unique runtime warning."""

        normalized = warning.strip()

        if not normalized:
            raise ValueError("warning cannot be empty.")

        if normalized not in self.warnings:
            self.warnings.append(normalized)

    def request_shutdown(self) -> None:
        """Request a graceful runtime shutdown."""

        self.shutdown_requested = True

    @property
    def has_failures(self) -> bool:
        """Return whether an engine has failed."""

        return bool(self.failed_engines)

    @property
    def is_idle(self) -> bool:
        """Return whether no engine is currently active."""

        return self.active_engine is None
