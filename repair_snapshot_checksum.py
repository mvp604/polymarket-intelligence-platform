from __future__ import annotations

import sqlite3
from pathlib import Path

SNAPSHOT_ID = "live-428f01dc002d21b8345fefed"

OLD_CHECKSUM = (
    "1829ce208bdc453b155c2182a8a3388071593cce4398645a62288a74ca213ce5"
)

NEW_CHECKSUM = (
    "2ca2e3ad296067e3882807ed1e1cb39e3f9561d52454d1c0bd256e0a4bc84648"
)


def find_snapshot_databases(project_root: Path) -> list[Path]:
    matches: list[Path] = []

    for database_path in project_root.rglob("*.db"):
        try:
            with sqlite3.connect(database_path) as connection:
                table = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name = 'historical_snapshots'
                    """
                ).fetchone()

                if table is not None:
                    matches.append(database_path)

        except sqlite3.Error:
            continue

    return matches


def repair_database(database_path: Path) -> bool:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT checksum
            FROM historical_snapshots
            WHERE snapshot_id = ?
            """,
            (SNAPSHOT_ID,),
        ).fetchone()

        if row is None:
            return False

        stored_checksum = row[0]

        print(f"Database: {database_path}")
        print(f"Snapshot: {SNAPSHOT_ID}")
        print(f"Stored checksum: {stored_checksum}")

        if stored_checksum == NEW_CHECKSUM:
            print("Checksum is already repaired.")
            return True

        if stored_checksum != OLD_CHECKSUM:
            raise RuntimeError(
                "The stored checksum does not match the expected old checksum. "
                "No update was made."
            )

        cursor = connection.execute(
            """
            UPDATE historical_snapshots
            SET checksum = ?
            WHERE snapshot_id = ?
              AND checksum = ?
            """,
            (
                NEW_CHECKSUM,
                SNAPSHOT_ID,
                OLD_CHECKSUM,
            ),
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                f"Expected to update one row, but updated {cursor.rowcount}."
            )

        connection.commit()

        repaired = connection.execute(
            """
            SELECT checksum
            FROM historical_snapshots
            WHERE snapshot_id = ?
            """,
            (SNAPSHOT_ID,),
        ).fetchone()

        if repaired is None or repaired[0] != NEW_CHECKSUM:
            raise RuntimeError("Checksum verification failed after update.")

        print("Checksum repaired successfully.")
        return True


def main() -> None:
    project_root = Path(__file__).resolve().parent
    databases = find_snapshot_databases(project_root)

    if not databases:
        raise SystemExit(
            "No SQLite database containing historical_snapshots was found."
        )

    repaired_any = False

    for database_path in databases:
        if repair_database(database_path):
            repaired_any = True

    if not repaired_any:
        raise SystemExit(
            f"Snapshot {SNAPSHOT_ID} was not found in any discovered database."
        )


if __name__ == "__main__":
    main()