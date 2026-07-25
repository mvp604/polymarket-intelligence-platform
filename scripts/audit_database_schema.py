from __future__ import annotations

import argparse
import ast
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MARKDOWN_OUTPUT = (
    PROJECT_ROOT
    / "docs"
    / "database_schema_specification_v1.md"
)

DEFAULT_JSON_OUTPUT = (
    PROJECT_ROOT
    / "artifacts"
    / "database_schema_specification_v1.json"
)


@dataclass(slots=True)
class ColumnSpec:
    cid: int
    name: str
    declared_type: str
    not_null: bool
    default_value: Any
    primary_key_position: int


@dataclass(slots=True)
class ForeignKeySpec:
    id: int
    sequence: int
    referenced_table: str
    from_column: str
    to_column: str
    on_update: str
    on_delete: str
    match: str


@dataclass(slots=True)
class IndexColumnSpec:
    sequence: int
    column_id: int
    column_name: str | None


@dataclass(slots=True)
class IndexSpec:
    sequence: int
    name: str
    unique: bool
    origin: str
    partial: bool
    columns: list[IndexColumnSpec] = field(default_factory=list)
    sql: str | None = None


@dataclass(slots=True)
class TableSpec:
    name: str
    sql: str | None
    row_count: int
    columns: list[ColumnSpec]
    foreign_keys: list[ForeignKeySpec]
    indexes: list[IndexSpec]
    referenced_by: list[str]
    source_references: list[str]


@dataclass(slots=True)
class SchemaObjectSpec:
    object_type: str
    name: str
    table_name: str
    sql: str | None


@dataclass(slots=True)
class DatabaseAudit:
    generated_at_utc: str
    project_root: str
    database_path: str
    sqlite_version: str
    journal_mode: str
    foreign_keys_enabled: bool
    integrity_check: str
    table_count: int
    view_count: int
    trigger_count: int
    index_count: int
    tables: list[TableSpec]
    views: list[SchemaObjectSpec]
    triggers: list[SchemaObjectSpec]
    warnings: list[str]


def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def evaluate_path_expression(
    node: ast.AST,
) -> Path | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
    ):
        return Path(node.value)

    if isinstance(node, ast.Call):
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "Path"
        ):
            parts: list[str] = []

            for argument in node.args:
                if not (
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                ):
                    return None

                parts.append(argument.value)

            return Path(*parts)

    if (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Div)
    ):
        left = evaluate_path_expression(node.left)
        right = evaluate_path_expression(node.right)

        if left is not None and right is not None:
            return left / right

    return None


def load_database_path_from_config() -> Path:
    config_path = (
        PROJECT_ROOT
        / "src"
        / "config"
        / "database.py"
    )

    if not config_path.exists():
        raise FileNotFoundError(
            f"Database configuration was not found: "
            f"{config_path}"
        )

    source = config_path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(config_path),
    )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        target_names = [
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
        ]

        if "DATABASE_SETTINGS" not in target_names:
            continue

        if not isinstance(node.value, ast.Call):
            continue

        for keyword in node.value.keywords:
            if keyword.arg != "sqlite_path":
                continue

            value = evaluate_path_expression(
                keyword.value
            )

            if value is not None:
                if value.is_absolute():
                    return value

                return PROJECT_ROOT / value

    fallback_match = re.search(
        (
            r"sqlite_path\s*=\s*"
            r"Path\((['\"])(.*?)\1\)"
            r"\s*/\s*"
            r"(['\"])(.*?)\3"
        ),
        source,
    )

    if fallback_match:
        relative_path = (
            Path(fallback_match.group(2))
            / fallback_match.group(4)
        )

        return PROJECT_ROOT / relative_path

    raise RuntimeError(
        "Unable to determine sqlite_path from "
        "src/config/database.py."
    )


