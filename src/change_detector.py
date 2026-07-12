from __future__ import annotations


def safe_number(value: object) -> float:
    """Convert a value to float without crashing."""

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def position_key(position: dict) -> str:
    """
    Create a unique key for a position.

    A market can contain more than one outcome, so the outcome must
    be included along with the market ID.
    """

    market_id = (
        position.get("market_id")
        or position.get("conditionId")
        or position.get("marketId")
        or position.get("slug")
        or position.get("asset")
        or position.get("title")
        or "unknown-market"
    )

    outcome = position.get("outcome") or "Unknown"

    return f"{market_id}|{outcome}"


def compare_positions(
    previous_positions: list[dict],
    current_positions: list[dict],
    minimum_share_change: float = 0.01,
) -> list[dict]:
    """
    Compare two wallet snapshots.

    Returns a list of detected changes.
    """

    previous_map = {
        position_key(position): position
        for position in previous_positions
    }

    current_map = {
        position_key(position): position
        for position in current_positions
    }

    changes: list[dict] = []

    # Detect new, increased, reduced and unchanged positions.
    for key, current in current_map.items():
        previous = previous_map.get(key)

        current_shares = safe_number(
            current.get("shares", current.get("size"))
        )

        if previous is None:
            changes.append(
                {
                    "change_type": "NEW",
                    "title": current.get("title") or "Unknown market",
                    "outcome": current.get("outcome") or "Unknown",
                    "old_shares": 0.0,
                    "new_shares": current_shares,
                    "share_change": current_shares,
                }
            )
            continue

        previous_shares = safe_number(
            previous.get("shares", previous.get("size"))
        )

        difference = current_shares - previous_shares

        if difference > minimum_share_change:
            change_type = "INCREASED"
        elif difference < -minimum_share_change:
            change_type = "REDUCED"
        else:
            change_type = "UNCHANGED"

        changes.append(
            {
                "change_type": change_type,
                "title": current.get("title") or "Unknown market",
                "outcome": current.get("outcome") or "Unknown",
                "old_shares": previous_shares,
                "new_shares": current_shares,
                "share_change": difference,
            }
        )

    # Detect positions that disappeared from the latest scan.
    for key, previous in previous_map.items():
        if key in current_map:
            continue

        previous_shares = safe_number(
            previous.get("shares", previous.get("size"))
        )

        changes.append(
            {
                "change_type": "CLOSED",
                "title": previous.get("title") or "Unknown market",
                "outcome": previous.get("outcome") or "Unknown",
                "old_shares": previous_shares,
                "new_shares": 0.0,
                "share_change": -previous_shares,
            }
        )

    return changes


def display_changes(changes: list[dict]) -> None:
    """Print meaningful wallet changes."""

    meaningful_changes = [
        change
        for change in changes
        if change["change_type"] != "UNCHANGED"
    ]

    print()
    print("=" * 76)
    print("WALLET POSITION CHANGES")
    print("=" * 76)

    if not meaningful_changes:
        print("No meaningful position changes were detected.")
        print("=" * 76)
        return

    for number, change in enumerate(meaningful_changes, start=1):
        change_type = change["change_type"]
        title = change["title"]
        outcome = change["outcome"]
        old_shares = change["old_shares"]
        new_shares = change["new_shares"]
        share_change = change["share_change"]

        print()
        print(f"{number}. {change_type}: {title}")
        print(f"   Outcome: {outcome}")
        print(f"   Previous shares: {old_shares:,.2f}")
        print(f"   Current shares:  {new_shares:,.2f}")
        print(f"   Share change:    {share_change:+,.2f}")

    print()
    print("=" * 76)
    print(f"Meaningful changes found: {len(meaningful_changes)}")
    print("=" * 76)