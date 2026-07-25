from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

RESOLUTION_TABLES = [
    "market_resolutions",
    "market_resolution_outcomes",
    "mapped_market_results",
    "market_mappings",
    "canonical_market_identities",
    "market_identifier_registry",
    "wallet_closed_position_snapshots",
    "wallet_trade_positions",
    "wallet_performance",
    "wallet_performance_markets",
]


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found:\n{DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
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
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return [
        {
            "position": int(row["cid"]),
            "name": str(row["name"]),
            "type": str(row["type"]),
            "not_null": bool(row["notnull"]),
            "default": row["dflt_value"],
            "primary_key": bool(row["pk"]),
        }
        for row in rows
    ]


def get_row_count(
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    row = connection.execute(
        f'SELECT COUNT(*) AS total FROM "{table_name}"'
    ).fetchone()

    return int(row["total"])


def get_sample_rows(
    connection: sqlite3.Connection,
    table_name: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    columns = get_columns(connection, table_name)
    column_names = {column["name"] for column in columns}

    preferred_order = [
        "resolved_at",
        "calculated_at",
        "observed_at",
        "created_at",
        "updated_at",
        "scanned_at",
        "id",
    ]

    order_column = next(
        (
            column
            for column in preferred_order
            if column in column_names
        ),
        None,
    )

    query = f'SELECT * FROM "{table_name}"'

    if order_column:
        query += f' ORDER BY "{order_column}" DESC'

    query += " LIMIT ?"

    rows = connection.execute(query, (limit,)).fetchall()
    return [dict(row) for row in rows]


def find_identifier_columns(
    columns: list[dict[str, Any]],
) -> list[str]:
    candidates = {
        "market_id",
        "condition_id",
        "canonical_market_id",
        "event_id",
        "token_id",
        "slug",
        "question_id",
        "position_id",
        "wallet",
        "outcome",
        "winning_outcome",
        "result",
        "status",
    }

    return [
        column["name"]
        for column in columns
        if column["name"] in candidates
    ]


def print_table_report(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    print("\n" + "=" * 100)
    print(f"TABLE: {table_name}")
    print("=" * 100)

    columns = get_columns(connection, table_name)
    row_count = get_row_count(connection, table_name)
    identifier_columns = find_identifier_columns(columns)

    print(f"Rows: {row_count}")
    print(
        "Potential linkage columns: "
        + (
            ", ".join(identifier_columns)
            if identifier_columns
            else "none detected"
        )
    )

    print("\nColumns:")

    for column in columns:
        flags: list[str] = []

        if column["primary_key"]:
            flags.append("PRIMARY KEY")

        if column["not_null"]:
            flags.append("NOT NULL")

        if column["default"] is not None:
            flags.append(f"DEFAULT={column['default']}")

        flag_text = ", ".join(flags) if flags else "-"

        print(
            f"  {column['position']:>2}. "
            f"{column['name']:<38} "
            f"{column['type']:<14} "
            f"{flag_text}"
        )

    if row_count == 0:
        print("\nSample rows: none")
        return

    try:
        rows = get_sample_rows(
            connection=connection,
            table_name=table_name,
            limit=3,
        )
    except sqlite3.Error as error:
        print(f"\nUnable to read sample rows: {error}")
        return

    print("\nSample rows:")

    for index, row in enumerate(rows, start=1):
        print(f"\n  Row {index}:")

        for key, value in row.items():
            print(f"    {key}: {value}")


def print_basic_resolution_counts(
    connection: sqlite3.Connection,
) -> None:
    print("\n" + "=" * 100)
    print("BASIC LINKAGE COUNTS")
    print("=" * 100)

    positions_total = connection.execute(
        "SELECT COUNT(*) AS total FROM positions"
    ).fetchone()["total"]

    positions_with_market_id = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM positions
        WHERE market_id IS NOT NULL
          AND TRIM(market_id) <> ''
        """
    ).fetchone()["total"]

    unique_position_markets = connection.execute(
        """
        SELECT COUNT(DISTINCT market_id) AS total
        FROM positions
        WHERE market_id IS NOT NULL
          AND TRIM(market_id) <> ''
        """
    ).fetchone()["total"]

    print(f"Total position rows: {positions_total}")
    print(f"Positions with market_id: {positions_with_market_id}")
    print(f"Unique position market IDs: {unique_position_markets}")

    if table_exists(connection, "market_resolutions"):
        resolution_columns = {
            column["name"]
            for column in get_columns(
                connection,
                "market_resolutions",
            )
        }

        if "market_id" in resolution_columns:
            resolved_market_ids = connection.execute(
                """
                SELECT COUNT(DISTINCT market_id) AS total
                FROM market_resolutions
                WHERE market_id IS NOT NULL
                  AND TRIM(market_id) <> ''
                """
            ).fetchone()["total"]

            matching_position_rows = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM positions AS p
                WHERE EXISTS (
                    SELECT 1
                    FROM market_resolutions AS r
                    WHERE r.market_id = p.market_id
                )
                """
            ).fetchone()["total"]

            matching_unique_markets = connection.execute(
                """
                SELECT COUNT(DISTINCT p.market_id) AS total
                FROM positions AS p
                WHERE EXISTS (
                    SELECT 1
                    FROM market_resolutions AS r
                    WHERE r.market_id = p.market_id
                )
                """
            ).fetchone()["total"]

            print(
                f"Distinct IDs in market_resolutions: "
                f"{resolved_market_ids}"
            )
            print(
                f"Position rows matching market_resolutions: "
                f"{matching_position_rows}"
            )
            print(
                f"Unique position markets matching resolutions: "
                f"{matching_unique_markets}"
            )
        else:
            print(
                "market_resolutions exists, but it has no "
                "market_id column."
            )

    if table_exists(connection, "market_resolution_outcomes"):
        outcome_columns = {
            column["name"]
            for column in get_columns(
                connection,
                "market_resolution_outcomes",
            )
        }

        if "market_id" in outcome_columns:
            matching_outcome_rows = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM positions AS p
                WHERE EXISTS (
                    SELECT 1
                    FROM market_resolution_outcomes AS o
                    WHERE o.market_id = p.market_id
                )
                """
            ).fetchone()["total"]

            print(
                "Position rows matching "
                f"market_resolution_outcomes: {matching_outcome_rows}"
            )


def main() -> None:
    print("\nPOLYMARKET RESOLUTION LINKAGE AUDIT")
    print("=" * 100)
    print(f"Database: {DATABASE_PATH}")

    connection = connect_database()

    try:
        existing_tables = [
            table_name
            for table_name in RESOLUTION_TABLES
            if table_exists(connection, table_name)
        ]

        missing_tables = [
            table_name
            for table_name in RESOLUTION_TABLES
            if not table_exists(connection, table_name)
        ]

        print("\nResolution-related tables found:")

        for table_name in existing_tables:
            print(f"  [FOUND] {table_name}")

        print("\nResolution-related tables missing:")

        if missing_tables:
            for table_name in missing_tables:
                print(f"  [MISSING] {table_name}")
        else:
            print("  None")

        print_basic_resolution_counts(connection)

        for table_name in existing_tables:
            print_table_report(connection, table_name)

        print("\n" + "=" * 100)
        print("RESOLUTION LINKAGE AUDIT COMPLETE")
        print("=" * 100)

        print(
            "\nNext step: use this report to identify the "
            "canonical join path between wallet positions and "
            "verified winning outcomes."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()