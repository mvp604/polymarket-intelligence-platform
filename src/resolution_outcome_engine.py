from __future__ import annotations

import json
import math
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.0.0"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
HTTP_TIMEOUT_SECONDS = 25
REQUEST_PAUSE_SECONDS = 0.08
RESOLUTION_PRICE_TOLERANCE = 0.001


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def make_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"resolution_run:{stamp}"


def safe_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        if value is None:
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_outcome(value: Any) -> str:
    text = str(value or "").strip()
    return text.upper() if text else "UNKNOWN"


def parse_json_array(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA busy_timeout = 30000;")
    return connection


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    }


def first_present(columns: set[str], candidates: Iterable[str]) -> str | None:
    return next((name for name in candidates if name in columns), None)


def ensure_required_sources(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "market_consensus"):
        raise RuntimeError(
            "market_consensus does not exist. Run "
            "python -m src.consensus_intelligence_engine first."
        )
    required = {
        "condition_id", "event_id", "market_title", "domain", "subdomain",
        "leading_outcome", "consensus_grade", "consensus_score",
        "consensus_confidence", "wallet_count", "effective_wallet_count",
        "total_capital_committed", "recommendation", "pass_reason", "updated_at",
    }
    missing = required - table_columns(connection, "market_consensus")
    if missing:
        raise RuntimeError(
            "market_consensus is missing required columns: " + ", ".join(sorted(missing))
        )


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily_market_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_date TEXT NOT NULL,
            condition_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            market_title TEXT NOT NULL,
            domain TEXT NOT NULL,
            subdomain TEXT NOT NULL,
            leading_outcome TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            consensus_grade TEXT NOT NULL,
            consensus_score REAL NOT NULL,
            consensus_confidence REAL NOT NULL,
            wallet_count INTEGER NOT NULL,
            effective_wallet_count REAL NOT NULL,
            total_capital_committed REAL NOT NULL,
            pass_reason TEXT,
            consensus_updated_at TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            UNIQUE(review_date, condition_id)
        );

        CREATE INDEX IF NOT EXISTS idx_daily_market_reviews_date
        ON daily_market_reviews(review_date, consensus_grade, consensus_score DESC);

        CREATE INDEX IF NOT EXISTS idx_daily_market_reviews_market
        ON daily_market_reviews(condition_id, review_date DESC);

        CREATE TABLE IF NOT EXISTS signal_ledger (
            signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_key TEXT NOT NULL UNIQUE,
            signal_date TEXT NOT NULL,
            condition_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            market_title TEXT NOT NULL,
            domain TEXT NOT NULL,
            subdomain TEXT NOT NULL,
            recommended_outcome TEXT NOT NULL,
            signal_grade TEXT NOT NULL,
            consensus_score REAL NOT NULL,
            consensus_confidence REAL NOT NULL,
            wallet_count INTEGER NOT NULL,
            effective_wallet_count REAL NOT NULL,
            total_capital_committed REAL NOT NULL,
            entry_price REAL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            source_engine_version TEXT NOT NULL,
            signal_status TEXT NOT NULL DEFAULT 'PENDING'
        );

        CREATE INDEX IF NOT EXISTS idx_signal_ledger_status
        ON signal_ledger(signal_status, signal_date, signal_grade);

        CREATE INDEX IF NOT EXISTS idx_signal_ledger_condition
        ON signal_ledger(condition_id, signal_date DESC);

        CREATE TABLE IF NOT EXISTS consensus_market_resolutions (
            condition_id TEXT PRIMARY KEY,
            gamma_market_id TEXT,
            event_id TEXT,
            market_title TEXT NOT NULL,
            market_slug TEXT,
            market_status TEXT NOT NULL,
            active INTEGER NOT NULL,
            closed INTEGER NOT NULL,
            accepting_orders INTEGER,
            outcomes_json TEXT NOT NULL,
            outcome_prices_json TEXT NOT NULL,
            resolved_outcome TEXT,
            resolved_outcome_index INTEGER,
            resolution_source TEXT,
            end_date TEXT,
            resolution_time TEXT,
            fetched_at TEXT NOT NULL,
            raw_market_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_resolution_consensus_market_status
        ON consensus_market_resolutions(market_status, fetched_at DESC);

        CREATE TABLE IF NOT EXISTS signal_results (
            signal_id INTEGER PRIMARY KEY,
            signal_key TEXT NOT NULL UNIQUE,
            condition_id TEXT NOT NULL,
            signal_date TEXT NOT NULL,
            market_title TEXT NOT NULL,
            recommended_outcome TEXT NOT NULL,
            resolved_outcome TEXT,
            signal_grade TEXT NOT NULL,
            consensus_score REAL NOT NULL,
            consensus_confidence REAL NOT NULL,
            entry_price REAL,
            closing_price REAL,
            result TEXT NOT NULL,
            profit_loss_units REAL,
            roi_pct REAL,
            clv_price_points REAL,
            resolved_at TEXT,
            evaluated_at TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY(signal_id) REFERENCES signal_ledger(signal_id)
        );

        CREATE INDEX IF NOT EXISTS idx_signal_results_date
        ON signal_results(signal_date, result, signal_grade);

        CREATE TABLE IF NOT EXISTS daily_outcomes (
            outcome_date TEXT PRIMARY KEY,
            markets_reviewed INTEGER NOT NULL,
            actionable_signals INTEGER NOT NULL,
            pass_markets INTEGER NOT NULL,
            pending_signals INTEGER NOT NULL,
            resolved_signals INTEGER NOT NULL,
            wins INTEGER NOT NULL,
            losses INTEGER NOT NULL,
            pushes INTEGER NOT NULL,
            voids INTEGER NOT NULL,
            unresolved INTEGER NOT NULL,
            hit_rate_pct REAL,
            profit_loss_units REAL NOT NULL,
            roi_pct REAL,
            s_plus_record TEXT NOT NULL,
            s_record TEXT NOT NULL,
            a_record TEXT NOT NULL,
            b_record TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resolution_outcome_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            review_date TEXT NOT NULL,
            markets_reviewed INTEGER NOT NULL,
            signals_archived INTEGER NOT NULL,
            resolution_candidates INTEGER NOT NULL,
            markets_resolved INTEGER NOT NULL,
            results_evaluated INTEGER NOT NULL,
            api_successes INTEGER NOT NULL,
            api_failures INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


@dataclass
class ApiStats:
    successes: int = 0
    failures: int = 0


class GammaClient:
    def __init__(self) -> None:
        self.stats = ApiStats()
        self.user_agent = f"PolymarketIntelligencePlatform/{ENGINE_VERSION}"

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = f"{GAMMA_API_BASE}{path}"
        if query:
            url += "?" + query
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": self.user_agent},
        )
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.stats.successes += 1
            return payload
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            self.stats.failures += 1
            return None

    def fetch_market(self, condition_id: str) -> dict[str, Any] | None:
        # Gamma has supported both singular and plural condition filters over time.
        # Try narrow public queries first, then a direct ID lookup when a Gamma ID is supplied.
        query_variants = [
            {"condition_ids": condition_id, "limit": 5},
            {"condition_id": condition_id, "limit": 5},
        ]
        for params in query_variants:
            payload = self._get_json("/markets", params)
            if isinstance(payload, list):
                for market in payload:
                    if normalize_condition_id(market.get("conditionId")) == condition_id:
                        time.sleep(REQUEST_PAUSE_SECONDS)
                        return market
            time.sleep(REQUEST_PAUSE_SECONDS)
        return None


def normalize_condition_id(value: Any) -> str:
    return str(value or "").strip().lower()


def latest_observed_price(
    connection: sqlite3.Connection,
    condition_id: str,
    recommended_outcome: str,
) -> float | None:
    if table_exists(connection, "consensus_signal_history"):
        row = connection.execute(
            """
            SELECT observed_price
            FROM consensus_signal_history
            WHERE condition_id = ?
              AND UPPER(leading_outcome) = UPPER(?)
              AND observed_price IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (condition_id, recommended_outcome),
        ).fetchone()
        if row:
            value = safe_float(row["observed_price"], None)
            if value is not None and 0 < value <= 1:
                return value

    # Fall back to local position pricing. This is only an approximation of an
    # executable market entry and is explicitly retained as nullable.
    if table_exists(connection, "positions"):
        columns = table_columns(connection, "positions")
        condition_col = first_present(columns, ["condition_id", "market_id"])
        outcome_col = first_present(columns, ["outcome", "side"])
        price_col = first_present(columns, ["current_price", "cur_price", "price", "average_price"])
        if condition_col and outcome_col and price_col:
            sql = f"""
                SELECT AVG(CAST(\"{price_col}\" AS REAL)) AS observed_price
                FROM positions
                WHERE LOWER(CAST(\"{condition_col}\" AS TEXT)) = ?
                  AND UPPER(CAST(\"{outcome_col}\" AS TEXT)) = UPPER(?)
                  AND CAST(\"{price_col}\" AS REAL) > 0
                  AND CAST(\"{price_col}\" AS REAL) <= 1
            """
            row = connection.execute(sql, (condition_id, recommended_outcome)).fetchone()
            if row:
                value = safe_float(row["observed_price"], None)
                if value is not None and 0 < value <= 1:
                    return value
    return None


def capture_daily_reviews(connection: sqlite3.Connection, review_date: str) -> int:
    rows = connection.execute("SELECT * FROM market_consensus").fetchall()
    captured_at = utc_now()
    for row in rows:
        connection.execute(
            """
            INSERT INTO daily_market_reviews (
                review_date, condition_id, event_id, market_title, domain,
                subdomain, leading_outcome, recommendation, consensus_grade,
                consensus_score, consensus_confidence, wallet_count,
                effective_wallet_count, total_capital_committed, pass_reason,
                consensus_updated_at, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(review_date, condition_id) DO UPDATE SET
                event_id = excluded.event_id,
                market_title = excluded.market_title,
                domain = excluded.domain,
                subdomain = excluded.subdomain,
                leading_outcome = excluded.leading_outcome,
                recommendation = excluded.recommendation,
                consensus_grade = excluded.consensus_grade,
                consensus_score = excluded.consensus_score,
                consensus_confidence = excluded.consensus_confidence,
                wallet_count = excluded.wallet_count,
                effective_wallet_count = excluded.effective_wallet_count,
                total_capital_committed = excluded.total_capital_committed,
                pass_reason = excluded.pass_reason,
                consensus_updated_at = excluded.consensus_updated_at,
                captured_at = excluded.captured_at
            """,
            (
                review_date,
                normalize_condition_id(row["condition_id"]),
                str(row["event_id"]),
                str(row["market_title"]),
                str(row["domain"]),
                str(row["subdomain"]),
                normalize_outcome(row["leading_outcome"]),
                normalize_outcome(row["recommendation"]),
                str(row["consensus_grade"]),
                safe_float(row["consensus_score"], 0.0),
                safe_float(row["consensus_confidence"], 0.0),
                safe_int(row["wallet_count"]),
                safe_float(row["effective_wallet_count"], 0.0),
                safe_float(row["total_capital_committed"], 0.0),
                row["pass_reason"],
                str(row["updated_at"]),
                captured_at,
            ),
        )
    return len(rows)


def archive_actionable_signals(connection: sqlite3.Connection, signal_date: str) -> int:
    rows = connection.execute(
        """
        SELECT *
        FROM market_consensus
        WHERE consensus_grade IN ('S+', 'S', 'A', 'B')
          AND UPPER(recommendation) <> 'PASS'
        """
    ).fetchall()
    inserted = 0
    now = utc_now()
    for row in rows:
        condition_id = normalize_condition_id(row["condition_id"])
        recommended_outcome = normalize_outcome(row["recommendation"])
        signal_key = f"{signal_date}:{condition_id}:{recommended_outcome}"
        entry_price = latest_observed_price(connection, condition_id, recommended_outcome)
        cursor = connection.execute(
            """
            INSERT INTO signal_ledger (
                signal_key, signal_date, condition_id, event_id, market_title,
                domain, subdomain, recommended_outcome, signal_grade,
                consensus_score, consensus_confidence, wallet_count,
                effective_wallet_count, total_capital_committed, entry_price,
                first_seen_at, last_seen_at, source_engine_version, signal_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
            ON CONFLICT(signal_key) DO UPDATE SET
                event_id = excluded.event_id,
                market_title = excluded.market_title,
                domain = excluded.domain,
                subdomain = excluded.subdomain,
                signal_grade = excluded.signal_grade,
                consensus_score = excluded.consensus_score,
                consensus_confidence = excluded.consensus_confidence,
                wallet_count = excluded.wallet_count,
                effective_wallet_count = excluded.effective_wallet_count,
                total_capital_committed = excluded.total_capital_committed,
                entry_price = COALESCE(signal_ledger.entry_price, excluded.entry_price),
                last_seen_at = excluded.last_seen_at
            """,
            (
                signal_key, signal_date, condition_id, str(row["event_id"]),
                str(row["market_title"]), str(row["domain"]), str(row["subdomain"]),
                recommended_outcome, str(row["consensus_grade"]),
                safe_float(row["consensus_score"], 0.0),
                safe_float(row["consensus_confidence"], 0.0),
                safe_int(row["wallet_count"]),
                safe_float(row["effective_wallet_count"], 0.0),
                safe_float(row["total_capital_committed"], 0.0),
                entry_price, now, now, str(row["engine_version"]),
            ),
        )
        if cursor.rowcount == 1:
            inserted += 1
    return len(rows)


def resolution_from_market(market: dict[str, Any]) -> tuple[str, int | None, str]:
    outcomes = [normalize_outcome(x) for x in parse_json_array(market.get("outcomes"))]
    prices = [safe_float(x, None) for x in parse_json_array(market.get("outcomePrices"))]
    closed = bool(market.get("closed"))
    active = bool(market.get("active"))
    accepting = market.get("acceptingOrders")

    winner_index: int | None = None
    if outcomes and len(outcomes) == len(prices):
        one_indices = [
            index for index, price in enumerate(prices)
            if price is not None and abs(price - 1.0) <= RESOLUTION_PRICE_TOLERANCE
        ]
        zero_count = sum(
            1 for price in prices
            if price is not None and abs(price) <= RESOLUTION_PRICE_TOLERANCE
        )
        if len(one_indices) == 1 and zero_count >= max(1, len(prices) - 1):
            winner_index = one_indices[0]

    if winner_index is not None and closed:
        return outcomes[winner_index], winner_index, "RESOLVED"
    if closed:
        return "", None, "CLOSED_UNRESOLVED"
    if active or accepting is True:
        return "", None, "OPEN"
    return "", None, "INACTIVE"


def upsert_resolution(
    connection: sqlite3.Connection,
    condition_id: str,
    fallback_title: str,
    fallback_event_id: str,
    market: dict[str, Any],
) -> bool:
    resolved_outcome, winner_index, status = resolution_from_market(market)
    fetched_at = utc_now()
    closed = int(bool(market.get("closed")))
    active = int(bool(market.get("active")))
    accepting_raw = market.get("acceptingOrders")
    accepting = None if accepting_raw is None else int(bool(accepting_raw))
    title = str(market.get("question") or fallback_title)
    outcomes = parse_json_array(market.get("outcomes"))
    prices = parse_json_array(market.get("outcomePrices"))
    end_date = market.get("endDate") or market.get("endDateIso")
    resolution_time = fetched_at if status == "RESOLVED" else None

    connection.execute(
        """
        INSERT INTO consensus_market_resolutions (
            condition_id, gamma_market_id, event_id, market_title, market_slug,
            market_status, active, closed, accepting_orders, outcomes_json,
            outcome_prices_json, resolved_outcome, resolved_outcome_index,
            resolution_source, end_date, resolution_time, fetched_at, raw_market_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(condition_id) DO UPDATE SET
            gamma_market_id = excluded.gamma_market_id,
            event_id = excluded.event_id,
            market_title = excluded.market_title,
            market_slug = excluded.market_slug,
            market_status = excluded.market_status,
            active = excluded.active,
            closed = excluded.closed,
            accepting_orders = excluded.accepting_orders,
            outcomes_json = excluded.outcomes_json,
            outcome_prices_json = excluded.outcome_prices_json,
            resolved_outcome = COALESCE(excluded.resolved_outcome, consensus_market_resolutions.resolved_outcome),
            resolved_outcome_index = COALESCE(excluded.resolved_outcome_index, consensus_market_resolutions.resolved_outcome_index),
            resolution_source = excluded.resolution_source,
            end_date = excluded.end_date,
            resolution_time = COALESCE(consensus_market_resolutions.resolution_time, excluded.resolution_time),
            fetched_at = excluded.fetched_at,
            raw_market_json = excluded.raw_market_json
        """,
        (
            condition_id, str(market.get("id") or ""),
            str(market.get("eventId") or fallback_event_id), title,
            str(market.get("slug") or ""), status, active, closed, accepting,
            json.dumps(outcomes, ensure_ascii=False),
            json.dumps(prices, ensure_ascii=False),
            resolved_outcome or None, winner_index,
            str(market.get("resolutionSource") or ""),
            str(end_date or ""), resolution_time, fetched_at,
            json.dumps(market, ensure_ascii=False, sort_keys=True),
        ),
    )
    return status == "RESOLVED"


def refresh_resolutions(connection: sqlite3.Connection, client: GammaClient) -> tuple[int, int]:
    rows = connection.execute(
        """
        SELECT condition_id, MIN(market_title) AS market_title, MIN(event_id) AS event_id
        FROM signal_ledger
        WHERE signal_status = 'PENDING'
        GROUP BY condition_id
        ORDER BY MIN(signal_date), condition_id
        """
    ).fetchall()
    resolved = 0
    for row in rows:
        condition_id = normalize_condition_id(row["condition_id"])
        market = client.fetch_market(condition_id)
        if market is None:
            continue
        if upsert_resolution(
            connection, condition_id, str(row["market_title"]), str(row["event_id"]), market
        ):
            resolved += 1
    return len(rows), resolved


def price_for_outcome(resolution: sqlite3.Row, outcome: str) -> float | None:
    outcomes = [normalize_outcome(x) for x in parse_json_array(resolution["outcomes_json"])]
    prices = [safe_float(x, None) for x in parse_json_array(resolution["outcome_prices_json"])]
    target = normalize_outcome(outcome)
    for index, candidate in enumerate(outcomes):
        if candidate == target and index < len(prices):
            return prices[index]
    return None


def calculate_result(
    recommended_outcome: str,
    resolved_outcome: str,
    entry_price: float | None,
) -> tuple[str, float | None, float | None, str | None]:
    recommended = normalize_outcome(recommended_outcome)
    winner = normalize_outcome(resolved_outcome)
    if winner in {"UNKNOWN", "", "INVALID", "AMBIGUOUS"}:
        return "VOID", 0.0, 0.0, "Market resolved without a tradable winning outcome"
    result = "WIN" if recommended == winner else "LOSS"
    if entry_price is None or entry_price <= 0 or entry_price >= 1:
        return result, None, None, "Entry price unavailable; result recorded without ROI"
    if result == "WIN":
        pnl = (1.0 / entry_price) - 1.0
    else:
        pnl = -1.0
    return result, pnl, pnl * 100.0, None


def evaluate_resolved_signals(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        """
        SELECT sl.*, mr.resolved_outcome, mr.outcome_prices_json,
               mr.outcomes_json, mr.resolution_time
        FROM signal_ledger sl
        JOIN consensus_market_resolutions mr ON mr.condition_id = sl.condition_id
        WHERE sl.signal_status = 'PENDING'
          AND mr.market_status = 'RESOLVED'
          AND mr.resolved_outcome IS NOT NULL
        """
    ).fetchall()
    evaluated_at = utc_now()
    for row in rows:
        entry_price = safe_float(row["entry_price"], None)
        closing_price = price_for_outcome(row, str(row["recommended_outcome"]))
        result, pnl, roi, note = calculate_result(
            str(row["recommended_outcome"]), str(row["resolved_outcome"]), entry_price
        )
        clv = None
        if entry_price is not None and closing_price is not None:
            clv = (closing_price - entry_price) * 100.0
        connection.execute(
            """
            INSERT INTO signal_results (
                signal_id, signal_key, condition_id, signal_date, market_title,
                recommended_outcome, resolved_outcome, signal_grade,
                consensus_score, consensus_confidence, entry_price, closing_price,
                result, profit_loss_units, roi_pct, clv_price_points,
                resolved_at, evaluated_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signal_id) DO UPDATE SET
                resolved_outcome = excluded.resolved_outcome,
                closing_price = excluded.closing_price,
                result = excluded.result,
                profit_loss_units = excluded.profit_loss_units,
                roi_pct = excluded.roi_pct,
                clv_price_points = excluded.clv_price_points,
                resolved_at = excluded.resolved_at,
                evaluated_at = excluded.evaluated_at,
                notes = excluded.notes
            """,
            (
                row["signal_id"], row["signal_key"], row["condition_id"],
                row["signal_date"], row["market_title"], row["recommended_outcome"],
                row["resolved_outcome"], row["signal_grade"], row["consensus_score"],
                row["consensus_confidence"], entry_price, closing_price, result,
                pnl, roi, clv, row["resolution_time"], evaluated_at, note,
            ),
        )
        connection.execute(
            "UPDATE signal_ledger SET signal_status = ? WHERE signal_id = ?",
            (result, row["signal_id"]),
        )
    return len(rows)


def grade_record(connection: sqlite3.Connection, outcome_date: str, grade: str) -> str:
    row = connection.execute(
        """
        SELECT
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN result='PUSH' THEN 1 ELSE 0 END) AS pushes,
            SUM(CASE WHEN result='VOID' THEN 1 ELSE 0 END) AS voids
        FROM signal_results
        WHERE signal_date = ? AND signal_grade = ?
        """,
        (outcome_date, grade),
    ).fetchone()
    return f"{safe_int(row['wins'])}-{safe_int(row['losses'])}-{safe_int(row['pushes'])}-{safe_int(row['voids'])}"


def rebuild_daily_outcomes(connection: sqlite3.Connection) -> int:
    dates = {
        str(row[0])
        for row in connection.execute("SELECT DISTINCT review_date FROM daily_market_reviews")
    }
    dates.update(
        str(row[0])
        for row in connection.execute("SELECT DISTINCT signal_date FROM signal_ledger")
    )
    now = utc_now()
    for outcome_date in sorted(dates):
        review = connection.execute(
            """
            SELECT COUNT(*) AS reviewed,
                   SUM(CASE WHEN recommendation='PASS' OR consensus_grade='PASS' THEN 1 ELSE 0 END) AS passed
            FROM daily_market_reviews WHERE review_date = ?
            """,
            (outcome_date,),
        ).fetchone()
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS signals,
                SUM(CASE WHEN signal_status='PENDING' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN signal_status IN ('WIN','LOSS','PUSH','VOID') THEN 1 ELSE 0 END) AS resolved,
                SUM(CASE WHEN signal_status='WIN' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN signal_status='LOSS' THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN signal_status='PUSH' THEN 1 ELSE 0 END) AS pushes,
                SUM(CASE WHEN signal_status='VOID' THEN 1 ELSE 0 END) AS voids
            FROM signal_ledger WHERE signal_date = ?
            """,
            (outcome_date,),
        ).fetchone()
        pnl_row = connection.execute(
            """
            SELECT COALESCE(SUM(profit_loss_units), 0.0) AS pnl,
                   SUM(CASE WHEN profit_loss_units IS NOT NULL THEN 1 ELSE 0 END) AS priced
            FROM signal_results WHERE signal_date = ?
            """,
            (outcome_date,),
        ).fetchone()
        wins = safe_int(summary["wins"])
        losses = safe_int(summary["losses"])
        decisions = wins + losses
        hit_rate = (100.0 * wins / decisions) if decisions else None
        pnl = safe_float(pnl_row["pnl"], 0.0) or 0.0
        priced = safe_int(pnl_row["priced"])
        roi = (100.0 * pnl / priced) if priced else None
        connection.execute(
            """
            INSERT INTO daily_outcomes (
                outcome_date, markets_reviewed, actionable_signals, pass_markets,
                pending_signals, resolved_signals, wins, losses, pushes, voids,
                unresolved, hit_rate_pct, profit_loss_units, roi_pct,
                s_plus_record, s_record, a_record, b_record, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(outcome_date) DO UPDATE SET
                markets_reviewed = excluded.markets_reviewed,
                actionable_signals = excluded.actionable_signals,
                pass_markets = excluded.pass_markets,
                pending_signals = excluded.pending_signals,
                resolved_signals = excluded.resolved_signals,
                wins = excluded.wins,
                losses = excluded.losses,
                pushes = excluded.pushes,
                voids = excluded.voids,
                unresolved = excluded.unresolved,
                hit_rate_pct = excluded.hit_rate_pct,
                profit_loss_units = excluded.profit_loss_units,
                roi_pct = excluded.roi_pct,
                s_plus_record = excluded.s_plus_record,
                s_record = excluded.s_record,
                a_record = excluded.a_record,
                b_record = excluded.b_record,
                updated_at = excluded.updated_at
            """,
            (
                outcome_date, safe_int(review["reviewed"]), safe_int(summary["signals"]),
                safe_int(review["passed"]), safe_int(summary["pending"]),
                safe_int(summary["resolved"]), wins, losses,
                safe_int(summary["pushes"]), safe_int(summary["voids"]),
                safe_int(summary["pending"]), hit_rate, pnl, roi,
                grade_record(connection, outcome_date, "S+"),
                grade_record(connection, outcome_date, "S"),
                grade_record(connection, outcome_date, "A"),
                grade_record(connection, outcome_date, "B"), now,
            ),
        )
    return len(dates)


def print_report(connection: sqlite3.Connection, run: dict[str, Any]) -> None:
    width = 126
    print("=" * width)
    print("RESOLUTION & OUTCOME ENGINE COMPLETE")
    print("=" * width)
    print(f"Database: {DATABASE_PATH}")
    print(f"Review date: {run['review_date']}")
    print(f"Markets reviewed: {run['markets_reviewed']}")
    print(f"Actionable signals archived: {run['signals_archived']}")
    print(f"Pending markets checked: {run['resolution_candidates']}")
    print(f"Markets newly observed as resolved: {run['markets_resolved']}")
    print(f"Signal results evaluated: {run['results_evaluated']}")
    print(f"Gamma API successes/failures: {run['api_successes']}/{run['api_failures']}")
    print(f"Run ID: {run['run_id']}")

    print("\nDAILY OUTCOME SUMMARY")
    print("-" * width)
    rows = connection.execute(
        """
        SELECT * FROM daily_outcomes
        ORDER BY outcome_date DESC
        LIMIT 10
        """
    ).fetchall()
    for row in rows:
        hit = "n/a" if row["hit_rate_pct"] is None else f"{row['hit_rate_pct']:.2f}%"
        roi = "n/a" if row["roi_pct"] is None else f"{row['roi_pct']:+.2f}%"
        print(
            f"{row['outcome_date']} | reviewed={row['markets_reviewed']:>3} | picks={row['actionable_signals']:>3} "
            f"| pass={row['pass_markets']:>3} | W-L={row['wins']}-{row['losses']} "
            f"| pending={row['pending_signals']:>3} | hit={hit:>8} | units={row['profit_loss_units']:+.3f} | ROI={roi}"
        )

    print("\nLATEST SIGNAL LEDGER")
    print("-" * width)
    rows = connection.execute(
        """
        SELECT signal_date, market_title, recommended_outcome, signal_grade,
               consensus_score, consensus_confidence, entry_price, signal_status
        FROM signal_ledger
        ORDER BY signal_date DESC,
                 CASE signal_grade WHEN 'S+' THEN 1 WHEN 'S' THEN 2 WHEN 'A' THEN 3 ELSE 4 END,
                 consensus_score DESC
        LIMIT 30
        """
    ).fetchall()
    for index, row in enumerate(rows, 1):
        price = "n/a" if row["entry_price"] is None else f"{row['entry_price']:.4f}"
        print(
            f"{index:>2}. {str(row['market_title'])[:55]:<55} | {row['recommended_outcome'][:13]:<13} "
            f"| {row['signal_grade']:<4} | score={row['consensus_score']:>6.2f} "
            f"| conf={row['consensus_confidence']:>6.2f} | entry={price:<6} | {row['signal_status']}"
        )

    print("\nLATEST FINAL OUTCOMES")
    print("-" * width)
    rows = connection.execute(
        """
        SELECT signal_date, market_title, recommended_outcome, resolved_outcome,
               signal_grade, result, profit_loss_units, roi_pct
        FROM signal_results
        ORDER BY evaluated_at DESC
        LIMIT 30
        """
    ).fetchall()
    if not rows:
        print("No archived signals have resolved yet. This is expected until Gamma reports a final 1/0 outcome price.")
    for index, row in enumerate(rows, 1):
        units = "n/a" if row["profit_loss_units"] is None else f"{row['profit_loss_units']:+.3f}u"
        roi = "n/a" if row["roi_pct"] is None else f"{row['roi_pct']:+.2f}%"
        print(
            f"{index:>2}. {str(row['market_title'])[:52]:<52} | pick={row['recommended_outcome'][:10]:<10} "
            f"| final={str(row['resolved_outcome'])[:10]:<10} | {row['signal_grade']:<3} | {row['result']:<5} | {units:<9} | {roi}"
        )

    print("\nNext command:")
    print("  python -m src.resolution_outcome_engine 2>&1 | Tee-Object -FilePath resolution_outcome_output.txt")


def main() -> None:
    run_identifier = make_run_id()
    review_date = utc_date()
    connection = connect_database()
    client = GammaClient()
    try:
        ensure_required_sources(connection)
        ensure_schema(connection)
        with connection:
            markets_reviewed = capture_daily_reviews(connection, review_date)
            signals_archived = archive_actionable_signals(connection, review_date)
            candidates, markets_resolved = refresh_resolutions(connection, client)
            results_evaluated = evaluate_resolved_signals(connection)
            rebuild_daily_outcomes(connection)
            run = {
                "run_id": run_identifier,
                "engine_version": ENGINE_VERSION,
                "review_date": review_date,
                "markets_reviewed": markets_reviewed,
                "signals_archived": signals_archived,
                "resolution_candidates": candidates,
                "markets_resolved": markets_resolved,
                "results_evaluated": results_evaluated,
                "api_successes": client.stats.successes,
                "api_failures": client.stats.failures,
                "created_at": utc_now(),
            }
            connection.execute(
                """
                INSERT INTO resolution_outcome_runs (
                    run_id, engine_version, review_date, markets_reviewed,
                    signals_archived, resolution_candidates, markets_resolved,
                    results_evaluated, api_successes, api_failures, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(run.values()),
            )
        print_report(connection, run)
    finally:
        connection.close()


if __name__ == "__main__":
    main()