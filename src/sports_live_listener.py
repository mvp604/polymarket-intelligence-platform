from __future__ import annotations

import argparse
import json
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websocket

from market_monitor_database import create_market_monitor_tables


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

SPORTS_WEBSOCKET_URL = "wss://sports-api.polymarket.com/ws"

DATABASE_BUSY_TIMEOUT_MS = 30_000
INITIAL_RECONNECT_DELAY_SECONDS = 2
MAX_RECONNECT_DELAY_SECONDS = 60

STOP_REQUESTED = threading.Event()
ACTIVE_SOCKET: websocket.WebSocketApp | None = None
ACTIVE_SOCKET_LOCK = threading.Lock()


# =============================================================================
# BASIC HELPERS
# =============================================================================


def configure_utf8_output() -> None:
    """Prevent Windows terminal encoding crashes."""

    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except (AttributeError, OSError):
        pass

    try:
        sys.stderr.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except (AttributeError, OSError):
        pass


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC time as ISO text."""

    return utc_now().isoformat()


def safe_bool(value: Any) -> bool:
    """Convert common values into a Boolean."""

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    return str(value or "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def safe_float(value: Any) -> float:
    """Convert a value into a float safely."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value into an integer safely."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def clean_text(value: Any) -> str:
    """Return trimmed text."""

    return str(value or "").strip()


def normalize_text(value: Any) -> str:
    """Normalize text for comparison."""

    return clean_text(value).casefold()


def normalize_slug(value: Any) -> str:
    """Normalize an event slug."""

    return clean_text(value).strip("/").casefold()


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""

    seconds = max(int(seconds), 0)

    hours, remainder = divmod(
        seconds,
        3600,
    )

    minutes, seconds_left = divmod(
        remainder,
        60,
    )

    if hours:
        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds_left:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{seconds_left:02d}"
    )


# =============================================================================
# ACTIVE SOCKET CONTROL
# =============================================================================


def set_active_socket(
    socket_app: websocket.WebSocketApp | None,
) -> None:
    """Store the current active WebSocket safely."""

    global ACTIVE_SOCKET

    with ACTIVE_SOCKET_LOCK:
        ACTIVE_SOCKET = socket_app


def close_active_socket() -> None:
    """Close the active WebSocket immediately."""

    with ACTIVE_SOCKET_LOCK:
        socket_app = ACTIVE_SOCKET

    if socket_app is None:
        return

    try:
        socket_app.keep_running = False
    except Exception:
        pass

    try:
        socket_app.close()
    except Exception:
        pass

    try:
        if socket_app.sock is not None:
            socket_app.sock.close()
    except Exception:
        pass


def request_stop(
    reason: str,
) -> None:
    """Request shutdown and force-close the active socket."""

    if STOP_REQUESTED.is_set():
        return

    STOP_REQUESTED.set()

    print()
    print(reason)
    print(
        "Closing the active sports WebSocket..."
    )

    close_active_socket()


# =============================================================================
# DATABASE
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
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )
    connection.execute(
        "PRAGMA journal_mode = WAL"
    )
    connection.execute(
        f"PRAGMA busy_timeout = "
        f"{DATABASE_BUSY_TIMEOUT_MS}"
    )

    return connection


