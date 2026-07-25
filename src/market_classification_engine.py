from __future__ import annotations

import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
RULE_VERSION = "2.0"

MANUAL_OVERRIDE_METHOD = "manual_override"
MIN_CONFIDENCE_TO_REPLACE = 0.55


# Exact-name knowledge bases. These are intentionally transparent and easy
# to expand. Matching is case-insensitive and uses normalized text.
MLB_TEAMS = {
    "arizona diamondbacks", "atlanta braves", "baltimore orioles",
    "boston red sox", "chicago cubs", "chicago white sox",
    "cincinnati reds", "cleveland guardians", "colorado rockies",
    "detroit tigers", "houston astros", "kansas city royals",
    "los angeles angels", "los angeles dodgers", "miami marlins",
    "milwaukee brewers", "minnesota twins", "new york mets",
    "new york yankees", "oakland athletics", "athletics",
    "philadelphia phillies", "pittsburgh pirates", "san diego padres",
    "san francisco giants", "seattle mariners", "st. louis cardinals",
    "st louis cardinals", "tampa bay rays", "texas rangers",
    "toronto blue jays", "washington nationals",
}

NBA_TEAMS = {
    "atlanta hawks", "boston celtics", "brooklyn nets",
    "charlotte hornets", "chicago bulls", "cleveland cavaliers",
    "dallas mavericks", "denver nuggets", "detroit pistons",
    "golden state warriors", "houston rockets", "indiana pacers",
    "los angeles clippers", "la clippers", "los angeles lakers",
    "memphis grizzlies", "miami heat", "milwaukee bucks",
    "minnesota timberwolves", "new orleans pelicans",
    "new york knicks", "oklahoma city thunder", "orlando magic",
    "philadelphia 76ers", "phoenix suns", "portland trail blazers",
    "sacramento kings", "san antonio spurs", "toronto raptors",
    "utah jazz", "washington wizards",
}

WNBA_TEAMS = {
    "atlanta dream", "chicago sky", "connecticut sun",
    "dallas wings", "golden state valkyries", "indiana fever",
    "las vegas aces", "los angeles sparks", "minnesota lynx",
    "new york liberty", "phoenix mercury", "seattle storm",
    "washington mystics", "toronto tempo",
}

NHL_TEAMS = {
    "anaheim ducks", "boston bruins", "buffalo sabres",
    "calgary flames", "carolina hurricanes", "chicago blackhawks",
    "colorado avalanche", "columbus blue jackets", "dallas stars",
    "detroit red wings", "edmonton oilers", "florida panthers",
    "los angeles kings", "minnesota wild", "montreal canadiens",
    "nashville predators", "new jersey devils", "new york islanders",
    "new york rangers", "ottawa senators", "philadelphia flyers",
    "pittsburgh penguins", "san jose sharks", "seattle kraken",
    "st. louis blues", "st louis blues", "tampa bay lightning",
    "toronto maple leafs", "utah mammoth", "vancouver canucks",
    "vegas golden knights", "washington capitals", "winnipeg jets",
}

NFL_TEAMS = {
    "arizona cardinals", "atlanta falcons", "baltimore ravens",
    "buffalo bills", "carolina panthers", "chicago bears",
    "cincinnati bengals", "cleveland browns", "dallas cowboys",
    "denver broncos", "detroit lions", "green bay packers",
    "houston texans", "indianapolis colts", "jacksonville jaguars",
    "kansas city chiefs", "las vegas raiders", "los angeles chargers",
    "la chargers", "los angeles rams", "la rams", "miami dolphins",
    "minnesota vikings", "new england patriots", "new orleans saints",
    "new york giants", "new york jets", "philadelphia eagles",
    "pittsburgh steelers", "san francisco 49ers", "seattle seahawks",
    "tampa bay buccaneers", "tennessee titans",
    "washington commanders",
}

