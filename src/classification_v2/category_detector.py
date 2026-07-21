from __future__ import annotations

import re
from .models import Detection
from .parser import ParsedTitle


RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Politics", (
        r"\belection\b", r"\bpresident\b", r"\bnomination\b", r"\bgop\b",
        r"\brepublican\b", r"\bdemocrat\b", r"\bsenate\b", r"\bcongress\b",
        r"\bgovernor\b", r"\bprime minister\b", r"\bparliament\b",
    )),
    ("Crypto", (
        r"\bbitcoin\b", r"\bbtc\b", r"\bethereum\b", r"\beth\b",
        r"\bsolana\b", r"\bcrypto\b", r"\btoken\b", r"\bdefi\b",
        r"\bstablecoin\b", r"\bblockchain\b",
    )),
    ("Economics", (
        r"\bfederal reserve\b", r"\bfed\b", r"\binterest rates?\b",
        r"\binflation\b", r"\bcpi\b", r"\bgdp\b", r"\bunemployment\b",
        r"\brecession\b", r"\bjobs report\b",
    )),
    ("Finance", (
        r"\bs&p 500\b", r"\bspy\b", r"\bnasdaq\b", r"\bdow jones\b",
        r"\bstock price\b", r"\bmarket cap\b", r"\bipo\b", r"\bearnings\b",
    )),
    ("Technology", (
        r"\bopenai\b", r"\bartificial intelligence\b", r"\bai model\b",
        r"\bmicrosoft\b", r"\bgoogle\b", r"\bapple\b", r"\bmeta\b",
        r"\bspacex\b", r"\bsemiconductor\b",
    )),
    ("Entertainment", (
        r"\boscar\b", r"\bemmy\b", r"\bgrammy\b", r"\bbox office\b",
        r"\bmovie\b", r"\btelevision\b", r"\bcelebrity\b", r"\balbum\b",
    )),
    ("World Events", (
        r"\bceasefire\b", r"\binvasion\b", r"\bsanctions?\b", r"\bnato\b",
        r"\bunited nations\b", r"\btreaty\b", r"\bwar\b",
    )),
    ("Science", (
        r"\bnasa\b", r"\bspace mission\b", r"\bvaccine\b",
        r"\bpandemic\b", r"\bclinical trial\b",
    )),
)


def detect_category(parsed: ParsedTitle) -> Detection:
    text = parsed.normalized.lower()
    evidence: list[str] = []

    for label, patterns in RULES:
        evidence.clear()
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                evidence.append(f"matched:{pattern}")
        if evidence:
            confidence = min(0.70 + 0.08 * (len(evidence) - 1), 0.98)
            result = Detection(label, confidence, tuple(evidence), "category_rules_v2")
            result.validate()
            return result

    result = Detection("Other", 0.25, ("no-category-rule-match",), "category_fallback_v2")
    result.validate()
    return result