def connect_read_only(
    database_path: Path,
) -> sqlite3.Connection:
    if not database_path.exists():
        raise FileNotFoundError(
            f"SQLite database does not exist: "
            f"{database_path}"
        )

    connection = sqlite3.connect(
        (
            f"file:"
            f"{database_path.resolve()}"
            f"?mode=ro"
        ),
        uri=True,
        timeout=30.0,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA query_only = ON"
    )

    connection.execute(
        "PRAGMA busy_timeout = 30000"
    )

    return connection


def inspect_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[ColumnSpec]:
    rows = connection.execute(
        (
            f"PRAGMA table_info("
            f"{quote_identifier(table_name)}"
            f")"
        )
    ).fetchall()

    return [
        ColumnSpec(
            cid=int(row["cid"]),
            name=str(row["name"]),
            declared_type=str(
                row["type"] or ""
            ),
            not_null=bool(row["notnull"]),
            default_value=row["dflt_value"],
            primary_key_position=int(
                row["pk"]
            ),
        )
        for row in rows
    ]


def inspect_foreign_keys(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[ForeignKeySpec]:
    rows = connection.execute(
        (
            f"PRAGMA foreign_key_list("
            f"{quote_identifier(table_name)}"
            f")"
        )
    ).fetchall()

    return [
        ForeignKeySpec(
            id=int(row["id"]),
            sequence=int(row["seq"]),
            referenced_table=str(
                row["table"]
            ),
            from_column=str(row["from"]),
            to_column=str(
                row["to"] or ""
            ),
            on_update=str(
                row["on_update"]
            ),
            on_delete=str(
                row["on_delete"]
            ),
            match=str(row["match"]),
        )
        for row in rows
    ]


def inspect_indexes(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[IndexSpec]:
    index_rows = connection.execute(
        (
            f"PRAGMA index_list("
            f"{quote_identifier(table_name)}"
            f")"
        )
    ).fetchall()

    indexes: list[IndexSpec] = []

    for index_row in index_rows:
        index_name = str(
            index_row["name"]
        )

        column_rows = connection.execute(
            (
                f"PRAGMA index_info("
                f"{quote_identifier(index_name)}"
                f")"
            )
        ).fetchall()

        sql_row = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE
                type = 'index'
                AND name = ?
            """,
            (index_name,),
        ).fetchone()

        indexes.append(
            IndexSpec(
                sequence=int(
                    index_row["seq"]
                ),
                name=index_name,
                unique=bool(
                    index_row["unique"]
                ),
                origin=str(
                    index_row["origin"]
                ),
                partial=bool(
                    index_row["partial"]
                ),
                columns=[
                    IndexColumnSpec(
                        sequence=int(
                            column_row["seqno"]
                        ),
                        column_id=int(
                            column_row["cid"]
                        ),
                        column_name=(
                            None
                            if column_row["name"]
                            is None
                            else str(
                                column_row["name"]
                            )
                        ),
                    )
                    for column_row
                    in column_rows
                ],
                sql=(
                    None
                    if sql_row is None
                    else sql_row["sql"]
                ),
            )
        )

    return indexes


def collect_source_references(
    table_names: Iterable[str],
) -> dict[str, list[str]]:
    references = {
        table_name: []
        for table_name in table_names
    }

    source_root = PROJECT_ROOT / "src"

    if not source_root.exists():
        return references

    ignored_parts = {
        ".venv",
        "__pycache__",
        "backups",
        "artifacts",
    }

    for path in source_root.rglob("*.py"):
        if any(
            part in ignored_parts
            for part in path.parts
        ):
            continue

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        relative_path = str(
            path.relative_to(PROJECT_ROOT)
        ).replace("\\", "/")

        lines = text.splitlines()

        for table_name in table_names:
            pattern = re.compile(
                (
                    rf"(?<![A-Za-z0-9_])"
                    rf"{re.escape(table_name)}"
                    rf"(?![A-Za-z0-9_])"
                ),
                flags=re.IGNORECASE,
            )

            line_numbers = [
                str(line_number)
                for line_number, line
                in enumerate(
                    lines,
                    start=1,
                )
                if pattern.search(line)
            ]

            if line_numbers:
                references[
                    table_name
                ].append(
                    (
                        f"{relative_path}:"
                        + ",".join(
                            line_numbers[:25]
                        )
                    )
                )

    return references


def build_audit(
    database_path: Path,
) -> DatabaseAudit:
    connection = connect_read_only(
        database_path
    )

    try:
        schema_rows = list(
            connection.execute(
                """
                SELECT
                    type,
                    name,
                    tbl_name,
                    sql
                FROM sqlite_master
                WHERE
                    name NOT LIKE 'sqlite_%'
                ORDER BY
                    type,
                    name
                """
            ).fetchall()
        )

        table_rows = [
            row
            for row in schema_rows
            if row["type"] == "table"
        ]

        table_names = [
            str(row["name"])
            for row in table_rows
        ]

        source_references = (
            collect_source_references(
                table_names
            )
        )

        foreign_keys_by_table = {
            table_name: inspect_foreign_keys(
                connection,
                table_name,
            )
            for table_name in table_names
        }

        referenced_by_map: dict[
            str,
            set[str],
        ] = {
            table_name: set()
            for table_name in table_names
        }

        for (
            source_table,
            foreign_keys,
        ) in foreign_keys_by_table.items():
            for foreign_key in foreign_keys:
                referenced_by_map.setdefault(
                    foreign_key.referenced_table,
                    set(),
                ).add(source_table)

        warnings: list[str] = []
        tables: list[TableSpec] = []

        for table_row in table_rows:
            table_name = str(
                table_row["name"]
            )

            try:
                count_row = connection.execute(
                    (
                        f"SELECT COUNT(*) "
                        f"AS row_count "
                        f"FROM "
                        f"{quote_identifier(table_name)}"
                    )
                ).fetchone()

                row_count = int(
                    count_row["row_count"]
                )

            except sqlite3.Error as error:
                row_count = -1

                warnings.append(
                    (
                        f"Unable to count rows "
                        f"in {table_name}: "
                        f"{error}"
                    )
                )

            tables.append(
                TableSpec(
                    name=table_name,
                    sql=table_row["sql"],
                    row_count=row_count,
                    columns=inspect_columns(
                        connection,
                        table_name,
                    ),
                    foreign_keys=(
                        foreign_keys_by_table[
                            table_name
                        ]
                    ),
                    indexes=inspect_indexes(
                        connection,
                        table_name,
                    ),
                    referenced_by=sorted(
                        referenced_by_map.get(
                            table_name,
                            set(),
                        )
                    ),
                    source_references=sorted(
                        source_references.get(
                            table_name,
                            [],
                        )
                    ),
                )
            )

        views = [
            SchemaObjectSpec(
                object_type="view",
                name=str(row["name"]),
                table_name=str(
                    row["tbl_name"]
                ),
                sql=row["sql"],
            )
            for row in schema_rows
            if row["type"] == "view"
        ]

        triggers = [
            SchemaObjectSpec(
                object_type="trigger",
                name=str(row["name"]),
                table_name=str(
                    row["tbl_name"]
                ),
                sql=row["sql"],
            )
            for row in schema_rows
            if row["type"] == "trigger"
        ]

        sqlite_version = str(
            connection.execute(
                "SELECT sqlite_version()"
            ).fetchone()[0]
        )

        journal_mode = str(
            connection.execute(
                "PRAGMA journal_mode"
            ).fetchone()[0]
        )

        foreign_keys_enabled = bool(
            connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]
        )

        integrity_check = str(
            connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
        )

        if integrity_check.lower() != "ok":
            warnings.append(
                (
                    "SQLite integrity check "
                    f"returned: {integrity_check}"
                )
            )

        index_count = sum(
            len(table.indexes)
            for table in tables
        )

        return DatabaseAudit(
            generated_at_utc=utc_now_iso(),
            project_root=str(PROJECT_ROOT),
            database_path=str(
                database_path.resolve()
            ),
            sqlite_version=sqlite_version,
            journal_mode=journal_mode,
            foreign_keys_enabled=(
                foreign_keys_enabled
            ),
            integrity_check=integrity_check,
            table_count=len(tables),
            view_count=len(views),
            trigger_count=len(triggers),
            index_count=index_count,
            tables=tables,
            views=views,
            triggers=triggers,
            warnings=warnings,
        )

    finally:
        connection.close()


def markdown_escape(
    value: Any,
) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def render_markdown(
    audit: DatabaseAudit,
) -> str:
    lines: list[str] = [
        "# Database Schema Specification v1.0",
        "",
        "## Audit Summary",
        "",
        (
            f"- Generated: "
            f"`{audit.generated_at_utc}`"
        ),
        (
            f"- Database: "
            f"`{audit.database_path}`"
        ),
        (
            f"- SQLite version: "
            f"`{audit.sqlite_version}`"
        ),
        (
            f"- Journal mode: "
            f"`{audit.journal_mode}`"
        ),
        (
            f"- Foreign keys enabled: "
            f"`{audit.foreign_keys_enabled}`"
        ),
        (
            f"- Integrity check: "
            f"`{audit.integrity_check}`"
        ),
        f"- Tables: `{audit.table_count}`",
        f"- Views: `{audit.view_count}`",
        f"- Triggers: `{audit.trigger_count}`",
        f"- Indexes: `{audit.index_count}`",
        "",
        "## Repository Planning Matrix",
        "",
        (
            "| Table | Rows | Primary Key | "
            "Foreign Keys | Source References |"
        ),
        "|---|---:|---|---:|---:|",
    ]

    for table in audit.tables:
        primary_key = ", ".join(
            column.name
            for column in sorted(
                table.columns,
                key=lambda item: (
                    item.primary_key_position
                ),
            )
            if column.primary_key_position > 0
        ) or "—"

        lines.append(
            (
                f"| {markdown_escape(table.name)} "
                f"| {table.row_count} "
                f"| {markdown_escape(primary_key)} "
                f"| {len(table.foreign_keys)} "
                f"| {len(table.source_references)} |"
            )
        )

    lines.extend(
        [
            "",
            "## Tables",
            "",
        ]
    )

    for table in audit.tables:
        lines.extend(
            [
                f"### `{table.name}`",
                "",
                (
                    f"- Row count: "
                    f"`{table.row_count}`"
                ),
                (
                    "- Referenced by: "
                    + (
                        ", ".join(
                            f"`{name}`"
                            for name
                            in table.referenced_by
                        )
                        if table.referenced_by
                        else "None detected"
                    )
                ),
                "",
                "#### Columns",
                "",
                (
                    "| Position | Name | "
                    "Declared type | Not null | "
                    "Default | PK position |"
                ),
                "|---:|---|---|---|---|---:|",
            ]
        )

        for column in table.columns:
            lines.append(
                (
                    f"| {column.cid} "
                    f"| {markdown_escape(column.name)} "
                    f"| {markdown_escape(column.declared_type or '—')} "
                    f"| {column.not_null} "
                    f"| {markdown_escape(column.default_value or '—')} "
                    f"| {column.primary_key_position} |"
                )
            )

        lines.extend(
            [
                "",
                "#### Foreign Keys",
                "",
            ]
        )

        if table.foreign_keys:
            lines.extend(
                [
                    (
                        "| From | Referenced table | "
                        "To | On update | On delete | Match |"
                    ),
                    "|---|---|---|---|---|---|",
                ]
            )

            for key in table.foreign_keys:
                lines.append(
                    (
                        f"| {markdown_escape(key.from_column)} "
                        f"| {markdown_escape(key.referenced_table)} "
                        f"| {markdown_escape(key.to_column or '—')} "
                        f"| {markdown_escape(key.on_update)} "
                        f"| {markdown_escape(key.on_delete)} "
                        f"| {markdown_escape(key.match)} |"
                    )
                )

        else:
            lines.append("None.")

        lines.extend(
            [
                "",
                "#### Indexes",
                "",
            ]
        )

        if table.indexes:
            lines.extend(
                [
                    (
                        "| Name | Unique | Origin | "
                        "Partial | Columns |"
                    ),
                    "|---|---|---|---|---|",
                ]
            )

            for index in table.indexes:
                column_names = ", ".join(
                    (
                        index_column.column_name
                        or (
                            "expression:"
                            f"{index_column.column_id}"
                        )
                    )
                    for index_column
                    in index.columns
                ) or "—"

                lines.append(
                    (
                        f"| {markdown_escape(index.name)} "
                        f"| {index.unique} "
                        f"| {markdown_escape(index.origin)} "
                        f"| {index.partial} "
                        f"| {markdown_escape(column_names)} |"
                    )
                )

        else:
            lines.append("None.")

        lines.extend(
            [
                "",
                "#### Source References",
                "",
            ]
        )

        if table.source_references:
            for reference in table.source_references:
                lines.append(
                    f"- `{reference}`"
                )

        else:
            lines.append(
                (
                    "No direct table-name references "
                    "were detected under `src/`."
                )
            )

        lines.extend(
            [
                "",
                "#### Create SQL",
                "",
                "```sql",
                table.sql or "-- SQL unavailable",
                "```",
                "",
            ]
        )

    if audit.views:
        lines.extend(
            [
                "## Views",
                "",
            ]
        )

        for view in audit.views:
            lines.extend(
                [
                    f"### `{view.name}`",
                    "",
                    "```sql",
                    view.sql or "-- SQL unavailable",
                    "```",
                    "",
                ]
            )

    if audit.triggers:
        lines.extend(
            [
                "## Triggers",
                "",
            ]
        )

        for trigger in audit.triggers:
            lines.extend(
                [
                    f"### `{trigger.name}`",
                    "",
                    (
                        f"- Table: "
                        f"`{trigger.table_name}`"
                    ),
                    "",
                    "```sql",
                    trigger.sql or "-- SQL unavailable",
                    "```",
                    "",
                ]
            )

    if audit.warnings:
        lines.extend(
            [
                "## Warnings",
                "",
            ]
        )

        for warning in audit.warnings:
            lines.append(
                f"- {warning}"
            )

        lines.append("")

    lines.extend(
        [
            "## Repository Implementation Gate",
            "",
            (
                "Repository classes must be generated "
                "from this specification rather than "
                "from assumed table or column names."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def write_outputs(
    audit: DatabaseAudit,
    markdown_output: Path,
    json_output: Path,
) -> None:
    markdown_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    markdown_output.write_text(
        render_markdown(audit),
        encoding="utf-8",
    )

    json_output.write_text(
        json.dumps(
            asdict(audit),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the Polymarket Intelligence "
            "Platform SQLite database schema."
        )
    )

    parser.add_argument(
        "--database",
        type=Path,
        help=(
            "Optional explicit SQLite path. "
            "Normally loaded from config."
        ),
    )

    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=DEFAULT_MARKDOWN_OUTPUT,
    )

    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_OUTPUT,
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    database_path = (
        arguments.database
        if arguments.database is not None
        else load_database_path_from_config()
    )

    if not database_path.is_absolute():
        database_path = (
            PROJECT_ROOT
            / database_path
        )

    audit = build_audit(
        database_path
    )

    write_outputs(
        audit,
        arguments.markdown_output,
        arguments.json_output,
    )

    print("=" * 72)
    print("POLYMARKET INTELLIGENCE PLATFORM")
    print("DATABASE SCHEMA AUDIT")
    print("=" * 72)
    print(f"Database: {audit.database_path}")
    print(f"Tables: {audit.table_count}")
    print(f"Views: {audit.view_count}")
    print(f"Triggers: {audit.trigger_count}")
    print(f"Indexes: {audit.index_count}")
    print(
        f"Integrity check: "
        f"{audit.integrity_check}"
    )
    print(
        f"Markdown output: "
        f"{arguments.markdown_output}"
    )
    print(
        f"JSON output: "
        f"{arguments.json_output}"
    )

    if audit.warnings:
        print("")
        print("Warnings:")

        for warning in audit.warnings:
            print(f"  - {warning}")

    print("")
    print("Status: PASSED")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())