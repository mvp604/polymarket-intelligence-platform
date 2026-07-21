from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

TARGET_TABLES = (
    "canonical_market_identities",
    "market_metadata",
    "market_price_metrics",
    "opportunity_scores",
    "opportunity_rankings",
    "institutional_consensus",
    "position_evolution",
    "closing_line_metrics",
    "wallet_ratings",
    "wallet_intelligence",
    "portfolio_overlap",
    "consensus_history",
    "master_opportunities",
    "master_opportunity_history",
    "master_alerts",
    "tracked_markets",
    "positions",
    "wallet_scans",
)

OUTPUT_PATH = PROJECT_ROOT / "logs" / "dashboard_schema_audit.json"


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
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


def get_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return [
        {
            "cid": row["cid"],
            "name": row["name"],
            "type": row["type"],
            "notnull": row["notnull"],
            "default_value": row["dflt_value"],
            "primary_key": row["pk"],
        }
        for row in rows
    ]


def get_indexes(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        f'PRAGMA index_list("{table_name}")'
    ).fetchall()

    indexes: list[dict[str, Any]] = []

    for row in rows:
        index_name = row["name"]
        index_columns = connection.execute(
            f'PRAGMA index_info("{index_name}")'
        ).fetchall()

        indexes.append(
            {
                "name": index_name,
                "unique": row["unique"],
                "origin": row["origin"],
                "partial": row["partial"],
                "columns": [
                    index_column["name"]
                    for index_column in index_columns
                ],
            }
        )

    return indexes


def get_row_count(
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    row = connection.execute(
        f'SELECT COUNT(*) AS total FROM "{table_name}"'
    ).fetchone()
    return int(row["total"] if row else 0)


def get_sample_rows(
    connection: sqlite3.Connection,
    table_name: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        f'SELECT * FROM "{table_name}" LIMIT ?',
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_candidate_keys(
    columns: list[dict[str, Any]],
) -> list[str]:
    names = {column["name"] for column in columns}

    preferred = (
        "canonical_market_id",
        "market_id",
        "condition_id",
        "opportunity_key",
        "consensus_key",
        "evolution_key",
        "wallet",
        "outcome",
        "title",
        "event_id",
        "token_id",
        "yes_token_id",
        "no_token_id",
    )

    return [name for name in preferred if name in names]


def audit_database() -> dict[str, Any]:
    connection = connect_database()

    try:
        audit: dict[str, Any] = {
            "database_path": str(DATABASE_PATH),
            "tables": {},
        }

        all_tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                ORDER BY name
                """
            ).fetchall()
        }

        audit["all_tables"] = sorted(all_tables)

        for table_name in TARGET_TABLES:
            if not table_exists(connection, table_name):
                audit["tables"][table_name] = {
                    "exists": False,
                }
                continue

            columns = get_columns(connection, table_name)

            audit["tables"][table_name] = {
                "exists": True,
                "row_count": get_row_count(connection, table_name),
                "candidate_keys": get_candidate_keys(columns),
                "columns": columns,
                "indexes": get_indexes(connection, table_name),
                "sample_rows": get_sample_rows(
                    connection,
                    table_name,
                ),
            }

        return audit

    finally:
        connection.close()


def print_summary(audit: dict[str, Any]) -> None:
    print()
    print("=" * 118)
    print("MASTER INTELLIGENCE DASHBOARD - SCHEMA AUDIT")
    print("=" * 118)
    print(f"Database: {audit['database_path']}")
    print()

    for table_name in TARGET_TABLES:
        table = audit["tables"].get(
            table_name,
            {"exists": False},
        )

        if not table.get("exists"):
            print(
                f"{table_name:<42}"
                f"{'NOT FOUND':>14}"
            )
            continue

        keys = ", ".join(
            table.get("candidate_keys", [])
        ) or "-"

        print(
            f"{table_name:<42}"
            f"{table['row_count']:>10} rows"
            f"   keys: {keys}"
        )

    print("=" * 118)
    print(f"Full audit saved to: {OUTPUT_PATH}")
    print("=" * 118)


def main() -> None:
    audit = audit_database()

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            audit,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print_summary(audit)


if __name__ == "__main__":
    main()