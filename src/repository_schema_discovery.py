from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
REPORT_PATH = PROJECT_ROOT / "reports" / "repository_compatibility.json"


@dataclass(frozen=True)
class ColumnInfo:
    cid: int
    name: str
    declared_type: str
    not_null: bool
    default_value: Any
    primary_key_position: int


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def object_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[ColumnInfo]:
    rows = connection.execute(
        f"PRAGMA table_info({quote_identifier(table_name)})"
    ).fetchall()
    return [
        ColumnInfo(
            cid=int(row[0]),
            name=str(row[1]),
            declared_type=str(row[2] or ""),
            not_null=bool(row[3]),
            default_value=row[4],
            primary_key_position=int(row[5]),
        )
        for row in rows
    ]


def foreign_keys(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    try:
        rows = connection.execute(
            f"PRAGMA foreign_key_list({quote_identifier(table_name)})"
        ).fetchall()
    except sqlite3.DatabaseError as error:
        return [{"inspection_error": str(error)}]

    return [
        {
            "id": row[0],
            "sequence": row[1],
            "referenced_table": row[2],
            "from_column": row[3],
            "to_column": row[4],
            "on_update": row[5],
            "on_delete": row[6],
            "match": row[7],
        }
        for row in rows
    ]


def indexes(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        rows = connection.execute(
            f"PRAGMA index_list({quote_identifier(table_name)})"
        ).fetchall()
    except sqlite3.DatabaseError as error:
        return [{"inspection_error": str(error)}]

    for row in rows:
        index_name = str(row[1])
        try:
            columns = [
                info[2]
                for info in connection.execute(
                    f"PRAGMA index_info({quote_identifier(index_name)})"
                ).fetchall()
            ]
        except sqlite3.DatabaseError as error:
            columns = [f"inspection_error: {error}"]
        results.append(
            {
                "name": index_name,
                "unique": bool(row[2]),
                "origin": row[3] if len(row) > 3 else None,
                "partial": bool(row[4]) if len(row) > 4 else False,
                "columns": columns,
            }
        )
    return results


def row_count(
    connection: sqlite3.Connection,
    table_name: str,
) -> dict[str, Any]:
    try:
        total = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table_name)}"
        ).fetchone()[0]
        return {"count": int(total), "error": None}
    except sqlite3.DatabaseError as error:
        return {"count": None, "error": str(error)}


def integrity_probe(connection: sqlite3.Connection) -> dict[str, Any]:
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        return {
            "integrity_check": [row[0] for row in integrity],
            "integrity_error": None,
        }
    except sqlite3.DatabaseError as error:
        return {
            "integrity_check": [],
            "integrity_error": str(error),
        }


def foreign_key_probe(connection: sqlite3.Connection) -> dict[str, Any]:
    try:
        rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        return {
            "foreign_key_violations": [
                {
                    "table": row[0],
                    "rowid": row[1],
                    "referenced_table": row[2],
                    "foreign_key_id": row[3],
                }
                for row in rows
            ],
            "foreign_key_check_error": None,
        }
    except sqlite3.DatabaseError as error:
        return {
            "foreign_key_violations": [],
            "foreign_key_check_error": str(error),
        }


