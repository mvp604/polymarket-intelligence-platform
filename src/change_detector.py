from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


EPSILON = 1e-9


@dataclass(slots=True)
class PositionSnapshot:
    """Normalized position values used by the scan-to-scan comparison."""

    key: str
    market_id: str
    title: str
    outcome: str
    shares: float
    average_price: float
    current_price: float
    current_value: float
    cash_pnl: float
    percent_pnl: float


@dataclass(slots=True)
class PositionChange:
    """Difference between two normalized position snapshots."""

    key: str
    title: str
    outcome: str
    previous: PositionSnapshot | None
    current: PositionSnapshot | None
    shares_change: float = 0.0
    value_change: float = 0.0
    cash_pnl_change: float = 0.0
    price_change: float = 0.0


@dataclass(slots=True)
class ChangeSummary:
    """Complete comparison returned to wallet_tracker."""

    opened: list[PositionChange] = field(default_factory=list)
    closed: list[PositionChange] = field(default_factory=list)
    increased: list[PositionChange] = field(default_factory=list)
    decreased: list[PositionChange] = field(default_factory=list)
    price_only: list[PositionChange] = field(default_factory=list)
    unchanged: list[PositionChange] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return (
            len(self.opened)
            + len(self.closed)
            + len(self.increased)
            + len(self.decreased)
            + len(self.price_only)
        )


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def _number(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(row: Any) -> Mapping[str, Any]:
    if isinstance(row, Mapping):
        return row

    keys = getattr(row, "keys", None)
    if callable(keys):
        return {key: row[key] for key in keys()}

    raise TypeError(
        "Position rows must be dictionaries, sqlite3.Row objects, "
        f"or another mapping type. Received: {type(row).__name__}"
    )


def _normalize(row: Any) -> PositionSnapshot:
    data = _mapping(row)

    market_id = _text(
        _value(
            data,
            "market_id",
            "marketId",
            "condition_id",
            "conditionId",
            "asset",
            "slug",
        )
    )
    title = _text(_value(data, "title", "question", default="Unknown market"))
    outcome = _text(
        _value(
            data,
            "outcome",
            "outcome_name",
            "recommended_outcome",
            default="Unknown",
        )
    )

    identity = market_id.lower() if market_id else title.lower()
    key = f"{identity}::{outcome.lower()}"

    return PositionSnapshot(
        key=key,
        market_id=market_id,
        title=title or "Unknown market",
        outcome=outcome or "Unknown",
        shares=_number(_value(data, "shares", "size")),
        average_price=_number(
            _value(data, "average_price", "avgPrice", "averagePrice")
        ),
        current_price=_number(
            _value(data, "current_price", "curPrice", "currentPrice")
        ),
        current_value=_number(
            _value(data, "current_value", "currentValue", "value")
        ),
        cash_pnl=_number(_value(data, "cash_pnl", "cashPnl", "pnl")),
        percent_pnl=_number(
            _value(data, "percent_pnl", "percentPnl", "roi")
        ),
    )


def _index_positions(rows: Iterable[Any]) -> dict[str, PositionSnapshot]:
    indexed: dict[str, PositionSnapshot] = {}

    for row in rows:
        position = _normalize(row)
        existing = indexed.get(position.key)

        if existing is None:
            indexed[position.key] = position
            continue

        combined_shares = existing.shares + position.shares
        combined_value = existing.current_value + position.current_value
        combined_pnl = existing.cash_pnl + position.cash_pnl

        if combined_shares > EPSILON:
            weighted_average_price = (
                (existing.average_price * existing.shares)
                + (position.average_price * position.shares)
            ) / combined_shares
        else:
            weighted_average_price = position.average_price

        indexed[position.key] = PositionSnapshot(
            key=position.key,
            market_id=position.market_id or existing.market_id,
            title=position.title or existing.title,
            outcome=position.outcome or existing.outcome,
            shares=combined_shares,
            average_price=weighted_average_price,
            current_price=position.current_price,
            current_value=combined_value,
            cash_pnl=combined_pnl,
            percent_pnl=position.percent_pnl,
        )

    return indexed


def _change(
    previous: PositionSnapshot | None,
    current: PositionSnapshot | None,
) -> PositionChange:
    reference = current or previous
    if reference is None:
        raise ValueError("A position change requires a previous or current row.")

    return PositionChange(
        key=reference.key,
        title=reference.title,
        outcome=reference.outcome,
        previous=previous,
        current=current,
        shares_change=(
            (current.shares if current else 0.0)
            - (previous.shares if previous else 0.0)
        ),
        value_change=(
            (current.current_value if current else 0.0)
            - (previous.current_value if previous else 0.0)
        ),
        cash_pnl_change=(
            (current.cash_pnl if current else 0.0)
            - (previous.cash_pnl if previous else 0.0)
        ),
        price_change=(
            (current.current_price if current else 0.0)
            - (previous.current_price if previous else 0.0)
        ),
    )


def compare_positions(
    *,
    previous_positions: Iterable[Any],
    current_positions: Iterable[Any],
) -> ChangeSummary:
    """Compare two stored wallet scans."""

    previous = _index_positions(previous_positions)
    current = _index_positions(current_positions)
    summary = ChangeSummary()

    for key in sorted(set(previous) | set(current)):
        before = previous.get(key)
        after = current.get(key)
        change = _change(before, after)

        if before is None:
            summary.opened.append(change)
        elif after is None:
            summary.closed.append(change)
        elif change.shares_change > EPSILON:
            summary.increased.append(change)
        elif change.shares_change < -EPSILON:
            summary.decreased.append(change)
        elif (
            abs(change.price_change) > EPSILON
            or abs(change.value_change) > EPSILON
            or abs(change.cash_pnl_change) > EPSILON
        ):
            summary.price_only.append(change)
        else:
            summary.unchanged.append(change)

    return summary


def _short_money(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.2f}"


def _short_number(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.2f}"


def _print_change(label: str, change: PositionChange) -> None:
    print(f"{label:<10} {change.title}")
    print(f"           Outcome: {change.outcome}")

    if change.previous is None and change.current is not None:
        print(
            f"           Shares:  {change.current.shares:,.2f} | "
            f"Value: ${change.current.current_value:,.2f} | "
            f"Price: {change.current.current_price:.4f}"
        )
        return

    if change.current is None and change.previous is not None:
        print(
            f"           Previous shares: {change.previous.shares:,.2f} | "
            f"Previous value: ${change.previous.current_value:,.2f}"
        )
        return

    print(
        f"           Shares Δ: {_short_number(change.shares_change)} | "
        f"Value Δ: {_short_money(change.value_change)} | "
        f"PnL Δ: {_short_money(change.cash_pnl_change)} | "
        f"Price Δ: {change.price_change:+.4f}"
    )


def display_changes(changes: ChangeSummary) -> None:
    """Print a concise comparison report."""

    print()
    print("=" * 76)
    print("CHANGE DETECTOR")
    print("=" * 76)
    print(f"New positions:       {len(changes.opened)}")
    print(f"Closed positions:    {len(changes.closed)}")
    print(f"Positions increased: {len(changes.increased)}")
    print(f"Positions decreased: {len(changes.decreased)}")
    print(f"Price/value changes: {len(changes.price_only)}")
    print(f"Unchanged positions: {len(changes.unchanged)}")
    print("=" * 76)

    if changes.total_changes == 0:
        print("No material position changes were detected.")
        print("=" * 76)
        return

    for label, rows in (
        ("OPENED", changes.opened),
        ("CLOSED", changes.closed),
        ("INCREASED", changes.increased),
        ("DECREASED", changes.decreased),
        ("UPDATED", changes.price_only),
    ):
        for change in rows:
            print()
            _print_change(label, change)

    print()
    print("=" * 76)


__all__ = [
    "ChangeSummary",
    "PositionChange",
    "PositionSnapshot",
    "compare_positions",
    "display_changes",
]