from __future__ import annotations

import sqlite3

from src.outcome_resolution_reporting_v2 import (
    grade_signal_outcome,
    normalize_result,
    period_bounds,
)
from src.outcome_resolution_schema_v2 import (
    ensure_schema,
    table_columns,
)


def test_normalization_and_grading() -> None:
    assert normalize_result("yes") == "WIN"
    assert normalize_result("lost") == "LOSS"
    assert normalize_result("push") == "VOID"
    assert grade_signal_outcome(
        "STRONG_ELITE_CONSENSUS", "S+", "WIN"
    ) == ("HIT", 1.0)
    assert grade_signal_outcome(
        "LOW_SIGNAL", "PASS", "WIN"
    ) == ("NO_ACTION", None)


def test_repairs_partial_v1_table() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE market_resolutions (
            market_id TEXT,
            outcome TEXT,
            final_result TEXT
        )
        """
    )
    repairs = ensure_schema(connection)
    assert "market_resolutions.resolved_at" in repairs
    assert "resolved_at" in table_columns(
        connection, "market_resolutions"
    )
    assert "resolved_signal_results" in {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def test_weekly_period_bounds() -> None:
    from datetime import date
    start, end, key = period_bounds("WEEKLY", date(2026, 7, 25))
    assert start.date().isoformat() == "2026-07-20"
    assert end.date().isoformat() == "2026-07-27"
    assert key == "2026-07-20_to_2026-07-26"
