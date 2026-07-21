from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "polymarket.db"

BUSY_TIMEOUT_MS = 30_000
DEFAULT_LOOKBACK_HOURS = 24
DEFAULT_DISPLAY_LIMIT = 30
DEFAULT_MIN_OPPORTUNITY_SCORE = 35.0
DEFAULT_MIN_T_MINUS_MINUTES = 15
POLYMARKET_BASE_URL = "https://polymarket.com/event"


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def configure_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    normalized = clean_text(value).lower()

    return normalized in {
        "1",
        "true",
        "yes",
        "y",
        "closed",
        "resolved",
    }


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(value, maximum))


def divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def parse_json_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (list, dict, int, float, bool)):
        return value

    raw = clean_text(value)

    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_datetime(value: Any) -> datetime | None:
    raw = clean_text(value)

    if not raw:
        return None

    # Handle epoch values that may be stored as strings.
    try:
        numeric = float(raw)

        if numeric > 10_000_000_000:
            numeric /= 1000.0

        if numeric > 1_000_000_000:
            return datetime.fromtimestamp(
                numeric,
                tz=timezone.utc,
            )
    except ValueError:
        pass

    normalized = raw.replace(
        "Z",
        "+00:00",
    )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except ValueError:
        return None


def format_money(value: Any) -> str:
    amount = safe_float(value)

    if amount > 0:
        return f"+${amount:,.2f}"

    if amount < 0:
        return f"-${abs(amount):,.2f}"

    return "$0.00"


def format_datetime_local(
    value: datetime | None,
) -> str:
    if value is None:
        return "UNKNOWN"

    return value.astimezone().strftime(
        "%Y-%m-%d %I:%M %p %Z"
    )


