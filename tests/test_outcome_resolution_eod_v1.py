from __future__ import annotations

from src.outcome_resolution_eod_reporting_v1 import (
    build_markdown_report,
    grade_signal_outcome,
    normalize_result,
)


def test_result_normalization() -> None:
    assert normalize_result("yes") == "WIN"
    assert normalize_result("lost") == "LOSS"
    assert normalize_result("push") == "VOID"


def test_signal_grading() -> None:
    assert grade_signal_outcome(
        "STRONG_ELITE_CONSENSUS", "S+", "WIN"
    ) == ("HIT", 1.0)
    assert grade_signal_outcome(
        "STRONG_ELITE_CONSENSUS", "S+", "LOSS"
    ) == ("MISS", 0.0)
    assert grade_signal_outcome(
        "LOW_SIGNAL", "PASS", "WIN"
    ) == ("NO_ACTION", 0.0)


def test_markdown_report_contains_summary() -> None:
    data = {
        "report_date": "2026-07-25",
        "summary": {
            "total_resolved": 10,
            "hits": 7,
            "misses": 3,
            "voids": 0,
            "no_action": 0,
            "hit_rate": 0.7,
            "average_heat_score": 72.5,
            "maximum_heat_score": 91.1,
            "combined_capital": 1000000,
        },
        "grades": [],
        "categories": [],
        "strongest_signals": [],
        "highest_conviction_misses": [],
    }
    report = build_markdown_report(data)
    assert "70.00%" in report
    assert "Polymarket Intelligence Daily Report" in report
