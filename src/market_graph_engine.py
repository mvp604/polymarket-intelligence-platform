from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.1"


SPORT_CATEGORIES = {
    "SOCCER",
    "BASEBALL",
    "BASKETBALL",
    "HOCKEY",
    "AMERICAN_FOOTBALL",
    "MMA",
    "TENNIS",
}

EVENT_MARKET_TYPES = (
    ("BOTH_TEAMS_TO_SCORE", ("both teams to score", "btts")),
    ("TEAM_TO_ADVANCE", ("team to advance", "to advance", "to qualify")),
    ("EXTRA_TIME", ("go to extra time", "extra time")),
    ("HALFTIME_RESULT", ("leading at halftime", "draw at halftime", "halftime")),
    ("TOTAL_CORNERS", ("total corners", "corners")),
    ("FIRST_HALF_TOTAL", ("1st half o/u", "first half o/u", "1h o/u")),
    ("TEAM_TOTAL", ("team total",)),
    ("TOTAL", ("o/u", "over/under", "total goals", "total runs", "total points")),
    ("SPREAD", ("spread", "handicap", "run line", "puck line")),
    ("MONEYLINE", ("moneyline", "team to win", "will win")),
    ("CORRECT_SCORE", ("correct score", "exact score")),
    ("CLEAN_SHEET", ("clean sheet",)),
    ("PLAYER_PROP", (
        "shots", "assists", "rebounds", "strikeouts", "home run",
        "passing yards", "rushing yards", "receiving yards",
        "aces", "double faults", "submission", "knockout",
    )),
    ("FIGHT_ROUNDS", ("rounds",)),
    ("GOES_DISTANCE", ("goes the distance",)),
)


@dataclass(frozen=True)
class SourceSchema:
    table: str
    condition_id: str
    title: str
    wallet: str | None
    outcome: str | None
    shares: str | None
    current_value: str | None
    capital_committed: str | None
    cash_pnl: str | None
    average_price: str | None
    current_price: str | None


@dataclass(frozen=True)
class EventIdentity:
    event_id: str
    event_key: str
    event_name: str
    category: str
    participant_a: str | None
    participant_b: str | None
    event_date: str | None
    confidence: float
    method: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str | None) -> str:
    text = (value or "").lower()
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("’", "'")
    text = re.sub(r"[^\w\s.+/'&:?-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_name(value: str | None) -> str | None:
    if not value:
        return None
    text = normalize_text(value)
    text = re.sub(r"\b(fc|cf|cd|sc|fk|bk|if|afc)\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def stable_hash(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()
    return row is not None


def table_columns(
    connection: sqlite3.Connection,
    table: str,
) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table)})"
        ).fetchall()
    }


