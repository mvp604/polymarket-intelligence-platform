"""Sequential execution of immutable runtime plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from time import perf_counter
from types import MappingProxyType
from typing import Any, Mapping

from .context import PlatformContext
from .planner import ExecutionPlan, ExecutionStep
from .registry import EngineRegistry


class ErrorPolicy(str, Enum):
    """Control how execution responds to engine failures."""

    STRICT = "strict"
    CONTINUE = "continue"
    SKIP_DEPENDENTS = "skip_dependents"


class EngineStatus(str, Enum):
    """Final status of one planned engine."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class EngineExecutionResult:
    """Immutable result for one engine execution."""

    engine_name: str
    status: EngineStatus
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float
    output: Any = None
    error_type: str | None = None
    error_message: str | None = None
    skipped_reason: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is EngineStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status is EngineStatus.FAILED

    @property
    def skipped(self) -> bool:
        return self.status is EngineStatus.SKIPPED


@dataclass(frozen=True, slots=True)
class RuntimeReport:
    """Immutable report for one runtime execution."""

    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    results: tuple[EngineExecutionResult, ...]
    error_policy: ErrorPolicy
    _results_by_name: Mapping[str, EngineExecutionResult]

    @classmethod
    def build(
        cls,
        *,
        started_at: datetime,
        finished_at: datetime,
        duration_seconds: float,
        results: tuple[EngineExecutionResult, ...],
        error_policy: ErrorPolicy,
    ) -> "RuntimeReport":
        """Build and validate a runtime report."""

        if duration_seconds < 0:
            raise ValueError(
                "duration_seconds cannot be negative."
            )

        results_by_name = {
            result.engine_name: result
            for result in results
        }

        if len(results_by_name) != len(results):
            raise ValueError(
                "Runtime report contains duplicate engine names."
            )

        return cls(
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            results=results,
            error_policy=error_policy,
            _results_by_name=MappingProxyType(
                results_by_name
            ),
        )

    @property
    def success(self) -> bool:
        """Return whether every planned engine succeeded."""

        return all(
            result.succeeded
            for result in self.results
        )

    @property
    def failed_engines(self) -> tuple[str, ...]:
        """Return failed engine names in execution order."""

        return tuple(
            result.engine_name
            for result in self.results
            if result.failed
        )

    @property
    def skipped_engines(self) -> tuple[str, ...]:
        """Return skipped engine names in execution order."""

        return tuple(
            result.engine_name
            for result in self.results
            if result.skipped
        )

    def require(
        self,
        engine_name: str,
    ) -> EngineExecutionResult:
        """Return one result or raise a clear error."""

        normalized = self._normalize_name(
            engine_name
        )

        try:
            return self._results_by_name[normalized]
        except KeyError as error:
            raise KeyError(
                "Engine is not present in the runtime report: "
                f"{normalized}"
            ) from error

    def visualize(self) -> str:
        """Return a deterministic readable summary."""

        if not self.results:
            return "<empty runtime report>"

        lines: list[str] = []

        for result in self.results:
            line = (
                f"{result.engine_name}: "
                f"{result.status.value}"
            )

            if (
                result.failed
                and result.error_message
            ):
                line += (
                    f" ({result.error_message})"
                )

            elif (
                result.skipped
                and result.skipped_reason
            ):
                line += (
                    f" ({result.skipped_reason})"
                )

            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def _normalize_name(value: str) -> str:
        if not isinstance(value, str):
            raise TypeError(
                "Engine names must be strings."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Engine names cannot be empty."
            )

        return normalized


