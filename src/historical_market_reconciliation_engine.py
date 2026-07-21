from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from data_access import DATABASE_PATH
except ImportError:
    from src.data_access import DATABASE_PATH

LOGGER = logging.getLogger(__name__)
BUSY_TIMEOUT_MS = 30_000
CANONICAL_TABLE = "canonical_market_identities"
LEGACY_TABLE = "gamma_markets"
RUNS_TABLE = "historical_market_reconciliation_runs"
AUDIT_TABLE = "historical_market_reconciliation_audit"
SUMMARY_TABLE = "historical_market_reconciliation_summary"

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
    "market_id",
    "canonical_market_id",
    "market_condition_id",
    "conditionId",
)
TITLE_CANDIDATES = ("title", "question", "market_title", "name")
OUTCOME_CANDIDATES = ("outcome", "selected_outcome", "side", "position")
TIMESTAMP_CANDIDATES = (
    "scanned_at",
    "created_at",
    "updated_at",
    "observed_at",
    "timestamp",
    "recorded_at",
)
HEX_32_RE = re.compile(r"^0x[0-9a-f]{64}$", re.IGNORECASE)


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


def first_existing(columns: set[str], candidates: Sequence[str]) -> str | None:
    return next((candidate for candidate in candidates if candidate in columns), None)


@dataclass(slots=True)
class SourceSpec:
    table_name: str
    market_id_column: str
    title_column: str | None
    outcome_column: str | None
    timestamp_column: str | None


@dataclass(slots=True)
class ReconciliationRecord:
    source_table: str
    source_rowid: int | None
    market_id: str
    title: str
    outcome: str
    source_timestamp: str
    classification: str
    reason_code: str
    reason_detail: str
    canonical_match: int
    gamma_match: int
    malformed: int


