import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database/polymarket.db")


def inspect_database() -> None:
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}")
        return

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
        """
    )

    tables = cursor.fetchall()

    print("=" * 76)
    print("POLYMARKET DATABASE STRUCTURE")
    print("=" * 76)

    if not tables:
        print("No tables found.")
        connection.close()
        return

    for (table_name,) in tables:
        print()
        print(f"TABLE: {table_name}")
        print("-" * 76)

        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = cursor.fetchall()

        for column in columns:
            column_id = column[0]
            column_name = column[1]
            column_type = column[2]
            required = "YES" if column[3] else "NO"
            primary_key = "YES" if column[5] else "NO"

            print(
                f"{column_id}: {column_name} | "
                f"Type: {column_type} | "
                f"Required: {required} | "
                f"Primary key: {primary_key}"
            )

        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        row_count = cursor.fetchone()[0]
        print(f"Rows stored: {row_count}")

    connection.close()


if __name__ == "__main__":
    inspect_database()