class Runner:
    """Execute a dependency-safe plan sequentially."""

    def run(
        self,
        plan: ExecutionPlan,
        registry: EngineRegistry,
        context: PlatformContext,
        *,
        error_policy: ErrorPolicy = ErrorPolicy.STRICT,
    ) -> RuntimeReport:
        """Execute the plan and return an immutable report."""

        if not isinstance(plan, ExecutionPlan):
            raise TypeError(
                "plan must be an ExecutionPlan."
            )

        if not isinstance(
            registry,
            EngineRegistry,
        ):
            raise TypeError(
                "registry must be an EngineRegistry."
            )

        if not isinstance(
            context,
            PlatformContext,
        ):
            raise TypeError(
                "context must be a PlatformContext."
            )

        try:
            policy = ErrorPolicy(error_policy)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Unsupported error policy: "
                f"{error_policy}"
            ) from error

        self._validate_plan_registry(
            plan,
            registry,
        )

        report_started_at = self._utc_now()
        report_timer = perf_counter()

        results: list[
            EngineExecutionResult
        ] = []

        results_by_name: dict[
            str,
            EngineExecutionResult,
        ] = {}

        strict_failure: (
            EngineExecutionResult | None
        ) = None

        for step in plan.steps:
            if strict_failure is not None:
                result = self._skipped_result(
                    step,
                    reason=(
                        "Execution halted after "
                        "strict-policy failure: "
                        f"{strict_failure.engine_name}"
                    ),
                )

            elif (
                policy
                is ErrorPolicy.SKIP_DEPENDENTS
            ):
                blocked_dependencies = tuple(
                    dependency
                    for dependency
                    in step.dependencies
                    if not results_by_name[
                        dependency
                    ].succeeded
                )

                if blocked_dependencies:
                    result = self._skipped_result(
                        step,
                        reason=(
                            "Blocked by unsuccessful "
                            "dependencies: "
                            + ", ".join(
                                blocked_dependencies
                            )
                        ),
                    )
                else:
                    result = self._execute_step(
                        step,
                        registry,
                        context,
                    )

            else:
                result = self._execute_step(
                    step,
                    registry,
                    context,
                )

            results.append(result)

            results_by_name[
                result.engine_name
            ] = result

            if (
                policy is ErrorPolicy.STRICT
                and result.failed
            ):
                strict_failure = result

        return RuntimeReport.build(
            started_at=report_started_at,
            finished_at=self._utc_now(),
            duration_seconds=(
                perf_counter() - report_timer
            ),
            results=tuple(results),
            error_policy=policy,
        )

    def _execute_step(
        self,
        step: ExecutionStep,
        registry: EngineRegistry,
        context: PlatformContext,
    ) -> EngineExecutionResult:
        registration = registry.require(
            step.engine_name
        )

        started_at = self._utc_now()
        timer = perf_counter()

        try:
            output = registration.engine.execute(
                context
            )

        except Exception as error:
            return EngineExecutionResult(
                engine_name=step.engine_name,
                status=EngineStatus.FAILED,
                started_at=started_at,
                finished_at=self._utc_now(),
                duration_seconds=(
                    perf_counter() - timer
                ),
                error_type=type(error).__name__,
                error_message=str(error),
            )

        return EngineExecutionResult(
            engine_name=step.engine_name,
            status=EngineStatus.SUCCESS,
            started_at=started_at,
            finished_at=self._utc_now(),
            duration_seconds=(
                perf_counter() - timer
            ),
            output=output,
        )

    @staticmethod
    def _skipped_result(
        step: ExecutionStep,
        *,
        reason: str,
    ) -> EngineExecutionResult:
        return EngineExecutionResult(
            engine_name=step.engine_name,
            status=EngineStatus.SKIPPED,
            started_at=None,
            finished_at=None,
            duration_seconds=0.0,
            skipped_reason=reason,
        )

    @staticmethod
    def _validate_plan_registry(
        plan: ExecutionPlan,
        registry: EngineRegistry,
    ) -> None:
        enabled_names = set(
            registry.names(
                include_disabled=False
            )
        )

        missing = tuple(
            sorted(
                set(plan.engine_names)
                - enabled_names
            )
        )

        if missing:
            raise KeyError(
                "Execution plan contains engines "
                "unavailable in the enabled registry: "
                + ", ".join(missing)
            )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)