def t_minus_display(
    seconds: int | None,
    status: str,
) -> str:
    if status == "LIVE":
        return "LIVE"

    if status == "CLOSED":
        return "CLOSED"

    if status == "RESOLUTION PENDING":
        return "RESOLUTION PENDING"

    if seconds is None:
        return "UNKNOWN"

    if seconds < 0:
        elapsed = abs(seconds)
        days, remainder = divmod(
            elapsed,
            86_400,
        )
        hours, remainder = divmod(
            remainder,
            3_600,
        )
        minutes = remainder // 60

        if days > 0:
            return (
                f"ENDED {days}d "
                f"{hours:02d}h AGO"
            )

        if hours > 0:
            return (
                f"ENDED {hours}h "
                f"{minutes:02d}m AGO"
            )

        return f"ENDED {minutes}m AGO"

    days, remainder = divmod(
        seconds,
        86_400,
    )
    hours, remainder = divmod(
        remainder,
        3_600,
    )
    minutes = remainder // 60

    if days > 0:
        return (
            f"T-{days}d "
            f"{hours:02d}h "
            f"{minutes:02d}m"
        )

    if hours > 0:
        return (
            f"T-{hours:02d}h "
            f"{minutes:02d}m"
        )

    return f"T-{minutes:02d}m"


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(
            f"Database not found: {DB}"
        )

    connection = sqlite3.connect(
        DB,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(
        f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}"
    )

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
            WHERE type='table'
              AND name=?
            """,
            (table_name,),
        ).fetchone()
        is not None
    )


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    if not table_exists(
        connection,
        table_name,
    ):
        return set()

    return {
        clean_text(row["name"])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def first_existing(
    columns: set[str],
    candidates: tuple[str, ...],
) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


def require_table(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    if not table_exists(
        connection,
        table_name,
    ):
        raise RuntimeError(
            f"Required table is missing: {table_name}"
        )


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_tables() -> None:
    connection = connect_database()

    try:
        require_table(
            connection,
            "market_predictions",
        )

        require_table(
            connection,
            "smart_money_flow_signals",
        )

        require_table(
            connection,
            "market_memory_snapshots",
        )

        require_table(
            connection,
            "gamma_markets",
        )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ranked_market_opportunities (
                opportunity_key TEXT PRIMARY KEY,

                rank_number INTEGER,

                condition_id TEXT NOT NULL,
                market_id TEXT,
                event_id TEXT,

                title TEXT,
                outcome TEXT,

                event_slug TEXT,
                market_slug TEXT,

                polymarket_url TEXT,
                url_source TEXT,
                link_verified INTEGER
                    NOT NULL DEFAULT 0,

                category TEXT,

                lookback_hours INTEGER
                    NOT NULL DEFAULT 24,

                prediction_key TEXT,
                flow_signal_key TEXT,
                memory_snapshot_key TEXT,

                predicted_direction TEXT,
                research_probability REAL
                    NOT NULL DEFAULT 50,

                prediction_confidence REAL
                    NOT NULL DEFAULT 0,

                prediction_grade TEXT,
                prediction_action TEXT,

                smart_money_flow_score REAL
                    NOT NULL DEFAULT 0,

                market_memory_score REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                persistence_score REAL
                    NOT NULL DEFAULT 0,

                trusted_flow_score REAL
                    NOT NULL DEFAULT 0,

                accumulation_score REAL
                    NOT NULL DEFAULT 0,

                distribution_score REAL
                    NOT NULL DEFAULT 0,

                current_net_flow REAL
                    NOT NULL DEFAULT 0,

                current_gross_flow REAL
                    NOT NULL DEFAULT 0,

                wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                qualified_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                watchlist_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                concentration_risk REAL
                    NOT NULL DEFAULT 0,

                whale_concentration REAL
                    NOT NULL DEFAULT 0,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                model_disagreement_score REAL
                    NOT NULL DEFAULT 0,

                current_price REAL,
                probability_edge REAL
                    NOT NULL DEFAULT 0,

                liquidity REAL
                    NOT NULL DEFAULT 0,

                volume REAL
                    NOT NULL DEFAULT 0,

                open_interest REAL
                    NOT NULL DEFAULT 0,

                spread REAL,

                market_start_at TEXT,
                market_end_at TEXT,
                event_start_at TEXT,
                event_end_at TEXT,
                resolution_at TEXT,

                t_minus_target_at TEXT,
                t_minus_target_type TEXT,
                t_minus_seconds INTEGER,
                t_minus_display TEXT,

                time_status TEXT
                    NOT NULL DEFAULT 'UNKNOWN',

                is_open INTEGER
                    NOT NULL DEFAULT 0,

                is_live INTEGER
                    NOT NULL DEFAULT 0,

                is_closed INTEGER
                    NOT NULL DEFAULT 0,

                is_expired INTEGER
                    NOT NULL DEFAULT 0,

                resolution_pending INTEGER
                    NOT NULL DEFAULT 0,

                starts_too_soon INTEGER
                    NOT NULL DEFAULT 0,

                exact_mapping INTEGER
                    NOT NULL DEFAULT 0,

                opportunity_score REAL
                    NOT NULL DEFAULT 0,

                opportunity_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                recommendation TEXT
                    NOT NULL DEFAULT 'PASS',

                is_actionable INTEGER
                    NOT NULL DEFAULT 0,

                positive_evidence_json TEXT,
                risk_flags_json TEXT,
                component_scores_json TEXT,
                metadata_json TEXT,

                observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_ranked_market_opportunities_rank
            ON ranked_market_opportunities(
                is_actionable DESC,
                opportunity_score DESC,
                rank_number ASC
            );

            CREATE INDEX IF NOT EXISTS
            idx_ranked_market_opportunities_condition
            ON ranked_market_opportunities(
                condition_id,
                observed_at DESC
            );

            CREATE INDEX IF NOT EXISTS
            idx_ranked_market_opportunities_time
            ON ranked_market_opportunities(
                time_status,
                t_minus_seconds
            );

            CREATE TABLE IF NOT EXISTS market_opportunity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                condition_id TEXT NOT NULL,

                rank_number INTEGER,
                opportunity_score REAL,
                opportunity_grade TEXT,
                recommendation TEXT,
                is_actionable INTEGER,

                research_probability REAL,
                prediction_confidence REAL,
                current_net_flow REAL,
                wallet_count INTEGER,

                polymarket_url TEXT,
                t_minus_target_at TEXT,
                t_minus_seconds INTEGER,
                t_minus_display TEXT,
                time_status TEXT,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                winning_outcome TEXT,

                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_market_opportunity_history_condition
            ON market_opportunity_history(
                condition_id,
                observed_at DESC
            );

            CREATE TABLE IF NOT EXISTS market_opportunity_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                lookback_hours INTEGER NOT NULL,

                predictions_loaded INTEGER
                    NOT NULL DEFAULT 0,

                exact_mappings INTEGER
                    NOT NULL DEFAULT 0,

                links_created INTEGER
                    NOT NULL DEFAULT 0,

                opportunities_saved INTEGER
                    NOT NULL DEFAULT 0,

                actionable_opportunities INTEGER
                    NOT NULL DEFAULT 0,

                open_opportunities INTEGER
                    NOT NULL DEFAULT 0,

                live_opportunities INTEGER
                    NOT NULL DEFAULT 0,

                closed_opportunities INTEGER
                    NOT NULL DEFAULT 0,

                missing_link_count INTEGER
                    NOT NULL DEFAULT 0,

                unknown_time_count INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# SOURCE LOADERS
# =============================================================================


def load_latest_predictions(
    lookback_hours: int,
) -> list[dict[str, Any]]:
    connection = connect_database()

    try:
        latest_predicted_at = connection.execute(
            """
            SELECT MAX(predicted_at)
            FROM market_predictions
            WHERE lookback_hours=?
            """,
            (lookback_hours,),
        ).fetchone()[0]

        if not latest_predicted_at:
            return []

        rows = connection.execute(
            """
            SELECT *
            FROM market_predictions
            WHERE lookback_hours=?
              AND predicted_at=?
            ORDER BY
                is_actionable DESC,
                confidence_score DESC,
                ABS(research_probability - 50) DESC
            """,
            (
                lookback_hours,
                latest_predicted_at,
            ),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


def load_latest_flow_signals(
    lookback_hours: int,
) -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        latest_observed_at = connection.execute(
            """
            SELECT MAX(observed_at)
            FROM smart_money_flow_signals
            WHERE lookback_hours=?
            """,
            (lookback_hours,),
        ).fetchone()[0]

        if not latest_observed_at:
            return {}

        rows = connection.execute(
            """
            SELECT *
            FROM smart_money_flow_signals
            WHERE lookback_hours=?
              AND observed_at=?
            """,
            (
                lookback_hours,
                latest_observed_at,
            ),
        ).fetchall()

        return {
            clean_text(
                row["condition_id"]
            ).lower(): dict(row)
            for row in rows
            if clean_text(
                row["condition_id"]
            )
        }

    finally:
        connection.close()


def load_latest_memory(
    lookback_hours: int,
) -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        latest_snapshot_at = connection.execute(
            """
            SELECT MAX(snapshot_at)
            FROM market_memory_snapshots
            WHERE lookback_hours=?
            """,
            (lookback_hours,),
        ).fetchone()[0]

        if not latest_snapshot_at:
            return {}

        rows = connection.execute(
            """
            SELECT *
            FROM market_memory_snapshots
            WHERE lookback_hours=?
              AND snapshot_at=?
            """,
            (
                lookback_hours,
                latest_snapshot_at,
            ),
        ).fetchall()

        return {
            clean_text(
                row["condition_id"]
            ).lower(): dict(row)
            for row in rows
            if clean_text(
                row["condition_id"]
            )
        }

    finally:
        connection.close()


def row_value(
    row: sqlite3.Row,
    columns: set[str],
    candidates: tuple[str, ...],
) -> Any:
    column = first_existing(
        columns,
        candidates,
    )

    if column is None:
        return None

    return row[column]


def load_gamma_events() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    connection = connect_database()

    try:
        if not table_exists(
            connection,
            "gamma_events",
        ):
            return {}, {}

        columns = table_columns(
            connection,
            "gamma_events",
        )

        rows = connection.execute(
            """
            SELECT *
            FROM gamma_events
            """
        ).fetchall()

        by_id: dict[
            str,
            dict[str, Any],
        ] = {}

        by_slug: dict[
            str,
            dict[str, Any],
        ] = {}

        for row in rows:
            event_id = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "event_id",
                        "id",
                        "gamma_event_id",
                    ),
                )
            )

            slug = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "slug",
                        "event_slug",
                    ),
                )
            )

            event = {
                "event_id": event_id,
                "slug": slug,
                "title": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "title",
                            "name",
                        ),
                    )
                ),
                "start_at": row_value(
                    row,
                    columns,
                    (
                        "start_date",
                        "startDate",
                        "start_at",
                        "start_time",
                    ),
                ),
                "end_at": row_value(
                    row,
                    columns,
                    (
                        "end_date",
                        "endDate",
                        "end_at",
                        "end_time",
                    ),
                ),
                "active": row_value(
                    row,
                    columns,
                    (
                        "active",
                        "is_active",
                    ),
                ),
                "closed": row_value(
                    row,
                    columns,
                    (
                        "closed",
                        "is_closed",
                    ),
                ),
                "archived": row_value(
                    row,
                    columns,
                    (
                        "archived",
                        "is_archived",
                    ),
                ),
                "liquidity": safe_float(
                    row_value(
                        row,
                        columns,
                        (
                            "liquidity",
                            "liquidity_num",
                        ),
                    )
                ),
                "volume": safe_float(
                    row_value(
                        row,
                        columns,
                        (
                            "volume",
                            "volume_num",
                        ),
                    )
                ),
                "open_interest": safe_float(
                    row_value(
                        row,
                        columns,
                        (
                            "open_interest",
                            "openInterest",
                        ),
                    )
                ),
            }

            if event_id:
                by_id[event_id] = event

            if slug:
                by_slug[slug] = event

        return by_id, by_slug

    finally:
        connection.close()


def load_gamma_markets() -> dict[str, dict[str, Any]]:
    connection = connect_database()

    try:
        columns = table_columns(
            connection,
            "gamma_markets",
        )

        rows = connection.execute(
            """
            SELECT *
            FROM gamma_markets
            """
        ).fetchall()

        markets: dict[
            str,
            dict[str, Any],
        ] = {}

        for row in rows:
            condition_id = clean_text(
                row_value(
                    row,
                    columns,
                    (
                        "condition_id",
                        "conditionId",
                        "conditionid",
                    ),
                )
            ).lower()

            if not condition_id:
                continue

            outcome_prices = parse_json_value(
                row_value(
                    row,
                    columns,
                    (
                        "outcome_prices",
                        "outcomePrices",
                    ),
                )
            )

            outcomes = parse_json_value(
                row_value(
                    row,
                    columns,
                    (
                        "outcomes",
                    ),
                )
            )

            current_price: float | None = None

            if isinstance(
                outcome_prices,
                list,
            ) and outcome_prices:
                current_price = safe_float(
                    outcome_prices[0],
                    0.0,
                )

            markets[condition_id] = {
                "condition_id": condition_id,
                "market_id": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "market_id",
                            "id",
                            "gamma_market_id",
                        ),
                    )
                ),
                "event_id": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "event_id",
                            "gamma_event_id",
                        ),
                    )
                ),
                "question": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "question",
                            "title",
                        ),
                    )
                ),
                "slug": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "slug",
                            "market_slug",
                        ),
                    )
                ),
                "event_slug": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "event_slug",
                            "eventSlug",
                        ),
                    )
                ),
                "category": clean_text(
                    row_value(
                        row,
                        columns,
                        (
                            "category",
                        ),
                    )
                ),
                "start_at": row_value(
                    row,
                    columns,
                    (
                        "start_date",
                        "startDate",
                        "start_at",
                        "start_time",
                        "game_start_time",
                    ),
                ),
                "end_at": row_value(
                    row,
                    columns,
                    (
                        "end_date",
                        "endDate",
                        "end_at",
                        "end_time",
                    ),
                ),
                "resolution_at": row_value(
                    row,
                    columns,
                    (
                        "resolution_at",
                        "resolved_at",
                        "resolution_date",
                    ),
                ),
                "active": row_value(
                    row,
                    columns,
                    (
                        "active",
                        "is_active",
                    ),
                ),
                "closed": row_value(
                    row,
                    columns,
                    (
                        "closed",
                        "is_closed",
                    ),
                ),
                "archived": row_value(
                    row,
                    columns,
                    (
                        "archived",
                        "is_archived",
                    ),
                ),
                "accepting_orders": row_value(
                    row,
                    columns,
                    (
                        "accepting_orders",
                        "acceptingOrders",
                    ),
                ),
                "liquidity": safe_float(
                    row_value(
                        row,
                        columns,
                        (
                            "liquidity",
                            "liquidity_num",
                        ),
                    )
                ),
                "volume": safe_float(
                    row_value(
                        row,
                        columns,
                        (
                            "volume",
                            "volume_num",
                        ),
                    )
                ),
                "open_interest": safe_float(
                    row_value(
                        row,
                        columns,
                        (
                            "open_interest",
                            "openInterest",
                        ),
                    )
                ),
                "spread": (
                    safe_float(
                        row_value(
                            row,
                            columns,
                            (
                                "spread",
                            ),
                        )
                    )
                    if row_value(
                        row,
                        columns,
                        (
                            "spread",
                        ),
                    )
                    is not None
                    else None
                ),
                "current_price": current_price,
                "outcomes": outcomes,
            }

        return markets

    finally:
        connection.close()


# =============================================================================
# TIME AND LINK LOGIC
# =============================================================================


def build_polymarket_link(
    market: dict[str, Any],
    event: dict[str, Any],
) -> tuple[str, str, int]:
    event_slug = (
        clean_text(
            market.get(
                "event_slug"
            )
        )
        or clean_text(
            event.get(
                "slug"
            )
        )
    )

    market_slug = clean_text(
        market.get(
            "slug"
        )
    )

    if event_slug:
        return (
            f"{POLYMARKET_BASE_URL}/"
            f"{quote(event_slug, safe='-')}",
            "EVENT_SLUG",
            1,
        )

    if market_slug:
        # Polymarket frontend slugs are served on the /event/ route.
        return (
            f"{POLYMARKET_BASE_URL}/"
            f"{quote(market_slug, safe='-')}",
            "MARKET_SLUG_EVENT_ROUTE",
            1,
        )

    return (
        "",
        "MISSING",
        0,
    )


def is_short_scheduled_event(
    market: dict[str, Any],
    event: dict[str, Any],
    start_at: datetime | None,
    end_at: datetime | None,
) -> bool:
    """
    Decide whether Gamma start/end timestamps represent a single scheduled
    contest that can genuinely become LIVE.

    Long-running futures such as tournament winners, elections, season awards,
    and championship outrights often have a historical startDate representing
    when the event or market opened. Those must remain OPEN until endDate rather
    than being labelled LIVE for the entire tournament or season.
    """
    if start_at is None or end_at is None:
        return False

    duration_hours = (
        end_at - start_at
    ).total_seconds() / 3600.0

    if duration_hours <= 0 or duration_hours > 48:
        return False

    searchable = " ".join(
        [
            clean_text(market.get("question")),
            clean_text(market.get("slug")),
            clean_text(market.get("event_slug")),
            clean_text(event.get("title")),
            clean_text(event.get("slug")),
        ]
    ).lower()

    scheduled_markers = (
        " vs ",
        "-vs-",
        " v ",
        "match",
        "game",
        "fight",
        "bout",
        "race",
        "map ",
        "set ",
    )

    return any(
        marker in searchable
        for marker in scheduled_markers
    )


def determine_time_status(
    market: dict[str, Any],
    event: dict[str, Any],
    now_utc: datetime,
    minimum_t_minus_minutes: int,
) -> dict[str, Any]:
    market_start = parse_datetime(
        market.get(
            "start_at"
        )
    )

    market_end = parse_datetime(
        market.get(
            "end_at"
        )
    )

    event_start = parse_datetime(
        event.get(
            "start_at"
        )
    )

    event_end = parse_datetime(
        event.get(
            "end_at"
        )
    )

    resolution_at = parse_datetime(
        market.get(
            "resolution_at"
        )
    )

    closed_flag = (
        safe_bool(
            market.get(
                "closed"
            )
        )
        or safe_bool(
            event.get(
                "closed"
            )
        )
    )

    archived_flag = (
        safe_bool(
            market.get(
                "archived"
            )
        )
        or safe_bool(
            event.get(
                "archived"
            )
        )
    )

    active_raw = market.get(
        "active"
    )

    accepting_orders_raw = market.get(
        "accepting_orders"
    )

    active_flag = (
        True
        if active_raw is None
        else safe_bool(
            active_raw
        )
    )

    accepting_orders = (
        True
        if accepting_orders_raw is None
        else safe_bool(
            accepting_orders_raw
        )
    )

    start_target = (
        market_start
        or event_start
    )

    end_target = (
        market_end
        or event_end
    )

    short_scheduled_event = is_short_scheduled_event(
        market=market,
        event=event,
        start_at=start_target,
        end_at=end_target,
    )

    target_at: datetime | None = None
    target_type = "UNKNOWN"
    is_live = 0
    is_closed = 0
    is_expired = 0
    resolution_pending = 0
    is_open = 0

    if closed_flag or archived_flag:
        is_closed = 1

        if resolution_at is None:
            resolution_pending = 1
            time_status = (
                "RESOLUTION PENDING"
            )
        else:
            time_status = "CLOSED"

        target_at = (
            resolution_at
            or end_target
        )

        target_type = (
            "RESOLUTION"
            if resolution_at
            else "MARKET_END"
        )

    elif (
        short_scheduled_event
        and start_target is not None
        and now_utc >= start_target
        and (
            end_target is None
            or now_utc < end_target
        )
    ):
        is_live = 1
        time_status = "LIVE"
        target_at = (
            end_target
            or start_target
        )
        target_type = (
            "GAME_END"
            if end_target
            else "GAME_START"
        )

    elif (
        end_target is not None
        and now_utc >= end_target
    ):
        is_expired = 1
        resolution_pending = 1
        time_status = (
            "RESOLUTION PENDING"
        )
        target_at = end_target
        target_type = "MARKET_END"

    elif (
        not active_flag
        or not accepting_orders
    ):
        is_closed = 1
        time_status = "CLOSED"
        target_at = (
            end_target
            or start_target
        )
        target_type = (
            "MARKET_END"
            if end_target
            else "GAME_START"
        )

    else:
        is_open = 1
        # For a true short scheduled contest, T-minus targets kickoff/start.
        # For futures and long-duration markets, T-minus targets market close/end.
        if (
            short_scheduled_event
            and start_target is not None
            and now_utc < start_target
        ):
            target_at = start_target
            target_type = "GAME_START"

        elif end_target is not None:
            target_at = end_target
            target_type = "MARKET_END"

        elif start_target is not None and now_utc < start_target:
            target_at = start_target
            target_type = "MARKET_START"

        else:
            target_at = None
            target_type = "UNKNOWN"

        if target_at is None:
            time_status = "OPEN - TIME UNKNOWN"

        else:
            seconds = int(
                (
                    target_at
                    - now_utc
                ).total_seconds()
            )

            if seconds <= (
                minimum_t_minus_minutes
                * 60
            ):
                time_status = (
                    "STARTING SOON"
                )
            else:
                time_status = "OPEN"

    seconds_remaining = (
        int(
            (
                target_at
                - now_utc
            ).total_seconds()
        )
        if target_at
        else None
    )

    starts_too_soon = int(
        is_open
        and seconds_remaining is not None
        and 0
        <= seconds_remaining
        <= (
            minimum_t_minus_minutes
            * 60
        )
    )

    return {
        "market_start_at": (
            market_start.isoformat()
            if market_start
            else None
        ),
        "market_end_at": (
            market_end.isoformat()
            if market_end
            else None
        ),
        "event_start_at": (
            event_start.isoformat()
            if event_start
            else None
        ),
        "event_end_at": (
            event_end.isoformat()
            if event_end
            else None
        ),
        "resolution_at": (
            resolution_at.isoformat()
            if resolution_at
            else None
        ),
        "t_minus_target_at": (
            target_at.isoformat()
            if target_at
            else None
        ),
        "t_minus_target_type": (
            target_type
        ),
        "t_minus_seconds": (
            seconds_remaining
        ),
        "t_minus_display": (
            t_minus_display(
                seconds_remaining,
                time_status,
            )
        ),
        "time_status": time_status,
        "is_open": is_open,
        "is_live": is_live,
        "is_closed": is_closed,
        "is_expired": is_expired,
        "resolution_pending": (
            resolution_pending
        ),
        "starts_too_soon": (
            starts_too_soon
        ),
        "short_scheduled_event": int(
            short_scheduled_event
        ),
    }


# =============================================================================
# SCORING
# =============================================================================


def opportunity_grade(
    score: float,
) -> str:
    if score >= 90:
        return "S+"

    if score >= 82:
        return "S"

    if score >= 74:
        return "A+"

    if score >= 66:
        return "A"

    if score >= 56:
        return "B"

    if score >= 45:
        return "WATCH"

    return "PASS"


def recommendation_from_score(
    score: float,
    predicted_direction: str,
    time_status: str,
    exact_mapping: int,
    link_verified: int,
    prediction_confidence: float,
) -> str:
    if not exact_mapping:
        return "PASS - NO EXACT MAPPING"

    if not link_verified:
        return "PASS - NO LINK"

    if time_status in {
        "CLOSED",
        "RESOLUTION PENDING",
    }:
        return "PASS - CLOSED"

    if time_status == "LIVE":
        return "LIVE WATCH"

    if time_status == "STARTING SOON":
        return "WATCH - STARTING SOON"

    if prediction_confidence < 45:
        return "PASS"

    if predicted_direction == "BULLISH":
        if score >= 85:
            return "STRONG YES LEAN"

        if score >= 68:
            return "YES LEAN"

    if predicted_direction == "BEARISH":
        if score >= 85:
            return "STRONG NO LEAN"

        if score >= 68:
            return "NO LEAN"

    if score >= 55:
        return "WATCH"

    return "PASS"


def build_opportunities(
    lookback_hours: int,
    minimum_score: float,
    minimum_t_minus_minutes: int,
    include_live: bool,
) -> tuple[
    list[dict[str, Any]],
    int,
]:
    predictions = load_latest_predictions(
        lookback_hours
    )

    if not predictions:
        raise RuntimeError(
            "No current predictions were found. "
            "Run prediction_engine.py first."
        )

    flow_lookup = load_latest_flow_signals(
        lookback_hours
    )

    memory_lookup = load_latest_memory(
        lookback_hours
    )

    gamma_markets = load_gamma_markets()

    (
        events_by_id,
        events_by_slug,
    ) = load_gamma_events()

    now_utc = utc_now()
    observed_at = now_utc.isoformat()

    opportunities: list[
        dict[str, Any]
    ] = []

    for prediction in predictions:
        condition_id = clean_text(
            prediction.get(
                "condition_id"
            )
        ).lower()

        if not condition_id:
            continue

        market = gamma_markets.get(
            condition_id,
            {},
        )

        exact_mapping = int(
            bool(market)
        )

        event = {}

        event_id = clean_text(
            market.get(
                "event_id"
            )
            or prediction.get(
                "event_id"
            )
        )

        event_slug = clean_text(
            market.get(
                "event_slug"
            )
        )

        if event_id:
            event = events_by_id.get(
                event_id,
                {},
            )

        if not event and event_slug:
            event = events_by_slug.get(
                event_slug,
                {},
            )

        flow = flow_lookup.get(
            condition_id,
            {},
        )

        memory = memory_lookup.get(
            condition_id,
            {},
        )

        (
            polymarket_url,
            url_source,
            link_verified,
        ) = build_polymarket_link(
            market,
            event,
        )

        time_data = determine_time_status(
            market=market,
            event=event,
            now_utc=now_utc,
            minimum_t_minus_minutes=(
                minimum_t_minus_minutes
            ),
        )

        if (
            time_data[
                "is_live"
            ]
            and not include_live
        ):
            continue

        research_probability = safe_float(
            prediction.get(
                "research_probability"
            ),
            50.0,
        )

        prediction_confidence = safe_float(
            prediction.get(
                "confidence_score"
            )
        )

        flow_score = safe_float(
            prediction.get(
                "smart_money_flow_score"
            )
            or flow.get(
                "smart_money_flow_score"
            )
        )

        memory_score = safe_float(
            prediction.get(
                "market_memory_score"
            )
            or memory.get(
                "market_memory_score"
            )
        )

        consensus_strength = safe_float(
            prediction.get(
                "consensus_strength"
            )
            or flow.get(
                "consensus_strength"
            )
        )

        persistence_score = safe_float(
            prediction.get(
                "persistence_score"
            )
            or flow.get(
                "persistence_score"
            )
        )

        trusted_flow_score = safe_float(
            prediction.get(
                "trusted_flow_score"
            )
            or flow.get(
                "trusted_flow_score"
            )
        )

        concentration_risk = safe_float(
            prediction.get(
                "concentration_risk"
            )
            or flow.get(
                "concentration_risk"
            )
        )

        whale_concentration = safe_float(
            prediction.get(
                "whale_concentration"
            )
            or flow.get(
                "whale_concentration"
            )
        )

        data_completeness = safe_float(
            prediction.get(
                "data_completeness_score"
            )
        )

        model_disagreement = safe_float(
            prediction.get(
                "model_disagreement_score"
            )
        )

        wallet_count = safe_int(
            prediction.get(
                "current_wallet_count"
            )
            or flow.get(
                "current_unique_wallet_count"
            )
        )

        gross_flow = safe_float(
            prediction.get(
                "current_gross_flow"
            )
            or flow.get(
                "current_gross_flow"
            )
        )

        net_flow = safe_float(
            prediction.get(
                "current_net_flow"
            )
            or flow.get(
                "current_net_flow"
            )
        )

        probability_strength = clamp(
            abs(
                research_probability
                - 50.0
            )
            * 2.0
        )

        breadth_score = clamp(
            wallet_count
            / 6.0
            * 100.0
        )

        liquidity = safe_float(
            market.get(
                "liquidity"
            )
            or event.get(
                "liquidity"
            )
        )

        volume = safe_float(
            market.get(
                "volume"
            )
            or event.get(
                "volume"
            )
        )

        open_interest = safe_float(
            market.get(
                "open_interest"
            )
            or event.get(
                "open_interest"
            )
        )

        liquidity_score = clamp(
            math.log1p(
                max(
                    liquidity,
                    0.0,
                )
            )
            / math.log1p(
                1_000_000.0
            )
            * 100.0
        )

        volume_score = clamp(
            math.log1p(
                max(
                    volume,
                    0.0,
                )
            )
            / math.log1p(
                10_000_000.0
            )
            * 100.0
        )

        timing_score = 100.0

        if time_data[
            "time_status"
        ] == "OPEN - TIME UNKNOWN":
            timing_score = 55.0

        elif time_data[
            "time_status"
        ] == "STARTING SOON":
            timing_score = 25.0

        elif time_data[
            "time_status"
        ] == "LIVE":
            timing_score = 20.0

        elif time_data[
            "time_status"
        ] in {
            "CLOSED",
            "RESOLUTION PENDING",
        }:
            timing_score = 0.0

        mapping_score = (
            100.0
            if exact_mapping
            and link_verified
            else 0.0
        )

        evidence_score = clamp(
            probability_strength
            * 0.22
            + prediction_confidence
            * 0.20
            + flow_score
            * 0.14
            + memory_score
            * 0.08
            + consensus_strength
            * 0.10
            + persistence_score
            * 0.08
            + trusted_flow_score
            * 0.08
            + breadth_score
            * 0.05
            + data_completeness
            * 0.05
        )

        market_quality_score = clamp(
            liquidity_score
            * 0.45
            + volume_score
            * 0.35
            + clamp(
                open_interest
                / 100_000.0
                * 100.0
            )
            * 0.20
        )

        risk_penalty = (
            concentration_risk
            * 0.12
            + whale_concentration
            * 0.10
            + model_disagreement
            * 0.07
        )

        opportunity_score = clamp(
            evidence_score
            * 0.72
            + market_quality_score
            * 0.10
            + timing_score
            * 0.10
            + mapping_score
            * 0.08
            - risk_penalty
        )

        if not exact_mapping:
            opportunity_score = min(
                opportunity_score,
                25.0,
            )

        if not link_verified:
            opportunity_score = min(
                opportunity_score,
                25.0,
            )

        if time_data[
            "time_status"
        ] in {
            "CLOSED",
            "RESOLUTION PENDING",
        }:
            opportunity_score = min(
                opportunity_score,
                10.0,
            )

        if (
            time_data[
                "time_status"
            ]
            == "LIVE"
        ):
            opportunity_score = min(
                opportunity_score,
                45.0,
            )

        if time_data[
            "starts_too_soon"
        ]:
            opportunity_score = min(
                opportunity_score,
                50.0,
            )

        predicted_direction = clean_text(
            prediction.get(
                "predicted_direction"
            )
        ).upper()

        recommendation = (
            recommendation_from_score(
                score=opportunity_score,
                predicted_direction=(
                    predicted_direction
                ),
                time_status=(
                    time_data[
                        "time_status"
                    ]
                ),
                exact_mapping=(
                    exact_mapping
                ),
                link_verified=(
                    link_verified
                ),
                prediction_confidence=(
                    prediction_confidence
                ),
            )
        )

        actionable = int(
            recommendation
            in {
                "STRONG YES LEAN",
                "YES LEAN",
                "STRONG NO LEAN",
                "NO LEAN",
            }
            and time_data[
                "is_open"
            ]
            and not time_data[
                "starts_too_soon"
            ]
            and exact_mapping
            and link_verified
        )

        positive_evidence: list[str] = []
        risk_flags: list[str] = []

        if exact_mapping:
            positive_evidence.append(
                "Exact Gamma condition-ID mapping"
            )

        if link_verified:
            positive_evidence.append(
                "Direct Polymarket event link available"
            )

        if prediction_confidence >= 60:
            positive_evidence.append(
                "Prediction confidence is at least medium"
            )

        if consensus_strength >= 75:
            positive_evidence.append(
                "Strong wallet consensus"
            )

        if persistence_score >= 75:
            positive_evidence.append(
                "Persistent wallet participation"
            )

        if trusted_flow_score >= 60:
            positive_evidence.append(
                "Trusted wallets dominate measured flow"
            )

        if wallet_count >= 5:
            positive_evidence.append(
                "Broad wallet participation"
            )

        if not exact_mapping:
            risk_flags.append(
                "No exact Gamma condition-ID mapping"
            )

        if not link_verified:
            risk_flags.append(
                "No verified Polymarket link"
            )

        if (
            time_data[
                "time_status"
            ]
            == "OPEN - TIME UNKNOWN"
        ):
            risk_flags.append(
                "No trustworthy T-minus timestamp"
            )

        if time_data[
            "starts_too_soon"
        ]:
            risk_flags.append(
                "Market starts too soon for normal entry"
            )

        if time_data[
            "is_live"
        ]:
            risk_flags.append(
                "Market is live"
            )

        if time_data[
            "is_closed"
        ] or time_data[
            "is_expired"
        ]:
            risk_flags.append(
                "Market is not open"
            )

        if concentration_risk >= 70:
            risk_flags.append(
                "High flow concentration"
            )

        if whale_concentration >= 70:
            risk_flags.append(
                "One wallet dominates observed flow"
            )

        if wallet_count < 3:
            risk_flags.append(
                "Limited wallet breadth"
            )

        if model_disagreement >= 35:
            risk_flags.append(
                "Model components disagree materially"
            )

        if opportunity_score < minimum_score:
            continue

        title = (
            clean_text(
                market.get(
                    "question"
                )
            )
            or clean_text(
                prediction.get(
                    "title"
                )
            )
            or condition_id
        )

        outcomes = market.get(
            "outcomes"
        )

        selected_outcome = (
            "YES"
            if predicted_direction
            == "BULLISH"
            else (
                "NO"
                if predicted_direction
                == "BEARISH"
                else ""
            )
        )

        opportunity_key = (
            f"{condition_id}:"
            f"{lookback_hours}:"
            f"{observed_at}"
        )

        component_scores = {
            "evidence_score": (
                evidence_score
            ),
            "market_quality_score": (
                market_quality_score
            ),
            "timing_score": (
                timing_score
            ),
            "mapping_score": (
                mapping_score
            ),
            "risk_penalty": (
                risk_penalty
            ),
            "probability_strength": (
                probability_strength
            ),
            "liquidity_score": (
                liquidity_score
            ),
            "volume_score": (
                volume_score
            ),
        }

        opportunities.append(
            {
                "opportunity_key": (
                    opportunity_key
                ),
                "rank_number": None,
                "condition_id": (
                    condition_id
                ),
                "market_id": clean_text(
                    market.get(
                        "market_id"
                    )
                    or prediction.get(
                        "market_id"
                    )
                ),
                "event_id": event_id,
                "title": title,
                "outcome": (
                    selected_outcome
                ),
                "event_slug": (
                    clean_text(
                        market.get(
                            "event_slug"
                        )
                    )
                    or clean_text(
                        event.get(
                            "slug"
                        )
                    )
                ),
                "market_slug": clean_text(
                    market.get(
                        "slug"
                    )
                ),
                "polymarket_url": (
                    polymarket_url
                ),
                "url_source": url_source,
                "link_verified": (
                    link_verified
                ),
                "category": (
                    clean_text(
                        market.get(
                            "category"
                        )
                    )
                    or clean_text(
                        prediction.get(
                            "category"
                        )
                    )
                ),
                "lookback_hours": (
                    lookback_hours
                ),
                "prediction_key": (
                    clean_text(
                        prediction.get(
                            "prediction_key"
                        )
                    )
                ),
                "flow_signal_key": (
                    clean_text(
                        flow.get(
                            "signal_key"
                        )
                    )
                ),
                "memory_snapshot_key": (
                    clean_text(
                        memory.get(
                            "snapshot_key"
                        )
                    )
                ),
                "predicted_direction": (
                    predicted_direction
                ),
                "research_probability": (
                    research_probability
                ),
                "prediction_confidence": (
                    prediction_confidence
                ),
                "prediction_grade": (
                    clean_text(
                        prediction.get(
                            "prediction_grade"
                        )
                    )
                ),
                "prediction_action": (
                    clean_text(
                        prediction.get(
                            "recommended_action"
                        )
                    )
                ),
                "smart_money_flow_score": (
                    flow_score
                ),
                "market_memory_score": (
                    memory_score
                ),
                "consensus_strength": (
                    consensus_strength
                ),
                "persistence_score": (
                    persistence_score
                ),
                "trusted_flow_score": (
                    trusted_flow_score
                ),
                "accumulation_score": (
                    safe_float(
                        prediction.get(
                            "accumulation_score"
                        )
                    )
                ),
                "distribution_score": (
                    safe_float(
                        prediction.get(
                            "distribution_score"
                        )
                    )
                ),
                "current_net_flow": (
                    net_flow
                ),
                "current_gross_flow": (
                    gross_flow
                ),
                "wallet_count": (
                    wallet_count
                ),
                "elite_wallet_count": (
                    safe_int(
                        prediction.get(
                            "elite_wallet_count"
                        )
                    )
                ),
                "qualified_wallet_count": (
                    safe_int(
                        prediction.get(
                            "qualified_wallet_count"
                        )
                    )
                ),
                "watchlist_wallet_count": (
                    safe_int(
                        prediction.get(
                            "watchlist_wallet_count"
                        )
                    )
                ),
                "concentration_risk": (
                    concentration_risk
                ),
                "whale_concentration": (
                    whale_concentration
                ),
                "data_completeness_score": (
                    data_completeness
                ),
                "model_disagreement_score": (
                    model_disagreement
                ),
                "current_price": (
                    safe_float(
                        prediction.get(
                            "current_price"
                        )
                        or market.get(
                            "current_price"
                        )
                    )
                    if (
                        prediction.get(
                            "current_price"
                        )
                        is not None
                        or market.get(
                            "current_price"
                        )
                        is not None
                    )
                    else None
                ),
                "probability_edge": (
                    safe_float(
                        prediction.get(
                            "probability_edge"
                        )
                    )
                ),
                "liquidity": liquidity,
                "volume": volume,
                "open_interest": (
                    open_interest
                ),
                "spread": (
                    market.get(
                        "spread"
                    )
                ),
                **{
                    key: value
                    for key, value in time_data.items()
                    if key != "short_scheduled_event"
                },
                "exact_mapping": (
                    exact_mapping
                ),
                "opportunity_score": (
                    opportunity_score
                ),
                "opportunity_grade": (
                    opportunity_grade(
                        opportunity_score
                    )
                ),
                "recommendation": (
                    recommendation
                ),
                "is_actionable": (
                    actionable
                ),
                "positive_evidence_json": (
                    stable_json(
                        positive_evidence
                    )
                ),
                "risk_flags_json": (
                    stable_json(
                        risk_flags
                    )
                ),
                "component_scores_json": (
                    stable_json(
                        component_scores
                    )
                ),
                "metadata_json": stable_json(
                    {
                        "model_version": "1.0",
                        "probability_status": (
                            "UNCALIBRATED_RESEARCH_ESTIMATE"
                        ),
                        "gamma_outcomes": (
                            outcomes
                        ),
                        "minimum_score": (
                            minimum_score
                        ),
                        "minimum_t_minus_minutes": (
                            minimum_t_minus_minutes
                        ),
                        "include_live": (
                            include_live
                        ),
                        "short_scheduled_event": (
                            time_data.get(
                                "short_scheduled_event",
                                0,
                            )
                        ),
                    }
                ),
                "observed_at": (
                    observed_at
                ),
                "created_at": (
                    observed_at
                ),
                "updated_at": (
                    observed_at
                ),
            }
        )

    opportunities.sort(
        key=lambda row: (
            row[
                "is_actionable"
            ],
            row[
                "opportunity_score"
            ],
            row[
                "prediction_confidence"
            ],
            abs(
                row[
                    "research_probability"
                ]
                - 50.0
            ),
        ),
        reverse=True,
    )

    for rank, row in enumerate(
        opportunities,
        start=1,
    ):
        row[
            "rank_number"
        ] = rank

    return (
        opportunities,
        len(predictions),
    )


# =============================================================================
# SAVE
# =============================================================================


OPPORTUNITY_COLUMNS = [
    "opportunity_key",
    "rank_number",
    "condition_id",
    "market_id",
    "event_id",
    "title",
    "outcome",
    "event_slug",
    "market_slug",
    "polymarket_url",
    "url_source",
    "link_verified",
    "category",
    "lookback_hours",
    "prediction_key",
    "flow_signal_key",
    "memory_snapshot_key",
    "predicted_direction",
    "research_probability",
    "prediction_confidence",
    "prediction_grade",
    "prediction_action",
    "smart_money_flow_score",
    "market_memory_score",
    "consensus_strength",
    "persistence_score",
    "trusted_flow_score",
    "accumulation_score",
    "distribution_score",
    "current_net_flow",
    "current_gross_flow",
    "wallet_count",
    "elite_wallet_count",
    "qualified_wallet_count",
    "watchlist_wallet_count",
    "concentration_risk",
    "whale_concentration",
    "data_completeness_score",
    "model_disagreement_score",
    "current_price",
    "probability_edge",
    "liquidity",
    "volume",
    "open_interest",
    "spread",
    "market_start_at",
    "market_end_at",
    "event_start_at",
    "event_end_at",
    "resolution_at",
    "t_minus_target_at",
    "t_minus_target_type",
    "t_minus_seconds",
    "t_minus_display",
    "time_status",
    "is_open",
    "is_live",
    "is_closed",
    "is_expired",
    "resolution_pending",
    "starts_too_soon",
    "exact_mapping",
    "opportunity_score",
    "opportunity_grade",
    "recommendation",
    "is_actionable",
    "positive_evidence_json",
    "risk_flags_json",
    "component_scores_json",
    "metadata_json",
    "observed_at",
    "created_at",
    "updated_at",
]


def build_insert_query(
    table_name: str,
    columns: list[str],
) -> str:
    names = ", ".join(
        f'"{column}"'
        for column in columns
    )

    placeholders = ", ".join(
        "?"
        for _ in columns
    )

    return (
        f'INSERT OR REPLACE INTO "{table_name}" '
        f'({names}) VALUES ({placeholders})'
    )


def save_opportunities(
    opportunities: list[dict[str, Any]],
) -> tuple[int, int]:
    connection = connect_database()

    opportunity_query = build_insert_query(
        "ranked_market_opportunities",
        OPPORTUNITY_COLUMNS,
    )

    history_rows = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        for row in opportunities:
            connection.execute(
                opportunity_query,
                tuple(
                    row[column]
                    for column
                    in OPPORTUNITY_COLUMNS
                ),
            )

            connection.execute(
                """
                INSERT INTO market_opportunity_history (
                    opportunity_key,
                    condition_id,
                    rank_number,
                    opportunity_score,
                    opportunity_grade,
                    recommendation,
                    is_actionable,
                    research_probability,
                    prediction_confidence,
                    current_net_flow,
                    wallet_count,
                    polymarket_url,
                    t_minus_target_at,
                    t_minus_seconds,
                    t_minus_display,
                    time_status,
                    resolved,
                    winning_outcome,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    row[
                        "opportunity_key"
                    ],
                    row[
                        "condition_id"
                    ],
                    row[
                        "rank_number"
                    ],
                    row[
                        "opportunity_score"
                    ],
                    row[
                        "opportunity_grade"
                    ],
                    row[
                        "recommendation"
                    ],
                    row[
                        "is_actionable"
                    ],
                    row[
                        "research_probability"
                    ],
                    row[
                        "prediction_confidence"
                    ],
                    row[
                        "current_net_flow"
                    ],
                    row[
                        "wallet_count"
                    ],
                    row[
                        "polymarket_url"
                    ],
                    row[
                        "t_minus_target_at"
                    ],
                    row[
                        "t_minus_seconds"
                    ],
                    row[
                        "t_minus_display"
                    ],
                    row[
                        "time_status"
                    ],
                    0,
                    "",
                    row[
                        "observed_at"
                    ],
                ),
            )

            history_rows += 1

        connection.commit()

        return (
            len(opportunities),
            history_rows,
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# RUN LOGGING
# =============================================================================


def start_run(
    lookback_hours: int,
) -> tuple[int, datetime]:
    started_at = utc_now()
    connection = connect_database()

    try:
        cursor = connection.execute(
            """
            INSERT INTO market_opportunity_runs (
                started_at,
                lookback_hours,
                status
            )
            VALUES (
                ?, ?, 'RUNNING'
            )
            """,
            (
                started_at.isoformat(),
                lookback_hours,
            ),
        )

        connection.commit()

        return (
            cursor.lastrowid,
            started_at,
        )

    finally:
        connection.close()


def finish_run(
    run_id: int,
    started_at: datetime,
    status: str,
    predictions_loaded: int,
    opportunities: list[dict[str, Any]],
    opportunities_saved: int,
    error_message: str = "",
) -> None:
    finished_at = utc_now()
    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE market_opportunity_runs
            SET
                finished_at=?,
                elapsed_seconds=?,
                predictions_loaded=?,
                exact_mappings=?,
                links_created=?,
                opportunities_saved=?,
                actionable_opportunities=?,
                open_opportunities=?,
                live_opportunities=?,
                closed_opportunities=?,
                missing_link_count=?,
                unknown_time_count=?,
                status=?,
                error_message=?
            WHERE id=?
            """,
            (
                finished_at.isoformat(),
                (
                    finished_at
                    - started_at
                ).total_seconds(),
                predictions_loaded,
                sum(
                    1
                    for row in opportunities
                    if row[
                        "exact_mapping"
                    ]
                ),
                sum(
                    1
                    for row in opportunities
                    if row[
                        "link_verified"
                    ]
                ),
                opportunities_saved,
                sum(
                    1
                    for row in opportunities
                    if row[
                        "is_actionable"
                    ]
                ),
                sum(
                    1
                    for row in opportunities
                    if row[
                        "is_open"
                    ]
                ),
                sum(
                    1
                    for row in opportunities
                    if row[
                        "is_live"
                    ]
                ),
                sum(
                    1
                    for row in opportunities
                    if row[
                        "is_closed"
                    ]
                    or row[
                        "is_expired"
                    ]
                ),
                sum(
                    1
                    for row in opportunities
                    if not row[
                        "link_verified"
                    ]
                ),
                sum(
                    1
                    for row in opportunities
                    if row[
                        "t_minus_target_at"
                    ]
                    is None
                ),
                status,
                error_message,
                run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# DISPLAY
# =============================================================================


def display_summary(
    opportunities: list[dict[str, Any]],
    predictions_loaded: int,
    display_limit: int,
) -> None:
    print()
    print("=" * 124)
    print("OPPORTUNITY RANKING ENGINE SUMMARY")
    print("=" * 124)

    print(
        f"Predictions loaded:             "
        f"{predictions_loaded}"
    )

    print(
        f"Opportunities ranked:           "
        f"{len(opportunities)}"
    )

    print(
        f"Actionable opportunities:       "
        f"{sum(1 for row in opportunities if row['is_actionable'])}"
    )

    print(
        f"Exact Gamma mappings:           "
        f"{sum(1 for row in opportunities if row['exact_mapping'])}"
    )

    print(
        f"Direct links created:           "
        f"{sum(1 for row in opportunities if row['link_verified'])}"
    )

    print(
        f"Open / live / closed:           "
        f"{sum(1 for row in opportunities if row['is_open'])} "
        f"/ {sum(1 for row in opportunities if row['is_live'])} "
        f"/ {sum(1 for row in opportunities if row['is_closed'] or row['is_expired'])}"
    )

    print(
        f"Unknown T-minus targets:        "
        f"{sum(1 for row in opportunities if row['t_minus_target_at'] is None)}"
    )

    print()
    print(
        "WARNING: prediction probabilities remain uncalibrated "
        "research estimates until resolution-based validation is complete."
    )

    print("=" * 124)

    print()
    print("TOP RANKED MARKET OPPORTUNITIES")

    for row in opportunities[:display_limit]:
        positive_evidence = json.loads(
            row[
                "positive_evidence_json"
            ]
        )

        risk_flags = json.loads(
            row[
                "risk_flags_json"
            ]
        )

        target_at = parse_datetime(
            row[
                "t_minus_target_at"
            ]
        )

        print()
        print("-" * 124)

        print(
            f"{row['rank_number']}. "
            f"{row['title']}"
        )

        print("-" * 124)

        print(
            f"Outcome / recommendation:       "
            f"{row['outcome'] or '-'} "
            f"/ {row['recommendation']}"
        )

        print(
            f"Opportunity score / grade:      "
            f"{row['opportunity_score']:.1f} "
            f"/ {row['opportunity_grade']}"
        )

        print(
            f"Research probability:           "
            f"{row['research_probability']:.1f}%"
        )

        print(
            f"Prediction confidence:          "
            f"{row['prediction_confidence']:.1f} "
            f"/ {row['prediction_grade'] or '-'}"
        )

        print(
            f"Smart-money flow / memory:      "
            f"{row['smart_money_flow_score']:.1f} "
            f"/ {row['market_memory_score']:.1f}"
        )

        print(
            f"Wallets / trusted flow score:   "
            f"{row['wallet_count']} "
            f"/ {row['trusted_flow_score']:.1f}"
        )

        print(
            f"Net / gross flow:               "
            f"{format_money(row['current_net_flow'])} "
            f"/ ${row['current_gross_flow']:,.2f}"
        )

        print(
            f"Concentration / disagreement:   "
            f"{row['concentration_risk']:.1f} "
            f"/ {row['model_disagreement_score']:.1f}"
        )

        print(
            f"Time status / T-minus:          "
            f"{row['time_status']} "
            f"/ {row['t_minus_display']}"
        )

        print(
            f"T-minus target:                 "
            f"{row['t_minus_target_type']} "
            f"/ {format_datetime_local(target_at)}"
        )

        print(
            f"Polymarket link:                "
            f"{row['polymarket_url'] or 'MISSING'}"
        )

        if positive_evidence:
            print(
                "Positive evidence:              "
                + ", ".join(
                    positive_evidence
                )
            )

        if risk_flags:
            print(
                "Risk flags:                     "
                + ", ".join(
                    risk_flags
                )
            )


# =============================================================================
# MAIN
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rank current Polymarket opportunities using predictions, "
            "smart-money flow, market memory, exact Gamma mappings, "
            "direct Polymarket links and T-minus timing."
        )
    )

    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=DEFAULT_LOOKBACK_HOURS,
    )

    parser.add_argument(
        "--minimum-score",
        type=float,
        default=DEFAULT_MIN_OPPORTUNITY_SCORE,
    )

    parser.add_argument(
        "--minimum-t-minus-minutes",
        type=int,
        default=DEFAULT_MIN_T_MINUS_MINUTES,
        help=(
            "Open markets inside this window are downgraded to "
            "STARTING SOON and cannot be actionable."
        ),
    )

    parser.add_argument(
        "--include-live",
        action="store_true",
        help=(
            "Include LIVE markets on the board. They remain "
            "non-actionable in v1."
        ),
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    configure_utf8()
    arguments = parse_arguments()

    lookback_hours = max(
        arguments.lookback_hours,
        1,
    )

    minimum_score = clamp(
        arguments.minimum_score,
        0.0,
        100.0,
    )

    minimum_t_minus_minutes = max(
        arguments.minimum_t_minus_minutes,
        0,
    )

    print()
    print("=" * 124)
    print("POLYMARKET OPPORTUNITY RANKING ENGINE v1")
    print("=" * 124)

    print(f"Database:                    {DB}")

    print(
        f"Lookback:                    "
        f"{lookback_hours} hours"
    )

    print(
        f"Minimum opportunity score:  "
        f"{minimum_score:.1f}"
    )

    print(
        f"Minimum safe T-minus:       "
        f"{minimum_t_minus_minutes} minutes"
    )

    print(
        f"Include live markets:       "
        f"{arguments.include_live}"
    )

    print(
        "Required for action:        "
        "EXACT CONDITION ID + DIRECT LINK + OPEN MARKET + SAFE T-MINUS"
    )

    print("=" * 124)

    create_tables()

    run_id, started_at = start_run(
        lookback_hours
    )

    opportunities: list[
        dict[str, Any]
    ] = []

    predictions_loaded = 0
    opportunities_saved = 0

    try:
        (
            opportunities,
            predictions_loaded,
        ) = build_opportunities(
            lookback_hours=(
                lookback_hours
            ),
            minimum_score=(
                minimum_score
            ),
            minimum_t_minus_minutes=(
                minimum_t_minus_minutes
            ),
            include_live=(
                arguments.include_live
            ),
        )

        if not opportunities:
            raise RuntimeError(
                "No opportunities passed the selected filters."
            )

        (
            opportunities_saved,
            _,
        ) = save_opportunities(
            opportunities
        )

        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="SUCCESS",
            predictions_loaded=(
                predictions_loaded
            ),
            opportunities=(
                opportunities
            ),
            opportunities_saved=(
                opportunities_saved
            ),
        )

        display_summary(
            opportunities=opportunities,
            predictions_loaded=(
                predictions_loaded
            ),
            display_limit=max(
                arguments.display_limit,
                1,
            ),
        )

        print()
        print("=" * 124)
        print("OPPORTUNITY RANKING ENGINE COMPLETE")
        print("=" * 124)

        print(
            "Current ranked board:       "
            "ranked_market_opportunities"
        )

        print(
            "Opportunity history:        "
            "market_opportunity_history"
        )

        print(
            "Run history:                "
            "market_opportunity_runs"
        )

        print()
        print(
            "Every actionable recommendation requires an exact "
            "Gamma mapping, a direct Polymarket link, an open market "
            "and a safe T-minus window."
        )

        print("=" * 124)

    except Exception as error:
        finish_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            predictions_loaded=(
                predictions_loaded
            ),
            opportunities=(
                opportunities
            ),
            opportunities_saved=(
                opportunities_saved
            ),
            error_message=(
                f"{type(error).__name__}: "
                f"{error}"
            ),
        )

        raise


if __name__ == "__main__":
    main()