def discover_repository(
    database_path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        objects = object_rows(connection)
        report: dict[str, Any] = {
            "generated_at": utc_now(),
            "database_path": str(database_path),
            "sqlite_version": sqlite3.sqlite_version,
            "database": {},
            "tables": {},
            "views": {},
            "indexes": {},
            "triggers": {},
            "compatibility": {},
        }

        report["database"].update(integrity_probe(connection))
        report["database"].update(foreign_key_probe(connection))

        for row in objects:
            object_type = str(row["type"])
            name = str(row["name"])
            base = {
                "name": name,
                "table_name": row["tbl_name"],
                "sql": row["sql"],
            }
            if object_type == "table":
                report["tables"][name] = {
                    **base,
                    "columns": [
                        asdict(column)
                        for column in table_columns(connection, name)
                    ],
                    "foreign_keys": foreign_keys(connection, name),
                    "indexes": indexes(connection, name),
                    "row_count": row_count(connection, name),
                }
            elif object_type == "view":
                report["views"][name] = base
            elif object_type == "index":
                report["indexes"][name] = base
            elif object_type == "trigger":
                report["triggers"][name] = base

        report["compatibility"] = build_compatibility_summary(report)
        return report


def column_names(report: dict[str, Any], table: str) -> list[str]:
    entry = report["tables"].get(table)
    if not entry:
        return []
    return [column["name"] for column in entry["columns"]]


def build_compatibility_summary(report: dict[str, Any]) -> dict[str, Any]:
    known_tables = (
        "schema_migrations",
        "event_consumers",
        "platform_events",
        "elite_wallet_profiles",
        "positions",
        "opportunity_enrichment_current",
        "institutional_reviews",
    )
    summary = {
        "known_tables": {},
        "legacy_or_backup_objects": [],
        "warnings": [],
    }

    all_names = (
        list(report["tables"])
        + list(report["views"])
        + list(report["indexes"])
        + list(report["triggers"])
    )
    summary["legacy_or_backup_objects"] = sorted(
        name
        for name in all_names
        if any(token in name.lower() for token in ("legacy", "backup", "_old"))
    )

    for table in known_tables:
        summary["known_tables"][table] = {
            "exists": table in report["tables"],
            "columns": column_names(report, table),
        }

    if report["database"].get("foreign_key_check_error"):
        summary["warnings"].append(
            "PRAGMA foreign_key_check could not complete: "
            + report["database"]["foreign_key_check_error"]
        )
    if summary["legacy_or_backup_objects"]:
        summary["warnings"].append(
            "Legacy or backup objects exist and should be reviewed before "
            "destructive cleanup."
        )

    migration_columns = set(column_names(report, "schema_migrations"))
    if migration_columns and "migration_id" not in migration_columns:
        summary["warnings"].append(
            "schema_migrations exists but does not use migration_id."
        )

    consumer_columns = set(column_names(report, "event_consumers"))
    if consumer_columns and "enabled" not in consumer_columns:
        summary["warnings"].append(
            "event_consumers exists but does not use enabled."
        )

    elite_columns = set(column_names(report, "elite_wallet_profiles"))
    if elite_columns and "elite_status" not in elite_columns:
        summary["warnings"].append(
            "elite_wallet_profiles is incompatible with the new elite "
            "wallet engine."
        )
    return summary


def write_report(report: dict[str, Any], path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )


def print_summary(report: dict[str, Any]) -> None:
    compatibility = report["compatibility"]
    print("=" * 88)
    print("REPOSITORY COMPATIBILITY DISCOVERY")
    print("=" * 88)
    print(f"{'Tables':<46} {len(report['tables']):,}")
    print(f"{'Views':<46} {len(report['views']):,}")
    print(f"{'Indexes':<46} {len(report['indexes']):,}")
    print(f"{'Triggers':<46} {len(report['triggers']):,}")
    print(
        f"{'Legacy/backup objects':<46} "
        f"{len(compatibility['legacy_or_backup_objects']):,}"
    )
    print("-" * 88)

    for table, status in compatibility["known_tables"].items():
        state = "FOUND" if status["exists"] else "MISSING"
        print(f"{table:<46} {state}")
        if status["exists"]:
            print("  columns: " + ", ".join(status["columns"]))

    print("-" * 88)
    warnings = compatibility["warnings"]
    if warnings:
        print("WARNINGS")
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("WARNINGS: NONE")
    print("=" * 88)


def main() -> int:
    try:
        report = discover_repository()
        write_report(report)
        print_summary(report)
        print(f"Report written to: {REPORT_PATH}")
        return 0
    except Exception as error:
        print(f"DISCOVERY FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
