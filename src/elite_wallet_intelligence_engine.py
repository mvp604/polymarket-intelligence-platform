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
TITLE_ALIASES = (
    "question", "title", "market_title", "market_question", "event_title",
)
CATEGORY_ALIASES = (
    "category", "market_category", "sport", "league", "vertical", "topic",
)
PNL_ALIASES = (
    "realized_pnl", "cash_pnl", "total_pnl", "pnl", "profit", "net_pnl",
)
ROI_ALIASES = (
    "roi", "roi_pct", "return_pct", "percent_pnl", "profit_percentage",
)
WIN_RATE_ALIASES = (
    "win_rate", "accuracy", "prediction_accuracy", "resolved_win_rate",
)
RESOLVED_ALIASES = (
    "resolved_markets", "resolved_count", "settled_count", "closed_markets",
    "markets_resolved", "resolution_count",
)
TRADE_COUNT_ALIASES = (
    "trade_count", "trades", "total_trades", "activity_count",
)
CAPITAL_ALIASES = (
    "capital_deployed", "total_volume", "volume", "current_value",
    "position_value", "value", "amount", "size", "shares",
)
TIMESTAMP_ALIASES = (
    "updated_at", "calculated_at", "scanned_at", "created_at", "timestamp",
    "trade_time", "event_time", "last_updated",
)

