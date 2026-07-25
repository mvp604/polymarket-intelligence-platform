from __future__ import annotations

import json
import math
import sqlite3
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA busy_timeout = 30000;")
    return connection


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table)})"
        ).fetchall()
    }


def first_present(columns: set[str], candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS wallet_influence (
            wallet TEXT PRIMARY KEY,
            event_count INTEGER NOT NULL,
            position_count INTEGER NOT NULL,
            category_count INTEGER NOT NULL,
            total_capital_committed REAL NOT NULL,
            median_event_capital REAL NOT NULL,
            largest_event_capital REAL NOT NULL,
            average_event_conviction REAL NOT NULL,
            weighted_event_conviction REAL NOT NULL,
            expertise_score REAL NOT NULL,
            capital_score REAL NOT NULL,
            allocation_intensity_score REAL NOT NULL,
            specialization_score REAL NOT NULL,
            consistency_score REAL NOT NULL,
            diversification_score REAL NOT NULL,
            concentration_risk_score REAL NOT NULL,
            influence_score REAL NOT NULL,
            influence_percentile REAL NOT NULL,
            influence_grade TEXT NOT NULL,
            primary_category TEXT,
            primary_category_share REAL NOT NULL,
            category_distribution_json TEXT NOT NULL,
            data_quality_score REAL NOT NULL,
            engine_version TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_wallet_influence_score
        ON wallet_influence(influence_score DESC);

        CREATE INDEX IF NOT EXISTS idx_wallet_influence_grade
        ON wallet_influence(influence_grade);

        CREATE TABLE IF NOT EXISTS wallet_event_influence (
            event_id TEXT NOT NULL,
            wallet TEXT NOT NULL,
            category TEXT NOT NULL,
            capital_committed REAL NOT NULL,
            wallet_total_capital REAL NOT NULL,
            wallet_allocation_pct REAL NOT NULL,
            event_capital_share REAL NOT NULL,
            event_conviction_score REAL NOT NULL,
            expertise_weight REAL NOT NULL,
            base_influence_score REAL NOT NULL,
            allocation_multiplier REAL NOT NULL,
            event_influence_weight REAL NOT NULL,
            event_influence_share REAL NOT NULL,
            influence_grade TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(event_id, wallet),
            FOREIGN KEY(event_id) REFERENCES market_events(event_id),
            FOREIGN KEY(wallet) REFERENCES wallet_influence(wallet)
        );

        CREATE INDEX IF NOT EXISTS idx_wallet_event_influence_event
        ON wallet_event_influence(event_id, event_influence_weight DESC);

        CREATE INDEX IF NOT EXISTS idx_wallet_event_influence_wallet
        ON wallet_event_influence(wallet, wallet_allocation_pct DESC);

        CREATE TABLE IF NOT EXISTS wallet_influence_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            wallets_scored INTEGER NOT NULL,
            event_profiles_scored INTEGER NOT NULL,
            total_capital_analyzed REAL NOT NULL,
            source_event_profiles INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


@dataclass
class EventProfile:
    event_id: str
    wallet: str
    category: str
    position_count: int
    capital: float
    conviction: float
    expertise: float


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        number = float(value)
        if not math.isfinite(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    n = len(ordered)
    if n == 1:
        return {ordered[0][0]: 100.0}

    result: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        average_index = (i + j) / 2.0
        percentile = 100.0 * average_index / (n - 1)
        for k in range(i, j + 1):
            result[ordered[k][0]] = percentile
        i = j + 1
    return result


def weighted_average(values: list[tuple[float, float]]) -> float:
    denominator = sum(max(0.0, weight) for _, weight in values)
    if denominator <= 0:
        return statistics.fmean(value for value, _ in values) if values else 0.0
    return sum(value * max(0.0, weight) for value, weight in values) / denominator


def normalized_entropy(shares: list[float]) -> float:
    positive = [share for share in shares if share > 0]
    if len(positive) <= 1:
        return 0.0
    total = sum(positive)
    probabilities = [share / total for share in positive]
    entropy = -sum(p * math.log(p) for p in probabilities)
    return entropy / math.log(len(probabilities))


def influence_grade(percentile: float) -> str:
    if percentile >= 99.5:
        return "TITAN"
    if percentile >= 98.0:
        return "INSTITUTIONAL"
    if percentile >= 90.0:
        return "ELITE"
    if percentile >= 75.0:
        return "PROFESSIONAL"
    return "STANDARD"


def load_profiles(connection: sqlite3.Connection) -> list[EventProfile]:
    if not table_exists(connection, "wallet_event_exposure"):
        raise RuntimeError(
            "wallet_event_exposure is missing. Run python -m src.market_graph_engine first."
        )

    columns = table_columns(connection, "wallet_event_exposure")
    required = {"event_id", "wallet", "category", "position_count"}
    missing = required - columns
    if missing:
        raise RuntimeError(
            "wallet_event_exposure is missing required columns: " + ", ".join(sorted(missing))
        )

    capital_col = first_present(
        columns,
        ("total_capital_committed", "total_current_value", "total_shares"),
    )
    conviction_col = first_present(columns, ("event_conviction_score",))
    expertise_col = first_present(columns, ("expertise_influence_weight",))

    if not capital_col:
        raise RuntimeError("No capital-compatible column found in wallet_event_exposure.")

    query = f"""
        SELECT
            event_id,
            wallet,
            category,
            position_count,
            {quote_identifier(capital_col)} AS capital,
            {quote_identifier(conviction_col) if conviction_col else '0'} AS conviction,
            {quote_identifier(expertise_col) if expertise_col else '0'} AS expertise
        FROM wallet_event_exposure
        WHERE wallet IS NOT NULL AND TRIM(wallet) <> ''
    """

    profiles: list[EventProfile] = []
    for row in connection.execute(query).fetchall():
        profiles.append(
            EventProfile(
                event_id=str(row["event_id"]),
                wallet=str(row["wallet"]).lower(),
                category=str(row["category"] or "OTHER").upper(),
                position_count=int(safe_float(row["position_count"])),
                capital=max(0.0, safe_float(row["capital"])),
                conviction=clamp(safe_float(row["conviction"])),
                expertise=clamp(safe_float(row["expertise"]) * 100.0 if safe_float(row["expertise"]) <= 1.0 else safe_float(row["expertise"])),
            )
        )
    return profiles


def build_wallet_metrics(profiles: list[EventProfile]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[EventProfile]] = defaultdict(list)
    for profile in profiles:
        grouped[profile.wallet].append(profile)

    raw_capital = {
        wallet: sum(profile.capital for profile in rows)
        for wallet, rows in grouped.items()
    }
    log_capital = {
        wallet: math.log1p(capital)
        for wallet, capital in raw_capital.items()
    }
    capital_percentiles = percentile_ranks(log_capital)

    metrics: dict[str, dict[str, Any]] = {}
    for wallet, rows in grouped.items():
        event_capitals = [row.capital for row in rows]
        total_capital = sum(event_capitals)
        category_capital: dict[str, float] = defaultdict(float)
        for row in rows:
            category_capital[row.category] += row.capital

        if total_capital > 0:
            category_shares = {
                category: capital / total_capital
                for category, capital in category_capital.items()
            }
            event_shares = [capital / total_capital for capital in event_capitals if capital > 0]
        else:
            counts = Counter(row.category for row in rows)
            total_count = sum(counts.values()) or 1
            category_shares = {
                category: count / total_count
                for category, count in counts.items()
            }
            event_shares = [1.0 / len(rows)] * len(rows) if rows else []

        primary_category, primary_share = max(
            category_shares.items(), key=lambda item: item[1]
        ) if category_shares else ("OTHER", 0.0)

        hhi = sum(share * share for share in event_shares)
        concentration_risk = clamp(hhi * 100.0)
        diversification = clamp(normalized_entropy(event_shares) * 100.0)
        specialization = clamp(primary_share * 100.0)

        avg_conviction = statistics.fmean(row.conviction for row in rows) if rows else 0.0
        weighted_conviction = weighted_average(
            [(row.conviction, max(row.capital, 1.0)) for row in rows]
        )
        expertise = weighted_average(
            [(row.expertise, max(row.capital, 1.0)) for row in rows]
        )

        allocations = [share * 100.0 for share in event_shares]
        median_allocation = statistics.median(allocations) if allocations else 0.0
        top_allocation = max(allocations) if allocations else 0.0
        allocation_intensity = clamp(
            0.65 * min(100.0, median_allocation * 8.0)
            + 0.35 * min(100.0, top_allocation * 2.0)
        )

        convictions = [row.conviction for row in rows]
        conviction_spread = statistics.pstdev(convictions) if len(convictions) > 1 else 0.0
        sample_score = min(100.0, 25.0 * math.log1p(len(rows)))
        consistency = clamp(
            0.55 * (100.0 - min(100.0, conviction_spread * 2.0))
            + 0.45 * sample_score
        )

        capital_score = capital_percentiles.get(wallet, 0.0)
        data_quality = clamp(
            45.0
            + min(25.0, len(rows) * 2.5)
            + (20.0 if total_capital > 0 else 0.0)
            + (10.0 if expertise > 0 else 0.0)
        )

        # Capital is deliberately limited to 20%. Expertise and repeatable
        # conviction matter more than absolute wallet size.
        influence = clamp(
            0.27 * expertise
            + 0.23 * weighted_conviction
            + 0.20 * capital_score
            + 0.12 * consistency
            + 0.10 * allocation_intensity
            + 0.08 * specialization
            - 0.08 * max(0.0, concentration_risk - 70.0)
        )

        metrics[wallet] = {
            "wallet": wallet,
            "event_count": len(rows),
            "position_count": sum(row.position_count for row in rows),
            "category_count": len(category_shares),
            "total_capital_committed": total_capital,
            "median_event_capital": statistics.median(event_capitals) if event_capitals else 0.0,
            "largest_event_capital": max(event_capitals) if event_capitals else 0.0,
            "average_event_conviction": avg_conviction,
            "weighted_event_conviction": weighted_conviction,
            "expertise_score": expertise,
            "capital_score": capital_score,
            "allocation_intensity_score": allocation_intensity,
            "specialization_score": specialization,
            "consistency_score": consistency,
            "diversification_score": diversification,
            "concentration_risk_score": concentration_risk,
            "influence_score": influence,
            "primary_category": primary_category,
            "primary_category_share": primary_share,
            "category_distribution_json": json.dumps(
                dict(sorted(category_shares.items(), key=lambda item: item[1], reverse=True)),
                sort_keys=True,
            ),
            "data_quality_score": data_quality,
        }

    score_percentiles = percentile_ranks(
        {wallet: metric["influence_score"] for wallet, metric in metrics.items()}
    )
    for wallet, metric in metrics.items():
        percentile = score_percentiles.get(wallet, 0.0)
        metric["influence_percentile"] = percentile
        metric["influence_grade"] = influence_grade(percentile)
    return metrics


def write_wallet_metrics(
    connection: sqlite3.Connection,
    metrics: dict[str, dict[str, Any]],
) -> None:
    now = utc_now()
    connection.execute("DELETE FROM wallet_influence")
    connection.executemany(
        """
        INSERT INTO wallet_influence (
            wallet, event_count, position_count, category_count,
            total_capital_committed, median_event_capital, largest_event_capital,
            average_event_conviction, weighted_event_conviction, expertise_score,
            capital_score, allocation_intensity_score, specialization_score,
            consistency_score, diversification_score, concentration_risk_score,
            influence_score, influence_percentile, influence_grade,
            primary_category, primary_category_share, category_distribution_json,
            data_quality_score, engine_version, updated_at
        ) VALUES (
            :wallet, :event_count, :position_count, :category_count,
            :total_capital_committed, :median_event_capital, :largest_event_capital,
            :average_event_conviction, :weighted_event_conviction, :expertise_score,
            :capital_score, :allocation_intensity_score, :specialization_score,
            :consistency_score, :diversification_score, :concentration_risk_score,
            :influence_score, :influence_percentile, :influence_grade,
            :primary_category, :primary_category_share, :category_distribution_json,
            :data_quality_score, :engine_version, :updated_at
        )
        """,
        [
            {
                **metric,
                "engine_version": ENGINE_VERSION,
                "updated_at": now,
            }
            for metric in metrics.values()
        ],
    )


def write_event_influence(
    connection: sqlite3.Connection,
    profiles: list[EventProfile],
    metrics: dict[str, dict[str, Any]],
) -> int:
    now = utc_now()
    event_capital: dict[str, float] = defaultdict(float)
    for profile in profiles:
        event_capital[profile.event_id] += profile.capital

    provisional: list[dict[str, Any]] = []
    event_weight_totals: dict[str, float] = defaultdict(float)

    for profile in profiles:
        metric = metrics[profile.wallet]
        wallet_total = max(metric["total_capital_committed"], 0.0)
        allocation_pct = 100.0 * profile.capital / wallet_total if wallet_total > 0 else 0.0
        event_share = 100.0 * profile.capital / event_capital[profile.event_id] if event_capital[profile.event_id] > 0 else 0.0

        # Allocation is capped so one all-in position cannot create unbounded weight.
        allocation_multiplier = 0.75 + min(0.75, math.sqrt(max(0.0, allocation_pct) / 25.0) * 0.75)
        expertise_multiplier = 0.70 + 0.60 * (profile.expertise / 100.0)
        conviction_multiplier = 0.70 + 0.60 * (profile.conviction / 100.0)
        event_weight = (
            metric["influence_score"]
            * allocation_multiplier
            * expertise_multiplier
            * conviction_multiplier
        )
        event_weight_totals[profile.event_id] += event_weight
        provisional.append(
            {
                "event_id": profile.event_id,
                "wallet": profile.wallet,
                "category": profile.category,
                "capital_committed": profile.capital,
                "wallet_total_capital": wallet_total,
                "wallet_allocation_pct": allocation_pct,
                "event_capital_share": event_share,
                "event_conviction_score": profile.conviction,
                "expertise_weight": profile.expertise,
                "base_influence_score": metric["influence_score"],
                "allocation_multiplier": allocation_multiplier,
                "event_influence_weight": event_weight,
                "influence_grade": metric["influence_grade"],
            }
        )

    connection.execute("DELETE FROM wallet_event_influence")
    rows = []
    for item in provisional:
        total_weight = event_weight_totals[item["event_id"]]
        item["event_influence_share"] = (
            100.0 * item["event_influence_weight"] / total_weight
            if total_weight > 0 else 0.0
        )
        item["updated_at"] = now
        rows.append(item)

    connection.executemany(
        """
        INSERT INTO wallet_event_influence (
            event_id, wallet, category, capital_committed, wallet_total_capital,
            wallet_allocation_pct, event_capital_share, event_conviction_score,
            expertise_weight, base_influence_score, allocation_multiplier,
            event_influence_weight, event_influence_share, influence_grade, updated_at
        ) VALUES (
            :event_id, :wallet, :category, :capital_committed, :wallet_total_capital,
            :wallet_allocation_pct, :event_capital_share, :event_conviction_score,
            :expertise_weight, :base_influence_score, :allocation_multiplier,
            :event_influence_weight, :event_influence_share, :influence_grade, :updated_at
        )
        """,
        rows,
    )
    return len(rows)


def print_report(
    connection: sqlite3.Connection,
    wallets_scored: int,
    profiles_scored: int,
    total_capital: float,
    run_id: str,
) -> None:
    print("\n" + "=" * 122)
    print("WALLET INFLUENCE ENGINE COMPLETE")
    print("=" * 122)
    print(f"Database: {DATABASE_PATH}")
    print(f"Wallets scored: {wallets_scored}")
    print(f"Wallet-event profiles scored: {profiles_scored}")
    print(f"Historical capital analyzed: ${total_capital:,.2f}")
    print(f"Run ID: {run_id}")

    print("\nInfluence grade distribution:")
    for row in connection.execute(
        """
        SELECT influence_grade, COUNT(*) AS total
        FROM wallet_influence
        GROUP BY influence_grade
        ORDER BY CASE influence_grade
            WHEN 'TITAN' THEN 1
            WHEN 'INSTITUTIONAL' THEN 2
            WHEN 'ELITE' THEN 3
            WHEN 'PROFESSIONAL' THEN 4
            ELSE 5 END
        """
    ).fetchall():
        print(f"  {row['influence_grade']:<16} {row['total']:>6}")

    print("\nTop wallet influence profiles:")
    rows = connection.execute(
        """
        SELECT
            wallet, influence_grade, influence_score, influence_percentile,
            primary_category, primary_category_share, event_count,
            total_capital_committed, capital_score, expertise_score,
            weighted_event_conviction, concentration_risk_score
        FROM wallet_influence
        ORDER BY influence_score DESC, total_capital_committed DESC
        LIMIT 20
        """
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        print(
            f"{index:>2}. {row['wallet']} | {row['influence_grade']:<13} "
            f"| influence={row['influence_score']:>6.2f} "
            f"| pct={row['influence_percentile']:>6.2f} "
            f"| category={str(row['primary_category']):<12} "
            f"| specialization={100.0 * row['primary_category_share']:>6.2f}% "
            f"| events={row['event_count']:>4} "
            f"| capital=${row['total_capital_committed']:>13,.2f} "
            f"| expertise={row['expertise_score']:>6.2f} "
            f"| conviction={row['weighted_event_conviction']:>6.2f} "
            f"| concentration_risk={row['concentration_risk_score']:>6.2f}"
        )

    print("\nHighest-conviction wallet allocations:")
    rows = connection.execute(
        """
        SELECT
            e.event_name, wei.wallet, wei.influence_grade,
            wei.wallet_allocation_pct, wei.event_capital_share,
            wei.event_influence_share, wei.capital_committed,
            wei.event_conviction_score
        FROM wallet_event_influence wei
        JOIN market_events e ON e.event_id = wei.event_id
        ORDER BY wei.wallet_allocation_pct DESC, wei.event_influence_weight DESC
        LIMIT 25
        """
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        print(
            f"{index:>2}. {str(row['event_name'])[:52]:<52} "
            f"| {row['wallet']} | {row['influence_grade']:<13} "
            f"| wallet_alloc={row['wallet_allocation_pct']:>7.3f}% "
            f"| event_capital={row['event_capital_share']:>7.2f}% "
            f"| influence_share={row['event_influence_share']:>7.2f}% "
            f"| capital=${row['capital_committed']:>12,.2f} "
            f"| conviction={row['event_conviction_score']:>6.2f}"
        )

    print("\nNext command:")
    print("  python -m src.wallet_influence_engine 2>&1 | Tee-Object -FilePath wallet_influence_output.txt")


def run() -> None:
    run_id = "wallet_influence_run:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    with connect_database() as connection:
        ensure_schema(connection)
        profiles = load_profiles(connection)
        if not profiles:
            raise RuntimeError("No wallet-event profiles were found to score.")

        metrics = build_wallet_metrics(profiles)
        write_wallet_metrics(connection, metrics)
        event_profiles_scored = write_event_influence(connection, profiles, metrics)
        total_capital = sum(profile.capital for profile in profiles)

        connection.execute(
            """
            INSERT INTO wallet_influence_runs (
                run_id, engine_version, wallets_scored, event_profiles_scored,
                total_capital_analyzed, source_event_profiles, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                ENGINE_VERSION,
                len(metrics),
                event_profiles_scored,
                total_capital,
                len(profiles),
                utc_now(),
            ),
        )
        connection.commit()
        print_report(
            connection,
            wallets_scored=len(metrics),
            profiles_scored=event_profiles_scored,
            total_capital=total_capital,
            run_id=run_id,
        )


if __name__ == "__main__":
    run()