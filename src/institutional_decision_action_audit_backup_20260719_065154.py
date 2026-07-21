"""
Institutional Decision Action Audit
Version 1.0

Purpose
-------
Audit institutional learning observations before permanent outcome grading.

This diagnostic reports:

- BUY versus AVOID distribution
- resolved versus unresolved distribution
- decision actions by resolution status
- outcome grading readiness
- duplicate market/outcome observations
- observations with missing or invalid actions
- available source/provenance columns
- distributions for likely engine/source fields

This script is read-only.
It never modifies the database.
"""

from __future__ import annotations

import argparse
import sqlite3

from collections import Counter
from pathlib import Path
from typing import Any


DATABASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "polymarket.db"
)

TABLE_NAME = (
    "institutional_learning_observations"
)

DEFAULT_DISPLAY_LIMIT = 100


def normalize_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value)
        .strip()
        .split()
    )


def normalize_upper(
    value: Any,
) -> str:
    return normalize_text(
        value
    ).upper()


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
        (
            table_name,
        ),
    ).fetchone()

    return row is not None


def get_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[str]:
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return [
        str(
            row["name"]
        )
        for row in rows
    ]


def safe_column(
    columns: set[str],
    candidates: list[str],
) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


def print_header(
    title: str,
) -> None:
    print()
    print("=" * 150)
    print(title)
    print("=" * 150)


def print_section(
    title: str,
) -> None:
    print()
    print(title)
    print("-" * 150)