def load_matching_markets(
    slug: str,
) -> list[dict[str, Any]]:
    """Find tracked markets matching one event slug."""

    normalized_slug = normalize_slug(slug)

    if not normalized_slug:
        return []

    connection = connect_database()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM market_metadata
            WHERE LOWER(
                TRIM(
                    COALESCE(
                        sports_slug,
                        ''
                    )
                )
            ) = ?
               OR LOWER(
                    TRIM(
                        COALESCE(
                            event_slug,
                            ''
                        )
                    )
               ) = ?
               OR LOWER(
                    TRIM(
                        COALESCE(
                            market_slug,
                            ''
                        )
                    )
               ) = ?
            ORDER BY
                title,
                outcome
            """,
            (
                normalized_slug,
                normalized_slug,
                normalized_slug,
            ),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


def lifecycle_from_update(
    live: bool,
    ended: bool,
    previous_status: str,
) -> str:
    """Determine lifecycle state from a live update."""

    if ended:
        return "ENDED"

    if live:
        return "LIVE"

    normalized_previous = normalize_text(
        previous_status
    )

    if normalized_previous == "resolved":
        return "RESOLVED"

    if normalized_previous in {
        "closed",
        "ended",
    }:
        return previous_status

    return "PREGAME"


def update_market_live_state(
    previous: dict[str, Any],
    update: dict[str, Any],
) -> dict[str, Any]:
    """Apply one WebSocket update to one market."""

    live = safe_bool(
        update.get("live")
    )

    ended = safe_bool(
        update.get("ended")
    )

    now_iso = utc_now_iso()

    current = dict(previous)

    current.update(
        {
            "lifecycle_status": (
                lifecycle_from_update(
                    live=live,
                    ended=ended,
                    previous_status=clean_text(
                        previous.get(
                            "lifecycle_status"
                        )
                    ),
                )
            ),
            "is_pregame": int(
                not live
                and not ended
            ),
            "is_live": int(live),
            "is_ended": int(ended),
            "score": clean_text(
                update.get("score")
            ),
            "period": clean_text(
                update.get("period")
            ),
            "elapsed": clean_text(
                update.get("elapsed")
            ),
            "seconds_to_start": (
                0
                if live or ended
                else previous.get(
                    "seconds_to_start"
                )
            ),
            "source_updated_at": (
                clean_text(
                    update.get(
                        "last_update"
                    )
                )
                or now_iso
            ),
            "last_checked_at": now_iso,
            "updated_at": now_iso,
        }
    )

    connection = connect_database()

    try:
        connection.execute(
            """
            UPDATE market_metadata
            SET
                lifecycle_status = ?,
                is_pregame = ?,
                is_live = ?,
                is_ended = ?,
                score = ?,
                period = ?,
                elapsed = ?,
                seconds_to_start = ?,
                source_updated_at = ?,
                last_checked_at = ?,
                updated_at = ?
            WHERE market_id = ?
            """,
            (
                current[
                    "lifecycle_status"
                ],
                current["is_pregame"],
                current["is_live"],
                current["is_ended"],
                current["score"],
                current["period"],
                current["elapsed"],
                current[
                    "seconds_to_start"
                ],
                current[
                    "source_updated_at"
                ],
                current[
                    "last_checked_at"
                ],
                current["updated_at"],
                current["market_id"],
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return current


def status_changed(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> bool:
    """Check whether meaningful live fields changed."""

    fields = (
        "lifecycle_status",
        "is_live",
        "is_ended",
        "score",
        "period",
        "elapsed",
    )

    return any(
        str(
            previous.get(field)
            or ""
        )
        != str(
            current.get(field)
            or ""
        )
        for field in fields
    )


def save_status_history(
    record: dict[str, Any],
) -> None:
    """Store a meaningful lifecycle snapshot."""

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
                record[
                    "lifecycle_status"
                ],
                safe_int(
                    record.get(
                        "is_pregame"
                    )
                ),
                safe_int(
                    record.get("is_live")
                ),
                safe_int(
                    record.get("is_ended")
                ),
                safe_int(
                    record.get("is_closed")
                ),
                safe_int(
                    record.get(
                        "is_resolved"
                    )
                ),
                record.get("start_time"),
                record.get(
                    "game_start_time"
                ),
                clean_text(
                    record.get("score")
                ),
                clean_text(
                    record.get("period")
                ),
                clean_text(
                    record.get("elapsed")
                ),
                clean_text(
                    record.get(
                        "winning_outcome"
                    )
                ),
                clean_text(
                    record.get(
                        "resolution_status"
                    )
                ),
                record.get(
                    "seconds_to_start"
                ),
                safe_float(
                    record.get(
                        "current_price"
                    )
                ),
                record["updated_at"],
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =============================================================================
# ALERTS
# =============================================================================


def alert_exists(
    alert_key: str,
) -> bool:
    """Check whether an alert already exists."""

    connection = connect_database()

    try:
        row = connection.execute(
            """
            SELECT id
            FROM monitor_alerts
            WHERE alert_key = ?
            """,
            (alert_key,),
        ).fetchone()

        return row is not None

    finally:
        connection.close()


def create_monitor_alert(
    alert_key: str,
    alert_type: str,
    severity: str,
    market: dict[str, Any],
    message: str,
    source_time: str,
) -> bool:
    """Create one deduplicated monitor alert."""

    if alert_exists(alert_key):
        return False

    connection = connect_database()

    try:
        connection.execute(
            """
            INSERT INTO monitor_alerts (
                alert_key,
                alert_type,
                severity,
                market_id,
                wallet,
                title,
                outcome,
                message,
                lifecycle_status,
                seconds_to_start,
                wallet_count,
                conviction_score,
                capital_change,
                wallet_change,
                conviction_change,
                price_change,
                score,
                period,
                elapsed,
                source_time,
                created_at,
                acknowledged,
                delivered_dashboard,
                delivered_discord,
                delivered_email
            )
            VALUES (
                ?, ?, ?, ?, NULL, ?, ?, ?, ?,
                ?, NULL, NULL, NULL, NULL,
                NULL, NULL, ?, ?, ?, ?, ?,
                0, 0, 0, 0
            )
            """,
            (
                alert_key,
                alert_type,
                severity,
                market["market_id"],
                market["title"],
                market.get("outcome"),
                message,
                market[
                    "lifecycle_status"
                ],
                market.get(
                    "seconds_to_start"
                ),
                market.get("score"),
                market.get("period"),
                market.get("elapsed"),
                source_time,
                utc_now_iso(),
            ),
        )

        connection.commit()
        return True

    except sqlite3.IntegrityError:
        connection.rollback()
        return False

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def alert_fragment(
    value: Any,
) -> str:
    """Create a compact alert-key fragment."""

    return (
        normalize_text(value)
        .replace(" ", "_")
        .replace(":", "-")
        .replace("/", "-")
        or "none"
    )


def create_live_alerts(
    previous: dict[str, Any],
    current: dict[str, Any],
    update: dict[str, Any],
) -> int:
    """Create start, score, period and final alerts."""

    alerts_created = 0

    slug = normalize_slug(
        update.get("slug")
    )

    source_time = (
        clean_text(
            update.get("last_update")
        )
        or utc_now_iso()
    )

    previous_live = safe_bool(
        previous.get("is_live")
    )

    current_live = safe_bool(
        current.get("is_live")
    )

    previous_ended = safe_bool(
        previous.get("is_ended")
    )

    current_ended = safe_bool(
        current.get("is_ended")
    )

    previous_score = clean_text(
        previous.get("score")
    )

    current_score = clean_text(
        current.get("score")
    )

    previous_period = clean_text(
        previous.get("period")
    )

    current_period = clean_text(
        current.get("period")
    )

    if current_live and not previous_live:
        if create_monitor_alert(
            alert_key=(
                f"GAME_STARTED:"
                f"{current['market_id']}:"
                f"{slug}"
            ),
            alert_type="GAME_STARTED",
            severity="HIGH",
            market=current,
            message=(
                f"{current['title']} is now live."
            ),
            source_time=source_time,
        ):
            alerts_created += 1

    if (
        current_score
        and current_score
        != previous_score
    ):
        if create_monitor_alert(
            alert_key=(
                f"SCORE_CHANGE:"
                f"{current['market_id']}:"
                f"{alert_fragment(current_score)}"
            ),
            alert_type="SCORE_CHANGE",
            severity="INFO",
            market=current,
            message=(
                f"Score update for "
                f"{current['title']}: "
                f"{current_score}."
            ),
            source_time=source_time,
        ):
            alerts_created += 1

    if (
        current_period
        and current_period
        != previous_period
    ):
        if create_monitor_alert(
            alert_key=(
                f"PERIOD_CHANGE:"
                f"{current['market_id']}:"
                f"{alert_fragment(current_period)}"
            ),
            alert_type="PERIOD_CHANGE",
            severity="INFO",
            market=current,
            message=(
                f"{current['title']} moved to "
                f"{current_period}."
            ),
            source_time=source_time,
        ):
            alerts_created += 1

    if current_ended and not previous_ended:
        message = (
            f"{current['title']} has ended."
        )

        if current_score:
            message += (
                f" Final score: "
                f"{current_score}."
            )

        if create_monitor_alert(
            alert_key=(
                f"GAME_ENDED:"
                f"{current['market_id']}:"
                f"{slug}"
            ),
            alert_type="GAME_ENDED",
            severity="HIGH",
            market=current,
            message=message,
            source_time=source_time,
        ):
            alerts_created += 1

    return alerts_created


# =============================================================================
# MESSAGE PROCESSING
# =============================================================================


def decode_message(
    raw_message: Any,
) -> list[dict[str, Any]]:
    """Decode one WebSocket message."""

    if raw_message is None:
        return []

    if isinstance(raw_message, bytes):
        text = raw_message.decode(
            "utf-8",
            errors="replace",
        )
    else:
        text = str(raw_message)

    stripped = text.strip()

    if not stripped:
        return []

    if stripped.casefold() in {
        "ping",
        "pong",
    }:
        return []

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, list):
        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]

    if isinstance(payload, dict):
        data = payload.get("data")

        if isinstance(data, list):
            return [
                item
                for item in data
                if isinstance(item, dict)
            ]

        if isinstance(data, dict):
            return [data]

        return [payload]

    return []


def is_sports_update(
    update: dict[str, Any],
) -> bool:
    """Check whether a record resembles a sports update."""

    return bool(
        normalize_slug(
            update.get("slug")
        )
    ) and any(
        key in update
        for key in (
            "live",
            "ended",
            "score",
            "period",
            "elapsed",
        )
    )


class ListenerStatistics:
    """Track listener activity."""

    def __init__(self) -> None:
        self.messages_received = 0
        self.updates_received = 0
        self.matched_events = 0
        self.unmatched_events = 0
        self.market_rows_updated = 0
        self.history_rows_created = 0
        self.alerts_created = 0
        self.last_message_at: datetime | None = None

    def display(self) -> None:
        """Print final statistics."""

        print()
        print("=" * 92)
        print("SPORTS LISTENER STATISTICS")
        print("=" * 92)

        print(
            f"Messages received:       "
            f"{self.messages_received}"
        )
        print(
            f"Sports updates:          "
            f"{self.updates_received}"
        )
        print(
            f"Matched events:          "
            f"{self.matched_events}"
        )
        print(
            f"Unmatched events:        "
            f"{self.unmatched_events}"
        )
        print(
            f"Market rows updated:     "
            f"{self.market_rows_updated}"
        )
        print(
            f"History rows created:    "
            f"{self.history_rows_created}"
        )
        print(
            f"Alerts created:          "
            f"{self.alerts_created}"
        )
        print(
            f"Last message:            "
            f"{self.last_message_at.isoformat() if self.last_message_at else 'None'}"
        )

        print("=" * 92)


STATISTICS = ListenerStatistics()


def process_sports_update(
    update: dict[str, Any],
) -> None:
    """Process one sports update."""

    slug = normalize_slug(
        update.get("slug")
    )

    if not slug:
        return

    STATISTICS.updates_received += 1
    STATISTICS.last_message_at = utc_now()

    matching_markets = load_matching_markets(
        slug
    )

    if not matching_markets:
        STATISTICS.unmatched_events += 1

        print(
            f"[UNMATCHED] "
            f"{slug:<55} "
            f"score="
            f"{clean_text(update.get('score')) or '-'} "
            f"period="
            f"{clean_text(update.get('period')) or '-'}"
        )

        return

    STATISTICS.matched_events += 1

    rows_updated = 0
    event_alerts = 0

    for previous in matching_markets:
        current = update_market_live_state(
            previous,
            update,
        )

        rows_updated += 1
        STATISTICS.market_rows_updated += 1

        if status_changed(
            previous,
            current,
        ):
            save_status_history(
                current
            )

            STATISTICS.history_rows_created += 1

        created = create_live_alerts(
            previous,
            current,
            update,
        )

        event_alerts += created
        STATISTICS.alerts_created += created

    status = (
        "ENDED"
        if safe_bool(
            update.get("ended")
        )
        else (
            "LIVE"
            if safe_bool(
                update.get("live")
            )
            else "PREGAME"
        )
    )

    print(
        f"[MATCHED] "
        f"{status:<8} "
        f"{slug:<45} "
        f"markets={rows_updated:<3} "
        f"score="
        f"{clean_text(update.get('score')) or '-':<10} "
        f"period="
        f"{clean_text(update.get('period')) or '-':<8} "
        f"elapsed="
        f"{clean_text(update.get('elapsed')) or '-':<8} "
        f"alerts={event_alerts}"
    )


# =============================================================================
# WEBSOCKET CALLBACKS
# =============================================================================


def on_open(
    socket_app: websocket.WebSocketApp,
) -> None:
    """Handle successful connection."""

    del socket_app

    print()
    print("=" * 92)
    print(
        "CONNECTED TO POLYMARKET "
        "SPORTS WEBSOCKET"
    )
    print("=" * 92)
    print(
        f"Endpoint: "
        f"{SPORTS_WEBSOCKET_URL}"
    )
    print(
        f"Connected: "
        f"{utc_now_iso()}"
    )
    print(
        "Waiting for live sports messages..."
    )
    print("=" * 92)


def on_message(
    socket_app: websocket.WebSocketApp,
    raw_message: Any,
) -> None:
    """Handle one incoming message."""

    STATISTICS.messages_received += 1
    STATISTICS.last_message_at = utc_now()

    if isinstance(raw_message, bytes):
        text = raw_message.decode(
            "utf-8",
            errors="replace",
        ).strip()
    else:
        text = str(raw_message).strip()

    if text.casefold() == "ping":
        try:
            socket_app.send("pong")
        except Exception:
            pass

        return

    for update in decode_message(
        raw_message
    ):
        if is_sports_update(update):
            process_sports_update(update)


def on_error(
    socket_app: websocket.WebSocketApp,
    error: Any,
) -> None:
    """Handle WebSocket errors."""

    del socket_app

    if STOP_REQUESTED.is_set():
        return

    print()
    print(
        f"[WEBSOCKET ERROR] "
        f"{type(error).__name__}: "
        f"{error}"
    )


def on_close(
    socket_app: websocket.WebSocketApp,
    status_code: int | None,
    close_message: str | None,
) -> None:
    """Handle WebSocket closure."""

    del socket_app

    print()
    print(
        "[WEBSOCKET CLOSED] "
        f"code={status_code} "
        f"message={close_message or 'None'}"
    )


# =============================================================================
# SHUTDOWN
# =============================================================================


def signal_handler(
    signal_number: int,
    frame: Any,
) -> None:
    """Immediately stop the active listener."""

    del signal_number
    del frame

    request_stop(
        "Shutdown requested by Ctrl+C."
    )


def install_signal_handlers() -> None:
    """Install Ctrl+C and termination handlers."""

    signal.signal(
        signal.SIGINT,
        signal_handler,
    )

    if hasattr(signal, "SIGTERM"):
        signal.signal(
            signal.SIGTERM,
            signal_handler,
        )


# =============================================================================
# COMMAND-LINE ARGUMENTS
# =============================================================================


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Continuously receive Polymarket "
            "sports updates."
        )
    )

    parser.add_argument(
        "--seconds",
        type=int,
        default=0,
        help=(
            "Optional test duration. "
            "Use 0 to run continuously."
        ),
    )

    parser.add_argument(
        "--verbose-websocket",
        action="store_true",
        help=(
            "Enable websocket-client tracing."
        ),
    )

    return parser.parse_args()


# =============================================================================
# LISTENER
# =============================================================================


def run_listener(
    maximum_seconds: int,
    verbose_websocket: bool,
) -> None:
    """Run the listener and reconnect when necessary."""

    websocket.enableTrace(
        verbose_websocket
    )

    listener_started_at = utc_now()
    reconnect_delay = (
        INITIAL_RECONNECT_DELAY_SECONDS
    )

    timeout_timer: threading.Timer | None = None

    if maximum_seconds > 0:
        timeout_timer = threading.Timer(
            maximum_seconds,
            lambda: request_stop(
                "Configured listener test "
                "duration has completed."
            ),
        )

        timeout_timer.daemon = True
        timeout_timer.start()

    try:
        while not STOP_REQUESTED.is_set():
            socket_app = websocket.WebSocketApp(
                SPORTS_WEBSOCKET_URL,
                header=[
                    "User-Agent: "
                    "Polymarket-Intelligence-"
                    "Platform/1.0",
                ],
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )

            set_active_socket(
                socket_app
            )

            connection_started_at = utc_now()

            socket_thread = threading.Thread(
                target=socket_app.run_forever,
                kwargs={
                    "ping_interval": 0,
                    "ping_timeout": None,
                    "skip_utf8_validation": True,
                    "http_proxy_host": None,
                    "http_proxy_port": None,
                },
                daemon=True,
            )

            socket_thread.start()

            while (
                socket_thread.is_alive()
                and not STOP_REQUESTED.is_set()
            ):
                socket_thread.join(
                    timeout=0.25
                )

            if STOP_REQUESTED.is_set():
                close_active_socket()

                socket_thread.join(
                    timeout=3
                )

                break

            set_active_socket(None)

            connected_seconds = (
                utc_now()
                - connection_started_at
            ).total_seconds()

            if connected_seconds >= 60:
                reconnect_delay = (
                    INITIAL_RECONNECT_DELAY_SECONDS
                )
            else:
                reconnect_delay = min(
                    reconnect_delay * 2,
                    MAX_RECONNECT_DELAY_SECONDS,
                )

            print(
                f"Reconnecting in "
                f"{reconnect_delay} seconds..."
            )

            STOP_REQUESTED.wait(
                reconnect_delay
            )

    finally:
        if timeout_timer is not None:
            timeout_timer.cancel()

        close_active_socket()
        set_active_socket(None)


def main() -> None:
    """Start the live sports listener."""

    configure_utf8_output()
    install_signal_handlers()

    arguments = parse_arguments()

    print()
    print("=" * 92)
    print(
        "POLYMARKET LIVE SPORTS "
        "LISTENER v1.2"
    )
    print("=" * 92)

    print(
        f"Database: "
        f"{DATABASE_PATH}"
    )
    print(
        f"Endpoint: "
        f"{SPORTS_WEBSOCKET_URL}"
    )

    if arguments.seconds > 0:
        print(
            f"Test duration: "
            f"{arguments.seconds} seconds"
        )
    else:
        print(
            "Run mode: continuous until Ctrl+C"
        )

    print("=" * 92)

    create_market_monitor_tables()

    started_at = utc_now()

    run_listener(
        maximum_seconds=max(
            arguments.seconds,
            0,
        ),
        verbose_websocket=(
            arguments.verbose_websocket
        ),
    )

    elapsed_seconds = (
        utc_now()
        - started_at
    ).total_seconds()

    STATISTICS.display()

    print()
    print(
        "Live sports listener stopped after "
        f"{format_duration(elapsed_seconds)}."
    )


if __name__ == "__main__":
    main()