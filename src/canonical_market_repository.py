from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from data_access import DataAccess, DATABASE_PATH
except ImportError:
    from src.data_access import DataAccess, DATABASE_PATH


LOGGER = logging.getLogger(__name__)

CANONICAL_TABLE = "canonical_market_identities"
LEGACY_MARKET_TABLE = "gamma_markets"
LEGACY_EVENT_TABLE = "gamma_events"
POLYMARKET_EVENT_URL = "https://polymarket.com/event"


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_id(value: Any) -> str:
    return clean_text(value).lower()


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


def safe_bool_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(bool(value))
    return int(clean_text(value).lower() in {"1", "true", "yes", "y", "on"})


def parse_json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return None
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return value


def ensure_list(value: Any) -> list[Any]:
    parsed = parse_json_value(value)
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    return [parsed]


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def first_present(
    row: Mapping[str, Any],
    candidates: Sequence[str],
    default: Any = None,
) -> Any:
    for candidate in candidates:
        if candidate in row and row[candidate] not in (None, ""):
            return row[candidate]
    return default


@dataclass(slots=True)
class CanonicalMarket:
    condition_id: str
    canonical_market_id: str = ""
    gamma_market_id: str = ""
    event_id: str = ""
    title: str = ""
    question: str = ""
    outcome: str = ""
    category: str = ""
    market_slug: str = ""
    event_slug: str = ""
    polymarket_url: str = ""
    url_source: str = ""
    link_verified: int = 0
    active: int = 0
    closed: int = 0
    archived: int = 0
    restricted: int = 0
    tradable_identity: int = 0
    accepting_orders: int = 0
    yes_token_id: str = ""
    no_token_id: str = ""
    token_ids: list[Any] | None = None
    outcomes: list[Any] | None = None
    current_price: float | None = None
    liquidity: float = 0.0
    volume: float = 0.0
    open_interest: float = 0.0
    spread: float | None = None
    market_start_at: str | None = None
    market_end_at: str | None = None
    event_start_at: str | None = None
    event_end_at: str | None = None
    resolution_at: str | None = None
    source: str = "CANONICAL"
    exact_mapping: int = 1
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CanonicalMarketRepository:
    """
    Canonical-first market lookup service.

    Resolution order:
        1. canonical_market_identities by condition ID
        2. canonical aliases, when an alias table is present
        3. legacy gamma_markets by condition ID, when fallback is enabled

    The returned object uses the same field names expected by the existing
    opportunity ranking engine, allowing incremental modernization without
    changing its scoring logic.
    """

    CONDITION_COLUMNS = (
        "condition_id",
        "canonical_condition_id",
        "conditionId",
        "market_id",
    )

    def __init__(
        self,
        data_access: DataAccess | None = None,
        database_path: Path | str = DATABASE_PATH,
        *,
        allow_legacy_fallback: bool = True,
    ) -> None:
        self.data = data_access or DataAccess(database_path)
        self.database_path = Path(self.data.database_path)
        self.allow_legacy_fallback = allow_legacy_fallback
        self._columns_cache: dict[str, set[str]] = {}
        self._canonical_cache: dict[str, CanonicalMarket] | None = None
        self._legacy_cache: dict[str, CanonicalMarket] | None = None

    def table_exists(self, table_name: str) -> bool:
        return self.data.table_exists(table_name)

    def table_columns(self, table_name: str) -> set[str]:
        if table_name not in self._columns_cache:
            rows = self.data.fetch_all(
                f"PRAGMA table_info({quote_identifier(table_name)})"
            )
            self._columns_cache[table_name] = {
                clean_text(row.get("name")) for row in rows
            }
        return self._columns_cache[table_name]

    def first_existing_column(
        self,
        table_name: str,
        candidates: Sequence[str],
    ) -> str | None:
        columns = self.table_columns(table_name)
        return next(
            (candidate for candidate in candidates if candidate in columns),
            None,
        )

    def validate(self) -> None:
        if not self.table_exists(CANONICAL_TABLE):
            raise RuntimeError(
                f"Required table missing: {CANONICAL_TABLE}"
            )
        if not self.first_existing_column(
            CANONICAL_TABLE,
            self.CONDITION_COLUMNS,
        ):
            raise RuntimeError(
                f"{CANONICAL_TABLE} has no usable condition ID column."
            )

    def _build_url(
        self,
        row: Mapping[str, Any],
    ) -> tuple[str, str, int]:
        direct_url = clean_text(
            first_present(
                row,
                ("polymarket_url", "market_url", "url"),
            )
        )
        if direct_url:
            return direct_url, "CANONICAL_URL", 1

        event_slug = clean_text(
            first_present(row, ("event_slug", "eventSlug"))
        )
        if event_slug:
            return (
                f"{POLYMARKET_EVENT_URL}/{event_slug}",
                "EVENT_SLUG",
                1,
            )

        market_slug = clean_text(
            first_present(
                row,
                ("market_slug", "slug", "marketSlug"),
            )
        )
        if market_slug:
            return (
                f"{POLYMARKET_EVENT_URL}/{market_slug}",
                "MARKET_SLUG_EVENT_ROUTE",
                1,
            )

        return "", "MISSING", 0

    def _extract_current_price(
        self,
        row: Mapping[str, Any],
    ) -> float | None:
        direct = first_present(
            row,
            (
                "current_price",
                "last_price",
                "price",
                "best_ask",
            ),
        )
        if direct not in (None, ""):
            return safe_float(direct)

        prices = ensure_list(
            first_present(row, ("outcome_prices", "outcomePrices"))
        )
        if prices:
            return safe_float(prices[0])

        return None

    def _normalize_row(
        self,
        row: Mapping[str, Any],
        *,
        source: str,
        exact_mapping: int = 1,
    ) -> CanonicalMarket:
        condition_id = normalize_id(
            first_present(row, self.CONDITION_COLUMNS)
        )
        polymarket_url, url_source, link_verified = self._build_url(row)

        title = clean_text(
            first_present(row, ("title", "question", "name"))
        )
        question = clean_text(
            first_present(row, ("question", "title", "name"))
        )

        active = safe_bool_int(
            first_present(row, ("active", "is_active"), 0)
        )
        closed = safe_bool_int(
            first_present(row, ("closed", "is_closed"), 0)
        )
        archived = safe_bool_int(
            first_present(row, ("archived", "is_archived"), 0)
        )
        restricted = safe_bool_int(row.get("restricted"))

        tradable_raw = first_present(
            row,
            ("tradable_identity", "tradable", "is_tradable"),
        )
        tradable_identity = (
            safe_bool_int(tradable_raw)
            if tradable_raw not in (None, "")
            else int(active == 1 and closed == 0 and archived == 0)
        )

        accepting_orders_raw = first_present(
            row,
            ("accepting_orders", "acceptingOrders"),
        )
        accepting_orders = (
            safe_bool_int(accepting_orders_raw)
            if accepting_orders_raw not in (None, "")
            else tradable_identity
        )

        return CanonicalMarket(
            condition_id=condition_id,
            canonical_market_id=clean_text(
                first_present(
                    row,
                    (
                        "canonical_market_id",
                        "canonical_id",
                        "identity_id",
                    ),
                )
            ),
            gamma_market_id=clean_text(
                first_present(
                    row,
                    ("gamma_market_id", "gamma_id", "market_id", "id"),
                )
            ),
            event_id=clean_text(
                first_present(
                    row,
                    ("event_id", "gamma_event_id"),
                )
            ),
            title=title,
            question=question,
            outcome=clean_text(
                first_present(row, ("outcome", "selected_outcome"))
            ),
            category=clean_text(
                first_present(row, ("category", "market_category"))
            ),
            market_slug=clean_text(
                first_present(
                    row,
                    ("market_slug", "slug", "marketSlug"),
                )
            ),
            event_slug=clean_text(
                first_present(row, ("event_slug", "eventSlug"))
            ),
            polymarket_url=polymarket_url,
            url_source=url_source,
            link_verified=link_verified,
            active=active,
            closed=closed,
            archived=archived,
            restricted=restricted,
            tradable_identity=tradable_identity,
            accepting_orders=accepting_orders,
            yes_token_id=clean_text(
                first_present(row, ("yes_token_id", "yes_clob_token_id"))
            ),
            no_token_id=clean_text(
                first_present(row, ("no_token_id", "no_clob_token_id"))
            ),
            token_ids=ensure_list(
                first_present(row, ("token_ids", "clob_token_ids"))
            ),
            outcomes=ensure_list(row.get("outcomes")),
            current_price=self._extract_current_price(row),
            liquidity=safe_float(
                first_present(row, ("liquidity", "liquidity_num"))
            ),
            volume=safe_float(
                first_present(row, ("volume", "volume_num"))
            ),
            open_interest=safe_float(
                first_present(row, ("open_interest", "openInterest"))
            ),
            spread=(
                safe_float(row.get("spread"))
                if row.get("spread") not in (None, "")
                else None
            ),
            market_start_at=clean_text(
                first_present(
                    row,
                    (
                        "market_start_at",
                        "start_date",
                        "startDate",
                        "start_at",
                        "game_start_time",
                    ),
                )
            ) or None,
            market_end_at=clean_text(
                first_present(
                    row,
                    (
                        "market_end_at",
                        "end_date",
                        "endDate",
                        "end_at",
                    ),
                )
            ) or None,
            event_start_at=clean_text(
                first_present(row, ("event_start_at",))
            ) or None,
            event_end_at=clean_text(
                first_present(row, ("event_end_at",))
            ) or None,
            resolution_at=clean_text(
                first_present(
                    row,
                    (
                        "resolution_at",
                        "resolved_at",
                        "resolution_date",
                    ),
                )
            ) or None,
            source=source,
            exact_mapping=exact_mapping,
            metadata={
                "restricted": restricted,
                "tradable_identity": tradable_identity,
                "raw_source": source,
            },
        )

    def load_all_canonical(
        self,
        *,
        tradable_only: bool = False,
        force_reload: bool = False,
    ) -> dict[str, CanonicalMarket]:
        self.validate()

        if self._canonical_cache is not None and not force_reload:
            if tradable_only:
                return {
                    key: market
                    for key, market in self._canonical_cache.items()
                    if market.tradable_identity == 1
                }
            return dict(self._canonical_cache)

        rows = self.data.fetch_all(
            f"SELECT * FROM {quote_identifier(CANONICAL_TABLE)}"
        )

        markets: dict[str, CanonicalMarket] = {}
        for row in rows:
            market = self._normalize_row(
                row,
                source="CANONICAL",
                exact_mapping=1,
            )
            if market.condition_id:
                markets[market.condition_id] = market

        self._canonical_cache = markets

        if tradable_only:
            return {
                key: market
                for key, market in markets.items()
                if market.tradable_identity == 1
            }

        return dict(markets)

    def load_all_legacy(
        self,
        *,
        force_reload: bool = False,
    ) -> dict[str, CanonicalMarket]:
        if not self.allow_legacy_fallback:
            return {}
        if not self.table_exists(LEGACY_MARKET_TABLE):
            return {}

        if self._legacy_cache is not None and not force_reload:
            return dict(self._legacy_cache)

        rows = self.data.fetch_all(
            f"SELECT * FROM {quote_identifier(LEGACY_MARKET_TABLE)}"
        )

        markets: dict[str, CanonicalMarket] = {}
        for row in rows:
            market = self._normalize_row(
                row,
                source="LEGACY_GAMMA",
                exact_mapping=1,
            )
            if market.condition_id:
                markets[market.condition_id] = market

        self._legacy_cache = markets
        return dict(markets)

    def resolve(
        self,
        condition_id: str,
        *,
        include_legacy: bool | None = None,
    ) -> CanonicalMarket | None:
        normalized = normalize_id(condition_id)
        if not normalized:
            return None

        canonical = self.load_all_canonical()
        if normalized in canonical:
            return canonical[normalized]

        use_legacy = (
            self.allow_legacy_fallback
            if include_legacy is None
            else include_legacy
        )
        if use_legacy:
            return self.load_all_legacy().get(normalized)

        return None

    def resolve_many(
        self,
        condition_ids: Iterable[str],
        *,
        include_legacy: bool | None = None,
    ) -> dict[str, CanonicalMarket]:
        resolved: dict[str, CanonicalMarket] = {}
        for condition_id in condition_ids:
            normalized = normalize_id(condition_id)
            market = self.resolve(
                normalized,
                include_legacy=include_legacy,
            )
            if market:
                resolved[normalized] = market
        return resolved

    def lookup_dict(
        self,
        *,
        tradable_only: bool = False,
        include_legacy: bool = True,
    ) -> dict[str, dict[str, Any]]:
        canonical = self.load_all_canonical(
            tradable_only=tradable_only
        )
        combined: dict[str, CanonicalMarket] = dict(canonical)

        if include_legacy and self.allow_legacy_fallback:
            for condition_id, market in self.load_all_legacy().items():
                combined.setdefault(condition_id, market)

        return {
            condition_id: market.to_dict()
            for condition_id, market in combined.items()
        }

    def stats(self) -> dict[str, Any]:
        canonical = self.load_all_canonical()
        legacy = self.load_all_legacy()

        canonical_ids = set(canonical)
        legacy_ids = set(legacy)

        return {
            "database_path": str(self.database_path),
            "canonical_markets": len(canonical),
            "canonical_tradable": sum(
                market.tradable_identity == 1
                for market in canonical.values()
            ),
            "canonical_with_links": sum(
                market.link_verified == 1
                for market in canonical.values()
            ),
            "legacy_markets": len(legacy),
            "legacy_only_markets": len(legacy_ids - canonical_ids),
            "canonical_only_markets": len(canonical_ids - legacy_ids),
            "overlapping_markets": len(canonical_ids & legacy_ids),
        }

    def audit_condition_ids(
        self,
        condition_ids: Iterable[str],
    ) -> dict[str, Any]:
        canonical = self.load_all_canonical()
        legacy = self.load_all_legacy()

        normalized_ids = {
            normalize_id(condition_id)
            for condition_id in condition_ids
            if normalize_id(condition_id)
        }

        canonical_matches = normalized_ids & set(canonical)
        legacy_matches = normalized_ids & set(legacy)
        unresolved = normalized_ids - canonical_matches - legacy_matches

        return {
            "requested": len(normalized_ids),
            "canonical_matches": len(canonical_matches),
            "legacy_only_matches": len(
                legacy_matches - canonical_matches
            ),
            "unresolved": len(unresolved),
            "unresolved_condition_ids": sorted(unresolved),
        }


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Canonical-first Polymarket market repository."
    )
    parser.add_argument(
        "--condition-id",
        help="Resolve and print one condition ID.",
    )
    parser.add_argument(
        "--no-legacy",
        action="store_true",
        help="Disable fallback to gamma_markets.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print repository statistics.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    repository = CanonicalMarketRepository(
        allow_legacy_fallback=not args.no_legacy
    )

    if args.condition_id:
        market = repository.resolve(
            args.condition_id,
            include_legacy=not args.no_legacy,
        )
        if not market:
            raise SystemExit(
                f"No market found for condition ID: {args.condition_id}"
            )
        print(json.dumps(
            market.to_dict(),
            indent=2,
            ensure_ascii=False,
            default=str,
        ))
        return

    stats = repository.stats()
    print()
    print("=" * 96)
    print("CANONICAL MARKET REPOSITORY")
    print("=" * 96)
    for key, value in stats.items():
        print(f"{key:<32} {value}")
    print("=" * 96)


if __name__ == "__main__":
    main()