from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegistryRule:
    rule_id: str
    rule_type: str
    value: str
    aliases: tuple[str, ...]
    confidence: float
    category: str | None = None
    sport: str | None = None
    metadata: dict[str, str] = field(
        default_factory=dict
    )

    def validate(self) -> None:
        if not self.rule_id.strip():
            raise ValueError(
                "rule_id cannot be empty"
            )

        if not self.rule_type.strip():
            raise ValueError(
                f"{self.rule_id}: rule_type cannot be empty"
            )

        if not self.value.strip():
            raise ValueError(
                f"{self.rule_id}: value cannot be empty"
            )

        if not self.aliases:
            raise ValueError(
                f"{self.rule_id}: aliases cannot be empty"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"{self.rule_id}: invalid confidence "
                f"{self.confidence}"
            )
