from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import src.institutional_review_engine as engine


def test_assess_high_quality_actionable_opportunity() -> None:
    result = engine.assess(
        {
            "opportunity_score": 94,
            "opportunity_grade": "S+",
            "recommendation": "ACTIONABLE",
            "wallet_quality_score": 90,
            "timing_score": 92,
            "timing_status": "TIGHT",
            "market_structure_score": 84,
            "historical_reliability_score": 80,
            "wallet_count": 7,
            "elite_wallet_count": 3,
            "combined_capital": 500_000,
            "current_price": 0.61,
        }
    )

    assert result.confidence_score >= 88
    assert result.grade in {"S+", "S"}
    assert result.decision == "APPROVE"
    assert result.risk_level == "LOW"


def test_assess_rejects_weak_single_wallet_signal() -> None:
    result = engine.assess(
        {
            "opportunity_score": 72,
            "recommendation": "WATCHLIST",
            "wallet_quality_score": 40,
            "timing_status": "UNKNOWN",
            "market_structure_score": 30,
            "historical_reliability_score": 25,
            "wallet_count": 1,
            "elite_wallet_count": 0,
            "combined_capital": 500,
            "current_price": 0.99,
        }
    )

    assert result.risk_level == "HIGH"
    assert result.decision == "REJECT"
    assert "INSUFFICIENT_WALLET_CONFIRMATION" in result.risk_flags


def test_migration_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    migration = tmp_path / "004_institutional_reviews.sql"
    migration.write_text(engine.MIGRATION_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(engine, "MIGRATION_PATH", migration)

    with sqlite3.connect(":memory:") as connection:
        engine.ensure_schema(connection)
        engine.ensure_schema(connection)

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        views = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='view'"
            )
        }

    assert "institutional_reviews" in tables
    assert "institutional_review_runs" in tables
    assert "current_institutional_reviews" in views
    assert "ranked_institutional_reviews" in views
