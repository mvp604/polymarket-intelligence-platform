from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import src.opportunity_enrichment_engine as engine


def make_row(connection: sqlite3.Connection) -> sqlite3.Row:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        """
        SELECT
            'opp-1' AS opportunity_id,
            'market-1' AS market_id,
            'YES' AS outcome,
            'Test market' AS title,
            'Sports' AS category,
            88.0 AS opportunity_score,
            'S' AS opportunity_grade,
            'WATCHLIST' AS recommendation,
            82.0 AS wallet_quality_score,
            70.0 AS timing_score,
            'COORDINATED' AS timing_status,
            4 AS wallet_count,
            2 AS elite_wallet_count,
            125000.0 AS combined_capital,
            0.62 AS current_price,
            250000.0 AS liquidity,
            0.02 AS spread,
            76.0 AS market_structure_score,
            68.0 AS historical_reliability_score,
            'state-1' AS state_checksum,
            'cluster-1' AS source_cluster_id,
            NULL AS cluster_wallet_count,
            NULL AS cluster_elite_wallet_count,
            NULL AS cluster_combined_capital,
            NULL AS cluster_timing_score,
            NULL AS cluster_timing_status,
            NULL AS cluster_current_price,
            NULL AS cluster_liquidity,
            NULL AS cluster_spread,
            NULL AS cluster_wallet_quality
        """
    ).fetchone()


def test_enrich_preserves_real_capital_and_market_data() -> None:
    with sqlite3.connect(":memory:") as connection:
        row = make_row(connection)
        result = engine.enrich(connection, row)

    assert result["combined_capital"] == 125000.0
    assert result["wallet_count"] == 4
    assert result["elite_wallet_count"] == 2
    assert result["liquidity"] == 250000.0
    assert result["data_completeness_score"] >= 75


def test_market_structure_penalizes_extreme_price() -> None:
    normal = engine.market_structure(0.55, 500000, 0.01, 50)
    extreme = engine.market_structure(0.99, 500000, 0.01, 50)
    assert normal > extreme


def test_migration_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = tmp_path / "005.sql"
    migration.write_text(
        engine.MIGRATION_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
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

    assert "opportunity_enrichment_current" in tables
    assert "opportunity_enrichment_history" in tables
