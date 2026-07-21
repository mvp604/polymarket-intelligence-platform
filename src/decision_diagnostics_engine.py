from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENGINE_VERSION = "1.0"

DEFAULT_DATABASE = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "polymarket.db"
)

BUY_THRESHOLDS = {
    "decision_score": 82.0,
    "actionability_score": 76.0,
    "confidence": 62.0,
    "entry_quality_score": 68.0,
    "market_structure_score": 55.0,
    "trust_quality_score": 48.0,
    "wallet_count": 2.0,
    "data_quality_score": 55.0,
}

WATCH_THRESHOLDS = {
    "decision_score": 70.0,
    "actionability_score": 58.0,
    "confidence": 50.0,
}


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_json_list(value: Any) -> list[str]:
    if value in (None, "", "null"):
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    if isinstance(value, dict):
        return [
            f"{key}: {item}"
            for key, item in value.items()
        ]

    try:
        parsed = json.loads(str(value))
    except (json.JSONDecodeError, TypeError):
        text = str(value).strip()
        return [text] if text else []

    return parse_json_list(parsed)


def connect_database(
    database_path: Path,
) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def create_schema(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS
        institutional_decision_diagnostics (
            opportunity_key TEXT PRIMARY KEY,
            market_id TEXT,
            title TEXT NOT NULL,
            outcome TEXT,

            current_action TEXT NOT NULL,
            decision_grade TEXT,

            decision_score REAL NOT NULL DEFAULT 0,
            actionability_score REAL NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0,

            entry_quality_score REAL NOT NULL DEFAULT 0,
            market_structure_score REAL NOT NULL DEFAULT 0,
            trust_quality_score REAL NOT NULL DEFAULT 0,
            data_quality_score REAL NOT NULL DEFAULT 0,

            wallet_count INTEGER NOT NULL DEFAULT 0,
            elite_wallet_count INTEGER NOT NULL DEFAULT 0,
            supporting_wallet_count INTEGER NOT NULL DEFAULT 0,
            trusted_wallet_count INTEGER NOT NULL DEFAULT 0,

            hard_veto INTEGER NOT NULL DEFAULT 0,

            buy_requirements_passed INTEGER NOT NULL DEFAULT 0,
            buy_requirements_failed INTEGER NOT NULL DEFAULT 0,

            watch_requirements_passed INTEGER NOT NULL DEFAULT 0,
            watch_requirements_failed INTEGER NOT NULL DEFAULT 0,

            buy_gap_score REAL NOT NULL DEFAULT 0,
            watch_gap_score REAL NOT NULL DEFAULT 0,

            nearest_upgrade TEXT NOT NULL,
            upgrade_difficulty TEXT NOT NULL,

            primary_blocker TEXT NOT NULL,
            secondary_blocker TEXT,
            blocker_category TEXT NOT NULL,

            failed_buy_requirements_json TEXT NOT NULL,
            failed_watch_requirements_json TEXT NOT NULL,

            veto_reasons_json TEXT NOT NULL,
            positive_reasons_json TEXT NOT NULL,
            risk_flags_json TEXT NOT NULL,
            upgrade_actions_json TEXT NOT NULL,

            diagnostic_summary TEXT NOT NULL,

            source_calculated_at TEXT,
            diagnosed_at TEXT NOT NULL,
            run_id TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS
        institutional_decision_diagnostic_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            opportunity_key TEXT NOT NULL,
            market_id TEXT,
            title TEXT NOT NULL,
            outcome TEXT,

            current_action TEXT NOT NULL,
            decision_grade TEXT,

            decision_score REAL NOT NULL DEFAULT 0,
            actionability_score REAL NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0,

            entry_quality_score REAL NOT NULL DEFAULT 0,
            market_structure_score REAL NOT NULL DEFAULT 0,
            trust_quality_score REAL NOT NULL DEFAULT 0,
            data_quality_score REAL NOT NULL DEFAULT 0,

            wallet_count INTEGER NOT NULL DEFAULT 0,
            elite_wallet_count INTEGER NOT NULL DEFAULT 0,
            supporting_wallet_count INTEGER NOT NULL DEFAULT 0,
            trusted_wallet_count INTEGER NOT NULL DEFAULT 0,

            hard_veto INTEGER NOT NULL DEFAULT 0,

            buy_requirements_passed INTEGER NOT NULL DEFAULT 0,
            buy_requirements_failed INTEGER NOT NULL DEFAULT 0,

            watch_requirements_passed INTEGER NOT NULL DEFAULT 0,
            watch_requirements_failed INTEGER NOT NULL DEFAULT 0,

            buy_gap_score REAL NOT NULL DEFAULT 0,
            watch_gap_score REAL NOT NULL DEFAULT 0,

            nearest_upgrade TEXT NOT NULL,
            upgrade_difficulty TEXT NOT NULL,

            primary_blocker TEXT NOT NULL,
            secondary_blocker TEXT,
            blocker_category TEXT NOT NULL,

            failed_buy_requirements_json TEXT NOT NULL,
            failed_watch_requirements_json TEXT NOT NULL,

            veto_reasons_json TEXT NOT NULL,
            positive_reasons_json TEXT NOT NULL,
            risk_flags_json TEXT NOT NULL,
            upgrade_actions_json TEXT NOT NULL,

            diagnostic_summary TEXT NOT NULL,

            source_calculated_at TEXT,
            diagnosed_at TEXT NOT NULL,
            run_id TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
        idx_decision_diagnostics_upgrade
        ON institutional_decision_diagnostics(
            nearest_upgrade
        );

        CREATE INDEX IF NOT EXISTS
        idx_decision_diagnostic_history_key
        ON institutional_decision_diagnostic_history(
            opportunity_key
        );

        CREATE INDEX IF NOT EXISTS
        idx_decision_diagnostic_history_run
        ON institutional_decision_diagnostic_history(
            run_id
        );

        CREATE TABLE IF NOT EXISTS
        institutional_decision_diagnostic_runs (
            run_id TEXT PRIMARY KEY,
            methodology_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            source_decisions INTEGER NOT NULL DEFAULT 0,
            diagnostics_analyzed INTEGER NOT NULL DEFAULT 0,
            diagnostics_saved INTEGER NOT NULL DEFAULT 0,
            history_saved INTEGER NOT NULL DEFAULT 0,

            buy_ready_count INTEGER NOT NULL DEFAULT 0,
            near_buy_count INTEGER NOT NULL DEFAULT 0,
            watch_ready_count INTEGER NOT NULL DEFAULT 0,
            near_watch_count INTEGER NOT NULL DEFAULT 0,
            distant_count INTEGER NOT NULL DEFAULT 0,
            veto_blocked_count INTEGER NOT NULL DEFAULT 0,

            duration_seconds REAL,
            status TEXT NOT NULL,
            error_message TEXT
        );
        """
    )


def evaluate_requirements(
    values: dict[str, float],
    thresholds: dict[str, float],
) -> tuple[list[str], list[dict[str, Any]], float]:
    passed: list[str] = []
    failed: list[dict[str, Any]] = []
    normalized_gaps: list[float] = []

    for metric, required in thresholds.items():
        current = safe_float(values.get(metric))

        if current >= required:
            passed.append(metric)
            continue

        gap = required - current
        normalized_gap = gap / max(required, 1.0)

        normalized_gaps.append(normalized_gap)

        failed.append(
            {
                "metric": metric,
                "current": round(current, 4),
                "required": round(required, 4),
                "gap": round(gap, 4),
                "normalized_gap": round(
                    normalized_gap,
                    6,
                ),
            }
        )

    aggregate_gap = (
        100.0
        * sum(normalized_gaps)
        / max(len(thresholds), 1)
    )

    return (
        passed,
        failed,
        round(aggregate_gap, 4),
    )


def rank_failures(
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        failures,
        key=lambda item: (
            safe_float(item.get("normalized_gap")),
            safe_float(item.get("gap")),
        ),
        reverse=True,
    )


def blocker_label(metric: str) -> str:
    labels = {
        "decision_score": "DECISION_SCORE",
        "actionability_score": "ACTIONABILITY",
        "confidence": "CONFIDENCE",
        "entry_quality_score": "ENTRY_QUALITY",
        "market_structure_score": "MARKET_STRUCTURE",
        "trust_quality_score": "WALLET_TRUST",
        "wallet_count": "WALLET_BREADTH",
        "data_quality_score": "DATA_QUALITY",
        "hard_veto": "HARD_VETO",
    }

    return labels.get(
        metric,
        metric.upper(),
    )


def blocker_category(metric: str) -> str:
    categories = {
        "decision_score": "COMPOSITE",
        "actionability_score": "ACTIONABILITY",
        "confidence": "CONFIDENCE",
        "entry_quality_score": "PRICE_AND_ENTRY",
        "market_structure_score": "MARKET_STRUCTURE",
        "trust_quality_score": "WALLET_QUALITY",
        "wallet_count": "WALLET_BREADTH",
        "data_quality_score": "DATA_QUALITY",
        "hard_veto": "VETO",
    }

    return categories.get(
        metric,
        "OTHER",
    )


def build_upgrade_action(
    failure: dict[str, Any],
) -> str:
    metric = str(failure["metric"])
    current = safe_float(failure.get("current"))
    required = safe_float(failure.get("required"))
    gap = max(0.0, required - current)

    if metric == "hard_veto":
        return (
            "Clear every hard-veto condition before "
            "considering an upgrade."
        )

    if metric == "decision_score":
        return (
            f"Decision score needs {gap:.2f} more points "
            "from stronger underlying evidence."
        )

    if metric == "actionability_score":
        return (
            f"Actionability needs {gap:.2f} more points "
            "from improved timing, liquidity, edge, or "
            "execution conditions."
        )

    if metric == "confidence":
        return (
            f"Confidence needs {gap:.2f} more points "
            "from broader and more consistent evidence."
        )

    if metric == "entry_quality_score":
        return (
            f"Entry quality needs {gap:.2f} more points. "
            "Wait for a better price or more remaining edge."
        )

    if metric == "market_structure_score":
        return (
            f"Market structure needs {gap:.2f} more points "
            "from improved liquidity, spreads, or tradability."
        )

    if metric == "trust_quality_score":
        return (
            f"Trust quality needs {gap:.2f} more points "
            "from wallets with stronger resolved performance."
        )

    if metric == "wallet_count":
        additional_wallets = max(
            1,
            int(round(required - current)),
        )

        suffix = (
            "s"
            if additional_wallets != 1
            else ""
        )

        return (
            f"Require at least {additional_wallets} "
            f"additional independent supporting wallet"
            f"{suffix}."
        )

    if metric == "data_quality_score":
        return (
            f"Data quality needs {gap:.2f} more points. "
            "Refresh incomplete or stale upstream data."
        )

    return (
        f"Improve {metric} from {current:.2f} "
        f"to at least {required:.2f}."
    )


def classify_upgrade(
    action: str,
    hard_veto: bool,
    buy_failed_count: int,
    watch_failed_count: int,
    buy_gap: float,
    watch_gap: float,
) -> tuple[str, str]:
    if hard_veto:
        return "VETO_BLOCKED", "BLOCKED"

    if action == "BUY" or buy_failed_count == 0:
        return "BUY_READY", "READY"

    if (
        buy_failed_count <= 2
        and buy_gap <= 8.0
    ):
        return "NEAR_BUY", "LOW"

    if (
        action == "WATCH"
        or watch_failed_count == 0
    ):
        return "WATCH_READY", "READY"

    if (
        watch_failed_count <= 1
        and watch_gap <= 10.0
    ):
        return "NEAR_WATCH", "LOW"

    if (
        watch_failed_count <= 2
        and watch_gap <= 22.0
    ):
        return "NEAR_WATCH", "MODERATE"

    return "DISTANT", "HIGH"


def diagnose_decision(
    row: sqlite3.Row,
) -> dict[str, Any]:
    values = {
        "decision_score": safe_float(
            row["decision_score"]
        ),
        "actionability_score": safe_float(
            row["actionability_score"]
        ),
        "confidence": safe_float(
            row["confidence"]
        ),
        "entry_quality_score": safe_float(
            row["entry_quality_score"]
        ),
        "market_structure_score": safe_float(
            row["market_structure_score"]
        ),
        "trust_quality_score": safe_float(
            row["trust_quality_score"]
        ),
        "wallet_count": float(
            safe_int(row["wallet_count"])
        ),
        "data_quality_score": safe_float(
            row["data_quality_score"]
        ),
    }

    veto_reasons = parse_json_list(
        row["veto_reasons_json"]
    )

    positive_reasons = parse_json_list(
        row["positive_reasons_json"]
    )

    risk_flags = parse_json_list(
        row["risk_flags_json"]
    )

    hard_veto = (
        bool(safe_int(row["hard_veto"]))
        or bool(veto_reasons)
    )

    (
        buy_passed,
        buy_failed,
        buy_gap,
    ) = evaluate_requirements(
        values,
        BUY_THRESHOLDS,
    )

    (
        watch_passed,
        watch_failed,
        watch_gap,
    ) = evaluate_requirements(
        values,
        WATCH_THRESHOLDS,
    )

    if hard_veto:
        veto_failure = {
            "metric": "hard_veto",
            "current": 1.0,
            "required": 0.0,
            "gap": 1.0,
            "normalized_gap": 1.0,
            "reasons": veto_reasons,
        }

        buy_failed.append(veto_failure)
        watch_failed.append(veto_failure)

    ranked_buy_failures = rank_failures(
        buy_failed
    )

    ranked_watch_failures = rank_failures(
        watch_failed
    )

    current_action = str(
        row["decision_action"]
        or "PASS"
    ).upper()

    (
        nearest_upgrade,
        upgrade_difficulty,
    ) = classify_upgrade(
        action=current_action,
        hard_veto=hard_veto,
        buy_failed_count=len(buy_failed),
        watch_failed_count=len(watch_failed),
        buy_gap=buy_gap,
        watch_gap=watch_gap,
    )

    if nearest_upgrade in {
        "BUY_READY",
        "NEAR_BUY",
    }:
        relevant_failures = (
            ranked_buy_failures
        )
    else:
        relevant_failures = (
            ranked_watch_failures
        )

    if not relevant_failures:
        relevant_failures = (
            ranked_buy_failures
            or ranked_watch_failures
        )

    if hard_veto:
        primary_metric = "hard_veto"
    elif relevant_failures:
        primary_metric = str(
            relevant_failures[0]["metric"]
        )
    else:
        primary_metric = "none"

    secondary_metric = None

    if len(relevant_failures) > 1:
        secondary_metric = str(
            relevant_failures[1]["metric"]
        )

    primary_blocker = (
        "NONE"
        if primary_metric == "none"
        else blocker_label(primary_metric)
    )

    secondary_blocker = (
        blocker_label(secondary_metric)
        if secondary_metric
        else None
    )

    category = (
        "NONE"
        if primary_metric == "none"
        else blocker_category(primary_metric)
    )

    if nearest_upgrade in {
        "BUY_READY",
        "NEAR_BUY",
    }:
        upgrade_failures = (
            ranked_buy_failures
        )
    else:
        upgrade_failures = (
            ranked_watch_failures
        )

    upgrade_actions = [
        build_upgrade_action(failure)
        for failure in upgrade_failures[:3]
    ]

    title = str(
        row["title"]
        or "Untitled opportunity"
    )

    if hard_veto:
        veto_text = (
            "; ".join(veto_reasons[:3])
            or "active hard veto"
        )

        diagnostic_summary = (
            f"{title} remains {current_action}. "
            f"It is veto-blocked by: {veto_text}."
        )

    elif nearest_upgrade in {
        "BUY_READY",
        "WATCH_READY",
    }:
        readable_upgrade = (
            nearest_upgrade
            .replace("_", " ")
            .lower()
        )

        diagnostic_summary = (
            f"{title} is {readable_upgrade} "
            "under the configured thresholds."
        )

    else:
        target = (
            "BUY"
            if nearest_upgrade == "NEAR_BUY"
            else "WATCH"
        )

        diagnostic_summary = (
            f"{title} remains {current_action}. "
            f"Nearest upgrade: {target}. "
            f"Primary blocker: {primary_blocker}."
        )

        if secondary_blocker:
            diagnostic_summary += (
                f" Secondary blocker: "
                f"{secondary_blocker}."
            )

    return {
        "opportunity_key": str(
            row["opportunity_key"]
        ),
        "market_id": (
            str(row["market_id"])
            if row["market_id"] is not None
            else None
        ),
        "title": title,
        "outcome": str(
            row["outcome"]
            or ""
        ),
        "current_action": current_action,
        "decision_grade": (
            str(row["decision_grade"])
            if row["decision_grade"] is not None
            else None
        ),
        "decision_score": values[
            "decision_score"
        ],
        "actionability_score": values[
            "actionability_score"
        ],
        "confidence": values[
            "confidence"
        ],
        "entry_quality_score": values[
            "entry_quality_score"
        ],
        "market_structure_score": values[
            "market_structure_score"
        ],
        "trust_quality_score": values[
            "trust_quality_score"
        ],
        "wallet_count": int(
            values["wallet_count"]
        ),
        "elite_wallet_count": safe_int(
            row["elite_wallet_count"]
        ),
        "supporting_wallet_count": safe_int(
            row["supporting_wallet_count"]
        ),
        "trusted_wallet_count": safe_int(
            row["trusted_wallet_count"]
        ),
        "data_quality_score": values[
            "data_quality_score"
        ],
        "hard_veto": int(hard_veto),
        "buy_requirements_passed": len(
            buy_passed
        ),
        "buy_requirements_failed": len(
            buy_failed
        ),
        "watch_requirements_passed": len(
            watch_passed
        ),
        "watch_requirements_failed": len(
            watch_failed
        ),
        "buy_gap_score": buy_gap,
        "watch_gap_score": watch_gap,
        "nearest_upgrade": nearest_upgrade,
        "upgrade_difficulty": (
            upgrade_difficulty
        ),
        "primary_blocker": (
            primary_blocker
        ),
        "secondary_blocker": (
            secondary_blocker
        ),
        "blocker_category": category,
        "failed_buy_requirements_json": (
            json.dumps(
                ranked_buy_failures,
                ensure_ascii=False,
                sort_keys=True,
            )
        ),
        "failed_watch_requirements_json": (
            json.dumps(
                ranked_watch_failures,
                ensure_ascii=False,
                sort_keys=True,
            )
        ),
        "veto_reasons_json": json.dumps(
            veto_reasons,
            ensure_ascii=False,
        ),
        "positive_reasons_json": (
            json.dumps(
                positive_reasons,
                ensure_ascii=False,
            )
        ),
        "risk_flags_json": json.dumps(
            risk_flags,
            ensure_ascii=False,
        ),
        "upgrade_actions_json": json.dumps(
            upgrade_actions,
            ensure_ascii=False,
        ),
        "diagnostic_summary": (
            diagnostic_summary
        ),
        "source_calculated_at": (
            str(row["calculated_at"])
            if row["calculated_at"] is not None
            else None
        ),
    }


DIAGNOSTIC_COLUMNS = (
    "opportunity_key",
    "market_id",
    "title",
    "outcome",
    "current_action",
    "decision_grade",
    "decision_score",
    "actionability_score",
    "confidence",
    "entry_quality_score",
    "market_structure_score",
    "trust_quality_score",
    "wallet_count",
    "elite_wallet_count",
    "supporting_wallet_count",
    "trusted_wallet_count",
    "data_quality_score",
    "hard_veto",
    "buy_requirements_passed",
    "buy_requirements_failed",
    "watch_requirements_passed",
    "watch_requirements_failed",
    "buy_gap_score",
    "watch_gap_score",
    "nearest_upgrade",
    "upgrade_difficulty",
    "primary_blocker",
    "secondary_blocker",
    "blocker_category",
    "failed_buy_requirements_json",
    "failed_watch_requirements_json",
    "veto_reasons_json",
    "positive_reasons_json",
    "risk_flags_json",
    "upgrade_actions_json",
    "diagnostic_summary",
    "source_calculated_at",
    "diagnosed_at",
    "run_id",
)


def diagnostic_values(
    diagnostic: dict[str, Any],
    diagnosed_at: str,
    run_id: str,
) -> tuple[Any, ...]:
    return tuple(
        (
            diagnosed_at
            if column == "diagnosed_at"
            else run_id
            if column == "run_id"
            else diagnostic.get(column)
        )
        for column in DIAGNOSTIC_COLUMNS
    )


def save_diagnostics(
    connection: sqlite3.Connection,
    diagnostics: list[dict[str, Any]],
    diagnosed_at: str,
    run_id: str,
) -> tuple[int, int]:
    placeholders = ", ".join(
        "?"
        for _ in DIAGNOSTIC_COLUMNS
    )

    columns_sql = ", ".join(
        DIAGNOSTIC_COLUMNS
    )

    update_sql = ", ".join(
        f"{column} = excluded.{column}"
        for column in DIAGNOSTIC_COLUMNS
        if column != "opportunity_key"
    )

    current_sql = f"""
        INSERT INTO
        institutional_decision_diagnostics (
            {columns_sql}
        )
        VALUES (
            {placeholders}
        )
        ON CONFLICT(opportunity_key)
        DO UPDATE SET
            {update_sql}
    """

    history_sql = f"""
        INSERT INTO
        institutional_decision_diagnostic_history (
            {columns_sql}
        )
        VALUES (
            {placeholders}
        )
    """

    values = [
        diagnostic_values(
            diagnostic,
            diagnosed_at,
            run_id,
        )
        for diagnostic in diagnostics
    ]

    connection.executemany(
        current_sql,
        values,
    )

    connection.executemany(
        history_sql,
        values,
    )

    return len(values), len(values)


def print_board(
    diagnostics: list[dict[str, Any]],
    display_limit: int,
) -> None:
    priority = {
        "BUY_READY": 0,
        "NEAR_BUY": 1,
        "WATCH_READY": 2,
        "NEAR_WATCH": 3,
        "DISTANT": 4,
        "VETO_BLOCKED": 5,
    }

    ordered = sorted(
        diagnostics,
        key=lambda item: (
            priority.get(
                item["nearest_upgrade"],
                99,
            ),
            item["buy_gap_score"],
            item["watch_gap_score"],
            -item["decision_score"],
        ),
    )

    print()
    print("DECISION DIAGNOSTIC BOARD")
    print("-" * 120)

    for index, item in enumerate(
        ordered[:display_limit],
        start=1,
    ):
        outcome_text = (
            f" — {item['outcome']}"
            if item["outcome"]
            else ""
        )

        print(
            f"{index:>3}. "
            f"{item['nearest_upgrade']:<13} "
            f"{item['current_action']:<5} "
            f"score={item['decision_score']:>6.2f} "
            f"buy_gap={item['buy_gap_score']:>6.2f} "
            f"watch_gap={item['watch_gap_score']:>6.2f}"
        )

        print(
            f"     {item['title']}"
            f"{outcome_text}"
        )

        print(
            "     "
            f"BUY passed/failed="
            f"{item['buy_requirements_passed']}/"
            f"{item['buy_requirements_failed']} | "
            f"WATCH passed/failed="
            f"{item['watch_requirements_passed']}/"
            f"{item['watch_requirements_failed']}"
        )

        blocker_text = item[
            "primary_blocker"
        ]

        if item["secondary_blocker"]:
            blocker_text += (
                f" / "
                f"{item['secondary_blocker']}"
            )

        print(
            "     "
            f"blocker={blocker_text} | "
            f"difficulty="
            f"{item['upgrade_difficulty']}"
        )

        upgrade_actions = parse_json_list(
            item["upgrade_actions_json"]
        )

        if upgrade_actions:
            print(
                f"     next="
                f"{upgrade_actions[0]}"
            )

        veto_reasons = parse_json_list(
            item["veto_reasons_json"]
        )

        if veto_reasons:
            print(
                f"     veto="
                f"{'; '.join(veto_reasons[:2])}"
            )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Explain saved institutional decisions "
            "and calculate their distance to WATCH "
            "and BUY thresholds."
        )
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
    )

    parser.add_argument(
        "--decision-limit",
        type=int,
        default=250,
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=25,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    if arguments.decision_limit <= 0:
        print(
            "ERROR: --decision-limit must be "
            "greater than zero.",
            file=sys.stderr,
        )
        return 2

    if arguments.display_limit <= 0:
        print(
            "ERROR: --display-limit must be "
            "greater than zero.",
            file=sys.stderr,
        )
        return 2

    database_path = (
        arguments.database
        .expanduser()
        .resolve()
    )

    if not database_path.exists():
        print(
            f"ERROR: Database not found: "
            f"{database_path}",
            file=sys.stderr,
        )
        return 2

    started_clock = time.perf_counter()
    started_at = utc_now()

    run_id = uuid.uuid4().hex

    mode = (
        "APPLY"
        if arguments.apply
        else "DRY RUN"
    )

    connection = connect_database(
        database_path
    )

    try:
        if not table_exists(
            connection,
            "institutional_decisions",
        ):
            print(
                "ERROR: Required table "
                "'institutional_decisions' "
                "does not exist. Run the "
                "Institutional Decision Engine "
                "with --apply first.",
                file=sys.stderr,
            )
            return 2

        create_schema(connection)

        if arguments.apply:
            connection.execute(
                """
                INSERT INTO
                institutional_decision_diagnostic_runs (
                    run_id,
                    methodology_version,
                    mode,
                    started_at,
                    status
                )
                VALUES (?, ?, ?, ?, 'RUNNING')
                """,
                (
                    run_id,
                    ENGINE_VERSION,
                    mode,
                    started_at,
                ),
            )

            connection.commit()

        rows = connection.execute(
            """
            SELECT *
            FROM institutional_decisions
            ORDER BY
                decision_score DESC,
                actionability_score DESC
            LIMIT ?
            """,
            (
                arguments.decision_limit,
            ),
        ).fetchall()

        diagnostics = [
            diagnose_decision(row)
            for row in rows
        ]

        classifications = (
            "BUY_READY",
            "NEAR_BUY",
            "WATCH_READY",
            "NEAR_WATCH",
            "DISTANT",
            "VETO_BLOCKED",
        )

        counts = {
            classification: sum(
                1
                for item in diagnostics
                if item["nearest_upgrade"]
                == classification
            )
            for classification in classifications
        }

        diagnosed_at = utc_now()

        diagnostics_saved = 0
        history_saved = 0

        if arguments.apply:
            (
                diagnostics_saved,
                history_saved,
            ) = save_diagnostics(
                connection,
                diagnostics,
                diagnosed_at,
                run_id,
            )

        duration_seconds = (
            time.perf_counter()
            - started_clock
        )

        completed_at = utc_now()

        if arguments.apply:
            connection.execute(
                """
                UPDATE
                    institutional_decision_diagnostic_runs
                SET
                    completed_at = ?,
                    source_decisions = ?,
                    diagnostics_analyzed = ?,
                    diagnostics_saved = ?,
                    history_saved = ?,
                    buy_ready_count = ?,
                    near_buy_count = ?,
                    watch_ready_count = ?,
                    near_watch_count = ?,
                    distant_count = ?,
                    veto_blocked_count = ?,
                    duration_seconds = ?,
                    status = 'COMPLETED',
                    error_message = NULL
                WHERE run_id = ?
                """,
                (
                    completed_at,
                    len(rows),
                    len(diagnostics),
                    diagnostics_saved,
                    history_saved,
                    counts["BUY_READY"],
                    counts["NEAR_BUY"],
                    counts["WATCH_READY"],
                    counts["NEAR_WATCH"],
                    counts["DISTANT"],
                    counts["VETO_BLOCKED"],
                    duration_seconds,
                    run_id,
                ),
            )

            connection.commit()

        print()
        print("=" * 120)
        print(
            "POLYMARKET DECISION DIAGNOSTICS "
            f"& EXPLAINABILITY ENGINE "
            f"v{ENGINE_VERSION}"
        )
        print("=" * 120)

        print(
            f"Database:                  "
            f"{database_path}"
        )

        print(
            f"Mode:                      "
            f"{mode}"
        )

        print(
            f"Run ID:                    "
            f"{run_id}"
        )

        print(
            f"Source decisions:          "
            f"{len(rows)}"
        )

        print(
            f"Diagnostics analyzed:      "
            f"{len(diagnostics)}"
        )

        print(
            f"Diagnostics saved:         "
            f"{diagnostics_saved}"
        )

        print(
            f"History saved:             "
            f"{history_saved}"
        )

        print(
            "BUY READY/NEAR BUY/"
            "WATCH READY/NEAR WATCH/"
            "DISTANT/VETO: "
            f"{counts['BUY_READY']}/"
            f"{counts['NEAR_BUY']}/"
            f"{counts['WATCH_READY']}/"
            f"{counts['NEAR_WATCH']}/"
            f"{counts['DISTANT']}/"
            f"{counts['VETO_BLOCKED']}"
        )

        print(
            f"Duration:                  "
            f"{duration_seconds:.3f}s"
        )

        print("=" * 120)

        print_board(
            diagnostics,
            arguments.display_limit,
        )

        print()
        print("=" * 120)

        if arguments.apply:
            print(
                "Current diagnostics: "
                "institutional_decision_diagnostics"
            )

            print(
                "Historical diagnostics: "
                "institutional_decision_"
                "diagnostic_history"
            )

        else:
            print(
                "Dry run complete. No diagnostics "
                "or history snapshots were changed."
            )

            print(
                "Review the board, then rerun "
                "with --apply."
            )

        print(
            "Diagnostics explain research "
            "classifications; they do not "
            "guarantee outcomes or prescribe "
            "position size."
        )

        print("=" * 120)

        return 0

    except Exception as error:
        duration_seconds = (
            time.perf_counter()
            - started_clock
        )

        if arguments.apply:
            try:
                connection.execute(
                    """
                    UPDATE
                        institutional_decision_diagnostic_runs
                    SET
                        completed_at = ?,
                        duration_seconds = ?,
                        status = 'FAILED',
                        error_message = ?
                    WHERE run_id = ?
                    """,
                    (
                        utc_now(),
                        duration_seconds,
                        (
                            f"{type(error).__name__}: "
                            f"{error}"
                        ),
                        run_id,
                    ),
                )

                connection.commit()

            except Exception:
                connection.rollback()

        print(
            f"ERROR: "
            f"{type(error).__name__}: "
            f"{error}",
            file=sys.stderr,
        )

        return 1

    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())