def first_present(
    columns: set[str],
    candidates: Iterable[str],
) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def discover_source_schema(
    connection: sqlite3.Connection,
) -> SourceSchema:
    candidates = (
        "wallet_performance_markets",
        "positions",
        "normalized_positions",
    )

    for table in candidates:
        if not table_exists(connection, table):
            continue

        columns = table_columns(connection, table)

        condition_id = first_present(
            columns,
            ("condition_id", "market_id", "token_id"),
        )
        title = first_present(
            columns,
            ("title", "market_title", "question"),
        )

        if not condition_id or not title:
            continue

        return SourceSchema(
            table=table,
            condition_id=condition_id,
            title=title,
            wallet=first_present(
                columns,
                ("wallet", "proxy_wallet", "user"),
            ),
            outcome=first_present(
                columns,
                ("selected_outcome", "outcome", "position_outcome"),
            ),
            shares=first_present(
                columns,
                ("shares", "size", "position_size"),
            ),
            current_value=first_present(
                columns,
                ("current_value", "value", "position_value"),
            ),
            capital_committed=first_present(
                columns,
                ("capital_committed", "cost_basis", "initial_value", "amount_invested", "invested_value"),
            ),
            cash_pnl=first_present(
                columns,
                ("cash_pnl", "realized_pnl", "pnl"),
            ),
            average_price=first_present(
                columns,
                ("average_price", "avg_price", "entry_price"),
            ),
            current_price=first_present(
                columns,
                ("current_price", "price", "mark_price"),
            ),
        )

    raise RuntimeError(
        "Could not find a supported market-position source table. "
        "Expected wallet_performance_markets, positions, or normalized_positions."
    )


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA busy_timeout = 30000;")
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_events (
            event_id TEXT PRIMARY KEY,
            event_key TEXT NOT NULL UNIQUE,
            event_name TEXT NOT NULL,
            category TEXT NOT NULL,
            participant_a TEXT,
            participant_b TEXT,
            event_date TEXT,
            event_status TEXT NOT NULL DEFAULT 'UNKNOWN',
            market_count INTEGER NOT NULL DEFAULT 0,
            wallet_count INTEGER NOT NULL DEFAULT 0,
            total_exposure REAL NOT NULL DEFAULT 0,
            total_capital_committed REAL NOT NULL DEFAULT 0,
            classification_confidence REAL NOT NULL DEFAULT 0,
            classification_method TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_market_events_category
        ON market_events(category);

        CREATE INDEX IF NOT EXISTS idx_market_events_participants
        ON market_events(participant_a, participant_b);

        CREATE TABLE IF NOT EXISTS market_event_links (
            condition_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            market_title TEXT NOT NULL,
            category TEXT NOT NULL,
            market_type TEXT NOT NULL,
            market_subtype TEXT,
            line_value REAL,
            primary_subject TEXT,
            selected_outcome TEXT,
            link_confidence REAL NOT NULL,
            link_method TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES market_events(event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_market_event_links_event
        ON market_event_links(event_id);

        CREATE INDEX IF NOT EXISTS idx_market_event_links_type
        ON market_event_links(market_type);

        CREATE TABLE IF NOT EXISTS market_relationships (
            relationship_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            source_condition_id TEXT NOT NULL,
            target_condition_id TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            correlation_group TEXT NOT NULL,
            relationship_strength REAL NOT NULL,
            explanation TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES market_events(event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_market_relationships_event
        ON market_relationships(event_id);

        CREATE TABLE IF NOT EXISTS wallet_event_exposure (
            event_id TEXT NOT NULL,
            wallet TEXT NOT NULL,
            category TEXT NOT NULL,
            position_count INTEGER NOT NULL,
            market_type_count INTEGER NOT NULL,
            total_shares REAL NOT NULL,
            total_current_value REAL NOT NULL,
            total_capital_committed REAL NOT NULL DEFAULT 0,
            total_cash_pnl REAL NOT NULL,
            weighted_average_entry REAL,
            weighted_average_current_price REAL,
            dominant_outcome TEXT,
            thesis_consistency REAL NOT NULL,
            concentration_score REAL NOT NULL,
            event_conviction_score REAL NOT NULL,
            expertise_influence_weight REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(event_id, wallet),
            FOREIGN KEY(event_id) REFERENCES market_events(event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_wallet_event_exposure_wallet
        ON wallet_event_exposure(wallet);

        CREATE INDEX IF NOT EXISTS idx_wallet_event_exposure_conviction
        ON wallet_event_exposure(event_conviction_score DESC);

        CREATE TABLE IF NOT EXISTS market_graph_runs (
            graph_run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            source_table TEXT NOT NULL,
            source_rows INTEGER NOT NULL,
            events_created INTEGER NOT NULL,
            markets_linked INTEGER NOT NULL,
            relationships_created INTEGER NOT NULL,
            wallet_event_profiles INTEGER NOT NULL,
            unlinked_markets INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    # Safe migrations for databases created by Market Graph Engine v1.0.
    existing_event_columns = table_columns(connection, "market_events")
    if "total_capital_committed" not in existing_event_columns:
        connection.execute(
            "ALTER TABLE market_events ADD COLUMN total_capital_committed REAL NOT NULL DEFAULT 0"
        )

    existing_exposure_columns = table_columns(connection, "wallet_event_exposure")
    if "total_capital_committed" not in existing_exposure_columns:
        connection.execute(
            "ALTER TABLE wallet_event_exposure ADD COLUMN total_capital_committed REAL NOT NULL DEFAULT 0"
        )


def category_for_market(
    connection: sqlite3.Connection,
    condition_id: str,
) -> tuple[str, float]:
    if not table_exists(connection, "market_category_dictionary"):
        return "OTHER", 0.35

    row = connection.execute(
        """
        SELECT category, classification_confidence
        FROM market_category_dictionary
        WHERE condition_id = ?
        """,
        (condition_id,),
    ).fetchone()

    if row is None:
        return "OTHER", 0.35

    return (
        str(row["category"] or "OTHER"),
        float(row["classification_confidence"] or 0.35),
    )


def extract_date(text: str) -> str | None:
    patterns = (
        r"\b(20\d{2})-(\d{2})-(\d{2})\b",
        r"\b(\d{4})/(\d{2})/(\d{2})\b",
    )

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"

    return None


def strip_market_suffix(title: str) -> str:
    text = title.strip()

    suffix_patterns = (
        r":\s*o/u\s+\d+(?:\.\d+)?(?:\s+total\s+\w+)?$",
        r":\s*1st half o/u\s+\d+(?:\.\d+)?$",
        r":\s*first half o/u\s+\d+(?:\.\d+)?$",
        r":\s*both teams to score.*$",
        r":\s*team to advance.*$",
        r":\s*team to win.*$",
        r":\s*will the match go to extra time.*$",
        r":\s*draw at halftime.*$",
        r":\s*.+ leading at halftime.*$",
        r":\s*correct score.*$",
        r":\s*exact score.*$",
        r":\s*spread.*$",
        r":\s*moneyline.*$",
        r":\s*.+ o/u \d+(?:\.\d+)?$",
    )

    for pattern in suffix_patterns:
        updated = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if updated != text:
            return updated

    return text


def extract_matchup(title: str) -> tuple[str | None, str | None]:
    base = strip_market_suffix(title)
    normalized = normalize_text(base)

    for separator in (" vs. ", " vs ", " v. ", " v "):
        if separator in normalized:
            left, right = normalized.split(separator, 1)
            left = left.strip(" :-")
            right = right.strip(" :-")
            if left and right:
                return left, right

    return None, None


def event_identity(
    title: str,
    category: str,
    category_confidence: float,
) -> EventIdentity:
    participant_a, participant_b = extract_matchup(title)
    event_date = extract_date(title)

    if participant_a and participant_b:
        a = normalized_name(participant_a) or participant_a
        b = normalized_name(participant_b) or participant_b

        ordered = sorted((a, b))
        key_parts = [
            category,
            ordered[0],
            ordered[1],
            event_date or "undated",
        ]
        event_key = "|".join(key_parts)
        event_name = f"{participant_a.title()} vs. {participant_b.title()}"

        return EventIdentity(
            event_id=stable_hash("event", event_key),
            event_key=event_key,
            event_name=event_name,
            category=category,
            participant_a=participant_a.title(),
            participant_b=participant_b.title(),
            event_date=event_date,
            confidence=max(0.78, category_confidence),
            method="matchup_participants",
        )

    base = strip_market_suffix(title)
    normalized_base = normalize_text(base)

    # Generic markets such as "O/U 2.5 Rounds" cannot safely be merged
    # together without fighter/event metadata. Keep them isolated.
    if re.fullmatch(
        r"o/u \d+(?:\.\d+)? rounds",
        normalized_base,
    ):
        event_key = f"{category}|isolated|{normalize_text(title)}"
        return EventIdentity(
            event_id=stable_hash("event", event_key),
            event_key=event_key,
            event_name=title.strip(),
            category=category,
            participant_a=None,
            participant_b=None,
            event_date=event_date,
            confidence=0.40,
            method="isolated_generic_market",
        )

    event_key = "|".join(
        (
            category,
            normalized_base or normalize_text(title),
            event_date or "undated",
        )
    )

    return EventIdentity(
        event_id=stable_hash("event", event_key),
        event_key=event_key,
        event_name=base.strip() or title.strip(),
        category=category,
        participant_a=None,
        participant_b=None,
        event_date=event_date,
        confidence=max(0.45, category_confidence * 0.75),
        method="normalized_title_family",
    )


def detect_market_type(title: str) -> tuple[str, str | None]:
    text = normalize_text(title)

    for market_type, phrases in EVENT_MARKET_TYPES:
        for phrase in phrases:
            if phrase in text:
                subtype = phrase.upper().replace(" ", "_")
                return market_type, subtype

    if " vs " in text or " vs. " in text:
        return "MATCH_WINNER", None

    return "OTHER", None


def extract_line_value(title: str) -> float | None:
    text = normalize_text(title)
    patterns = (
        r"\bo/u\s+(-?\d+(?:\.\d+)?)",
        r"\b(?:over|under)\s+(-?\d+(?:\.\d+)?)",
        r"\bspread\s+(-?\d+(?:\.\d+)?)",
    )

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None

    return None


def primary_subject(
    title: str,
    participant_a: str | None,
    participant_b: str | None,
) -> str | None:
    text = normalize_text(title)

    for participant in (participant_a, participant_b):
        if participant and normalize_text(participant) in text:
            if any(
                phrase in text
                for phrase in (
                    "team to win",
                    "team to advance",
                    "leading at halftime",
                    "o/u",
                )
            ):
                return participant

    return None


def numeric_value(row: sqlite3.Row, column: str | None) -> float:
    if not column:
        return 0.0

    value = row[column]
    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def position_capital_committed(row: sqlite3.Row) -> tuple[float, str]:
    """Return historical capital committed without confusing it with current value.

    Resolved positions often have current_value = 0. Their original cost basis is
    still recoverable from an explicit cost-basis field or shares * average_price.
    """
    explicit = numeric_value(row, "capital_committed")
    if explicit > 0:
        return explicit, "explicit_cost_basis"

    shares = numeric_value(row, "shares")
    average_price = numeric_value(row, "average_price")
    if shares > 0 and average_price > 0:
        return shares * average_price, "shares_x_average_price"

    current_value = numeric_value(row, "current_value")
    if current_value > 0:
        return current_value, "current_value_fallback"

    return 0.0, "unavailable"


def load_source_rows(
    connection: sqlite3.Connection,
    schema: SourceSchema,
) -> list[sqlite3.Row]:
    selected_columns = [
        f"{quote_identifier(schema.condition_id)} AS condition_id",
        f"{quote_identifier(schema.title)} AS title",
    ]

    optional_fields = {
        "wallet": schema.wallet,
        "selected_outcome": schema.outcome,
        "shares": schema.shares,
        "current_value": schema.current_value,
        "capital_committed": schema.capital_committed,
        "cash_pnl": schema.cash_pnl,
        "average_price": schema.average_price,
        "current_price": schema.current_price,
    }

    for alias, column in optional_fields.items():
        if column:
            selected_columns.append(
                f"{quote_identifier(column)} AS {quote_identifier(alias)}"
            )
        else:
            selected_columns.append(f"NULL AS {quote_identifier(alias)}")

    query = f"""
        SELECT {", ".join(selected_columns)}
        FROM {quote_identifier(schema.table)}
        WHERE {quote_identifier(schema.condition_id)} IS NOT NULL
          AND TRIM(CAST({quote_identifier(schema.condition_id)} AS TEXT)) <> ''
          AND {quote_identifier(schema.title)} IS NOT NULL
          AND TRIM(CAST({quote_identifier(schema.title)} AS TEXT)) <> ''
    """

    return connection.execute(query).fetchall()


def expertise_weight(
    connection: sqlite3.Connection,
    wallet: str,
    category: str,
) -> float:
    if not table_exists(connection, "wallet_market_expertise"):
        return 0.0

    columns = table_columns(connection, "wallet_market_expertise")
    required = {
        "wallet",
        "category",
        "expertise_influence_weight",
    }
    if not required.issubset(columns):
        return 0.0

    row = connection.execute(
        """
        SELECT expertise_influence_weight
        FROM wallet_market_expertise
        WHERE wallet = ? AND category = ?
        """,
        (wallet, category),
    ).fetchone()

    if row is None:
        return 0.0

    return max(0.0, min(1.0, float(row[0] or 0.0)))


def relationship_profile(
    source_type: str,
    target_type: str,
) -> tuple[str, str, float, str]:
    types = {source_type, target_type}

    if len(types) == 1:
        return (
            "SAME_MARKET_FAMILY",
            source_type,
            0.90,
            "Markets share the same event and market type.",
        )

    if types <= {"MONEYLINE", "MATCH_WINNER", "TEAM_TO_ADVANCE"}:
        return (
            "DIRECTIONALLY_RELATED",
            "EVENT_RESULT",
            0.88,
            "Result and advancement markets express closely related event outcomes.",
        )

    if types <= {"TOTAL", "FIRST_HALF_TOTAL", "TEAM_TOTAL"}:
        return (
            "TOTALS_FAMILY",
            "TOTALS",
            0.75,
            "Markets express related scoring or production totals.",
        )

    if "CORRECT_SCORE" in types and (
        "TOTAL" in types or "BOTH_TEAMS_TO_SCORE" in types
    ):
        return (
            "STRUCTURALLY_RELATED",
            "SCORE_NARRATIVE",
            0.70,
            "Correct-score and scoring markets encode related match narratives.",
        )

    if "TOTAL_CORNERS" in types:
        return (
            "SAME_EVENT_LOW_CORRELATION",
            "EVENT_ACTIVITY",
            0.25,
            "Markets share the event but corners generally represent a separate activity dimension.",
        )

    if "PLAYER_PROP" in types:
        return (
            "SAME_EVENT_PLAYER_LINK",
            "PLAYER_EVENT",
            0.35,
            "Player and event markets share context but are not necessarily directionally aligned.",
        )

    return (
        "SAME_EVENT",
        "EVENT",
        0.20,
        "Markets belong to the same real-world event.",
    )


def thesis_consistency(outcomes: list[str]) -> tuple[str | None, float]:
    cleaned = [
        normalize_text(outcome)
        for outcome in outcomes
        if normalize_text(outcome)
    ]

    if not cleaned:
        return None, 0.0

    counts = Counter(cleaned)
    dominant, dominant_count = counts.most_common(1)[0]
    return dominant, dominant_count / len(cleaned)


def conviction_score(
    position_count: int,
    market_type_count: int,
    total_value: float,
    consistency: float,
    expertise: float,
) -> tuple[float, float]:
    position_component = min(1.0, position_count / 6.0)
    diversity_component = min(1.0, market_type_count / 4.0)
    value_component = min(1.0, (max(total_value, 0.0) ** 0.5) / 100.0)
    consistency_component = max(0.0, min(1.0, consistency))
    expertise_component = max(0.0, min(1.0, expertise))

    concentration = (
        0.55 * position_component
        + 0.45 * value_component
    )

    conviction = 100.0 * (
        0.22 * position_component
        + 0.18 * diversity_component
        + 0.18 * value_component
        + 0.22 * consistency_component
        + 0.20 * expertise_component
    )

    return round(concentration * 100.0, 2), round(conviction, 2)


def run() -> None:
    timestamp = utc_now()
    run_id = (
        "market_graph_run:"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )

    connection = connect_database()

    try:
        ensure_schema(connection)
        source_schema = discover_source_schema(connection)
        rows = load_source_rows(connection, source_schema)

        if not rows:
            raise RuntimeError(
                f"No usable rows found in {source_schema.table}."
            )

        event_payloads: dict[str, dict[str, Any]] = {}
        market_links: dict[str, dict[str, Any]] = {}
        event_markets: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        wallet_event_rows: defaultdict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = defaultdict(list)

        for row in rows:
            condition_id = str(row["condition_id"])
            title = str(row["title"])
            wallet = str(row["wallet"]) if row["wallet"] else None
            outcome = (
                str(row["selected_outcome"])
                if row["selected_outcome"] is not None
                else ""
            )

            category, category_confidence = category_for_market(
                connection,
                condition_id,
            )
            identity = event_identity(
                title,
                category,
                category_confidence,
            )
            market_type, market_subtype = detect_market_type(title)
            line_value = extract_line_value(title)
            subject = primary_subject(
                title,
                identity.participant_a,
                identity.participant_b,
            )

            event_payloads[identity.event_id] = {
                "event_id": identity.event_id,
                "event_key": identity.event_key,
                "event_name": identity.event_name,
                "category": identity.category,
                "participant_a": identity.participant_a,
                "participant_b": identity.participant_b,
                "event_date": identity.event_date,
                "classification_confidence": identity.confidence,
                "classification_method": identity.method,
            }

            link = {
                "condition_id": condition_id,
                "event_id": identity.event_id,
                "market_title": title,
                "category": category,
                "market_type": market_type,
                "market_subtype": market_subtype,
                "line_value": line_value,
                "primary_subject": subject,
                "selected_outcome": outcome or None,
                "link_confidence": identity.confidence,
                "link_method": identity.method,
            }
            market_links[condition_id] = link
            event_markets[identity.event_id].append(link)

            if wallet:
                wallet_event_rows[(identity.event_id, wallet)].append(
                    {
                        **link,
                        "wallet": wallet,
                        "shares": numeric_value(row, "shares"),
                        "current_value": numeric_value(row, "current_value"),
                        "capital_committed": position_capital_committed(row)[0],
                        "capital_method": position_capital_committed(row)[1],
                        "cash_pnl": numeric_value(row, "cash_pnl"),
                        "average_price": (
                            numeric_value(row, "average_price")
                            if row["average_price"] is not None
                            else None
                        ),
                        "current_price": (
                            numeric_value(row, "current_price")
                            if row["current_price"] is not None
                            else None
                        ),
                    }
                )

        with connection:
            connection.execute("DELETE FROM market_relationships")
            connection.execute("DELETE FROM wallet_event_exposure")
            connection.execute("DELETE FROM market_event_links")
            connection.execute("DELETE FROM market_events")

            for payload in event_payloads.values():
                related_markets = event_markets[payload["event_id"]]
                wallets = {
                    str(row["wallet"])
                    for key, rows_for_wallet in wallet_event_rows.items()
                    if key[0] == payload["event_id"]
                    for row in rows_for_wallet
                }
                total_exposure = sum(
                    row["current_value"]
                    for key, rows_for_wallet in wallet_event_rows.items()
                    if key[0] == payload["event_id"]
                    for row in rows_for_wallet
                )
                total_capital_committed = sum(
                    row["capital_committed"]
                    for key, rows_for_wallet in wallet_event_rows.items()
                    if key[0] == payload["event_id"]
                    for row in rows_for_wallet
                )

                connection.execute(
                    """
                    INSERT INTO market_events (
                        event_id,
                        event_key,
                        event_name,
                        category,
                        participant_a,
                        participant_b,
                        event_date,
                        event_status,
                        market_count,
                        wallet_count,
                        total_exposure,
                        total_capital_committed,
                        classification_confidence,
                        classification_method,
                        engine_version,
                        first_seen_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'UNKNOWN', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["event_id"],
                        payload["event_key"],
                        payload["event_name"],
                        payload["category"],
                        payload["participant_a"],
                        payload["participant_b"],
                        payload["event_date"],
                        len({row["condition_id"] for row in related_markets}),
                        len(wallets),
                        total_exposure,
                        total_capital_committed,
                        payload["classification_confidence"],
                        payload["classification_method"],
                        ENGINE_VERSION,
                        timestamp,
                        timestamp,
                    ),
                )

            for link in market_links.values():
                connection.execute(
                    """
                    INSERT INTO market_event_links (
                        condition_id,
                        event_id,
                        market_title,
                        category,
                        market_type,
                        market_subtype,
                        line_value,
                        primary_subject,
                        selected_outcome,
                        link_confidence,
                        link_method,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        link["condition_id"],
                        link["event_id"],
                        link["market_title"],
                        link["category"],
                        link["market_type"],
                        link["market_subtype"],
                        link["line_value"],
                        link["primary_subject"],
                        link["selected_outcome"],
                        link["link_confidence"],
                        link["link_method"],
                        timestamp,
                        timestamp,
                    ),
                )

            relationship_count = 0
            for event_id, links in event_markets.items():
                unique_links = list(
                    {
                        link["condition_id"]: link
                        for link in links
                    }.values()
                )

                for source_index, source in enumerate(unique_links):
                    for target in unique_links[source_index + 1:]:
                        (
                            relationship_type,
                            correlation_group,
                            strength,
                            explanation,
                        ) = relationship_profile(
                            source["market_type"],
                            target["market_type"],
                        )

                        relationship_key = "|".join(
                            sorted(
                                (
                                    source["condition_id"],
                                    target["condition_id"],
                                )
                            )
                        )
                        relationship_id = stable_hash(
                            "relationship",
                            f"{event_id}|{relationship_key}",
                        )

                        connection.execute(
                            """
                            INSERT INTO market_relationships (
                                relationship_id,
                                event_id,
                                source_condition_id,
                                target_condition_id,
                                relationship_type,
                                correlation_group,
                                relationship_strength,
                                explanation,
                                created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                relationship_id,
                                event_id,
                                source["condition_id"],
                                target["condition_id"],
                                relationship_type,
                                correlation_group,
                                strength,
                                explanation,
                                timestamp,
                            ),
                        )
                        relationship_count += 1

            for (event_id, wallet), positions in wallet_event_rows.items():
                category = str(positions[0]["category"])
                position_count = len(positions)
                market_types = {
                    str(position["market_type"])
                    for position in positions
                }
                total_shares = sum(
                    float(position["shares"])
                    for position in positions
                )
                total_current_value = sum(
                    float(position["current_value"])
                    for position in positions
                )
                total_capital_committed = sum(
                    float(position["capital_committed"])
                    for position in positions
                )
                total_cash_pnl = sum(
                    float(position["cash_pnl"])
                    for position in positions
                )

                price_weights = [
                    max(float(position["capital_committed"]), 0.0)
                    or max(float(position["current_value"]), 0.0)
                    or max(float(position["shares"]), 0.0)
                    or 1.0
                    for position in positions
                ]

                entry_pairs = [
                    (position["average_price"], weight)
                    for position, weight in zip(positions, price_weights)
                    if position["average_price"] is not None
                ]
                current_pairs = [
                    (position["current_price"], weight)
                    for position, weight in zip(positions, price_weights)
                    if position["current_price"] is not None
                ]

                weighted_average_entry = (
                    sum(float(value) * weight for value, weight in entry_pairs)
                    / sum(weight for _, weight in entry_pairs)
                    if entry_pairs
                    else None
                )
                weighted_average_current_price = (
                    sum(float(value) * weight for value, weight in current_pairs)
                    / sum(weight for _, weight in current_pairs)
                    if current_pairs
                    else None
                )

                dominant_outcome, consistency = thesis_consistency(
                    [
                        str(position["selected_outcome"] or "")
                        for position in positions
                    ]
                )
                expertise = expertise_weight(
                    connection,
                    wallet,
                    category,
                )
                concentration, conviction = conviction_score(
                    position_count=position_count,
                    market_type_count=len(market_types),
                    total_value=total_capital_committed or total_current_value,
                    consistency=consistency,
                    expertise=expertise,
                )

                connection.execute(
                    """
                    INSERT INTO wallet_event_exposure (
                        event_id,
                        wallet,
                        category,
                        position_count,
                        market_type_count,
                        total_shares,
                        total_current_value,
                        total_capital_committed,
                        total_cash_pnl,
                        weighted_average_entry,
                        weighted_average_current_price,
                        dominant_outcome,
                        thesis_consistency,
                        concentration_score,
                        event_conviction_score,
                        expertise_influence_weight,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        wallet,
                        category,
                        position_count,
                        len(market_types),
                        total_shares,
                        total_current_value,
                        total_capital_committed,
                        total_cash_pnl,
                        weighted_average_entry,
                        weighted_average_current_price,
                        dominant_outcome,
                        consistency,
                        concentration,
                        conviction,
                        expertise,
                        timestamp,
                    ),
                )

            unlinked_markets = sum(
                1
                for link in market_links.values()
                if link["link_confidence"] < 0.50
            )

            connection.execute(
                """
                INSERT INTO market_graph_runs (
                    graph_run_id,
                    engine_version,
                    source_table,
                    source_rows,
                    events_created,
                    markets_linked,
                    relationships_created,
                    wallet_event_profiles,
                    unlinked_markets,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    ENGINE_VERSION,
                    source_schema.table,
                    len(rows),
                    len(event_payloads),
                    len(market_links),
                    relationship_count,
                    len(wallet_event_rows),
                    unlinked_markets,
                    timestamp,
                ),
            )

        category_counts = connection.execute(
            """
            SELECT category, COUNT(*) AS event_count
            FROM market_events
            GROUP BY category
            ORDER BY event_count DESC, category
            """
        ).fetchall()

        top_events = connection.execute(
            """
            SELECT
                e.event_name,
                e.category,
                e.market_count,
                e.wallet_count,
                ROUND(e.total_exposure, 2) AS total_exposure,
                ROUND(e.total_capital_committed, 2) AS total_capital_committed,
                ROUND(MAX(w.event_conviction_score), 2) AS top_conviction
            FROM market_events e
            LEFT JOIN wallet_event_exposure w
                ON w.event_id = e.event_id
            GROUP BY e.event_id
            ORDER BY
                e.market_count DESC,
                e.wallet_count DESC,
                e.total_capital_committed DESC
            LIMIT 20
            """
        ).fetchall()

        print("\n" + "=" * 120)
        print("MARKET KNOWLEDGE GRAPH ENGINE COMPLETE")
        print("=" * 120)
        print(f"Database: {DATABASE_PATH}")
        print(f"Source table: {source_schema.table}")
        print(
            "Valuation inputs: "
            f"shares={source_schema.shares or 'missing'}, "
            f"average_price={source_schema.average_price or 'missing'}, "
            f"current_value={source_schema.current_value or 'missing'}, "
            f"explicit_capital={source_schema.capital_committed or 'missing'}"
        )
        print(f"Source rows analyzed: {len(rows)}")
        print(f"Events created: {len(event_payloads)}")
        print(f"Unique markets linked: {len(market_links)}")
        print(f"Relationships created: {relationship_count}")
        print(f"Wallet-event profiles: {len(wallet_event_rows)}")
        print(f"Low-confidence event links: {unlinked_markets}")
        print(f"Graph run ID: {run_id}")

        print("\nEvent distribution:")
        for row in category_counts:
            print(
                f"  {str(row['category']):<22} "
                f"{int(row['event_count']):>5}"
            )

        print("\nTop event families:")
        for index, row in enumerate(top_events, start=1):
            conviction = (
                f"{float(row['top_conviction']):.2f}"
                if row["top_conviction"] is not None
                else "N/A"
            )
            print(
                f"{index:>2}. {str(row['event_name'])[:65]:<65} "
                f"| category={str(row['category']):<12} "
                f"| markets={int(row['market_count']):>3} "
                f"| wallets={int(row['wallet_count']):>2} "
                f"| current={float(row['total_exposure'] or 0):>11,.2f} "
                f"| capital={float(row['total_capital_committed'] or 0):>11,.2f} "
                f"| top_conviction={conviction}"
            )

        print("\nNext command:")
        print("  python -m src.market_graph_engine 2>&1 | "
              "Tee-Object -FilePath market_graph_output.txt")

    finally:
        connection.close()


if __name__ == "__main__":
    run()