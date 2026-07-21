from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_monitor_database import create_market_monitor_tables


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"

REQUEST_TIMEOUT_SECONDS = 25
REQUEST_RETRIES = 3
REQUEST_DELAY_SECONDS = 0.15

STARTING_SOON_SECONDS = 60 * 60
MAX_UNCONFIRMED_GAME_SECONDS = 8 * 60 * 60

RESOLUTION_WIN_THRESHOLD = 0.995
RESOLUTION_LOSS_THRESHOLD = 0.005

MAX_MARKETS_PER_RUN = 150

VALID_CONDITION_ID = re.compile(
    r"^0x[a-fA-F0-9]{64}$"
)

SPORTS_KEYWORDS = (
    " vs ",
    " vs. ",
    "spread:",
    "o/u",
    "over/under",
    "exact score",
    "team to advance",
    "both teams to score",
    "win on 2026-",
    "nba",
    "wnba",
    "nfl",
    "nhl",
    "mlb",
    "mls",
    "soccer",
    "football",
    "basketball",
    "baseball",
    "hockey",
    "tennis",
    "wimbledon",
    "open:",
    "ufc",
    "mma",
    "boxing",
    "cricket",
    "rugby",
    "golf",
    "formula 1",
)


# =============================================================================
# BASIC HELPERS
# =============================================================================


def connect_database() -> sqlite3.Connection:
    """Open the platform SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}."
        )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC time as ISO text."""

    return utc_now().isoformat()


def safe_float(value: Any) -> float:
    """Convert a value to float safely."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value to integer safely."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def safe_bool(value: Any) -> bool:
    """Convert common API values to Boolean."""

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    return str(value or "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def clean_text(value: Any) -> str:
    """Return trimmed display text."""

    return str(value or "").strip()


def normalize_text(value: Any) -> str:
    """Normalize text for matching."""

    return clean_text(value).casefold()


def normalize_market_id(value: Any) -> str:
    """Normalize a condition ID."""

    return clean_text(value).lower()


def is_valid_condition_id(value: Any) -> bool:
    """Validate a Polymarket condition ID."""

    return bool(
        VALID_CONDITION_ID.fullmatch(
            clean_text(value)
        )
    )


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp and convert it to UTC."""

    text = clean_text(value)

    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(timezone.utc)


def datetime_to_iso(
    value: datetime | None,
) -> str | None:
    """Convert a datetime to UTC ISO text."""

    if value is None:
        return None

    return value.astimezone(
        timezone.utc
    ).isoformat()