class HistoricalMarketReconciliationEngine:
    """Classify downstream market references without deleting source data."""

    def __init__(
        self,
        database_path: Path | str = DATABASE_PATH,
        source_tables: Sequence[str] = DEFAULT_SOURCE_TABLES,
    ) -> None:
        self.database_path = Path(database_path)
        self.source_tables = tuple(source_tables)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        return connection

    def table_exists(self, table_name: str) -> bool:
        connection = self.connect()
        try:
            row = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                (table_name,),
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    def table_columns(self, table_name: str) -> set[str]:
        if not self.table_exists(table_name):
            return set()
        connection = self.connect()
        try:
            rows = connection.execute(
                f"PRAGMA table_info({quote_identifier(table_name)})"
            ).fetchall()
            return {clean_text(row["name"]) for row in rows}
        finally:
            connection.close()

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
                    source_table_count INTEGER NOT NULL DEFAULT 0,
                    rows_scanned INTEGER NOT NULL DEFAULT 0,
                    rows_persisted INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(AUDIT_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_rowid INTEGER,
                    market_id TEXT,
                    title TEXT,
                    outcome TEXT,
                    source_timestamp TEXT,
                    classification TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    canonical_match INTEGER NOT NULL DEFAULT 0,
                    gamma_match INTEGER NOT NULL DEFAULT 0,
                    malformed INTEGER NOT NULL DEFAULT 0,
                    reconciled_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(SUMMARY_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_historical_reconciliation_market
                ON {quote_identifier(AUDIT_TABLE)}(market_id, reconciled_at DESC);

                CREATE INDEX IF NOT EXISTS idx_historical_reconciliation_classification
                ON {quote_identifier(AUDIT_TABLE)}(classification, reconciled_at DESC);

                CREATE INDEX IF NOT EXISTS idx_historical_reconciliation_source
                ON {quote_identifier(AUDIT_TABLE)}(source_table, source_rowid);
                """
            )
            connection.commit()
        finally:
            connection.close()

    def resolve_registry_columns(self) -> tuple[str, str, str | None]:
        canonical_columns = self.table_columns(CANONICAL_TABLE)
        gamma_columns = self.table_columns(LEGACY_TABLE)
        canonical_id = first_existing(canonical_columns, MARKET_ID_CANDIDATES)
        gamma_id = first_existing(gamma_columns, MARKET_ID_CANDIDATES)
        tradable_column = first_existing(
            canonical_columns,
            ("tradable_identity", "tradable", "is_tradable"),
        )
        if not canonical_id:
            raise RuntimeError(f"{CANONICAL_TABLE} has no recognized market ID column.")
        if not gamma_id:
            raise RuntimeError(f"{LEGACY_TABLE} has no recognized market ID column.")
        return canonical_id, gamma_id, tradable_column

    def resolve_source_specs(self) -> list[SourceSpec]:
        specs: list[SourceSpec] = []
        for table_name in self.source_tables:
            columns = self.table_columns(table_name)
            if not columns:
                LOGGER.warning("Skipping missing table: %s", table_name)
                continue
            market_id_column = first_existing(columns, MARKET_ID_CANDIDATES)
            if not market_id_column:
                LOGGER.warning("Skipping %s: no market ID column", table_name)
                continue
            specs.append(
                SourceSpec(
                    table_name=table_name,
                    market_id_column=market_id_column,
                    title_column=first_existing(columns, TITLE_CANDIDATES),
                    outcome_column=first_existing(columns, OUTCOME_CANDIDATES),
                    timestamp_column=first_existing(columns, TIMESTAMP_CANDIDATES),
                )
            )
        return specs

    def load_registry_sets(self) -> tuple[dict[str, int], set[str]]:
        canonical_id, gamma_id, tradable_column = self.resolve_registry_columns()
        connection = self.connect()
        try:
            canonical_sql = f"SELECT LOWER({quote_identifier(canonical_id)}) AS market_id"
            canonical_sql += (
                f", COALESCE({quote_identifier(tradable_column)}, 0) AS tradable"
                if tradable_column
                else ", 0 AS tradable"
            )
            canonical_sql += (
                f" FROM {quote_identifier(CANONICAL_TABLE)} "
                f"WHERE {quote_identifier(canonical_id)} IS NOT NULL"
            )
            canonical_rows = connection.execute(canonical_sql).fetchall()
            gamma_rows = connection.execute(
                f"SELECT LOWER({quote_identifier(gamma_id)}) AS market_id "
                f"FROM {quote_identifier(LEGACY_TABLE)} "
                f"WHERE {quote_identifier(gamma_id)} IS NOT NULL"
            ).fetchall()
        finally:
            connection.close()

        canonical = {
            normalize_market_id(row["market_id"]): int(row["tradable"] or 0)
            for row in canonical_rows
            if normalize_market_id(row["market_id"])
        }
        gamma = {
            normalize_market_id(row["market_id"])
            for row in gamma_rows
            if normalize_market_id(row["market_id"])
        }
        return canonical, gamma

    def select_source_rows(
        self,
        spec: SourceSpec,
        per_table_limit: int | None,
    ) -> list[sqlite3.Row]:
        parts = [
            "rowid AS source_rowid",
            f"{quote_identifier(spec.market_id_column)} AS market_id",
            (
                f"{quote_identifier(spec.title_column)} AS title"
                if spec.title_column
                else "NULL AS title"
            ),
            (
                f"{quote_identifier(spec.outcome_column)} AS outcome"
                if spec.outcome_column
                else "NULL AS outcome"
            ),
            (
                f"{quote_identifier(spec.timestamp_column)} AS source_timestamp"
                if spec.timestamp_column
                else "NULL AS source_timestamp"
            ),
        ]
        sql = (
            f"SELECT {', '.join(parts)} "
            f"FROM {quote_identifier(spec.table_name)} ORDER BY rowid"
        )
        parameters: tuple[Any, ...] = ()
        if per_table_limit is not None:
            sql += " LIMIT ?"
            parameters = (max(0, int(per_table_limit)),)
        connection = self.connect()
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def classify(
        self,
        market_id: str,
        canonical: Mapping[str, int],
        gamma: set[str],
    ) -> tuple[str, str, str, int, int, int]:
        normalized = normalize_market_id(market_id)
        if not normalized:
            return (
                "MALFORMED_ID",
                "EMPTY_MARKET_ID",
                "The source record has no market identifier.",
                0,
                0,
                1,
            )
        if not HEX_32_RE.fullmatch(normalized):
            legacy_like = (
                normalized.isdigit()
                or normalized.startswith("market-")
                or normalized.startswith("event-")
                or len(normalized) < 40
            )
            if legacy_like:
                return (
                    "LEGACY_FORMAT",
                    "NON_CONDITION_ID_FORMAT",
                    "The identifier appears to use an older or alternate market-ID format.",
                    0,
                    0,
                    1,
                )
            return (
                "MALFORMED_ID",
                "INVALID_CONDITION_ID",
                "The identifier is not a valid 0x-prefixed 64-character hex condition ID.",
                0,
                0,
                1,
            )

        canonical_match = int(normalized in canonical)
        gamma_match = int(normalized in gamma)
        if canonical_match:
            if int(canonical.get(normalized, 0)):
                return (
                    "VALID_CURRENT",
                    "CANONICAL_TRADABLE",
                    "The market exists in the canonical registry and is tradable.",
                    1,
                    gamma_match,
                    0,
                )
            return (
                "VALID_NON_TRADABLE",
                "CANONICAL_NON_TRADABLE",
                "The market exists in canonical but is not currently tradable.",
                1,
                gamma_match,
                0,
            )
        if gamma_match:
            return (
                "REGISTRY_DRIFT",
                "GAMMA_ONLY_AFTER_SYNC",
                "The market exists in Gamma but not canonical; new post-sync drift exists.",
                0,
                1,
                0,
            )
        return (
            "HISTORICAL_NOT_IN_CURRENT_REGISTRY",
            "VALID_SHAPE_MISSING_FROM_CURRENT_REGISTRIES",
            "Valid condition-ID shape, absent from both current registries; preserve as historical pending archival recovery.",
            0,
            0,
            0,
        )

    def scan(
        self,
        specs: Sequence[SourceSpec],
        per_table_limit: int | None,
    ) -> list[ReconciliationRecord]:
        canonical, gamma = self.load_registry_sets()
        records: list[ReconciliationRecord] = []
        for spec in specs:
            rows = self.select_source_rows(spec, per_table_limit)
            LOGGER.info("Reconciling %s rows from %s", len(rows), spec.table_name)
            for row in rows:
                market_id = normalize_market_id(row["market_id"])
                (
                    classification,
                    reason_code,
                    reason_detail,
                    canonical_match,
                    gamma_match,
                    malformed,
                ) = self.classify(market_id, canonical, gamma)
                records.append(
                    ReconciliationRecord(
                        source_table=spec.table_name,
                        source_rowid=(
                            int(row["source_rowid"])
                            if row["source_rowid"] is not None
                            else None
                        ),
                        market_id=market_id,
                        title=clean_text(row["title"]),
                        outcome=clean_text(row["outcome"]),
                        source_timestamp=clean_text(row["source_timestamp"]),
                        classification=classification,
                        reason_code=reason_code,
                        reason_detail=reason_detail,
                        canonical_match=canonical_match,
                        gamma_match=gamma_match,
                        malformed=malformed,
                    )
                )
        return records

    def persist(self, run_id: str, records: Sequence[ReconciliationRecord]) -> int:
        reconciled_at = utc_now_iso()
        summary_counts: dict[str, int] = {}
        for record in records:
            summary_counts[record.classification] = summary_counts.get(record.classification, 0) + 1

        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(AUDIT_TABLE)} (
                    run_id, source_table, source_rowid, market_id, title, outcome,
                    source_timestamp, classification, reason_code, reason_detail,
                    canonical_match, gamma_match, malformed, reconciled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        r.source_table,
                        r.source_rowid,
                        r.market_id,
                        r.title,
                        r.outcome,
                        r.source_timestamp,
                        r.classification,
                        r.reason_code,
                        r.reason_detail,
                        r.canonical_match,
                        r.gamma_match,
                        r.malformed,
                        reconciled_at,
                    )
                    for r in records
                ],
            )
            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(SUMMARY_TABLE)} (
                    run_id, classification, record_count, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (run_id, classification, count, reconciled_at)
                    for classification, count in sorted(summary_counts.items())
                ],
            )
            connection.commit()
            return len(records)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def run(
        self,
        apply: bool = False,
        per_table_limit: int | None = None,
    ) -> dict[str, Any]:
        self.create_tables()
        run_id = uuid.uuid4().hex
        started = utc_now()
        mode = "APPLY" if apply else "DRY RUN"
        specs = self.resolve_source_specs()

        connection = self.connect()
        try:
            connection.execute(
                f"INSERT INTO {quote_identifier(RUNS_TABLE)} "
                "(run_id, started_at, mode, source_table_count, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, started.isoformat(), mode, len(specs), "RUNNING"),
            )
            connection.commit()
        finally:
            connection.close()

        status = "SUCCESS"
        error_message = ""
        records: list[ReconciliationRecord] = []
        rows_persisted = 0
        try:
            records = self.scan(specs, per_table_limit)
            if apply:
                rows_persisted = self.persist(run_id, records)
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
                    f"UPDATE {quote_identifier(RUNS_TABLE)} SET "
                    "finished_at=?, elapsed_seconds=?, rows_scanned=?, "
                    "rows_persisted=?, status=?, error_message=? WHERE run_id=?",
                    (
                        finished.isoformat(),
                        elapsed_seconds,
                        len(records),
                        rows_persisted,
                        status,
                        error_message or None,
                        run_id,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

        classification_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        for record in records:
            classification_counts[record.classification] = classification_counts.get(record.classification, 0) + 1
            source_counts[record.source_table] = source_counts.get(record.source_table, 0) + 1

        return {
            "run_id": run_id,
            "database_path": str(self.database_path),
            "mode": mode,
            "source_specs": specs,
            "rows_scanned": len(records),
            "rows_persisted": rows_persisted,
            "classification_counts": classification_counts,
            "source_counts": source_counts,
            "records": records,
            "elapsed_seconds": elapsed_seconds,
            "status": status,
        }


def print_report(report: Mapping[str, Any], preview_limit: int) -> None:
    print()
    print("=" * 118)
    print("HISTORICAL MARKET RECONCILIATION ENGINE")
    print("=" * 118)
    print(f"{'Database:':36} {report['database_path']}")
    print(f"{'Mode:':36} {report['mode']}")
    print(f"{'Run ID:':36} {report['run_id']}")
    print(f"{'Source tables:':36} {len(report['source_specs'])}")
    print(f"{'Rows scanned:':36} {report['rows_scanned']}")
    print(f"{'Rows persisted:':36} {report['rows_persisted']}")
    print(f"{'Duration:':36} {report['elapsed_seconds']:.3f}s")
    print(f"{'Status:':36} {report['status']}")

    print()
    print("CLASSIFICATION COUNTS")
    print("-" * 118)
    for classification, count in sorted(
        report["classification_counts"].items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"{classification:<56} {count:>10}")

    print()
    print("SOURCE TABLE COUNTS")
    print("-" * 118)
    for table_name, count in sorted(report["source_counts"].items()):
        print(f"{table_name:<56} {count:>10}")

    print()
    print("RECONCILIATION PREVIEW")
    print("-" * 118)
    records: list[ReconciliationRecord] = list(report["records"])
    non_current = [
        record
        for record in records
        if record.classification not in {"VALID_CURRENT", "VALID_NON_TRADABLE"}
    ]
    if not non_current:
        print("No historical, malformed, legacy-format, or drift records found.")
    else:
        for record in non_current[:preview_limit]:
            print(
                f"{record.classification:<42} | "
                f"{record.source_table:<30} | "
                f"{record.market_id or 'EMPTY'}"
            )
            if record.outcome or record.title:
                print(f"    {record.outcome or '-'} | {record.title or 'UNKNOWN TITLE'}")
            print(f"    {record.reason_code}: {record.reason_detail}")
    print("=" * 118)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify downstream market references as current, historical, "
            "legacy-format, malformed, or registry drift."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist findings to reconciliation audit tables. Dry run is default.",
    )
    parser.add_argument(
        "--per-table-limit",
        type=int,
        help="Limit rows scanned from each source table for controlled testing.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=30,
        help="Maximum non-current rows to print. Default: 30.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    configure_utf8()
    args = parse_args()
    configure_logging(args.verbose)
    engine = HistoricalMarketReconciliationEngine()
    report = engine.run(
        apply=args.apply,
        per_table_limit=args.per_table_limit,
    )
    print_report(report, preview_limit=max(1, args.preview_limit))


if __name__ == "__main__":
    main()