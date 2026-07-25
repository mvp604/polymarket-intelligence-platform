from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TableAdapter:
    table_name: str
    columns: frozenset[str]

    def has(self, column: str) -> bool:
        return column in self.columns

    def first_available(self, *candidates: str) -> str | None:
        for candidate in candidates:
            if candidate in self.columns:
                return candidate
        return None


def adapter_from_report(
    report: dict[str, Any],
    table_name: str,
) -> TableAdapter:
    table = report.get("tables", {}).get(table_name)
    columns = frozenset(
        column["name"] for column in table.get("columns", [])
    ) if table else frozenset()
    return TableAdapter(table_name=table_name, columns=columns)


def migration_adapter(report: dict[str, Any]) -> dict[str, str | None]:
    table = adapter_from_report(report, "schema_migrations")
    return {
        "id": table.first_available(
            "migration_id", "version", "name", "filename", "id"
        ),
        "checksum": table.first_available(
            "checksum", "sha256", "hash", "file_hash"
        ),
        "status": table.first_available(
            "status", "state", "result", "success"
        ),
        "applied_at": table.first_available(
            "applied_at", "executed_at", "created_at", "run_at"
        ),
    }


def event_consumer_adapter(
    report: dict[str, Any],
) -> dict[str, str | None]:
    table = adapter_from_report(report, "event_consumers")
    return {
        "name": table.first_available(
            "consumer_name", "name", "consumer", "id"
        ),
        "enabled": table.first_available(
            "enabled", "is_enabled", "active", "is_active"
        ),
        "last_run": table.first_available(
            "last_run_at", "last_run", "updated_at"
        ),
        "last_success": table.first_available(
            "last_successful_run_at",
            "last_success_at",
            "last_success",
        ),
        "last_error": table.first_available(
            "last_error", "error_message", "error"
        ),
    }