PERFORMANCE_NAME_HINTS = (
    "wallet_performance", "elite_wallet", "wallet_rank", "wallet_score",
    "trader_performance", "wallet_stats",
)
ACTIVITY_NAME_HINTS = (
    "official_wallet_trades", "official_wallet_activity", "positions",
    "wallet_position", "trade", "activity",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


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
    by_lower = {column.lower(): column for column in available}
    for alias in aliases:
        if alias.lower() in by_lower:
            return by_lower[alias.lower()]
    return None


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


def normalize_rate(value: float | None) -> float | None:
    if value is None:
        return None
    if -1.0 <= value <= 1.0:
        return value * 100.0
    return value


def percentile_ranks(values: dict[str, float | None]) -> dict[str, float]:
    numeric = sorted(value for value in values.values() if value is not None)
    if not numeric:
        return {key: 50.0 for key in values}
    if len(numeric) == 1:
        return {key: 50.0 for key in values}

    result: dict[str, float] = {}
    for key, value in values.items():
        if value is None:
            result[key] = 50.0
            continue
        lower = sum(1 for item in numeric if item < value)
        equal = sum(1 for item in numeric if item == value)
        rank = (lower + 0.5 * equal) / len(numeric)
        result[key] = max(0.0, min(100.0, rank * 100.0))
    return result


def infer_category(explicit: Any, title: Any) -> str:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()[:80]

    text = str(title or "").lower()
    category_rules = (
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
    for category, terms in category_rules:
        if any(term in text for term in terms):
            return category
    return "Other"


@dataclass
class WalletAggregate:
    wallet: str
    pnl_values: list[float] = field(default_factory=list)
    roi_values: list[float] = field(default_factory=list)
    win_rates: list[float] = field(default_factory=list)
    resolved_counts: list[float] = field(default_factory=list)
    trade_counts: list[float] = field(default_factory=list)
    capital_values: list[float] = field(default_factory=list)
    observed_rows: int = 0
    markets: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    categories: dict[str, "CategoryAggregate"] = field(
        default_factory=lambda: defaultdict(CategoryAggregate)
    )


@dataclass
class CategoryAggregate:
    pnl_values: list[float] = field(default_factory=list)
    roi_values: list[float] = field(default_factory=list)
    win_rates: list[float] = field(default_factory=list)
    resolved_count: float = 0.0
    trade_count: int = 0
    capital: float = 0.0
    markets: set[str] = field(default_factory=set)


def discover_sources(
    connection: sqlite3.Connection,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    performance_sources: list[dict[str, Any]] = []
    activity_sources: list[dict[str, Any]] = []

    excluded_prefixes = (
        "wallet_intelligence", "elite_wallet_intelligence", "elite_wallet_",
        "opportunity_", "schema_", "sqlite_",
    )

    for table in table_names(connection):
        lowered = table.lower()
        if lowered.startswith(excluded_prefixes):
            continue

        available = columns(connection, table)
        wallet_col = find_column(available, WALLET_ALIASES)
        if wallet_col is None:
            continue

        mapping = {
            "table": table,
            "rows": row_count(connection, table),
            "wallet": wallet_col,
            "market": find_column(available, MARKET_ALIASES),
            "title": find_column(available, TITLE_ALIASES),
            "category": find_column(available, CATEGORY_ALIASES),
            "pnl": find_column(available, PNL_ALIASES),
            "roi": find_column(available, ROI_ALIASES),
            "win_rate": find_column(available, WIN_RATE_ALIASES),
            "resolved": find_column(available, RESOLVED_ALIASES),
            "trade_count": find_column(available, TRADE_COUNT_ALIASES),
            "capital": find_column(available, CAPITAL_ALIASES),
            "timestamp": find_column(available, TIMESTAMP_ALIASES),
        }

        metric_count = sum(
            mapping[key] is not None
            for key in ("pnl", "roi", "win_rate", "resolved", "trade_count")
        )
        activity_count = sum(
            mapping[key] is not None
            for key in ("market", "title", "category", "capital", "timestamp")
        )

        performance_hint = any(hint in lowered for hint in PERFORMANCE_NAME_HINTS)
        activity_hint = any(hint in lowered for hint in ACTIVITY_NAME_HINTS)

        if metric_count >= 2 or (performance_hint and metric_count >= 1):
            mapping["quality"] = metric_count * 100 + min(mapping["rows"], 99999)
            performance_sources.append(mapping)

        if activity_count >= 2 or (activity_hint and activity_count >= 1):
            mapping = dict(mapping)
            mapping["quality"] = activity_count * 100 + min(mapping["rows"], 99999)
            activity_sources.append(mapping)

    performance_sources.sort(key=lambda item: item["quality"], reverse=True)
    activity_sources.sort(key=lambda item: item["quality"], reverse=True)

    return performance_sources[:4], activity_sources[:6]


def select_rows(
    connection: sqlite3.Connection,
    source: dict[str, Any],
    limit: int | None = None,
) -> Iterable[sqlite3.Row]:
    selected: list[str] = []
    aliases = (
        "wallet", "market", "title", "category", "pnl", "roi",
        "win_rate", "resolved", "trade_count", "capital", "timestamp",
    )
    for alias in aliases:
        column = source.get(alias)
        if column is None:
            selected.append(f"NULL AS {quote(alias)}")
        else:
            selected.append(f"{quote(column)} AS {quote(alias)}")

    sql = (
        f"SELECT {', '.join(selected)} "
        f"FROM {quote(source['table'])} "
        f"WHERE {quote(source['wallet'])} IS NOT NULL"
    )
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return connection.execute(sql)


def load_data(
    connection: sqlite3.Connection,
    performance_sources: list[dict[str, Any]],
    activity_sources: list[dict[str, Any]],
) -> dict[str, WalletAggregate]:
    wallets: dict[str, WalletAggregate] = {}

    def get_wallet(raw: Any) -> WalletAggregate | None:
        if raw is None:
            return None
        wallet = str(raw).strip()
        if not wallet:
            return None
        return wallets.setdefault(wallet, WalletAggregate(wallet=wallet))

    for source in performance_sources:
        for row in select_rows(connection, source):
            aggregate = get_wallet(row["wallet"])
            if aggregate is None:
                continue
            aggregate.sources.add(source["table"])
            aggregate.observed_rows += 1

            pnl = safe_float(row["pnl"])
            roi = normalize_rate(safe_float(row["roi"]))
            win_rate = normalize_rate(safe_float(row["win_rate"]))
            resolved = safe_float(row["resolved"])
            trades = safe_float(row["trade_count"])
            capital = safe_float(row["capital"])

            if pnl is not None:
                aggregate.pnl_values.append(pnl)
            if roi is not None:
                aggregate.roi_values.append(roi)
            if win_rate is not None:
                aggregate.win_rates.append(win_rate)
            if resolved is not None:
                aggregate.resolved_counts.append(max(0.0, resolved))
            if trades is not None:
                aggregate.trade_counts.append(max(0.0, trades))
            if capital is not None:
                aggregate.capital_values.append(abs(capital))

    for source in activity_sources:
        for row in select_rows(connection, source):
            aggregate = get_wallet(row["wallet"])
            if aggregate is None:
                continue

            aggregate.sources.add(source["table"])
            aggregate.observed_rows += 1

            market = str(row["market"] or "").strip()
            title = row["title"]
            category = infer_category(row["category"], title)
            pnl = safe_float(row["pnl"])
            roi = normalize_rate(safe_float(row["roi"]))
            win_rate = normalize_rate(safe_float(row["win_rate"]))
            resolved = safe_float(row["resolved"])
            capital = safe_float(row["capital"])

            if market:
                aggregate.markets.add(market)

            category_agg = aggregate.categories[category]
            category_agg.trade_count += 1
            if market:
                category_agg.markets.add(market)
            if capital is not None:
                category_agg.capital += abs(capital)
                aggregate.capital_values.append(abs(capital))
            if pnl is not None:
                category_agg.pnl_values.append(pnl)
            if roi is not None:
                category_agg.roi_values.append(roi)
            if win_rate is not None:
                category_agg.win_rates.append(win_rate)
            if resolved is not None:
                category_agg.resolved_count += max(0.0, resolved)

    return wallets


def average(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def grade(score: float, confidence: float) -> str:
    if score >= 90 and confidence >= 80:
        return "S+"
    if score >= 82 and confidence >= 65:
        return "S"
    if score >= 75 and confidence >= 50:
        return "A+"
    if score >= 68 and confidence >= 35:
        return "A"
    if score >= 58:
        return "B"
    return "C"


def confidence_label(score: float) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    if score >= 30:
        return "LOW"
    return "PROVISIONAL"


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS elite_wallet_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            wallets_scored INTEGER NOT NULL DEFAULT 0,
            category_profiles INTEGER NOT NULL DEFAULT 0,
            performance_sources_json TEXT NOT NULL DEFAULT '[]',
            activity_sources_json TEXT NOT NULL DEFAULT '[]',
            warnings_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS elite_wallet_intelligence (
            wallet TEXT PRIMARY KEY,
            overall_score REAL NOT NULL,
            elite_grade TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            confidence_level TEXT NOT NULL,
            profitability_score REAL NOT NULL,
            consistency_score REAL NOT NULL,
            experience_score REAL NOT NULL,
            activity_score REAL NOT NULL,
            specialization_score REAL NOT NULL,
            total_pnl REAL,
            average_roi REAL,
            win_rate REAL,
            resolved_markets REAL NOT NULL DEFAULT 0,
            trade_count REAL NOT NULL DEFAULT 0,
            unique_markets INTEGER NOT NULL DEFAULT 0,
            capital_observed REAL NOT NULL DEFAULT 0,
            best_category TEXT,
            best_category_score REAL,
            source_count INTEGER NOT NULL DEFAULT 0,
            source_tables_json TEXT NOT NULL DEFAULT '[]',
            methodology_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_elite_wallet_rank
        ON elite_wallet_intelligence(
            elite_grade,
            overall_score DESC,
            confidence_score DESC
        );

        CREATE TABLE IF NOT EXISTS elite_wallet_category_intelligence (
            wallet TEXT NOT NULL,
            category TEXT NOT NULL,
            category_score REAL NOT NULL,
            category_grade TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            confidence_level TEXT NOT NULL,
            trade_count INTEGER NOT NULL DEFAULT 0,
            unique_markets INTEGER NOT NULL DEFAULT 0,
            resolved_markets REAL NOT NULL DEFAULT 0,
            capital_observed REAL NOT NULL DEFAULT 0,
            average_roi REAL,
            win_rate REAL,
            specialization_share REAL NOT NULL DEFAULT 0,
            evidence_status TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            PRIMARY KEY(wallet, category),
            FOREIGN KEY(wallet) REFERENCES elite_wallet_intelligence(wallet)
        );

        CREATE INDEX IF NOT EXISTS idx_elite_wallet_category_rank
        ON elite_wallet_category_intelligence(
            category,
            category_score DESC,
            confidence_score DESC
        );

        CREATE TABLE IF NOT EXISTS elite_wallet_intelligence_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            wallet TEXT NOT NULL,
            overall_score REAL NOT NULL,
            elite_grade TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            calculated_at TEXT NOT NULL
        );

        CREATE VIEW IF NOT EXISTS elite_wallet_leaderboard AS
        SELECT
            wallet,
            overall_score,
            elite_grade,
            confidence_score,
            confidence_level,
            total_pnl,
            average_roi,
            win_rate,
            resolved_markets,
            unique_markets,
            best_category,
            best_category_score,
            calculated_at
        FROM elite_wallet_intelligence
        WHERE confidence_score >= 30
        ORDER BY
            overall_score DESC,
            confidence_score DESC;
        """
    )


def score_wallets(
    wallets: dict[str, WalletAggregate],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    totals = {
        wallet: {
            "pnl": sum(agg.pnl_values) if agg.pnl_values else None,
            "roi": average(agg.roi_values),
            "win_rate": average(agg.win_rates),
            "resolved": max(agg.resolved_counts) if agg.resolved_counts else 0.0,
            "trades": max(
                [float(agg.observed_rows), *agg.trade_counts]
            ) if (agg.trade_counts or agg.observed_rows) else 0.0,
            "capital": sum(agg.capital_values),
            "markets": len(agg.markets),
        }
        for wallet, agg in wallets.items()
    }

    pnl_rank = percentile_ranks({w: item["pnl"] for w, item in totals.items()})
    roi_rank = percentile_ranks({w: item["roi"] for w, item in totals.items()})
    win_rank = percentile_ranks({w: item["win_rate"] for w, item in totals.items()})
    resolved_rank = percentile_ranks(
        {w: math.log1p(item["resolved"]) for w, item in totals.items()}
    )
    activity_rank = percentile_ranks(
        {
            w: math.log1p(item["trades"] + item["markets"])
            for w, item in totals.items()
        }
    )
    capital_rank = percentile_ranks(
        {w: math.log1p(item["capital"]) for w, item in totals.items()}
    )

    wallet_rows: list[dict[str, Any]] = []
    category_rows: list[dict[str, Any]] = []

    for wallet, aggregate in wallets.items():
        item = totals[wallet]

        profitability_evidence = int(item["pnl"] is not None) + int(
            item["roi"] is not None
        )
        if profitability_evidence == 2:
            profitability = 0.55 * pnl_rank[wallet] + 0.45 * roi_rank[wallet]
        elif item["pnl"] is not None:
            profitability = pnl_rank[wallet]
        elif item["roi"] is not None:
            profitability = roi_rank[wallet]
        else:
            profitability = 45.0

        consistency = win_rank[wallet] if item["win_rate"] is not None else 45.0
        experience = (
            0.65 * resolved_rank[wallet] + 0.35 * activity_rank[wallet]
        )
        activity = 0.65 * activity_rank[wallet] + 0.35 * capital_rank[wallet]

        total_category_trades = sum(
            category.trade_count for category in aggregate.categories.values()
        )
        category_scores_local: list[tuple[str, float, float]] = []

        for category, category_agg in aggregate.categories.items():
            share = (
                category_agg.trade_count / total_category_trades
                if total_category_trades else 0.0
            )
            category_roi = average(category_agg.roi_values)
            category_win = average(category_agg.win_rates)

            evidence = min(
                100.0,
                12.0 * math.log1p(category_agg.trade_count)
                + 15.0 * math.log1p(category_agg.resolved_count)
                + (15.0 if category_roi is not None else 0.0)
                + (15.0 if category_win is not None else 0.0),
            )

            category_performance = profitability
            if category_roi is not None:
                category_performance = (
                    0.65 * category_performance
                    + 0.35 * max(0.0, min(100.0, 50.0 + category_roi))
                )
            if category_win is not None:
                category_performance = (
                    0.65 * category_performance
                    + 0.35 * max(0.0, min(100.0, category_win))
                )

            specialization_bonus = min(12.0, share * 15.0)
            category_score = max(
                0.0,
                min(
                    100.0,
                    0.55 * category_performance
                    + 0.25 * consistency
                    + 0.20 * experience
                    + specialization_bonus,
                ),
            )

            category_confidence = min(
                100.0,
                0.55 * evidence
                + 0.25 * min(100.0, aggregate.observed_rows * 2.0)
                + 0.20 * min(100.0, len(category_agg.markets) * 4.0),
            )

            category_scores_local.append(
                (category, category_score, category_confidence)
            )
            category_rows.append(
                {
                    "wallet": wallet,
                    "category": category,
                    "category_score": category_score,
                    "category_grade": grade(category_score, category_confidence),
                    "confidence_score": category_confidence,
                    "confidence_level": confidence_label(category_confidence),
                    "trade_count": category_agg.trade_count,
                    "unique_markets": len(category_agg.markets),
                    "resolved_markets": category_agg.resolved_count,
                    "capital_observed": category_agg.capital,
                    "average_roi": category_roi,
                    "win_rate": category_win,
                    "specialization_share": share,
                    "evidence_status": (
                        "VALIDATED"
                        if category_confidence >= 65
                        else "DEVELOPING"
                        if category_confidence >= 35
                        else "PROVISIONAL"
                    ),
                }
            )

        if category_scores_local:
            best_category, best_category_score, _ = max(
                category_scores_local,
                key=lambda row: (row[1], row[2]),
            )
            specialization = max(
                45.0,
                min(
                    100.0,
                    best_category_score
                    + min(8.0, len(category_scores_local) * 0.5),
                ),
            )
        else:
            best_category = None
            best_category_score = None
            specialization = 40.0

        data_fields = sum(
            value is not None
            for value in (
                item["pnl"], item["roi"], item["win_rate"],
            )
        )
        confidence = min(
            100.0,
            8.0 * data_fields
            + 18.0 * math.log1p(item["resolved"])
            + 7.0 * math.log1p(item["markets"])
            + 4.0 * math.log1p(item["trades"])
            + min(15.0, len(aggregate.sources) * 4.0),
        )

        overall = (
            0.30 * profitability
            + 0.22 * consistency
            + 0.20 * experience
            + 0.13 * activity
            + 0.15 * specialization
        )

        # Confidence shrinkage keeps sparse-history wallets from appearing elite.
        shrinkage = min(1.0, 0.40 + confidence / 100.0 * 0.60)
        overall = 50.0 + (overall - 50.0) * shrinkage
        overall = max(0.0, min(100.0, overall))

        wallet_rows.append(
            {
                "wallet": wallet,
                "overall_score": overall,
                "elite_grade": grade(overall, confidence),
                "confidence_score": confidence,
                "confidence_level": confidence_label(confidence),
                "profitability_score": profitability,
                "consistency_score": consistency,
                "experience_score": experience,
                "activity_score": activity,
                "specialization_score": specialization,
                "total_pnl": item["pnl"],
                "average_roi": item["roi"],
                "win_rate": item["win_rate"],
                "resolved_markets": item["resolved"],
                "trade_count": item["trades"],
                "unique_markets": item["markets"],
                "capital_observed": item["capital"],
                "best_category": best_category,
                "best_category_score": best_category_score,
                "source_count": len(aggregate.sources),
                "source_tables_json": json.dumps(sorted(aggregate.sources)),
            }
        )

    wallet_rows.sort(
        key=lambda row: (
            row["overall_score"],
            row["confidence_score"],
        ),
        reverse=True,
    )
    category_rows.sort(
        key=lambda row: (
            row["category"],
            -row["category_score"],
            -row["confidence_score"],
        )
    )
    return wallet_rows, category_rows


def persist(
    connection: sqlite3.Connection,
    run_id: str,
    wallet_rows: list[dict[str, Any]],
    category_rows: list[dict[str, Any]],
    calculated_at: str,
) -> None:
    connection.execute("DELETE FROM elite_wallet_category_intelligence")

    wallet_sql = """
    INSERT INTO elite_wallet_intelligence (
        wallet, overall_score, elite_grade, confidence_score,
        confidence_level, profitability_score, consistency_score,
        experience_score, activity_score, specialization_score,
        total_pnl, average_roi, win_rate, resolved_markets,
        trade_count, unique_markets, capital_observed, best_category,
        best_category_score, source_count, source_tables_json,
        methodology_version, calculated_at
    ) VALUES (
        :wallet, :overall_score, :elite_grade, :confidence_score,
        :confidence_level, :profitability_score, :consistency_score,
        :experience_score, :activity_score, :specialization_score,
        :total_pnl, :average_roi, :win_rate, :resolved_markets,
        :trade_count, :unique_markets, :capital_observed, :best_category,
        :best_category_score, :source_count, :source_tables_json,
        :methodology_version, :calculated_at
    )
    ON CONFLICT(wallet) DO UPDATE SET
        overall_score=excluded.overall_score,
        elite_grade=excluded.elite_grade,
        confidence_score=excluded.confidence_score,
        confidence_level=excluded.confidence_level,
        profitability_score=excluded.profitability_score,
        consistency_score=excluded.consistency_score,
        experience_score=excluded.experience_score,
        activity_score=excluded.activity_score,
        specialization_score=excluded.specialization_score,
        total_pnl=excluded.total_pnl,
        average_roi=excluded.average_roi,
        win_rate=excluded.win_rate,
        resolved_markets=excluded.resolved_markets,
        trade_count=excluded.trade_count,
        unique_markets=excluded.unique_markets,
        capital_observed=excluded.capital_observed,
        best_category=excluded.best_category,
        best_category_score=excluded.best_category_score,
        source_count=excluded.source_count,
        source_tables_json=excluded.source_tables_json,
        methodology_version=excluded.methodology_version,
        calculated_at=excluded.calculated_at
    """

    for row in wallet_rows:
        payload = dict(row)
        payload["methodology_version"] = ENGINE_VERSION
        payload["calculated_at"] = calculated_at
        connection.execute(wallet_sql, payload)
        connection.execute(
            """
            INSERT INTO elite_wallet_intelligence_history (
                run_id, wallet, overall_score, elite_grade,
                confidence_score, calculated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row["wallet"],
                row["overall_score"],
                row["elite_grade"],
                row["confidence_score"],
                calculated_at,
            ),
        )

    category_sql = """
    INSERT INTO elite_wallet_category_intelligence (
        wallet, category, category_score, category_grade,
        confidence_score, confidence_level, trade_count,
        unique_markets, resolved_markets, capital_observed,
        average_roi, win_rate, specialization_share,
        evidence_status, calculated_at
    ) VALUES (
        :wallet, :category, :category_score, :category_grade,
        :confidence_score, :confidence_level, :trade_count,
        :unique_markets, :resolved_markets, :capital_observed,
        :average_roi, :win_rate, :specialization_share,
        :evidence_status, :calculated_at
    )
    """
    for row in category_rows:
        payload = dict(row)
        payload["calculated_at"] = calculated_at
        connection.execute(category_sql, payload)


def print_sources(title: str, sources: list[dict[str, Any]]) -> None:
    print()
    print(title)
    print("-" * 118)
    if not sources:
        print("None discovered")
        return
    for source in sources:
        metrics = [
            key for key in (
                "pnl", "roi", "win_rate", "resolved", "trade_count",
                "market", "title", "category", "capital",
            )
            if source.get(key) is not None
        ]
        print(
            f"{source['rows']:>10,} rows | {source['table']:<45} "
            f"| {', '.join(metrics)}"
        )


def main() -> int:
    started_at = utc_now()
    run_id = f"elite-wallet:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:8]}"
    warnings: list[str] = []

    print("=" * 118)
    print(f"ELITE WALLET INTELLIGENCE ENGINE v{ENGINE_VERSION}")
    print("=" * 118)
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

        performance_sources, activity_sources = discover_sources(connection)
        print_sources("PERFORMANCE SOURCES", performance_sources)
        print_sources("ACTIVITY / POSITION SOURCES", activity_sources)

        if not performance_sources and not activity_sources:
            raise RuntimeError(
                "No compatible wallet performance, trade, activity, or position tables found."
            )
        if not performance_sources:
            warnings.append(
                "No dedicated performance source found; all grades are provisional."
            )

        connection.execute(
            """
            INSERT INTO elite_wallet_intelligence_runs (
                run_id, engine_version, started_at, status,
                performance_sources_json, activity_sources_json,
                warnings_json
            ) VALUES (?, ?, ?, 'RUNNING', ?, ?, ?)
            """,
            (
                run_id,
                ENGINE_VERSION,
                started_at,
                json.dumps(
                    [source["table"] for source in performance_sources]
                ),
                json.dumps(
                    [source["table"] for source in activity_sources]
                ),
                json.dumps(warnings),
            ),
        )
        connection.commit()

        wallets = load_data(connection, performance_sources, activity_sources)
        wallet_rows, category_rows = score_wallets(wallets)
        calculated_at = utc_now()

        persist(
            connection,
            run_id,
            wallet_rows,
            category_rows,
            calculated_at,
        )

        connection.execute(
            """
            UPDATE elite_wallet_intelligence_runs
            SET completed_at=?,
                status='SUCCESS',
                wallets_scored=?,
                category_profiles=?,
                warnings_json=?
            WHERE run_id=?
            """,
            (
                calculated_at,
                len(wallet_rows),
                len(category_rows),
                json.dumps(warnings),
                run_id,
            ),
        )
        connection.commit()

    print()
    print("TOP ELITE WALLET BOARD")
    print("-" * 118)
    for index, row in enumerate(wallet_rows[:25], start=1):
        wallet_display = row["wallet"]
        if len(wallet_display) > 20:
            wallet_display = wallet_display[:10] + "..." + wallet_display[-8:]
        print(
            f"{index:>2}. {row['elite_grade']:<3} "
            f"Score={row['overall_score']:>6.2f} "
            f"Conf={row['confidence_score']:>6.2f} "
            f"{row['confidence_level']:<11} "
            f"Markets={row['unique_markets']:>5} "
            f"Best={str(row['best_category'] or '-'): <18} "
            f"| {wallet_display}"
        )

    grade_counts: dict[str, int] = defaultdict(int)
    for row in wallet_rows:
        grade_counts[row["elite_grade"]] += 1

    print()
    print("ELITE WALLET INTELLIGENCE HEALTH SUMMARY")
    print("-" * 118)
    print("Status:             SUCCESS")
    print(f"Wallets scored:     {len(wallet_rows):,}")
    print(f"Category profiles:  {len(category_rows):,}")
    print(f"S+ wallets:         {grade_counts['S+']:,}")
    print(f"S wallets:          {grade_counts['S']:,}")
    print(f"A+ wallets:         {grade_counts['A+']:,}")
    print(f"A wallets:          {grade_counts['A']:,}")
    print(f"Warnings:           {len(warnings):,}")
    for warning in warnings:
        print(f"  - {warning}")
    print("=" * 118)
    print("ELITE WALLET INTELLIGENCE COMPLETE")
    print("=" * 118)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
