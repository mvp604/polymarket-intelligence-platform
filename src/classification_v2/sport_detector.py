from __future__ import annotations

import re
from .models import Detection
from .parser import ParsedTitle


RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Soccer", (
        r"\bfifa\b", r"\bworld cup\b", r"\buefa\b", r"\bchampions league\b",
        r"\bpremier league\b", r"\bla liga\b", r"\bserie a\b",
        r"\bbundesliga\b", r"\bligue 1\b", r"\bmls\b", r"\bsoccer\b",
        r"\bbtts\b", r"\bclean sheet\b", r"\bexact score\b",
        r"\b(?:vs\.?|v\.?)\b.*\bgoals?\b",
        r"\bgoals?\b.*\b(?:vs\.?|v\.?)\b",
        r"\b(?:vs\.?|v\.?)\b.*\bcorners?\b",
        r"\b(?:vs\.?|v\.?)\b.*\bto qualify\b",
    )),
    ("Basketball", (
        r"\bnba\b", r"\bwnba\b", r"\beuroleague\b", r"\bbasketball\b",
        r"\bncaab\b", r"\bmarch madness\b",
    )),
    ("Baseball", (
        r"\bmlb\b", r"\bbaseball\b", r"\bworld series\b",
    )),
    ("American Football", (
        r"\bnfl\b", r"\bsuper bowl\b", r"\bcollege football\b", r"\bncaaf\b",
    )),
    ("MMA", (
        r"\bufc\b", r"\bmma\b", r"\bbellator\b", r"\bpfl\b", r"\bfight night\b",
    )),
    ("Tennis", (
        r"\btennis\b", r"\bwimbledon\b", r"\bus open\b",
        r"\baustralian open\b", r"\bfrench open\b", r"\batp\b", r"\bwta\b",
    )),
    ("Ice Hockey", (
        r"\bnhl\b", r"\bstanley cup\b", r"\bice hockey\b",
    )),
    ("Golf", (
        r"\bpga\b", r"\bliv golf\b", r"\bmasters tournament\b",
        r"\bthe open\b", r"\bgolf\b",
    )),
    ("Motorsport", (
        r"\bformula 1\b", r"\bf1\b", r"\bnascar\b",
        r"\bindycar\b", r"\bgrand prix\b",
    )),
    ("Cricket", (
        r"\bipl\b", r"\bcricket\b", r"\bt20\b", r"\btest match\b",
    )),
    ("Boxing", (
        r"\bboxing\b", r"\bheavyweight\b", r"\bknockout\b",
    )),
    ("Esports", (
        r"\besports\b", r"\bleague of legends\b", r"\bvalorant\b",
        r"\bdota\b", r"\bcounter-strike\b", r"\bcs2\b",
    )),
)


def detect_sport(parsed: ParsedTitle) -> Detection:
    text = parsed.normalized.lower()

    best_label: str | None = None
    best_evidence: list[str] = []

    for label, patterns in RULES:
        evidence = [
            f"matched:{pattern}"
            for pattern in patterns
            if re.search(pattern, text, flags=re.IGNORECASE)
        ]
        if len(evidence) > len(best_evidence):
            best_label = label
            best_evidence = evidence

    if best_label:
        confidence = min(0.72 + 0.07 * (len(best_evidence) - 1), 0.99)
        result = Detection(
            best_label,
            confidence,
            tuple(best_evidence),
            "sport_rules_v2",
        )
        result.validate()
        return result

    result = Detection(None, 0.15, ("no-sport-rule-match",), "sport_fallback_v2")
    result.validate()
    return result