def print_counter(
    counter: Counter,
    empty_label: str = "(blank/null)",
) -> None:
    if not counter:
        print("No rows found.")
        return

    width = max(
        len(
            empty_label
            if not key
            else str(key)
        )
        for key in counter
    )

    for key, count in sorted(
        counter.items(),
        key=lambda item: (
            -item[1],
            str(item[0]),
        ),
    ):
        label = (
            empty_label
            if not key
            else str(key)
        )

        print(
            f"{label:<{width}} : {count:,}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit institutional decision actions "
            "without modifying the database."
        )
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    display_limit = max(
        args.display_limit,
        1,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        if not table_exists(
            connection,
            TABLE_NAME,
        ):
            raise RuntimeError(
                "Missing required table: "
                f"{TABLE_NAME}"
            )

        column_list = get_columns(
            connection,
            TABLE_NAME,
        )

        columns = set(
            column_list
        )

        required_columns = {
            "observation_key",
            "market_id",
            "title",
            "selected_outcome",
            "decision_action",
            "resolution_status",
            "actual_result",
            "is_correct",
            "source_outcome_won",
            "source_outcome_lost",
            "winning_outcome",
        }

        missing = sorted(
            required_columns
            - columns
        )

        if missing:
            raise RuntimeError(
                "Missing required columns: "
                + ", ".join(
                    missing
                )
            )

        rows = connection.execute(
            f"""
            SELECT *

            FROM {TABLE_NAME}

            ORDER BY
                COALESCE(
                    resolved_at,
                    created_at,
                    updated_at,
                    ''
                ) ASC,
                observation_key ASC
            """
        ).fetchall()

        total_rows = len(
            rows
        )

        action_counter = Counter(
            normalize_upper(
                row[
                    "decision_action"
                ]
            )
            for row in rows
        )

        resolution_counter = Counter(
            normalize_upper(
                row[
                    "resolution_status"
                ]
            )
            for row in rows
        )

        action_resolution_counter = Counter(
            (
                normalize_upper(
                    row[
                        "decision_action"
                    ]
                ),
                normalize_upper(
                    row[
                        "resolution_status"
                    ]
                ),
            )
            for row in rows
        )

        actual_result_counter = Counter(
            normalize_upper(
                row[
                    "actual_result"
                ]
            )
            for row in rows
        )

        resolved_rows = [
            row
            for row in rows
            if normalize_upper(
                row[
                    "resolution_status"
                ]
            ) == "RESOLVED"
        ]

        unresolved_rows = [
            row
            for row in rows
            if normalize_upper(
                row[
                    "resolution_status"
                ]
            ) != "RESOLVED"
        ]

        resolved_ungraded = [
            row
            for row in resolved_rows
            if not normalize_text(
                row[
                    "actual_result"
                ]
            )
        ]

        resolved_graded = [
            row
            for row in resolved_rows
            if normalize_text(
                row[
                    "actual_result"
                ]
            )
        ]

        valid_actions = {
            "BUY",
            "AVOID",
        }

        invalid_action_rows = [
            row
            for row in rows
            if normalize_upper(
                row[
                    "decision_action"
                ]
            )
            not in valid_actions
        ]

        resolved_action_counter = Counter(
            normalize_upper(
                row[
                    "decision_action"
                ]
            )
            for row in resolved_rows
        )

        unresolved_action_counter = Counter(
            normalize_upper(
                row[
                    "decision_action"
                ]
            )
            for row in unresolved_rows
        )

        complementary_rows = []
        invalid_flag_rows = []

        for row in resolved_ungraded:
            won = row[
                "source_outcome_won"
            ]

            lost = row[
                "source_outcome_lost"
            ]

            if (
                won in {
                    0,
                    1,
                }
                and lost in {
                    0,
                    1,
                }
                and won + lost == 1
            ):
                complementary_rows.append(
                    row
                )
            else:
                invalid_flag_rows.append(
                    row
                )

        duplicate_counter = Counter(
            (
                normalize_text(
                    row[
                        "market_id"
                    ]
                ),
                normalize_text(
                    row[
                        "selected_outcome"
                    ]
                ).casefold(),
                normalize_upper(
                    row[
                        "decision_action"
                    ]
                ),
            )
            for row in rows
        )

        duplicate_keys = {
            key: count
            for key, count in duplicate_counter.items()
            if count > 1
        }

        opposite_action_counter = Counter()

        market_outcome_actions: dict[
            tuple[str, str],
            set[str],
        ] = {}

        for row in rows:
            key = (
                normalize_text(
                    row[
                        "market_id"
                    ]
                ),
                normalize_text(
                    row[
                        "selected_outcome"
                    ]
                ).casefold(),
            )

            market_outcome_actions.setdefault(
                key,
                set(),
            ).add(
                normalize_upper(
                    row[
                        "decision_action"
                    ]
                )
            )

        for actions in market_outcome_actions.values():
            if (
                "BUY" in actions
                and "AVOID" in actions
            ):
                opposite_action_counter[
                    "BUY_AND_AVOID"
                ] += 1

        provenance_candidates = [
            "source_engine",
            "engine_name",
            "decision_engine",
            "created_by",
            "source",
            "observation_source",
            "methodology",
            "decision_method",
            "model_version",
            "engine_version",
            "run_id",
            "decision_run_id",
            "source_run_id",
            "institutional_run_id",
            "recommendation_tier",
            "conviction_grade",
            "decision_grade",
        ]

        provenance_columns = [
            column
            for column in provenance_candidates
            if column in columns
        ]

        print_header(
            "POLYMARKET INSTITUTIONAL DECISION ACTION AUDIT v1.0"
        )

        print(
            f"Database:                         "
            f"{DATABASE_PATH}"
        )

        print(
            f"Table:                            "
            f"{TABLE_NAME}"
        )

        print(
            f"Total observations:               "
            f"{total_rows:,}"
        )

        print(
            f"Resolved observations:            "
            f"{len(resolved_rows):,}"
        )

        print(
            f"Unresolved observations:          "
            f"{len(unresolved_rows):,}"
        )

        print(
            f"Resolved and ungraded:             "
            f"{len(resolved_ungraded):,}"
        )

        print(
            f"Resolved and already graded:       "
            f"{len(resolved_graded):,}"
        )

        print(
            f"Resolved grading-ready flags:      "
            f"{len(complementary_rows):,}"
        )

        print(
            f"Resolved invalid settlement flags: "
            f"{len(invalid_flag_rows):,}"
        )

        print(
            f"Invalid decision actions:          "
            f"{len(invalid_action_rows):,}"
        )

        print(
            f"Duplicate market/outcome/actions:  "
            f"{len(duplicate_keys):,}"
        )

        print(
            f"Market/outcomes with BUY + AVOID:  "
            f"{opposite_action_counter['BUY_AND_AVOID']:,}"
        )

        print_section(
            "ALL DECISION ACTIONS"
        )

        print_counter(
            action_counter
        )

        print_section(
            "RESOLVED DECISION ACTIONS"
        )

        print_counter(
            resolved_action_counter
        )

        print_section(
            "UNRESOLVED DECISION ACTIONS"
        )

        print_counter(
            unresolved_action_counter
        )

        print_section(
            "RESOLUTION STATUS DISTRIBUTION"
        )

        print_counter(
            resolution_counter
        )

        print_section(
            "ACTION BY RESOLUTION STATUS"
        )

        if action_resolution_counter:
            for (
                action,
                status,
            ), count in sorted(
                action_resolution_counter.items(),
                key=lambda item: (
                    -item[1],
                    item[0][0],
                    item[0][1],
                ),
            ):
                print(
                    f"action={action or '(blank/null)':<12} "
                    f"status={status or '(blank/null)':<24} "
                    f"count={count:,}"
                )
        else:
            print(
                "No rows found."
            )

        print_section(
            "EXISTING ACTUAL RESULT DISTRIBUTION"
        )

        print_counter(
            actual_result_counter
        )

        print_section(
            "AVAILABLE PROVENANCE COLUMNS"
        )

        if provenance_columns:
            for column in provenance_columns:
                values = Counter(
                    normalize_text(
                        row[
                            column
                        ]
                    )
                    for row in rows
                )

                print()
                print(
                    f"{column}:"
                )

                for value, count in values.most_common(
                    20
                ):
                    label = (
                        value
                        if value
                        else "(blank/null)"
                    )

                    print(
                        f"  {label:<70} "
                        f"{count:,}"
                    )
        else:
            print(
                "No recognized provenance or "
                "engine-source columns were found."
            )

        print_section(
            "RESOLVED UNGRADED SAMPLE"
        )

        for index, row in enumerate(
            resolved_ungraded[
                :display_limit
            ],
            start=1,
        ):
            print(
                f"{index:>3}. "
                f"action="
                f"{normalize_upper(row['decision_action']):<7} "
                f"won={str(row['source_outcome_won']):<4} "
                f"lost={str(row['source_outcome_lost']):<4} "
                f"selected="
                f"{normalize_text(row['selected_outcome'])}"
            )

            print(
                f"     winner="
                f"{normalize_text(row['winning_outcome']) or '-'}"
            )

            print(
                f"     title="
                f"{normalize_text(row['title'])}"
            )

            print(
                f"     market_id="
                f"{normalize_text(row['market_id'])}"
            )

            print(
                f"     observation_key="
                f"{normalize_text(row['observation_key'])}"
            )

        if (
            len(resolved_ungraded)
            > display_limit
        ):
            print()
            print(
                f"... "
                f"{len(resolved_ungraded) - display_limit:,} "
                f"additional rows omitted."
            )

        print_section(
            "DUPLICATE MARKET / OUTCOME / ACTION GROUPS"
        )

        shown = 0

        for (
            market_id,
            selected_outcome,
            decision_action,
        ), count in sorted(
            duplicate_keys.items(),
            key=lambda item: (
                -item[1],
                item[0][0],
                item[0][1],
            ),
        ):
            if shown >= display_limit:
                break

            shown += 1

            print(
                f"{shown:>3}. "
                f"count={count:<4} "
                f"action={decision_action or '(blank/null)':<8} "
                f"selected={selected_outcome or '(blank/null)'}"
            )

            print(
                f"     market_id="
                f"{market_id or '(blank/null)'}"
            )

        if not duplicate_keys:
            print(
                "No duplicate market/outcome/action "
                "groups were detected."
            )

        print_section(
            "AUDIT INTERPRETATION"
        )

        if (
            resolved_action_counter.get(
                "BUY",
                0,
            ) == 0
            and resolved_action_counter.get(
                "AVOID",
                0,
            ) > 0
        ):
            print(
                "WARNING: All resolved observations "
                "are classified as AVOID."
            )

            print(
                "Before running the learning outcome "
                "engine with --apply, verify that the "
                "upstream decision engine intentionally "
                "created only AVOID observations."
            )

        elif (
            resolved_action_counter.get(
                "BUY",
                0,
            ) > 0
            and resolved_action_counter.get(
                "AVOID",
                0,
            ) > 0
        ):
            print(
                "Resolved observations contain both "
                "BUY and AVOID decisions."
            )

        else:
            print(
                "No resolved BUY or AVOID observations "
                "were found."
            )

        if invalid_flag_rows:
            print(
                "WARNING: Some resolved ungraded rows "
                "have incomplete or conflicting "
                "settlement flags."
            )

        if invalid_action_rows:
            print(
                "WARNING: Some observations have missing "
                "or unsupported decision actions."
            )

        print(
            "Database writes:                 NONE"
        )

        print(
            "Learning outcomes modified:      NO"
        )

        print(
            "Settlement records modified:     NO"
        )

        print(
            "Decision methodology modified:   NO"
        )

        print("=" * 150)

    finally:
        connection.close()


if __name__ == "__main__":
    main()
