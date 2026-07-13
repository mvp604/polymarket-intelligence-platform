from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("database/polymarket.db")

MINIMUM_ALERT_SCORE = 65.0
HIGH_CONVICTION_SCORE = 75.0
ELITE_CONVICTION_SCORE = 85.0

VALUE_SURGE_PERCENT = 25.0
SIGNIFICANT_SCORE_CHANGE = 5.0
CHASE_PRICE_MOVE = 0.10


def connect_database() -> sqlite3.Connection:
    """Connect to the local SQLite database."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH.resolve()}. "
            "Run the scanners and conviction engine first."
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def safe_float(value: Any) -> float:
    """Convert a value to float without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    """Convert a value to integer without crashing."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def create_alerts_table() -> None:
    """Create persistent alert storage."""

    connection = connect_database()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_key TEXT NOT NULL UNIQUE,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                message TEXT NOT NULL,
                wallet_count INTEGER NOT NULL,
                previous_wallet_count INTEGER,
                combined_value REAL NOT NULL,
                previous_combined_value REAL,
                conviction_score REAL NOT NULL,
                previous_conviction_score REAL,
                observed_price_move REAL,
                source_scanned_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_alerts_created_at
            ON alerts(created_at)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_alerts_market
            ON alerts(market_id, outcome)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_alerts_severity
            ON alerts(severity)
            """
        )

        connection.commit()

    finally:
        connection.close()


def fetch_latest_two_snapshots() -> dict[
    tuple[str, str],
    list[dict[str, Any]],
]:
    """
    Return the newest two consensus-history snapshots for every
    market and outcome.
    """

    connection = connect_database()

    try:
        query = """
            SELECT
                id,
                market_id,
                title,
                outcome,
                wallet_count,
                combined_shares,
                combined_value,
                combined_pnl,
                conviction_score,
                conviction_grade,
                average_entry_price,
                average_current_price,
                observed_price_move,
                scanned_at
            FROM consensus_history
            ORDER BY
                market_id,
                LOWER(TRIM(outcome)),
                scanned_at DESC,
                id DESC
        """

        rows = connection.execute(query).fetchall()

    finally:
        connection.close()

    grouped: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = {}

    for row in rows:
        item = dict(row)

        market_id = str(item.get("market_id") or "").strip()
        outcome = str(item.get("outcome") or "").strip()
        normalized_outcome = outcome.casefold()

        if not market_id or not normalized_outcome:
            continue

        key = (market_id, normalized_outcome)

        if key not in grouped:
            grouped[key] = []

        if len(grouped[key]) < 2:
            grouped[key].append(item)

    return grouped


def determine_severity(
    alert_type: str,
    score: float,
) -> str:
    """Assign alert severity."""

    critical_types = {
        "ELITE_SIGNAL",
        "STRONG_WALLET_EXIT",
    }

    high_types = {
        "NEW_CONSENSUS",
        "CONVICTION_UPGRADE",
        "WALLET_JOINED",
        "VALUE_SURGE",
    }

    warning_types = {
        "SIGNAL_WEAKENING",
        "WALLET_EXITED",
        "CHASE_RISK",
    }

    if alert_type in critical_types:
        return "CRITICAL"

    if alert_type in high_types or score >= ELITE_CONVICTION_SCORE:
        return "HIGH"

    if alert_type in warning_types:
        return "WARNING"

    return "INFO"


def build_alert_key(
    alert_type: str,
    latest: dict[str, Any],
) -> str:
    """
    Create a stable deduplication key.

    The latest source snapshot ID is included so the same unchanged
    database snapshot cannot generate the same alert repeatedly.
    """

    raw_key = "|".join(
        [
            alert_type,
            str(latest.get("market_id") or ""),
            str(latest.get("outcome") or "").casefold(),
            str(latest.get("id") or ""),
        ]
    )

    return hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()


def percentage_change(
    current: float,
    previous: float,
) -> float:
    """Calculate percentage change safely."""

    if previous == 0:
        return 100.0 if current > 0 else 0.0

    return ((current - previous) / abs(previous)) * 100.0


