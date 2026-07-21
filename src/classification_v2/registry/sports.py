from __future__ import annotations

from .models import RegistryRule


RULES: tuple[RegistryRule, ...] = (
    RegistryRule(
        rule_id="sport.soccer",
        rule_type="sport",
        value="Soccer",
        aliases=(
            r"\bsoccer\b",
            r"\bassociation football\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.basketball",
        rule_type="sport",
        value="Basketball",
        aliases=(
            r"\bbasketball\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.baseball",
        rule_type="sport",
        value="Baseball",
        aliases=(
            r"\bbaseball\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.american_football",
        rule_type="sport",
        value="American Football",
        aliases=(
            r"\bamerican football\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.ice_hockey",
        rule_type="sport",
        value="Ice Hockey",
        aliases=(
            r"\bice hockey\b",
            r"\bhockey\b",
        ),
        confidence=0.91,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.mma",
        rule_type="sport",
        value="MMA",
        aliases=(
            r"\bmma\b",
            r"\bmixed martial arts\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.tennis",
        rule_type="sport",
        value="Tennis",
        aliases=(
            r"\btennis\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.cricket",
        rule_type="sport",
        value="Cricket",
        aliases=(
            r"\bcricket\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.golf",
        rule_type="sport",
        value="Golf",
        aliases=(
            r"\bgolf\b",
        ),
        confidence=0.94,
        category="Sports",
    ),
    RegistryRule(
        rule_id="sport.motorsport",
        rule_type="sport",
        value="Motorsport",
        aliases=(
            r"\bmotorsport\b",
            r"\bmotor racing\b",
        ),
        confidence=0.92,
        category="Sports",
    ),
)
