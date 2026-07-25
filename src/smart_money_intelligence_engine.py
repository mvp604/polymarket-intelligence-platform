from __future__ import annotations

import json
import math
import sqlite3
import statistics
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.0.0"

WALLET_ALIASES = (
    "wallet", "wallet_address", "user", "user_address", "proxy_wallet",
    "trader", "trader_address", "address", "owner",
)
MARKET_ALIASES = (
    "market_id", "condition_id", "token_id", "asset_id", "slug", "market",
)
OUTCOME_ALIASES = (
    "outcome", "selected_outcome", "position", "side", "answer",
)
TITLE_ALIASES = (
    "question", "title", "market_title", "market_question", "event_title",
)
CATEGORY_ALIASES = (
    "category", "market_category", "sport", "league", "vertical", "topic",
)
PRICE_ALIASES = (
    "average_price", "avg_price", "entry_price", "price", "current_price",
)
CAPITAL_ALIASES = (
    "current_value", "position_value", "value", "amount", "notional",
    "capital", "capital_deployed", "shares", "size",
)
TIMESTAMP_ALIASES = (
    "updated_at", "calculated_at", "scanned_at", "created_at", "timestamp",
    "trade_time", "event_time", "last_updated",
)

SOURCE_PRIORITY = (
    "wallet_current_position_snapshots",
    "positions",
    "official_wallet_trades",
    "official_wallet_activity",
    "wallet_trade_events",
)

DERIVED_PREFIXES = (
    "elite_wallet_", "smart_money_", "opportunity_", "consensus_",
    "market_feature_", "market_memory_", "wallet_relationship_",
    "schema_", "sqlite_",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def table_names(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    ]


def columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in connection.execute(
            f"PRAGMA table_info({quote(table)})"
        ).fetchall()
    ]


def row_count(connection: sqlite3.Connection, table: str) -> int:
    return int(
        connection.execute(
            f"SELECT COUNT(*) FROM {quote(table)}"
        ).fetchone()[0]
    )


def find_column(available: Iterable[str], aliases: Iterable[str]) -> str | None:
    lower = {name.lower(): name for name in available}
    for alias in aliases:
        if alias.lower() in lower:
            return lower[alias.lower()]
    return None


def infer_category(explicit: Any, title: Any) -> str:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()[:80]

    text = str(title or "").lower()
    rules = (
        ("Soccer", ("soccer", "football", "epl", "champions league", "world cup",
                    "la liga", "serie a", "bundesliga", "mls", "uefa", "fifa")),
        ("Basketball", ("nba", "wnba", "basketball", "ncaa")),
        ("American Football", ("nfl", "super bowl", "american football")),
        ("Baseball", ("mlb", "baseball", "world series")),
        ("Hockey", ("nhl", "hockey", "stanley cup")),
        ("MMA", ("ufc", "mma", "fight night")),
        ("Tennis", ("tennis", "wimbledon", "us open", "french open")),
        ("Crypto", ("bitcoin", "btc", "ethereum", "eth", "crypto", "solana")),
        ("Politics", ("election", "president", "senate", "congress", "nomination",
                      "prime minister", "governor", "democratic", "republican")),
        ("Economics", ("fed", "interest rate", "inflation", "cpi", "gdp",
                       "unemployment", "recession")),
        ("Technology", ("openai", "apple", "google", "microsoft", "ai model",
                        "artificial intelligence")),
        ("Entertainment", ("oscar", "grammy", "movie", "box office", "album")),
        ("Weather", ("temperature", "rain", "snow", "hurricane", "weather")),
    )
    for category, terms in rules:
        if any(term in text for term in terms):
            return category
    return "Other"


