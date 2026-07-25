from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.elite_wallet_intelligence_v2 import (
    category_from_title,
    compute_metrics,
    derive_tier,
)


def config() -> dict:
    return {
        "bayesian_prior_wins": 5.0,
        "bayesian_prior_losses": 5.0,
        "sample_size_full_confidence": 100,
        "minimum_consensus_positions": 10,
        "minimum_elite_positions": 25,
        "minimum_consensus_score": 45.0,
        "minimum_elite_score": 65.0,
        "roi_outlier_absolute_percent": 300.0,
        "roi_score_divisor": 2.0,
        "consistency_range_divisor": 8.0,
        "tiers": [
            {"name": "Institutional", "grade": "S+", "minimum_score": 85.0, "minimum_sample_strength": 80.0},
            {"name": "Elite", "grade": "S", "minimum_score": 75.0, "minimum_sample_strength": 60.0},
            {"name": "Professional", "grade": "A", "minimum_score": 65.0, "minimum_sample_strength": 40.0},
            {"name": "Advanced", "grade": "B", "minimum_score": 55.0, "minimum_sample_strength": 25.0},
            {"name": "Developing", "grade": "WATCH", "minimum_score": 40.0, "minimum_sample_strength": 10.0},
        ],
    }


def make_rows(count: int = 30):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE positions (
            wallet TEXT, market_id TEXT, title TEXT, outcome TEXT,
            current_value REAL, cash_pnl REAL, percent_pnl REAL
        )
        """
    )
    for index in range(count):
        won = index % 3 != 0
        connection.execute(
            "INSERT INTO positions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "0xabc", str(index), "Will Spain win the FIFA World Cup?",
                "Yes", 1000.0, 75.0 if won else -50.0,
                7.5 if won else -5.0,
            ),
        )
    return connection.execute("SELECT * FROM positions").fetchall()


def test_category_detection() -> None:
    assert category_from_title("Will Spain win the FIFA World Cup?") == "Soccer"
    assert category_from_title("Will Bitcoin exceed $100k?") == "Crypto"
    assert category_from_title("Unknown market") == "Other"


def test_metrics_are_bounded_and_explainable() -> None:
    metrics = compute_metrics("0xabc", make_rows(), config())
    assert 0 <= metrics.confidence_adjusted_score <= 100
    assert metrics.resolved_positions == 30
    assert json.loads(metrics.explanation_json)["summary"]


def test_tier_requires_score_and_sample() -> None:
    tier, grade = derive_tier(90.0, 20.0, config())
    assert tier != "Institutional"
    assert grade != "S+"
