from __future__ import annotations

"""
Repository-native resolution sync adapter.

This module intentionally provides a clean adapter boundary rather than
hard-coding an external API contract. Connect the repository's official
Polymarket client here and return ResolutionRecord instances.
"""

from collections.abc import Iterable
from src.outcome_resolution_reporting_v2 import ResolutionRecord


def fetch_official_resolutions() -> Iterable[ResolutionRecord]:
    # Replace this adapter body with the repository's tested official
    # Polymarket Gamma/Data API client. Do not scrape webpages.
    return []
