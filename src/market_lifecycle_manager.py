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


LOGGER = logging.getLogger(__name__)

BUSY_TIMEOUT_MS = 30_000

RUNS_TABLE = "market_lifecycle_manager_runs"
AUDIT_TABLE = "market_lifecycle_manager_audit"

CANONICAL_TABLE = "canonical_market_identities"
LEGACY_TABLE = "gamma_markets"

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

ACTIVE_CANDIDATES = ("active", "is_active")
CLOSED_CANDIDATES = ("closed", "is_closed")
ARCHIVED_CANDIDATES = ("archived", "is_archived")
RESTRICTED_CANDIDATES = ("restricted", "is_restricted")
ACCEPTING_ORDERS_CANDIDATES = (
    "accepting_orders",
    "acceptingOrders",
    "is_accepting_orders",
)
UPDATED_AT_CANDIDATES = (
    "updated_at",
    "last_updated_at",
    "modified_at",
    "synced_at",
    "created_at",
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


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


@dataclass(slots=True)
class LifecycleDecision:
    market_id: str
    title: str
    lifecycle_status: str
    action: str
    reason_code: str
    reason_detail: str
    canonical_present: int
    legacy_present: int
    active: int
    closed: int
    archived: int
    accepting_orders: int
    restricted: int
    tradable: int
    source_updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketLifecycleManager:
    """
    Governs lifecycle state for canonical Polymarket identities.

    Core policies:
      - tradable = active AND closed is false AND archived is false
      - restricted is metadata only and does not determine tradability
      - canonical identities are preserved; historical markets are never deleted
      - legacy-only markets are reported for canonical backfill
      - canonical markets absent from legacy are reviewed, not automatically deleted
    """

    def __init__(
        self,
        database_path: Path | str = DATABASE_PATH,
    ) -> None:
        self.database_path = Path(database_path)
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
                    canonical_rows INTEGER NOT NULL DEFAULT 0,
                    legacy_rows INTEGER NOT NULL DEFAULT 0,
                    decisions INTEGER NOT NULL DEFAULT 0,
                    actionable_changes INTEGER NOT NULL DEFAULT 0,
                    canonical_updates INTEGER NOT NULL DEFAULT 0,
                    legacy_only INTEGER NOT NULL DEFAULT 0,
                    canonical_only INTEGER NOT NULL DEFAULT 0,
                    tradable INTEGER NOT NULL DEFAULT 0,
                    non_tradable INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(AUDIT_TABLE)} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    title TEXT,
                    lifecycle_status TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    canonical_present INTEGER NOT NULL DEFAULT 0,
                    legacy_present INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 0,
                    closed INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    accepting_orders INTEGER NOT NULL DEFAULT 0,
                    restricted INTEGER NOT NULL DEFAULT 0,
                    tradable INTEGER NOT NULL DEFAULT 0,
                    source_updated_at TEXT,
                    audited_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES {quote_identifier(RUNS_TABLE)}(run_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS
                idx_market_lifecycle_audit_market
                ON {quote_identifier(AUDIT_TABLE)}(
                    market_id,
                    audited_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_market_lifecycle_audit_status
                ON {quote_identifier(AUDIT_TABLE)}(
                    lifecycle_status,
                    audited_at DESC
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

    def _load_table_records(
        self,
        table_name: str,
    ) -> dict[str, dict[str, Any]]:
        if not self.table_exists(table_name):
            raise RuntimeError(f"Required table is missing: {table_name}")

        columns = self.table_columns(table_name)
        market_id_column = first_existing(columns, MARKET_ID_CANDIDATES)
        if not market_id_column:
            raise RuntimeError(
                f"{table_name} has no recognized market identifier column."
            )

        title_column = first_existing(columns, TITLE_CANDIDATES)
        active_column = first_existing(columns, ACTIVE_CANDIDATES)
        closed_column = first_existing(columns, CLOSED_CANDIDATES)
        archived_column = first_existing(columns, ARCHIVED_CANDIDATES)
        restricted_column = first_existing(columns, RESTRICTED_CANDIDATES)
        accepting_orders_column = first_existing(
            columns,
            ACCEPTING_ORDERS_CANDIDATES,
        )
        updated_at_column = first_existing(columns, UPDATED_AT_CANDIDATES)

        select_parts = [
            f"{quote_identifier(market_id_column)} AS market_id",
            (
                f"{quote_identifier(title_column)} AS title"
                if title_column
                else "NULL AS title"
            ),
            (
                f"{quote_identifier(active_column)} AS active"
                if active_column
                else "NULL AS active"
            ),
            (
                f"{quote_identifier(closed_column)} AS closed"
                if closed_column
                else "NULL AS closed"
            ),
            (
                f"{quote_identifier(archived_column)} AS archived"
                if archived_column
                else "NULL AS archived"
            ),
            (
                f"{quote_identifier(restricted_column)} AS restricted"
                if restricted_column
                else "NULL AS restricted"
            ),
            (
                f"{quote_identifier(accepting_orders_column)} AS accepting_orders"
                if accepting_orders_column
                else "NULL AS accepting_orders"
            ),
            (
                f"{quote_identifier(updated_at_column)} AS source_updated_at"
                if updated_at_column
                else "NULL AS source_updated_at"
            ),
        ]

        connection = self.connect()
        try:
            rows = connection.execute(
                f"""
                SELECT {", ".join(select_parts)}
                FROM {quote_identifier(table_name)}
                """
            ).fetchall()
        finally:
            connection.close()

        records: dict[str, dict[str, Any]] = {}
        for row in rows:
            market_id = normalize_market_id(row["market_id"])
            if not market_id:
                continue

            records[market_id] = {
                "market_id": market_id,
                "title": clean_text(row["title"]),
                "active": bool_int(row["active"], default=0),
                "closed": bool_int(row["closed"], default=0),
                "archived": bool_int(row["archived"], default=0),
                "restricted": bool_int(row["restricted"], default=0),
                "accepting_orders": bool_int(
                    row["accepting_orders"],
                    default=0,
                ),
                "source_updated_at": (
                    clean_text(row["source_updated_at"]) or None
                ),
            }

        return records

    def load_canonical_records(self) -> dict[str, dict[str, Any]]:
        return self._load_table_records(CANONICAL_TABLE)

    def load_legacy_records(self) -> dict[str, dict[str, Any]]:
        return self._load_table_records(LEGACY_TABLE)

    def classify(
        self,
        canonical: dict[str, Any] | None,
        legacy: dict[str, Any] | None,
    ) -> LifecycleDecision:
        source = canonical or legacy or {}
        market_id = normalize_market_id(source.get("market_id"))
        title = clean_text(
            (canonical or {}).get("title")
            or (legacy or {}).get("title")
        )

        canonical_present = int(canonical is not None)
        legacy_present = int(legacy is not None)

        if canonical is not None and legacy is not None:
            active = bool_int(legacy.get("active"), canonical.get("active", 0))
            closed = bool_int(legacy.get("closed"), canonical.get("closed", 0))
            archived = bool_int(
                legacy.get("archived"),
                canonical.get("archived", 0),
            )
            restricted = bool_int(
                legacy.get("restricted"),
                canonical.get("restricted", 0),
            )
            accepting_orders = bool_int(
                legacy.get("accepting_orders"),
                canonical.get("accepting_orders", 0),
            )
            tradable = int(active == 1 and closed == 0 and archived == 0)

            changes: list[str] = []
            for field_name, new_value in (
                ("active", active),
                ("closed", closed),
                ("archived", archived),
                ("restricted", restricted),
                ("accepting_orders", accepting_orders),
            ):
                if bool_int(canonical.get(field_name)) != new_value:
                    changes.append(field_name)

            canonical_tradable = int(
                bool_int(canonical.get("active")) == 1
                and bool_int(canonical.get("closed")) == 0
                and bool_int(canonical.get("archived")) == 0
            )
            if canonical_tradable != tradable:
                changes.append("tradable_identity")

            if tradable:
                lifecycle_status = "ACTIVE_TRADABLE"
            elif closed:
                lifecycle_status = "CLOSED"
            elif archived:
                lifecycle_status = "ARCHIVED"
            else:
                lifecycle_status = "INACTIVE"

            return LifecycleDecision(
                market_id=market_id,
                title=title,
                lifecycle_status=lifecycle_status,
                action="SYNC_CANONICAL" if changes else "NO_CHANGE",
                reason_code=(
                    "CANONICAL_STATUS_DRIFT"
                    if changes
                    else "CANONICAL_AND_LEGACY_ALIGNED"
                ),
                reason_detail=(
                    "Canonical fields differ from Gamma: "
                    + ", ".join(sorted(set(changes)))
                    if changes
                    else "Canonical identity matches the current Gamma state."
                ),
                canonical_present=1,
                legacy_present=1,
                active=active,
                closed=closed,
                archived=archived,
                accepting_orders=accepting_orders,
                restricted=restricted,
                tradable=tradable,
                source_updated_at=legacy.get("source_updated_at"),
            )

        if legacy is not None:
            active = bool_int(legacy.get("active"))
            closed = bool_int(legacy.get("closed"))
            archived = bool_int(legacy.get("archived"))
            restricted = bool_int(legacy.get("restricted"))
            accepting_orders = bool_int(legacy.get("accepting_orders"))
            tradable = int(active == 1 and closed == 0 and archived == 0)

            return LifecycleDecision(
                market_id=market_id,
                title=title,
                lifecycle_status="LEGACY_ONLY",
                action="BACKFILL_CANONICAL",
                reason_code="MISSING_CANONICAL_IDENTITY",
                reason_detail=(
                    "Market exists in gamma_markets but not in "
                    "canonical_market_identities."
                ),
                canonical_present=0,
                legacy_present=1,
                active=active,
                closed=closed,
                archived=archived,
                accepting_orders=accepting_orders,
                restricted=restricted,
                tradable=tradable,
                source_updated_at=legacy.get("source_updated_at"),
            )

        if canonical is not None:
            active = bool_int(canonical.get("active"))
            closed = bool_int(canonical.get("closed"))
            archived = bool_int(canonical.get("archived"))
            restricted = bool_int(canonical.get("restricted"))
            accepting_orders = bool_int(canonical.get("accepting_orders"))
            tradable = int(active == 1 and closed == 0 and archived == 0)

            return LifecycleDecision(
                market_id=market_id,
                title=title,
                lifecycle_status="CANONICAL_ONLY",
                action="REVIEW_CANONICAL_ONLY",
                reason_code="MISSING_FROM_LEGACY_REGISTRY",
                reason_detail=(
                    "Market exists canonically but is absent from gamma_markets. "
                    "It is preserved and requires review rather than deletion."
                ),
                canonical_present=1,
                legacy_present=0,
                active=active,
                closed=closed,
                archived=archived,
                accepting_orders=accepting_orders,
                restricted=restricted,
                tradable=tradable,
                source_updated_at=canonical.get("source_updated_at"),
            )

        raise RuntimeError("Lifecycle classification received no market record.")

    def build_decisions(self) -> tuple[
        list[LifecycleDecision],
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
    ]:
        canonical_records = self.load_canonical_records()
        legacy_records = self.load_legacy_records()

        all_market_ids = sorted(
            set(canonical_records) | set(legacy_records)
        )

        decisions = [
            self.classify(
                canonical_records.get(market_id),
                legacy_records.get(market_id),
            )
            for market_id in all_market_ids
        ]

        return decisions, canonical_records, legacy_records

    def _canonical_update_columns(self) -> dict[str, str | None]:
        columns = self.table_columns(CANONICAL_TABLE)
        return {
            "market_id": first_existing(columns, MARKET_ID_CANDIDATES),
            "active": first_existing(columns, ACTIVE_CANDIDATES),
            "closed": first_existing(columns, CLOSED_CANDIDATES),
            "archived": first_existing(columns, ARCHIVED_CANDIDATES),
            "restricted": first_existing(columns, RESTRICTED_CANDIDATES),
            "accepting_orders": first_existing(
                columns,
                ACCEPTING_ORDERS_CANDIDATES,
            ),
            "tradable_identity": (
                "tradable_identity"
                if "tradable_identity" in columns
                else None
            ),
            "updated_at": (
                "updated_at"
                if "updated_at" in columns
                else None
            ),
        }

    def apply_sync_updates(
        self,
        decisions: Iterable[LifecycleDecision],
    ) -> int:
        column_map = self._canonical_update_columns()
        market_id_column = column_map["market_id"]
        if not market_id_column:
            raise RuntimeError(
                "canonical_market_identities has no market ID column."
            )

        updateable_fields = [
            field_name
            for field_name in (
                "active",
                "closed",
                "archived",
                "restricted",
                "accepting_orders",
                "tradable_identity",
            )
            if column_map.get(field_name)
        ]

        if not updateable_fields:
            LOGGER.warning(
                "No supported canonical status columns are available."
            )
            return 0

        connection = self.connect()
        updated_count = 0
        try:
            for decision in decisions:
                if decision.action != "SYNC_CANONICAL":
                    continue

                values_by_field = {
                    "active": decision.active,
                    "closed": decision.closed,
                    "archived": decision.archived,
                    "restricted": decision.restricted,
                    "accepting_orders": decision.accepting_orders,
                    "tradable_identity": decision.tradable,
                }

                assignments = [
                    f"{quote_identifier(clean_text(column_map[field_name]))}=?"
                    for field_name in updateable_fields
                ]
                parameters: list[Any] = [
                    values_by_field[field_name]
                    for field_name in updateable_fields
                ]

                if column_map.get("updated_at"):
                    assignments.append(
                        f"{quote_identifier(clean_text(column_map['updated_at']))}=?"
                    )
                    parameters.append(utc_now_iso())

                parameters.append(decision.market_id)

                cursor = connection.execute(
                    f"""
                    UPDATE {quote_identifier(CANONICAL_TABLE)}
                    SET {", ".join(assignments)}
                    WHERE LOWER(
                        {quote_identifier(clean_text(market_id_column))}
                    )=?
                    """,
                    parameters,
                )
                updated_count += cursor.rowcount

            connection.commit()
        finally:
            connection.close()

        return updated_count

    def persist_audit(
        self,
        run_id: str,
        decisions: Iterable[LifecycleDecision],
    ) -> None:
        audited_at = utc_now_iso()

        rows = [
            (
                run_id,
                decision.market_id,
                decision.title,
                decision.lifecycle_status,
                decision.action,
                decision.reason_code,
                decision.reason_detail,
                decision.canonical_present,
                decision.legacy_present,
                decision.active,
                decision.closed,
                decision.archived,
                decision.accepting_orders,
                decision.restricted,
                decision.tradable,
                decision.source_updated_at,
                audited_at,
            )
            for decision in decisions
        ]

        connection = self.connect()
        try:
            connection.executemany(
                f"""
                INSERT INTO {quote_identifier(AUDIT_TABLE)} (
                    run_id,
                    market_id,
                    title,
                    lifecycle_status,
                    action,
                    reason_code,
                    reason_detail,
                    canonical_present,
                    legacy_present,
                    active,
                    closed,
                    archived,
                    accepting_orders,
                    restricted,
                    tradable,
                    source_updated_at,
                    audited_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
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
    ) -> dict[str, Any]:
        self.create_tables()

        run_id = uuid.uuid4().hex
        started = utc_now()
        mode = "APPLY" if apply else "DRY RUN"

        connection = self.connect()
        try:
            connection.execute(
                f"""
                INSERT INTO {quote_identifier(RUNS_TABLE)} (
                    run_id,
                    started_at,
                    mode,
                    status
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    run_id,
                    started.isoformat(),
                    mode,
                    "RUNNING",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        status = "SUCCESS"
        error_message = ""
        canonical_updates = 0
        decisions: list[LifecycleDecision] = []
        canonical_records: dict[str, dict[str, Any]] = {}
        legacy_records: dict[str, dict[str, Any]] = {}

        try:
            decisions, canonical_records, legacy_records = (
                self.build_decisions()
            )

            if apply:
                canonical_updates = self.apply_sync_updates(decisions)
                self.persist_audit(run_id, decisions)

        except Exception as exc:
            status = "FAILED"
            error_message = str(exc)
            raise

        finally:
            finished = utc_now()
            elapsed_seconds = (finished - started).total_seconds()

            action_counts: dict[str, int] = {}
            status_counts: dict[str, int] = {}
            for decision in decisions:
                action_counts[decision.action] = (
                    action_counts.get(decision.action, 0) + 1
                )
                status_counts[decision.lifecycle_status] = (
                    status_counts.get(decision.lifecycle_status, 0) + 1
                )

            connection = self.connect()
            try:
                connection.execute(
                    f"""
                    UPDATE {quote_identifier(RUNS_TABLE)}
                    SET
                        finished_at=?,
                        elapsed_seconds=?,
                        canonical_rows=?,
                        legacy_rows=?,
                        decisions=?,
                        actionable_changes=?,
                        canonical_updates=?,
                        legacy_only=?,
                        canonical_only=?,
                        tradable=?,
                        non_tradable=?,
                        status=?,
                        error_message=?
                    WHERE run_id=?
                    """,
                    (
                        finished.isoformat(),
                        elapsed_seconds,
                        len(canonical_records),
                        len(legacy_records),
                        len(decisions),
                        sum(
                            count
                            for action, count in action_counts.items()
                            if action != "NO_CHANGE"
                        ),
                        canonical_updates,
                        status_counts.get("LEGACY_ONLY", 0),
                        status_counts.get("CANONICAL_ONLY", 0),
                        sum(
                            1
                            for decision in decisions
                            if decision.tradable == 1
                        ),
                        sum(
                            1
                            for decision in decisions
                            if decision.tradable == 0
                        ),
                        status,
                        error_message or None,
                        run_id,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

        action_counts: dict[str, int] = {}
        lifecycle_counts: dict[str, int] = {}
        for decision in decisions:
            action_counts[decision.action] = (
                action_counts.get(decision.action, 0) + 1
            )
            lifecycle_counts[decision.lifecycle_status] = (
                lifecycle_counts.get(decision.lifecycle_status, 0) + 1
            )

        return {
            "run_id": run_id,
            "database_path": str(self.database_path),
            "mode": mode,
            "canonical_rows": len(canonical_records),
            "legacy_rows": len(legacy_records),
            "decisions": len(decisions),
            "action_counts": action_counts,
            "lifecycle_counts": lifecycle_counts,
            "canonical_updates": canonical_updates,
            "preview": [
                decision
                for decision in decisions
                if decision.action != "NO_CHANGE"
            ],
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
    print("MARKET LIFECYCLE MANAGER")
    print("=" * 112)
    print(f"{'Database:':32} {report['database_path']}")
    print(f"{'Mode:':32} {report['mode']}")
    print(f"{'Run ID:':32} {report['run_id']}")
    print(f"{'Canonical rows:':32} {report['canonical_rows']}")
    print(f"{'Legacy rows:':32} {report['legacy_rows']}")
    print(f"{'Lifecycle decisions:':32} {report['decisions']}")
    print(f"{'Canonical updates:':32} {report['canonical_updates']}")
    print(f"{'Duration:':32} {report['elapsed_seconds']:.3f}s")
    print(f"{'Status:':32} {report['status']}")

    print()
    print("LIFECYCLE COUNTS")
    print("-" * 112)
    for lifecycle_status, count in sorted(
        report["lifecycle_counts"].items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"{lifecycle_status:<48} {count:>8}")

    print()
    print("ACTION COUNTS")
    print("-" * 112)
    for action, count in sorted(
        report["action_counts"].items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"{action:<48} {count:>8}")

    print()
    print("ACTION PREVIEW")
    print("-" * 112)

    preview: list[LifecycleDecision] = list(report["preview"])
    if not preview:
        print("No lifecycle actions are currently required.")
    else:
        for decision in preview[:preview_limit]:
            print(
                f"{decision.action:<24} | "
                f"{decision.lifecycle_status:<20} | "
                f"{decision.market_id}"
            )
            print(
                f"    {decision.title or 'UNKNOWN TITLE'}"
            )
            print(
                f"    active={decision.active} "
                f"closed={decision.closed} "
                f"archived={decision.archived} "
                f"tradable={decision.tradable}"
            )
            print(
                f"    {decision.reason_code}: {decision.reason_detail}"
            )

    print("=" * 112)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile canonical Polymarket lifecycle state against "
            "the local Gamma market registry."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply supported lifecycle status updates to existing canonical "
            "identities and persist the lifecycle audit. Dry run is default."
        ),
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=25,
        help="Maximum action rows to print. Default: 25.",
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

    manager = MarketLifecycleManager()
    report = manager.run(apply=args.apply)

    print_report(
        report,
        preview_limit=max(1, args.preview_limit),
    )


if __name__ == "__main__":
    main()