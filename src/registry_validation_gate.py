from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from data_access import DATABASE_PATH
except ImportError:
    from src.data_access import DATABASE_PATH

try:
    from canonical_market_repository import CanonicalMarketRepository
except ImportError:
    from src.canonical_market_repository import CanonicalMarketRepository


LOGGER = logging.getLogger(__name__)

BUSY_TIMEOUT_MS = 30_000

RUNS_TABLE = "registry_validation_gate_runs"
RESULTS_TABLE = "registry_validation_gate_results"
QUARANTINE_TABLE = "registry_validation_quarantine"

DEFAULT_SOURCE_TABLES = (
    "consensus_history",
    "institutional_consensus",
    "position_evolution",
    "market_memory_snapshots",
    "smart_money_flow_signals",
    "market_predictions",
    "ranked_market_opportunities",
    "master_opportunities",
)

MARKET_ID_CANDIDATES = (
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
    "calculated_at",
    "created_at",
    "updated_at",
    "recorded_at",
)


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


def is_probable_condition_id(value: str) -> bool:
    normalized = normalize_market_id(value)
    return (
        normalized.startswith("0x")
        and len(normalized) == 66
        and all(character in "0123456789abcdef" for character in normalized[2:])
    )


@dataclass(slots=True)
class ValidationResult:
    source_table: str
    source_rowid: int | None
    market_id: str
    title: str
    outcome: str
    observed_at: str | None
    validation_status: str
    registry_source: str
    canonical_market_id: str
    tradable_identity: int
    active: int
    closed: int
    archived: int
    restricted: int
    accepting_orders: int
    polymarket_url: str
    reason_code: str
    reason_detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RegistryValidationGate:
    """
    Canonical-first market validation gate.

    The gate does not delete or rewrite upstream data. It classifies each
    market record and can persist failures to a quarantine table for later
    review or targeted registry recovery.

    Validation classes:
        VALID_TRADABLE
        VALID_NON_TRADABLE
        LEGACY_ONLY
        MALFORMED_MARKET_ID
        MISSING_MARKET_ID
        UNKNOWN_MARKET
    """

    def __init__(
        self,
        database_path: Path | str = DATABASE_PATH,
        *,
        allow_legacy_fallback: bool = True,
    ) -> None:
        self.database_path = Path(database_path)
        self.repository = CanonicalMarketRepository(
            database_path=self.database_path,
            allow_legacy_fallback=allow_legacy_fallback,
        )
        self.allow_legacy_fallback = allow_legacy_fallback
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

    def table_columns(self, table_name: str) -> set[str]:
        if table_name not in self._columns_cache:
            connection = self.connect()
            try:
                rows = connection.execute(
                    f"PRAGMA table_info({quote_identifier(table_name)})"
                ).fetchall()
            finally:
                connection.close()

            self._columns_cache[table_name] = {
                clean_text(row["name"])
                for row in rows
                if clean_text(row["name"])
            }

        return self._columns_cache[table_name]

    def source_metadata(
        self,
        table_name: str,
    ) -> dict[str, str | None] | None:
        if not self.table_exists(table_name):
            return None

        columns = self.table_columns(table_name)
        market_id_column = first_existing(columns, MARKET_ID_CANDIDATES)
        if not market_id_column:
            return None

        return {
            "market_id_column": market_id_column,
            "title_column": first_existing(columns, TITLE_CANDIDATES),
            "outcome_column": first_existing(columns, OUTCOME_CANDIDATES),
            "timestamp_column": first_existing(columns, TIMESTAMP_CANDIDATES),
        }

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
                    source_tables_json TEXT NOT NULL,
                    rows_scanned INTEGER NOT NULL DEFAULT 0,
                    valid_tradable INTEGER NOT NULL DEFAULT 0,
                    valid_non_tradable INTEGER NOT NULL DEFAULT 0,
                    legacy_only INTEGER NOT NULL DEFAULT 0,
                    malformed INTEGER NOT NULL DEFAULT 0,
                    missing_market_id INTEGER NOT NULL DEFAULT 0,
                    unknown_market INTEGER NOT NULL DEFAULT 0,
                    quarantined INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(RESULTS_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_rowid INTEGER,
                    market_id TEXT,
                    title TEXT,
                    outcome TEXT,
                    observed_at TEXT,
                    validation_status TEXT NOT NULL,
                    registry_source TEXT,
                    canonical_market_id TEXT,
                    tradable_identity INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 0,
                    closed INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    restricted INTEGER NOT NULL DEFAULT 0,
                    accepting_orders INTEGER NOT NULL DEFAULT 0,
                    polymarket_url TEXT,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    validated_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS
                idx_registry_validation_results_market
                ON {quote_identifier(RESULTS_TABLE)}(
                    market_id,
                    validated_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_registry_validation_results_status
                ON {quote_identifier(RESULTS_TABLE)}(
                    validation_status,
                    validated_at DESC
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(QUARANTINE_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_run_id TEXT NOT NULL,
                    latest_run_id TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_rowid INTEGER,
                    market_id TEXT,
                    title TEXT,
                    outcome TEXT,
                    observed_at TEXT,
                    validation_status TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    resolved_at TEXT,
                    resolution_note TEXT,
                    UNIQUE(
                        source_table,
                        source_rowid,
                        market_id,
                        validation_status
                    )
                );

                CREATE INDEX IF NOT EXISTS
                idx_registry_validation_quarantine_open
                ON {quote_identifier(QUARANTINE_TABLE)}(
                    resolved,
                    validation_status,
                    last_seen_at DESC
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

    def discover_source_tables(
        self,
        requested_tables: Iterable[str] | None = None,
    ) -> list[str]:
        candidates = list(requested_tables or DEFAULT_SOURCE_TABLES)
        return [
            table_name
            for table_name in candidates
            if self.source_metadata(table_name) is not None
        ]

    def load_rows(
        self,
        table_name: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        metadata = self.source_metadata(table_name)
        if not metadata:
            return []

        market_id_column = clean_text(metadata["market_id_column"])
        title_column = metadata["title_column"]
        outcome_column = metadata["outcome_column"]
        timestamp_column = metadata["timestamp_column"]

        select_parts = [
            "rowid AS source_rowid",
            f"{quote_identifier(market_id_column)} AS market_id",
        ]

        select_parts.append(
            f"{quote_identifier(clean_text(title_column))} AS title"
            if title_column
            else "NULL AS title"
        )
        select_parts.append(
            f"{quote_identifier(clean_text(outcome_column))} AS outcome"
            if outcome_column
            else "NULL AS outcome"
        )
        select_parts.append(
            f"{quote_identifier(clean_text(timestamp_column))} AS observed_at"
            if timestamp_column
            else "NULL AS observed_at"
        )

        sql = f"""
            SELECT
                {", ".join(select_parts)}
            FROM {quote_identifier(table_name)}
        """

        parameters: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            parameters = (max(0, int(limit)),)

        connection = self.connect()
        try:
            rows = connection.execute(sql, parameters).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def validate_record(
        self,
        *,
        source_table: str,
        source_rowid: int | None,
        market_id: Any,
        title: Any,
        outcome: Any,
        observed_at: Any,
    ) -> ValidationResult:
        normalized_market_id = normalize_market_id(market_id)
        title_text = clean_text(title)
        outcome_text = clean_text(outcome)
        observed_at_text = clean_text(observed_at) or None

        common = {
            "source_table": source_table,
            "source_rowid": source_rowid,
            "market_id": normalized_market_id,
            "title": title_text,
            "outcome": outcome_text,
            "observed_at": observed_at_text,
        }

        if not normalized_market_id:
            return ValidationResult(
                **common,
                validation_status="MISSING_MARKET_ID",
                registry_source="NONE",
                canonical_market_id="",
                tradable_identity=0,
                active=0,
                closed=0,
                archived=0,
                restricted=0,
                accepting_orders=0,
                polymarket_url="",
                reason_code="MISSING_MARKET_ID",
                reason_detail="The source row does not contain a market identifier.",
            )

        if not is_probable_condition_id(normalized_market_id):
            return ValidationResult(
                **common,
                validation_status="MALFORMED_MARKET_ID",
                registry_source="NONE",
                canonical_market_id="",
                tradable_identity=0,
                active=0,
                closed=0,
                archived=0,
                restricted=0,
                accepting_orders=0,
                polymarket_url="",
                reason_code="INVALID_CONDITION_ID_FORMAT",
                reason_detail=(
                    "Expected a 0x-prefixed 32-byte hexadecimal condition ID."
                ),
            )

        canonical_market = self.repository.resolve(
            normalized_market_id,
            include_legacy=False,
        )

        if canonical_market is not None:
            status = (
                "VALID_TRADABLE"
                if canonical_market.tradable_identity == 1
                else "VALID_NON_TRADABLE"
            )
            reason_code = (
                "CANONICAL_TRADABLE"
                if status == "VALID_TRADABLE"
                else "CANONICAL_NON_TRADABLE"
            )
            reason_detail = (
                "Resolved through canonical_market_identities."
                if status == "VALID_TRADABLE"
                else (
                    "Resolved canonically but is not currently tradable "
                    f"(active={canonical_market.active}, "
                    f"closed={canonical_market.closed}, "
                    f"archived={canonical_market.archived})."
                )
            )

            return ValidationResult(
                **common,
                validation_status=status,
                registry_source="CANONICAL",
                canonical_market_id=canonical_market.canonical_market_id,
                tradable_identity=canonical_market.tradable_identity,
                active=canonical_market.active,
                closed=canonical_market.closed,
                archived=canonical_market.archived,
                restricted=canonical_market.restricted,
                accepting_orders=canonical_market.accepting_orders,
                polymarket_url=canonical_market.polymarket_url,
                reason_code=reason_code,
                reason_detail=reason_detail,
            )

        if self.allow_legacy_fallback:
            legacy_market = self.repository.resolve(
                normalized_market_id,
                include_legacy=True,
            )
            if legacy_market is not None:
                return ValidationResult(
                    **common,
                    validation_status="LEGACY_ONLY",
                    registry_source="LEGACY_GAMMA",
                    canonical_market_id="",
                    tradable_identity=legacy_market.tradable_identity,
                    active=legacy_market.active,
                    closed=legacy_market.closed,
                    archived=legacy_market.archived,
                    restricted=legacy_market.restricted,
                    accepting_orders=legacy_market.accepting_orders,
                    polymarket_url=legacy_market.polymarket_url,
                    reason_code="LEGACY_ONLY_MARKET",
                    reason_detail=(
                        "Resolved in gamma_markets but is absent from "
                        "canonical_market_identities."
                    ),
                )

        return ValidationResult(
            **common,
            validation_status="UNKNOWN_MARKET",
            registry_source="NONE",
            canonical_market_id="",
            tradable_identity=0,
            active=0,
            closed=0,
            archived=0,
            restricted=0,
            accepting_orders=0,
            polymarket_url="",
            reason_code="MISSING_FROM_ALL_REGISTRIES",
            reason_detail=(
                "The condition ID was not found in canonical_market_identities "
                "or gamma_markets."
            ),
        )

    def should_quarantine(
        self,
        result: ValidationResult,
        *,
        quarantine_non_tradable: bool,
        quarantine_legacy_only: bool,
    ) -> bool:
        if result.validation_status in {
            "UNKNOWN_MARKET",
            "MALFORMED_MARKET_ID",
            "MISSING_MARKET_ID",
        }:
            return True
        if (
            quarantine_non_tradable
            and result.validation_status == "VALID_NON_TRADABLE"
        ):
            return True
        if (
            quarantine_legacy_only
            and result.validation_status == "LEGACY_ONLY"
        ):
            return True
        return False

    def persist_results(
        self,
        *,
        run_id: str,
        results: Sequence[ValidationResult],
        quarantine_non_tradable: bool,
        quarantine_legacy_only: bool,
    ) -> int:
        if not results:
            return 0

        validated_at = utc_now_iso()
        quarantine_count = 0

        connection = self.connect()
        try:
            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(RESULTS_TABLE)} (
                    run_id,
                    source_table,
                    source_rowid,
                    market_id,
                    title,
                    outcome,
                    observed_at,
                    validation_status,
                    registry_source,
                    canonical_market_id,
                    tradable_identity,
                    active,
                    closed,
                    archived,
                    restricted,
                    accepting_orders,
                    polymarket_url,
                    reason_code,
                    reason_detail,
                    validated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    (
                        run_id,
                        result.source_table,
                        result.source_rowid,
                        result.market_id,
                        result.title,
                        result.outcome,
                        result.observed_at,
                        result.validation_status,
                        result.registry_source,
                        result.canonical_market_id,
                        result.tradable_identity,
                        result.active,
                        result.closed,
                        result.archived,
                        result.restricted,
                        result.accepting_orders,
                        result.polymarket_url,
                        result.reason_code,
                        result.reason_detail,
                        validated_at,
                    )
                    for result in results
                ],
            )

            for result in results:
                if not self.should_quarantine(
                    result,
                    quarantine_non_tradable=quarantine_non_tradable,
                    quarantine_legacy_only=quarantine_legacy_only,
                ):
                    continue

                quarantine_count += 1
                connection.execute(
                    f"""
                    INSERT INTO {quote_identifier(QUARANTINE_TABLE)} (
                        first_run_id,
                        latest_run_id,
                        source_table,
                        source_rowid,
                        market_id,
                        title,
                        outcome,
                        observed_at,
                        validation_status,
                        reason_code,
                        reason_detail,
                        first_seen_at,
                        last_seen_at,
                        occurrence_count,
                        resolved
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0
                    )
                    ON CONFLICT(
                        source_table,
                        source_rowid,
                        market_id,
                        validation_status
                    )
                    DO UPDATE SET
                        latest_run_id=excluded.latest_run_id,
                        title=excluded.title,
                        outcome=excluded.outcome,
                        observed_at=excluded.observed_at,
                        reason_code=excluded.reason_code,
                        reason_detail=excluded.reason_detail,
                        last_seen_at=excluded.last_seen_at,
                        occurrence_count=
                            {quote_identifier(QUARANTINE_TABLE)}.occurrence_count + 1,
                        resolved=0,
                        resolved_at=NULL,
                        resolution_note=NULL
                    """,
                    (
                        run_id,
                        run_id,
                        result.source_table,
                        result.source_rowid,
                        result.market_id,
                        result.title,
                        result.outcome,
                        result.observed_at,
                        result.validation_status,
                        result.reason_code,
                        result.reason_detail,
                        validated_at,
                        validated_at,
                    ),
                )

            connection.commit()
        finally:
            connection.close()

        return quarantine_count

    def run(
        self,
        *,
        source_tables: Iterable[str] | None = None,
        limit_per_table: int | None = None,
        apply: bool = False,
        quarantine_non_tradable: bool = False,
        quarantine_legacy_only: bool = False,
    ) -> dict[str, Any]:
        self.create_tables()

        run_id = uuid.uuid4().hex
        started = utc_now()
        started_at = started.isoformat()
        valid_source_tables = self.discover_source_tables(source_tables)

        connection = self.connect()
        try:
            connection.execute(
                f"""
                INSERT INTO {quote_identifier(RUNS_TABLE)} (
                    run_id,
                    started_at,
                    mode,
                    source_tables_json,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    started_at,
                    "APPLY" if apply else "DRY RUN",
                    stable_json(valid_source_tables),
                    "RUNNING",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        results: list[ValidationResult] = []
        status = "SUCCESS"
        error_message = ""
        quarantine_count = 0

        try:
            for table_name in valid_source_tables:
                rows = self.load_rows(
                    table_name,
                    limit=limit_per_table,
                )

                LOGGER.info(
                    "Validating %s rows from %s",
                    len(rows),
                    table_name,
                )

                for row in rows:
                    results.append(
                        self.validate_record(
                            source_table=table_name,
                            source_rowid=row.get("source_rowid"),
                            market_id=row.get("market_id"),
                            title=row.get("title"),
                            outcome=row.get("outcome"),
                            observed_at=row.get("observed_at"),
                        )
                    )

            if apply:
                quarantine_count = self.persist_results(
                    run_id=run_id,
                    results=results,
                    quarantine_non_tradable=quarantine_non_tradable,
                    quarantine_legacy_only=quarantine_legacy_only,
                )

        except Exception as exc:
            status = "FAILED"
            error_message = str(exc)
            raise

        finally:
            finished = utc_now()
            elapsed_seconds = (finished - started).total_seconds()

            counts: dict[str, int] = {}
            for result in results:
                counts[result.validation_status] = (
                    counts.get(result.validation_status, 0) + 1
                )

            connection = self.connect()
            try:
                connection.execute(
                    f"""
                    UPDATE {quote_identifier(RUNS_TABLE)}
                    SET
                        finished_at=?,
                        elapsed_seconds=?,
                        rows_scanned=?,
                        valid_tradable=?,
                        valid_non_tradable=?,
                        legacy_only=?,
                        malformed=?,
                        missing_market_id=?,
                        unknown_market=?,
                        quarantined=?,
                        status=?,
                        error_message=?
                    WHERE run_id=?
                    """,
                    (
                        finished.isoformat(),
                        elapsed_seconds,
                        len(results),
                        counts.get("VALID_TRADABLE", 0),
                        counts.get("VALID_NON_TRADABLE", 0),
                        counts.get("LEGACY_ONLY", 0),
                        counts.get("MALFORMED_MARKET_ID", 0),
                        counts.get("MISSING_MARKET_ID", 0),
                        counts.get("UNKNOWN_MARKET", 0),
                        quarantine_count,
                        status,
                        error_message or None,
                        run_id,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

        counts: dict[str, int] = {}
        for result in results:
            counts[result.validation_status] = (
                counts.get(result.validation_status, 0) + 1
            )

        failures = [
            result
            for result in results
            if self.should_quarantine(
                result,
                quarantine_non_tradable=quarantine_non_tradable,
                quarantine_legacy_only=quarantine_legacy_only,
            )
        ]

        return {
            "run_id": run_id,
            "database_path": str(self.database_path),
            "mode": "APPLY" if apply else "DRY RUN",
            "source_tables": valid_source_tables,
            "rows_scanned": len(results),
            "counts": counts,
            "quarantined": quarantine_count,
            "failures": failures,
            "elapsed_seconds": elapsed_seconds,
            "status": status,
        }


def print_report(
    report: Mapping[str, Any],
    *,
    preview_limit: int,
) -> None:
    print()
    print("=" * 112)
    print("REGISTRY VALIDATION GATE")
    print("=" * 112)
    print(f"{'Database:':32} {report['database_path']}")
    print(f"{'Mode:':32} {report['mode']}")
    print(f"{'Run ID:':32} {report['run_id']}")
    print(f"{'Source tables:':32} {len(report['source_tables'])}")
    print(f"{'Rows scanned:':32} {report['rows_scanned']}")
    print(f"{'Rows quarantined:':32} {report['quarantined']}")
    print(f"{'Duration:':32} {report['elapsed_seconds']:.3f}s")
    print(f"{'Status:':32} {report['status']}")

    print()
    print("VALIDATION COUNTS")
    print("-" * 112)
    if report["counts"]:
        for status, count in sorted(
            report["counts"].items(),
            key=lambda item: (-item[1], item[0]),
        ):
            print(f"{status:<48} {count:>8}")
    else:
        print("No rows were scanned.")

    print()
    print("SOURCE TABLES")
    print("-" * 112)
    for table_name in report["source_tables"]:
        print(table_name)

    print()
    print("QUARANTINE PREVIEW")
    print("-" * 112)

    failures: list[ValidationResult] = list(report["failures"])
    if not failures:
        print("No records met the quarantine criteria.")
    else:
        for result in failures[:preview_limit]:
            print(
                f"{result.validation_status:<22} | "
                f"{result.source_table:<30} | "
                f"{result.market_id or 'NO MARKET ID'}"
            )
            print(
                f"    {result.outcome or 'UNKNOWN OUTCOME'} | "
                f"{result.title or 'UNKNOWN TITLE'}"
            )
            print(
                f"    {result.reason_code}: {result.reason_detail}"
            )

    print("=" * 112)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate upstream Polymarket records against the canonical "
            "market registry and quarantine invalid identities."
        )
    )
    parser.add_argument(
        "--source-table",
        action="append",
        dest="source_tables",
        help=(
            "Validate only this source table. May be repeated. "
            "Defaults to the core intelligence pipeline tables."
        ),
    )
    parser.add_argument(
        "--limit-per-table",
        type=int,
        help="Optional row limit per source table for testing.",
    )
    parser.add_argument(
        "--no-legacy",
        action="store_true",
        help="Disable fallback validation against gamma_markets.",
    )
    parser.add_argument(
        "--quarantine-non-tradable",
        action="store_true",
        help="Also quarantine canonical markets that are not tradable.",
    )
    parser.add_argument(
        "--quarantine-legacy-only",
        action="store_true",
        help="Also quarantine markets found only in gamma_markets.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist validation results and quarantine failures. "
            "Dry run is the default."
        ),
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=20,
        help="Maximum quarantine rows to print. Default: 20.",
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

    gate = RegistryValidationGate(
        allow_legacy_fallback=not args.no_legacy
    )

    report = gate.run(
        source_tables=args.source_tables,
        limit_per_table=args.limit_per_table,
        apply=args.apply,
        quarantine_non_tradable=args.quarantine_non_tradable,
        quarantine_legacy_only=args.quarantine_legacy_only,
    )

    print_report(
        report,
        preview_limit=max(1, args.preview_limit),
    )


if __name__ == "__main__":
    main()