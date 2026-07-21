from __future__ import annotations

import argparse
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
LEADERBOARD_ENDPOINT = "/v1/leaderboard"

DEFAULT_LIMIT = 50
DEFAULT_MAX_RESULTS = 250
DEFAULT_DISPLAY_LIMIT = 25
DEFAULT_DELAY = 0.15
MAX_RETRIES = 5

DEFAULT_BOARDS = [
    ("OVERALL", "WEEK", "PNL"),
    ("OVERALL", "WEEK", "VOL"),
    ("OVERALL", "MONTH", "PNL"),
    ("OVERALL", "MONTH", "VOL"),
    ("OVERALL", "ALL", "PNL"),
    ("SPORTS", "WEEK", "PNL"),
    ("SPORTS", "WEEK", "VOL"),
    ("SPORTS", "MONTH", "PNL"),
    ("SPORTS", "ALL", "PNL"),
]

VALID_CATEGORIES = {
    "OVERALL", "POLITICS", "SPORTS", "CRYPTO", "CULTURE",
    "MENTIONS", "WEATHER", "ECONOMICS", "TECH", "FINANCE",
}
VALID_PERIODS = {"DAY", "WEEK", "MONTH", "ALL"}
VALID_ORDERINGS = {"PNL", "VOL"}
PROTECTED_STATUSES = {"QUALIFIED", "ELITE"}


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


def money(value: Any) -> str:
    amount = number(value)
    if amount > 0:
        return f"+${amount:,.2f}"
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return "$0.00"


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


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    return {
        text(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        )
    }


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    if column_name not in table_columns(connection, table_name):
        connection.execute(
            f'ALTER TABLE "{table_name}" '
            f'ADD COLUMN "{column_name}" {definition}'
        )