def decode_json_list(value: Any) -> list[Any]:
    """Decode API values stored as lists or JSON strings."""

    if isinstance(value, list):
        return value

    text = clean_text(value)

    if not text:
        return []

    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return []

    return decoded if isinstance(decoded, list) else []


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Return True when a table exists."""

    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def is_probably_sports_market(title: str) -> bool:
    """Identify likely sports markets from their titles."""

    normalized = normalize_text(title)

    return any(
        keyword in normalized
        for keyword in SPORTS_KEYWORDS
    )


# =============================================================================
# CURRENT MARKET DISCOVERY
# =============================================================================


def load_current_market_sources() -> dict[str, dict[str, Any]]:
    """
    Load only markets relevant to the platform now.

    Sources:
    - latest scan of each tracked wallet
    - latest stored consensus signal for each market/outcome
    """

    connection = connect_database()
    discovered: dict[str, dict[str, Any]] = {}

    try:
        if table_exists(connection, "positions"):
            rows = connection.execute(
                """
                WITH latest_scans AS (
                    SELECT
                        wallet,
                        MAX(id) AS latest_scan_id
                    FROM wallet_scans
                    GROUP BY wallet
                )
                SELECT
                    positions.market_id,
                    MAX(positions.title) AS title,
                    MAX(positions.outcome) AS outcome,
                    MAX(positions.current_price) AS current_price,
                    SUM(
                        COALESCE(
                            positions.current_value,
                            0
                        )
                    ) AS total_value
                FROM positions
                INNER JOIN latest_scans
                    ON positions.wallet = latest_scans.wallet
                   AND positions.scan_id =
                       latest_scans.latest_scan_id
                WHERE positions.market_id IS NOT NULL
                  AND TRIM(positions.market_id) != ''
                GROUP BY positions.market_id
                ORDER BY total_value DESC
                """
            ).fetchall()

            for row in rows:
                market_id = normalize_market_id(
                    row["market_id"]
                )

                if not is_valid_condition_id(market_id):
                    continue

                discovered[market_id] = {
                    "market_id": market_id,
                    "title": clean_text(row["title"]),
                    "outcome": clean_text(row["outcome"]),
                    "current_price": safe_float(
                        row["current_price"]
                    ),
                    "priority_value": safe_float(
                        row["total_value"]
                    ),
                    "source": "LATEST_POSITIONS",
                }

        if table_exists(
            connection,
            "consensus_history",
        ):
            rows = connection.execute(
                """
                WITH latest_consensus AS (
                    SELECT
                        market_id,
                        LOWER(TRIM(outcome))
                            AS normalized_outcome,
                        MAX(id) AS latest_id
                    FROM consensus_history
                    GROUP BY
                        market_id,
                        LOWER(TRIM(outcome))
                )
                SELECT
                    history.market_id,
                    history.title,
                    history.outcome,
                    history.average_current_price,
                    history.combined_value,
                    history.conviction_score
                FROM consensus_history AS history
                INNER JOIN latest_consensus AS latest
                    ON history.id = latest.latest_id
                ORDER BY
                    history.conviction_score DESC,
                    history.combined_value DESC
                """
            ).fetchall()

            for row in rows:
                market_id = normalize_market_id(
                    row["market_id"]
                )

                if not is_valid_condition_id(market_id):
                    continue

                existing = discovered.get(market_id)

                consensus_value = safe_float(
                    row["combined_value"]
                )

                if existing is None:
                    discovered[market_id] = {
                        "market_id": market_id,
                        "title": clean_text(row["title"]),
                        "outcome": clean_text(row["outcome"]),
                        "current_price": safe_float(
                            row["average_current_price"]
                        ),
                        "priority_value": consensus_value,
                        "source": "LATEST_CONSENSUS",
                    }

                elif consensus_value > safe_float(
                    existing.get("priority_value")
                ):
                    existing["title"] = (
                        clean_text(row["title"])
                        or existing["title"]
                    )

                    existing["outcome"] = (
                        clean_text(row["outcome"])
                        or existing["outcome"]
                    )

                    existing["current_price"] = safe_float(
                        row["average_current_price"]
                    )

                    existing["priority_value"] = (
                        consensus_value
                    )

                    existing["source"] = (
                        "POSITIONS_AND_CONSENSUS"
                    )

    finally:
        connection.close()

    ordered = sorted(
        discovered.values(),
        key=lambda record: (
            is_probably_sports_market(
                record["title"]
            ),
            safe_float(
                record["priority_value"]
            ),
        ),
        reverse=True,
    )

    return {
        record["market_id"]: record
        for record in ordered[
            :MAX_MARKETS_PER_RUN
        ]
    }


# =============================================================================
# EXACT GAMMA LOOKUP
# =============================================================================


def build_market_url(
    condition_id: str,
) -> str:
    """Build an exact condition-ID lookup URL."""

    query = urllib.parse.urlencode(
        {
            "condition_ids": condition_id,
            "limit": 10,
        }
    )

    return f"{GAMMA_MARKETS_URL}?{query}"


def fetch_exact_gamma_market(
    condition_id: str,
) -> dict[str, Any] | None:
    """
    Fetch one market and accept only an exact condition-ID match.

    Unrelated records returned by Gamma are ignored.
    """

    if not is_valid_condition_id(
        condition_id
    ):
        return None

    url = build_market_url(
        condition_id
    )

    last_error: Exception | None = None

    for attempt in range(
        1,
        REQUEST_RETRIES + 1,
    ):
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/149.0 Safari/537.36"
                ),
                "Cache-Control": "no-cache",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                payload = json.loads(
                    response.read().decode(
                        "utf-8",
                        errors="replace",
                    )
                )

            if isinstance(payload, dict):
                possible_markets = (
                    payload.get("markets")
                    or payload.get("data")
                    or []
                )
            elif isinstance(payload, list):
                possible_markets = payload
            else:
                possible_markets = []

            for market in possible_markets:
                if not isinstance(market, dict):
                    continue

                returned_id = normalize_market_id(
                    market.get("conditionId")
                )

                if returned_id == condition_id:
                    return market

            return None

        except urllib.error.HTTPError as error:
            last_error = error

            if error.code not in {
                403,
                429,
                500,
                502,
                503,
                504,
            }:
                break

        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as error:
            last_error = error

        if attempt < REQUEST_RETRIES:
            time.sleep(attempt * 1.0)

    if last_error is not None:
        print(
            f"  Request failed for "
            f"{condition_id[:12]}...: "
            f"{type(last_error).__name__}"
        )

    return None


# =============================================================================
# MARKET PARSING
# =============================================================================


def get_primary_event(
    market: dict[str, Any],
) -> dict[str, Any]:
    """Return the first nested event."""

    events = market.get("events")

    if not isinstance(events, list):
        return {}

    for event in events:
        if isinstance(event, dict):
            return event

    return {}


def choose_confirmed_game_start(
    market: dict[str, Any],
    event: dict[str, Any],
) -> datetime | None:
    """
    Choose an actual sports-game start field.

    startDate is intentionally excluded because it often represents
    the time trading opened rather than the game kickoff.
    """

    candidates = (
        market.get("gameStartTime"),
        event.get("gameStartTime"),
        event.get("scheduledStartTime"),
        market.get("scheduledStartTime"),
    )

    for candidate in candidates:
        parsed = parse_datetime(candidate)

        if parsed is not None:
            return parsed

    return None


def choose_end_time(
    market: dict[str, Any],
    event: dict[str, Any],
) -> datetime | None:
    """Choose a market/event end time."""

    for candidate in (
        market.get("endDate"),
        event.get("endDate"),
    ):
        parsed = parse_datetime(candidate)

        if parsed is not None:
            return parsed

    return None


def parse_outcomes_and_prices(
    market: dict[str, Any],
) -> tuple[list[str], list[float]]:
    """Decode outcomes and prices."""

    outcomes = [
        clean_text(value)
        for value in decode_json_list(
            market.get("outcomes")
        )
    ]

    prices = [
        safe_float(value)
        for value in decode_json_list(
            market.get("outcomePrices")
        )
    ]

    return outcomes, prices


def detect_resolution(
    market: dict[str, Any],
    outcomes: list[str],
    prices: list[float],
) -> tuple[bool, str, str]:
    """Detect a clearly resolved market."""

    closed = safe_bool(
        market.get("closed")
    )

    if (
        closed
        and outcomes
        and len(outcomes) == len(prices)
    ):
        winners = [
            index
            for index, price in enumerate(prices)
            if price >= RESOLUTION_WIN_THRESHOLD
        ]

        valid_losers = all(
            index in winners
            or price <= RESOLUTION_LOSS_THRESHOLD
            for index, price in enumerate(prices)
        )

        if len(winners) == 1 and valid_losers:
            return (
                True,
                outcomes[winners[0]],
                "RESOLVED",
            )

    resolution_text = normalize_text(
        market.get("resolutionStatus")
        or market.get("umaResolutionStatus")
    )

    if resolution_text in {
        "resolved",
        "final",
        "completed",
        "complete",
    }:
        return True, "", "RESOLVED"

    if closed:
        return (
            False,
            "",
            "CLOSED_PENDING_RESOLUTION",
        )

    return False, "", "UNRESOLVED"


def extract_live_state(
    market: dict[str, Any],
    event: dict[str, Any],
) -> tuple[bool, bool, str, str, str]:
    """Extract live fields when Gamma already contains them."""

    status = normalize_text(
        event.get("gameStatus")
        or market.get("gameStatus")
        or event.get("status")
    )

    is_live = (
        safe_bool(event.get("live"))
        or safe_bool(market.get("live"))
        or status in {
            "live",
            "inprogress",
            "in_progress",
            "in progress",
            "playing",
            "halftime",
        }
    )

    is_ended = (
        safe_bool(event.get("ended"))
        or safe_bool(market.get("ended"))
        or status in {
            "ended",
            "final",
            "finished",
            "complete",
            "completed",
        }
    )

    score = clean_text(
        event.get("score")
        or market.get("score")
    )

    period = clean_text(
        event.get("period")
        or market.get("period")
        or event.get("gameStatus")
    )

    elapsed = clean_text(
        event.get("elapsed")
        or market.get("elapsed")
    )

    return (
        is_live,
        is_ended,
        score,
        period,
        elapsed,
    )


def determine_lifecycle(
    game_start: datetime | None,
    active: bool,
    accepting_orders: bool,
    closed: bool,
    is_live: bool,
    is_ended: bool,
    is_resolved: bool,
) -> tuple[str, int, int | None, int | None]:
    """Calculate lifecycle and countdown fields."""

    now = utc_now()

    seconds_to_start: int | None = None
    seconds_since_start: int | None = None

    if game_start is not None:
        difference = int(
            (game_start - now).total_seconds()
        )

        seconds_to_start = difference

        if difference <= 0:
            seconds_since_start = abs(difference)

    if is_resolved:
        return (
            "RESOLVED",
            0,
            seconds_to_start,
            seconds_since_start,
        )

    if is_live:
        return (
            "LIVE",
            0,
            seconds_to_start,
            seconds_since_start,
        )

    if is_ended:
        return (
            "ENDED",
            0,
            seconds_to_start,
            seconds_since_start,
        )

    if closed:
        return (
            "CLOSED",
            0,
            seconds_to_start,
            seconds_since_start,
        )

    if (
        game_start is not None
        and seconds_to_start is not None
        and seconds_to_start > 0
    ):
        if seconds_to_start <= STARTING_SOON_SECONDS:
            return (
                "STARTING_SOON",
                1,
                seconds_to_start,
                None,
            )

        return (
            "PREGAME",
            1,
            seconds_to_start,
            None,
        )

    if (
        game_start is not None
        and seconds_since_start is not None
    ):
        if (
            seconds_since_start
            <= MAX_UNCONFIRMED_GAME_SECONDS
            and (active or accepting_orders)
        ):
            return (
                "LIVE_UNCONFIRMED",
                0,
                seconds_to_start,
                seconds_since_start,
            )

        return (
            "ENDED_UNCONFIRMED",
            0,
            seconds_to_start,
            seconds_since_start,
        )

    if active or accepting_orders:
        return (
            "ACTIVE_UNSCHEDULED",
            0,
            None,
            None,
        )

    return (
        "UNKNOWN",
        0,
        None,
        None,
    )


def choose_tracked_price(
    source: dict[str, Any],
    outcomes: list[str],
    prices: list[float],
) -> float:
    """Choose the price corresponding to the tracked outcome."""

    tracked_outcome = normalize_text(
        source.get("outcome")
    )

    if (
        tracked_outcome
        and len(outcomes) == len(prices)
    ):
        for outcome, price in zip(
            outcomes,
            prices,
        ):
            if normalize_text(outcome) == tracked_outcome:
                return price

    source_price = safe_float(
        source.get("current_price")
    )

    if source_price > 0:
        return source_price

    return prices[0] if prices else 0.0


def infer_sport(title: str) -> str:
    """Infer a broad sports label."""

    normalized = normalize_text(title)

    if any(
        value in normalized
        for value in (
            "soccer",
            "football",
            "world cup",
            "exact score",
            "team to advance",
        )
    ):
        return "Soccer"

    if any(
        value in normalized
        for value in (
            "nba",
            "wnba",
            "basketball",
        )
    ):
        return "Basketball"

    if any(
        value in normalized
        for value in (
            "mlb",
            "baseball",
        )
    ):
        return "Baseball"

    if any(
        value in normalized
        for value in (
            "nhl",
            "hockey",
        )
    ):
        return "Hockey"

    if any(
        value in normalized
        for value in (
            "tennis",
            "wimbledon",
            "open:",
        )
    ):
        return "Tennis"

    if any(
        value in normalized
        for value in (
            "ufc",
            "mma",
        )
    ):
        return "MMA"

    return "Sports" if is_probably_sports_market(title) else ""


def parse_gamma_market(
    market: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    """Convert one exact Gamma result into local metadata."""

    now_iso = utc_now_iso()
    event = get_primary_event(market)

    condition_id = normalize_market_id(
        market.get("conditionId")
    )

    title = (
        clean_text(market.get("question"))
        or clean_text(market.get("title"))
        or clean_text(source.get("title"))
        or "Unknown market"
    )

    game_start = choose_confirmed_game_start(
        market,
        event,
    )

    end_time = choose_end_time(
        market,
        event,
    )

    active = safe_bool(
        market.get("active")
    )

    accepting_orders = safe_bool(
        market.get("acceptingOrders")
    )

    closed = safe_bool(
        market.get("closed")
    )

    (
        is_live,
        is_ended,
        score,
        period,
        elapsed,
    ) = extract_live_state(
        market,
        event,
    )

    outcomes, prices = parse_outcomes_and_prices(
        market
    )

    (
        is_resolved,
        winning_outcome,
        resolution_status,
    ) = detect_resolution(
        market,
        outcomes,
        prices,
    )

    (
        lifecycle,
        is_pregame,
        seconds_to_start,
        seconds_since_start,
    ) = determine_lifecycle(
        game_start=game_start,
        active=active,
        accepting_orders=accepting_orders,
        closed=closed,
        is_live=is_live,
        is_ended=is_ended,
        is_resolved=is_resolved,
    )

    event_slug = clean_text(
        event.get("slug")
    )

    market_slug = clean_text(
        market.get("slug")
    )

    return {
        "market_id": condition_id,
        "gamma_market_id": clean_text(
            market.get("id")
        ),
        "condition_id": condition_id,
        "event_id": clean_text(
            event.get("id")
        ),
        "title": title,
        "event_title": clean_text(
            event.get("title")
        ),
        "outcome": clean_text(
            source.get("outcome")
        ),
        "market_slug": market_slug,
        "event_slug": event_slug,
        "sports_slug": (
            clean_text(
                market.get("sportsSlug")
            )
            or clean_text(
                event.get("sportsSlug")
            )
            or event_slug
        ),
        "category": clean_text(
            market.get("category")
            or event.get("category")
        ),
        "sport": infer_sport(title),
        "league": clean_text(
            event.get("league")
            or event.get(
                "leagueAbbreviation"
            )
        ),
        "start_time": None,
        "game_start_time": datetime_to_iso(
            game_start
        ),
        "end_time": datetime_to_iso(
            end_time
        ),
        "lifecycle_status": lifecycle,
        "is_pregame": is_pregame,
        "is_live": int(is_live),
        "is_ended": int(is_ended),
        "is_closed": int(closed),
        "is_resolved": int(is_resolved),
        "score": score,
        "period": period,
        "elapsed": elapsed,
        "winning_outcome": winning_outcome,
        "resolution_status": resolution_status,
        "active": int(active),
        "accepting_orders": int(
            accepting_orders
        ),
        "current_price": choose_tracked_price(
            source,
            outcomes,
            prices,
        ),
        "outcome_prices_json": json.dumps(
            {
                "outcomes": outcomes,
                "prices": prices,
            },
            ensure_ascii=False,
        ),
        "seconds_to_start": seconds_to_start,
        "seconds_since_start": (
            seconds_since_start
        ),
        "source_updated_at": clean_text(
            market.get("updatedAt")
            or event.get("updatedAt")
        ),
        "first_seen_at": now_iso,
        "last_checked_at": now_iso,
        "updated_at": now_iso,
    }


# =============================================================================
# DATABASE WRITES
# =============================================================================


def load_existing_metadata(
    market_id: str,
) -> dict[str, Any] | None:
    """Load existing metadata for comparison."""

    connection = connect_database()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM market_metadata
            WHERE market_id = ?
            """,
            (market_id,),
        ).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def save_market_metadata(
    record: dict[str, Any],
) -> None:
    """Insert or update current metadata."""

    connection = connect_database()

    columns = [
        "market_id",
        "gamma_market_id",
        "condition_id",
        "event_id",
        "title",
        "event_title",
        "outcome",
        "market_slug",
        "event_slug",
        "sports_slug",
        "category",
        "sport",
        "league",
        "start_time",
        "game_start_time",
        "end_time",
        "lifecycle_status",
        "is_pregame",
        "is_live",
        "is_ended",
        "is_closed",
        "is_resolved",
        "score",
        "period",
        "elapsed",
        "winning_outcome",
        "resolution_status",
        "active",
        "accepting_orders",
        "current_price",
        "outcome_prices_json",
        "seconds_to_start",
        "seconds_since_start",
        "source_updated_at",
        "first_seen_at",
        "last_checked_at",
        "updated_at",
    ]

    placeholders = ", ".join(
        "?" for _ in columns
    )

    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in columns
        if column not in {
            "market_id",
            "first_seen_at",
        }
    )

    query = f"""
        INSERT INTO market_metadata (
            {", ".join(columns)}
        )
        VALUES ({placeholders})
        ON CONFLICT(market_id) DO UPDATE SET
            {updates}
    """

    try:
        connection.execute(
            query,
            tuple(
                record[column]
                for column in columns
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def ensure_tracked_market(
    record: dict[str, Any],
    source: str,
) -> None:
    """Add or update a valid tracked market."""

    connection = connect_database()
    now_iso = utc_now_iso()

    try:
        connection.execute(
            """
            INSERT INTO tracked_markets (
                market_id,
                title,
                outcome,
                priority,
                monitor_wallets,
                monitor_status,
                monitor_price,
                monitor_resolution,
                enabled,
                source,
                added_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, 1, 1, 1, 1,
                1, ?, ?, ?
            )
            ON CONFLICT(market_id) DO UPDATE SET
                title = excluded.title,
                outcome = excluded.outcome,
                priority = excluded.priority,
                enabled = 1,
                updated_at = excluded.updated_at
            """,
            (
                record["market_id"],
                record["title"],
                record["outcome"],
                9 if record["sport"] else 5,
                source,
                now_iso,
                now_iso,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def status_changed(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> bool:
    """Detect meaningful lifecycle changes."""

    if previous is None:
        return True

    fields = (
        "lifecycle_status",
        "game_start_time",
        "is_live",
        "is_ended",
        "is_closed",
        "is_resolved",
        "score",
        "period",
        "elapsed",
        "winning_outcome",
    )

    return any(
        str(previous.get(field) or "")
        != str(current.get(field) or "")
        for field in fields
    )


def save_status_history(
    record: dict[str, Any],
) -> None:
    """Store one meaningful lifecycle snapshot."""

    connection = connect_database()

    try:
        connection.execute(
            """
            INSERT INTO market_status_history (
                market_id,
                lifecycle_status,
                is_pregame,
                is_live,
                is_ended,
                is_closed,
                is_resolved,
                start_time,
                game_start_time,
                score,
                period,
                elapsed,
                winning_outcome,
                resolution_status,
                seconds_to_start,
                current_price,
                observed_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                record["market_id"],
                record["lifecycle_status"],
                record["is_pregame"],
                record["is_live"],
                record["is_ended"],
                record["is_closed"],
                record["is_resolved"],
                record["start_time"],
                record["game_start_time"],
                record["score"],
                record["period"],
                record["elapsed"],
                record["winning_outcome"],
                record["resolution_status"],
                record["seconds_to_start"],
                record["current_price"],
                record["updated_at"],
            ),
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# MONITOR RUN LOGGING
# =============================================================================


def start_monitor_run() -> tuple[str, datetime]:
    """Create a monitor-run record."""

    run_id = str(uuid.uuid4())
    started_at = utc_now()

    connection = connect_database()

    try:
        connection.execute(
            """
            INSERT INTO monitor_runs (
                run_id,
                status,
                started_at
            )
            VALUES (?, 'RUNNING', ?)
            """,
            (
                run_id,
                started_at.isoformat(),
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return run_id, started_at


def finish_monitor_run(
    run_id: str,
    started_at: datetime,
    status: str,
    markets_checked: int,
    markets_updated: int,
    live_games: int,
    ended_games: int,
    resolved_markets: int,
    error: Exception | None = None,
) -> None:
    """Complete a monitor-run record."""

    finished_at = utc_now()

    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE monitor_runs
            SET
                status = ?,
                finished_at = ?,
                elapsed_seconds = ?,
                markets_checked = ?,
                markets_updated = ?,
                live_games = ?,
                ended_games = ?,
                resolved_markets = ?,
                error_type = ?,
                error_message = ?
            WHERE run_id = ?
            """,
            (
                status,
                finished_at.isoformat(),
                (
                    finished_at
                    - started_at
                ).total_seconds(),
                markets_checked,
                markets_updated,
                live_games,
                ended_games,
                resolved_markets,
                (
                    type(error).__name__
                    if error
                    else None
                ),
                str(error) if error else None,
                run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


# =============================================================================
# DISPLAY
# =============================================================================


def format_t_minus(
    seconds: int | None,
) -> str:
    """Format a T-minus value."""

    if seconds is None:
        return "NO CONFIRMED START"

    if seconds <= 0:
        return "STARTED"

    days, remainder = divmod(
        seconds,
        86400,
    )

    hours, remainder = divmod(
        remainder,
        3600,
    )

    minutes, seconds_left = divmod(
        remainder,
        60,
    )

    if days:
        return (
            f"T-{days}d "
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds_left:02d}"
        )

    return (
        f"T-{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds_left:02d}"
    )


def display_upcoming(
    records: list[dict[str, Any]],
) -> None:
    """Display the nearest confirmed sports starts."""

    upcoming = [
        record
        for record in records
        if record["seconds_to_start"] is not None
        and safe_int(
            record["seconds_to_start"]
        ) > 0
    ]

    upcoming.sort(
        key=lambda record: safe_int(
            record["seconds_to_start"]
        )
    )

    if not upcoming:
        print()
        print(
            "No confirmed upcoming game-start "
            "times were found in this refresh."
        )
        return

    print()
    print("NEXT CONFIRMED STARTS")
    print("-" * 100)

    for record in upcoming[:20]:
        print(
            f"{format_t_minus(record['seconds_to_start']):<22}"
            f"{record['title']} — "
            f"{record['outcome']}"
        )


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Refresh exact market scheduling and lifecycle metadata."""

    print()
    print("=" * 100)
    print(
        "POLYMARKET MARKET STATUS "
        "AND T-MINUS ENGINE v2"
    )
    print("=" * 100)

    create_market_monitor_tables()

    run_id, started_at = start_monitor_run()

    checked = 0
    updated = 0
    exact_matches = 0
    misses = 0
    live_games = 0
    ended_games = 0
    resolved_markets = 0

    try:
        sources = load_current_market_sources()

        print(
            f"Current valid markets discovered: "
            f"{len(sources)}"
        )

        records: list[dict[str, Any]] = []

        for number, (
            market_id,
            source,
        ) in enumerate(
            sources.items(),
            start=1,
        ):
            checked += 1

            gamma_market = fetch_exact_gamma_market(
                market_id
            )

            if gamma_market is None:
                misses += 1

                print(
                    f"[{number}/{len(sources)}] "
                    f"MISS  "
                    f"{source['title'][:65]}"
                )

                time.sleep(
                    REQUEST_DELAY_SECONDS
                )

                continue

            returned_id = normalize_market_id(
                gamma_market.get("conditionId")
            )

            if returned_id != market_id:
                misses += 1
                continue

            exact_matches += 1

            record = parse_gamma_market(
                gamma_market,
                source,
            )

            previous = load_existing_metadata(
                market_id
            )

            save_market_metadata(record)

            ensure_tracked_market(
                record,
                clean_text(source.get("source"))
                or "AUTO",
            )

            if status_changed(
                previous,
                record,
            ):
                save_status_history(record)

            updated += 1
            records.append(record)

            if record["is_live"]:
                live_games += 1

            if record["is_ended"]:
                ended_games += 1

            if record["is_resolved"]:
                resolved_markets += 1

            print(
                f"[{number}/{len(sources)}] "
                f"OK    "
                f"{record['lifecycle_status']:<20}"
                f"{record['title'][:55]}"
            )

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

        finish_monitor_run(
            run_id=run_id,
            started_at=started_at,
            status="COMPLETED",
            markets_checked=checked,
            markets_updated=updated,
            live_games=live_games,
            ended_games=ended_games,
            resolved_markets=resolved_markets,
        )

        print()
        print("=" * 100)
        print("MARKET STATUS SUMMARY")
        print("=" * 100)

        print(
            f"Markets checked:          {checked}"
        )
        print(
            f"Exact Gamma matches:      {exact_matches}"
        )
        print(
            f"Lookup misses:            {misses}"
        )
        print(
            f"Metadata rows updated:    {updated}"
        )
        print(
            f"Confirmed live games:     {live_games}"
        )
        print(
            f"Confirmed ended games:    {ended_games}"
        )
        print(
            f"Resolved markets:         {resolved_markets}"
        )

        print("=" * 100)

        display_upcoming(records)

        print()
        print("=" * 100)
        print("MARKET STATUS ENGINE COMPLETE")
        print("=" * 100)

        print(
            "Only exact condition-ID matches were stored."
        )

        print(
            "Markets without confirmed gameStartTime "
            "remain ACTIVE_UNSCHEDULED."
        )

        print(
            "The next step is the Sports WebSocket "
            "listener for live scores and confirmed game status."
        )

        print("=" * 100)

    except Exception as error:
        finish_monitor_run(
            run_id=run_id,
            started_at=started_at,
            status="FAILED",
            markets_checked=checked,
            markets_updated=updated,
            live_games=live_games,
            ended_games=ended_games,
            resolved_markets=resolved_markets,
            error=error,
        )

        print()
        print(
            f"FAILED: {type(error).__name__}: "
            f"{error}"
        )

        raise


if __name__ == "__main__":
    main()