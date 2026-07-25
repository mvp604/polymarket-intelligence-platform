from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from data_access import DATABASE_PATH
except ImportError:
    from src.data_access import DATABASE_PATH


PRODUCTION_RUNS_TABLE = "wallet_profile_collection_runs"
PRODUCTION_PROFILES_TABLE = "wallet_profiles_raw"
PRODUCTION_CURRENT_TABLE = "wallet_current_position_snapshots"
PRODUCTION_CLOSED_TABLE = "wallet_closed_position_snapshots"
PRODUCTION_TRADES_TABLE = "wallet_trade_snapshots"
PRODUCTION_ACTIVITY_TABLE = "wallet_activity_snapshots"

LEGACY_SCANS_TABLE = "wallet_scans"
LEGACY_POSITIONS_TABLE = "positions"

ACCEPTED_COLLECTION_STATUSES = {"SUCCESS", "PARTIAL"}


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_wallet(value: Any) -> str:
    return clean_text(value).lower()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value is not None else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class WalletPositionObservation:
    wallet: str
    market_id: str
    title: str
    outcome: str
    outcome_index: int | None
    asset: str
    shares: float
    average_price: float
    current_price: float
    current_value: float
    cash_pnl: float
    percent_pnl: float
    realized_pnl: float
    total_bought: float
    observed_at: str
    source_run_id: str
    source_name: str

    @property
    def identity_key(self) -> tuple[str, ...]:
        """
        Return the strongest available identity for deduplication.

        Priority:
        1. Asset/token identifier
        2. Market/condition plus outcome index
        3. Market/condition plus outcome name
        4. Title plus outcome
        """
        if self.asset:
            return ("asset", self.asset.lower())

        if self.market_id and self.outcome_index is not None:
            return (
                "market-index",
                self.market_id.lower(),
                str(self.outcome_index),
            )

        if self.market_id and self.outcome:
            return (
                "market-outcome",
                self.market_id.lower(),
                self.outcome.lower(),
            )

        return (
            "title-outcome",
            self.title.lower(),
            self.outcome.lower(),
        )


@dataclass(frozen=True, slots=True)
class WalletSourceResult:
    wallet: str
    source_name: str
    source_run_id: str
    observed_at: str
    positions: tuple[WalletPositionObservation, ...]
    duplicate_rows_removed: int

    @property
    def position_count(self) -> int:
        return len(self.positions)


