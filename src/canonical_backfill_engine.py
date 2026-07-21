from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from data_access import DATABASE_PATH
except ImportError:
    from src.data_access import DATABASE_PATH


LOGGER = logging.getLogger(__name__)

BUSY_TIMEOUT_MS = 30_000

RUNS_TABLE = "canonical_backfill_runs"
AUDIT_TABLE = "canonical_backfill_audit"

CANONICAL_TABLE = "canonical_market_identities"
LEGACY_TABLE = "gamma_markets"

MARKET_ID_CANDIDATES = (
    "canonical_market_id",
    "condition_id",
    "market_id",
    "market_condition_id",
    "conditionId",
)

FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "canonical_market_id": (
        "canonical_market_id",
        "condition_id",
        "market_id",
        "market_condition_id",
        "conditionId",
    ),
    "condition_id": (
        "condition_id",
        "canonical_market_id",
        "market_id",
        "market_condition_id",
        "conditionId",
    ),
    "market_id": (
        "market_id",
        "condition_id",
        "canonical_market_id",
        "market_condition_id",
        "conditionId",
    ),
    "title": (
        "title",
        "question",
        "market_title",
        "name",
    ),
    "question": (
        "question",
        "title",
        "market_title",
        "name",
    ),
    "slug": (
        "slug",
        "market_slug",
    ),
    "event_slug": (
        "event_slug",
        "eventSlug",
    ),
    "event_id": (
        "event_id",
        "eventId",
    ),
    "category": (
        "category",
        "market_category",
    ),
    "market_type": (
        "market_type",
        "type",
        "category",
    ),
    "active": (
        "active",
        "is_active",
    ),
    "closed": (
        "closed",
        "is_closed",
    ),
    "archived": (
        "archived",
        "is_archived",
    ),
    "restricted": (
        "restricted",
        "is_restricted",
    ),
    "accepting_orders": (
        "accepting_orders",
        "acceptingOrders",
        "is_accepting_orders",
    ),
    "tradable_identity": (
        "tradable_identity",
    ),
    "polymarket_url": (
        "polymarket_url",
        "url",
        "market_url",
    ),
    "url": (
        "url",
        "polymarket_url",
        "market_url",
    ),
    "end_date": (
        "end_date",
        "endDate",
        "end_time",
        "endTime",
    ),
    "start_date": (
        "start_date",
        "startDate",
        "start_time",
        "startTime",
    ),
    "created_at": (
        "created_at",
        "createdAt",
    ),
    "updated_at": (
        "updated_at",
        "updatedAt",
        "modified_at",
        "synced_at",
    ),
    "source": (
        "source",
    ),
    "source_table": (
        "source_table",
    ),
    "raw_json": (
        "raw_json",
        "metadata_json",
        "payload_json",
    ),
    "metadata_json": (
        "metadata_json",
        "raw_json",
        "payload_json",
    ),
}

INTEGER_BOOLEAN_FIELDS = {
    "active",
    "closed",
    "archived",
    "restricted",
    "accepting_orders",
    "tradable_identity",
}


def configure_utf8() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_market_id(value: Any) -> str:
    return clean_text(value).lower()


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def first_existing(
    columns: set[str],
    candidates: Sequence[str],
) -> str | None:
    return next((candidate for candidate in candidates if candidate in columns), None)


def bool_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(bool(value))

    normalized = clean_text(value).lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return 1
    if normalized in {"0", "false", "no", "n", "off", ""}:
        return 0
    return default


@dataclass(slots=True)
class ColumnInfo:
    cid: int
    name: str
    declared_type: str
    not_null: int
    default_value: Any
    primary_key: int


