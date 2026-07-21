from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 0.25


class DataAccessError(RuntimeError):
    """Base exception for database access failures."""


class MissingTableError(DataAccessError):
    """Raised when a required table is unavailable."""


class DataAccess:
    """
    Centralized SQLite access layer for the Polymarket Intelligence Platform.

    Design goals:
    - one connection configuration
    - one transaction pattern
    - canonical market identity as the primary market source
    - graceful handling of optional engine tables
    - reusable reads for dashboards, reports, APIs, and future UI layers
    """

    def __init__(
        self,
        database_path: Path | str = DATABASE_PATH,
        *,
        busy_timeout_ms: int = BUSY_TIMEOUT_MS,
        retries: int = DEFAULT_RETRIES,
        retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    ) -> None:
        self.database_path = Path(database_path)
        self.busy_timeout_ms = busy_timeout_ms
        self.retries = max(1, retries)
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)

        if not self.database_path.exists():
            raise FileNotFoundError(
                f"Database not found: {self.database_path}"
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=max(1, self.busy_timeout_ms // 1000),
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            f"PRAGMA busy_timeout = {self.busy_timeout_ms}"
        )
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _run_with_retry(
        self,
        operation: callable,
    ) -> Any:
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            try:
                return operation()
            except sqlite3.OperationalError as error:
                last_error = error
                message = str(error).casefold()

                retryable = (
                    "database is locked" in message
                    or "database table is locked" in message
                    or "busy" in message
                )

                if not retryable or attempt >= self.retries:
                    raise

                time.sleep(self.retry_delay_seconds * attempt)

        if last_error is not None:
            raise last_error

        raise DataAccessError("Database operation failed unexpectedly.")

    def table_exists(self, table_name: str) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = ?
                """,
                (table_name,),
            ).fetchone()
        return row is not None

    def require_table(self, table_name: str) -> None:
        if not self.table_exists(table_name):
            raise MissingTableError(
                f"Required table not found: {table_name}"
            )

    def get_table_columns(self, table_name: str) -> list[str]:
        if not self.table_exists(table_name):
            return []

        with self.connection() as connection:
            rows = connection.execute(
                f'PRAGMA table_info("{table_name}")'
            ).fetchall()

        return [str(row["name"]) for row in rows]

    def table_row_count(self, table_name: str) -> int:
        if not self.table_exists(table_name):
            return 0

        with self.connection() as connection:
            row = connection.execute(
                f'SELECT COUNT(*) AS total FROM "{table_name}"'
            ).fetchone()

        return int(row["total"] if row else 0)

    def fetch_all(
        self,
        query: str,
        parameters: Sequence[Any] = (),
    ) -> list[dict[str, Any]]:
        def operation() -> list[dict[str, Any]]:
            with self.connection() as connection:
                rows = connection.execute(
                    query,
                    tuple(parameters),
                ).fetchall()
            return [dict(row) for row in rows]

        return self._run_with_retry(operation)

    def fetch_one(
        self,
        query: str,
        parameters: Sequence[Any] = (),
    ) -> dict[str, Any] | None:
        def operation() -> dict[str, Any] | None:
            with self.connection() as connection:
                row = connection.execute(
                    query,
                    tuple(parameters),
                ).fetchone()
            return dict(row) if row else None

        return self._run_with_retry(operation)

    def execute(
        self,
        query: str,
        parameters: Sequence[Any] = (),
    ) -> int:
        def operation() -> int:
            with self.transaction() as connection:
                cursor = connection.execute(
                    query,
                    tuple(parameters),
                )
                return cursor.rowcount

        return self._run_with_retry(operation)

    def executemany(
        self,
        query: str,
        parameter_rows: Iterable[Sequence[Any]],
    ) -> int:
        rows = [tuple(row) for row in parameter_rows]

        if not rows:
            return 0

        def operation() -> int:
            with self.transaction() as connection:
                cursor = connection.executemany(
                    query,
                    rows,
                )
                return cursor.rowcount

        return self._run_with_retry(operation)

    @staticmethod
    def normalize_market_id(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def normalize_outcome(value: Any) -> str:
        return str(value or "").strip().casefold()

    @staticmethod
    def decode_json(value: Any, default: Any = None) -> Any:
        if value in (None, ""):
            return default

        if isinstance(value, (dict, list)):
            return value

        try:
            return json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return default

    # -------------------------------------------------------------------------
    # CANONICAL MARKET IDENTITY
    # -------------------------------------------------------------------------

    def get_market(
        self,
        condition_id: str,
    ) -> dict[str, Any] | None:
        self.require_table("canonical_market_identities")

        market_id = self.normalize_market_id(condition_id)

        return self.fetch_one(
            """
            SELECT *
            FROM canonical_market_identities
            WHERE LOWER(condition_id) = ?
            """,
            (market_id,),
        )

    def get_market_by_gamma_id(
        self,
        gamma_market_id: str,
    ) -> dict[str, Any] | None:
        self.require_table("canonical_market_identities")

        return self.fetch_one(
            """
            SELECT *
            FROM canonical_market_identities
            WHERE gamma_market_id = ?
            LIMIT 1
            """,
            (str(gamma_market_id).strip(),),
        )

    def get_tradable_markets(
        self,
        *,
        limit: int | None = None,
        category: str | None = None,
        market_type: str | None = None,
        min_liquidity: float | None = None,
    ) -> list[dict[str, Any]]:
        self.require_table("canonical_market_identities")

        conditions = [
            "tradable_identity = 1",
            "active = 1",
            "closed = 0",
            "archived = 0",
        ]
        parameters: list[Any] = []

        if category:
            conditions.append("LOWER(category) = LOWER(?)")
            parameters.append(category.strip())

        if market_type:
            conditions.append("LOWER(market_type) = LOWER(?)")
            parameters.append(market_type.strip())

        if min_liquidity is not None:
            conditions.append("liquidity >= ?")
            parameters.append(float(min_liquidity))

        query = f"""
            SELECT *
            FROM canonical_market_identities
            WHERE {" AND ".join(conditions)}
            ORDER BY
                volume_24h DESC,
                liquidity DESC,
                volume DESC
        """

        if limit is not None:
            query += "\nLIMIT ?"
            parameters.append(max(1, int(limit)))

        return self.fetch_all(query, parameters)

    def get_markets_by_ids(
        self,
        condition_ids: Sequence[str],
    ) -> dict[str, dict[str, Any]]:
        normalized = [
            self.normalize_market_id(value)
            for value in condition_ids
            if self.normalize_market_id(value)
        ]

        if not normalized:
            return {}

        placeholders = ", ".join("?" for _ in normalized)

        rows = self.fetch_all(
            f"""
            SELECT *
            FROM canonical_market_identities
            WHERE LOWER(condition_id) IN ({placeholders})
            """,
            normalized,
        )

        return {
            self.normalize_market_id(row["condition_id"]): row
            for row in rows
        }

    # -------------------------------------------------------------------------
    # STATUS AND PRICE
    # -------------------------------------------------------------------------

    def get_market_status(
        self,
        condition_id: str,
    ) -> dict[str, Any] | None:
        if not self.table_exists("market_metadata"):
            return None

        market_id = self.normalize_market_id(condition_id)

        return self.fetch_one(
            """
            SELECT *
            FROM market_metadata
            WHERE LOWER(market_id) = ?
               OR LOWER(condition_id) = ?
            LIMIT 1
            """,
            (market_id, market_id),
        )

    def get_price_metrics(
        self,
        condition_id: str,
    ) -> dict[str, Any] | None:
        if not self.table_exists("market_price_metrics"):
            return None

        market_id = self.normalize_market_id(condition_id)

        return self.fetch_one(
            """
            SELECT *
            FROM market_price_metrics
            WHERE LOWER(market_id) = ?
            LIMIT 1
            """,
            (market_id,),
        )

    # -------------------------------------------------------------------------
    # OPPORTUNITY AND CONSENSUS
    # -------------------------------------------------------------------------

    def get_master_opportunities(
        self,
        *,
        limit: int = 100,
        minimum_score: float | None = None,
        recommendation_prefix: str | None = None,
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        if not self.table_exists("master_opportunities"):
            return []

        conditions: list[str] = []
        parameters: list[Any] = []

        if minimum_score is not None:
            conditions.append("master_score >= ?")
            parameters.append(float(minimum_score))

        if recommendation_prefix:
            conditions.append("recommendation LIKE ?")
            parameters.append(
                f"{recommendation_prefix.strip()}%"
            )

        if not include_inactive:
            conditions.append(
                """
                LOWER(COALESCE(lifecycle_status, ''))
                NOT IN (
                    'resolved',
                    'closed',
                    'ended',
                    'ended_unconfirmed'
                )
                """
            )

        where_clause = (
            f"WHERE {' AND '.join(conditions)}"
            if conditions
            else ""
        )

        parameters.append(max(1, int(limit)))

        return self.fetch_all(
            f"""
            SELECT *
            FROM master_opportunities
            {where_clause}
            ORDER BY
                master_score DESC,
                data_completeness_score DESC,
                effective_wallet_count DESC
            LIMIT ?
            """,
            parameters,
        )

    def get_opportunity(
        self,
        condition_id: str,
        outcome: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.table_exists("master_opportunities"):
            return None

        market_id = self.normalize_market_id(condition_id)
        conditions = ["LOWER(market_id) = ?"]
        parameters: list[Any] = [market_id]

        if outcome:
            conditions.append("LOWER(TRIM(outcome)) = ?")
            parameters.append(self.normalize_outcome(outcome))

        return self.fetch_one(
            f"""
            SELECT *
            FROM master_opportunities
            WHERE {" AND ".join(conditions)}
            ORDER BY master_score DESC
            LIMIT 1
            """,
            parameters,
        )

    def get_institutional_consensus(
        self,
        condition_id: str,
        outcome: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.table_exists("institutional_consensus"):
            return []

        market_id = self.normalize_market_id(condition_id)
        conditions = ["LOWER(market_id) = ?"]
        parameters: list[Any] = [market_id]

        if outcome:
            conditions.append("LOWER(TRIM(outcome)) = ?")
            parameters.append(self.normalize_outcome(outcome))

        return self.fetch_all(
            f"""
            SELECT *
            FROM institutional_consensus
            WHERE {" AND ".join(conditions)}
            ORDER BY consensus_strength DESC
            """,
            parameters,
        )

    def get_position_evolution(
        self,
        condition_id: str,
        outcome: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.table_exists("position_evolution"):
            return []

        market_id = self.normalize_market_id(condition_id)
        conditions = ["LOWER(market_id) = ?"]
        parameters: list[Any] = [market_id]

        if outcome:
            conditions.append("LOWER(TRIM(outcome)) = ?")
            parameters.append(self.normalize_outcome(outcome))

        order_column = (
            "calculated_at"
            if "calculated_at" in self.get_table_columns(
                "position_evolution"
            )
            else "rowid"
        )

        return self.fetch_all(
            f"""
            SELECT *
            FROM position_evolution
            WHERE {" AND ".join(conditions)}
            ORDER BY {order_column} DESC
            """,
            parameters,
        )

    def get_closing_line_metrics(
        self,
        condition_id: str,
        outcome: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.table_exists("closing_line_metrics"):
            return []

        market_id = self.normalize_market_id(condition_id)
        conditions = ["LOWER(market_id) = ?"]
        parameters: list[Any] = [market_id]

        if outcome:
            conditions.append("LOWER(TRIM(outcome)) = ?")
            parameters.append(self.normalize_outcome(outcome))

        return self.fetch_all(
            f"""
            SELECT *
            FROM closing_line_metrics
            WHERE {" AND ".join(conditions)}
            ORDER BY opportunity_key
            """,
            parameters,
        )

    # -------------------------------------------------------------------------
    # WALLET AND POSITION DATA
    # -------------------------------------------------------------------------

    def get_positions(
        self,
        condition_id: str,
        *,
        latest_scans_only: bool = True,
    ) -> list[dict[str, Any]]:
        if not self.table_exists("positions"):
            return []

        market_id = self.normalize_market_id(condition_id)

        if (
            latest_scans_only
            and self.table_exists("wallet_scans")
        ):
            return self.fetch_all(
                """
                WITH latest_scans AS (
                    SELECT
                        wallet,
                        MAX(id) AS latest_scan_id
                    FROM wallet_scans
                    GROUP BY wallet
                )
                SELECT positions.*
                FROM positions
                INNER JOIN latest_scans
                    ON positions.wallet = latest_scans.wallet
                   AND positions.scan_id =
                       latest_scans.latest_scan_id
                WHERE LOWER(positions.market_id) = ?
                ORDER BY
                    positions.current_value DESC,
                    positions.cash_pnl DESC
                """,
                (market_id,),
            )

        return self.fetch_all(
            """
            SELECT *
            FROM positions
            WHERE LOWER(market_id) = ?
            ORDER BY
                current_value DESC,
                cash_pnl DESC
            """,
            (market_id,),
        )

    def get_wallet_positions(
        self,
        wallet: str,
        *,
        latest_scan_only: bool = True,
    ) -> list[dict[str, Any]]:
        if not self.table_exists("positions"):
            return []

        wallet_value = str(wallet or "").strip().lower()

        if (
            latest_scan_only
            and self.table_exists("wallet_scans")
        ):
            return self.fetch_all(
                """
                SELECT *
                FROM positions
                WHERE LOWER(wallet) = ?
                  AND scan_id = (
                      SELECT MAX(id)
                      FROM wallet_scans
                      WHERE LOWER(wallet) = ?
                  )
                ORDER BY current_value DESC
                """,
                (wallet_value, wallet_value),
            )

        return self.fetch_all(
            """
            SELECT *
            FROM positions
            WHERE LOWER(wallet) = ?
            ORDER BY scan_id DESC, current_value DESC
            """,
            (wallet_value,),
        )

    def get_consensus_history(
        self,
        condition_id: str,
        outcome: str | None = None,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self.table_exists("consensus_history"):
            return []

        market_id = self.normalize_market_id(condition_id)
        conditions = ["LOWER(market_id) = ?"]
        parameters: list[Any] = [market_id]

        if outcome:
            conditions.append("LOWER(TRIM(outcome)) = ?")
            parameters.append(self.normalize_outcome(outcome))

        parameters.append(max(1, int(limit)))

        return self.fetch_all(
            f"""
            SELECT *
            FROM consensus_history
            WHERE {" AND ".join(conditions)}
            ORDER BY id DESC
            LIMIT ?
            """,
            parameters,
        )

    # -------------------------------------------------------------------------
    # ALERTS
    # -------------------------------------------------------------------------

    def get_alerts(
        self,
        *,
        condition_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self.table_exists("master_alerts"):
            return []

        parameters: list[Any] = []
        where_clause = ""

        if condition_id:
            where_clause = "WHERE LOWER(market_id) = ?"
            parameters.append(
                self.normalize_market_id(condition_id)
            )

        parameters.append(max(1, int(limit)))

        return self.fetch_all(
            f"""
            SELECT *
            FROM master_alerts
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            parameters,
        )

    # -------------------------------------------------------------------------
    # UNIFIED MARKET INTELLIGENCE
    # -------------------------------------------------------------------------

    def get_market_intelligence(
        self,
        condition_id: str,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        """
        Return a unified market payload without mutating any source table.
        """
        market = self.get_market(condition_id)

        if market is None:
            return {}

        return {
            "canonical": market,
            "status": self.get_market_status(condition_id),
            "price_metrics": self.get_price_metrics(condition_id),
            "opportunity": self.get_opportunity(
                condition_id,
                outcome,
            ),
            "institutional_consensus": (
                self.get_institutional_consensus(
                    condition_id,
                    outcome,
                )
            ),
            "position_evolution": self.get_position_evolution(
                condition_id,
                outcome,
            ),
            "closing_line_metrics": (
                self.get_closing_line_metrics(
                    condition_id,
                    outcome,
                )
            ),
            "positions": self.get_positions(condition_id),
            "consensus_history": self.get_consensus_history(
                condition_id,
                outcome,
            ),
            "alerts": self.get_alerts(
                condition_id=condition_id,
            ),
        }

    def readiness_report(self) -> dict[str, Any]:
        tables = (
            "canonical_market_identities",
            "market_metadata",
            "market_price_metrics",
            "opportunity_scores",
            "institutional_consensus",
            "position_evolution",
            "closing_line_metrics",
            "consensus_history",
            "master_opportunities",
            "master_alerts",
            "positions",
            "wallet_scans",
        )

        return {
            table_name: {
                "exists": self.table_exists(table_name),
                "row_count": self.table_row_count(table_name),
            }
            for table_name in tables
        }


def main() -> None:
    data = DataAccess()

    print()
    print("=" * 108)
    print("POLYMARKET DATA ACCESS LAYER")
    print("=" * 108)

    report = data.readiness_report()

    for table_name, status in report.items():
        label = (
            f"{status['row_count']} rows"
            if status["exists"]
            else "NOT FOUND"
        )
        print(f"{table_name:<42}{label:>18}")

    print("=" * 108)

    tradable = data.get_tradable_markets(limit=5)

    print()
    print("TOP 5 TRADABLE MARKETS BY ACTIVITY")
    print("-" * 108)

    for index, market in enumerate(tradable, start=1):
        print(
            f"{index}. "
            f"{market.get('question', 'Unknown market')} | "
            f"Liquidity ${float(market.get('liquidity') or 0):,.0f} | "
            f"24h volume ${float(market.get('volume_24h') or 0):,.0f}"
        )

    print()
    print("DATA ACCESS LAYER READY")


if __name__ == "__main__":
    main()