def normalize_outcome(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"


@dataclass
class Position:
    wallet: str
    market_id: str
    outcome: str
    title: str
    category: str
    price: float | None
    capital: float
    observed_at: datetime | None


@dataclass
class Cluster:
    market_id: str
    outcome: str
    title: str
    category: str
    positions: list[Position] = field(default_factory=list)


def discover_source(connection: sqlite3.Connection) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    for table in table_names(connection):
        lowered = table.lower()
        if lowered.startswith(DERIVED_PREFIXES):
            continue

        available = columns(connection, table)
        wallet = find_column(available, WALLET_ALIASES)
        market = find_column(available, MARKET_ALIASES)
        outcome = find_column(available, OUTCOME_ALIASES)
        if not wallet or not market:
            continue

        mapping = {
            "table": table,
            "rows": row_count(connection, table),
            "wallet": wallet,
            "market": market,
            "outcome": outcome,
            "title": find_column(available, TITLE_ALIASES),
            "category": find_column(available, CATEGORY_ALIASES),
            "price": find_column(available, PRICE_ALIASES),
            "capital": find_column(available, CAPITAL_ALIASES),
            "timestamp": find_column(available, TIMESTAMP_ALIASES),
        }

        feature_hits = sum(
            mapping[key] is not None
            for key in ("outcome", "title", "category", "price", "capital", "timestamp")
        )

        priority_bonus = 0
        if table in SOURCE_PRIORITY:
            priority_bonus = (len(SOURCE_PRIORITY) - SOURCE_PRIORITY.index(table)) * 50

        score = (
            feature_hits * 100
            + min(mapping["rows"] // 1000, 200)
            + priority_bonus
        )
        mapping["feature_hits"] = feature_hits
        mapping["score"] = score
        candidates.append(mapping)

    if not candidates:
        raise RuntimeError("No compatible wallet position/trade source found.")

    candidates.sort(
        key=lambda item: (item["score"], item["rows"]),
        reverse=True,
    )

    print()
    print("SMART MONEY SOURCE DISCOVERY")
    print("-" * 122)
    for index, candidate in enumerate(candidates[:12]):
        label = "SELECTED " if index == 0 else "candidate"
        print(
            f"{label:<9} rows={candidate['rows']:>9,} "
            f"feature_hits={candidate['feature_hits']:>2} "
            f"score={candidate['score']:>4} | {candidate['table']}"
        )
    print("-" * 122)
    return candidates[0]


def select_positions(
    connection: sqlite3.Connection,
    source: dict[str, Any],
) -> Iterable[sqlite3.Row]:
    aliases = (
        "wallet", "market", "outcome", "title", "category",
        "price", "capital", "timestamp",
    )
    selected: list[str] = []
    for alias in aliases:
        column = source.get(alias)
        if column is None:
            selected.append(f"NULL AS {quote(alias)}")
        else:
            selected.append(f"{quote(column)} AS {quote(alias)}")

    return connection.execute(
        f"""
        SELECT {", ".join(selected)}
        FROM {quote(source["table"])}
        WHERE {quote(source["wallet"])} IS NOT NULL
          AND {quote(source["market"])} IS NOT NULL
        """
    )


def load_elite_scores(
    connection: sqlite3.Connection,
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    overall: dict[str, dict[str, Any]] = {}
    category: dict[tuple[str, str], dict[str, Any]] = {}

    if "elite_wallet_intelligence" in table_names(connection):
        for row in connection.execute(
            """
            SELECT wallet, overall_score, elite_grade,
                   confidence_score, confidence_level
            FROM elite_wallet_intelligence
            """
        ):
            overall[str(row["wallet"])] = dict(row)

    if "elite_wallet_category_intelligence" in table_names(connection):
        for row in connection.execute(
            """
            SELECT wallet, category, category_score, category_grade,
                   confidence_score, confidence_level
            FROM elite_wallet_category_intelligence
            """
        ):
            category[(str(row["wallet"]), str(row["category"]))] = dict(row)

    return overall, category


def wallet_weight(
    wallet: str,
    market_category: str,
    overall: dict[str, dict[str, Any]],
    category: dict[tuple[str, str], dict[str, Any]],
) -> tuple[float, float, str]:
    overall_row = overall.get(wallet)
    category_row = category.get((wallet, market_category))

    if category_row:
        score = safe_float(category_row["category_score"]) or 50.0
        confidence = safe_float(category_row["confidence_score"]) or 0.0
        grade = str(category_row["category_grade"])
        evidence_weight = 0.45 + 0.55 * min(1.0, confidence / 100.0)
        return score * evidence_weight, confidence, grade

    if overall_row:
        score = safe_float(overall_row["overall_score"]) or 50.0
        confidence = safe_float(overall_row["confidence_score"]) or 0.0
        grade = str(overall_row["elite_grade"])
        evidence_weight = 0.40 + 0.60 * min(1.0, confidence / 100.0)
        return score * evidence_weight, confidence, grade

    return 35.0, 0.0, "UNRATED"


def build_clusters(
    connection: sqlite3.Connection,
    source: dict[str, Any],
) -> dict[tuple[str, str], Cluster]:
    clusters: dict[tuple[str, str], Cluster] = {}

    for row in select_positions(connection, source):
        wallet = str(row["wallet"] or "").strip()
        market_id = str(row["market"] or "").strip()
        if not wallet or not market_id:
            continue

        outcome = normalize_outcome(row["outcome"])
        title = str(row["title"] or market_id).strip()
        category = infer_category(row["category"], title)
        price = safe_float(row["price"])
        capital = abs(safe_float(row["capital"]) or 0.0)
        observed_at = parse_timestamp(row["timestamp"])

        key = (market_id, outcome)
        cluster = clusters.setdefault(
            key,
            Cluster(
                market_id=market_id,
                outcome=outcome,
                title=title,
                category=category,
            ),
        )
        cluster.positions.append(
            Position(
                wallet=wallet,
                market_id=market_id,
                outcome=outcome,
                title=title,
                category=category,
                price=price,
                capital=capital,
                observed_at=observed_at,
            )
        )

    return clusters


def cluster_metrics(
    clusters: dict[tuple[str, str], Cluster],
    overall_scores: dict[str, dict[str, Any]],
    category_scores: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for cluster in clusters.values():
        by_wallet: dict[str, list[Position]] = defaultdict(list)
        for position in cluster.positions:
            by_wallet[position.wallet].append(position)

        unique_wallets = sorted(by_wallet)
        if not unique_wallets:
            continue

        wallet_details: list[dict[str, Any]] = []
        total_capital = 0.0
        prices: list[float] = []
        timestamps: list[datetime] = []

        for wallet in unique_wallets:
            positions = by_wallet[wallet]
            wallet_capital = sum(position.capital for position in positions)
            total_capital += wallet_capital

            for position in positions:
                if position.price is not None:
                    prices.append(position.price)
                if position.observed_at is not None:
                    timestamps.append(position.observed_at)

            quality, confidence, grade = wallet_weight(
                wallet,
                cluster.category,
                overall_scores,
                category_scores,
            )
            wallet_details.append(
                {
                    "wallet": wallet,
                    "quality": quality,
                    "confidence": confidence,
                    "grade": grade,
                    "capital": wallet_capital,
                }
            )

        raw_quality = statistics.fmean(
            item["quality"] for item in wallet_details
        )
        weighted_quality_numerator = sum(
            item["quality"] * max(item["capital"], 1.0)
            for item in wallet_details
        )
        weighted_quality_denominator = sum(
            max(item["capital"], 1.0)
            for item in wallet_details
        )
        weighted_quality = (
            weighted_quality_numerator / weighted_quality_denominator
            if weighted_quality_denominator else raw_quality
        )

        elite_wallet_count = sum(
            1 for item in wallet_details
            if item["grade"] in {"S+", "S", "A+", "A"}
            and item["confidence"] >= 35
        )
        rated_wallet_count = sum(
            1 for item in wallet_details if item["grade"] != "UNRATED"
        )
        average_confidence = statistics.fmean(
            item["confidence"] for item in wallet_details
        )

        wallet_count = len(unique_wallets)
        agreement_score = min(
            100.0,
            22.0 * math.log1p(wallet_count)
            + 8.0 * elite_wallet_count,
        )
        quality_score = max(0.0, min(100.0, weighted_quality))

        if total_capital > 0:
            capital_score = min(
                100.0,
                18.0 * math.log10(1.0 + total_capital),
            )
            top_capital = max(item["capital"] for item in wallet_details)
            concentration = top_capital / total_capital
        else:
            capital_score = 25.0
            concentration = 1.0 / wallet_count

        if timestamps:
            earliest = min(timestamps)
            latest = max(timestamps)
            entry_window_minutes = max(
                0.0,
                (latest - earliest).total_seconds() / 60.0,
            )
            timing_score = max(
                0.0,
                min(
                    100.0,
                    100.0 - 18.0 * math.log1p(entry_window_minutes),
                ),
            )
            first_seen_at = earliest.isoformat(timespec="seconds")
            last_seen_at = latest.isoformat(timespec="seconds")
        else:
            entry_window_minutes = None
            timing_score = 35.0
            first_seen_at = None
            last_seen_at = None

        average_entry_price = statistics.fmean(prices) if prices else None
        price_dispersion = (
            statistics.pstdev(prices) if len(prices) >= 2 else 0.0
        )
        cohesion_score = max(
            0.0,
            min(100.0, 100.0 - price_dispersion * 500.0),
        ) if prices else 40.0

        coverage_score = min(
            100.0,
            (rated_wallet_count / wallet_count) * 100.0,
        )
        data_quality_score = (
            0.40 * coverage_score
            + 0.35 * average_confidence
            + 0.25 * (100.0 if timestamps else 35.0)
        )

        concentration_penalty = max(
            0.0,
            (concentration - 0.55) * 70.0,
        )
        unknown_outcome_penalty = 20.0 if cluster.outcome == "UNKNOWN" else 0.0
        single_wallet_penalty = 28.0 if wallet_count == 1 else 0.0

        smart_money_score = (
            0.28 * quality_score
            + 0.24 * agreement_score
            + 0.17 * capital_score
            + 0.13 * timing_score
            + 0.10 * cohesion_score
            + 0.08 * data_quality_score
            - concentration_penalty
            - unknown_outcome_penalty
            - single_wallet_penalty
        )
        smart_money_score = max(0.0, min(100.0, smart_money_score))

        if (
            smart_money_score >= 80
            and elite_wallet_count >= 2
            and wallet_count >= 3
            and data_quality_score >= 60
        ):
            recommendation = "ACTIONABLE"
            signal_grade = "S"
        elif (
            smart_money_score >= 68
            and wallet_count >= 2
            and data_quality_score >= 45
        ):
            recommendation = "WATCHLIST"
            signal_grade = "A"
        elif smart_money_score >= 55 and wallet_count >= 2:
            recommendation = "MONITOR"
            signal_grade = "B"
        else:
            recommendation = "PASS"
            signal_grade = "C"

        if entry_window_minutes is None:
            timing_status = "UNKNOWN"
        elif entry_window_minutes <= 15:
            timing_status = "TIGHT"
        elif entry_window_minutes <= 120:
            timing_status = "COORDINATED"
        elif entry_window_minutes <= 1440:
            timing_status = "DISTRIBUTED"
        else:
            timing_status = "STALE"

        top_wallets = sorted(
            wallet_details,
            key=lambda item: (item["quality"], item["capital"]),
            reverse=True,
        )[:10]

        rows.append(
            {
                "cluster_id": f"{cluster.market_id}:{cluster.outcome}",
                "market_id": cluster.market_id,
                "outcome": cluster.outcome,
                "title": cluster.title,
                "category": cluster.category,
                "wallet_count": wallet_count,
                "elite_wallet_count": elite_wallet_count,
                "rated_wallet_count": rated_wallet_count,
                "combined_capital": total_capital,
                "average_entry_price": average_entry_price,
                "price_dispersion": price_dispersion,
                "entry_window_minutes": entry_window_minutes,
                "first_seen_at": first_seen_at,
                "last_seen_at": last_seen_at,
                "timing_status": timing_status,
                "wallet_quality_score": quality_score,
                "agreement_score": agreement_score,
                "capital_score": capital_score,
                "timing_score": timing_score,
                "cohesion_score": cohesion_score,
                "data_quality_score": data_quality_score,
                "concentration_ratio": concentration,
                "risk_penalty": (
                    concentration_penalty
                    + unknown_outcome_penalty
                    + single_wallet_penalty
                ),
                "smart_money_score": smart_money_score,
                "recommendation": recommendation,
                "signal_grade": signal_grade,
                "top_wallets_json": json.dumps(top_wallets),
            }
        )

    rows.sort(
        key=lambda row: (
            row["smart_money_score"],
            row["elite_wallet_count"],
            row["wallet_count"],
            row["combined_capital"],
        ),
        reverse=True,
    )
    return rows


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS smart_money_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            source_table TEXT NOT NULL,
            source_rows INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            clusters_scored INTEGER NOT NULL DEFAULT 0,
            actionable_count INTEGER NOT NULL DEFAULT 0,
            watchlist_count INTEGER NOT NULL DEFAULT 0,
            warnings_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS smart_money_clusters (
            cluster_id TEXT PRIMARY KEY,
            market_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            title TEXT,
            category TEXT,
            wallet_count INTEGER NOT NULL,
            elite_wallet_count INTEGER NOT NULL,
            rated_wallet_count INTEGER NOT NULL,
            combined_capital REAL NOT NULL,
            average_entry_price REAL,
            price_dispersion REAL,
            entry_window_minutes REAL,
            first_seen_at TEXT,
            last_seen_at TEXT,
            timing_status TEXT NOT NULL,
            wallet_quality_score REAL NOT NULL,
            agreement_score REAL NOT NULL,
            capital_score REAL NOT NULL,
            timing_score REAL NOT NULL,
            cohesion_score REAL NOT NULL,
            data_quality_score REAL NOT NULL,
            concentration_ratio REAL NOT NULL,
            risk_penalty REAL NOT NULL,
            smart_money_score REAL NOT NULL,
            recommendation TEXT NOT NULL,
            signal_grade TEXT NOT NULL,
            top_wallets_json TEXT NOT NULL,
            methodology_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_smart_money_rank
        ON smart_money_clusters(
            recommendation,
            smart_money_score DESC,
            elite_wallet_count DESC
        );

        CREATE INDEX IF NOT EXISTS idx_smart_money_market
        ON smart_money_clusters(market_id, outcome);

        CREATE TABLE IF NOT EXISTS smart_money_cluster_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            cluster_id TEXT NOT NULL,
            market_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            smart_money_score REAL NOT NULL,
            recommendation TEXT NOT NULL,
            signal_grade TEXT NOT NULL,
            wallet_count INTEGER NOT NULL,
            elite_wallet_count INTEGER NOT NULL,
            combined_capital REAL NOT NULL,
            calculated_at TEXT NOT NULL
        );

        CREATE VIEW IF NOT EXISTS smart_money_action_board AS
        SELECT
            market_id,
            outcome,
            title,
            category,
            smart_money_score,
            recommendation,
            signal_grade,
            wallet_count,
            elite_wallet_count,
            combined_capital,
            average_entry_price,
            entry_window_minutes,
            timing_status,
            data_quality_score,
            calculated_at
        FROM smart_money_clusters
        WHERE recommendation IN ('ACTIONABLE', 'WATCHLIST', 'MONITOR')
        ORDER BY
            CASE recommendation
                WHEN 'ACTIONABLE' THEN 1
                WHEN 'WATCHLIST' THEN 2
                ELSE 3
            END,
            smart_money_score DESC,
            elite_wallet_count DESC;
        """
    )


def persist(
    connection: sqlite3.Connection,
    run_id: str,
    rows: list[dict[str, Any]],
    calculated_at: str,
) -> None:
    sql = """
    INSERT INTO smart_money_clusters (
        cluster_id, market_id, outcome, title, category,
        wallet_count, elite_wallet_count, rated_wallet_count,
        combined_capital, average_entry_price, price_dispersion,
        entry_window_minutes, first_seen_at, last_seen_at, timing_status,
        wallet_quality_score, agreement_score, capital_score,
        timing_score, cohesion_score, data_quality_score,
        concentration_ratio, risk_penalty, smart_money_score,
        recommendation, signal_grade, top_wallets_json,
        methodology_version, calculated_at
    ) VALUES (
        :cluster_id, :market_id, :outcome, :title, :category,
        :wallet_count, :elite_wallet_count, :rated_wallet_count,
        :combined_capital, :average_entry_price, :price_dispersion,
        :entry_window_minutes, :first_seen_at, :last_seen_at, :timing_status,
        :wallet_quality_score, :agreement_score, :capital_score,
        :timing_score, :cohesion_score, :data_quality_score,
        :concentration_ratio, :risk_penalty, :smart_money_score,
        :recommendation, :signal_grade, :top_wallets_json,
        :methodology_version, :calculated_at
    )
    ON CONFLICT(cluster_id) DO UPDATE SET
        market_id=excluded.market_id,
        outcome=excluded.outcome,
        title=excluded.title,
        category=excluded.category,
        wallet_count=excluded.wallet_count,
        elite_wallet_count=excluded.elite_wallet_count,
        rated_wallet_count=excluded.rated_wallet_count,
        combined_capital=excluded.combined_capital,
        average_entry_price=excluded.average_entry_price,
        price_dispersion=excluded.price_dispersion,
        entry_window_minutes=excluded.entry_window_minutes,
        first_seen_at=excluded.first_seen_at,
        last_seen_at=excluded.last_seen_at,
        timing_status=excluded.timing_status,
        wallet_quality_score=excluded.wallet_quality_score,
        agreement_score=excluded.agreement_score,
        capital_score=excluded.capital_score,
        timing_score=excluded.timing_score,
        cohesion_score=excluded.cohesion_score,
        data_quality_score=excluded.data_quality_score,
        concentration_ratio=excluded.concentration_ratio,
        risk_penalty=excluded.risk_penalty,
        smart_money_score=excluded.smart_money_score,
        recommendation=excluded.recommendation,
        signal_grade=excluded.signal_grade,
        top_wallets_json=excluded.top_wallets_json,
        methodology_version=excluded.methodology_version,
        calculated_at=excluded.calculated_at
    """

    for row in rows:
        payload = dict(row)
        payload["methodology_version"] = ENGINE_VERSION
        payload["calculated_at"] = calculated_at
        connection.execute(sql, payload)

        connection.execute(
            """
            INSERT INTO smart_money_cluster_history (
                run_id, cluster_id, market_id, outcome,
                smart_money_score, recommendation, signal_grade,
                wallet_count, elite_wallet_count, combined_capital,
                calculated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row["cluster_id"],
                row["market_id"],
                row["outcome"],
                row["smart_money_score"],
                row["recommendation"],
                row["signal_grade"],
                row["wallet_count"],
                row["elite_wallet_count"],
                row["combined_capital"],
                calculated_at,
            ),
        )


def main() -> int:
    started_at = utc_now()
    run_id = (
        f"smart-money:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:"
        f"{uuid.uuid4().hex[:8]}"
    )
    warnings: list[str] = []

    print("=" * 122)
    print(f"SMART MONEY INTELLIGENCE ENGINE v{ENGINE_VERSION}")
    print("=" * 122)
    print(f"Run ID:   {run_id}")
    print(f"Database: {DATABASE_PATH}")

    if not DATABASE_PATH.exists():
        print("ERROR: Database not found.", file=sys.stderr)
        return 1

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        ensure_schema(connection)

        source = discover_source(connection)
        print(
            f"Source:   {source['table']} "
            f"({source['rows']:,} rows)"
        )

        overall_scores, category_scores = load_elite_scores(connection)
        if not overall_scores:
            warnings.append(
                "Elite wallet scores were unavailable; fallback wallet weights were used."
            )

        connection.execute(
            """
            INSERT INTO smart_money_intelligence_runs (
                run_id, engine_version, source_table, source_rows,
                started_at, status, warnings_json
            ) VALUES (?, ?, ?, ?, ?, 'RUNNING', ?)
            """,
            (
                run_id,
                ENGINE_VERSION,
                source["table"],
                source["rows"],
                started_at,
                json.dumps(warnings),
            ),
        )
        connection.commit()

        clusters = build_clusters(connection, source)
        rows = cluster_metrics(
            clusters,
            overall_scores,
            category_scores,
        )
        calculated_at = utc_now()
        persist(connection, run_id, rows, calculated_at)

        actionable = sum(
            1 for row in rows if row["recommendation"] == "ACTIONABLE"
        )
        watchlist = sum(
            1 for row in rows if row["recommendation"] == "WATCHLIST"
        )

        connection.execute(
            """
            UPDATE smart_money_intelligence_runs
            SET completed_at=?,
                status='SUCCESS',
                clusters_scored=?,
                actionable_count=?,
                watchlist_count=?,
                warnings_json=?
            WHERE run_id=?
            """,
            (
                calculated_at,
                len(rows),
                actionable,
                watchlist,
                json.dumps(warnings),
                run_id,
            ),
        )
        connection.commit()

    print()
    print("TOP SMART MONEY BOARD")
    print("-" * 122)
    for index, row in enumerate(rows[:30], start=1):
        title = str(row["title"] or row["market_id"])
        if len(title) > 64:
            title = title[:61] + "..."
        print(
            f"{index:>2}. {row['signal_grade']:<2} "
            f"{row['recommendation']:<10} "
            f"Score={row['smart_money_score']:>6.2f} "
            f"Wallets={row['wallet_count']:>3} "
            f"Elite={row['elite_wallet_count']:>2} "
            f"Capital=${row['combined_capital']:>12,.2f} "
            f"Timing={row['timing_status']:<11} "
            f"| {title} [{row['outcome']}]"
        )

    monitor = sum(1 for row in rows if row["recommendation"] == "MONITOR")
    passed = sum(1 for row in rows if row["recommendation"] == "PASS")

    print()
    print("SMART MONEY INTELLIGENCE HEALTH SUMMARY")
    print("-" * 122)
    print("Status:             SUCCESS")
    print(f"Source table:       {source['table']}")
    print(f"Source rows:        {source['rows']:,}")
    print(f"Clusters scored:    {len(rows):,}")
    print(f"Actionable:         {actionable:,}")
    print(f"Watchlist:          {watchlist:,}")
    print(f"Monitor:            {monitor:,}")
    print(f"Pass:               {passed:,}")
    print(f"Elite wallets read: {len(overall_scores):,}")
    print(f"Warnings:           {len(warnings):,}")
    for warning in warnings:
        print(f"  - {warning}")
    print("=" * 122)
    print("SMART MONEY INTELLIGENCE COMPLETE")
    print("=" * 122)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
