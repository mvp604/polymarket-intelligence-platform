from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest
import src.elite_wallet_intelligence_engine as engine


def make_row(connection, title, pnl, value, won=1):
    connection.row_factory = sqlite3.Row
    return connection.execute(
        """SELECT '0xwallet' wallet, 'market-1' market_id, ? title, 'YES' outcome,
        100.0 shares, 0.5 average_price, 1.0 current_price, ? current_value,
        ? cash_pnl, 0.0 percent_pnl, '2026-07-25T00:00:00+00:00' observed_at,
        1 resolved_flag, ? won_flag""",
        (title, value, pnl, won),
    ).fetchone()


def test_profitable_specialist_scores_above_weak_wallet():
    with sqlite3.connect(":memory:") as connection:
        strong_rows = [make_row(connection, "World Cup soccer match", 5000, 10000, 1) for _ in range(25)]
        weak_rows = [make_row(connection, "Random market", -100, 1000, 0) for _ in range(5)]
        strong, _ = engine.profile_wallet("0xstrong", strong_rows)
        weak, _ = engine.profile_wallet("0xweak", weak_rows)
    assert strong["wallet_score"] > weak["wallet_score"]
    assert strong["primary_category"] == "SOCCER"
    assert strong["elite_status"] in {"ELITE", "QUALIFIED"}


def test_category_profiles_are_created():
    with sqlite3.connect(":memory:") as connection:
        rows = [
            make_row(connection, "World Cup soccer match", 100, 1000),
            make_row(connection, "Bitcoin above 100k", 200, 1000),
        ]
        _, categories = engine.profile_wallet("0xwallet", rows)
    assert {"SOCCER", "CRYPTO"} <= {item["category"] for item in categories}


def test_migration_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    migration = tmp_path / "006.sql"
    migration.write_text(engine.MIGRATION_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(engine, "MIGRATION_PATH", migration)
    with sqlite3.connect(":memory:") as connection:
        engine.ensure_schema(connection)
        engine.ensure_schema(connection)
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert "elite_wallet_profiles" in tables
    assert "elite_wallet_category_profiles" in tables
