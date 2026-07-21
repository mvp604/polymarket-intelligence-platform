from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    label: str | None
    confidence: float
    evidence: tuple[str, ...]
    method: str

    def validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Invalid confidence: {self.confidence}")
        if self.label is None and self.confidence > 0.5:
            raise ValueError("Unknown labels cannot have high confidence.")

