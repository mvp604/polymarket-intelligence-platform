from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

EXPECTED_TABLES = {
    "wallet_scans",
    "positions",
    "consensus_history",
    "elite_wallet_runs",
    "elite_wallet_rankings",
    "elite_wallet_category_weights",
    "elite_wallet_history",
}


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database was not found:\n{DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def get_table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    return {str(row["name"]) for row in rows}


def get_table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return [
        {
            "position": row["cid"],
            "name": row["name"],
            "type": row["type"],
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


def get_latest_rows(
    connection: sqlite3.Connection,
    table_name: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    columns = get_table_columns(connection, table_name)

    if not columns:
        return []

    column_names = {column["name"] for column in columns}

    preferred_order_columns = [
        "created_at",
        "scanned_at",
        "calculated_at",
        "recorded_at",
        "run_at",
        "id",
    ]

    order_column = next(
        (
            column
            for column in preferred_order_columns
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


def print_table_report(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    print("\n" + "=" * 88)
    print(f"TABLE: {table_name}")
    print("=" * 88)

    columns = get_table_columns(connection, table_name)
    row_count = get_row_count(connection, table_name)

    print(f"Rows: {row_count}")
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
            f"{column['name']:<32} "
            f"{column['type']:<14} "
            f"{flag_text}"
        )

    if row_count == 0:
        print("\nLatest rows: none")
        return

    print("\nLatest rows:")

    try:
        latest_rows = get_latest_rows(
            connection=connection,
            table_name=table_name,
            limit=3,
        )
    except sqlite3.Error as error:
        print(f"  Unable to read sample rows: {error}")
        return

    for index, row in enumerate(latest_rows, start=1):
        print(f"\n  Row {index}:")
        for key, value in row.items():
            print(f"    {key}: {value}")


def main() -> None:
    print("\nPOLYMARKET ELITE WALLET DATABASE AUDIT")
    print("=" * 88)
    print(f"Database: {DATABASE_PATH}")

    connection = connect_database()

    try:
        existing_tables = get_table_names(connection)

        print(f"\nExisting application tables: {len(existing_tables)}")

        for table_name in sorted(existing_tables):
            print(f"  - {table_name}")

        missing_tables = EXPECTED_TABLES - existing_tables
        existing_expected_tables = EXPECTED_TABLES & existing_tables

        print("\nExpected intelligence tables found:")
        if existing_expected_tables:
            for table_name in sorted(existing_expected_tables):
                print(f"  [FOUND] {table_name}")
        else:
            print("  None")

        print("\nExpected intelligence tables missing:")
        if missing_tables:
            for table_name in sorted(missing_tables):
                print(f"  [MISSING] {table_name}")
        else:
            print("  None")

        tables_to_report = [
            table_name
            for table_name in sorted(EXPECTED_TABLES)
            if table_name in existing_tables
        ]

        for table_name in tables_to_report:
            print_table_report(connection, table_name)

        print("\n" + "=" * 88)
        print("AUDIT COMPLETE")
        print("=" * 88)

        if missing_tables:
            print(
                "\nResult: Some Elite Wallet tables are missing. "
                "The next step will be a safe schema migration."
            )
        else:
            print(
                "\nResult: All expected Elite Wallet tables exist. "
                "The next step will be the scoring-engine integration."
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()