def create_tables() -> None:
    connection = connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS wallet_registry (
                wallet TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'CANDIDATE',
                first_discovered_at TEXT,
                last_discovered_at TEXT,
                first_discovery_source TEXT,
                latest_discovery_source TEXT,
                discovery_count INTEGER NOT NULL DEFAULT 0,
                leaderboard_appearance_count INTEGER NOT NULL DEFAULT 0,
                best_rank INTEGER,
                latest_rank INTEGER,
                latest_username TEXT,
                latest_x_username TEXT,
                latest_profile_image TEXT,
                latest_verified_badge INTEGER NOT NULL DEFAULT 0,
                latest_category TEXT,
                latest_time_period TEXT,
                latest_order_by TEXT,
                latest_pnl REAL NOT NULL DEFAULT 0,
                latest_volume REAL NOT NULL DEFAULT 0,
                best_observed_pnl REAL NOT NULL DEFAULT 0,
                highest_observed_volume REAL NOT NULL DEFAULT 0,
                weekly_pnl_appearances INTEGER NOT NULL DEFAULT 0,
                weekly_volume_appearances INTEGER NOT NULL DEFAULT 0,
                monthly_pnl_appearances INTEGER NOT NULL DEFAULT 0,
                all_time_pnl_appearances INTEGER NOT NULL DEFAULT 0,
                sports_appearances INTEGER NOT NULL DEFAULT 0,
                active_for_scanning INTEGER NOT NULL DEFAULT 0,
                qualification_eligible INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_key TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                time_period TEXT NOT NULL,
                order_by TEXT NOT NULL,
                requested_limit INTEGER NOT NULL DEFAULT 50,
                requested_max_results INTEGER NOT NULL DEFAULT 0,
                entries_received INTEGER NOT NULL DEFAULT 0,
                pages_requested INTEGER NOT NULL DEFAULT 0,
                api_url TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS leaderboard_entries (
                entry_key TEXT PRIMARY KEY,
                snapshot_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                rank INTEGER,
                username TEXT,
                pnl REAL NOT NULL DEFAULT 0,
                volume REAL NOT NULL DEFAULT 0,
                profile_image TEXT,
                x_username TEXT,
                verified_badge INTEGER NOT NULL DEFAULT 0,
                category TEXT NOT NULL,
                time_period TEXT NOT NULL,
                order_by TEXT NOT NULL,
                raw_json TEXT,
                observed_at TEXT NOT NULL,
                FOREIGN KEY(snapshot_id)
                    REFERENCES leaderboard_snapshots(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS wallet_discovery_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT UNIQUE NOT NULL,
                wallet TEXT NOT NULL,
                event_type TEXT NOT NULL,
                discovery_source TEXT NOT NULL,
                snapshot_id INTEGER,
                previous_status TEXT,
                resulting_status TEXT,
                category TEXT,
                time_period TEXT,
                order_by TEXT,
                rank INTEGER,
                pnl REAL,
                volume REAL,
                explanation_json TEXT,
                discovered_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallet_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                previous_status TEXT,
                new_status TEXT NOT NULL,
                reason TEXT NOT NULL,
                source_module TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallet_discovery_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                board_count INTEGER NOT NULL DEFAULT 0,
                successful_boards INTEGER NOT NULL DEFAULT 0,
                failed_boards INTEGER NOT NULL DEFAULT 0,
                entries_received INTEGER NOT NULL DEFAULT 0,
                valid_entries INTEGER NOT NULL DEFAULT 0,
                invalid_entries INTEGER NOT NULL DEFAULT 0,
                unique_wallets_seen INTEGER NOT NULL DEFAULT 0,
                new_wallets_added INTEGER NOT NULL DEFAULT 0,
                existing_wallets_updated INTEGER NOT NULL DEFAULT 0,
                protected_wallets_preserved INTEGER NOT NULL DEFAULT 0,
                qualification_candidates INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_wallet_registry_status
            ON wallet_registry(
                status,
                qualification_eligible,
                leaderboard_appearance_count DESC
            );

            CREATE INDEX IF NOT EXISTS idx_leaderboard_entries_wallet
            ON leaderboard_entries(wallet, observed_at DESC);
            """
        )

        # Safe migration if an earlier wallet_registry already exists.
        required_columns = {
            "status": "TEXT NOT NULL DEFAULT 'CANDIDATE'",
            "first_discovered_at": "TEXT",
            "last_discovered_at": "TEXT",
            "first_discovery_source": "TEXT",
            "latest_discovery_source": "TEXT",
            "discovery_count": "INTEGER NOT NULL DEFAULT 0",
            "leaderboard_appearance_count": "INTEGER NOT NULL DEFAULT 0",
            "best_rank": "INTEGER",
            "latest_rank": "INTEGER",
            "latest_username": "TEXT",
            "latest_x_username": "TEXT",
            "latest_profile_image": "TEXT",
            "latest_verified_badge": "INTEGER NOT NULL DEFAULT 0",
            "latest_category": "TEXT",
            "latest_time_period": "TEXT",
            "latest_order_by": "TEXT",
            "latest_pnl": "REAL NOT NULL DEFAULT 0",
            "latest_volume": "REAL NOT NULL DEFAULT 0",
            "best_observed_pnl": "REAL NOT NULL DEFAULT 0",
            "highest_observed_volume": "REAL NOT NULL DEFAULT 0",
            "weekly_pnl_appearances": "INTEGER NOT NULL DEFAULT 0",
            "weekly_volume_appearances": "INTEGER NOT NULL DEFAULT 0",
            "monthly_pnl_appearances": "INTEGER NOT NULL DEFAULT 0",
            "all_time_pnl_appearances": "INTEGER NOT NULL DEFAULT 0",
            "sports_appearances": "INTEGER NOT NULL DEFAULT 0",
            "active_for_scanning": "INTEGER NOT NULL DEFAULT 0",
            "qualification_eligible": "INTEGER NOT NULL DEFAULT 0",
            "metadata_json": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }

        for column, definition in required_columns.items():
            ensure_column(connection, "wallet_registry", column, definition)

        connection.commit()
    finally:
        connection.close()


def build_url(
    category: str,
    period: str,
    order_by: str,
    limit: int,
    offset: int,
) -> str:
    query = urllib.parse.urlencode(
        {
            "category": category,
            "timePeriod": period,
            "orderBy": order_by,
            "limit": limit,
            "offset": offset,
        }
    )
    return DATA_API + LEADERBOARD_ENDPOINT + "?" + query


def fetch_json(url: str) -> Any:
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "PolymarketIntelligencePlatform/"
                    "weekly-wallet-discovery-v1"
                ),
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:
                return json.loads(
                    response.read().decode(
                        "utf-8",
                        errors="replace",
                    )
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
            print(f"  Retrying after {delay}s: {last_error}")
            time.sleep(delay)

    raise RuntimeError(
        f"Request failed after {MAX_RETRIES} attempts: {last_error}"
    )


def fetch_board(
    category: str,
    period: str,
    order_by: str,
    limit: int,
    max_results: int,
    delay: float,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    entries: list[dict[str, Any]] = []
    urls: list[str] = []
    pages = 0
    offset = 0

    while offset <= 1000 and len(entries) < max_results:
        page_limit = min(limit, max_results - len(entries), 50)
        url = build_url(
            category,
            period,
            order_by,
            page_limit,
            offset,
        )
        urls.append(url)

        payload = fetch_json(url)
        if not isinstance(payload, list):
            raise RuntimeError(
                f"Expected list response, got {type(payload).__name__}"
            )

        pages += 1
        entries.extend(
            item for item in payload if isinstance(item, dict)
        )

        print(
            f"  Page {pages}: {len(payload)} entries "
            f"(offset {offset})"
        )

        if len(payload) < page_limit:
            break

        offset += page_limit

        if delay > 0:
            time.sleep(delay)

    return entries[:max_results], pages, urls


def qualification_eligible(
    appearances: int,
    best_rank: int,
    sports_appearances: int,
    weekly_pnl_appearances: int,
    monthly_pnl_appearances: int,
) -> int:
    if appearances >= 3:
        return 1
    if best_rank <= 25 and appearances >= 2:
        return 1
    if sports_appearances >= 2 and weekly_pnl_appearances >= 1:
        return 1
    if monthly_pnl_appearances >= 2:
        return 1
    return 0


def create_snapshot(
    category: str,
    period: str,
    order_by: str,
    limit: int,
    max_results: int,
    started_at: str,
) -> tuple[int, str]:
    snapshot_key = (
        f"{category}:{period}:{order_by}:{started_at}"
    )
    connection = connect()

    try:
        cursor = connection.execute(
            """
            INSERT INTO leaderboard_snapshots (
                snapshot_key,
                category,
                time_period,
                order_by,
                requested_limit,
                requested_max_results,
                api_url,
                started_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'RUNNING')
            """,
            (
                snapshot_key,
                category,
                period,
                order_by,
                limit,
                max_results,
                build_url(category, period, order_by, limit, 0),
                started_at,
            ),
        )
        connection.commit()
        return cursor.lastrowid, snapshot_key
    finally:
        connection.close()


def finish_snapshot(
    snapshot_id: int,
    status: str,
    entry_count: int,
    page_count: int,
    urls: list[str],
    error_message: str = "",
) -> None:
    connection = connect()
    try:
        connection.execute(
            """
            UPDATE leaderboard_snapshots
            SET completed_at=?,
                entries_received=?,
                pages_requested=?,
                status=?,
                error_message=?,
                metadata_json=?
            WHERE id=?
            """,
            (
                now_iso(),
                entry_count,
                page_count,
                status,
                error_message,
                json.dumps({"requested_urls": urls}),
                snapshot_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def save_entries(
    snapshot_id: int,
    snapshot_key: str,
    category: str,
    period: str,
    order_by: str,
    entries: list[dict[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    connection = connect()
    result = {
        "valid": 0,
        "invalid": 0,
        "new": 0,
        "updated": 0,
        "protected": 0,
        "wallets": set(),
    }

    source = f"LEADERBOARD:{category}:{period}:{order_by}"

    try:
        connection.execute("BEGIN IMMEDIATE")

        for index, raw in enumerate(entries):
            wallet = wallet_text(raw.get("proxyWallet"))

            if not valid_wallet(wallet):
                result["invalid"] += 1
                continue

            rank = integer(raw.get("rank"), index + 1)
            username = text(raw.get("userName"))
            pnl = number(raw.get("pnl"))
            volume = number(raw.get("vol"))
            profile_image = text(raw.get("profileImage"))
            x_username = text(raw.get("xUsername"))
            verified = int(bool(raw.get("verifiedBadge")))
            entry_key = f"{snapshot_key}:{wallet}"

            connection.execute(
                """
                INSERT OR REPLACE INTO leaderboard_entries (
                    entry_key, snapshot_id, wallet, rank,
                    username, pnl, volume, profile_image,
                    x_username, verified_badge, category,
                    time_period, order_by, raw_json, observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_key,
                    snapshot_id,
                    wallet,
                    rank,
                    username,
                    pnl,
                    volume,
                    profile_image,
                    x_username,
                    verified,
                    category,
                    period,
                    order_by,
                    json.dumps(raw, ensure_ascii=False),
                    observed_at,
                ),
            )

            existing = connection.execute(
                "SELECT * FROM wallet_registry WHERE wallet=?",
                (wallet,),
            ).fetchone()

            weekly_pnl = int(period == "WEEK" and order_by == "PNL")
            weekly_volume = int(period == "WEEK" and order_by == "VOL")
            monthly_pnl = int(period == "MONTH" and order_by == "PNL")
            all_time_pnl = int(period == "ALL" and order_by == "PNL")
            sports = int(category == "SPORTS")

            if existing is None:
                eligibility = qualification_eligible(
                    1,
                    rank,
                    sports,
                    weekly_pnl,
                    monthly_pnl,
                )

                connection.execute(
                    """
                    INSERT INTO wallet_registry (
                        wallet, status, first_discovered_at,
                        last_discovered_at, first_discovery_source,
                        latest_discovery_source, discovery_count,
                        leaderboard_appearance_count, best_rank,
                        latest_rank, latest_username, latest_x_username,
                        latest_profile_image, latest_verified_badge,
                        latest_category, latest_time_period,
                        latest_order_by, latest_pnl, latest_volume,
                        best_observed_pnl, highest_observed_volume,
                        weekly_pnl_appearances,
                        weekly_volume_appearances,
                        monthly_pnl_appearances,
                        all_time_pnl_appearances,
                        sports_appearances, active_for_scanning,
                        qualification_eligible, metadata_json,
                        created_at, updated_at
                    )
                    VALUES (
                        ?, 'CANDIDATE', ?, ?, ?, ?, 1, 1, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, 0, ?, ?, ?, ?
                    )
                    """,
                    (
                        wallet,
                        observed_at,
                        observed_at,
                        source,
                        source,
                        rank,
                        rank,
                        username,
                        x_username,
                        profile_image,
                        verified,
                        category,
                        period,
                        order_by,
                        pnl,
                        volume,
                        pnl,
                        volume,
                        weekly_pnl,
                        weekly_volume,
                        monthly_pnl,
                        all_time_pnl,
                        sports,
                        eligibility,
                        json.dumps({"latest_snapshot_id": snapshot_id}),
                        observed_at,
                        observed_at,
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO wallet_status_history (
                        wallet, previous_status, new_status,
                        reason, source_module, changed_at
                    )
                    VALUES (?, NULL, 'CANDIDATE', ?,
                            'weekly_wallet_discovery', ?)
                    """,
                    (
                        wallet,
                        f"First appearance on {category}/{period}/{order_by}",
                        observed_at,
                    ),
                )

                previous_status = None
                resulting_status = "CANDIDATE"
                event_type = "DISCOVERED"
                result["new"] += 1

            else:
                previous_status = text(existing["status"]).upper() or "CANDIDATE"
                resulting_status = previous_status
                event_type = "REDISCOVERED"

                if previous_status in PROTECTED_STATUSES:
                    result["protected"] += 1

                old_best = integer(existing["best_rank"], rank)
                best_rank = min(old_best, rank)
                appearances = integer(
                    existing["leaderboard_appearance_count"]
                ) + 1
                new_weekly_pnl = (
                    integer(existing["weekly_pnl_appearances"])
                    + weekly_pnl
                )
                new_monthly_pnl = (
                    integer(existing["monthly_pnl_appearances"])
                    + monthly_pnl
                )
                new_sports = (
                    integer(existing["sports_appearances"])
                    + sports
                )

                eligibility = max(
                    integer(existing["qualification_eligible"]),
                    qualification_eligible(
                        appearances,
                        best_rank,
                        new_sports,
                        new_weekly_pnl,
                        new_monthly_pnl,
                    ),
                )

                connection.execute(
                    """
                    UPDATE wallet_registry
                    SET status=?,
                        last_discovered_at=?,
                        latest_discovery_source=?,
                        discovery_count=discovery_count+1,
                        leaderboard_appearance_count=
                            leaderboard_appearance_count+1,
                        best_rank=?,
                        latest_rank=?,
                        latest_username=?,
                        latest_x_username=?,
                        latest_profile_image=?,
                        latest_verified_badge=?,
                        latest_category=?,
                        latest_time_period=?,
                        latest_order_by=?,
                        latest_pnl=?,
                        latest_volume=?,
                        best_observed_pnl=MAX(best_observed_pnl, ?),
                        highest_observed_volume=
                            MAX(highest_observed_volume, ?),
                        weekly_pnl_appearances=
                            weekly_pnl_appearances+?,
                        weekly_volume_appearances=
                            weekly_volume_appearances+?,
                        monthly_pnl_appearances=
                            monthly_pnl_appearances+?,
                        all_time_pnl_appearances=
                            all_time_pnl_appearances+?,
                        sports_appearances=sports_appearances+?,
                        qualification_eligible=?,
                        metadata_json=?,
                        updated_at=?
                    WHERE wallet=?
                    """,
                    (
                        resulting_status,
                        observed_at,
                        source,
                        best_rank,
                        rank,
                        username,
                        x_username,
                        profile_image,
                        verified,
                        category,
                        period,
                        order_by,
                        pnl,
                        volume,
                        pnl,
                        volume,
                        weekly_pnl,
                        weekly_volume,
                        monthly_pnl,
                        all_time_pnl,
                        sports,
                        eligibility,
                        json.dumps({"latest_snapshot_id": snapshot_id}),
                        observed_at,
                        wallet,
                    ),
                )
                result["updated"] += 1

            connection.execute(
                """
                INSERT OR IGNORE INTO wallet_discovery_events (
                    event_key, wallet, event_type, discovery_source,
                    snapshot_id, previous_status, resulting_status,
                    category, time_period, order_by, rank, pnl,
                    volume, explanation_json, discovered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{snapshot_key}:{wallet}:{event_type}",
                    wallet,
                    event_type,
                    source,
                    snapshot_id,
                    previous_status,
                    resulting_status,
                    category,
                    period,
                    order_by,
                    rank,
                    pnl,
                    volume,
                    json.dumps(
                        {
                            "auto_promoted_to_consensus": False,
                            "protected_status_preserved": (
                                resulting_status in PROTECTED_STATUSES
                            ),
                        }
                    ),
                    observed_at,
                ),
            )

            result["valid"] += 1
            result["wallets"].add(wallet)

        connection.commit()
        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def start_run(board_count: int) -> tuple[int, datetime]:
    started = now()
    connection = connect()
    try:
        cursor = connection.execute(
            """
            INSERT INTO wallet_discovery_runs (
                started_at, board_count, status
            )
            VALUES (?, ?, 'RUNNING')
            """,
            (started.isoformat(), board_count),
        )
        connection.commit()
        return cursor.lastrowid, started
    finally:
        connection.close()


def finish_run(
    run_id: int,
    started: datetime,
    status: str,
    successful: int,
    failed: int,
    received: int,
    valid: int,
    invalid: int,
    wallets: int,
    new_wallets: int,
    updated: int,
    protected: int,
    error_message: str = "",
) -> None:
    connection = connect()
    finished = now()

    try:
        qualification_candidates = connection.execute(
            """
            SELECT COUNT(*)
            FROM wallet_registry
            WHERE qualification_eligible=1
              AND status IN ('CANDIDATE', 'WATCHLIST')
            """
        ).fetchone()[0]

        connection.execute(
            """
            UPDATE wallet_discovery_runs
            SET finished_at=?,
                elapsed_seconds=?,
                successful_boards=?,
                failed_boards=?,
                entries_received=?,
                valid_entries=?,
                invalid_entries=?,
                unique_wallets_seen=?,
                new_wallets_added=?,
                existing_wallets_updated=?,
                protected_wallets_preserved=?,
                qualification_candidates=?,
                status=?,
                error_message=?
            WHERE id=?
            """,
            (
                finished.isoformat(),
                (finished - started).total_seconds(),
                successful,
                failed,
                received,
                valid,
                invalid,
                wallets,
                new_wallets,
                updated,
                protected,
                qualification_candidates,
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
        total = connection.execute(
            "SELECT COUNT(*) FROM wallet_registry"
        ).fetchone()[0]

        eligible = connection.execute(
            """
            SELECT COUNT(*)
            FROM wallet_registry
            WHERE qualification_eligible=1
              AND status IN ('CANDIDATE', 'WATCHLIST')
            """
        ).fetchone()[0]

        rows = connection.execute(
            """
            SELECT *
            FROM wallet_registry
            ORDER BY qualification_eligible DESC,
                     leaderboard_appearance_count DESC,
                     best_rank ASC,
                     best_observed_pnl DESC
            LIMIT ?
            """,
            (max(display_limit, 1),),
        ).fetchall()
    finally:
        connection.close()

    print()
    print("=" * 108)
    print("WALLET REGISTRY SUMMARY")
    print("=" * 108)
    print(f"Total registered wallets:       {total}")
    print(f"Qualification candidates:       {eligible}")
    print("=" * 108)

    print()
    print("TOP DISCOVERED WALLETS")

    for index, row in enumerate(rows, start=1):
        print()
        print("-" * 108)
        print(f"{index}. {row['wallet']}")
        print("-" * 108)
        print(
            f"Status / qualification:         "
            f"{row['status']} / "
            f"{'ELIGIBLE' if row['qualification_eligible'] else 'OBSERVING'}"
        )
        print(f"Username:                       {row['latest_username'] or '-'}")
        print(
            f"Appearances / best rank:        "
            f"{row['leaderboard_appearance_count']} / "
            f"{row['best_rank'] or '-'}"
        )
        print(
            f"Latest board:                   "
            f"{row['latest_category']} / "
            f"{row['latest_time_period']} / "
            f"{row['latest_order_by']}"
        )
        print(
            f"Latest PnL / volume:            "
            f"{money(row['latest_pnl'])} / "
            f"${number(row['latest_volume']):,.2f}"
        )


def parse_board(value: str) -> tuple[str, str, str]:
    parts = [item.strip().upper() for item in value.split(":")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "Use CATEGORY:TIME_PERIOD:ORDER_BY"
        )

    category, period, order_by = parts

    if category not in VALID_CATEGORIES:
        raise argparse.ArgumentTypeError(f"Invalid category: {category}")
    if period not in VALID_PERIODS:
        raise argparse.ArgumentTypeError(f"Invalid period: {period}")
    if order_by not in VALID_ORDERINGS:
        raise argparse.ArgumentTypeError(f"Invalid order: {order_by}")

    return category, period, order_by


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect official Polymarket trader leaderboards and "
            "maintain a persistent candidate wallet registry."
        )
    )
    parser.add_argument(
        "--board",
        action="append",
        type=parse_board,
        help=(
            "Custom CATEGORY:TIME_PERIOD:ORDER_BY board. "
            "May be repeated."
        ),
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--max-results-per-board",
        type=int,
        default=DEFAULT_MAX_RESULTS,
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
        "--continue-on-board-failure",
        action="store_true",
    )
    return parser.parse_args()


def main() -> None:
    configure_utf8()
    args = parse_args()

    boards = args.board or DEFAULT_BOARDS
    limit = min(max(args.limit, 1), 50)
    max_results = min(max(args.max_results_per_board, 1), 1050)
    delay = max(args.request_delay, 0.0)

    print()
    print("=" * 108)
    print("POLYMARKET WEEKLY WALLET DISCOVERY v1")
    print("=" * 108)
    print(f"Database:                    {DB}")
    print(f"Data API:                    {DATA_API}")
    print(f"Boards:                      {len(boards)}")
    print(f"Page limit:                  {limit}")
    print(f"Maximum results per board:   {max_results}")
    print("Consensus:                   CANDIDATES NOT AUTO-PROMOTED")
    print("=" * 108)

    create_tables()
    run_id, started = start_run(len(boards))

    successful = 0
    failed = 0
    received = 0
    valid = 0
    invalid = 0
    new_wallets = 0
    updated = 0
    protected = 0
    unique_wallets: set[str] = set()
    errors: list[str] = []

    try:
        for board_index, (category, period, order_by) in enumerate(
            boards,
            start=1,
        ):
            print()
            print("-" * 108)
            print(
                f"BOARD {board_index}/{len(boards)}: "
                f"{category} / {period} / {order_by}"
            )
            print("-" * 108)

            observed_at = now_iso()
            snapshot_id, snapshot_key = create_snapshot(
                category,
                period,
                order_by,
                limit,
                max_results,
                observed_at,
            )

            urls: list[str] = []

            try:
                entries, pages, urls = fetch_board(
                    category,
                    period,
                    order_by,
                    limit,
                    max_results,
                    delay,
                )

                counts = save_entries(
                    snapshot_id,
                    snapshot_key,
                    category,
                    period,
                    order_by,
                    entries,
                    observed_at,
                )

                finish_snapshot(
                    snapshot_id,
                    "SUCCESS",
                    len(entries),
                    pages,
                    urls,
                )

                successful += 1
                received += len(entries)
                valid += counts["valid"]
                invalid += counts["invalid"]
                new_wallets += counts["new"]
                updated += counts["updated"]
                protected += counts["protected"]
                unique_wallets.update(counts["wallets"])

                print(
                    f"Completed: {len(entries)} entries, "
                    f"{len(counts['wallets'])} unique wallets."
                )

            except Exception as error:
                failed += 1
                message = (
                    f"{category}/{period}/{order_by}: "
                    f"{type(error).__name__}: {error}"
                )
                errors.append(message)

                finish_snapshot(
                    snapshot_id,
                    "FAILED",
                    0,
                    0,
                    urls,
                    message,
                )

                print(f"FAILED: {message}")

                if not args.continue_on_board_failure:
                    raise

        final_status = "SUCCESS" if failed == 0 else "PARTIAL_SUCCESS"

        finish_run(
            run_id,
            started,
            final_status,
            successful,
            failed,
            received,
            valid,
            invalid,
            len(unique_wallets),
            new_wallets,
            updated,
            protected,
            "\n".join(errors),
        )

        print()
        print("=" * 108)
        print("WEEKLY WALLET DISCOVERY SUMMARY")
        print("=" * 108)
        print(f"Successful boards:              {successful}")
        print(f"Failed boards:                  {failed}")
        print(f"Entries received:               {received}")
        print(f"Valid entries:                  {valid}")
        print(f"Invalid entries:                {invalid}")
        print(f"Unique wallets this run:        {len(unique_wallets)}")
        print(f"New wallets added:              {new_wallets}")
        print(f"Existing wallets updated:       {updated}")
        print(f"Qualified/elite preserved:      {protected}")
        print("=" * 108)

        show_summary(args.display_limit)

        print()
        print("=" * 108)
        print("WEEKLY WALLET DISCOVERY COMPLETE")
        print("=" * 108)
        print("Registry:                    wallet_registry")
        print("Snapshots:                   leaderboard_snapshots")
        print("Entries:                     leaderboard_entries")
        print("Discovery history:           wallet_discovery_events")
        print("Status history:              wallet_status_history")
        print("Run history:                 wallet_discovery_runs")
        print()
        print(
            "New wallets remain CANDIDATES. They are not "
            "automatically included in trusted consensus."
        )
        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id,
            started,
            "FAILED",
            successful,
            max(failed, 1),
            received,
            valid,
            invalid,
            len(unique_wallets),
            new_wallets,
            updated,
            protected,
            f"{type(error).__name__}: {error}",
        )
        raise


if __name__ == "__main__":
    main()