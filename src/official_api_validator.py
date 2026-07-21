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

DEFAULT_WALLET_LIMIT = 10
DEFAULT_TIMEOUT = 30
DEFAULT_DELAY = 0.10
DEFAULT_DISPLAY_LIMIT = 30
MAX_RETRIES = 3

ENDPOINT_TESTS: tuple[dict[str, Any], ...] = (
    {
        "name": "activity_minimal",
        "path": "/activity",
        "params": {"limit": 1, "offset": 0},
        "expected": "list",
    },
    {
        "name": "activity_page_500",
        "path": "/activity",
        "params": {"limit": 500, "offset": 0},
        "expected": "list",
    },
    {
        "name": "trades_minimal",
        "path": "/trades",
        "params": {"limit": 1, "offset": 0},
        "expected": "list",
    },
    {
        "name": "trades_page_500",
        "path": "/trades",
        "params": {"limit": 500, "offset": 0},
        "expected": "list",
    },
    {
        "name": "positions",
        "path": "/positions",
        "params": {"limit": 1, "offset": 0},
        "expected": "list",
    },
    {
        "name": "closed_positions",
        "path": "/closed-positions",
        "params": {"limit": 1, "offset": 0},
        "expected": "list",
    },
    {
        "name": "value",
        "path": "/value",
        "params": {},
        "expected": "any",
    },
    {
        "name": "traded",
        "path": "/traded",
        "params": {},
        "expected": "object",
    },
)


def configure_utf8() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def wallet_text(value: Any) -> str:
    return text(value).lower()


def integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


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


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
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
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_validation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                wallets_selected INTEGER NOT NULL DEFAULT 0,
                endpoint_tests_planned INTEGER NOT NULL DEFAULT 0,
                endpoint_tests_completed INTEGER NOT NULL DEFAULT 0,
                successful_tests INTEGER NOT NULL DEFAULT 0,
                failed_tests INTEGER NOT NULL DEFAULT 0,
                pagination_probes INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS api_endpoint_tests (
                test_key TEXT PRIMARY KEY,
                run_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                wallet_status TEXT,
                test_name TEXT NOT NULL,
                endpoint_path TEXT NOT NULL,
                request_url TEXT NOT NULL,
                request_params_json TEXT NOT NULL,
                requested_limit INTEGER,
                requested_offset INTEGER,
                http_status INTEGER,
                success INTEGER NOT NULL DEFAULT 0,
                response_type TEXT,
                response_count INTEGER,
                response_bytes INTEGER NOT NULL DEFAULT 0,
                elapsed_ms REAL,
                error_type TEXT,
                error_message TEXT,
                response_body_preview TEXT,
                response_headers_json TEXT,
                tested_at TEXT NOT NULL,
                FOREIGN KEY(run_id)
                    REFERENCES api_validation_runs(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_api_endpoint_tests_wallet
            ON api_endpoint_tests(wallet, tested_at DESC);

            CREATE INDEX IF NOT EXISTS idx_api_endpoint_tests_endpoint
            ON api_endpoint_tests(endpoint_path, http_status, success);

            CREATE TABLE IF NOT EXISTS wallet_endpoint_support (
                support_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                endpoint_path TEXT NOT NULL,
                minimal_request_supported INTEGER NOT NULL DEFAULT 0,
                large_page_supported INTEGER NOT NULL DEFAULT 0,
                pagination_supported INTEGER NOT NULL DEFAULT 0,
                maximum_successful_offset INTEGER,
                first_failed_offset INTEGER,
                latest_http_status INTEGER,
                latest_response_count INTEGER,
                latest_error_message TEXT,
                support_status TEXT NOT NULL DEFAULT 'UNKNOWN',
                first_tested_at TEXT NOT NULL,
                last_tested_at TEXT NOT NULL,
                metadata_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_wallet_endpoint_support_status
            ON wallet_endpoint_support(
                endpoint_path,
                support_status,
                wallet
            );

            CREATE TABLE IF NOT EXISTS api_pagination_probes (
                probe_key TEXT PRIMARY KEY,
                run_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                endpoint_path TEXT NOT NULL,
                requested_limit INTEGER NOT NULL,
                requested_offset INTEGER NOT NULL,
                http_status INTEGER,
                success INTEGER NOT NULL DEFAULT 0,
                response_count INTEGER,
                response_bytes INTEGER NOT NULL DEFAULT 0,
                elapsed_ms REAL,
                error_type TEXT,
                error_message TEXT,
                response_body_preview TEXT,
                probed_at TEXT NOT NULL,
                FOREIGN KEY(run_id)
                    REFERENCES api_validation_runs(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_api_pagination_probes_wallet
            ON api_pagination_probes(
                wallet,
                endpoint_path,
                requested_offset
            );
            """
        )

        connection.commit()

    finally:
        connection.close()


def build_url(
    endpoint_path: str,
    wallet: str,
    params: dict[str, Any],
) -> str:
    query_params = {
        "user": wallet,
        **params,
    }

    query = urllib.parse.urlencode(
        query_params,
        doseq=True,
    )

    return f"{DATA_API}{endpoint_path}?{query}"


def decode_body(
    raw_body: bytes,
    content_type: str,
) -> tuple[Any, str]:
    body_text = raw_body.decode(
        "utf-8",
        errors="replace",
    )

    if "application/json" in content_type.lower():
        try:
            return json.loads(body_text), body_text
        except json.JSONDecodeError:
            return None, body_text

    try:
        return json.loads(body_text), body_text
    except json.JSONDecodeError:
        return body_text, body_text


def response_shape(payload: Any) -> tuple[str, int | None]:
    if isinstance(payload, list):
        return "list", len(payload)

    if isinstance(payload, dict):
        return "object", len(payload)

    if payload is None:
        return "null", None

    return type(payload).__name__, None


def request_once(
    url: str,
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "PolymarketIntelligencePlatform/"
                "official-api-validator-v1"
            ),
        },
        method="GET",
    )

    started = time.perf_counter()

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw_body = response.read()
            elapsed_ms = (
                time.perf_counter() - started
            ) * 1000.0

            headers = {
                key: value
                for key, value in response.headers.items()
            }

            content_type = response.headers.get(
                "Content-Type",
                "",
            )

            payload, body_text = decode_body(
                raw_body,
                content_type,
            )

            shape, count = response_shape(payload)

            return {
                "http_status": response.status,
                "success": 1,
                "payload": payload,
                "response_type": shape,
                "response_count": count,
                "response_bytes": len(raw_body),
                "elapsed_ms": elapsed_ms,
                "error_type": "",
                "error_message": "",
                "response_body_preview": body_text[:2000],
                "response_headers_json": stable_json(headers),
            }

    except urllib.error.HTTPError as error:
        raw_body = error.read()
        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000.0

        content_type = (
            error.headers.get("Content-Type", "")
            if error.headers
            else ""
        )

        payload, body_text = decode_body(
            raw_body,
            content_type,
        )

        shape, count = response_shape(payload)

        headers = (
            {
                key: value
                for key, value in error.headers.items()
            }
            if error.headers
            else {}
        )

        return {
            "http_status": error.code,
            "success": 0,
            "payload": payload,
            "response_type": shape,
            "response_count": count,
            "response_bytes": len(raw_body),
            "elapsed_ms": elapsed_ms,
            "error_type": "HTTPError",
            "error_message": str(error),
            "response_body_preview": body_text[:2000],
            "response_headers_json": stable_json(headers),
        }

    except Exception as error:
        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000.0

        return {
            "http_status": None,
            "success": 0,
            "payload": None,
            "response_type": "",
            "response_count": None,
            "response_bytes": 0,
            "elapsed_ms": elapsed_ms,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "response_body_preview": "",
            "response_headers_json": "{}",
        }


def request_with_retry(
    url: str,
    timeout: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for attempt in range(MAX_RETRIES):
        result = request_once(
            url=url,
            timeout=timeout,
        )

        status = result.get("http_status")

        if result.get("success"):
            return result

        if status not in {
            425,
            429,
            500,
            502,
            503,
            504,
        }:
            return result

        if attempt < MAX_RETRIES - 1:
            delay = min(2 ** attempt, 8)
            time.sleep(delay)

    return result


def select_wallets(
    statuses: list[str],
    wallet_limit: int,
    include_failed_activity_wallets: bool,
) -> list[dict[str, Any]]:
    connection = connect()

    try:
        if not table_exists(connection, "wallet_registry"):
            raise RuntimeError(
                "wallet_registry is missing."
            )

        placeholders = ", ".join(
            "?"
            for _ in statuses
        )

        sql = f"""
            SELECT
                wr.wallet,
                wr.status,
                wr.leaderboard_appearance_count,
                wr.best_rank,
                wr.best_observed_pnl,
                COALESCE(cwe.evaluation_score, 0) AS evaluation_score,
                COALESCE(cwe.needs_position_scan, 0) AS needs_position_scan,
                COALESCE(cwe.needs_history_scan, 0) AS needs_history_scan,
                COALESCE(wac.last_error_message, '') AS last_error_message,
                COALESCE(wac.last_success_at, '') AS last_success_at
            FROM wallet_registry wr
            LEFT JOIN candidate_wallet_evaluations cwe
              ON cwe.wallet = wr.wallet
            LEFT JOIN wallet_activity_checkpoints wac
              ON wac.wallet = wr.wallet
            WHERE wr.status IN ({placeholders})
        """

        parameters: list[Any] = list(statuses)

        if include_failed_activity_wallets:
            sql += """
                AND COALESCE(wac.last_error_message, '') <> ''
            """

        sql += """
            ORDER BY
                CASE
                    WHEN COALESCE(wac.last_error_message, '') <> ''
                    THEN 0
                    ELSE 1
                END,
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
            for row in connection.execute(
                sql,
                tuple(parameters),
            ).fetchall()
        ]

    finally:
        connection.close()


def start_run(
    wallet_count: int,
    planned_tests: int,
) -> tuple[int, datetime]:
    started = utc_now()
    connection = connect()

    try:
        cursor = connection.execute(
            """
            INSERT INTO api_validation_runs (
                started_at,
                wallets_selected,
                endpoint_tests_planned,
                status
            )
            VALUES (?, ?, ?, 'RUNNING')
            """,
            (
                started.isoformat(),
                wallet_count,
                planned_tests,
            ),
        )

        connection.commit()

        return cursor.lastrowid, started

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started: datetime,
    completed: int,
    successful: int,
    failed: int,
    probes: int,
    status: str,
    error_message: str = "",
) -> None:
    finished = utc_now()
    connection = connect()

    try:
        connection.execute(
            """
            UPDATE api_validation_runs
            SET
                finished_at=?,
                elapsed_seconds=?,
                endpoint_tests_completed=?,
                successful_tests=?,
                failed_tests=?,
                pagination_probes=?,
                status=?,
                error_message=?
            WHERE id=?
            """,
            (
                finished.isoformat(),
                (finished - started).total_seconds(),
                completed,
                successful,
                failed,
                probes,
                status,
                error_message,
                run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def save_endpoint_test(
    run_id: int,
    wallet: str,
    wallet_status: str,
    test_name: str,
    endpoint_path: str,
    params: dict[str, Any],
    url: str,
    result: dict[str, Any],
) -> None:
    tested_at = utc_now_iso()
    test_key = (
        f"{run_id}:{wallet}:{test_name}"
    )

    connection = connect()

    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO api_endpoint_tests (
                test_key,
                run_id,
                wallet,
                wallet_status,
                test_name,
                endpoint_path,
                request_url,
                request_params_json,
                requested_limit,
                requested_offset,
                http_status,
                success,
                response_type,
                response_count,
                response_bytes,
                elapsed_ms,
                error_type,
                error_message,
                response_body_preview,
                response_headers_json,
                tested_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                test_key,
                run_id,
                wallet,
                wallet_status,
                test_name,
                endpoint_path,
                url,
                stable_json(params),
                params.get("limit"),
                params.get("offset"),
                result.get("http_status"),
                integer(result.get("success")),
                text(result.get("response_type")),
                result.get("response_count"),
                integer(result.get("response_bytes")),
                result.get("elapsed_ms"),
                text(result.get("error_type")),
                text(result.get("error_message")),
                text(result.get("response_body_preview")),
                text(result.get("response_headers_json")),
                tested_at,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def save_pagination_probe(
    run_id: int,
    wallet: str,
    endpoint_path: str,
    limit: int,
    offset: int,
    result: dict[str, Any],
) -> None:
    probed_at = utc_now_iso()
    probe_key = (
        f"{run_id}:{wallet}:{endpoint_path}:"
        f"{limit}:{offset}"
    )

    connection = connect()

    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO api_pagination_probes (
                probe_key,
                run_id,
                wallet,
                endpoint_path,
                requested_limit,
                requested_offset,
                http_status,
                success,
                response_count,
                response_bytes,
                elapsed_ms,
                error_type,
                error_message,
                response_body_preview,
                probed_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                probe_key,
                run_id,
                wallet,
                endpoint_path,
                limit,
                offset,
                result.get("http_status"),
                integer(result.get("success")),
                result.get("response_count"),
                integer(result.get("response_bytes")),
                result.get("elapsed_ms"),
                text(result.get("error_type")),
                text(result.get("error_message")),
                text(result.get("response_body_preview")),
                probed_at,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def update_endpoint_support(
    wallet: str,
    endpoint_path: str,
    minimal_supported: int,
    large_page_supported: int,
    pagination_supported: int,
    maximum_successful_offset: int | None,
    first_failed_offset: int | None,
    latest_result: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    tested_at = utc_now_iso()

    if minimal_supported and large_page_supported and pagination_supported:
        support_status = "FULL"

    elif minimal_supported and large_page_supported:
        support_status = "PAGE_ONLY"

    elif minimal_supported:
        support_status = "MINIMAL_ONLY"

    else:
        support_status = "UNSUPPORTED_OR_ERROR"

    support_key = f"{wallet}:{endpoint_path}"

    connection = connect()

    try:
        existing = connection.execute(
            """
            SELECT first_tested_at
            FROM wallet_endpoint_support
            WHERE support_key=?
            """,
            (support_key,),
        ).fetchone()

        first_tested_at = (
            text(existing["first_tested_at"])
            if existing
            else tested_at
        )

        connection.execute(
            """
            INSERT INTO wallet_endpoint_support (
                support_key,
                wallet,
                endpoint_path,
                minimal_request_supported,
                large_page_supported,
                pagination_supported,
                maximum_successful_offset,
                first_failed_offset,
                latest_http_status,
                latest_response_count,
                latest_error_message,
                support_status,
                first_tested_at,
                last_tested_at,
                metadata_json
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            ON CONFLICT(support_key) DO UPDATE SET
                minimal_request_supported=
                    excluded.minimal_request_supported,
                large_page_supported=
                    excluded.large_page_supported,
                pagination_supported=
                    excluded.pagination_supported,
                maximum_successful_offset=
                    excluded.maximum_successful_offset,
                first_failed_offset=
                    excluded.first_failed_offset,
                latest_http_status=
                    excluded.latest_http_status,
                latest_response_count=
                    excluded.latest_response_count,
                latest_error_message=
                    excluded.latest_error_message,
                support_status=
                    excluded.support_status,
                last_tested_at=
                    excluded.last_tested_at,
                metadata_json=
                    excluded.metadata_json
            """,
            (
                support_key,
                wallet,
                endpoint_path,
                minimal_supported,
                large_page_supported,
                pagination_supported,
                maximum_successful_offset,
                first_failed_offset,
                latest_result.get("http_status"),
                latest_result.get("response_count"),
                text(latest_result.get("error_message")),
                support_status,
                first_tested_at,
                tested_at,
                stable_json(metadata),
            ),
        )

        connection.commit()

    finally:
        connection.close()


def validate_pagination(
    run_id: int,
    wallet: str,
    endpoint_path: str,
    page_limit: int,
    max_offset: int,
    timeout: int,
    delay: float,
) -> dict[str, Any]:
    maximum_successful_offset: int | None = None
    first_failed_offset: int | None = None
    pagination_supported = 0
    probe_count = 0
    latest_result: dict[str, Any] = {}

    offset = 0

    while offset <= max_offset:
        params = {
            "limit": page_limit,
            "offset": offset,
        }

        url = build_url(
            endpoint_path,
            wallet,
            params,
        )

        result = request_with_retry(
            url=url,
            timeout=timeout,
        )

        save_pagination_probe(
            run_id=run_id,
            wallet=wallet,
            endpoint_path=endpoint_path,
            limit=page_limit,
            offset=offset,
            result=result,
        )

        probe_count += 1
        latest_result = result

        if not result.get("success"):
            first_failed_offset = offset
            break

        maximum_successful_offset = offset

        count = result.get("response_count")

        if count is None:
            break

        if count < page_limit:
            pagination_supported = 1
            break

        if offset > 0:
            pagination_supported = 1

        offset += page_limit

        if delay > 0:
            time.sleep(delay)

    return {
        "pagination_supported": pagination_supported,
        "maximum_successful_offset": maximum_successful_offset,
        "first_failed_offset": first_failed_offset,
        "probe_count": probe_count,
        "latest_result": latest_result,
    }


def show_summary(
    run_id: int,
    display_limit: int,
) -> None:
    connection = connect()

    try:
        status_rows = connection.execute(
            """
            SELECT
                endpoint_path,
                support_status,
                COUNT(*) AS wallet_count
            FROM wallet_endpoint_support
            GROUP BY endpoint_path, support_status
            ORDER BY endpoint_path, wallet_count DESC
            """
        ).fetchall()

        failed_rows = connection.execute(
            """
            SELECT
                wallet,
                test_name,
                endpoint_path,
                http_status,
                error_message,
                response_body_preview
            FROM api_endpoint_tests
            WHERE run_id=?
              AND success=0
            ORDER BY wallet, test_name
            LIMIT ?
            """,
            (
                run_id,
                max(display_limit, 1),
            ),
        ).fetchall()

        pagination_rows = connection.execute(
            """
            SELECT
                wallet,
                endpoint_path,
                support_status,
                maximum_successful_offset,
                first_failed_offset,
                latest_http_status,
                latest_error_message
            FROM wallet_endpoint_support
            WHERE endpoint_path IN (
                '/activity',
                '/trades'
            )
            ORDER BY
                CASE support_status
                    WHEN 'FULL' THEN 1
                    WHEN 'PAGE_ONLY' THEN 2
                    WHEN 'MINIMAL_ONLY' THEN 3
                    ELSE 4
                END,
                wallet
            LIMIT ?
            """,
            (
                max(display_limit, 1),
            ),
        ).fetchall()

    finally:
        connection.close()

    print()
    print("=" * 112)
    print("OFFICIAL API VALIDATION SUMMARY")
    print("=" * 112)

    for row in status_rows:
        print(
            f"{row['endpoint_path']:<24} "
            f"{row['support_status']:<24} "
            f"{row['wallet_count']:>6} wallets"
        )

    print("=" * 112)

    if failed_rows:
        print()
        print("FAILED ENDPOINT TESTS")

        for row in failed_rows:
            preview = text(
                row["response_body_preview"]
            ).replace("\n", " ")[:240]

            print()
            print(
                f"{row['wallet']} | "
                f"{row['test_name']} | "
                f"HTTP {row['http_status']}"
            )

            print(
                f"  Error: {row['error_message'] or '-'}"
            )

            print(
                f"  Body:  {preview or '-'}"
            )

    if pagination_rows:
        print()
        print("ACTIVITY / TRADE PAGINATION SUPPORT")

        for row in pagination_rows:
            print(
                f"{row['wallet']} | "
                f"{row['endpoint_path']:<10} | "
                f"{row['support_status']:<20} | "
                f"max OK offset "
                f"{row['maximum_successful_offset']} | "
                f"first failed "
                f"{row['first_failed_offset']} | "
                f"HTTP {row['latest_http_status']}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate official Polymarket Data API endpoint and "
            "pagination behavior wallet by wallet, including HTTP "
            "response bodies for 400-class errors."
        )
    )

    parser.add_argument(
        "--status",
        action="append",
        choices=[
            "CANDIDATE",
            "WATCHLIST",
            "QUALIFIED",
            "ELITE",
        ],
        help=(
            "Wallet registry status to test. May be repeated. "
            "Default: WATCHLIST."
        ),
    )

    parser.add_argument(
        "--wallet-limit",
        type=int,
        default=DEFAULT_WALLET_LIMIT,
    )

    parser.add_argument(
        "--failed-activity-wallets-only",
        action="store_true",
        help=(
            "Test only wallets whose previous official activity "
            "ingestion checkpoint contains an error."
        ),
    )

    parser.add_argument(
        "--probe-pagination",
        action="store_true",
        help=(
            "Probe /activity and /trades page-by-page until data "
            "exhaustion, the configured offset ceiling, or the "
            "first error."
        ),
    )

    parser.add_argument(
        "--activity-page-limit",
        type=int,
        default=500,
    )

    parser.add_argument(
        "--trades-page-limit",
        type=int,
        default=500,
    )

    parser.add_argument(
        "--max-probe-offset",
        type=int,
        default=10000,
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
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

    return parser.parse_args()


def main() -> None:
    configure_utf8()
    args = parse_args()

    statuses = args.status or ["WATCHLIST"]
    wallet_limit = max(args.wallet_limit, 0)
    timeout = max(args.timeout, 1)
    delay = max(args.request_delay, 0.0)
    activity_page_limit = min(
        max(args.activity_page_limit, 1),
        500,
    )
    trades_page_limit = min(
        max(args.trades_page_limit, 1),
        10000,
    )
    max_probe_offset = min(
        max(args.max_probe_offset, 0),
        10000,
    )

    print()
    print("=" * 112)
    print("POLYMARKET OFFICIAL API VALIDATOR v1")
    print("=" * 112)
    print(f"Database:                   {DB}")
    print(f"Data API:                   {DATA_API}")
    print(f"Statuses:                   {', '.join(statuses)}")
    print(f"Wallet limit:               {wallet_limit or 'ALL'}")
    print(
        f"Failed wallets only:        "
        f"{args.failed_activity_wallets_only}"
    )
    print(
        f"Pagination probes:          "
        f"{args.probe_pagination}"
    )
    print(f"Maximum probe offset:       {max_probe_offset}")
    print("=" * 112)

    create_tables()

    wallets = select_wallets(
        statuses=statuses,
        wallet_limit=wallet_limit,
        include_failed_activity_wallets=(
            args.failed_activity_wallets_only
        ),
    )

    if not wallets:
        raise RuntimeError(
            "No wallets matched the validator selection."
        )

    planned_tests = (
        len(wallets)
        * len(ENDPOINT_TESTS)
    )

    run_id, started = start_run(
        wallet_count=len(wallets),
        planned_tests=planned_tests,
    )

    completed = 0
    successful = 0
    failed = 0
    pagination_probes = 0
    fatal_error = ""

    try:
        for wallet_index, wallet_row in enumerate(
            wallets,
            start=1,
        ):
            wallet = wallet_text(
                wallet_row["wallet"]
            )

            wallet_status = text(
                wallet_row["status"]
            )

            if not valid_wallet(wallet):
                continue

            print()
            print("-" * 112)
            print(
                f"WALLET {wallet_index}/{len(wallets)}: "
                f"{wallet} [{wallet_status}]"
            )
            print("-" * 112)

            endpoint_results: dict[
                str,
                dict[str, Any],
            ] = {}

            for test_spec in ENDPOINT_TESTS:
                test_name = text(
                    test_spec["name"]
                )

                endpoint_path = text(
                    test_spec["path"]
                )

                params = dict(
                    test_spec["params"]
                )

                url = build_url(
                    endpoint_path,
                    wallet,
                    params,
                )

                result = request_with_retry(
                    url=url,
                    timeout=timeout,
                )

                save_endpoint_test(
                    run_id=run_id,
                    wallet=wallet,
                    wallet_status=wallet_status,
                    test_name=test_name,
                    endpoint_path=endpoint_path,
                    params=params,
                    url=url,
                    result=result,
                )

                completed += 1

                if result.get("success"):
                    successful += 1
                else:
                    failed += 1

                endpoint_results[
                    test_name
                ] = result

                print(
                    f"{test_name:<24} "
                    f"HTTP {result.get('http_status')} | "
                    f"{'OK' if result.get('success') else 'FAIL'} | "
                    f"rows {result.get('response_count')}"
                )

                if delay > 0:
                    time.sleep(delay)

            for endpoint_path, minimal_name, large_name, page_limit in (
                (
                    "/activity",
                    "activity_minimal",
                    "activity_page_500",
                    activity_page_limit,
                ),
                (
                    "/trades",
                    "trades_minimal",
                    "trades_page_500",
                    trades_page_limit,
                ),
            ):
                minimal_result = endpoint_results.get(
                    minimal_name,
                    {},
                )

                large_result = endpoint_results.get(
                    large_name,
                    {},
                )

                pagination_result = {
                    "pagination_supported": 0,
                    "maximum_successful_offset": (
                        0
                        if large_result.get("success")
                        else None
                    ),
                    "first_failed_offset": None,
                    "probe_count": 0,
                    "latest_result": large_result,
                }

                if (
                    args.probe_pagination
                    and large_result.get("success")
                ):
                    pagination_result = validate_pagination(
                        run_id=run_id,
                        wallet=wallet,
                        endpoint_path=endpoint_path,
                        page_limit=page_limit,
                        max_offset=max_probe_offset,
                        timeout=timeout,
                        delay=delay,
                    )

                    pagination_probes += integer(
                        pagination_result[
                            "probe_count"
                        ]
                    )

                latest_result = (
                    pagination_result.get(
                        "latest_result"
                    )
                    or large_result
                    or minimal_result
                )

                update_endpoint_support(
                    wallet=wallet,
                    endpoint_path=endpoint_path,
                    minimal_supported=integer(
                        minimal_result.get(
                            "success"
                        )
                    ),
                    large_page_supported=integer(
                        large_result.get(
                            "success"
                        )
                    ),
                    pagination_supported=integer(
                        pagination_result.get(
                            "pagination_supported"
                        )
                    ),
                    maximum_successful_offset=(
                        pagination_result.get(
                            "maximum_successful_offset"
                        )
                    ),
                    first_failed_offset=(
                        pagination_result.get(
                            "first_failed_offset"
                        )
                    ),
                    latest_result=latest_result,
                    metadata={
                        "minimal_test": minimal_name,
                        "large_page_test": large_name,
                        "page_limit": page_limit,
                        "pagination_probed": (
                            args.probe_pagination
                        ),
                    },
                )

        final_status = (
            "SUCCESS"
            if failed == 0
            else "PARTIAL_SUCCESS"
        )

        finish_run(
            run_id=run_id,
            started=started,
            completed=completed,
            successful=successful,
            failed=failed,
            probes=pagination_probes,
            status=final_status,
        )

        print()
        print("=" * 112)
        print("OFFICIAL API VALIDATION COMPLETE")
        print("=" * 112)
        print(f"Wallets tested:              {len(wallets)}")
        print(f"Endpoint tests completed:    {completed}")
        print(f"Successful tests:            {successful}")
        print(f"Failed tests:                {failed}")
        print(f"Pagination probes:           {pagination_probes}")
        print("=" * 112)

        show_summary(
            run_id=run_id,
            display_limit=args.display_limit,
        )

    except Exception as error:
        fatal_error = (
            f"{type(error).__name__}: {error}"
        )

        finish_run(
            run_id=run_id,
            started=started,
            completed=completed,
            successful=successful,
            failed=max(failed, 1),
            probes=pagination_probes,
            status="FAILED",
            error_message=fatal_error,
        )

        raise


if __name__ == "__main__":
    main()