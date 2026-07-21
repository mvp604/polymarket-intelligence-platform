from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from data_access import DataAccess, DATABASE_PATH
except ImportError:
    from src.data_access import DataAccess, DATABASE_PATH


LOGGER = logging.getLogger(__name__)

CANONICAL_TABLE = "canonical_market_identities"
RUN_TABLE = "canonical_identity_refresh_runs"
AUDIT_TABLE = "canonical_identity_refresh_audit"

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
DEFAULT_PAGE_SIZE = 500
DEFAULT_TIMEOUT_SECONDS = 30
SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_id(value: Any) -> str:
    return normalize_text(value).lower()


def to_int_bool(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(bool(value))
    text = normalize_text(value).lower()
    return int(text in {"1", "true", "yes", "y", "on"})


def parse_json_like(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if value in (None, ""):
        return None
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return value


def json_dumps(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def first_present(
    row: Mapping[str, Any],
    candidates: Sequence[str],
    default: Any = None,
) -> Any:
    for candidate in candidates:
        value = row.get(candidate)
        if value not in (None, ""):
            return value
    return default


def ensure_list(value: Any) -> list[Any]:
    parsed = parse_json_like(value)
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    return [parsed]


def pair_outcomes_with_tokens(
    outcomes_value: Any,
    token_ids_value: Any,
) -> tuple[str | None, str | None]:
    outcomes = [normalize_text(item) for item in ensure_list(outcomes_value)]
    token_ids = [normalize_text(item) for item in ensure_list(token_ids_value)]

    yes_token_id: str | None = None
    no_token_id: str | None = None

    for index, outcome in enumerate(outcomes):
        if index >= len(token_ids):
            continue
        token_id = token_ids[index] or None
        normalized_outcome = outcome.lower()
        if normalized_outcome == "yes":
            yes_token_id = token_id
        elif normalized_outcome == "no":
            no_token_id = token_id

    if not yes_token_id and token_ids:
        yes_token_id = token_ids[0] or None
    if not no_token_id and len(token_ids) > 1:
        no_token_id = token_ids[1] or None

    return yes_token_id, no_token_id


@dataclass(slots=True)
class RefreshSummary:
    run_id: str
    fetched_rows: int = 0
    normalized_rows: int = 0
    unique_condition_ids: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0
    unchanged_rows: int = 0
    archived_rows: int = 0
    skipped_rows: int = 0
    duplicate_source_rows: int = 0
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


class GammaClient:
    def __init__(
        self,
        base_url: str = GAMMA_BASE_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = "Polymarket-Intelligence-Platform/1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def get_json(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        query = urllib.parse.urlencode(
            {
                key: value
                for key, value in (params or {}).items()
                if value is not None
            },
            doseq=True,
        )
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=self.timeout_seconds,
        ) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)

    def fetch_markets(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_pages: int | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        markets: list[dict[str, Any]] = []
        offset = 0
        page_number = 0

        while True:
            params: dict[str, Any] = {
                "limit": page_size,
                "offset": offset,
                "order": "id",
                "ascending": "true",
            }
            if active_only:
                params["active"] = "true"

            payload = self.get_json("/markets", params)
            if not isinstance(payload, list):
                raise RuntimeError(
                    "Gamma /markets returned an unexpected payload."
                )

            batch = [
                item for item in payload if isinstance(item, dict)
            ]
            markets.extend(batch)
            page_number += 1

            LOGGER.info(
                "Fetched Gamma page %s with %s markets.",
                page_number,
                len(batch),
            )

            if len(batch) < page_size:
                break

            if max_pages is not None and page_number >= max_pages:
                break

            offset += page_size

        return markets


class CanonicalIdentityRefreshEngine:
    CONDITION_ID_CANDIDATES = (
        "condition_id",
        "conditionId",
        "market_id",
        "canonical_condition_id",
    )

    def __init__(
        self,
        data_access: DataAccess | None = None,
        database_path: Path | str = DATABASE_PATH,
        gamma_client: GammaClient | None = None,
    ) -> None:
        self.data = data_access or DataAccess(database_path)
        self.database_path = Path(self.data.database_path)
        self.gamma = gamma_client or GammaClient()
        self._columns_cache: dict[str, list[str]] = {}

    def initialize_schema(self) -> None:
        statements = [
            f"""
            CREATE TABLE IF NOT EXISTS {RUN_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                fetched_rows INTEGER NOT NULL DEFAULT 0,
                normalized_rows INTEGER NOT NULL DEFAULT 0,
                unique_condition_ids INTEGER NOT NULL DEFAULT 0,
                inserted_rows INTEGER NOT NULL DEFAULT 0,
                updated_rows INTEGER NOT NULL DEFAULT 0,
                unchanged_rows INTEGER NOT NULL DEFAULT 0,
                archived_rows INTEGER NOT NULL DEFAULT 0,
                skipped_rows INTEGER NOT NULL DEFAULT 0,
                duplicate_source_rows INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                success INTEGER,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                details_json TEXT NOT NULL DEFAULT '{{}}',
                schema_version INTEGER NOT NULL DEFAULT {SCHEMA_VERSION}
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                condition_id TEXT,
                action TEXT NOT NULL,
                changed_columns_json TEXT NOT NULL DEFAULT '[]',
                source_json TEXT NOT NULL DEFAULT '{{}}',
                error_message TEXT,
                created_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT {SCHEMA_VERSION}
            )
            """,
            f"""
            CREATE INDEX IF NOT EXISTS idx_identity_refresh_runs_started
            ON {RUN_TABLE}(started_at DESC)
            """,
            f"""
            CREATE INDEX IF NOT EXISTS idx_identity_refresh_audit_run
            ON {AUDIT_TABLE}(run_id)
            """,
            f"""
            CREATE INDEX IF NOT EXISTS idx_identity_refresh_audit_condition
            ON {AUDIT_TABLE}(condition_id)
            """,
        ]

        with self.data.transaction() as connection:
            for statement in statements:
                connection.execute(statement)

    def validate_prerequisites(self) -> None:
        if not self.data.table_exists(CANONICAL_TABLE):
            raise RuntimeError(
                f"Required table missing: {CANONICAL_TABLE}"
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

    def canonical_condition_column(self) -> str:
        column = self.first_existing_column(
            CANONICAL_TABLE,
            self.CONDITION_ID_CANDIDATES,
        )
        if not column:
            raise RuntimeError(
                f"{CANONICAL_TABLE} has no condition ID column."
            )
        return column

    def create_run(self, details: Mapping[str, Any]) -> str:
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
            (run_id, utc_now_iso(), json_dumps(details)),
        )
        return run_id

    def finish_run(self, summary: RefreshSummary) -> None:
        self.data.execute(
            f"""
            UPDATE {RUN_TABLE}
            SET
                finished_at = ?,
                duration_seconds = ?,
                fetched_rows = ?,
                normalized_rows = ?,
                unique_condition_ids = ?,
                inserted_rows = ?,
                updated_rows = ?,
                unchanged_rows = ?,
                archived_rows = ?,
                skipped_rows = ?,
                duplicate_source_rows = ?,
                error_count = ?,
                success = ?,
                status = ?,
                details_json = ?
            WHERE run_id = ?
            """,
            (
                summary.finished_at,
                summary.duration_seconds,
                summary.fetched_rows,
                summary.normalized_rows,
                summary.unique_condition_ids,
                summary.inserted_rows,
                summary.updated_rows,
                summary.unchanged_rows,
                summary.archived_rows,
                summary.skipped_rows,
                summary.duplicate_source_rows,
                summary.error_count,
                1 if summary.success else 0,
                "SUCCESS" if summary.success else "COMPLETED_WITH_ERRORS",
                json_dumps({"errors": summary.errors[:100]}),
                summary.run_id,
            ),
        )

    def write_audit(
        self,
        *,
        run_id: str,
        condition_id: str | None,
        action: str,
        changed_columns: Iterable[str] = (),
        source: Mapping[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        self.data.execute(
            f"""
            INSERT INTO {AUDIT_TABLE} (
                run_id,
                condition_id,
                action,
                changed_columns_json,
                source_json,
                error_message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                condition_id,
                action,
                json_dumps(sorted(set(changed_columns))),
                json_dumps(source or {}),
                error_message,
                utc_now_iso(),
            ),
        )

    def normalize_market(
        self,
        market: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        condition_id = normalize_id(
            first_present(
                market,
                ("conditionId", "condition_id", "condition"),
            )
        )
        if not condition_id:
            return None

        outcomes = first_present(
            market,
            ("outcomes", "outcomeNames"),
        )
        token_ids = first_present(
            market,
            ("clobTokenIds", "tokenIds", "tokens"),
        )
        yes_token_id, no_token_id = pair_outcomes_with_tokens(
            outcomes,
            token_ids,
        )

        active = to_int_bool(market.get("active"))
        closed = to_int_bool(market.get("closed"))
        archived = to_int_bool(market.get("archived"))
        restricted = to_int_bool(market.get("restricted"))

        tradable_identity = int(
            active == 1
            and closed == 0
            and archived == 0
        )

        normalized = {
            "condition_id": condition_id,
            "gamma_market_id": normalize_text(
                first_present(market, ("id", "marketId"))
            ),
            "question": normalize_text(
                first_present(market, ("question", "title"))
            ),
            "title": normalize_text(
                first_present(market, ("question", "title"))
            ),
            "slug": normalize_text(
                first_present(market, ("slug", "marketSlug"))
            ),
            "market_slug": normalize_text(
                first_present(market, ("slug", "marketSlug"))
            ),
            "event_slug": normalize_text(
                first_present(market, ("eventSlug",))
            ),
            "description": normalize_text(market.get("description")),
            "category": normalize_text(
                first_present(market, ("category", "groupItemTitle"))
            ),
            "active": active,
            "closed": closed,
            "archived": archived,
            "restricted": restricted,
            "tradable_identity": tradable_identity,
            "yes_token_id": yes_token_id,
            "no_token_id": no_token_id,
            "token_ids": json_dumps(ensure_list(token_ids)),
            "outcomes": json_dumps(ensure_list(outcomes)),
            "end_date": normalize_text(
                first_present(
                    market,
                    ("endDate", "end_date", "endDateIso"),
                )
            ),
            "start_date": normalize_text(
                first_present(
                    market,
                    ("startDate", "start_date"),
                )
            ),
            "created_at": normalize_text(
                first_present(
                    market,
                    ("createdAt", "created_at"),
                )
            ),
            "updated_at": normalize_text(
                first_present(
                    market,
                    ("updatedAt", "updated_at"),
                )
            ),
            "market_url": normalize_text(
                first_present(
                    market,
                    ("url",),
                    default=(
                        f"https://polymarket.com/event/"
                        f"{normalize_text(market.get('slug'))}"
                        if normalize_text(market.get("slug"))
                        else ""
                    ),
                )
            ),
            "raw_json": json_dumps(market),
            "last_identity_refresh_at": utc_now_iso(),
        }

        return normalized

    def adapt_to_schema(
        self,
        normalized: Mapping[str, Any],
    ) -> dict[str, Any]:
        available = set(self.table_columns(CANONICAL_TABLE))
        payload: dict[str, Any] = {}

        aliases = {
            "condition_id": (
                "condition_id",
                "canonical_condition_id",
                "market_id",
            ),
            "gamma_market_id": (
                "gamma_market_id",
                "gamma_id",
            ),
            "question": (
                "question",
                "title",
            ),
            "title": (
                "title",
                "question",
            ),
            "slug": (
                "slug",
                "market_slug",
            ),
            "market_slug": (
                "market_slug",
                "slug",
            ),
            "event_slug": ("event_slug",),
            "description": ("description",),
            "category": ("category",),
            "active": ("active",),
            "closed": ("closed",),
            "archived": ("archived",),
            "restricted": ("restricted",),
            "tradable_identity": (
                "tradable_identity",
                "tradable",
                "is_tradable",
            ),
            "yes_token_id": ("yes_token_id",),
            "no_token_id": ("no_token_id",),
            "token_ids": (
                "token_ids",
                "clob_token_ids",
            ),
            "outcomes": ("outcomes",),
            "end_date": (
                "end_date",
                "end_date_iso",
                "market_end_time",
            ),
            "start_date": (
                "start_date",
                "start_date_iso",
            ),
            "created_at": (
                "created_at",
                "gamma_created_at",
            ),
            "updated_at": (
                "updated_at",
                "gamma_updated_at",
            ),
            "market_url": (
                "market_url",
                "url",
            ),
            "raw_json": (
                "raw_json",
                "source_json",
            ),
            "last_identity_refresh_at": (
                "last_identity_refresh_at",
                "last_refreshed_at",
                "synced_at",
            ),
        }

        used_columns: set[str] = set()

        for normalized_name, candidate_columns in aliases.items():
            if normalized_name not in normalized:
                continue

            target_column = next(
                (
                    candidate
                    for candidate in candidate_columns
                    if candidate in available
                    and candidate not in used_columns
                ),
                None,
            )

            if target_column:
                payload[target_column] = normalized[normalized_name]
                used_columns.add(target_column)

        condition_column = self.canonical_condition_column()
        payload[condition_column] = normalized["condition_id"]

        return payload

    def load_existing_rows(self) -> dict[str, dict[str, Any]]:
        condition_column = self.canonical_condition_column()
        rows = self.data.fetch_all(
            f"SELECT * FROM {quote_identifier(CANONICAL_TABLE)}"
        )
        return {
            normalize_id(row.get(condition_column)): row
            for row in rows
            if normalize_id(row.get(condition_column))
        }

    def changed_columns(
        self,
        existing: Mapping[str, Any],
        incoming: Mapping[str, Any],
    ) -> list[str]:
        ignored = {
            "last_identity_refresh_at",
            "last_refreshed_at",
            "synced_at",
        }
        changed: list[str] = []

        for column, incoming_value in incoming.items():
            if column in ignored:
                continue

            existing_value = existing.get(column)

            if str(existing_value or "") != str(incoming_value or ""):
                changed.append(column)

        return changed

    def insert_row(self, payload: Mapping[str, Any]) -> int:
        columns = list(payload)
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(quote_identifier(column) for column in columns)

        return self.data.execute(
            f"""
            INSERT INTO {quote_identifier(CANONICAL_TABLE)}
            ({column_sql})
            VALUES ({placeholders})
            """,
            tuple(payload[column] for column in columns),
        )

    def update_row(
        self,
        *,
        condition_id: str,
        payload: Mapping[str, Any],
    ) -> int:
        condition_column = self.canonical_condition_column()
        update_columns = [
            column
            for column in payload
            if column != condition_column
        ]

        if not update_columns:
            return 0

        assignments = ", ".join(
            f"{quote_identifier(column)} = ?"
            for column in update_columns
        )

        values = [payload[column] for column in update_columns]
        values.append(condition_id)

        return self.data.execute(
            f"""
            UPDATE {quote_identifier(CANONICAL_TABLE)}
            SET {assignments}
            WHERE LOWER({quote_identifier(condition_column)}) = LOWER(?)
            """,
            tuple(values),
        )

    def archive_missing_rows(
        self,
        *,
        run_id: str,
        fetched_condition_ids: set[str],
        existing_rows: Mapping[str, Mapping[str, Any]],
        dry_run: bool,
    ) -> int:
        available = set(self.table_columns(CANONICAL_TABLE))
        archived_column = (
            "archived" if "archived" in available else None
        )
        tradable_column = next(
            (
                candidate
                for candidate in (
                    "tradable_identity",
                    "tradable",
                    "is_tradable",
                )
                if candidate in available
            ),
            None,
        )

        if not archived_column and not tradable_column:
            return 0

        archived_count = 0

        for condition_id, row in existing_rows.items():
            if condition_id in fetched_condition_ids:
                continue

            current_archived = to_int_bool(
                row.get(archived_column) if archived_column else 0
            )
            current_tradable = to_int_bool(
                row.get(tradable_column) if tradable_column else 0
            )

            if current_archived == 1 and current_tradable == 0:
                continue

            archived_count += 1
            changed = [
                column
                for column in (archived_column, tradable_column)
                if column
            ]

            if not dry_run:
                assignments: list[str] = []
                values: list[Any] = []

                if archived_column:
                    assignments.append(
                        f"{quote_identifier(archived_column)} = 1"
                    )
                if tradable_column:
                    assignments.append(
                        f"{quote_identifier(tradable_column)} = 0"
                    )

                condition_column = self.canonical_condition_column()
                values.append(condition_id)

                self.data.execute(
                    f"""
                    UPDATE {quote_identifier(CANONICAL_TABLE)}
                    SET {", ".join(assignments)}
                    WHERE LOWER({quote_identifier(condition_column)}) = LOWER(?)
                    """,
                    tuple(values),
                )

            self.write_audit(
                run_id=run_id,
                condition_id=condition_id,
                action="WOULD_ARCHIVE" if dry_run else "ARCHIVED",
                changed_columns=changed,
                source={},
            )

        return archived_count

    def refresh(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_pages: int | None = None,
        active_only: bool = False,
        dry_run: bool = True,
        archive_missing: bool = False,
    ) -> RefreshSummary:
        self.initialize_schema()
        self.validate_prerequisites()

        run_id = self.create_run(
            {
                "page_size": page_size,
                "max_pages": max_pages,
                "active_only": active_only,
                "dry_run": dry_run,
                "archive_missing": archive_missing,
            }
        )
        summary = RefreshSummary(run_id=run_id)
        started = time.perf_counter()

        try:
            source_markets = self.gamma.fetch_markets(
                page_size=page_size,
                max_pages=max_pages,
                active_only=active_only,
            )
            summary.fetched_rows = len(source_markets)

            normalized_by_condition: dict[str, dict[str, Any]] = {}

            for source_market in source_markets:
                normalized = self.normalize_market(source_market)
                if not normalized:
                    summary.skipped_rows += 1
                    self.write_audit(
                        run_id=run_id,
                        condition_id=None,
                        action="SKIPPED_NO_CONDITION_ID",
                        source=source_market,
                    )
                    continue

                summary.normalized_rows += 1
                condition_id = normalized["condition_id"]

                if condition_id in normalized_by_condition:
                    summary.duplicate_source_rows += 1

                normalized_by_condition[condition_id] = normalized

            summary.unique_condition_ids = len(normalized_by_condition)

            existing_rows = self.load_existing_rows()

            for condition_id, normalized in normalized_by_condition.items():
                try:
                    payload = self.adapt_to_schema(normalized)
                    existing = existing_rows.get(condition_id)

                    if existing is None:
                        summary.inserted_rows += 1

                        if not dry_run:
                            self.insert_row(payload)

                        self.write_audit(
                            run_id=run_id,
                            condition_id=condition_id,
                            action=(
                                "WOULD_INSERT"
                                if dry_run
                                else "INSERTED"
                            ),
                            changed_columns=payload.keys(),
                            source=normalized,
                        )
                        continue

                    changed = self.changed_columns(existing, payload)

                    if not changed:
                        summary.unchanged_rows += 1
                        self.write_audit(
                            run_id=run_id,
                            condition_id=condition_id,
                            action="UNCHANGED",
                            source=normalized,
                        )
                        continue

                    summary.updated_rows += 1

                    if not dry_run:
                        self.update_row(
                            condition_id=condition_id,
                            payload=payload,
                        )

                    self.write_audit(
                        run_id=run_id,
                        condition_id=condition_id,
                        action=(
                            "WOULD_UPDATE"
                            if dry_run
                            else "UPDATED"
                        ),
                        changed_columns=changed,
                        source=normalized,
                    )

                except Exception as error:
                    summary.error_count += 1
                    summary.errors.append(
                        f"{condition_id}: {error}"
                    )
                    LOGGER.exception(
                        "Failed refreshing canonical identity %s.",
                        condition_id,
                    )
                    self.write_audit(
                        run_id=run_id,
                        condition_id=condition_id,
                        action="ERROR",
                        source=normalized,
                        error_message=str(error),
                    )

            if archive_missing:
                summary.archived_rows = self.archive_missing_rows(
                    run_id=run_id,
                    fetched_condition_ids=set(normalized_by_condition),
                    existing_rows=existing_rows,
                    dry_run=dry_run,
                )

            summary.finished_at = utc_now_iso()
            summary.duration_seconds = time.perf_counter() - started
            self.finish_run(summary)
            return summary

        except Exception as error:
            summary.error_count = max(1, summary.error_count)
            summary.errors.append(str(error))
            summary.finished_at = utc_now_iso()
            summary.duration_seconds = time.perf_counter() - started
            self.finish_run(summary)
            raise

    def action_counts(self, run_id: str) -> list[dict[str, Any]]:
        return self.data.fetch_all(
            f"""
            SELECT
                action,
                COUNT(*) AS row_count
            FROM {AUDIT_TABLE}
            WHERE run_id = ?
            GROUP BY action
            ORDER BY row_count DESC, action
            """,
            (run_id,),
        )

    def print_summary(
        self,
        summary: RefreshSummary,
        *,
        dry_run: bool,
    ) -> None:
        print()
        print("=" * 112)
        print("CANONICAL IDENTITY REFRESH ENGINE")
        print("=" * 112)
        print(f"Database:                   {self.database_path}")
        print(f"Mode:                       {'DRY RUN' if dry_run else 'APPLY'}")
        print(f"Run ID:                     {summary.run_id}")
        print(f"Fetched Gamma rows:         {summary.fetched_rows}")
        print(f"Normalized rows:            {summary.normalized_rows}")
        print(f"Unique condition IDs:       {summary.unique_condition_ids}")
        print(f"Would insert/inserted:      {summary.inserted_rows}")
        print(f"Would update/updated:       {summary.updated_rows}")
        print(f"Unchanged:                  {summary.unchanged_rows}")
        print(f"Would archive/archived:     {summary.archived_rows}")
        print(f"Skipped:                    {summary.skipped_rows}")
        print(f"Duplicate source rows:      {summary.duplicate_source_rows}")
        print(f"Errors:                     {summary.error_count}")
        print(f"Duration:                   {summary.duration_seconds:.3f}s")
        print(
            f"Status:                     "
            f"{'SUCCESS' if summary.success else 'COMPLETED WITH ERRORS'}"
        )

        counts = self.action_counts(summary.run_id)
        if counts:
            print()
            print("ACTION COUNTS")
            print("-" * 112)
            for item in counts:
                print(
                    f"{item['action']:<40} "
                    f"{item['row_count']:>8}"
                )

        if summary.errors:
            print()
            print("ERROR PREVIEW")
            print("-" * 112)
            for error in summary.errors[:10]:
                print(error)

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
            "Refresh canonical_market_identities from Gamma markets."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply inserts and updates. Default behavior is a safe dry run."
        ),
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"Gamma page size. Default: {DEFAULT_PAGE_SIZE}.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional maximum number of Gamma pages.",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Fetch active Gamma markets only.",
    )
    parser.add_argument(
        "--archive-missing",
        action="store_true",
        help=(
            "Mark locally present but remotely absent markets archived. "
            "Use only with a complete, unfiltered Gamma fetch."
        ),
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

    if args.archive_missing and (
        args.active_only or args.max_pages is not None
    ):
        raise SystemExit(
            "--archive-missing requires a complete unfiltered fetch. "
            "Do not combine it with --active-only or --max-pages."
        )

    engine = CanonicalIdentityRefreshEngine()
    summary = engine.refresh(
        page_size=max(1, args.page_size),
        max_pages=args.max_pages,
        active_only=args.active_only,
        dry_run=not args.apply,
        archive_missing=args.archive_missing,
    )
    engine.print_summary(
        summary,
        dry_run=not args.apply,
    )


if __name__ == "__main__":
    main()