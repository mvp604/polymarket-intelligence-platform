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
AUDIT_TABLE = "canonical_coverage_audit"
RUN_TABLE = "canonical_coverage_audit_runs"
SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def json_dumps(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


@dataclass(slots=True)
class CoverageSummary:
    run_id: str
    canonical_rows: int = 0
    canonical_unique_markets: int = 0
    tradable_canonical_markets: int = 0
    opportunity_rows: int = 0
    opportunity_unique_markets: int = 0
    matched_opportunity_rows: int = 0
    orphaned_opportunity_rows: int = 0
    matched_unique_markets: int = 0
    orphaned_unique_markets: int = 0
    canonical_without_opportunities: int = 0
    tradable_without_opportunities: int = 0
    coverage_percent_rows: float = 0.0
    coverage_percent_unique_markets: float = 0.0
    likely_pipeline_bypass_rows: int = 0
    likely_missing_canonical_import_rows: int = 0
    indeterminate_rows: int = 0
    duplicate_opportunity_groups: int = 0
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


class CanonicalCoverageAudit:
    """
    Compare canonical market coverage against master opportunity coverage.

    This module is intentionally read-only with respect to source tables.
    It writes only audit and run-history records.
    """

    CONDITION_ID_CANDIDATES = (
        "condition_id",
        "canonical_condition_id",
        "market_id",
        "conditionId",
    )
    TITLE_CANDIDATES = (
        "question",
        "title",
        "market_title",
        "market_question",
    )
    SLUG_CANDIDATES = (
        "slug",
        "market_slug",
        "marketSlug",
    )
    GAMMA_ID_CANDIDATES = (
        "gamma_market_id",
        "gamma_id",
        "gammaMarketId",
    )
    OUTCOME_CANDIDATES = (
        "outcome",
        "selected_outcome",
        "side",
    )
    TRADABLE_CANDIDATES = (
        "tradable_identity",
        "tradable",
        "is_tradable",
    )

    def __init__(
        self,
        data_access: DataAccess | None = None,
        database_path: Path | str = DATABASE_PATH,
    ) -> None:
        self.data = data_access or DataAccess(database_path)
        self.database_path = Path(self.data.database_path)
        self._columns_cache: dict[str, list[str]] = {}

    def initialize_schema(self) -> None:
        statements = [
            f"""
            CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                opportunity_rowid INTEGER,
                opportunity_condition_id TEXT,
                opportunity_outcome TEXT,
                opportunity_title TEXT,
                opportunity_slug TEXT,
                opportunity_gamma_id TEXT,
                coverage_status TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                canonical_condition_id TEXT,
                canonical_title TEXT,
                evidence_json TEXT NOT NULL DEFAULT '{{}}',
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
                canonical_rows INTEGER NOT NULL DEFAULT 0,
                canonical_unique_markets INTEGER NOT NULL DEFAULT 0,
                tradable_canonical_markets INTEGER NOT NULL DEFAULT 0,
                opportunity_rows INTEGER NOT NULL DEFAULT 0,
                opportunity_unique_markets INTEGER NOT NULL DEFAULT 0,
                matched_opportunity_rows INTEGER NOT NULL DEFAULT 0,
                orphaned_opportunity_rows INTEGER NOT NULL DEFAULT 0,
                matched_unique_markets INTEGER NOT NULL DEFAULT 0,
                orphaned_unique_markets INTEGER NOT NULL DEFAULT 0,
                canonical_without_opportunities INTEGER NOT NULL DEFAULT 0,
                tradable_without_opportunities INTEGER NOT NULL DEFAULT 0,
                coverage_percent_rows REAL NOT NULL DEFAULT 0,
                coverage_percent_unique_markets REAL NOT NULL DEFAULT 0,
                likely_pipeline_bypass_rows INTEGER NOT NULL DEFAULT 0,
                likely_missing_canonical_import_rows INTEGER NOT NULL DEFAULT 0,
                indeterminate_rows INTEGER NOT NULL DEFAULT 0,
                duplicate_opportunity_groups INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                success INTEGER,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                details_json TEXT NOT NULL DEFAULT '{{}}',
                schema_version INTEGER NOT NULL DEFAULT {SCHEMA_VERSION}
            )
            """,
            f"""
            CREATE INDEX IF NOT EXISTS idx_coverage_audit_run
            ON {AUDIT_TABLE}(run_id)
            """,
            f"""
            CREATE INDEX IF NOT EXISTS idx_coverage_audit_status
            ON {AUDIT_TABLE}(coverage_status, diagnosis)
            """,
            f"""
            CREATE INDEX IF NOT EXISTS idx_coverage_audit_condition
            ON {AUDIT_TABLE}(opportunity_condition_id)
            """,
            f"""
            CREATE INDEX IF NOT EXISTS idx_coverage_runs_started
            ON {RUN_TABLE}(started_at DESC)
            """,
        ]

        with self.data.transaction() as connection:
            for statement in statements:
                connection.execute(statement)

    def validate_prerequisites(self) -> None:
        missing = [
            table
            for table in (CANONICAL_TABLE, OPPORTUNITY_TABLE)
            if not self.data.table_exists(table)
        ]
        if missing:
            raise RuntimeError(
                "Missing required table(s): " + ", ".join(missing)
            )

    def table_columns(self, table_name: str) -> list[str]:
        if table_name not in self._columns_cache:
            rows = self.data.fetch_all(
                f"PRAGMA table_info({quote_identifier(table_name)})"
            )
            self._columns_cache[table_name] = [
                str(row["name"]) for row in rows
            ]
        return self._columns_cache[table_name]

    def first_existing_column(
        self,
        table_name: str,
        candidates: Sequence[str],
    ) -> str | None:
        available = set(self.table_columns(table_name))
        return next(
            (candidate for candidate in candidates if candidate in available),
            None,
        )

    def value_from(
        self,
        row: Mapping[str, Any],
        candidates: Sequence[str],
    ) -> Any:
        for candidate in candidates:
            value = row.get(candidate)
            if value not in (None, ""):
                return value
        return None

    def canonical_condition_id(
        self,
        row: Mapping[str, Any],
    ) -> str:
        return normalize(
            self.value_from(row, self.CONDITION_ID_CANDIDATES)
        )

    def load_canonical_rows(self) -> list[dict[str, Any]]:
        return self.data.fetch_all(
            f"SELECT * FROM {quote_identifier(CANONICAL_TABLE)}"
        )

    def load_opportunity_rows(
        self,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        sql = (
            f"SELECT rowid AS __rowid__, * "
            f"FROM {quote_identifier(OPPORTUNITY_TABLE)} "
            "ORDER BY rowid"
        )
        parameters: tuple[Any, ...] = ()

        if limit is not None:
            sql += " LIMIT ?"
            parameters = (max(1, int(limit)),)

        return self.data.fetch_all(sql, parameters)

    def create_run(
        self,
        *,
        limit: int | None,
    ) -> str:
        run_id = uuid.uuid4().hex
        self.data.execute(
            f"""
            INSERT INTO {RUN_TABLE} (
                run_id,
                started_at,
                status,
                details_json
            )
            VALUES (?, ?, 'RUNNING', ?)
            """,
            (
                run_id,
                utc_now_iso(),
                json_dumps({"limit": limit}),
            ),
        )
        return run_id

    def finish_run(self, summary: CoverageSummary) -> None:
        self.data.execute(
            f"""
            UPDATE {RUN_TABLE}
            SET
                finished_at = ?,
                duration_seconds = ?,
                canonical_rows = ?,
                canonical_unique_markets = ?,
                tradable_canonical_markets = ?,
                opportunity_rows = ?,
                opportunity_unique_markets = ?,
                matched_opportunity_rows = ?,
                orphaned_opportunity_rows = ?,
                matched_unique_markets = ?,
                orphaned_unique_markets = ?,
                canonical_without_opportunities = ?,
                tradable_without_opportunities = ?,
                coverage_percent_rows = ?,
                coverage_percent_unique_markets = ?,
                likely_pipeline_bypass_rows = ?,
                likely_missing_canonical_import_rows = ?,
                indeterminate_rows = ?,
                duplicate_opportunity_groups = ?,
                error_count = ?,
                success = ?,
                status = ?,
                details_json = ?
            WHERE run_id = ?
            """,
            (
                summary.finished_at,
                summary.duration_seconds,
                summary.canonical_rows,
                summary.canonical_unique_markets,
                summary.tradable_canonical_markets,
                summary.opportunity_rows,
                summary.opportunity_unique_markets,
                summary.matched_opportunity_rows,
                summary.orphaned_opportunity_rows,
                summary.matched_unique_markets,
                summary.orphaned_unique_markets,
                summary.canonical_without_opportunities,
                summary.tradable_without_opportunities,
                summary.coverage_percent_rows,
                summary.coverage_percent_unique_markets,
                summary.likely_pipeline_bypass_rows,
                summary.likely_missing_canonical_import_rows,
                summary.indeterminate_rows,
                summary.duplicate_opportunity_groups,
                summary.error_count,
                1 if summary.success else 0,
                "SUCCESS" if summary.success else "COMPLETED_WITH_ERRORS",
                json_dumps({"errors": summary.errors[:100]}),
                summary.run_id,
            ),
        )

    def build_indexes(
        self,
        canonical_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        by_condition: dict[str, dict[str, Any]] = {}
        by_gamma: dict[str, set[str]] = {}
        by_slug: dict[str, set[str]] = {}
        by_title: dict[str, set[str]] = {}
        tradable_ids: set[str] = set()

        for row in canonical_rows:
            condition_id = self.canonical_condition_id(row)
            if not condition_id:
                continue

            by_condition[condition_id] = row

            gamma_id = normalize(
                self.value_from(row, self.GAMMA_ID_CANDIDATES)
            )
            slug = normalize(
                self.value_from(row, self.SLUG_CANDIDATES)
            )
            title = normalize(
                self.value_from(row, self.TITLE_CANDIDATES)
            )

            if gamma_id:
                by_gamma.setdefault(gamma_id, set()).add(condition_id)
            if slug:
                by_slug.setdefault(slug, set()).add(condition_id)
            if title:
                by_title.setdefault(title, set()).add(condition_id)

            tradable_value = self.value_from(
                row,
                self.TRADABLE_CANDIDATES,
            )
            try:
                if int(tradable_value or 0) == 1:
                    tradable_ids.add(condition_id)
            except (TypeError, ValueError):
                pass

        return {
            "by_condition": by_condition,
            "by_gamma": by_gamma,
            "by_slug": by_slug,
            "by_title": by_title,
            "tradable_ids": tradable_ids,
        }

    def diagnose_row(
        self,
        row: Mapping[str, Any],
        indexes: Mapping[str, Any],
    ) -> dict[str, Any]:
        source_condition_id = normalize(
            self.value_from(row, self.CONDITION_ID_CANDIDATES)
        )
        source_gamma_id = normalize(
            self.value_from(row, self.GAMMA_ID_CANDIDATES)
        )
        source_slug = normalize(
            self.value_from(row, self.SLUG_CANDIDATES)
        )
        source_title = normalize(
            self.value_from(row, self.TITLE_CANDIDATES)
        )

        by_condition = indexes["by_condition"]
        by_gamma = indexes["by_gamma"]
        by_slug = indexes["by_slug"]
        by_title = indexes["by_title"]

        if source_condition_id in by_condition:
            canonical = by_condition[source_condition_id]
            return {
                "coverage_status": "MATCHED",
                "diagnosis": "CANONICAL_MATCH",
                "canonical_condition_id": source_condition_id,
                "canonical": canonical,
                "evidence": {"method": "condition_id"},
            }

        candidate_sets: list[tuple[str, set[str]]] = []

        if source_gamma_id and source_gamma_id in by_gamma:
            candidate_sets.append(
                ("gamma_market_id", set(by_gamma[source_gamma_id]))
            )

        if source_slug and source_slug in by_slug:
            candidate_sets.append(
                ("slug", set(by_slug[source_slug]))
            )

        if source_title and source_title in by_title:
            candidate_sets.append(
                ("title", set(by_title[source_title]))
            )

        all_candidates: set[str] = set()
        evidence: dict[str, Any] = {}

        for method, candidates in candidate_sets:
            all_candidates.update(candidates)
            evidence[method] = sorted(candidates)

        if len(all_candidates) == 1:
            canonical_id = next(iter(all_candidates))
            return {
                "coverage_status": "ORPHANED",
                "diagnosis": "LIKELY_PIPELINE_BYPASS",
                "canonical_condition_id": canonical_id,
                "canonical": by_condition.get(canonical_id),
                "evidence": evidence,
            }

        if len(all_candidates) > 1:
            return {
                "coverage_status": "ORPHANED",
                "diagnosis": "INDETERMINATE_MULTIPLE_CANDIDATES",
                "canonical_condition_id": None,
                "canonical": None,
                "evidence": evidence,
            }

        has_alternate_identity = any(
            (source_gamma_id, source_slug, source_title)
        )

        diagnosis = (
            "LIKELY_MISSING_CANONICAL_IMPORT"
            if has_alternate_identity
            else "INDETERMINATE_NO_ALTERNATE_IDENTITY"
        )

        return {
            "coverage_status": "ORPHANED",
            "diagnosis": diagnosis,
            "canonical_condition_id": None,
            "canonical": None,
            "evidence": {
                "source_gamma_id": source_gamma_id or None,
                "source_slug": source_slug or None,
                "source_title": source_title or None,
            },
        }

    def write_audit_row(
        self,
        *,
        run_id: str,
        opportunity: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> None:
        canonical = result.get("canonical") or {}

        self.data.execute(
            f"""
            INSERT INTO {AUDIT_TABLE} (
                run_id,
                opportunity_rowid,
                opportunity_condition_id,
                opportunity_outcome,
                opportunity_title,
                opportunity_slug,
                opportunity_gamma_id,
                coverage_status,
                diagnosis,
                canonical_condition_id,
                canonical_title,
                evidence_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                opportunity.get("__rowid__"),
                normalize(
                    self.value_from(
                        opportunity,
                        self.CONDITION_ID_CANDIDATES,
                    )
                ),
                str(
                    self.value_from(
                        opportunity,
                        self.OUTCOME_CANDIDATES,
                    )
                    or "UNKNOWN"
                ),
                str(
                    self.value_from(
                        opportunity,
                        self.TITLE_CANDIDATES,
                    )
                    or ""
                ),
                str(
                    self.value_from(
                        opportunity,
                        self.SLUG_CANDIDATES,
                    )
                    or ""
                ),
                str(
                    self.value_from(
                        opportunity,
                        self.GAMMA_ID_CANDIDATES,
                    )
                    or ""
                ),
                result["coverage_status"],
                result["diagnosis"],
                result.get("canonical_condition_id"),
                str(
                    self.value_from(
                        canonical,
                        self.TITLE_CANDIDATES,
                    )
                    or ""
                ),
                json_dumps(result.get("evidence", {})),
                utc_now_iso(),
            ),
        )

    def count_duplicate_opportunity_groups(
        self,
        opportunity_rows: list[dict[str, Any]],
    ) -> int:
        groups: dict[tuple[str, str], int] = {}

        for row in opportunity_rows:
            condition_id = normalize(
                self.value_from(row, self.CONDITION_ID_CANDIDATES)
            )
            outcome = normalize(
                self.value_from(row, self.OUTCOME_CANDIDATES)
            )
            key = (condition_id, outcome)
            groups[key] = groups.get(key, 0) + 1

        return sum(1 for count in groups.values() if count > 1)

    def run(
        self,
        *,
        limit: int | None = None,
    ) -> CoverageSummary:
        self.initialize_schema()
        self.validate_prerequisites()

        run_id = self.create_run(limit=limit)
        summary = CoverageSummary(run_id=run_id)
        started = time.perf_counter()

        try:
            canonical_rows = self.load_canonical_rows()
            opportunity_rows = self.load_opportunity_rows(limit=limit)
            indexes = self.build_indexes(canonical_rows)

            canonical_ids = set(indexes["by_condition"])
            tradable_ids = set(indexes["tradable_ids"])

            summary.canonical_rows = len(canonical_rows)
            summary.canonical_unique_markets = len(canonical_ids)
            summary.tradable_canonical_markets = len(tradable_ids)
            summary.opportunity_rows = len(opportunity_rows)
            summary.duplicate_opportunity_groups = (
                self.count_duplicate_opportunity_groups(
                    opportunity_rows
                )
            )

            opportunity_ids: set[str] = set()
            matched_ids: set[str] = set()
            orphaned_ids: set[str] = set()

            for opportunity in opportunity_rows:
                source_id = normalize(
                    self.value_from(
                        opportunity,
                        self.CONDITION_ID_CANDIDATES,
                    )
                )
                if source_id:
                    opportunity_ids.add(source_id)

                result = self.diagnose_row(
                    opportunity,
                    indexes,
                )
                self.write_audit_row(
                    run_id=run_id,
                    opportunity=opportunity,
                    result=result,
                )

                if result["coverage_status"] == "MATCHED":
                    summary.matched_opportunity_rows += 1
                    if source_id:
                        matched_ids.add(source_id)
                else:
                    summary.orphaned_opportunity_rows += 1
                    if source_id:
                        orphaned_ids.add(source_id)

                    diagnosis = result["diagnosis"]
                    if diagnosis == "LIKELY_PIPELINE_BYPASS":
                        summary.likely_pipeline_bypass_rows += 1
                    elif diagnosis == "LIKELY_MISSING_CANONICAL_IMPORT":
                        summary.likely_missing_canonical_import_rows += 1
                    else:
                        summary.indeterminate_rows += 1

            summary.opportunity_unique_markets = len(opportunity_ids)
            summary.matched_unique_markets = len(matched_ids)
            summary.orphaned_unique_markets = len(orphaned_ids)

            canonical_with_opportunities = canonical_ids.intersection(
                opportunity_ids
            )
            tradable_with_opportunities = tradable_ids.intersection(
                opportunity_ids
            )

            summary.canonical_without_opportunities = (
                len(canonical_ids - canonical_with_opportunities)
            )
            summary.tradable_without_opportunities = (
                len(tradable_ids - tradable_with_opportunities)
            )

            if summary.opportunity_rows:
                summary.coverage_percent_rows = round(
                    100.0
                    * summary.matched_opportunity_rows
                    / summary.opportunity_rows,
                    4,
                )

            if summary.opportunity_unique_markets:
                summary.coverage_percent_unique_markets = round(
                    100.0
                    * summary.matched_unique_markets
                    / summary.opportunity_unique_markets,
                    4,
                )

            summary.finished_at = utc_now_iso()
            summary.duration_seconds = time.perf_counter() - started
            self.finish_run(summary)
            return summary

        except Exception as error:
            summary.error_count += 1
            summary.errors.append(str(error))
            summary.finished_at = utc_now_iso()
            summary.duration_seconds = time.perf_counter() - started
            self.finish_run(summary)
            raise

    def diagnosis_counts(
        self,
        run_id: str,
    ) -> list[dict[str, Any]]:
        return self.data.fetch_all(
            f"""
            SELECT
                diagnosis,
                COUNT(*) AS row_count
            FROM {AUDIT_TABLE}
            WHERE run_id = ?
            GROUP BY diagnosis
            ORDER BY row_count DESC, diagnosis
            """,
            (run_id,),
        )

    def orphan_preview(
        self,
        run_id: str,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        return self.data.fetch_all(
            f"""
            SELECT
                opportunity_condition_id,
                opportunity_outcome,
                opportunity_title,
                diagnosis,
                canonical_condition_id
            FROM {AUDIT_TABLE}
            WHERE run_id = ?
              AND coverage_status = 'ORPHANED'
            ORDER BY id
            LIMIT ?
            """,
            (run_id, max(1, int(limit))),
        )

    def print_summary(self, summary: CoverageSummary) -> None:
        print()
        print("=" * 112)
        print("CANONICAL COVERAGE AUDIT")
        print("=" * 112)
        print(f"Database:                         {self.database_path}")
        print(f"Run ID:                           {summary.run_id}")
        print(f"Canonical rows:                   {summary.canonical_rows}")
        print(f"Canonical unique markets:         {summary.canonical_unique_markets}")
        print(f"Tradable canonical markets:       {summary.tradable_canonical_markets}")
        print(f"Opportunity rows:                 {summary.opportunity_rows}")
        print(f"Opportunity unique markets:       {summary.opportunity_unique_markets}")
        print(f"Matched opportunity rows:         {summary.matched_opportunity_rows}")
        print(f"Orphaned opportunity rows:        {summary.orphaned_opportunity_rows}")
        print(f"Matched unique markets:           {summary.matched_unique_markets}")
        print(f"Orphaned unique markets:          {summary.orphaned_unique_markets}")
        print(f"Row coverage:                     {summary.coverage_percent_rows:.2f}%")
        print(
            f"Unique-market coverage:           "
            f"{summary.coverage_percent_unique_markets:.2f}%"
        )
        print(
            f"Canonical without opportunities:  "
            f"{summary.canonical_without_opportunities}"
        )
        print(
            f"Tradable without opportunities:   "
            f"{summary.tradable_without_opportunities}"
        )
        print(
            f"Likely pipeline bypass rows:       "
            f"{summary.likely_pipeline_bypass_rows}"
        )
        print(
            f"Likely missing canonical imports:  "
            f"{summary.likely_missing_canonical_import_rows}"
        )
        print(f"Indeterminate orphan rows:         {summary.indeterminate_rows}")
        print(
            f"Duplicate opportunity groups:      "
            f"{summary.duplicate_opportunity_groups}"
        )
        print(f"Errors:                            {summary.error_count}")
        print(f"Duration:                          {summary.duration_seconds:.3f}s")
        print(
            f"Status:                            "
            f"{'SUCCESS' if summary.success else 'COMPLETED WITH ERRORS'}"
        )

        counts = self.diagnosis_counts(summary.run_id)
        if counts:
            print()
            print("DIAGNOSIS COUNTS")
            print("-" * 112)
            for item in counts:
                print(
                    f"{item['diagnosis']:<44} "
                    f"{item['row_count']:>8}"
                )

        preview = self.orphan_preview(summary.run_id)
        if preview:
            print()
            print("ORPHAN PREVIEW")
            print("-" * 112)
            for item in preview:
                title = item.get("opportunity_title") or ""
                print(
                    f"{item.get('opportunity_condition_id') or 'UNKNOWN'} | "
                    f"{item.get('opportunity_outcome') or 'UNKNOWN'} | "
                    f"{item.get('diagnosis')} | "
                    f"{title[:50]}"
                )

        print("=" * 112)


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit coverage between canonical_market_identities "
            "and master_opportunities."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of opportunity rows.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    audit = CanonicalCoverageAudit()
    summary = audit.run(limit=args.limit)
    audit.print_summary(summary)


if __name__ == "__main__":
    main()