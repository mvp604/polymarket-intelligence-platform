from __future__ import annotations

from dataclasses import dataclass

from .category_detector import detect_category
from .models import Detection
from .parser import parse_title
from .sport_detector import detect_sport


@dataclass(frozen=True)
class Phase1Classification:
    title: str
    normalized_title: str
    category: Detection
    sport: Detection


def classify_phase1(title: str) -> Phase1Classification:
    parsed = parse_title(title)
    sport = detect_sport(parsed)
    category = detect_category(parsed)

    if sport.label is not None:
        category = Detection(
            label="Sports",
            confidence=max(0.90, sport.confidence),
            evidence=("sport-detected", *sport.evidence),
            method="sport_override_v2",
        )

    category.validate()
    sport.validate()

    return Phase1Classification(
        title=title,
        normalized_title=parsed.normalized,
        category=category,
        sport=sport,
    )

