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
    from data_access import DataAccess, DATABASE_PATH
except ImportError:
    from src.data_access import DataAccess, DATABASE_PATH

try:
    from canonical_market_repository import CanonicalMarketRepository
except ImportError:
    from src.canonical_market_repository import CanonicalMarketRepository


LOGGER = logging.getLogger(__name__)

BUSY_TIMEOUT_MS = 30_000

DEFAULT_SOURCE_TABLES = (
    "market_predictions",
    "smart_money_flow_signals",
    "market_memory_snapshots",
    "ranked_market_opportunities",
    "master_opportunities",
    "positions",
    "consensus_history",
    "institutional_consensus",
    "position_evolution",
)

CONDITION_ID_CANDIDATES = (
    "condition_id",
    "canonical_condition_id",
    "market_condition_id",
    "market_id",
    "conditionId",
)

TITLE_CANDIDATES = (
    "title",
    "question",
    "market_title",
    "name",
)

OUTCOME_CANDIDATES = (
    "outcome",
    "selected_outcome",
    "position_outcome",
)

TIMESTAMP_CANDIDATES = (
    "predicted_at",
    "observed_at",
    "snapshot_at",
    "scanned_at",
    "created_at",
    "updated_at",
    "recorded_at",
)

RUNS_TABLE = "condition_id_lineage_audit_runs"
RESULTS_TABLE = "condition_id_lineage_audit_results"


def configure_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
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


def normalize_condition_id(value: Any) -> str:
    return clean_text(value).lower()


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def first_existing(
    columns: set[str],
    candidates: Sequence[str],
) -> str | None:
    return next((candidate for candidate in candidates if candidate in columns), None)


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


@dataclass(slots=True)
class SourceOccurrence:
    table_name: str
    row_count: int
    first_seen_at: str | None
    last_seen_at: str | None
    title: str
    outcome: str


@dataclass(slots=True)
class ConditionLineage:
    condition_id: str
    canonical_found: int
    legacy_found: int
    registry_source: str
    first_source_table: str
    first_seen_at: str | None
    last_seen_at: str | None
    source_table_count: int
    total_occurrences: int
    title: str
    outcome: str
    diagnosis: str
    source_occurrences: list[SourceOccurrence]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_occurrences"] = [
            asdict(item) for item in self.source_occurrences
        ]
        return payload


