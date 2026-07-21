from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedTitle:
    original: str
    normalized: str
    tokens: tuple[str, ...]


def normalize_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("â€“", "-").replace("â€”", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(value: str) -> tuple[str, ...]:
    normalized = normalize_title(value).lower()
    return tuple(re.findall(r"[a-z0-9$%+.:-]+", normalized))


def parse_title(value: str) -> ParsedTitle:
    normalized = normalize_title(value)
    return ParsedTitle(
        original=value or "",
        normalized=normalized,
        tokens=tokenize(normalized),
    )

