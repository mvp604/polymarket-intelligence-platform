from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    """
    Typed operation result.

    A result contains either a value or an error message.
    """

    value: T | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        has_value = self.value is not None
        has_error = self.error is not None

        if has_value == has_error:
            raise ValueError(
                "Result must contain exactly one of value or error."
            )

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def is_failure(self) -> bool:
        return self.error is not None

    def unwrap(self) -> T:
        if self.error is not None:
            raise RuntimeError(self.error)

        if self.value is None:
            raise RuntimeError("Successful result contains no value.")

        return self.value

    @classmethod
    def success(cls, value: T) -> Result[T]:
        return cls(value=value)

    @classmethod
    def failure(cls, error: str) -> Result[T]:
        normalized_error = str(error or "").strip()

        if not normalized_error:
            raise ValueError("Failure result requires an error message.")

        return cls(error=normalized_error)