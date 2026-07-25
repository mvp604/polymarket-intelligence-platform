from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from .models import SnapshotConsensus, SnapshotMarket, SnapshotWallet


def _decimal(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


class LiveSnapshotAdapter:
    """Reads current platform state from the existing SQLite database."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def load_wallets(self) -> tuple[SnapshotWallet, ...]:
        with self._connect() as connection:
            columns = self._columns(connection, "positions")
            if not columns:
                return ()

            rows = connection.execute(
                """
                SELECT p.*
                FROM positions p
                JOIN (
                    SELECT wallet, MAX(scan_id) AS max_scan_id
                    FROM positions
                    GROUP BY wallet
                ) latest
                  ON latest.wallet = p.wallet
                 AND latest.max_scan_id = p.scan_id
                ORDER BY p.wallet, p.market_id, p.outcome
                """
            ).fetchall()

        results: list[SnapshotWallet] = []
        for row in rows:
            item = dict(row)
            results.append(
                SnapshotWallet(
                    wallet_id=str(item.get("wallet", "")),
                    market_id=str(item.get("market_id", "")),
                    outcome=str(item.get("outcome", "")),
                    shares=_decimal(item.get("shares")),
                    average_price=_decimal(item.get("average_price")),
                    current_price=_decimal(item.get("current_price")),
                    current_value=_decimal(item.get("current_value")),
                    cash_pnl=_decimal(item.get("cash_pnl")),
                    percent_pnl=_decimal(item.get("percent_pnl")),
                )
            )
        return tuple(results)

    def load_markets(
        self,
        wallets: Iterable[SnapshotWallet],
    ) -> tuple[SnapshotMarket, ...]:
        wallet_market_ids = sorted({str(item.market_id) for item in wallets})
        if not wallet_market_ids:
            return ()

        with self._connect() as connection:
            metadata_table = self._first_existing_table(
                connection,
                ("markets", "market_metadata", "polymarket_markets"),
            )

            metadata_by_id: dict[str, dict[str, Any]] = {}
            if metadata_table:
                placeholders = ",".join("?" for _ in wallet_market_ids)
                table_columns = self._columns(connection, metadata_table)
                market_key = self._first_present(
                    table_columns,
                    ("market_id", "id", "condition_id", "conditionId"),
                )
                if market_key:
                    rows = connection.execute(
                        f"SELECT * FROM {metadata_table} "
                        f"WHERE {market_key} IN ({placeholders})",
                        wallet_market_ids,
                    ).fetchall()
                    metadata_by_id = {
                        str(dict(row).get(market_key)): dict(row) for row in rows
                    }

            position_rows = connection.execute(
                """
                SELECT market_id, MAX(title) AS title,
                       MAX(current_price) AS current_price
                FROM positions
                WHERE market_id IN ({})
                GROUP BY market_id
                """.format(",".join("?" for _ in wallet_market_ids)),
                wallet_market_ids,
            ).fetchall()

        position_by_id = {str(row["market_id"]): dict(row) for row in position_rows}
        results: list[SnapshotMarket] = []

        for market_id in wallet_market_ids:
            metadata = metadata_by_id.get(market_id, {})
            position = position_by_id.get(market_id, {})
            title = str(
                metadata.get("title")
                or metadata.get("question")
                or position.get("title")
                or market_id
            )
            category = str(
                metadata.get("category")
                or metadata.get("sport")
                or metadata.get("series")
                or "unknown"
            )
            status = str(
                metadata.get("status")
                or ("closed" if metadata.get("closed") else "active")
            )
            yes_price = self._optional_decimal(
                metadata.get("yes_price")
                or metadata.get("yesPrice")
                or metadata.get("current_price")
                or position.get("current_price")
            )
            no_price = self._optional_decimal(
                metadata.get("no_price") or metadata.get("noPrice")
            )
            if no_price is None and yes_price is not None and Decimal("0") <= yes_price <= Decimal("1"):
                no_price = Decimal("1") - yes_price

            results.append(
                SnapshotMarket(
                    market_id=market_id,
                    title=title,
                    category=category,
                    status=status,
                    yes_price=yes_price,
                    no_price=no_price,
                )
            )
        return tuple(results)

    def load_consensus(self) -> tuple[SnapshotConsensus, ...]:
        with self._connect() as connection:
            columns = self._columns(connection, "consensus_history")
            if not columns:
                return ()

            order_column = "scanned_at" if "scanned_at" in columns else "id"
            rows = connection.execute(
                f"""
                SELECT c.*
                FROM consensus_history c
                JOIN (
                    SELECT market_id, outcome, MAX({order_column}) AS latest_value
                    FROM consensus_history
                    GROUP BY market_id, outcome
                ) latest
                  ON latest.market_id = c.market_id
                 AND latest.outcome = c.outcome
                 AND latest.latest_value = c.{order_column}
                ORDER BY c.market_id, c.outcome
                """
            ).fetchall()

        results: list[SnapshotConsensus] = []
        for row in rows:
            item = dict(row)
            results.append(
                SnapshotConsensus(
                    market_id=str(item.get("market_id", "")),
                    outcome=str(item.get("outcome", "")),
                    wallet_count=int(item.get("wallet_count") or 0),
                    combined_shares=_decimal(item.get("combined_shares")),
                    combined_value=_decimal(item.get("combined_value")),
                    combined_pnl=_decimal(item.get("combined_pnl")),
                    conviction_score=_decimal(item.get("conviction_score")),
                    conviction_grade=str(item.get("conviction_grade") or "UNRATED"),
                )
            )
        return tuple(results)

    def source_fingerprint(self) -> str:
        with self._connect() as connection:
            scan_row = connection.execute(
                "SELECT MAX(id), MAX(scanned_at) FROM wallet_scans"
            ).fetchone() if self._columns(connection, "wallet_scans") else None
            consensus_row = connection.execute(
                "SELECT MAX(id), MAX(scanned_at) FROM consensus_history"
            ).fetchone() if self._columns(connection, "consensus_history") else None

        scan_part = "none:none" if scan_row is None else f"{scan_row[0]}:{scan_row[1]}"
        consensus_part = (
            "none:none"
            if consensus_row is None
            else f"{consensus_row[0]}:{consensus_row[1]}"
        )
        return f"wallet_scans={scan_part}|consensus_history={consensus_part}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if row is None:
            return set()
        return {
            str(item["name"])
            for item in connection.execute(f"PRAGMA table_info({table})")
        }

    def _first_existing_table(
        self,
        connection: sqlite3.Connection,
        candidates: tuple[str, ...],
    ) -> str | None:
        for table in candidates:
            if self._columns(connection, table):
                return table
        return None

    @staticmethod
    def _first_present(columns: set[str], candidates: tuple[str, ...]) -> str | None:
        return next((item for item in candidates if item in columns), None)

    @staticmethod
    def _optional_decimal(value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            result = Decimal(str(value))
        except Exception:
            return None
        return result if Decimal("0") <= result <= Decimal("1") else None