class WalletIntelligenceSource:
    """
    Unified read-only source for wallet intelligence calculations.

    Production collector snapshots are preferred. Legacy positions are used
    only when no eligible production snapshot exists for a wallet.
    """

    def __init__(
        self,
        database_path: Path | str = DATABASE_PATH,
    ) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @staticmethod
    def table_exists(
        connection: sqlite3.Connection,
        table_name: str,
    ) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            LIMIT 1
            """,
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def table_columns(
        connection: sqlite3.Connection,
        table_name: str,
    ) -> set[str]:
        if not WalletIntelligenceSource.table_exists(
            connection,
            table_name,
        ):
            return set()

        return {
            str(row["name"])
            for row in connection.execute(
                f'PRAGMA table_info("{table_name}")'
            ).fetchall()
        }

    def production_schema_available(
        self,
        connection: sqlite3.Connection,
    ) -> bool:
        required = {
            PRODUCTION_RUNS_TABLE,
            PRODUCTION_PROFILES_TABLE,
            PRODUCTION_CURRENT_TABLE,
        }
        return all(
            self.table_exists(connection, table)
            for table in required
        )

    def legacy_schema_available(
        self,
        connection: sqlite3.Connection,
    ) -> bool:
        return self.table_exists(
            connection,
            LEGACY_POSITIONS_TABLE,
        )

    def available_wallets(self) -> list[str]:
        connection = self.connect()
        try:
            wallets: set[str] = set()

            if self.production_schema_available(connection):
                rows = connection.execute(
                    f"""
                    SELECT wallet
                    FROM "{PRODUCTION_PROFILES_TABLE}"
                    WHERE wallet IS NOT NULL
                      AND TRIM(wallet) <> ''
                    """
                ).fetchall()
                wallets.update(
                    normalize_wallet(row["wallet"])
                    for row in rows
                    if normalize_wallet(row["wallet"])
                )

            if self.legacy_schema_available(connection):
                rows = connection.execute(
                    f"""
                    SELECT DISTINCT wallet
                    FROM "{LEGACY_POSITIONS_TABLE}"
                    WHERE wallet IS NOT NULL
                      AND TRIM(wallet) <> ''
                    """
                ).fetchall()
                wallets.update(
                    normalize_wallet(row["wallet"])
                    for row in rows
                    if normalize_wallet(row["wallet"])
                )

            return sorted(wallets)
        finally:
            connection.close()

    def load_wallet(
        self,
        wallet: str,
    ) -> WalletSourceResult:
        normalized = normalize_wallet(wallet)
        if not normalized:
            raise ValueError("wallet must be a non-empty value")

        connection = self.connect()
        try:
            production = self._load_production_wallet(
                connection,
                normalized,
            )
            if production is not None:
                return production

            legacy = self._load_legacy_wallet(
                connection,
                normalized,
            )
            if legacy is not None:
                return legacy

            return WalletSourceResult(
                wallet=normalized,
                source_name="none",
                source_run_id="",
                observed_at="",
                positions=(),
                duplicate_rows_removed=0,
            )
        finally:
            connection.close()

    def load_all_wallets(self) -> dict[str, WalletSourceResult]:
        return {
            wallet: self.load_wallet(wallet)
            for wallet in self.available_wallets()
        }

    def _load_production_wallet(
        self,
        connection: sqlite3.Connection,
        wallet: str,
    ) -> WalletSourceResult | None:
        if not self.production_schema_available(connection):
            return None

        profile = connection.execute(
            f"""
            SELECT
                wallet,
                last_run_id,
                last_profiled_at,
                latest_collection_status
            FROM "{PRODUCTION_PROFILES_TABLE}"
            WHERE LOWER(wallet) = ?
            LIMIT 1
            """,
            (wallet,),
        ).fetchone()

        if profile is None:
            return None

        collection_status = clean_text(
            profile["latest_collection_status"]
        ).upper()

        if collection_status not in ACCEPTED_COLLECTION_STATUSES:
            return None

        run_id = clean_text(profile["last_run_id"])
        if not run_id:
            return None

        run = connection.execute(
            f"""
            SELECT
                run_id,
                mode,
                status,
                finished_at
            FROM "{PRODUCTION_RUNS_TABLE}"
            WHERE run_id = ?
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()

        if run is None:
            return None

        run_mode = clean_text(run["mode"]).upper()
        run_status = clean_text(run["status"]).upper()

        if run_mode != "APPLY":
            return None

        if run_status not in ACCEPTED_COLLECTION_STATUSES:
            return None

        rows = connection.execute(
            f"""
            SELECT
                wallet,
                condition_id,
                title,
                outcome,
                outcome_index,
                asset,
                size,
                avg_price,
                current_price,
                current_value,
                cash_pnl,
                percent_pnl,
                realized_pnl,
                total_bought,
                observed_at,
                run_id
            FROM "{PRODUCTION_CURRENT_TABLE}"
            WHERE run_id = ?
              AND LOWER(wallet) = ?
            ORDER BY id ASC
            """,
            (run_id, wallet),
        ).fetchall()

        positions = [
            WalletPositionObservation(
                wallet=wallet,
                market_id=clean_text(row["condition_id"]),
                title=clean_text(row["title"]),
                outcome=clean_text(row["outcome"]),
                outcome_index=(
                    safe_int(row["outcome_index"])
                    if row["outcome_index"] is not None
                    else None
                ),
                asset=clean_text(row["asset"]),
                shares=safe_float(row["size"]),
                average_price=safe_float(row["avg_price"]),
                current_price=safe_float(row["current_price"]),
                current_value=safe_float(row["current_value"]),
                cash_pnl=safe_float(row["cash_pnl"]),
                percent_pnl=safe_float(row["percent_pnl"]),
                realized_pnl=safe_float(row["realized_pnl"]),
                total_bought=safe_float(row["total_bought"]),
                observed_at=clean_text(row["observed_at"]),
                source_run_id=clean_text(row["run_id"]),
                source_name="production",
            )
            for row in rows
        ]

        deduplicated, removed = self._deduplicate(positions)

        observed_at = max(
            (
                position.observed_at
                for position in deduplicated
                if position.observed_at
            ),
            default=clean_text(
                run["finished_at"]
                or profile["last_profiled_at"]
            ),
        )

        return WalletSourceResult(
            wallet=wallet,
            source_name="production",
            source_run_id=run_id,
            observed_at=observed_at,
            positions=tuple(deduplicated),
            duplicate_rows_removed=removed,
        )

    def _load_legacy_wallet(
        self,
        connection: sqlite3.Connection,
        wallet: str,
    ) -> WalletSourceResult | None:
        if not self.legacy_schema_available(connection):
            return None

        columns = self.table_columns(
            connection,
            LEGACY_POSITIONS_TABLE,
        )

        def expression(column: str, fallback: str = "NULL") -> str:
            if column in columns:
                return f'p."{column}"'
            return fallback

        join_sql = ""
        scanned_at_expression = "NULL"

        if (
            "scan_id" in columns
            and self.table_exists(connection, LEGACY_SCANS_TABLE)
            and {"id", "scanned_at"}.issubset(
                self.table_columns(connection, LEGACY_SCANS_TABLE)
            )
        ):
            join_sql = (
                f'LEFT JOIN "{LEGACY_SCANS_TABLE}" ws '
                "ON ws.id = p.scan_id"
            )
            scanned_at_expression = "ws.scanned_at"

        rows = connection.execute(
            f"""
            SELECT
                {expression("wallet", "''")} AS wallet,
                {expression("market_id", "''")} AS market_id,
                {expression("title", "''")} AS title,
                {expression("outcome", "''")} AS outcome,
                {expression("shares", "0")} AS shares,
                {expression("average_price", "0")} AS average_price,
                {expression("current_price", "0")} AS current_price,
                {expression("current_value", "0")} AS current_value,
                {expression("cash_pnl", "0")} AS cash_pnl,
                {expression("percent_pnl", "0")} AS percent_pnl,
                {expression("scan_id", "NULL")} AS scan_id,
                {scanned_at_expression} AS observed_at
            FROM "{LEGACY_POSITIONS_TABLE}" p
            {join_sql}
            WHERE LOWER(p.wallet) = ?
            ORDER BY observed_at ASC
            """,
            (wallet,),
        ).fetchall()

        if not rows:
            return None

        latest_scan_id = rows[-1]["scan_id"]

        if latest_scan_id is not None:
            rows = [
                row
                for row in rows
                if row["scan_id"] == latest_scan_id
            ]

        positions = [
            WalletPositionObservation(
                wallet=wallet,
                market_id=clean_text(row["market_id"]),
                title=clean_text(row["title"]),
                outcome=clean_text(row["outcome"]),
                outcome_index=None,
                asset="",
                shares=safe_float(row["shares"]),
                average_price=safe_float(row["average_price"]),
                current_price=safe_float(row["current_price"]),
                current_value=safe_float(row["current_value"]),
                cash_pnl=safe_float(row["cash_pnl"]),
                percent_pnl=safe_float(row["percent_pnl"]),
                realized_pnl=0.0,
                total_bought=0.0,
                observed_at=clean_text(row["observed_at"]),
                source_run_id=clean_text(latest_scan_id),
                source_name="legacy",
            )
            for row in rows
        ]

        deduplicated, removed = self._deduplicate(positions)

        observed_at = max(
            (
                position.observed_at
                for position in deduplicated
                if position.observed_at
            ),
            default="",
        )

        return WalletSourceResult(
            wallet=wallet,
            source_name="legacy",
            source_run_id=clean_text(latest_scan_id),
            observed_at=observed_at,
            positions=tuple(deduplicated),
            duplicate_rows_removed=removed,
        )

    @staticmethod
    def _deduplicate(
        positions: Iterable[WalletPositionObservation],
    ) -> tuple[list[WalletPositionObservation], int]:
        """
        Keep the final occurrence of each position identity.

        Rows are normally supplied in database insertion order, so a later
        repeated row supersedes an earlier duplicate.
        """
        by_identity: dict[
            tuple[str, ...],
            WalletPositionObservation,
        ] = {}
        total = 0

        for position in positions:
            total += 1
            by_identity[position.identity_key] = position

        deduplicated = sorted(
            by_identity.values(),
            key=lambda item: (
                item.market_id,
                item.outcome_index
                if item.outcome_index is not None
                else -1,
                item.outcome,
                item.asset,
            ),
        )

        return deduplicated, total - len(deduplicated)