@dataclass(slots=True)
class FieldMapping:
    target_column: str
    source_column: str | None
    transform: str
    required: int
    has_default: int
    ready: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BackfillCandidate:
    market_id: str
    title: str
    active: int
    closed: int
    archived: int
    restricted: int
    accepting_orders: int
    tradable_identity: int
    source_rowid: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CanonicalBackfillEngine:
    """
    Backfills legacy-only Gamma markets into canonical_market_identities.

    Safety rules:
      - dry-run is the default
      - canonical records are never overwritten
      - inserts occur only for IDs absent from the canonical table
      - APPLY is blocked when required canonical columns cannot be populated
      - tradable_identity = active AND NOT closed AND NOT archived
      - restricted remains metadata and does not determine tradability
    """

    def __init__(
        self,
        database_path: Path | str = DATABASE_PATH,
    ) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        return connection

    def table_exists(self, table_name: str) -> bool:
        connection = self.connect()
        try:
            row = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type='table' AND name=?
                LIMIT 1
                """,
                (table_name,),
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    def table_info(self, table_name: str) -> list[ColumnInfo]:
        if not self.table_exists(table_name):
            raise RuntimeError(f"Required table is missing: {table_name}")

        connection = self.connect()
        try:
            rows = connection.execute(
                f"PRAGMA table_info({quote_identifier(table_name)})"
            ).fetchall()
        finally:
            connection.close()

        return [
            ColumnInfo(
                cid=int(row["cid"]),
                name=clean_text(row["name"]),
                declared_type=clean_text(row["type"]),
                not_null=int(row["notnull"] or 0),
                default_value=row["dflt_value"],
                primary_key=int(row["pk"] or 0),
            )
            for row in rows
        ]

    def create_tables(self) -> None:
        connection = self.connect()
        try:
            connection.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_identifier(RUNS_TABLE)} (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    elapsed_seconds REAL,
                    mode TEXT NOT NULL,
                    canonical_before INTEGER NOT NULL DEFAULT 0,
                    legacy_total INTEGER NOT NULL DEFAULT 0,
                    candidate_count INTEGER NOT NULL DEFAULT 0,
                    inserted_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    unresolved_required_columns INTEGER NOT NULL DEFAULT 0,
                    mapping_json TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(AUDIT_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    title TEXT,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    source_rowid INTEGER,
                    active INTEGER NOT NULL DEFAULT 0,
                    closed INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    restricted INTEGER NOT NULL DEFAULT 0,
                    accepting_orders INTEGER NOT NULL DEFAULT 0,
                    tradable_identity INTEGER NOT NULL DEFAULT 0,
                    audited_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS
                idx_canonical_backfill_audit_market
                ON {quote_identifier(AUDIT_TABLE)}(
                    market_id,
                    audited_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_canonical_backfill_audit_status
                ON {quote_identifier(AUDIT_TABLE)}(
                    status,
                    audited_at DESC
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

    def resolve_id_columns(self) -> tuple[str, str]:
        canonical_columns = {column.name for column in self.table_info(CANONICAL_TABLE)}
        legacy_columns = {column.name for column in self.table_info(LEGACY_TABLE)}

        canonical_id = first_existing(canonical_columns, MARKET_ID_CANDIDATES)
        legacy_id = first_existing(legacy_columns, MARKET_ID_CANDIDATES)

        if not canonical_id:
            raise RuntimeError(
                f"{CANONICAL_TABLE} has no recognized market identifier column."
            )
        if not legacy_id:
            raise RuntimeError(
                f"{LEGACY_TABLE} has no recognized market identifier column."
            )

        return canonical_id, legacy_id

    def build_mapping(self) -> list[FieldMapping]:
        canonical_info = self.table_info(CANONICAL_TABLE)
        legacy_columns = {column.name for column in self.table_info(LEGACY_TABLE)}

        mappings: list[FieldMapping] = []

        for target in canonical_info:
            candidates = FIELD_CANDIDATES.get(
                target.name,
                (target.name,),
            )
            source_column = first_existing(legacy_columns, candidates)

            required = int(
                target.not_null == 1
                and target.default_value is None
                and target.primary_key == 0
            )
            has_default = int(target.default_value is not None)

            if target.name == "tradable_identity":
                mappings.append(
                    FieldMapping(
                        target_column=target.name,
                        source_column=None,
                        transform="DERIVED_TRADABLE",
                        required=required,
                        has_default=has_default,
                        ready=1,
                        reason=(
                            "Derived from active, closed, and archived."
                        ),
                    )
                )
                continue

            if target.name == "source":
                mappings.append(
                    FieldMapping(
                        target_column=target.name,
                        source_column=None,
                        transform="CONSTANT_GAMMA_BACKFILL",
                        required=required,
                        has_default=has_default,
                        ready=1,
                        reason="Set to GAMMA_BACKFILL.",
                    )
                )
                continue

            if target.name == "source_table":
                mappings.append(
                    FieldMapping(
                        target_column=target.name,
                        source_column=None,
                        transform="CONSTANT_GAMMA_MARKETS",
                        required=required,
                        has_default=has_default,
                        ready=1,
                        reason="Set to gamma_markets.",
                    )
                )
                continue

            if target.name in {
                "created_at",
                "updated_at",
                "first_built_at",
                "last_built_at",
            } and not source_column:
                mappings.append(
                    FieldMapping(
                        target_column=target.name,
                        source_column=None,
                        transform="CURRENT_TIMESTAMP",
                        required=required,
                        has_default=has_default,
                        ready=1,
                        reason="Set to the current UTC timestamp.",
                    )
                )
                continue

            if source_column:
                transform = (
                    "BOOLEAN_INTEGER"
                    if target.name in INTEGER_BOOLEAN_FIELDS
                    else "DIRECT"
                )
                mappings.append(
                    FieldMapping(
                        target_column=target.name,
                        source_column=source_column,
                        transform=transform,
                        required=required,
                        has_default=has_default,
                        ready=1,
                        reason=f"Mapped from {LEGACY_TABLE}.{source_column}.",
                    )
                )
                continue

            if target.primary_key and "INT" in target.declared_type.upper():
                mappings.append(
                    FieldMapping(
                        target_column=target.name,
                        source_column=None,
                        transform="SQLITE_AUTOINCREMENT",
                        required=0,
                        has_default=1,
                        ready=1,
                        reason="Integer primary key is generated by SQLite.",
                    )
                )
                continue

            if has_default or not required:
                mappings.append(
                    FieldMapping(
                        target_column=target.name,
                        source_column=None,
                        transform="OMIT_USE_DEFAULT_OR_NULL",
                        required=required,
                        has_default=has_default,
                        ready=1,
                        reason=(
                            "Column may be omitted because it is nullable "
                            "or has a database default."
                        ),
                    )
                )
                continue

            mappings.append(
                FieldMapping(
                    target_column=target.name,
                    source_column=None,
                    transform="UNRESOLVED_REQUIRED",
                    required=1,
                    has_default=0,
                    ready=0,
                    reason=(
                        "Required canonical column has no compatible Gamma "
                        "source and no database default."
                    ),
                )
            )

        return mappings

    def load_candidates(
        self,
        *,
        limit: int | None = None,
    ) -> list[BackfillCandidate]:
        canonical_id, legacy_id = self.resolve_id_columns()

        legacy_columns = {column.name for column in self.table_info(LEGACY_TABLE)}

        def source_expr(
            candidates: Sequence[str],
            alias: str,
            fallback: str = "NULL",
        ) -> str:
            column = first_existing(legacy_columns, candidates)
            if column:
                return f"g.{quote_identifier(column)} AS {quote_identifier(alias)}"
            return f"{fallback} AS {quote_identifier(alias)}"

        select_parts = [
            "g.rowid AS source_rowid",
            f"g.{quote_identifier(legacy_id)} AS market_id",
            source_expr(FIELD_CANDIDATES["title"], "title"),
            source_expr(FIELD_CANDIDATES["active"], "active", "0"),
            source_expr(FIELD_CANDIDATES["closed"], "closed", "0"),
            source_expr(FIELD_CANDIDATES["archived"], "archived", "0"),
            source_expr(FIELD_CANDIDATES["restricted"], "restricted", "0"),
            source_expr(
                FIELD_CANDIDATES["accepting_orders"],
                "accepting_orders",
                "0",
            ),
        ]

        sql = f"""
            SELECT
                {", ".join(select_parts)}
            FROM {quote_identifier(LEGACY_TABLE)} AS g
            LEFT JOIN {quote_identifier(CANONICAL_TABLE)} AS c
                ON LOWER(c.{quote_identifier(canonical_id)})
                 = LOWER(g.{quote_identifier(legacy_id)})
            WHERE c.{quote_identifier(canonical_id)} IS NULL
              AND g.{quote_identifier(legacy_id)} IS NOT NULL
              AND TRIM(CAST(g.{quote_identifier(legacy_id)} AS TEXT)) <> ''
            ORDER BY g.rowid
        """

        parameters: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            parameters = (max(0, int(limit)),)

        connection = self.connect()
        try:
            rows = connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

        candidates: list[BackfillCandidate] = []
        for row in rows:
            active = bool_int(row["active"])
            closed = bool_int(row["closed"])
            archived = bool_int(row["archived"])
            restricted = bool_int(row["restricted"])
            accepting_orders = bool_int(row["accepting_orders"])
            tradable_identity = int(
                active == 1
                and closed == 0
                and archived == 0
            )

            candidates.append(
                BackfillCandidate(
                    market_id=normalize_market_id(row["market_id"]),
                    title=clean_text(row["title"]),
                    active=active,
                    closed=closed,
                    archived=archived,
                    restricted=restricted,
                    accepting_orders=accepting_orders,
                    tradable_identity=tradable_identity,
                    source_rowid=(
                        int(row["source_rowid"])
                        if row["source_rowid"] is not None
                        else None
                    ),
                )
            )

        return candidates

    def count_rows(self, table_name: str) -> int:
        connection = self.connect()
        try:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {quote_identifier(table_name)}"
            ).fetchone()
            return int(row["count"])
        finally:
            connection.close()

    def _build_insert_spec(
        self,
        mappings: Sequence[FieldMapping],
    ) -> tuple[list[str], list[str]]:
        target_columns: list[str] = []
        source_expressions: list[str] = []

        legacy_columns = {column.name for column in self.table_info(LEGACY_TABLE)}

        def gamma_boolean(column_name: str | None) -> str:
            if not column_name:
                return "0"
            quoted = f"g.{quote_identifier(column_name)}"
            return (
                "CASE "
                f"WHEN LOWER(TRIM(CAST({quoted} AS TEXT))) "
                "IN ('1','true','yes','y','on') THEN 1 "
                "ELSE 0 END"
            )

        active_source = first_existing(
            legacy_columns,
            FIELD_CANDIDATES["active"],
        )
        closed_source = first_existing(
            legacy_columns,
            FIELD_CANDIDATES["closed"],
        )
        archived_source = first_existing(
            legacy_columns,
            FIELD_CANDIDATES["archived"],
        )

        for mapping in mappings:
            if not mapping.ready:
                continue

            if mapping.transform in {
                "SQLITE_AUTOINCREMENT",
                "OMIT_USE_DEFAULT_OR_NULL",
            }:
                continue

            target_columns.append(mapping.target_column)

            if mapping.transform == "DIRECT":
                source_expressions.append(
                    f"g.{quote_identifier(clean_text(mapping.source_column))}"
                )
            elif mapping.transform == "BOOLEAN_INTEGER":
                source_expressions.append(
                    gamma_boolean(mapping.source_column)
                )
            elif mapping.transform == "DERIVED_TRADABLE":
                source_expressions.append(
                    "("
                    f"{gamma_boolean(active_source)} = 1 "
                    f"AND {gamma_boolean(closed_source)} = 0 "
                    f"AND {gamma_boolean(archived_source)} = 0"
                    ")"
                )
            elif mapping.transform == "CONSTANT_GAMMA_BACKFILL":
                source_expressions.append("'GAMMA_BACKFILL'")
            elif mapping.transform == "CONSTANT_GAMMA_MARKETS":
                source_expressions.append("'gamma_markets'")
            elif mapping.transform == "CURRENT_TIMESTAMP":
                source_expressions.append(f"'{utc_now_iso()}'")
            else:
                raise RuntimeError(
                    f"Unsupported mapping transform: {mapping.transform}"
                )

        return target_columns, source_expressions

    def apply_backfill(
        self,
        mappings: Sequence[FieldMapping],
        *,
        limit: int | None = None,
    ) -> int:
        unresolved = [mapping for mapping in mappings if not mapping.ready]
        if unresolved:
            names = ", ".join(mapping.target_column for mapping in unresolved)
            raise RuntimeError(
                "Backfill blocked because required canonical columns are "
                f"unresolved: {names}"
            )

        canonical_id, legacy_id = self.resolve_id_columns()
        target_columns, source_expressions = self._build_insert_spec(mappings)

        if canonical_id not in target_columns:
            raise RuntimeError(
                f"Insert mapping does not populate canonical ID column: {canonical_id}"
            )

        source_sql = f"""
            SELECT
                {", ".join(source_expressions)}
            FROM {quote_identifier(LEGACY_TABLE)} AS g
            LEFT JOIN {quote_identifier(CANONICAL_TABLE)} AS c
                ON LOWER(c.{quote_identifier(canonical_id)})
                 = LOWER(g.{quote_identifier(legacy_id)})
            WHERE c.{quote_identifier(canonical_id)} IS NULL
              AND g.{quote_identifier(legacy_id)} IS NOT NULL
              AND TRIM(CAST(g.{quote_identifier(legacy_id)} AS TEXT)) <> ''
            ORDER BY g.rowid
        """

        if limit is not None:
            source_sql += f" LIMIT {max(0, int(limit))}"

        sql = f"""
            INSERT INTO {quote_identifier(CANONICAL_TABLE)} (
                {", ".join(quote_identifier(column) for column in target_columns)}
            )
            {source_sql}
        """

        connection = self.connect()
        try:
            before = connection.total_changes
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(sql)
            inserted = connection.total_changes - before
            connection.commit()
            return int(inserted)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def persist_audit(
        self,
        run_id: str,
        candidates: Sequence[BackfillCandidate],
        *,
        inserted_market_ids: set[str],
    ) -> None:
        audited_at = utc_now_iso()
        rows = []

        for candidate in candidates:
            inserted = candidate.market_id in inserted_market_ids
            rows.append(
                (
                    run_id,
                    candidate.market_id,
                    candidate.title,
                    "INSERT_CANONICAL_IDENTITY",
                    "INSERTED" if inserted else "CANDIDATE",
                    (
                        "CANONICAL_BACKFILL_INSERTED"
                        if inserted
                        else "LEGACY_ONLY_CANDIDATE"
                    ),
                    (
                        "Inserted from gamma_markets."
                        if inserted
                        else (
                            "Market exists in gamma_markets but is absent "
                            "from canonical_market_identities."
                        )
                    ),
                    candidate.source_rowid,
                    candidate.active,
                    candidate.closed,
                    candidate.archived,
                    candidate.restricted,
                    candidate.accepting_orders,
                    candidate.tradable_identity,
                    audited_at,
                )
            )

        connection = self.connect()
        try:
            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(AUDIT_TABLE)} (
                    run_id,
                    market_id,
                    title,
                    action,
                    status,
                    reason_code,
                    reason_detail,
                    source_rowid,
                    active,
                    closed,
                    archived,
                    restricted,
                    accepting_orders,
                    tradable_identity,
                    audited_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()
        finally:
            connection.close()

    def run(
        self,
        *,
        apply: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]:
        self.create_tables()

        run_id = uuid.uuid4().hex
        started = utc_now()
        mode = "APPLY" if apply else "DRY RUN"

        canonical_before = self.count_rows(CANONICAL_TABLE)
        legacy_total = self.count_rows(LEGACY_TABLE)
        mappings = self.build_mapping()
        unresolved = [mapping for mapping in mappings if not mapping.ready]
        candidates = self.load_candidates(limit=limit)

        connection = self.connect()
        try:
            connection.execute(
                f"""
                INSERT INTO {quote_identifier(RUNS_TABLE)} (
                    run_id,
                    started_at,
                    mode,
                    canonical_before,
                    legacy_total,
                    candidate_count,
                    unresolved_required_columns,
                    mapping_json,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    started.isoformat(),
                    mode,
                    canonical_before,
                    legacy_total,
                    len(candidates),
                    len(unresolved),
                    stable_json([mapping.to_dict() for mapping in mappings]),
                    "RUNNING",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        inserted_count = 0
        status = "SUCCESS"
        error_message = ""
        inserted_market_ids: set[str] = set()

        try:
            if apply:
                if unresolved:
                    names = ", ".join(
                        mapping.target_column for mapping in unresolved
                    )
                    raise RuntimeError(
                        "APPLY blocked. Unresolved required canonical columns: "
                        f"{names}"
                    )

                before_ids = {candidate.market_id for candidate in candidates}
                inserted_count = self.apply_backfill(
                    mappings,
                    limit=limit,
                )

                canonical_id, _ = self.resolve_id_columns()
                connection = self.connect()
                try:
                    placeholders = ",".join("?" for _ in before_ids)
                    if before_ids:
                        rows = connection.execute(
                            f"""
                            SELECT LOWER({quote_identifier(canonical_id)}) AS market_id
                            FROM {quote_identifier(CANONICAL_TABLE)}
                            WHERE LOWER({quote_identifier(canonical_id)})
                            IN ({placeholders})
                            """,
                            tuple(sorted(before_ids)),
                        ).fetchall()
                        inserted_market_ids = {
                            normalize_market_id(row["market_id"])
                            for row in rows
                        }
                finally:
                    connection.close()

                self.persist_audit(
                    run_id,
                    candidates,
                    inserted_market_ids=inserted_market_ids,
                )

        except Exception as exc:
            status = "FAILED"
            error_message = str(exc)
            raise

        finally:
            finished = utc_now()
            elapsed_seconds = (finished - started).total_seconds()

            connection = self.connect()
            try:
                connection.execute(
                    f"""
                    UPDATE {quote_identifier(RUNS_TABLE)}
                    SET
                        finished_at=?,
                        elapsed_seconds=?,
                        inserted_count=?,
                        skipped_count=?,
                        status=?,
                        error_message=?
                    WHERE run_id=?
                    """,
                    (
                        finished.isoformat(),
                        elapsed_seconds,
                        inserted_count,
                        max(0, len(candidates) - inserted_count),
                        status,
                        error_message or None,
                        run_id,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

        return {
            "run_id": run_id,
            "database_path": str(self.database_path),
            "mode": mode,
            "canonical_before": canonical_before,
            "legacy_total": legacy_total,
            "candidate_count": len(candidates),
            "inserted_count": inserted_count,
            "unresolved_required_columns": unresolved,
            "mappings": mappings,
            "candidates": candidates,
            "elapsed_seconds": elapsed_seconds,
            "status": status,
        }


def print_report(
    report: Mapping[str, Any],
    *,
    preview_limit: int,
) -> None:
    print()
    print("=" * 118)
    print("CANONICAL BACKFILL ENGINE")
    print("=" * 118)
    print(f"{'Database:':34} {report['database_path']}")
    print(f"{'Mode:':34} {report['mode']}")
    print(f"{'Run ID:':34} {report['run_id']}")
    print(f"{'Canonical rows before:':34} {report['canonical_before']}")
    print(f"{'Legacy Gamma rows:':34} {report['legacy_total']}")
    print(f"{'Backfill candidates:':34} {report['candidate_count']}")
    print(f"{'Rows inserted:':34} {report['inserted_count']}")
    print(
        f"{'Unresolved required columns:':34} "
        f"{len(report['unresolved_required_columns'])}"
    )
    print(f"{'Duration:':34} {report['elapsed_seconds']:.3f}s")
    print(f"{'Status:':34} {report['status']}")

    print()
    print("SCHEMA MAPPING")
    print("-" * 118)
    for mapping in report["mappings"]:
        source = mapping.source_column or "-"
        readiness = "READY" if mapping.ready else "BLOCKED"
        print(
            f"{mapping.target_column:<32} "
            f"{source:<32} "
            f"{mapping.transform:<28} "
            f"{readiness}"
        )

    print()
    print("UNRESOLVED REQUIRED COLUMNS")
    print("-" * 118)
    unresolved: list[FieldMapping] = list(
        report["unresolved_required_columns"]
    )
    if not unresolved:
        print("None. The schema is ready for backfill.")
    else:
        for mapping in unresolved:
            print(
                f"{mapping.target_column}: {mapping.reason}"
            )

    print()
    print("BACKFILL PREVIEW")
    print("-" * 118)
    candidates: list[BackfillCandidate] = list(report["candidates"])
    if not candidates:
        print("No legacy-only markets require canonical backfill.")
    else:
        for candidate in candidates[:preview_limit]:
            print(
                f"{candidate.market_id} | "
                f"tradable={candidate.tradable_identity} | "
                f"{candidate.title or 'UNKNOWN TITLE'}"
            )
            print(
                f"    active={candidate.active} "
                f"closed={candidate.closed} "
                f"archived={candidate.archived} "
                f"restricted={candidate.restricted} "
                f"accepting_orders={candidate.accepting_orders}"
            )

    print("=" * 118)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill Gamma-only markets into canonical_market_identities "
            "using schema-aware, canonical-safe inserts."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Insert validated legacy-only markets into the canonical table. "
            "Dry run is the default."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        help=(
            "Limit the number of candidates processed. Useful for a small "
            "test backfill before the full run."
        ),
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=25,
        help="Maximum candidate rows to print. Default: 25.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def main() -> None:
    configure_utf8()
    args = parse_args()
    configure_logging(args.verbose)

    engine = CanonicalBackfillEngine()
    report = engine.run(
        apply=args.apply,
        limit=args.limit,
    )
    print_report(
        report,
        preview_limit=max(1, args.preview_limit),
    )


if __name__ == "__main__":
    main()