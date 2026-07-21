from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from data_access import DataAccess, DATABASE_PATH
except ImportError:
    from src.data_access import DataAccess, DATABASE_PATH


LOGGER = logging.getLogger(__name__)

CANONICAL_TABLE = "canonical_market_identities"
OPPORTUNITY_TABLE = "master_opportunities"
ALIAS_TABLE = "canonical_market_aliases"
AUDIT_TABLE = "canonical_identity_sync_audit"
RUN_TABLE = "canonical_identity_sync_runs"
SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text(value: Any) -> str:
    return str(value or "").strip()


def norm(value: Any) -> str:
    return text(value).lower()


def first(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


def qi(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


@dataclass(slots=True)
class Resolution:
    status: str
    source_market_id: str
    canonical_condition_id: str | None = None
    method: str | None = None
    matched_value: str | None = None
    confidence: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SyncSummary:
    run_id: str
    source_rows: int = 0
    resolved_rows: int = 0
    already_canonical_rows: int = 0
    repaired_rows: int = 0
    ambiguous_rows: int = 0
    orphaned_rows: int = 0
    skipped_rows: int = 0
    error_count: int = 0
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str | None = None
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CanonicalIdentitySynchronizer:
    CONDITION_NAMES = (
        "condition_id",
        "canonical_condition_id",
        "market_id",
        "conditionId",
    )
    GAMMA_NAMES = (
        "gamma_market_id",
        "gamma_id",
        "gammaMarketId",
    )
    TOKEN_NAMES = (
        "token_id",
        "clob_token_id",
        "yes_token_id",
        "no_token_id",
        "asset_id",
    )
    SLUG_NAMES = ("market_slug", "slug", "marketSlug")
    TITLE_NAMES = (
        "question",
        "title",
        "market_title",
        "market_question",
    )
    OUTCOME_NAMES = ("outcome", "selected_outcome", "side")

    def __init__(
        self,
        data_access: DataAccess | None = None,
        database_path: Path | str = DATABASE_PATH,
    ) -> None:
        self.data = data_access or DataAccess(database_path)
        self.database_path = Path(self.data.database_path)
        self._columns: dict[str, list[str]] = {}

    def initialize_schema(self) -> None:
        statements = [
            f"""
            CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                opportunity_rowid INTEGER,
                source_market_id TEXT,
                source_outcome TEXT,
                status TEXT NOT NULL,
                canonical_condition_id TEXT,
                match_method TEXT,
                match_value TEXT,
                confidence REAL NOT NULL DEFAULT 0,
                repaired INTEGER NOT NULL DEFAULT 0,
                details_json TEXT NOT NULL DEFAULT '{{}}',
                created_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT {SCHEMA_VERSION}
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {RUN_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                source_rows INTEGER NOT NULL DEFAULT 0,
                resolved_rows INTEGER NOT NULL DEFAULT 0,
                already_canonical_rows INTEGER NOT NULL DEFAULT 0,
                repaired_rows INTEGER NOT NULL DEFAULT 0,
                ambiguous_rows INTEGER NOT NULL DEFAULT 0,
                orphaned_rows INTEGER NOT NULL DEFAULT 0,
                skipped_rows INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                success INTEGER,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                error_message TEXT,
                details_json TEXT NOT NULL DEFAULT '{{}}',
                schema_version INTEGER NOT NULL DEFAULT {SCHEMA_VERSION}
            )
            """,
            f"CREATE INDEX IF NOT EXISTS idx_sync_audit_run ON {AUDIT_TABLE}(run_id)",
            f"CREATE INDEX IF NOT EXISTS idx_sync_audit_status ON {AUDIT_TABLE}(status)",
            f"CREATE INDEX IF NOT EXISTS idx_sync_runs_started ON {RUN_TABLE}(started_at DESC)",
        ]
        with self.data.transaction() as connection:
            for statement in statements:
                connection.execute(statement)

    def validate(self) -> None:
        missing = [
            name
            for name in (CANONICAL_TABLE, OPPORTUNITY_TABLE)
            if not self.data.table_exists(name)
        ]
        if missing:
            raise RuntimeError("Missing required table(s): " + ", ".join(missing))

    def columns(self, table: str) -> list[str]:
        if table not in self._columns:
            rows = self.data.fetch_all(f"PRAGMA table_info({qi(table)})")
            self._columns[table] = [str(row["name"]) for row in rows]
        return self._columns[table]

    def find_column(
        self,
        table: str,
        candidates: Sequence[str],
    ) -> str | None:
        available = set(self.columns(table))
        return next((name for name in candidates if name in available), None)

    def canonical_id_column(self) -> str:
        column = self.find_column(CANONICAL_TABLE, self.CONDITION_NAMES)
        if not column:
            raise RuntimeError("Canonical table has no condition ID column.")
        return column

    def opportunity_id_column(self) -> str:
        column = self.find_column(OPPORTUNITY_TABLE, self.CONDITION_NAMES)
        if not column:
            raise RuntimeError("Opportunity table has no writable market ID column.")
        return column

    def canonical_id(self, row: Mapping[str, Any]) -> str:
        return norm(first(row, self.CONDITION_NAMES))

    def direct_lookup(self, condition_id: str) -> dict[str, Any] | None:
        column = self.canonical_id_column()
        return self.data.fetch_one(
            f"""
            SELECT *
            FROM {qi(CANONICAL_TABLE)}
            WHERE LOWER(TRIM(CAST({qi(column)} AS TEXT))) = LOWER(TRIM(?))
            LIMIT 1
            """,
            (condition_id,),
        )

    def exact_matches(
        self,
        candidates: Sequence[str],
        value: str,
    ) -> list[dict[str, Any]]:
        if not value:
            return []
        column = self.find_column(CANONICAL_TABLE, candidates)
        if not column:
            return []
        return self.data.fetch_all(
            f"""
            SELECT *
            FROM {qi(CANONICAL_TABLE)}
            WHERE LOWER(TRIM(CAST({qi(column)} AS TEXT))) = LOWER(TRIM(?))
            """,
            (value,),
        )

    def token_matches(self, token_id: str) -> list[dict[str, Any]]:
        if not token_id:
            return []
        available = set(self.columns(CANONICAL_TABLE))
        token_columns = [
            name
            for name in (
                "yes_token_id",
                "no_token_id",
                "token_id",
                "clob_token_id",
                "token_ids",
                "clob_token_ids",
            )
            if name in available
        ]
        found: dict[str, dict[str, Any]] = {}
        for column in token_columns:
            rows = self.data.fetch_all(
                f"""
                SELECT *
                FROM {qi(CANONICAL_TABLE)}
                WHERE LOWER(CAST({qi(column)} AS TEXT)) LIKE LOWER(?)
                """,
                (f"%{token_id}%",),
            )
            for row in rows:
                condition_id = self.canonical_id(row)
                if condition_id:
                    found[condition_id] = row
        return list(found.values())

    def alias_matches(self, source_value: str) -> list[dict[str, Any]]:
        if not source_value or not self.data.table_exists(ALIAS_TABLE):
            return []

        alias_column = self.find_column(
            ALIAS_TABLE,
            ("alias", "alias_value", "external_id", "source_id"),
        )
        identity_column = self.find_column(
            ALIAS_TABLE,
            self.CONDITION_NAMES,
        )
        if not alias_column or not identity_column:
            return []

        alias_rows = self.data.fetch_all(
            f"""
            SELECT {qi(identity_column)} AS condition_id
            FROM {qi(ALIAS_TABLE)}
            WHERE LOWER(TRIM(CAST({qi(alias_column)} AS TEXT))) = LOWER(TRIM(?))
            """,
            (source_value,),
        )

        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for alias in alias_rows:
            condition_id = norm(alias.get("condition_id"))
            if not condition_id or condition_id in seen:
                continue
            canonical = self.direct_lookup(condition_id)
            if canonical:
                results.append(canonical)
                seen.add(condition_id)
        return results

    def make_resolution(
        self,
        matches: list[dict[str, Any]],
        *,
        source_market_id: str,
        method: str,
        matched_value: str,
        confidence: float,
    ) -> Resolution | None:
        unique = {
            self.canonical_id(row): row
            for row in matches
            if self.canonical_id(row)
        }
        if not unique:
            return None
        if len(unique) > 1:
            return Resolution(
                status="AMBIGUOUS",
                source_market_id=source_market_id,
                method=method,
                matched_value=matched_value,
                details={"candidate_condition_ids": sorted(unique)},
            )
        canonical_condition_id = next(iter(unique))
        return Resolution(
            status="RESOLVED",
            source_market_id=source_market_id,
            canonical_condition_id=canonical_condition_id,
            method=method,
            matched_value=matched_value,
            confidence=confidence,
        )

    def resolve(self, row: Mapping[str, Any]) -> Resolution:
        source_market_id = norm(first(row, self.CONDITION_NAMES))

        if source_market_id:
            direct = self.direct_lookup(source_market_id)
            if direct:
                return Resolution(
                    status="ALREADY_CANONICAL",
                    source_market_id=source_market_id,
                    canonical_condition_id=self.canonical_id(direct),
                    method="condition_id",
                    matched_value=source_market_id,
                    confidence=1.0,
                )

            result = self.make_resolution(
                self.alias_matches(source_market_id),
                source_market_id=source_market_id,
                method="alias",
                matched_value=source_market_id,
                confidence=0.99,
            )
            if result:
                return result

        gamma_id = text(first(row, self.GAMMA_NAMES))
        if gamma_id:
            result = self.make_resolution(
                self.exact_matches(
                    ("gamma_market_id", "gamma_id", "id"),
                    gamma_id,
                ),
                source_market_id=source_market_id,
                method="gamma_market_id",
                matched_value=gamma_id,
                confidence=0.99,
            )
            if result:
                return result

        token_id = text(first(row, self.TOKEN_NAMES))
        if token_id:
            result = self.make_resolution(
                self.token_matches(token_id),
                source_market_id=source_market_id,
                method="token_id",
                matched_value=token_id,
                confidence=0.98,
            )
            if result:
                return result

        slug = text(first(row, self.SLUG_NAMES))
        if slug:
            result = self.make_resolution(
                self.exact_matches(("market_slug", "slug"), slug),
                source_market_id=source_market_id,
                method="market_slug",
                matched_value=slug,
                confidence=0.95,
            )
            if result:
                return result

        title = text(first(row, self.TITLE_NAMES))
        if title:
            result = self.make_resolution(
                self.exact_matches(("question", "title"), title),
                source_market_id=source_market_id,
                method="question",
                matched_value=title,
                confidence=0.90,
            )
            if result:
                return result

        return Resolution(
            status="ORPHANED",
            source_market_id=source_market_id,
            details={
                "gamma_market_id": gamma_id,
                "token_id": token_id,
                "slug": slug,
                "title": title,
            },
        )

    def load_rows(self, limit: int | None) -> list[dict[str, Any]]:
        sql = f"SELECT rowid AS __rowid__, * FROM {qi(OPPORTUNITY_TABLE)} ORDER BY rowid"
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (max(1, int(limit)),)
        return self.data.fetch_all(sql, params)

    def repair(self, rowid: int, canonical_condition_id: str) -> int:
        column = self.opportunity_id_column()
        return self.data.execute(
            f"""
            UPDATE {qi(OPPORTUNITY_TABLE)}
            SET {qi(column)} = ?
            WHERE rowid = ?
            """,
            (canonical_condition_id, rowid),
        )

    def create_run(self, details: Mapping[str, Any]) -> str:
        run_id = uuid.uuid4().hex
        self.data.execute(
            f"""
            INSERT INTO {RUN_TABLE}(run_id, started_at, status, details_json)
            VALUES (?, ?, 'RUNNING', ?)
            """,
            (run_id, utc_now_iso(), dump_json(details)),
        )
        return run_id

    def audit(
        self,
        run_id: str,
        row: Mapping[str, Any],
        resolution: Resolution,
        repaired: bool,
    ) -> None:
        self.data.execute(
            f"""
            INSERT INTO {AUDIT_TABLE}(
                run_id,
                opportunity_rowid,
                source_market_id,
                source_outcome,
                status,
                canonical_condition_id,
                match_method,
                match_value,
                confidence,
                repaired,
                details_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row.get("__rowid__"),
                resolution.source_market_id,
                text(first(row, self.OUTCOME_NAMES)) or "UNKNOWN",
                resolution.status,
                resolution.canonical_condition_id,
                resolution.method,
                resolution.matched_value,
                resolution.confidence,
                1 if repaired else 0,
                dump_json(resolution.details),
                utc_now_iso(),
            ),
        )

    def finish_run(
        self,
        summary: SyncSummary,
        error_message: str | None = None,
    ) -> None:
        self.data.execute(
            f"""
            UPDATE {RUN_TABLE}
            SET
                finished_at = ?,
                duration_seconds = ?,
                source_rows = ?,
                resolved_rows = ?,
                already_canonical_rows = ?,
                repaired_rows = ?,
                ambiguous_rows = ?,
                orphaned_rows = ?,
                skipped_rows = ?,
                error_count = ?,
                success = ?,
                status = ?,
                error_message = ?,
                details_json = ?
            WHERE run_id = ?
            """,
            (
                summary.finished_at,
                summary.duration_seconds,
                summary.source_rows,
                summary.resolved_rows,
                summary.already_canonical_rows,
                summary.repaired_rows,
                summary.ambiguous_rows,
                summary.orphaned_rows,
                summary.skipped_rows,
                summary.error_count,
                1 if summary.success else 0,
                "SUCCESS" if summary.success else "COMPLETED_WITH_ERRORS",
                error_message,
                dump_json({"errors": summary.errors[:100]}),
                summary.run_id,
            ),
        )

    def synchronize(
        self,
        *,
        limit: int | None = None,
        dry_run: bool = True,
        continue_on_error: bool = True,
    ) -> SyncSummary:
        self.initialize_schema()
        self.validate()

        rows = self.load_rows(limit)
        run_id = self.create_run({"limit": limit, "dry_run": dry_run})
        summary = SyncSummary(run_id=run_id, source_rows=len(rows))
        started = time.perf_counter()

        try:
            for row in rows:
                try:
                    resolution = self.resolve(row)
                    repaired = False

                    if resolution.status == "ALREADY_CANONICAL":
                        summary.already_canonical_rows += 1
                        summary.resolved_rows += 1

                    elif resolution.status == "RESOLVED":
                        summary.resolved_rows += 1
                        if dry_run:
                            summary.repaired_rows += 1
                        else:
                            affected = self.repair(
                                int(row["__rowid__"]),
                                str(resolution.canonical_condition_id),
                            )
                            repaired = affected > 0
                            if repaired:
                                summary.repaired_rows += 1
                            else:
                                summary.skipped_rows += 1

                    elif resolution.status == "AMBIGUOUS":
                        summary.ambiguous_rows += 1

                    elif resolution.status == "ORPHANED":
                        summary.orphaned_rows += 1

                    else:
                        summary.skipped_rows += 1

                    self.audit(run_id, row, resolution, repaired)

                except Exception as error:
                    summary.error_count += 1
                    message = (
                        f"rowid={row.get('__rowid__')} "
                        f"market={first(row, self.CONDITION_NAMES)} "
                        f"error={error}"
                    )
                    summary.errors.append(message)
                    LOGGER.exception("Identity synchronization row failed.")
                    if not continue_on_error:
                        raise

            summary.finished_at = utc_now_iso()
            summary.duration_seconds = time.perf_counter() - started
            self.finish_run(summary)
            return summary

        except Exception as error:
            summary.error_count = max(1, summary.error_count)
            summary.errors.append(str(error))
            summary.finished_at = utc_now_iso()
            summary.duration_seconds = time.perf_counter() - started
            self.finish_run(summary, str(error))
            raise

    def unresolved(
        self,
        run_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return self.data.fetch_all(
            f"""
            SELECT *
            FROM {AUDIT_TABLE}
            WHERE run_id = ?
              AND status IN ('AMBIGUOUS', 'ORPHANED')
            ORDER BY id
            LIMIT ?
            """,
            (run_id, max(1, int(limit))),
        )

    def print_summary(self, summary: SyncSummary, dry_run: bool) -> None:
        print()
        print("=" * 108)
        print("CANONICAL IDENTITY SYNCHRONIZER")
        print("=" * 108)
        print(f"Database:             {self.database_path}")
        print(f"Mode:                 {'DRY RUN' if dry_run else 'APPLY'}")
        print(f"Run ID:               {summary.run_id}")
        print(f"Opportunity rows:     {summary.source_rows}")
        print(f"Resolved total:       {summary.resolved_rows}")
        print(f"Already canonical:    {summary.already_canonical_rows}")
        print(f"Repairable/repaired:  {summary.repaired_rows}")
        print(f"Ambiguous:            {summary.ambiguous_rows}")
        print(f"Orphaned:             {summary.orphaned_rows}")
        print(f"Skipped:              {summary.skipped_rows}")
        print(f"Errors:               {summary.error_count}")
        print(f"Duration:             {summary.duration_seconds:.3f} seconds")
        print(
            f"Status:               "
            f"{'SUCCESS' if summary.success else 'COMPLETED WITH ERRORS'}"
        )

        preview = self.unresolved(summary.run_id)
        if preview:
            print()
            print("UNRESOLVED PREVIEW")
            print("-" * 108)
            for row in preview:
                print(
                    f"{row.get('source_market_id') or 'UNKNOWN'} | "
                    f"{row.get('source_outcome') or 'UNKNOWN'} | "
                    f"{row.get('status')}"
                )
        print("=" * 108)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize master opportunity market IDs with canonical identities."
        )
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply unambiguous repairs. Default is dry-run.",
    )
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    synchronizer = CanonicalIdentitySynchronizer()
    summary = synchronizer.synchronize(
        limit=args.limit,
        dry_run=not args.apply,
        continue_on_error=not args.fail_fast,
    )
    synchronizer.print_summary(summary, dry_run=not args.apply)


if __name__ == "__main__":
    main()