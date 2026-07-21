from __future__ import annotations

import re
from dataclasses import dataclass

from .registry.loader import get_rules
from .registry.models import RegistryRule


@dataclass(frozen=True)
class MatchResult:
    rule_id: str | None
    rule_type: str
    value: str | None
    confidence: float
    evidence: tuple[str, ...]
    category: str | None = None
    sport: str | None = None


class RegistryMatcher:
    @staticmethod
    def normalize(text: str) -> str:
        return " ".join(
            text.strip().lower().split()
        )

    @staticmethod
    def find_alias_matches(
        text: str,
        rule: RegistryRule,
    ) -> tuple[str, ...]:
        return tuple(
            alias
            for alias in rule.aliases
            if re.search(
                alias,
                text,
                flags=re.IGNORECASE,
            )
        )

    def match(
        self,
        text: str,
        rule_type: str,
    ) -> MatchResult:
        normalized = self.normalize(text)

        best_rule: RegistryRule | None = None
        best_matches: tuple[str, ...] = ()

        for rule in get_rules(rule_type):
            matches = self.find_alias_matches(
                normalized,
                rule,
            )

            if not matches:
                continue

            if best_rule is None:
                best_rule = rule
                best_matches = matches
                continue

            current_score = (
                len(matches),
                rule.confidence,
                max(len(alias) for alias in matches),
            )

            best_score = (
                len(best_matches),
                best_rule.confidence,
                max(len(alias) for alias in best_matches),
            )

            if current_score > best_score:
                best_rule = rule
                best_matches = matches

        if best_rule is None:
            return MatchResult(
                rule_id=None,
                rule_type=rule_type,
                value=None,
                confidence=0.10,
                evidence=(
                    "no-registry-match",
                ),
            )

        confidence = min(
            best_rule.confidence
            + 0.015 * (len(best_matches) - 1),
            0.99,
        )

        return MatchResult(
            rule_id=best_rule.rule_id,
            rule_type=best_rule.rule_type,
            value=best_rule.value,
            confidence=confidence,
            evidence=tuple(
                f"matched:{alias}"
                for alias in best_matches
            ),
            category=best_rule.category,
            sport=best_rule.sport,
        )
