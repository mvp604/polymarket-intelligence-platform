from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


TABLE_NAME = "canonical_market_identities"
RUN_TABLE_NAME = "canonical_market_identity_runs"


def find_database() -> Path:
    """
    Search upward from this script and from the current working directory
    until database/polymarket.db is found.
    """

    search_starts = [
        Path(__file__).resolve().parent,
        Path.cwd().resolve(),
    ]

    checked: set[Path] = set()

    for start in search_starts:
        candidates = [start, *start.parents]

        for parent in candidates:
            candidate = parent / "database" / "polymarket.db"

            if candidate in checked:
                continue

            checked.add(candidate)

            if candidate.exists():
                return candidate

    searched_paths = "\n".join(
        f"  - {path}"
        for path in sorted(checked, key=str)
    )

    raise FileNotFoundError(
        "Could not locate database/polymarket.db.\n"
        f"Paths checked:\n{searched_paths}"
    )


DATABASE_PATH = find_database()


def print_divider(title: str) -> None:
    print()
    print("=" * 120)
    print(title)
    print("=" * 120)


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
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_column_names(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[str]:
    rows = connection.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return [str(row["name"]) for row in rows]


def print_value(value: Any) -> str:
    if value is None:
        return "NULL"

    if isinstance(value, float):
        return f"{value:,.6f}"

    return str(value)


def show_distribution(
    connection: sqlite3.Connection,
    field_name: str,
) -> None:
    rows = connection.execute(
        f"""
        SELECT
            "{field_name}" AS field_value,
            COUNT(*) AS row_count
        FROM "{TABLE_NAME}"
        GROUP BY "{field_name}"
        ORDER BY row_count DESC
        """
    ).fetchall()

    print()
    print(field_name)

    for row in rows:
        value = repr(row["field_value"])
        count = int(row["row_count"])

        print(f"    {value:<30} {count:>12,}")


def count_true(
    connection: sqlite3.Connection,
    field_name: str,
) -> int:
    row = connection.execute(
        f"""
        SELECT COUNT(*) AS row_count
        FROM "{TABLE_NAME}"
        WHERE COALESCE("{field_name}", 0) = 1
        """
    ).fetchone()

    return int(row["row_count"])


def count_nonempty(
    connection: sqlite3.Connection,
    field_name: str,
) -> int:
    row = connection.execute(
        f"""
        SELECT COUNT(*) AS row_count
        FROM "{TABLE_NAME}"
        WHERE "{field_name}" IS NOT NULL
          AND TRIM(CAST("{field_name}" AS TEXT)) <> ''
        """
    ).fetchone()

    return int(row["row_count"])


def main() -> None:
    print()
    print("=" * 120)
    print("CANONICAL MARKET IDENTITY TRADABILITY AUDIT")
    print("=" * 120)
    print(f"Database: {DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        if not table_exists(connection, TABLE_NAME):
            raise RuntimeError(
                f"Required table does not exist: {TABLE_NAME}"
            )

        columns = connection.execute(
            f'PRAGMA table_info("{TABLE_NAME}")'
        ).fetchall()

        column_names = get_column_names(
            connection,
            TABLE_NAME,
        )

        print_divider("TABLE COLUMNS")

        for column in columns:
            print(
                f"{str(column['name']):<38}"
                f"type={str(column['type']):<12}"
                f"not_null={column['notnull']}"
            )

        total_rows = connection.execute(
            f"""
            SELECT COUNT(*) AS row_count
            FROM "{TABLE_NAME}"
            """
        ).fetchone()["row_count"]

        print_divider("TOTAL ROWS")
        print(f"Canonical identities: {int(total_rows):,}")

        audit_fields = [
            "registry_verified",
            "identity_complete",
            "tradable_identity",
            "active",
            "closed",
            "archived",
            "resolved",
            "restricted",
            "accepting_orders",
            "time_status",
            "mapping_method",
        ]

        print_divider("TRADABILITY FIELD DISTRIBUTIONS")

        for field_name in audit_fields:
            if field_name in column_names:
                show_distribution(
                    connection,
                    field_name,
                )

        print_divider("INDIVIDUAL GATE COUNTS")

        boolean_fields = [
            "registry_verified",
            "identity_complete",
            "tradable_identity",
            "active",
            "closed",
            "archived",
            "resolved",
            "restricted",
            "accepting_orders",
        ]

        for field_name in boolean_fields:
            if field_name not in column_names:
                continue

            true_count = count_true(
                connection,
                field_name,
            )

            print(
                f"{field_name + ' = 1':<45}"
                f"{true_count:>12,}"
            )

        text_fields = [
            "polymarket_url",
            "condition_id",
            "gamma_market_id",
            "yes_token_id",
            "no_token_id",
            "start_time",
            "end_time",
            "game_start_time",
        ]

        for field_name in text_fields:
            if field_name not in column_names:
                continue

            populated_count = count_nonempty(
                connection,
                field_name,
            )

            print(
                f"{field_name + ' populated':<45}"
                f"{populated_count:>12,}"
            )

        required_columns = {
            "registry_verified",
            "identity_complete",
            "active",
            "closed",
            "archived",
            "resolved",
            "restricted",
            "accepting_orders",
            "polymarket_url",
        }

        print_divider("RECONSTRUCTED TRADABILITY FUNNEL")

        if required_columns.issubset(set(column_names)):
            funnel_queries = [
                (
                    "Total identities",
                    "1 = 1",
                ),
                (
                    "Registry verified",
                    "registry_verified = 1",
                ),
                (
                    "Verified + complete",
                    """
                    registry_verified = 1
                    AND identity_complete = 1
                    """,
                ),
                (
                    "Verified + complete + active",
                    """
                    registry_verified = 1
                    AND identity_complete = 1
                    AND active = 1
                    """,
                ),
                (
                    "Plus accepting orders",
                    """
                    registry_verified = 1
                    AND identity_complete = 1
                    AND active = 1
                    AND accepting_orders = 1
                    """,
                ),
                (
                    "Plus not closed",
                    """
                    registry_verified = 1
                    AND identity_complete = 1
                    AND active = 1
                    AND accepting_orders = 1
                    AND COALESCE(closed, 0) = 0
                    """,
                ),
                (
                    "Plus not archived",
                    """
                    registry_verified = 1
                    AND identity_complete = 1
                    AND active = 1
                    AND accepting_orders = 1
                    AND COALESCE(closed, 0) = 0
                    AND COALESCE(archived, 0) = 0
                    """,
                ),
                (
                    "Plus not resolved",
                    """
                    registry_verified = 1
                    AND identity_complete = 1
                    AND active = 1
                    AND accepting_orders = 1
                    AND COALESCE(closed, 0) = 0
                    AND COALESCE(archived, 0) = 0
                    AND COALESCE(resolved, 0) = 0
                    """,
                ),
                (
                    "Plus not restricted",
                    """
                    registry_verified = 1
                    AND identity_complete = 1
                    AND active = 1
                    AND accepting_orders = 1
                    AND COALESCE(closed, 0) = 0
                    AND COALESCE(archived, 0) = 0
                    AND COALESCE(resolved, 0) = 0
                    AND COALESCE(restricted, 0) = 0
                    """,
                ),
                (
                    "Plus URL populated",
                    """
                    registry_verified = 1
                    AND identity_complete = 1
                    AND active = 1
                    AND accepting_orders = 1
                    AND COALESCE(closed, 0) = 0
                    AND COALESCE(archived, 0) = 0
                    AND COALESCE(resolved, 0) = 0
                    AND COALESCE(restricted, 0) = 0
                    AND polymarket_url IS NOT NULL
                    AND TRIM(polymarket_url) <> ''
                    """,
                ),
            ]

            for label, where_clause in funnel_queries:
                row = connection.execute(
                    f"""
                    SELECT COUNT(*) AS row_count
                    FROM "{TABLE_NAME}"
                    WHERE {where_clause}
                    """
                ).fetchone()

                print(
                    f"{label:<45}"
                    f"{int(row['row_count']):>12,}"
                )

        else:
            missing = sorted(
                required_columns.difference(column_names)
            )

            print(
                "Cannot reconstruct the full funnel because "
                f"these columns are missing: {', '.join(missing)}"
            )

        print_divider("ROWS THAT APPEAR TRADABLE BUT ARE FLAGGED FALSE")

        if required_columns.issubset(set(column_names)):
            rows = connection.execute(
                f"""
                SELECT
                    condition_id,
                    question,
                    registry_verified,
                    identity_complete,
                    active,
                    closed,
                    archived,
                    resolved,
                    restricted,
                    accepting_orders,
                    tradable_identity,
                    polymarket_url
                FROM "{TABLE_NAME}"
                WHERE identity_complete = 1
                  AND active = 1
                  AND accepting_orders = 1
                  AND COALESCE(closed, 0) = 0
                  AND COALESCE(archived, 0) = 0
                  AND COALESCE(resolved, 0) = 0
                  AND COALESCE(restricted, 0) = 0
                  AND polymarket_url IS NOT NULL
                  AND TRIM(polymarket_url) <> ''
                  AND COALESCE(tradable_identity, 0) = 0
                LIMIT 10
                """
            ).fetchall()

            if not rows:
                print("No matching rows found.")
            else:
                for index, row in enumerate(rows, start=1):
                    print()
                    print(f"ROW {index}")
                    print(f"Question:             {row['question']}")
                    print(f"Condition ID:         {row['condition_id']}")
                    print(f"Registry verified:    {row['registry_verified']}")
                    print(f"Identity complete:    {row['identity_complete']}")
                    print(f"Active:               {row['active']}")
                    print(f"Closed:               {row['closed']}")
                    print(f"Archived:             {row['archived']}")
                    print(f"Resolved:             {row['resolved']}")
                    print(f"Restricted:           {row['restricted']}")
                    print(f"Accepting orders:     {row['accepting_orders']}")
                    print(f"Tradable identity:    {row['tradable_identity']}")
                    print(f"URL:                  {row['polymarket_url']}")

        print_divider("LATEST ENGINE RUN")

        if table_exists(connection, RUN_TABLE_NAME):
            run = connection.execute(
                f"""
                SELECT *
                FROM "{RUN_TABLE_NAME}"
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

            if run is None:
                print("No run history found.")
            else:
                for key in run.keys():
                    print(
                        f"{key:<40}"
                        f"{print_value(run[key])}"
                    )
        else:
            print(
                f"Run table does not exist: {RUN_TABLE_NAME}"
            )

        print()
        print("=" * 120)
        print("TRADABILITY AUDIT COMPLETE")
        print("=" * 120)

    finally:
        connection.close()


if __name__ == "__main__":
    main()