SOCCER_CLUBS = {
    # England
    "arsenal", "aston villa", "bournemouth", "brentford",
    "brighton", "burnley", "chelsea", "crystal palace",
    "everton", "fulham", "leeds united", "liverpool",
    "manchester city", "manchester united", "newcastle united",
    "nottingham forest", "sunderland", "tottenham", "west ham",
    "wolverhampton", "wolves",
    # Spain
    "real madrid", "barcelona", "atletico madrid", "athletic club",
    "real sociedad", "real betis", "sevilla", "villarreal",
    "valencia", "girona",
    # Germany
    "bayern munich", "borussia dortmund", "bayer leverkusen",
    "rb leipzig", "eintracht frankfurt", "stuttgart",
    # Italy
    "inter milan", "ac milan", "juventus", "napoli", "roma",
    "lazio", "atalanta", "fiorentina",
    # France
    "paris saint-germain", "paris saint germain", "psg",
    "marseille", "monaco", "lyon", "lille",
    # Mexico / Americas
    "cd guadalajara", "guadalajara", "chivas",
    "deportivo toluca fc", "toluca", "cf monterrey", "monterrey",
    "club america", "tigres uanl", "cruz azul", "pumas unam",
    "inter miami", "la galaxy", "los angeles fc", "seattle sounders",
    "portland timbers", "atlanta united", "new york city fc",
    "river plate", "boca juniors", "flamengo", "palmeiras",
    # Other common clubs
    "benfica", "porto", "sporting cp", "ajax", "psv",
    "feyenoord", "celtic", "rangers", "galatasaray",
    "fenerbahce", "al hilal", "al nassr",
}

COUNTRY_TEAMS = {
    "argentina", "australia", "austria", "belgium", "brazil",
    "canada", "chile", "china", "colombia", "croatia",
    "denmark", "ecuador", "egypt", "england", "finland",
    "france", "germany", "ghana", "greece", "hungary",
    "iceland", "india", "iran", "ireland", "israel", "italy",
    "japan", "mexico", "morocco", "netherlands", "new zealand",
    "nigeria", "norway", "panama", "paraguay", "peru",
    "poland", "portugal", "qatar", "romania", "saudi arabia",
    "scotland", "senegal", "serbia", "slovakia", "slovenia",
    "south africa", "south korea", "spain", "sweden",
    "switzerland", "tunisia", "turkey", "ukraine",
    "united states", "usa", "uruguay", "venezuela", "wales",
}

LEAGUE_RULES: dict[str, tuple[str, ...]] = {
    "SOCCER": (
        "fifa", "world cup", "premier league", "champions league",
        "europa league", "conference league", "la liga", "liga mx",
        "serie a", "bundesliga", "ligue 1", "mls", "nwsl",
        "copa libertadores", "copa sudamericana", "copa america",
        "uefa", "afcon", "concacaf", "eredivisie",
    ),
    "BASKETBALL": (
        "nba", "wnba", "euroleague", "ncaa basketball",
        "basketball", "fiba",
    ),
    "BASEBALL": (
        "mlb", "world series", "baseball", "npb", "kbo",
    ),
    "HOCKEY": (
        "nhl", "stanley cup", "hockey",
    ),
    "AMERICAN_FOOTBALL": (
        "nfl", "super bowl", "ncaa football", "american football",
    ),
    "MMA": (
        "ufc", "bellator", "pfl", "mma", "fight night",
    ),
    "TENNIS": (
        "atp", "wta", "wimbledon", "australian open",
        "french open", "us open tennis", "tennis",
    ),
}

NONSPORT_RULES: dict[str, tuple[str, ...]] = {
    "CRYPTO": (
        "bitcoin", "btc", "ethereum", "eth", "solana", "crypto",
        "blockchain", "coinbase", "binance", "token price",
    ),
    "POLITICS": (
        "election", "president", "prime minister", "congress",
        "senate", "governor", "republican", "democrat", "gop",
        "nomination", "parliament", "mayor", "approval rating",
    ),
    "ECONOMY": (
        "inflation", "cpi", "gdp", "interest rate",
        "federal reserve", "unemployment", "recession",
        "stock market", "nasdaq", "s&p 500",
    ),
    "GEOPOLITICS": (
        "ceasefire", "invasion", "nato", "sanctions",
        "ukraine", "russia", "israel", "gaza", "iran",
        "taiwan", "military strike",
    ),
    "ENTERTAINMENT": (
        "oscar", "emmy", "grammy", "box office", "album",
        "movie", "film", "celebrity", "reality show",
    ),
    "TECHNOLOGY": (
        "openai", "chatgpt", "artificial intelligence",
        "spacex", "apple event", "google", "microsoft",
    ),
}

