from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"
DATA_API = "https://data-api.polymarket.com"

DEFAULT_WALLET_LIMIT = 50
DEFAULT_PAGE_LIMIT = 500
DEFAULT_MAX_RECORDS = 5000
DEFAULT_DELAY = 0.15
DEFAULT_DISPLAY_LIMIT = 20
MAX_RETRIES = 5
MAX_OFFSET = 10000


def configure_utf8() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def wallet_text(value: Any) -> str:
    return text(value).lower()


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def valid_wallet(wallet: str) -> bool:
    if len(wallet) != 42 or not wallet.startswith("0x"):
        return False
    try:
        int(wallet[2:], 16)
        return True
    except ValueError:
        return False


def connect() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(f"Database not found: {DB}")

    connection = sqlite3.connect(DB, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name=?
            """,
            (table_name,),
        ).fetchone()
        is not None
    )


def create_tables() -> None:
    connection = connect()
    try:
        if not table_exists(connection, "wallet_registry"):
            raise RuntimeError(
                "wallet_registry is missing. Run weekly_wallet_discovery.py first."
            )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS official_wallet_activity (
                activity_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                timestamp INTEGER NOT NULL DEFAULT 0,
                observed_at TEXT,
                condition_id TEXT,
                activity_type TEXT,
                side TEXT,
                asset TEXT,
                outcome TEXT,
                outcome_index INTEGER,
                size REAL NOT NULL DEFAULT 0,
                usdc_size REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                transaction_hash TEXT,
                title TEXT,
                slug TEXT,
                event_slug TEXT,
                name TEXT,
                pseudonym TEXT,
                raw_json TEXT NOT NULL,
                first_ingested_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_official_activity_wallet_time
            ON official_wallet_activity(wallet, timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_official_activity_market
            ON official_wallet_activity(condition_id, timestamp DESC);

            CREATE TABLE IF NOT EXISTS official_wallet_trades (
                trade_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                timestamp INTEGER NOT NULL DEFAULT 0,
                observed_at TEXT,
                condition_id TEXT,
                side TEXT,
                asset TEXT,
                outcome TEXT,
                outcome_index INTEGER,
                size REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                notional REAL NOT NULL DEFAULT 0,
                transaction_hash TEXT,
                title TEXT,
                slug TEXT,
                event_slug TEXT,
                raw_json TEXT NOT NULL,
                first_ingested_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_official_trades_wallet_time
            ON official_wallet_trades(wallet, timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_official_trades_market
            ON official_wallet_trades(condition_id, timestamp DESC);

            CREATE TABLE IF NOT EXISTS wallet_activity_checkpoints (
                wallet TEXT PRIMARY KEY,
                last_activity_timestamp INTEGER NOT NULL DEFAULT 0,
                last_trade_timestamp INTEGER NOT NULL DEFAULT 0,
                activity_records INTEGER NOT NULL DEFAULT 0,
                trade_records INTEGER NOT NULL DEFAULT 0,
                last_success_at TEXT,
                last_error_at TEXT,
                last_error_message TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallet_activity_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                wallet TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_wallet_activity_errors_wallet
            ON wallet_activity_errors(wallet, created_at DESC);

            CREATE TABLE IF NOT EXISTS wallet_activity_ingestion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                wallets_selected INTEGER NOT NULL DEFAULT 0,
                wallets_succeeded INTEGER NOT NULL DEFAULT 0,
                wallets_failed INTEGER NOT NULL DEFAULT 0,
                activity_rows_received INTEGER NOT NULL DEFAULT 0,
                activity_rows_inserted INTEGER NOT NULL DEFAULT 0,
                trade_rows_received INTEGER NOT NULL DEFAULT 0,
                trade_rows_inserted INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def fetch_json(url: str) -> Any:
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "PolymarketIntelligencePlatform/"
                    "official-wallet-activity-v1"
                ),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(
                    response.read().decode("utf-8", errors="replace")
                )

        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in {425, 429, 500, 502, 503, 504}:
                raise

        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as error:
            last_error = error

        if attempt < MAX_RETRIES - 1:
            delay = min(2 ** attempt, 16)
            print(f"    Retry after {delay}s: {last_error}")
            time.sleep(delay)

    raise RuntimeError(
        f"Request failed after {MAX_RETRIES} attempts: {url} | {last_error}"
    )


def build_url(
    endpoint: str,
    wallet: str,
    limit: int,
    offset: int,
) -> str:
    query = urllib.parse.urlencode(
        {
            "user": wallet,
            "limit": limit,
            "offset": offset,
        }
    )
    return f"{DATA_API}{endpoint}?{query}"


def fetch_paginated(
    endpoint: str,
    wallet: str,
    page_limit: int,
    max_records: int,
    delay: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0

    while offset <= MAX_OFFSET and len(rows) < max_records:
        limit = min(page_limit, max_records - len(rows))
        payload = fetch_json(build_url(endpoint, wallet, limit, offset))

        if not isinstance(payload, list):
            raise RuntimeError(
                f"Unexpected {endpoint} response: {type(payload).__name__}"
            )

        page = [item for item in payload if isinstance(item, dict)]
        rows.extend(page)

        if len(payload) < limit:
            break

        offset += limit

        if delay > 0:
            time.sleep(delay)

    return rows[:max_records]


def canonical_key(prefix: str, wallet: str, row: dict[str, Any]) -> str:
    transaction_hash = text(row.get("transactionHash")).lower()
    timestamp = integer(row.get("timestamp"))
    condition_id = text(row.get("conditionId")).lower()
    asset = text(row.get("asset"))
    side = text(row.get("side")).upper()
    activity_type = text(row.get("type")).upper()
    size = number(row.get("size"))
    price = number(row.get("price"))

    raw_identity = "|".join(
        [
            prefix,
            wallet,
            transaction_hash,
            str(timestamp),
            condition_id,
            asset,
            side,
            activity_type,
            f"{size:.12f}",
            f"{price:.12f}",
        ]
    )

    return hashlib.sha256(raw_identity.encode("utf-8")).hexdigest()


def select_wallets(
    statuses: list[str],
    wallet_limit: int,
    only_scan_required: bool,
) -> list[dict[str, Any]]:
    connection = connect()
    try:
        placeholders = ", ".join("?" for _ in statuses)

        sql = f"""
            SELECT
                wr.wallet,
                wr.status,
                wr.qualification_eligible,
                wr.leaderboard_appearance_count,
                wr.best_rank,
                wr.best_observed_pnl,
                wr.highest_observed_volume,
                COALESCE(cwe.needs_position_scan, 0) AS needs_position_scan,
                COALESCE(cwe.needs_history_scan, 0) AS needs_history_scan,
                COALESCE(cwe.evaluation_score, 0) AS evaluation_score
            FROM wallet_registry wr
            LEFT JOIN candidate_wallet_evaluations cwe
              ON cwe.wallet = wr.wallet
            WHERE wr.status IN ({placeholders})
        """

        parameters: list[Any] = list(statuses)

        if only_scan_required:
            sql += """
                AND (
                    COALESCE(cwe.needs_position_scan, 0) = 1
                    OR COALESCE(cwe.needs_history_scan, 0) = 1
                )
            """

        sql += """
            ORDER BY
                CASE wr.status
                    WHEN 'ELITE' THEN 1
                    WHEN 'QUALIFIED' THEN 2
                    WHEN 'WATCHLIST' THEN 3
                    ELSE 4
                END,
                wr.qualification_eligible DESC,
                cwe.evaluation_score DESC,
                wr.leaderboard_appearance_count DESC,
                wr.best_rank ASC,
                wr.best_observed_pnl DESC
        """

        if wallet_limit > 0:
            sql += " LIMIT ?"
            parameters.append(wallet_limit)

        return [
            dict(row)
            for row in connection.execute(sql, tuple(parameters)).fetchall()
        ]

    finally:
        connection.close()


def save_activity_rows(
    wallet: str,
    rows: list[dict[str, Any]],
    ingested_at: str,
) -> int:
    connection = connect()
    inserted = 0

    try:
        connection.execute("BEGIN IMMEDIATE")

        for row in rows:
            key = canonical_key("ACTIVITY", wallet, row)
            timestamp = integer(row.get("timestamp"))
            observed_at = (
                datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                if timestamp > 0
                else ""
            )

            before = connection.total_changes

            connection.execute(
                """
                INSERT INTO official_wallet_activity (
                    activity_key, wallet, timestamp, observed_at,
                    condition_id, activity_type, side, asset,
                    outcome, outcome_index, size, usdc_size,
                    price, transaction_hash, title, slug,
                    event_slug, name, pseudonym, raw_json,
                    first_ingested_at, last_seen_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(activity_key) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,
                    raw_json=excluded.raw_json
                """,
                (
                    key,
                    wallet,
                    timestamp,
                    observed_at,
                    text(row.get("conditionId")).lower(),
                    text(row.get("type")).upper(),
                    text(row.get("side")).upper(),
                    text(row.get("asset")),
                    text(row.get("outcome")),
                    integer(row.get("outcomeIndex")),
                    number(row.get("size")),
                    number(row.get("usdcSize")),
                    number(row.get("price")),
                    text(row.get("transactionHash")).lower(),
                    text(row.get("title")),
                    text(row.get("slug")),
                    text(row.get("eventSlug")),
                    text(row.get("name")),
                    text(row.get("pseudonym")),
                    stable_json(row),
                    ingested_at,
                    ingested_at,
                ),
            )

            if connection.total_changes > before:
                inserted += 1

        connection.commit()
        return inserted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_trade_rows(
    wallet: str,
    rows: list[dict[str, Any]],
    ingested_at: str,
) -> int:
    connection = connect()
    inserted = 0

    try:
        connection.execute("BEGIN IMMEDIATE")

        for row in rows:
            key = canonical_key("TRADE", wallet, row)
            timestamp = integer(row.get("timestamp"))
            size = number(row.get("size"))
            price = number(row.get("price"))
            observed_at = (
                datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                if timestamp > 0
                else ""
            )

            exists = connection.execute(
                """
                SELECT 1
                FROM official_wallet_trades
                WHERE trade_key=?
                """,
                (key,),
            ).fetchone()

            connection.execute(
                """
                INSERT INTO official_wallet_trades (
                    trade_key, wallet, timestamp, observed_at,
                    condition_id, side, asset, outcome,
                    outcome_index, size, price, notional,
                    transaction_hash, title, slug, event_slug,
                    raw_json, first_ingested_at, last_seen_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(trade_key) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,
                    raw_json=excluded.raw_json
                """,
                (
                    key,
                    wallet,
                    timestamp,
                    observed_at,
                    text(row.get("conditionId")).lower(),
                    text(row.get("side")).upper(),
                    text(row.get("asset")),
                    text(row.get("outcome")),
                    integer(row.get("outcomeIndex")),
                    size,
                    price,
                    size * price,
                    text(row.get("transactionHash")).lower(),
                    text(row.get("title")),
                    text(row.get("slug")),
                    text(row.get("eventSlug")),
                    stable_json(row),
                    ingested_at,
                    ingested_at,
                ),
            )

            if exists is None:
                inserted += 1

        connection.commit()
        return inserted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def update_checkpoint(
    wallet: str,
    activity_rows: list[dict[str, Any]],
    trade_rows: list[dict[str, Any]],
    success: bool,
    error_message: str = "",
) -> None:
    connection = connect()
    timestamp = now_iso()

    try:
        last_activity = max(
            (integer(row.get("timestamp")) for row in activity_rows),
            default=0,
        )
        last_trade = max(
            (integer(row.get("timestamp")) for row in trade_rows),
            default=0,
        )

        connection.execute(
            """
            INSERT INTO wallet_activity_checkpoints (
                wallet, last_activity_timestamp, last_trade_timestamp,
                activity_records, trade_records, last_success_at,
                last_error_at, last_error_message, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                last_activity_timestamp=
                    MAX(last_activity_timestamp, excluded.last_activity_timestamp),
                last_trade_timestamp=
                    MAX(last_trade_timestamp, excluded.last_trade_timestamp),
                activity_records=excluded.activity_records,
                trade_records=excluded.trade_records,
                last_success_at=excluded.last_success_at,
                last_error_at=excluded.last_error_at,
                last_error_message=excluded.last_error_message,
                updated_at=excluded.updated_at
            """,
            (
                wallet,
                last_activity,
                last_trade,
                len(activity_rows),
                len(trade_rows),
                timestamp if success else None,
                None if success else timestamp,
                "" if success else error_message,
                timestamp,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def log_wallet_error(
    run_id: int,
    wallet: str,
    endpoint: str,
    error: Exception,
) -> None:
    connection = connect()
    try:
        connection.execute(
            """
            INSERT INTO wallet_activity_errors (
                run_id, wallet, endpoint, error_type,
                error_message, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                wallet,
                endpoint,
                type(error).__name__,
                str(error),
                now_iso(),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def start_run(wallet_count: int) -> tuple[int, datetime]:
    started = now()
    connection = connect()
    try:
        cursor = connection.execute(
            """
            INSERT INTO wallet_activity_ingestion_runs (
                started_at, wallets_selected, status
            )
            VALUES (?, ?, 'RUNNING')
            """,
            (started.isoformat(), wallet_count),
        )
        connection.commit()
        return cursor.lastrowid, started
    finally:
        connection.close()


def finish_run(
    run_id: int,
    started: datetime,
    status: str,
    succeeded: int,
    failed: int,
    activity_received: int,
    activity_inserted: int,
    trades_received: int,
    trades_inserted: int,
    error_message: str = "",
) -> None:
    finished = now()
    connection = connect()
    try:
        connection.execute(
            """
            UPDATE wallet_activity_ingestion_runs
            SET finished_at=?,
                elapsed_seconds=?,
                wallets_succeeded=?,
                wallets_failed=?,
                activity_rows_received=?,
                activity_rows_inserted=?,
                trade_rows_received=?,
                trade_rows_inserted=?,
                status=?,
                error_message=?
            WHERE id=?
            """,
            (
                finished.isoformat(),
                (finished - started).total_seconds(),
                succeeded,
                failed,
                activity_received,
                activity_inserted,
                trades_received,
                trades_inserted,
                status,
                error_message,
                run_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def show_summary(display_limit: int) -> None:
    connection = connect()
    try:
        activity_total = connection.execute(
            "SELECT COUNT(*) FROM official_wallet_activity"
        ).fetchone()[0]
        trade_total = connection.execute(
            "SELECT COUNT(*) FROM official_wallet_trades"
        ).fetchone()[0]
        checkpoint_total = connection.execute(
            "SELECT COUNT(*) FROM wallet_activity_checkpoints"
        ).fetchone()[0]

        rows = connection.execute(
            """
            SELECT
                wallet,
                activity_records,
                trade_records,
                last_activity_timestamp,
                last_trade_timestamp,
                last_success_at,
                last_error_message
            FROM wallet_activity_checkpoints
            ORDER BY trade_records DESC, activity_records DESC
            LIMIT ?
            """,
            (max(display_limit, 1),),
        ).fetchall()
    finally:
        connection.close()

    print()
    print("=" * 112)
    print("OFFICIAL WALLET ACTIVITY SUMMARY")
    print("=" * 112)
    print(f"Stored official activity rows:  {activity_total}")
    print(f"Stored official trade rows:     {trade_total}")
    print(f"Wallet checkpoints:             {checkpoint_total}")
    print("=" * 112)

    for index, row in enumerate(rows, start=1):
        print(
            f"{index:>3}. {row['wallet']} | "
            f"activity {row['activity_records']:>5} | "
            f"trades {row['trade_records']:>5} | "
            f"last success {row['last_success_at'] or '-'}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest official public Polymarket Data API activity and "
            "trade history for a controlled wallet subset."
        )
    )

    parser.add_argument(
        "--status",
        action="append",
        choices=["CANDIDATE", "WATCHLIST", "QUALIFIED", "ELITE"],
        help=(
            "Registry status to ingest. May be repeated. "
            "Default: WATCHLIST, QUALIFIED, ELITE."
        ),
    )
    parser.add_argument(
        "--wallet-limit",
        type=int,
        default=DEFAULT_WALLET_LIMIT,
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=DEFAULT_PAGE_LIMIT,
    )
    parser.add_argument(
        "--max-records-per-endpoint",
        type=int,
        default=DEFAULT_MAX_RECORDS,
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_DELAY,
    )
    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )
    parser.add_argument(
        "--only-scan-required",
        action="store_true",
    )
    parser.add_argument(
        "--continue-on-wallet-failure",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8()
    args = parse_args()

    statuses = args.status or ["WATCHLIST", "QUALIFIED", "ELITE"]
    wallet_limit = max(args.wallet_limit, 0)
    page_limit = min(max(args.page_limit, 1), 500)
    max_records = min(
        max(args.max_records_per_endpoint, 1),
        MAX_OFFSET + page_limit,
    )
    delay = max(args.request_delay, 0.0)

    print()
    print("=" * 112)
    print("POLYMARKET OFFICIAL WALLET ACTIVITY ENGINE v1")
    print("=" * 112)
    print(f"Database:                    {DB}")
    print(f"Data API:                    {DATA_API}")
    print(f"Statuses:                    {', '.join(statuses)}")
    print(f"Wallet limit:                {wallet_limit or 'ALL'}")
    print(f"Page limit:                  {page_limit}")
    print(f"Maximum records/endpoint:    {max_records}")
    print(f"Only scan-required wallets:  {args.only_scan_required}")
    print("=" * 112)

    create_tables()

    wallets = select_wallets(
        statuses=statuses,
        wallet_limit=wallet_limit,
        only_scan_required=args.only_scan_required,
    )

    if not wallets:
        raise RuntimeError(
            "No registry wallets matched the selected statuses. "
            "Apply WATCHLIST recommendations first or choose CANDIDATE."
        )

    run_id, started = start_run(len(wallets))

    succeeded = 0
    failed = 0
    activity_received = 0
    activity_inserted = 0
    trades_received = 0
    trades_inserted = 0
    errors: list[str] = []

    try:
        for index, registry in enumerate(wallets, start=1):
            wallet = wallet_text(registry["wallet"])

            if not valid_wallet(wallet):
                continue

            print()
            print("-" * 112)
            print(
                f"WALLET {index}/{len(wallets)}: {wallet} "
                f"[{registry['status']}]"
            )
            print("-" * 112)

            activity_rows: list[dict[str, Any]] = []
            trade_rows: list[dict[str, Any]] = []

            try:
                activity_rows = fetch_paginated(
                    endpoint="/activity",
                    wallet=wallet,
                    page_limit=page_limit,
                    max_records=max_records,
                    delay=delay,
                )

                trade_rows = fetch_paginated(
                    endpoint="/trades",
                    wallet=wallet,
                    page_limit=min(page_limit, 10000),
                    max_records=max_records,
                    delay=delay,
                )

                ingested_at = now_iso()

                inserted_activity = save_activity_rows(
                    wallet,
                    activity_rows,
                    ingested_at,
                )

                inserted_trades = save_trade_rows(
                    wallet,
                    trade_rows,
                    ingested_at,
                )

                update_checkpoint(
                    wallet,
                    activity_rows,
                    trade_rows,
                    True,
                )

                activity_received += len(activity_rows)
                activity_inserted += inserted_activity
                trades_received += len(trade_rows)
                trades_inserted += inserted_trades
                succeeded += 1

                print(
                    f"Activity: {len(activity_rows)} received, "
                    f"{inserted_activity} new | "
                    f"Trades: {len(trade_rows)} received, "
                    f"{inserted_trades} new"
                )

            except Exception as error:
                failed += 1
                message = f"{wallet}: {type(error).__name__}: {error}"
                errors.append(message)

                update_checkpoint(
                    wallet,
                    activity_rows,
                    trade_rows,
                    False,
                    message,
                )

                log_wallet_error(
                    run_id,
                    wallet,
                    "activity/trades",
                    error,
                )

                print(f"FAILED: {message}")

                if not args.continue_on_wallet_failure:
                    raise

        final_status = (
            "SUCCESS"
            if failed == 0
            else "PARTIAL_SUCCESS"
        )

        finish_run(
            run_id,
            started,
            final_status,
            succeeded,
            failed,
            activity_received,
            activity_inserted,
            trades_received,
            trades_inserted,
            "\n".join(errors),
        )

        print()
        print("=" * 112)
        print("OFFICIAL WALLET ACTIVITY INGESTION COMPLETE")
        print("=" * 112)
        print(f"Wallets succeeded:             {succeeded}")
        print(f"Wallets failed:                {failed}")
        print(f"Activity rows received/new:    {activity_received} / {activity_inserted}")
        print(f"Trade rows received/new:       {trades_received} / {trades_inserted}")
        print("=" * 112)

        show_summary(args.display_limit)

    except Exception as error:
        finish_run(
            run_id,
            started,
            "FAILED",
            succeeded,
            max(failed, 1),
            activity_received,
            activity_inserted,
            trades_received,
            trades_inserted,
            f"{type(error).__name__}: {error}",
        )
        raise


if __name__ == "__main__":
    main()