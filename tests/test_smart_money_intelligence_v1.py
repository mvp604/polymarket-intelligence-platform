from __future__ import annotations

import sqlite3

from src.smart_money_intelligence_v1 import (
    category_from_title,
    compute_signal,
    score_to_grade,
)


def test_category_detection() -> None:
    assert category_from_title("Will Spain win the FIFA World Cup?") == "Soccer"
    assert category_from_title("Will Bitcoin exceed $100k?") == "Crypto"
    assert category_from_title("Unknown market") == "Other"


def test_grade_boundaries() -> None:
    assert score_to_grade(90) == "S+"
    assert score_to_grade(76) == "S"
    assert score_to_grade(66) == "A"
    assert score_to_grade(20) == "PASS"


def test_signal_requires_minimum_wallets() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE sample (
            wallet TEXT, market_id TEXT, title TEXT, outcome TEXT,
            current_value REAL, average_price REAL, current_price REAL
        )
        """
    )
    connection.execute(
        "INSERT INTO sample VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("0x1", "m1", "Will Spain win the World Cup?", "Yes", 1000, .4, .5),
    )
    row = connection.execute("SELECT * FROM sample").fetchone()
    profiles = {
        "0x1": {
            "confidence_adjusted_score": 80.0,
            "influence_weight": 0.8,
            "consensus_eligible": 1,
            "elite_eligible": 1,
            "elite_tier": "Elite",
            "overall_grade": "S",
        }
    }
    config = {
        "minimum_wallets": 2,
        "strong_consensus_score": 70.0,
        "strong_consensus_agreement": 0.5,
        "high_disagreement_threshold": 0.45,
        "watch_score": 50.0,
        "capital_log_divisor": 7.0,
        "wallet_count_full_score": 8,
        "_groups": {("m1", "Yes"): [row]},
    }
    assert compute_signal(
        ("m1", "Yes"), [row], profiles, {"m1": {"Yes"}}, config
    ) is None
