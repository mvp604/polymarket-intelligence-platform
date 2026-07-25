from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def normalize_text(value: str | None) -> str:
    text = (value or "").lower().replace("–", "-").replace("—", "-").replace("’", "'")
    text = re.sub(r"[^a-z0-9\s.+/'&:?-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) == 1:
        return {ordered[0][0]: 100.0}
    result: dict[str, float] = {}
    i = 0
    n = len(ordered)
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        percentile = 100.0 * ((i + j) / 2.0) / (n - 1)
        for k in range(i, j + 1):
            result[ordered[k][0]] = percentile
        i = j + 1
    return result


def grade_from_percentile(percentile: float, confidence: float) -> str:
    # Confidence gate prevents tiny samples from receiving inflated specialist labels.
    if confidence < 35:
        return "UNPROVEN"
    if percentile >= 99.5 and confidence >= 80:
        return "TITAN"
    if percentile >= 98 and confidence >= 70:
        return "INSTITUTIONAL"
    if percentile >= 90 and confidence >= 60:
        return "ELITE"
    if percentile >= 75 and confidence >= 50:
        return "PROFESSIONAL"
    return "STANDARD"


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_domain_classification (
            condition_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            market_title TEXT NOT NULL,
            original_category TEXT NOT NULL,
            domain TEXT NOT NULL,
            subdomain TEXT NOT NULL,
            competition_family TEXT,
            classification_confidence REAL NOT NULL,
            classification_method TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES market_events(event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_market_domain_domain
        ON market_domain_classification(domain, subdomain);

        CREATE TABLE IF NOT EXISTS wallet_domain_profiles (
            wallet TEXT NOT NULL,
            domain TEXT NOT NULL,
            subdomain TEXT NOT NULL,
            event_count INTEGER NOT NULL,
            market_count INTEGER NOT NULL,
            position_count INTEGER NOT NULL,
            total_capital_committed REAL NOT NULL,
            average_event_capital REAL NOT NULL,
            largest_event_capital REAL NOT NULL,
            average_event_conviction REAL NOT NULL,
            capital_weighted_conviction REAL NOT NULL,
            average_expertise_weight REAL NOT NULL,
            global_influence_score REAL NOT NULL,
            domain_share REAL NOT NULL,
            sample_confidence REAL NOT NULL,
            domain_score REAL NOT NULL,
            domain_percentile REAL NOT NULL,
            domain_rank INTEGER NOT NULL,
            domain_grade TEXT NOT NULL,
            favorite_market_types_json TEXT NOT NULL,
            favorite_events_json TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(wallet, domain, subdomain)
        );

        CREATE INDEX IF NOT EXISTS idx_wallet_domain_leaderboard
        ON wallet_domain_profiles(domain, subdomain, domain_score DESC);

        CREATE INDEX IF NOT EXISTS idx_wallet_domain_wallet
        ON wallet_domain_profiles(wallet, domain_score DESC);

        CREATE TABLE IF NOT EXISTS domain_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            markets_classified INTEGER NOT NULL,
            wallet_domain_profiles INTEGER NOT NULL,
            wallets_analyzed INTEGER NOT NULL,
            domains_found INTEGER NOT NULL,
            reclassified_from_other INTEGER NOT NULL,
            total_capital_analyzed REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


SOCCER_TEAMS = {
    "argentina", "australia", "belgium", "brazil", "canada", "colombia", "cote d'ivoire",
    "curacao", "ecuador", "england", "france", "germany", "ghana", "iran", "japan",
    "korea republic", "mexico", "morocco", "netherlands", "new zealand", "norway",
    "panama", "paraguay", "portugal", "saudi arabia", "senegal", "spain", "sweden",
    "switzerland", "united states", "uruguay", "dr congo"
}

BASEBALL_TEAMS = {
    "athletics", "angels", "astros", "blue jays", "braves", "brewers", "cardinals",
    "cubs", "diamondbacks", "dodgers", "giants", "guardians", "mariners", "marlins",
    "mets", "nationals", "orioles", "padres", "phillies", "pirates", "rangers",
    "rays", "red sox", "reds", "rockies", "royals", "tigers", "twins", "white sox",
    "yankees"
}

BASKETBALL_TEAMS = {
    "celtics", "bulls", "cavaliers", "clippers", "fever", "knicks", "lakers", "liberty",
    "mavericks", "mystics", "pacers", "raptors", "spurs", "suns", "thunder", "timberwolves",
    "valkyries", "warriors"
}


def contains_any(text: str, values: set[str]) -> bool:
    return any(value in text for value in values)


def classify_market(title: str, original_category: str, market_type: str) -> tuple[str, str, str | None, float, str]:
    text = normalize_text(title)
    original = (original_category or "OTHER").upper()
    market_type = (market_type or "UNKNOWN").upper()

    # Domain detection: trust known sports labels first, then recover sports hidden in OTHER.
    if original == "SOCCER" or contains_any(text, SOCCER_TEAMS) or "fifa world cup" in text:
        domain = "SOCCER"
    elif original == "BASEBALL" or contains_any(text, BASEBALL_TEAMS) or "mlb" in text:
        domain = "BASEBALL"
    elif original == "BASKETBALL" or contains_any(text, BASKETBALL_TEAMS) or "nba" in text or "wnba" in text:
        domain = "BASKETBALL"
    elif original == "MMA" or "ufc" in text or any(x in text for x in ("knockout", "submission", "rounds", "goes the distance")):
        domain = "MMA"
    elif original == "HOCKEY" or "nhl" in text or "puck line" in text:
        domain = "HOCKEY"
    elif original == "TENNIS" or any(x in text for x in ("aces", "double faults", "sets")):
        domain = "TENNIS"
    elif original == "AMERICAN_FOOTBALL" or "nfl" in text or any(x in text for x in ("passing yards", "rushing yards", "receiving yards")):
        domain = "AMERICAN_FOOTBALL"
    elif original == "GEOPOLITICS" or any(x in text for x in ("president", "election", "nomination", "prime minister", "government", "ceasefire", "war")):
        domain = "POLITICS_GEOPOLITICS"
    elif any(x in text for x in ("bitcoin", "ethereum", "crypto", "btc", "eth")):
        domain = "CRYPTO"
    else:
        domain = "OTHER"

    # Subdomain detection.
    if domain in {"SOCCER", "BASEBALL", "BASKETBALL", "HOCKEY", "AMERICAN_FOOTBALL", "TENNIS"}:
        if any(x in text for x in ("win the 2026 fifa world cup", "win the world cup", "champion", "win the league", "win the tournament")):
            subdomain = "OUTRIGHT"
        elif any(x in text for x in ("will ", " end in a draw")) and " vs " not in text and "win on" in text:
            subdomain = "MATCH_WINNER"
        elif "end in a draw" in text:
            subdomain = "DRAW_MARKET"
        elif market_type == "PLAYER_PROP":
            subdomain = "PLAYER_PROP"
        elif market_type in {"TOTAL", "TEAM_TOTAL", "FIRST_HALF_TOTAL", "TOTAL_CORNERS"}:
            subdomain = "TOTALS"
        elif market_type == "SPREAD":
            subdomain = "SPREAD"
        elif market_type in {"MONEYLINE", "TEAM_TO_ADVANCE"}:
            subdomain = "MATCH_WINNER"
        else:
            subdomain = "MATCH_MARKET"
    elif domain == "MMA":
        if market_type == "FIGHT_ROUNDS" or "rounds" in text:
            subdomain = "ROUNDS"
        elif market_type == "GOES_DISTANCE" or "distance" in text:
            subdomain = "GOES_DISTANCE"
        elif any(x in text for x in ("knockout", "submission", "method of victory")):
            subdomain = "METHOD_OF_VICTORY"
        else:
            subdomain = "FIGHT_WINNER"
    elif domain == "POLITICS_GEOPOLITICS":
        subdomain = "ELECTION" if any(x in text for x in ("election", "nomination", "president", "prime minister")) else "GEOPOLITICS"
    elif domain == "CRYPTO":
        subdomain = "PRICE_MARKET" if any(x in text for x in ("price", "above", "below", "reach")) else "CRYPTO_EVENT"
    else:
        subdomain = "UNCLASSIFIED"

    competition: str | None = None
    if "fifa world cup" in text or "world cup" in text:
        competition = "FIFA_WORLD_CUP"
    elif "ufc" in text:
        competition = "UFC"
    elif domain == "BASEBALL":
        competition = "MLB"
    elif domain == "BASKETBALL":
        competition = "WNBA" if any(x in text for x in ("mystics", "fever", "liberty", "valkyries")) else "NBA_OR_BASKETBALL"

    recovered = original == "OTHER" and domain != "OTHER"
    confidence = 0.97 if original == domain else (0.90 if recovered else 0.65)
    method = "ORIGINAL_CATEGORY" if original == domain else ("TITLE_RECOVERY" if recovered else "FALLBACK")
    return domain, subdomain, competition, confidence, method


@dataclass
class MarketRow:
    condition_id: str
    event_id: str
    title: str
    original_category: str
    market_type: str


@dataclass
class ExposureRow:
    event_id: str
    wallet: str
    position_count: int
    capital: float
    conviction: float
    expertise: float


def load_markets(connection: sqlite3.Connection) -> list[MarketRow]:
    if not table_exists(connection, "market_event_links"):
        raise RuntimeError("market_event_links is missing. Run market_graph_engine first.")
    return [
        MarketRow(
            condition_id=str(row["condition_id"]),
            event_id=str(row["event_id"]),
            title=str(row["market_title"] or ""),
            original_category=str(row["category"] or "OTHER").upper(),
            market_type=str(row["market_type"] or "UNKNOWN").upper(),
        )
        for row in connection.execute(
            "SELECT condition_id, event_id, market_title, category, market_type FROM market_event_links"
        ).fetchall()
    ]


def load_exposures(connection: sqlite3.Connection) -> list[ExposureRow]:
    if not table_exists(connection, "wallet_event_exposure"):
        raise RuntimeError("wallet_event_exposure is missing. Run market_graph_engine first.")
    return [
        ExposureRow(
            event_id=str(row["event_id"]),
            wallet=str(row["wallet"]).lower(),
            position_count=int(safe_float(row["position_count"])),
            capital=max(0.0, safe_float(row["total_capital_committed"])),
            conviction=clamp(safe_float(row["event_conviction_score"])),
            expertise=clamp(safe_float(row["expertise_influence_weight"]) * 100.0),
        )
        for row in connection.execute(
            """
            SELECT event_id, wallet, position_count, total_capital_committed,
                   event_conviction_score, expertise_influence_weight
            FROM wallet_event_exposure
            WHERE wallet IS NOT NULL AND TRIM(wallet) <> ''
            """
        ).fetchall()
    ]


def run_engine() -> None:
    connection = connect_database()
    ensure_schema(connection)
    now = utc_now()
    run_id = "domain_intelligence_run:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    markets = load_markets(connection)
    exposures = load_exposures(connection)

    classifications: dict[str, tuple[str, str, str | None, float, str]] = {}
    event_domains: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    event_market_types: dict[str, Counter[str]] = defaultdict(Counter)
    event_titles: dict[str, Counter[str]] = defaultdict(Counter)
    reclassified = 0

    with connection:
        connection.execute("DELETE FROM market_domain_classification")
        connection.execute("DELETE FROM wallet_domain_profiles")

        for market in markets:
            classified = classify_market(market.title, market.original_category, market.market_type)
            classifications[market.condition_id] = classified
            domain, subdomain, competition, confidence, method = classified
            event_domains[market.event_id][(domain, subdomain)] += 1
            event_market_types[market.event_id][market.market_type] += 1
            event_titles[market.event_id][market.title] += 1
            if market.original_category == "OTHER" and domain != "OTHER":
                reclassified += 1

            connection.execute(
                """
                INSERT INTO market_domain_classification (
                    condition_id, event_id, market_title, original_category, domain,
                    subdomain, competition_family, classification_confidence,
                    classification_method, engine_version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    market.condition_id, market.event_id, market.title,
                    market.original_category, domain, subdomain, competition,
                    confidence, method, ENGINE_VERSION, now,
                ),
            )

        global_influence = {
            str(row["wallet"]).lower(): safe_float(row["influence_score"])
            for row in connection.execute(
                "SELECT wallet, influence_score FROM wallet_influence"
            ).fetchall()
        } if table_exists(connection, "wallet_influence") else {}

        wallet_totals: dict[str, float] = defaultdict(float)
        grouped: dict[tuple[str, str, str], list[ExposureRow]] = defaultdict(list)
        for exposure in exposures:
            wallet_totals[exposure.wallet] += exposure.capital
            domain_counter = event_domains.get(exposure.event_id)
            if not domain_counter:
                domain, subdomain = "OTHER", "UNCLASSIFIED"
            else:
                (domain, subdomain), _ = domain_counter.most_common(1)[0]
            grouped[(exposure.wallet, domain, subdomain)].append(exposure)

        raw_scores: dict[tuple[str, str, str], float] = {}
        aggregates: dict[tuple[str, str, str], dict[str, Any]] = {}

        for key, rows in grouped.items():
            wallet, domain, subdomain = key
            capitals = [r.capital for r in rows]
            total_capital = sum(capitals)
            event_count = len({r.event_id for r in rows})
            position_count = sum(r.position_count for r in rows)
            domain_share = total_capital / wallet_totals[wallet] if wallet_totals[wallet] > 0 else 0.0
            weighted_conviction = (
                sum(r.conviction * max(r.capital, 1.0) for r in rows) /
                sum(max(r.capital, 1.0) for r in rows)
            )
            avg_conviction = sum(r.conviction for r in rows) / len(rows)
            avg_expertise = sum(r.expertise for r in rows) / len(rows)
            sample_confidence = clamp(
                100.0 * (1.0 - math.exp(-event_count / 15.0)) *
                (0.65 + 0.35 * min(1.0, position_count / 40.0))
            )
            capital_depth = clamp(18.0 * math.log10(1.0 + total_capital))
            specialization = clamp(domain_share * 100.0)
            global_score = global_influence.get(wallet, 45.0)

            domain_score = clamp(
                0.30 * weighted_conviction +
                0.23 * avg_expertise +
                0.17 * global_score +
                0.12 * specialization +
                0.10 * sample_confidence +
                0.08 * capital_depth
            )

            raw_scores[key] = domain_score
            aggregates[key] = {
                "wallet": wallet,
                "domain": domain,
                "subdomain": subdomain,
                "event_count": event_count,
                "market_count": sum(event_domains[r.event_id][(domain, subdomain)] for r in rows),
                "position_count": position_count,
                "total_capital": total_capital,
                "average_event_capital": total_capital / event_count if event_count else 0.0,
                "largest_event_capital": max(capitals) if capitals else 0.0,
                "average_event_conviction": avg_conviction,
                "weighted_conviction": weighted_conviction,
                "average_expertise": avg_expertise,
                "global_score": global_score,
                "domain_share": domain_share,
                "sample_confidence": sample_confidence,
                "domain_score": domain_score,
                "market_types": Counter({
                    market_type: sum(event_market_types[r.event_id][market_type] for r in rows)
                    for market_type in set().union(*(event_market_types[r.event_id].keys() for r in rows))
                }),
                "events": Counter({
                    title: sum(event_titles[r.event_id][title] for r in rows)
                    for title in set().union(*(event_titles[r.event_id].keys() for r in rows))
                }),
            }

        # Percentiles are calculated within each domain/subdomain leaderboard.
        leaderboard_groups: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        for (wallet, domain, subdomain), score in raw_scores.items():
            leaderboard_groups[(domain, subdomain)][wallet] = score

        percentiles: dict[tuple[str, str, str], float] = {}
        ranks: dict[tuple[str, str, str], int] = {}
        for (domain, subdomain), values in leaderboard_groups.items():
            pct = percentile_ranks(values)
            ordered_wallets = sorted(values, key=lambda wallet: (-values[wallet], wallet))
            for rank, wallet in enumerate(ordered_wallets, start=1):
                percentiles[(wallet, domain, subdomain)] = pct[wallet]
                ranks[(wallet, domain, subdomain)] = rank

        for key, data in aggregates.items():
            pct = percentiles[key]
            rank = ranks[key]
            grade = grade_from_percentile(pct, data["sample_confidence"])
            favorite_market_types = data["market_types"].most_common(5)
            favorite_events = data["events"].most_common(5)

            connection.execute(
                """
                INSERT INTO wallet_domain_profiles (
                    wallet, domain, subdomain, event_count, market_count, position_count,
                    total_capital_committed, average_event_capital, largest_event_capital,
                    average_event_conviction, capital_weighted_conviction,
                    average_expertise_weight, global_influence_score, domain_share,
                    sample_confidence, domain_score, domain_percentile, domain_rank,
                    domain_grade, favorite_market_types_json, favorite_events_json,
                    engine_version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["wallet"], data["domain"], data["subdomain"], data["event_count"],
                    data["market_count"], data["position_count"], data["total_capital"],
                    data["average_event_capital"], data["largest_event_capital"],
                    data["average_event_conviction"], data["weighted_conviction"],
                    data["average_expertise"], data["global_score"], data["domain_share"],
                    data["sample_confidence"], data["domain_score"], pct, rank, grade,
                    json.dumps(favorite_market_types), json.dumps(favorite_events),
                    ENGINE_VERSION, now,
                ),
            )

        connection.execute(
            """
            INSERT INTO domain_intelligence_runs (
                run_id, engine_version, markets_classified, wallet_domain_profiles,
                wallets_analyzed, domains_found, reclassified_from_other,
                total_capital_analyzed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, ENGINE_VERSION, len(markets), len(aggregates), len(wallet_totals),
                len({data["domain"] for data in aggregates.values()}), reclassified,
                sum(wallet_totals.values()), now,
            ),
        )

    print("=" * 122)
    print("DOMAIN INTELLIGENCE ENGINE COMPLETE")
    print("=" * 122)
    print(f"Database: {DATABASE_PATH}")
    print(f"Markets classified: {len(markets)}")
    print(f"Markets recovered from OTHER: {reclassified}")
    print(f"Wallet-domain profiles: {len(aggregates)}")
    print(f"Wallets analyzed: {len(wallet_totals)}")
    print(f"Historical capital analyzed: ${sum(wallet_totals.values()):,.2f}")
    print(f"Run ID: {run_id}")

    print("\nDomain distribution:")
    domain_counts = Counter(classified[0] for classified in classifications.values())
    for domain, count in domain_counts.most_common():
        print(f"  {domain:<24} {count:>6}")

    print("\nTop domain specialists:")
    rows = connection.execute(
        """
        SELECT wallet, domain, subdomain, domain_grade, domain_rank,
               domain_score, domain_percentile, sample_confidence,
               total_capital_committed, event_count, domain_share
        FROM wallet_domain_profiles
        ORDER BY domain_score DESC, total_capital_committed DESC
        LIMIT 30
        """
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        print(
            f"{index:>2}. {row['wallet']} | {row['domain']}/{row['subdomain']} | "
            f"{row['domain_grade']:<12} | rank={row['domain_rank']:>2} | "
            f"score={row['domain_score']:>6.2f} | pct={row['domain_percentile']:>6.2f} | "
            f"confidence={row['sample_confidence']:>6.2f} | events={row['event_count']:>3} | "
            f"share={row['domain_share']*100:>6.2f}% | capital=${row['total_capital_committed']:>12,.2f}"
        )

    print("\nNext command:")
    print("  python -m src.domain_intelligence_engine 2>&1 | Tee-Object -FilePath domain_intelligence_output.txt")
    connection.close()


if __name__ == "__main__":
    run_engine()