from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .time import utc_now_iso


@dataclass(slots=True)
class TelemetryRecord:
    """
    Execution telemetry produced by an engine or infrastructure component.
    """

    component: str
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None
    duration_seconds: float = 0.0
    counters: dict[str, int | float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def increment(
        self,
        name: str,
        amount: int | float = 1,
    ) -> None:
        current_value = self.counters.get(name, 0)
        self.counters[name] = current_value + amount

    def set_counter(
        self,
        name: str,
        value: int | float,
    ) -> None:
        self.counters[name] = value

    def add_error(self, error: object) -> None:
        self.errors.append(str(error))


class TelemetryTimer:
    """
    Context manager that measures a TelemetryRecord's execution time.
    """

    def __init__(self, record: TelemetryRecord) -> None:
        self._record = record
        self._started_clock: float | None = None

    def __enter__(self) -> TelemetryRecord:
        self._started_clock = time.perf_counter()
        return self._record

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object | None,
    ) -> bool:
        if self._started_clock is None:
            return False

        self._record.duration_seconds = (
            time.perf_counter() - self._started_clock
        )

        self._record.completed_at = utc_now_iso()

        if exception is not None:
            self._record.add_error(exception)

        return False