def make_alert(
    alert_type: str,
    latest: dict[str, Any],
    previous: dict[str, Any] | None,
    message: str,
) -> dict[str, Any]:
    """Build one normalized alert dictionary."""

    score = safe_float(
        latest.get("conviction_score")
    )

    return {
        "alert_key": build_alert_key(
            alert_type,
            latest,
        ),
        "alert_type": alert_type,
        "severity": determine_severity(
            alert_type,
            score,
        ),
        "market_id": str(
            latest.get("market_id") or ""
        ),
        "title": str(
            latest.get("title") or "Unknown market"
        ),
        "outcome": str(
            latest.get("outcome") or "Unknown"
        ),
        "message": message,
        "wallet_count": safe_int(
            latest.get("wallet_count")
        ),
        "previous_wallet_count": (
            safe_int(previous.get("wallet_count"))
            if previous
            else None
        ),
        "combined_value": safe_float(
            latest.get("combined_value")
        ),
        "previous_combined_value": (
            safe_float(previous.get("combined_value"))
            if previous
            else None
        ),
        "conviction_score": score,
        "previous_conviction_score": (
            safe_float(previous.get("conviction_score"))
            if previous
            else None
        ),
        "observed_price_move": safe_float(
            latest.get("observed_price_move")
        ),
        "source_scanned_at": str(
            latest.get("scanned_at") or ""
        ),
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def detect_first_snapshot_alerts(
    latest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate alerts for a market's first stored consensus snapshot."""

    alerts: list[dict[str, Any]] = []

    score = safe_float(
        latest.get("conviction_score")
    )

    wallets = safe_int(
        latest.get("wallet_count")
    )

    value = safe_float(
        latest.get("combined_value")
    )

    price_move = safe_float(
        latest.get("observed_price_move")
    )

    if score >= MINIMUM_ALERT_SCORE:
        alerts.append(
            make_alert(
                alert_type="NEW_CONSENSUS",
                latest=latest,
                previous=None,
                message=(
                    f"New qualifying consensus detected with "
                    f"{wallets} agreeing wallets, "
                    f"${value:,.2f} in combined value and a "
                    f"{score:.1f}/100 conviction score."
                ),
            )
        )

    if score >= ELITE_CONVICTION_SCORE:
        alerts.append(
            make_alert(
                alert_type="ELITE_SIGNAL",
                latest=latest,
                previous=None,
                message=(
                    f"Signal entered elite territory on its first "
                    f"stored snapshot with a {score:.1f}/100 score."
                ),
            )
        )

    if abs(price_move) >= CHASE_PRICE_MOVE:
        alerts.append(
            make_alert(
                alert_type="CHASE_RISK",
                latest=latest,
                previous=None,
                message=(
                    f"Current price is already "
                    f"{price_move:+.3f} away from the observed "
                    f"average wallet entry. Avoid blindly chasing."
                ),
            )
        )

    return alerts


def detect_snapshot_changes(
    latest: dict[str, Any],
    previous: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare two snapshots and generate meaningful alerts."""

    alerts: list[dict[str, Any]] = []

    current_wallets = safe_int(
        latest.get("wallet_count")
    )

    previous_wallets = safe_int(
        previous.get("wallet_count")
    )

    current_score = safe_float(
        latest.get("conviction_score")
    )

    previous_score = safe_float(
        previous.get("conviction_score")
    )

    current_value = safe_float(
        latest.get("combined_value")
    )

    previous_value = safe_float(
        previous.get("combined_value")
    )

    price_move = safe_float(
        latest.get("observed_price_move")
    )

    score_change = current_score - previous_score

    value_change_percent = percentage_change(
        current=current_value,
        previous=previous_value,
    )

    if current_wallets > previous_wallets:
        joined = current_wallets - previous_wallets

        alerts.append(
            make_alert(
                alert_type="WALLET_JOINED",
                latest=latest,
                previous=previous,
                message=(
                    f"{joined} additional wallet"
                    f"{'s' if joined != 1 else ''} joined this "
                    f"consensus. Support increased from "
                    f"{previous_wallets} to {current_wallets} wallets."
                ),
            )
        )

    if current_wallets < previous_wallets:
        exited = previous_wallets - current_wallets

        alert_type = (
            "STRONG_WALLET_EXIT"
            if current_score >= HIGH_CONVICTION_SCORE
            else "WALLET_EXITED"
        )

        alerts.append(
            make_alert(
                alert_type=alert_type,
                latest=latest,
                previous=previous,
                message=(
                    f"{exited} wallet"
                    f"{'s' if exited != 1 else ''} left this "
                    f"consensus. Support declined from "
                    f"{previous_wallets} to {current_wallets} wallets."
                ),
            )
        )

    if (
        score_change >= SIGNIFICANT_SCORE_CHANGE
        and current_score >= MINIMUM_ALERT_SCORE
    ):
        alerts.append(
            make_alert(
                alert_type="CONVICTION_UPGRADE",
                latest=latest,
                previous=previous,
                message=(
                    f"Conviction increased by {score_change:.1f} "
                    f"points, from {previous_score:.1f} to "
                    f"{current_score:.1f}."
                ),
            )
        )

    if (
        previous_score < ELITE_CONVICTION_SCORE
        <= current_score
    ):
        alerts.append(
            make_alert(
                alert_type="ELITE_SIGNAL",
                latest=latest,
                previous=previous,
                message=(
                    f"Signal crossed into elite territory, rising "
                    f"from {previous_score:.1f} to "
                    f"{current_score:.1f}."
                ),
            )
        )

    if value_change_percent >= VALUE_SURGE_PERCENT:
        alerts.append(
            make_alert(
                alert_type="VALUE_SURGE",
                latest=latest,
                previous=previous,
                message=(
                    f"Combined smart-money value increased "
                    f"{value_change_percent:.1f}%, from "
                    f"${previous_value:,.2f} to "
                    f"${current_value:,.2f}."
                ),
            )
        )

    weakening = (
        score_change <= -SIGNIFICANT_SCORE_CHANGE
        or current_wallets < previous_wallets
        or value_change_percent <= -VALUE_SURGE_PERCENT
    )

    if weakening:
        alerts.append(
            make_alert(
                alert_type="SIGNAL_WEAKENING",
                latest=latest,
                previous=previous,
                message=(
                    f"Signal is weakening. Score change: "
                    f"{score_change:+.1f}; wallet change: "
                    f"{current_wallets - previous_wallets:+d}; "
                    f"value change: {value_change_percent:+.1f}%."
                ),
            )
        )

    if abs(price_move) >= CHASE_PRICE_MOVE:
        alerts.append(
            make_alert(
                alert_type="CHASE_RISK",
                latest=latest,
                previous=previous,
                message=(
                    f"Price is {price_move:+.3f} away from the "
                    f"observed average entry. Existing smart-money "
                    f"support may already be priced in."
                ),
            )
        )

    return alerts


def detect_alerts() -> list[dict[str, Any]]:
    """Detect alerts across all stored consensus markets."""

    grouped_snapshots = fetch_latest_two_snapshots()

    alerts: list[dict[str, Any]] = []

    for snapshots in grouped_snapshots.values():
        if not snapshots:
            continue

        latest = snapshots[0]

        if len(snapshots) == 1:
            alerts.extend(
                detect_first_snapshot_alerts(latest)
            )
            continue

        previous = snapshots[1]

        alerts.extend(
            detect_snapshot_changes(
                latest=latest,
                previous=previous,
            )
        )

    severity_order = {
        "CRITICAL": 4,
        "HIGH": 3,
        "WARNING": 2,
        "INFO": 1,
    }

    alerts.sort(
        key=lambda alert: (
            severity_order.get(
                alert["severity"],
                0,
            ),
            alert["conviction_score"],
            alert["combined_value"],
        ),
        reverse=True,
    )

    return alerts


def save_alerts(
    alerts: list[dict[str, Any]],
) -> tuple[int, int]:
    """
    Save alerts while preventing duplicates.

    Returns:
        Number of new alerts saved and duplicates skipped.
    """

    if not alerts:
        return 0, 0

    connection = connect_database()

    new_alerts = 0
    duplicates = 0

    try:
        for alert in alerts:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO alerts (
                    alert_key,
                    alert_type,
                    severity,
                    market_id,
                    title,
                    outcome,
                    message,
                    wallet_count,
                    previous_wallet_count,
                    combined_value,
                    previous_combined_value,
                    conviction_score,
                    previous_conviction_score,
                    observed_price_move,
                    source_scanned_at,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert["alert_key"],
                    alert["alert_type"],
                    alert["severity"],
                    alert["market_id"],
                    alert["title"],
                    alert["outcome"],
                    alert["message"],
                    alert["wallet_count"],
                    alert["previous_wallet_count"],
                    alert["combined_value"],
                    alert["previous_combined_value"],
                    alert["conviction_score"],
                    alert["previous_conviction_score"],
                    alert["observed_price_move"],
                    alert["source_scanned_at"],
                    alert["created_at"],
                ),
            )

            if cursor.rowcount == 1:
                new_alerts += 1
            else:
                duplicates += 1

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return new_alerts, duplicates


def display_alert(
    number: int,
    alert: dict[str, Any],
) -> None:
    """Display one alert."""

    print()
    print("=" * 96)
    print(
        f"{number}. [{alert['severity']}] "
        f"{alert['alert_type']}"
    )
    print("=" * 96)
    print(f"Market:             {alert['title']}")
    print(f"Outcome:            {alert['outcome']}")
    print(
        f"Agreeing wallets:   "
        f"{alert['wallet_count']}"
    )
    print(
        f"Combined value:     "
        f"${alert['combined_value']:,.2f}"
    )
    print(
        f"Conviction score:   "
        f"{alert['conviction_score']:.1f}/100"
    )
    print(
        f"Price move:         "
        f"{alert['observed_price_move']:+.3f}"
    )
    print()
    print(f"Reason: {alert['message']}")


def main() -> None:
    """Run the smart-money alert engine."""

    print()
    print("=" * 96)
    print("POLYMARKET SMART-MONEY ALERT ENGINE v1")
    print("=" * 96)

    create_alerts_table()

    alerts = detect_alerts()

    print(f"Alert conditions detected: {len(alerts)}")

    if not alerts:
        print()
        print("No meaningful alert conditions were detected.")
        return

    new_alerts, duplicates = save_alerts(alerts)

    print(f"New alerts stored:         {new_alerts}")
    print(f"Duplicate alerts skipped:  {duplicates}")

    for number, alert in enumerate(
        alerts,
        start=1,
    ):
        display_alert(number, alert)

    print()
    print("=" * 96)
    print("IMPORTANT")
    print("=" * 96)
    print(
        "Alerts identify changes that deserve research. "
        "They are not automatic trade recommendations."
    )
    print(
        "The alert engine relies on repeated wallet scans and "
        "conviction snapshots to detect changes over time."
    )
    print("=" * 96)


if __name__ == "__main__":
    main()