SOCCER_MARKET_PHRASES = (
    "both teams to score", "btts", "draw at halftime",
    "leading at halftime", "team to advance", "clean sheet",
    "correct score", "exact score", "1st half o/u",
    "first half o/u", "to qualify", "to win either half",
)

BASEBALL_MARKET_PHRASES = (
    "home run", "strikeout", "innings", "runs allowed",
    "hits+runs+rbi", "rbi", "moneyline - first 5",
)

BASKETBALL_MARKET_PHRASES = (
    "rebounds", "assists", "three pointers", "3-pointers",
    "double-double", "triple-double",
)

HOCKEY_MARKET_PHRASES = (
    "puck line", "shots on goal", "power play",
)

AMERICAN_FOOTBALL_MARKET_PHRASES = (
    "touchdown", "passing yards", "rushing yards",
    "receiving yards",
)

TENNIS_MARKET_PHRASES = (
    "aces", "double faults", "games won", "sets won",
)

MMA_MARKET_PHRASES = (
    "by submission", "by knockout", "by decision",
    "goes the distance", "round 1", "round 2", "round 3",
)


@dataclass(frozen=True)
class Classification:
    category: str
    subcategory: str | None
    confidence: float
    method: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str | None) -> str:
    text = (value or "").lower()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[^\w\s.+/'&:-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_phrase(text: str, phrase: str) -> bool:
    phrase = normalize_text(phrase)
    return re.search(
        rf"(?<!\w){re.escape(phrase)}(?!\w)",
        text,
        flags=re.IGNORECASE,
    ) is not None


def matching_names(text: str, names: Iterable[str]) -> list[str]:
    matches = [
        name
        for name in names
        if contains_phrase(text, name)
    ]
    return sorted(matches, key=len, reverse=True)


def extract_matchup_sides(title: str) -> tuple[str | None, str | None]:
    normalized = normalize_text(title)
    base = normalized.split(":", 1)[0].strip()

    for separator in (" vs. ", " vs ", " v. ", " v "):
        if separator in base:
            left, right = base.split(separator, 1)
            return left.strip(), right.strip()

    return None, None


def listed_team_category(text: str) -> tuple[str | None, list[str]]:
    team_sets = (
        ("BASEBALL", MLB_TEAMS),
        ("BASKETBALL", NBA_TEAMS | WNBA_TEAMS),
        ("HOCKEY", NHL_TEAMS),
        ("AMERICAN_FOOTBALL", NFL_TEAMS),
        ("SOCCER", SOCCER_CLUBS),
    )

    category_matches: dict[str, list[str]] = {}
    for category, names in team_sets:
        matches = matching_names(text, names)
        if matches:
            category_matches[category] = matches

    if not category_matches:
        return None, []

    ranked = sorted(
        category_matches.items(),
        key=lambda item: (len(item[1]), sum(map(len, item[1]))),
        reverse=True,
    )

    top_category, top_matches = ranked[0]
    if len(ranked) > 1 and len(ranked[0][1]) == len(ranked[1][1]):
        return None, []

    return top_category, top_matches


def phrase_category(text: str) -> tuple[str | None, list[str]]:
    groups = (
        ("SOCCER", SOCCER_MARKET_PHRASES),
        ("BASEBALL", BASEBALL_MARKET_PHRASES),
        ("BASKETBALL", BASKETBALL_MARKET_PHRASES),
        ("HOCKEY", HOCKEY_MARKET_PHRASES),
        ("AMERICAN_FOOTBALL", AMERICAN_FOOTBALL_MARKET_PHRASES),
        ("TENNIS", TENNIS_MARKET_PHRASES),
        ("MMA", MMA_MARKET_PHRASES),
    )

    hits: dict[str, list[str]] = {}
    for category, phrases in groups:
        matched = [
            phrase for phrase in phrases
            if phrase in text
        ]
        if matched:
            hits[category] = matched

    if not hits:
        return None, []

    ranked = sorted(
        hits.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    )
    return ranked[0]


def keyword_category(
    text: str,
    rules: dict[str, tuple[str, ...]],
) -> tuple[str | None, list[str]]:
    matches: dict[str, list[str]] = {}
    for category, phrases in rules.items():
        found = [
            phrase for phrase in phrases
            if contains_phrase(text, phrase)
        ]
        if found:
            matches[category] = found

    if not matches:
        return None, []

    ranked = sorted(
        matches.items(),
        key=lambda item: (len(item[1]), sum(map(len, item[1]))),
        reverse=True,
    )
    return ranked[0]


def countries_in_matchup(title: str) -> list[str]:
    left, right = extract_matchup_sides(title)
    if not left or not right:
        return []

    matches: list[str] = []
    for side in (left, right):
        side_matches = matching_names(side, COUNTRY_TEAMS)
        if side_matches:
            matches.append(side_matches[0])

    return matches


def looks_like_low_total_soccer(title: str) -> bool:
    normalized = normalize_text(title)
    match = re.search(r"\bo/u\s+(\d+(?:\.\d+)?)", normalized)
    if not match:
        return False

    line = float(match.group(1))
    return line <= 6.5


def classify_market(title: str, outcome: str = "") -> Classification:
    text = normalize_text(f"{title} {outcome}")
    title_text = normalize_text(title)

    nonsport_category, nonsport_hits = keyword_category(
        text,
        NONSPORT_RULES,
    )
    if nonsport_category and len(nonsport_hits) >= 2:
        return Classification(
            category=nonsport_category,
            subcategory=None,
            confidence=min(0.98, 0.82 + 0.04 * len(nonsport_hits)),
            method="v2:nonsport_keywords:" + ",".join(nonsport_hits[:5]),
        )

    league_category, league_hits = keyword_category(
        text,
        LEAGUE_RULES,
    )
    if league_category:
        return Classification(
            category=league_category,
            subcategory=league_category,
            confidence=min(0.99, 0.91 + 0.02 * len(league_hits)),
            method="v2:league:" + ",".join(league_hits[:5]),
        )

    team_category, team_hits = listed_team_category(title_text)
    if team_category:
        return Classification(
            category=team_category,
            subcategory=team_category,
            confidence=min(0.98, 0.88 + 0.03 * len(team_hits)),
            method="v2:team_dictionary:" + ",".join(team_hits[:4]),
        )

    market_category, market_hits = phrase_category(text)
    if market_category:
        confidence = 0.84 if market_category == "SOCCER" else 0.80
        return Classification(
            category=market_category,
            subcategory=market_category,
            confidence=min(0.95, confidence + 0.025 * len(market_hits)),
            method="v2:market_structure:" + ",".join(market_hits[:5]),
        )

    country_matches = countries_in_matchup(title)
    if len(country_matches) == 2 and looks_like_low_total_soccer(title):
        return Classification(
            category="SOCCER",
            subcategory="SOCCER",
            confidence=0.82,
            method="v2:country_matchup_low_total:" + ",".join(country_matches),
        )

    if len(country_matches) == 2 and any(
        phrase in text
        for phrase in (
            "team to advance", "draw", "halftime",
            "both teams to score", "clean sheet",
        )
    ):
        return Classification(
            category="SOCCER",
            subcategory="SOCCER",
            confidence=0.86,
            method="v2:country_matchup_soccer_structure:"
            + ",".join(country_matches),
        )

    # Club naming conventions are useful when a club is not yet in the
    # dictionary. We require a matchup plus a soccer-specific suffix/prefix.
    left, right = extract_matchup_sides(title)
    club_tokens = (
        " fc", "cf ", "cd ", " sc", " united", " city",
        " deportivo", " athletic", " real ", " club ",
    )
    if left and right and (
        any(token in f" {left} " for token in club_tokens)
        or any(token in f" {right} " for token in club_tokens)
    ):
        return Classification(
            category="SOCCER",
            subcategory="SOCCER",
            confidence=0.76,
            method="v2:soccer_club_naming_convention",
        )

    if nonsport_category:
        return Classification(
            category=nonsport_category,
            subcategory=None,
            confidence=min(0.88, 0.70 + 0.04 * len(nonsport_hits)),
            method="v2:nonsport_keyword:" + ",".join(nonsport_hits[:5]),
        )

    return Classification(
        category="OTHER",
        subcategory=None,
        confidence=0.35,
        method="v2:fallback:no_rule_match",
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
        CREATE TABLE IF NOT EXISTS market_category_dictionary (
            condition_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            classification_confidence REAL NOT NULL DEFAULT 0,
            classification_method TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            manually_overridden INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_mcd_category
        ON market_category_dictionary(category);

        CREATE TABLE IF NOT EXISTS market_classification_history (
            classification_run_id TEXT NOT NULL,
            condition_id TEXT NOT NULL,
            title TEXT NOT NULL,
            old_category TEXT,
            new_category TEXT NOT NULL,
            old_confidence REAL,
            new_confidence REAL NOT NULL,
            classification_method TEXT NOT NULL,
            changed INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (classification_run_id, condition_id)
        );

        CREATE INDEX IF NOT EXISTS idx_mch_condition
        ON market_classification_history(condition_id);

        CREATE INDEX IF NOT EXISTS idx_mch_run_changed
        ON market_classification_history(classification_run_id, changed);
        """
    )


def load_markets(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            condition_id,
            MAX(COALESCE(title, '')) AS title,
            MAX(COALESCE(selected_outcome, '')) AS selected_outcome
        FROM wallet_performance_markets
        WHERE condition_id IS NOT NULL
          AND TRIM(condition_id) <> ''
        GROUP BY condition_id
        ORDER BY title, condition_id
        """
    ).fetchall()


def upsert_classification(
    connection: sqlite3.Connection,
    condition_id: str,
    title: str,
    classification: Classification,
    timestamp: str,
) -> tuple[str | None, float | None, bool]:
    existing = connection.execute(
        """
        SELECT
            category,
            classification_confidence,
            manually_overridden
        FROM market_category_dictionary
        WHERE condition_id = ?
        """,
        (condition_id,),
    ).fetchone()

    old_category = (
        str(existing["category"])
        if existing is not None
        else None
    )
    old_confidence = (
        float(existing["classification_confidence"])
        if existing is not None
        else None
    )

    if existing is not None and int(existing["manually_overridden"]) == 1:
        return old_category, old_confidence, False

    should_replace = (
        existing is None
        or old_category == "OTHER"
        or classification.confidence >= (old_confidence or 0.0)
        or str(
            connection.execute(
                """
                SELECT rule_version
                FROM market_category_dictionary
                WHERE condition_id = ?
                """,
                (condition_id,),
            ).fetchone()["rule_version"]
        ) != RULE_VERSION
    )

    if not should_replace:
        return old_category, old_confidence, False

    connection.execute(
        """
        INSERT INTO market_category_dictionary (
            condition_id,
            title,
            category,
            subcategory,
            classification_confidence,
            classification_method,
            rule_version,
            manually_overridden,
            first_seen_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(condition_id) DO UPDATE SET
            title = excluded.title,
            category = excluded.category,
            subcategory = excluded.subcategory,
            classification_confidence =
                excluded.classification_confidence,
            classification_method =
                excluded.classification_method,
            rule_version = excluded.rule_version,
            updated_at = excluded.updated_at
        """,
        (
            condition_id,
            title,
            classification.category,
            classification.subcategory,
            classification.confidence,
            classification.method,
            RULE_VERSION,
            timestamp,
            timestamp,
        ),
    )

    changed = old_category != classification.category
    return old_category, old_confidence, changed


def store_history(
    connection: sqlite3.Connection,
    run_id: str,
    condition_id: str,
    title: str,
    old_category: str | None,
    old_confidence: float | None,
    classification: Classification,
    changed: bool,
    timestamp: str,
) -> None:
    connection.execute(
        """
        INSERT INTO market_classification_history (
            classification_run_id,
            condition_id,
            title,
            old_category,
            new_category,
            old_confidence,
            new_confidence,
            classification_method,
            changed,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            condition_id,
            title,
            old_category,
            classification.category,
            old_confidence,
            classification.confidence,
            classification.method,
            int(changed),
            timestamp,
        ),
    )


def print_report(
    total_markets: int,
    old_distribution: Counter[str],
    new_distribution: Counter[str],
    changed_pairs: Counter[tuple[str, str]],
    low_confidence: list[tuple[str, str, float, str]],
    run_id: str,
) -> None:
    old_other = old_distribution.get("OTHER", 0)
    new_other = new_distribution.get("OTHER", 0)
    reduction = old_other - new_other
    reduction_rate = (
        reduction / old_other
        if old_other
        else 0.0
    )

    print("\n" + "=" * 120)
    print("MARKET CLASSIFICATION ENGINE V2 COMPLETE")
    print("=" * 120)
    print(f"Database: {DATABASE_PATH}")
    print(f"Markets processed: {total_markets}")
    print(f"Classification run ID: {run_id}")
    print(
        f"OTHER reduction: {old_other} -> {new_other} "
        f"({reduction:+d}, {reduction_rate:.1%})"
    )

    print("\nNew category distribution:")
    for category, count in sorted(
        new_distribution.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"  {category:<22} {count:>5}")

    if changed_pairs:
        print("\nCategory changes:")
        for (old_category, new_category), count in sorted(
            changed_pairs.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            print(
                f"  {old_category:<18} -> "
                f"{new_category:<18} {count:>5}"
            )

    print("\nLowest-confidence remaining classifications:")
    for condition_id, title, confidence, method in low_confidence[:30]:
        print(
            f"  {confidence:.2f} | {title[:82]} | "
            f"{method} | {condition_id[:18]}..."
        )


def run() -> None:
    timestamp = utc_now()
    run_id = (
        "market_classification_run:"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )

    connection = connect_database()

    try:
        ensure_schema(connection)

        old_distribution = Counter(
            {
                str(row["category"]): int(row["market_count"])
                for row in connection.execute(
                    """
                    SELECT category, COUNT(*) AS market_count
                    FROM market_category_dictionary
                    GROUP BY category
                    """
                ).fetchall()
            }
        )

        markets = load_markets(connection)
        if not markets:
            raise RuntimeError(
                "No markets found in wallet_performance_markets."
            )

        changed_pairs: Counter[tuple[str, str]] = Counter()

        with connection:
            for row in markets:
                condition_id = str(row["condition_id"])
                title = str(row["title"] or "")
                outcome = str(row["selected_outcome"] or "")

                classification = classify_market(title, outcome)
                (
                    old_category,
                    old_confidence,
                    changed,
                ) = upsert_classification(
                    connection=connection,
                    condition_id=condition_id,
                    title=title,
                    classification=classification,
                    timestamp=timestamp,
                )

                if old_category is not None and changed:
                    changed_pairs[
                        (old_category, classification.category)
                    ] += 1

                store_history(
                    connection=connection,
                    run_id=run_id,
                    condition_id=condition_id,
                    title=title,
                    old_category=old_category,
                    old_confidence=old_confidence,
                    classification=classification,
                    changed=changed,
                    timestamp=timestamp,
                )

        new_distribution = Counter(
            {
                str(row["category"]): int(row["market_count"])
                for row in connection.execute(
                    """
                    SELECT category, COUNT(*) AS market_count
                    FROM market_category_dictionary
                    GROUP BY category
                    """
                ).fetchall()
            }
        )

        low_confidence = [
            (
                str(row["condition_id"]),
                str(row["title"]),
                float(row["classification_confidence"]),
                str(row["classification_method"]),
            )
            for row in connection.execute(
                """
                SELECT
                    condition_id,
                    title,
                    classification_confidence,
                    classification_method
                FROM market_category_dictionary
                WHERE manually_overridden = 0
                ORDER BY
                    classification_confidence ASC,
                    title ASC
                LIMIT 30
                """
            ).fetchall()
        ]

        print_report(
            total_markets=len(markets),
            old_distribution=old_distribution,
            new_distribution=new_distribution,
            changed_pairs=changed_pairs,
            low_confidence=low_confidence,
            run_id=run_id,
        )

        print("\nNext command:")
        print("  python -m src.market_expertise_engine")

    finally:
        connection.close()


if __name__ == "__main__":
    run()