class ConditionIdLineageAudit:
    def __init__(
        self,
        database_path: Path | str = DATABASE_PATH,
        *,
        include_legacy: bool = True,
    ) -> None:
        self.data = DataAccess(database_path)
        self.database_path = Path(self.data.database_path)
        self.repository = CanonicalMarketRepository(
            data_access=self.data,
            allow_legacy_fallback=include_legacy,
        )
        self.include_legacy = include_legacy
        self._columns_cache: dict[str, set[str]] = {}

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
        return self.data.table_exists(table_name)

    def table_columns(self, table_name: str) -> set[str]:
        if table_name not in self._columns_cache:
            rows = self.data.fetch_all(
                f"PRAGMA table_info({quote_identifier(table_name)})"
            )
            self._columns_cache[table_name] = {
                clean_text(row.get("name"))
                for row in rows
                if clean_text(row.get("name"))
            }
        return self._columns_cache[table_name]

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
                    target_count INTEGER NOT NULL DEFAULT 0,
                    resolved_count INTEGER NOT NULL DEFAULT 0,
                    unresolved_count INTEGER NOT NULL DEFAULT 0,
                    source_tables_checked INTEGER NOT NULL DEFAULT 0,
                    results_written INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(RESULTS_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    condition_id TEXT NOT NULL,
                    canonical_found INTEGER NOT NULL DEFAULT 0,
                    legacy_found INTEGER NOT NULL DEFAULT 0,
                    registry_source TEXT,
                    first_source_table TEXT,
                    first_seen_at TEXT,
                    last_seen_at TEXT,
                    source_table_count INTEGER NOT NULL DEFAULT 0,
                    total_occurrences INTEGER NOT NULL DEFAULT 0,
                    title TEXT,
                    outcome TEXT,
                    diagnosis TEXT NOT NULL,
                    source_occurrences_json TEXT,
                    audited_at TEXT NOT NULL,
                    UNIQUE(run_id, condition_id),
                    FOREIGN KEY(run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS
                idx_condition_lineage_results_condition
                ON {quote_identifier(RESULTS_TABLE)}(
                    condition_id,
                    audited_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_condition_lineage_results_diagnosis
                ON {quote_identifier(RESULTS_TABLE)}(
                    diagnosis,
                    audited_at DESC
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

    def _source_table_metadata(
        self,
        table_name: str,
    ) -> dict[str, str | None] | None:
        if not self.table_exists(table_name):
            return None

        columns = self.table_columns(table_name)
        condition_column = first_existing(columns, CONDITION_ID_CANDIDATES)
        if not condition_column:
            return None

        return {
            "condition_column": condition_column,
            "title_column": first_existing(columns, TITLE_CANDIDATES),
            "outcome_column": first_existing(columns, OUTCOME_CANDIDATES),
            "timestamp_column": first_existing(columns, TIMESTAMP_CANDIDATES),
        }

    def discover_source_tables(
        self,
        requested_tables: Iterable[str] | None = None,
    ) -> list[str]:
        candidates = list(requested_tables or DEFAULT_SOURCE_TABLES)
        valid_tables: list[str] = []

        for table_name in candidates:
            metadata = self._source_table_metadata(table_name)
            if metadata:
                valid_tables.append(table_name)

        return valid_tables

    def load_target_condition_ids(
        self,
        *,
        target_table: str,
        unresolved_only: bool,
        explicit_condition_ids: Iterable[str] | None = None,
    ) -> list[str]:
        if explicit_condition_ids:
            return sorted(
                {
                    normalize_condition_id(value)
                    for value in explicit_condition_ids
                    if normalize_condition_id(value)
                }
            )

        metadata = self._source_table_metadata(target_table)
        if not metadata:
            raise RuntimeError(
                f"Target table missing or lacks condition ID: {target_table}"
            )

        condition_column = clean_text(metadata["condition_column"])
        rows = self.data.fetch_all(
            f"""
            SELECT DISTINCT
                LOWER(TRIM({quote_identifier(condition_column)}))
                    AS condition_id
            FROM {quote_identifier(target_table)}
            WHERE {quote_identifier(condition_column)} IS NOT NULL
              AND TRIM({quote_identifier(condition_column)}) <> ''
            ORDER BY condition_id
            """
        )

        condition_ids = [
            normalize_condition_id(row.get("condition_id"))
            for row in rows
            if normalize_condition_id(row.get("condition_id"))
        ]

        if not unresolved_only:
            return condition_ids

        canonical = self.repository.load_all_canonical()
        legacy = (
            self.repository.load_all_legacy()
            if self.include_legacy
            else {}
        )

        return [
            condition_id
            for condition_id in condition_ids
            if condition_id not in canonical
            and condition_id not in legacy
        ]

    def _source_occurrence(
        self,
        table_name: str,
        condition_id: str,
    ) -> SourceOccurrence | None:
        metadata = self._source_table_metadata(table_name)
        if not metadata:
            return None

        condition_column = clean_text(metadata["condition_column"])
        title_column = metadata["title_column"]
        outcome_column = metadata["outcome_column"]
        timestamp_column = metadata["timestamp_column"]

        select_parts = ["COUNT(*) AS row_count"]

        if timestamp_column:
            quoted_timestamp = quote_identifier(clean_text(timestamp_column))
            select_parts.extend(
                [
                    f"MIN({quoted_timestamp}) AS first_seen_at",
                    f"MAX({quoted_timestamp}) AS last_seen_at",
                ]
            )
        else:
            select_parts.extend(
                [
                    "NULL AS first_seen_at",
                    "NULL AS last_seen_at",
                ]
            )

        row = self.data.fetch_one(
            f"""
            SELECT
                {", ".join(select_parts)}
            FROM {quote_identifier(table_name)}
            WHERE LOWER(TRIM({quote_identifier(condition_column)})) = ?
            """,
            (condition_id,),
        )

        if not row or safe_int(row.get("row_count")) == 0:
            return None

        title = ""
        outcome = ""

        detail_columns: list[str] = []
        if title_column:
            detail_columns.append(
                f"{quote_identifier(clean_text(title_column))} AS title"
            )
        if outcome_column:
            detail_columns.append(
                f"{quote_identifier(clean_text(outcome_column))} AS outcome"
            )

        if detail_columns:
            order_clause = ""
            if timestamp_column:
                order_clause = (
                    f"ORDER BY {quote_identifier(clean_text(timestamp_column))} ASC"
                )

            detail_row = self.data.fetch_one(
                f"""
                SELECT
                    {", ".join(detail_columns)}
                FROM {quote_identifier(table_name)}
                WHERE LOWER(TRIM({quote_identifier(condition_column)})) = ?
                {order_clause}
                LIMIT 1
                """,
                (condition_id,),
            ) or {}

            title = clean_text(detail_row.get("title"))
            outcome = clean_text(detail_row.get("outcome"))

        return SourceOccurrence(
            table_name=table_name,
            row_count=safe_int(row.get("row_count")),
            first_seen_at=clean_text(row.get("first_seen_at")) or None,
            last_seen_at=clean_text(row.get("last_seen_at")) or None,
            title=title,
            outcome=outcome,
        )

    def audit_condition(
        self,
        condition_id: str,
        source_tables: Sequence[str],
    ) -> ConditionLineage:
        normalized = normalize_condition_id(condition_id)

        canonical_market = self.repository.resolve(
            normalized,
            include_legacy=False,
        )
        legacy_market = None

        if self.include_legacy and not canonical_market:
            legacy_market = self.repository.resolve(
                normalized,
                include_legacy=True,
            )

        occurrences = [
            occurrence
            for table_name in source_tables
            if (
                occurrence := self._source_occurrence(
                    table_name,
                    normalized,
                )
            )
            is not None
        ]

        def sort_key(item: SourceOccurrence) -> tuple[int, str, str]:
            return (
                0 if item.first_seen_at else 1,
                item.first_seen_at or "",
                item.table_name,
            )

        occurrences.sort(key=sort_key)

        first_source = occurrences[0].table_name if occurrences else ""
        first_seen = next(
            (
                item.first_seen_at
                for item in occurrences
                if item.first_seen_at
            ),
            None,
        )

        last_seen_candidates = [
            item.last_seen_at
            for item in occurrences
            if item.last_seen_at
        ]
        last_seen = max(last_seen_candidates) if last_seen_candidates else None

        canonical_found = int(canonical_market is not None)
        legacy_found = int(
            canonical_market is None and legacy_market is not None
        )

        if canonical_found:
            registry_source = "CANONICAL"
            diagnosis = "CANONICAL_MATCH"
            registry_market = canonical_market
        elif legacy_found:
            registry_source = "LEGACY_GAMMA"
            diagnosis = "LEGACY_ONLY_MATCH"
            registry_market = legacy_market
        elif occurrences:
            registry_source = "NONE"
            diagnosis = "UPSTREAM_WITHOUT_REGISTRY"
            registry_market = None
        else:
            registry_source = "NONE"
            diagnosis = "NO_LINEAGE_FOUND"
            registry_market = None

        title = clean_text(
            registry_market.title
            if registry_market
            else next(
                (item.title for item in occurrences if item.title),
                "",
            )
        )
        outcome = clean_text(
            registry_market.outcome
            if registry_market
            else next(
                (item.outcome for item in occurrences if item.outcome),
                "",
            )
        )

        return ConditionLineage(
            condition_id=normalized,
            canonical_found=canonical_found,
            legacy_found=legacy_found,
            registry_source=registry_source,
            first_source_table=first_source,
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            source_table_count=len(occurrences),
            total_occurrences=sum(item.row_count for item in occurrences),
            title=title,
            outcome=outcome,
            diagnosis=diagnosis,
            source_occurrences=occurrences,
        )

    def run(
        self,
        *,
        target_table: str,
        unresolved_only: bool,
        source_tables: Iterable[str] | None,
        explicit_condition_ids: Iterable[str] | None,
        apply: bool,
    ) -> dict[str, Any]:
        self.create_tables()

        run_id = uuid.uuid4().hex
        started = utc_now()
        started_at = started.isoformat()

        target_condition_ids = self.load_target_condition_ids(
            target_table=target_table,
            unresolved_only=unresolved_only,
            explicit_condition_ids=explicit_condition_ids,
        )

        valid_source_tables = self.discover_source_tables(source_tables)

        connection = self.connect()
        try:
            connection.execute(
                f"""
                INSERT INTO {quote_identifier(RUNS_TABLE)} (
                    run_id,
                    started_at,
                    target_count,
                    source_tables_checked,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    started_at,
                    len(target_condition_ids),
                    len(valid_source_tables),
                    "RUNNING",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        results: list[ConditionLineage] = []
        error_message = ""
        status = "SUCCESS"

        try:
            for index, condition_id in enumerate(
                target_condition_ids,
                start=1,
            ):
                LOGGER.debug(
                    "Auditing %s/%s: %s",
                    index,
                    len(target_condition_ids),
                    condition_id,
                )
                results.append(
                    self.audit_condition(
                        condition_id,
                        valid_source_tables,
                    )
                )
        except Exception as exc:
            status = "FAILED"
            error_message = str(exc)
            raise
        finally:
            finished = utc_now()
            elapsed_seconds = (
                finished - started
            ).total_seconds()

            resolved_count = sum(
                result.diagnosis in {
                    "CANONICAL_MATCH",
                    "LEGACY_ONLY_MATCH",
                }
                for result in results
            )
            unresolved_count = sum(
                result.diagnosis in {
                    "UPSTREAM_WITHOUT_REGISTRY",
                    "NO_LINEAGE_FOUND",
                }
                for result in results
            )

            results_written = 0
            connection = self.connect()
            try:
                if apply and results:
                    audited_at = finished.isoformat()
                    connection.executemany(
                        f"""
                        INSERT INTO {quote_identifier(RESULTS_TABLE)} (
                            run_id,
                            condition_id,
                            canonical_found,
                            legacy_found,
                            registry_source,
                            first_source_table,
                            first_seen_at,
                            last_seen_at,
                            source_table_count,
                            total_occurrences,
                            title,
                            outcome,
                            diagnosis,
                            source_occurrences_json,
                            audited_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        [
                            (
                                run_id,
                                result.condition_id,
                                result.canonical_found,
                                result.legacy_found,
                                result.registry_source,
                                result.first_source_table,
                                result.first_seen_at,
                                result.last_seen_at,
                                result.source_table_count,
                                result.total_occurrences,
                                result.title,
                                result.outcome,
                                result.diagnosis,
                                stable_json(
                                    [
                                        asdict(item)
                                        for item in result.source_occurrences
                                    ]
                                ),
                                audited_at,
                            )
                            for result in results
                        ],
                    )
                    results_written = len(results)

                connection.execute(
                    f"""
                    UPDATE {quote_identifier(RUNS_TABLE)}
                    SET
                        finished_at=?,
                        elapsed_seconds=?,
                        resolved_count=?,
                        unresolved_count=?,
                        results_written=?,
                        status=?,
                        error_message=?
                    WHERE run_id=?
                    """,
                    (
                        finished.isoformat(),
                        elapsed_seconds,
                        resolved_count,
                        unresolved_count,
                        results_written,
                        status,
                        error_message or None,
                        run_id,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

        diagnosis_counts: dict[str, int] = {}
        first_source_counts: dict[str, int] = {}

        for result in results:
            diagnosis_counts[result.diagnosis] = (
                diagnosis_counts.get(result.diagnosis, 0) + 1
            )
            if result.first_source_table:
                first_source_counts[result.first_source_table] = (
                    first_source_counts.get(result.first_source_table, 0) + 1
                )

        return {
            "run_id": run_id,
            "database_path": str(self.database_path),
            "mode": "APPLY" if apply else "DRY RUN",
            "target_table": target_table,
            "unresolved_only": unresolved_only,
            "target_count": len(target_condition_ids),
            "source_tables_checked": valid_source_tables,
            "results": results,
            "diagnosis_counts": diagnosis_counts,
            "first_source_counts": first_source_counts,
            "results_written": results_written,
            "elapsed_seconds": elapsed_seconds,
            "status": status,
        }


def print_report(report: Mapping[str, Any], preview_limit: int) -> None:
    results: list[ConditionLineage] = list(report["results"])

    print()
    print("=" * 112)
    print("CONDITION ID LINEAGE AUDIT")
    print("=" * 112)
    print(f"{'Database:':32} {report['database_path']}")
    print(f"{'Mode:':32} {report['mode']}")
    print(f"{'Run ID:':32} {report['run_id']}")
    print(f"{'Target table:':32} {report['target_table']}")
    print(f"{'Unresolved only:':32} {report['unresolved_only']}")
    print(f"{'Condition IDs audited:':32} {report['target_count']}")
    print(f"{'Source tables checked:':32} {len(report['source_tables_checked'])}")
    print(f"{'Results written:':32} {report['results_written']}")
    print(f"{'Duration:':32} {report['elapsed_seconds']:.3f}s")
    print(f"{'Status:':32} {report['status']}")

    print()
    print("SOURCE TABLES")
    print("-" * 112)
    for table_name in report["source_tables_checked"]:
        print(table_name)

    print()
    print("DIAGNOSIS COUNTS")
    print("-" * 112)
    for diagnosis, count in sorted(
        report["diagnosis_counts"].items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"{diagnosis:<48} {count:>8}")

    print()
    print("FIRST-SOURCE COUNTS")
    print("-" * 112)
    if report["first_source_counts"]:
        for table_name, count in sorted(
            report["first_source_counts"].items(),
            key=lambda item: (-item[1], item[0]),
        ):
            print(f"{table_name:<48} {count:>8}")
    else:
        print("No source lineage found.")

    unresolved = [
        result
        for result in results
        if result.diagnosis in {
            "UPSTREAM_WITHOUT_REGISTRY",
            "NO_LINEAGE_FOUND",
        }
    ]

    print()
    print("UNRESOLVED LINEAGE PREVIEW")
    print("-" * 112)

    if not unresolved:
        print("No unresolved condition IDs.")
    else:
        for result in unresolved[:preview_limit]:
            source_path = " -> ".join(
                item.table_name
                for item in result.source_occurrences
            ) or "NO SOURCE"
            title = result.title or "UNKNOWN TITLE"
            outcome = result.outcome or "UNKNOWN OUTCOME"

            print(
                f"{result.condition_id} | "
                f"{outcome} | "
                f"{result.first_source_table or 'UNKNOWN'} | "
                f"{title}"
            )
            print(f"    lineage: {source_path}")
            print(
                f"    occurrences: {result.total_occurrences} | "
                f"first: {result.first_seen_at or 'UNKNOWN'} | "
                f"last: {result.last_seen_at or 'UNKNOWN'}"
            )

    print("=" * 112)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Trace condition IDs across upstream Polymarket intelligence tables "
            "and compare them with canonical and legacy market registries."
        )
    )
    parser.add_argument(
        "--target-table",
        default="master_opportunities",
        help=(
            "Table whose condition IDs should be audited. "
            "Default: master_opportunities"
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Audit all condition IDs in the target table. "
            "Default behavior audits registry-unresolved IDs only."
        ),
    )
    parser.add_argument(
        "--condition-id",
        action="append",
        dest="condition_ids",
        help=(
            "Audit a specific condition ID. May be repeated."
        ),
    )
    parser.add_argument(
        "--source-table",
        action="append",
        dest="source_tables",
        help=(
            "Restrict lineage checks to a source table. May be repeated."
        ),
    )
    parser.add_argument(
        "--no-legacy",
        action="store_true",
        help="Do not consider gamma_markets as a fallback registry.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist detailed results to condition_id_lineage_audit_results. "
            "Dry run is the default."
        ),
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=20,
        help="Maximum unresolved rows to display. Default: 20.",
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

    audit = ConditionIdLineageAudit(
        include_legacy=not args.no_legacy
    )

    report = audit.run(
        target_table=args.target_table,
        unresolved_only=not args.all,
        source_tables=args.source_tables,
        explicit_condition_ids=args.condition_ids,
        apply=args.apply,
    )

    print_report(
        report,
        preview_limit=max(1, args.preview_limit),
    )


if __name__ == "__main__":
    main()