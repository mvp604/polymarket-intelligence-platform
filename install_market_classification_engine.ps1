$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$srcDir = Join-Path $root "src"
$classificationDir = Join-Path $srcDir "classification"
$reportDir = Join-Path $root "reports\market_classification"
$databasePath = Join-Path $root "database\polymarket.db"
$backupDir = Join-Path $root "database\backups"

New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
New-Item -ItemType Directory -Path $classificationDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

if (-not (Test-Path $databasePath)) {
    throw "Database not found: $databasePath"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$databaseBackup = Join-Path $backupDir "polymarket_before_market_classifier_$timestamp.db"
Copy-Item $databasePath $databaseBackup -Force

$enginePath = Join-Path $srcDir "market_classifier.py"
$runnerPath = Join-Path $root "run_market_classifier.ps1"
$manifestPath = Join-Path $srcDir "market_classifier.manifest.json"
$packageInitPath = Join-Path $classificationDir "__init__.py"
$taxonomyPath = Join-Path $classificationDir "taxonomy.json"

$engineCode = @'
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT / "database" / "polymarket.db"
REPORT_DIR = ROOT / "reports" / "market_classification"
CLASSIFIER_VERSION = "1.0.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalized_key(value: Any) -> str:
    return normalize_text(value).lower()


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()
    }


@dataclass(frozen=True)
class MarketRecord:
    market_id: str
    title: str


@dataclass
class Classification:
    market_id: str
    title: str
    canonical_title: str
    primary_category: str
    secondary_category: str | None
    sport: str | None
    league: str | None
    event_type: str | None
    market_type: str
    confidence: float
    method: str
    matched_rules: list[str]


SPORT_RULES: list[tuple[str, str, list[str]]] = [
    ("Soccer", "FIFA World Cup", [
        r"\bfifa\b", r"\bworld cup\b", r"\buefa\b", r"\bchampions league\b",
        r"\bpremier league\b", r"\bla liga\b", r"\bserie a\b", r"\bbundesliga\b",
        r"\bligue 1\b", r"\bmls\b", r"\bcopa\b", r"\beuro 20\d{2}\b",
        r"\bsoccer\b", r"\bfootball match\b", r"\bto win on 20\d{2}-\d{2}-\d{2}\b",
        r"\bbtts\b", r"\bclean sheet\b", r"\bexact score\b"
    ]),
    ("Basketball", "NBA", [
        r"\bnba\b", r"\bwnba\b", r"\beuroleague\b", r"\bbasketball\b",
        r"\bncaab\b", r"\bmarch madness\b"
    ]),
    ("Baseball", "MLB", [
        r"\bmlb\b", r"\bbaseball\b", r"\bworld series\b"
    ]),
    ("American Football", "NFL", [
        r"\bnfl\b", r"\bsuper bowl\b", r"\bcollege football\b", r"\bncaaf\b"
    ]),
    ("MMA", "UFC", [
        r"\bufc\b", r"\bmma\b", r"\bbellator\b", r"\bpfl\b", r"\bfight night\b"
    ]),
    ("Tennis", "Tennis", [
        r"\btennis\b", r"\bwimbledon\b", r"\bus open\b", r"\baustralian open\b",
        r"\bfrench open\b", r"\batp\b", r"\bwta\b"
    ]),
    ("Ice Hockey", "NHL", [
        r"\bnhl\b", r"\bstanley cup\b", r"\bice hockey\b"
    ]),
    ("Golf", "Golf", [
        r"\bpga\b", r"\bliv golf\b", r"\bmasters tournament\b", r"\bthe open\b",
        r"\bgolf\b"
    ]),
    ("Motorsport", "Formula 1", [
        r"\bformula 1\b", r"\bf1\b", r"\bnascar\b", r"\bindycar\b", r"\bgrand prix\b"
    ]),
    ("Cricket", "Cricket", [
        r"\bipl\b", r"\bcricket\b", r"\bt20\b", r"\btest match\b"
    ]),
    ("Boxing", "Boxing", [
        r"\bboxing\b", r"\bheavyweight\b", r"\bknockout\b"
    ]),
    ("Esports", "Esports", [
        r"\besports\b", r"\bleague of legends\b", r"\bvalorant\b", r"\bdota\b",
        r"\bcounter-strike\b", r"\bcs2\b"
    ]),
]

CATEGORY_RULES: list[tuple[str, str | None, list[str]]] = [
    ("Politics", "US Politics", [
        r"\bpresident\b", r"\belection\b", r"\bnomination\b", r"\bdemocrat\b",
        r"\brepublican\b", r"\bgop\b", r"\bcongress\b", r"\bsenate\b",
        r"\bgovernor\b", r"\bprime minister\b", r"\bparliament\b",
        r"\bapproval rating\b", r"\bcabinet\b", r"\bwhite house\b"
    ]),
    ("Crypto", "Cryptocurrency", [
        r"\bbitcoin\b", r"\bbtc\b", r"\bethereum\b", r"\beth\b", r"\bsolana\b",
        r"\bcrypto\b", r"\btoken\b", r"\bdefi\b", r"\bstablecoin\b",
        r"\bblockchain\b", r"\bcoinbase\b"
    ]),
    ("Economics", "Macroeconomics", [
        r"\bfed\b", r"\bfederal reserve\b", r"\binterest rate\b", r"\binflation\b",
        r"\bcpi\b", r"\bgdp\b", r"\bunemployment\b", r"\brecession\b",
        r"\bcentral bank\b", r"\bjobs report\b", r"\btreasury\b"
    ]),
    ("Finance", "Markets", [
        r"\bs&p 500\b", r"\bspy\b", r"\bnasdaq\b", r"\bdow jones\b",
        r"\bstock price\b", r"\bmarket cap\b", r"\bipo\b", r"\bearnings\b"
    ]),
    ("Technology", "Technology", [
        r"\bopenai\b", r"\bartificial intelligence\b", r"\bai model\b",
        r"\bapple\b", r"\bmicrosoft\b", r"\bgoogle\b", r"\bmeta\b",
        r"\btesla\b", r"\bspacex\b", r"\bchip\b", r"\bsemiconductor\b"
    ]),
    ("Entertainment", "Entertainment", [
        r"\boscar\b", r"\bemmy\b", r"\bgrammy\b", r"\bbox office\b",
        r"\bmovie\b", r"\btelevision\b", r"\bcelebrity\b", r"\balbum\b",
        r"\bbillboard\b"
    ]),
    ("World Events", "Geopolitics", [
        r"\bwar\b", r"\bceasefire\b", r"\binvasion\b", r"\bsanction\b",
        r"\bnato\b", r"\bunited nations\b", r"\btreaty\b", r"\bconflict\b"
    ]),
    ("Science", "Science and Health", [
        r"\bnasa\b", r"\bspace mission\b", r"\bmoon landing\b", r"\bvaccine\b",
        r"\bpandemic\b", r"\bclinical trial\b", r"\btemperature record\b"
    ]),
]


LEAGUE_RULES: list[tuple[str, list[str]]] = [
    ("FIFA World Cup", [r"\bfifa world cup\b", r"\bworld cup\b"]),
    ("UEFA Champions League", [r"\bchampions league\b"]),
    ("UEFA Europa League", [r"\beuropa league\b"]),
    ("Premier League", [r"\bpremier league\b"]),
    ("La Liga", [r"\bla liga\b"]),
    ("Serie A", [r"\bserie a\b"]),
    ("Bundesliga", [r"\bbundesliga\b"]),
    ("Ligue 1", [r"\bligue 1\b"]),
    ("MLS", [r"\bmls\b"]),
    ("NBA", [r"\bnba\b"]),
    ("WNBA", [r"\bwnba\b"]),
    ("MLB", [r"\bmlb\b"]),
    ("NFL", [r"\bnfl\b"]),
    ("NHL", [r"\bnhl\b"]),
    ("UFC", [r"\bufc\b", r"\bfight night\b"]),
    ("PFL", [r"\bpfl\b"]),
    ("Bellator", [r"\bbellator\b"]),
    ("ATP", [r"\batp\b"]),
    ("WTA", [r"\bwta\b"]),
    ("Formula 1", [r"\bformula 1\b", r"\bf1\b", r"\bgrand prix\b"]),
    ("IPL", [r"\bipl\b"]),
]


MARKET_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("Exact Score", [r"\bexact score\b", r"\bscore exactly\b"]),
    ("Player Prop", [
        r"\bplayer\b", r"\bshots?\b", r"\bgoalscorer\b", r"\bassists?\b",
        r"\brebounds?\b", r"\bpoints?\b", r"\bstrikeouts?\b", r"\bhits?\b",
        r"\bfouls?\b", r"\bpassing yards?\b", r"\brushing yards?\b"
    ]),
    ("Both Teams To Score", [r"\bbtts\b", r"\bboth teams to score\b"]),
    ("Spread", [r"\bspread\b", r"\bhandicap\b", r"[+-]\d+(?:\.\d+)?"]),
    ("Total", [
        r"\bover\b", r"\bunder\b", r"\btotal goals?\b", r"\btotal points?\b",
        r"\bo/u\b"
    ]),
    ("Moneyline", [
        r"\bmoneyline\b", r"\bmatch winner\b", r"\bwill .* win on 20\d{2}-\d{2}-\d{2}\b"
    ]),
    ("Outright/Future", [
        r"\bto win the\b", r"\bchampion\b", r"\bwinner of\b", r"\bwin .* cup\b",
        r"\bnomination\b", r"\belection winner\b"
    ]),
    ("Margin of Victory", [r"\bmargin\b", r"\bwin by\b"]),
    ("Resolution Event", [
        r"\bwill .* happen\b", r"\bwill .* occur\b", r"\bby 20\d{2}\b",
        r"\bbefore 20\d{2}\b"
    ]),
    ("Yes/No", [r"^will\b", r"\byes\b", r"\bno\b"]),
]


EVENT_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("Single Match", [
        r"\bvs\.?\b", r"\bv\.?\b", r"\bto win on 20\d{2}-\d{2}-\d{2}\b"
    ]),
    ("Tournament", [
        r"\bworld cup\b", r"\bchampions league\b", r"\btournament\b",
        r"\bplayoffs\b", r"\bfinals\b"
    ]),
    ("Season", [
        r"\bseason\b", r"\bregular season\b", r"\bchampionship\b"
    ]),
    ("Election", [
        r"\belection\b", r"\bnomination\b", r"\bprimary\b"
    ]),
    ("Economic Release", [
        r"\bcpi\b", r"\bgdp\b", r"\bunemployment\b", r"\bjobs report\b",
        r"\bfed\b", r"\binterest rate\b"
    ]),
    ("Price Target", [
        r"\bprice\b.*\babove\b", r"\bprice\b.*\bbelow\b", r"\breach \$"
    ]),
]


def any_match(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def first_match(
    text: str,
    rules: Iterable[tuple[str, list[str]]],
) -> tuple[str | None, str | None]:
    for label, patterns in rules:
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return label, pattern
    return None, None


def canonicalize_title(title: str) -> str:
    result = normalize_text(title)
    result = re.sub(r"\s+\?", "?", result)
    result = re.sub(r"\s+:", ":", result)
    return result


def classify_market(record: MarketRecord) -> Classification:
    title = normalize_text(record.title)
    text = normalized_key(title)
    matched: list[str] = []

    primary_category = "Other"
    secondary_category: str | None = None
    sport: str | None = None
    league: str | None = None

    # Sports classification is evaluated first because many sports titles use
    # generic words such as "winner", "points", and "election-style" phrasing.
    for sport_name, default_league, patterns in SPORT_RULES:
        pattern = next(
            (pattern for pattern in patterns if re.search(pattern, text, re.IGNORECASE)),
            None,
        )
        if pattern:
            primary_category = "Sports"
            secondary_category = sport_name
            sport = sport_name
            league = default_league
            matched.append(f"sport:{pattern}")
            break

    if primary_category != "Sports":
        for category, secondary, patterns in CATEGORY_RULES:
            pattern = next(
                (pattern for pattern in patterns if re.search(pattern, text, re.IGNORECASE)),
                None,
            )
            if pattern:
                primary_category = category
                secondary_category = secondary
                matched.append(f"category:{pattern}")
                break

    league_label, league_pattern = first_match(text, LEAGUE_RULES)
    if league_label:
        league = league_label
        matched.append(f"league:{league_pattern}")

    market_type, market_pattern = first_match(text, MARKET_TYPE_RULES)
    if not market_type:
        market_type = "Yes/No" if text.startswith("will ") else "Unclassified"
    else:
        matched.append(f"market_type:{market_pattern}")

    event_type, event_pattern = first_match(text, EVENT_TYPE_RULES)
    if event_type:
        matched.append(f"event_type:{event_pattern}")
    elif primary_category == "Sports":
        event_type = "Sports Market"
    else:
        event_type = "General Event"

    confidence = 0.25
    if primary_category != "Other":
        confidence += 0.35
    if secondary_category:
        confidence += 0.10
    if league:
        confidence += 0.10
    if market_type != "Unclassified":
        confidence += 0.10
    if event_type not in {"General Event", "Sports Market"}:
        confidence += 0.10
    confidence = min(confidence, 0.99)

    method = "rules_v1"
    if primary_category == "Other":
        method = "rules_v1_fallback"

    return Classification(
        market_id=record.market_id,
        title=title,
        canonical_title=canonicalize_title(title),
        primary_category=primary_category,
        secondary_category=secondary_category,
        sport=sport,
        league=league,
        event_type=event_type,
        market_type=market_type,
        confidence=round(confidence, 4),
        method=method,
        matched_rules=matched,
    )


def load_markets(connection: sqlite3.Connection) -> list[MarketRecord]:
    sources: list[tuple[str, str, str]] = []

    for table in ("positions", "consensus_history"):
        if not table_exists(connection, table):
            continue
        columns = table_columns(connection, table)
        if {"market_id", "title"}.issubset(columns):
            sources.append((table, "market_id", "title"))

    if not sources:
        raise RuntimeError(
            "No source table contains both market_id and title."
        )

    markets: dict[str, MarketRecord] = {}

    for table, market_column, title_column in sources:
        rows = connection.execute(
            f"""
            SELECT DISTINCT
                "{market_column}" AS market_id,
                "{title_column}" AS title
            FROM "{table}"
            WHERE "{market_column}" IS NOT NULL
              AND TRIM(CAST("{market_column}" AS TEXT)) <> ''
              AND "{title_column}" IS NOT NULL
              AND TRIM(CAST("{title_column}" AS TEXT)) <> ''
            """
        ).fetchall()

        for row in rows:
            market_id = normalize_text(row[0])
            title = normalize_text(row[1])
            if not market_id or not title:
                continue

            existing = markets.get(market_id)
            if existing is None or len(title) > len(existing.title):
                markets[market_id] = MarketRecord(
                    market_id=market_id,
                    title=title,
                )

    return sorted(markets.values(), key=lambda item: (item.title.lower(), item.market_id))


def ensure_schema(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "market_category_classifications"):
        raise RuntimeError(
            "market_category_classifications is missing. "
            "Install the Elite Wallet Intelligence database foundation first."
        )

    columns = table_columns(connection, "market_category_classifications")
    additions = {
        "canonical_title": "TEXT",
        "market_type": "TEXT",
        "classifier_version": "TEXT",
        "matched_rules_json": "TEXT",
    }

    for column, sql_type in additions.items():
        if column not in columns:
            connection.execute(
                f'ALTER TABLE market_category_classifications '
                f'ADD COLUMN "{column}" {sql_type}'
            )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_classification_market_type
        ON market_category_classifications(market_type)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_classification_league
        ON market_category_classifications(league)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_classification_secondary
        ON market_category_classifications(secondary_category)
        """
    )


def validate_classifications(items: list[Classification]) -> None:
    ids = [item.market_id for item in items]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate market IDs produced by classifier.")

    for item in items:
        if not item.market_id:
            raise RuntimeError("Classification contains an empty market ID.")
        if not item.title:
            raise RuntimeError(f"Market {item.market_id} has an empty title.")
        if not 0 <= item.confidence <= 1:
            raise RuntimeError(
                f"Market {item.market_id} has invalid confidence {item.confidence}."
            )


def persist(
    connection: sqlite3.Connection,
    items: list[Classification],
) -> tuple[int, int]:
    inserted = 0
    updated = 0
    now = iso_now()

    existing = {
        str(row[0])
        for row in connection.execute(
            "SELECT market_id FROM market_category_classifications"
        ).fetchall()
    }

    for item in items:
        if item.market_id in existing:
            updated += 1
        else:
            inserted += 1

        connection.execute(
            """
            INSERT INTO market_category_classifications (
                market_id,
                title,
                canonical_title,
                primary_category,
                secondary_category,
                sport,
                league,
                event_type,
                market_type,
                classification_confidence,
                classification_method,
                classifier_version,
                matched_rules_json,
                classified_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(market_id) DO UPDATE SET
                title = excluded.title,
                canonical_title = excluded.canonical_title,
                primary_category = excluded.primary_category,
                secondary_category = excluded.secondary_category,
                sport = excluded.sport,
                league = excluded.league,
                event_type = excluded.event_type,
                market_type = excluded.market_type,
                classification_confidence = excluded.classification_confidence,
                classification_method = excluded.classification_method,
                classifier_version = excluded.classifier_version,
                matched_rules_json = excluded.matched_rules_json,
                updated_at = excluded.updated_at
            """,
            (
                item.market_id,
                item.title,
                item.canonical_title,
                item.primary_category,
                item.secondary_category,
                item.sport,
                item.league,
                item.event_type,
                item.market_type,
                item.confidence,
                item.method,
                CLASSIFIER_VERSION,
                json.dumps(item.matched_rules),
                now,
                now,
            ),
        )

    return inserted, updated


def summarize(items: list[Classification]) -> dict[str, Any]:
    def counts(field: str) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in items:
            value = getattr(item, field) or "Unknown"
            result[value] = result.get(value, 0) + 1
        return dict(sorted(result.items(), key=lambda pair: (-pair[1], pair[0])))

    low_confidence = [
        item for item in items
        if item.confidence < 0.60
    ]

    return {
        "markets": len(items),
        "primary_categories": counts("primary_category"),
        "secondary_categories": counts("secondary_category"),
        "sports": counts("sport"),
        "leagues": counts("league"),
        "market_types": counts("market_type"),
        "event_types": counts("event_type"),
        "low_confidence_count": len(low_confidence),
        "unclassified_count": sum(
            1 for item in items
            if item.primary_category == "Other"
            or item.market_type == "Unclassified"
        ),
    }


def write_reports(
    items: list[Classification],
    dry_run: bool,
    inserted: int,
    updated: int,
) -> dict[str, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    summary = summarize(items)

    payload = {
        "generated_at": iso_now(),
        "classifier_version": CLASSIFIER_VERSION,
        "dry_run": dry_run,
        "database_inserted": inserted,
        "database_updated": updated,
        "summary": summary,
        "classifications": [asdict(item) for item in items],
    }

    json_path = REPORT_DIR / f"classifications_{timestamp}.json"
    csv_path = REPORT_DIR / f"classifications_{timestamp}.csv"
    txt_path = REPORT_DIR / f"classifications_{timestamp}.txt"
    html_path = REPORT_DIR / f"classifications_{timestamp}.html"

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "market_id", "title", "canonical_title", "primary_category",
            "secondary_category", "sport", "league", "event_type",
            "market_type", "confidence", "method", "matched_rules"
        ])
        for item in items:
            writer.writerow([
                item.market_id,
                item.title,
                item.canonical_title,
                item.primary_category,
                item.secondary_category,
                item.sport,
                item.league,
                item.event_type,
                item.market_type,
                item.confidence,
                item.method,
                " | ".join(item.matched_rules),
            ])

    lines = [
        "POLYMARKET MARKET CLASSIFICATION ENGINE",
        "=" * 110,
        f"Generated: {payload['generated_at']}",
        f"Classifier version: {CLASSIFIER_VERSION}",
        f"Mode: {'DRY RUN' if dry_run else 'EXECUTION'}",
        f"Markets classified: {summary['markets']}",
        f"Inserted: {inserted}",
        f"Updated: {updated}",
        f"Unclassified: {summary['unclassified_count']}",
        "",
        "PRIMARY CATEGORIES",
        "-" * 110,
    ]
    for label, count in summary["primary_categories"].items():
        lines.append(f"{label:<35} {count}")

    lines.extend(["", "MARKET TYPES", "-" * 110])
    for label, count in summary["market_types"].items():
        lines.append(f"{label:<35} {count}")

    lines.extend(["", "CLASSIFICATIONS", "-" * 110])
    for item in items:
        lines.extend([
            f"{item.market_id}",
            f"  {item.title}",
            f"  {item.primary_category} / {item.secondary_category or 'Unknown'}"
            f" / {item.league or 'Unknown'} / {item.market_type}",
            f"  Confidence: {item.confidence:.2%}",
            "",
        ])
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    category_rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{count}</td></tr>"
        for label, count in summary["primary_categories"].items()
    )
    type_rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{count}</td></tr>"
        for label, count in summary["market_types"].items()
    )
    market_rows = "".join(
        f"""
        <tr>
          <td><code>{html.escape(item.market_id)}</code></td>
          <td>{html.escape(item.title)}</td>
          <td>{html.escape(item.primary_category)}</td>
          <td>{html.escape(item.secondary_category or '')}</td>
          <td>{html.escape(item.sport or '')}</td>
          <td>{html.escape(item.league or '')}</td>
          <td>{html.escape(item.event_type or '')}</td>
          <td>{html.escape(item.market_type)}</td>
          <td>{item.confidence:.0%}</td>
        </tr>
        """
        for item in items
    )

    html_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Classification Engine</title>
<style>
body {{ margin:0; font-family:Arial,sans-serif; background:#f4f6f8; color:#172033; }}
header {{ background:#111827; color:white; padding:28px; }}
main {{ max-width:1700px; margin:auto; padding:24px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:18px; }}
section {{ background:white; border-radius:12px; padding:18px; margin-bottom:20px; box-shadow:0 2px 10px rgba(0,0,0,.06); overflow:auto; }}
.metric {{ font-size:30px; font-weight:bold; }}
table {{ border-collapse:collapse; width:100%; }}
th,td {{ padding:10px; border-bottom:1px solid #e5e7eb; text-align:left; vertical-align:top; }}
th {{ background:#f8fafc; position:sticky; top:0; }}
code {{ font-size:11px; }}
</style>
</head>
<body>
<header>
<h1>Market Classification Engine v{CLASSIFIER_VERSION}</h1>
<div>{payload['generated_at']} · {'DRY RUN' if dry_run else 'EXECUTION'}</div>
</header>
<main>
<div class="grid">
<section><div class="metric">{summary['markets']}</div><div>Markets classified</div></section>
<section><div class="metric">{summary['unclassified_count']}</div><div>Require future taxonomy refinement</div></section>
<section><div class="metric">{inserted}</div><div>Inserted</div></section>
<section><div class="metric">{updated}</div><div>Updated</div></section>
</div>
<div class="grid">
<section>
<h2>Primary Categories</h2>
<table><tbody>{category_rows}</tbody></table>
</section>
<section>
<h2>Market Types</h2>
<table><tbody>{type_rows}</tbody></table>
</section>
</div>
<section>
<h2>Classified Markets</h2>
<table>
<thead>
<tr>
<th>Market ID</th><th>Title</th><th>Primary</th><th>Secondary</th>
<th>Sport</th><th>League</th><th>Event Type</th><th>Market Type</th><th>Confidence</th>
</tr>
</thead>
<tbody>{market_rows}</tbody>
</table>
</section>
</main>
</body>
</html>
""",
        encoding="utf-8",
    )

    latest = {
        "json": REPORT_DIR / "latest.json",
        "csv": REPORT_DIR / "latest.csv",
        "txt": REPORT_DIR / "latest.txt",
        "html": REPORT_DIR / "latest.html",
    }
    latest["json"].write_bytes(json_path.read_bytes())
    latest["csv"].write_bytes(csv_path.read_bytes())
    latest["txt"].write_bytes(txt_path.read_bytes())
    latest["html"].write_bytes(html_path.read_bytes())

    return {
        "json": json_path,
        "csv": csv_path,
        "txt": txt_path,
        "html": html_path,
        "latest_json": latest["json"],
        "latest_csv": latest["csv"],
        "latest_txt": latest["txt"],
        "latest_html": latest["html"],
    }


def self_test() -> None:
    cases = [
        (
            MarketRecord("1", "Will Spain win the 2026 FIFA World Cup?"),
            ("Sports", "Soccer", "FIFA World Cup", "Outright/Future"),
        ),
        (
            MarketRecord("2", "Will Marco Rubio win the 2028 GOP nomination?"),
            ("Politics", "US Politics", None, "Outright/Future"),
        ),
        (
            MarketRecord("3", "Will Bitcoin be above $150,000 by December 2026?"),
            ("Crypto", "Cryptocurrency", None, "Resolution Event"),
        ),
        (
            MarketRecord("4", "France vs Spain: Under 2.5 Goals"),
            ("Sports", "Soccer", "FIFA World Cup", "Total"),
        ),
        (
            MarketRecord("5", "Will the Fed cut interest rates in September?"),
            ("Economics", "Macroeconomics", None, "Economic Indicator"),
        ),
    ]

    for record, expected in cases:
        result = classify_market(record)
        actual = (
            result.primary_category,
            result.secondary_category,
            result.league,
            result.market_type,
        )
        if actual != expected:
            raise AssertionError(
                f"Classification mismatch for {record.title!r}: "
                f"expected {expected}, got {actual}"
            )

    print("Self-test passed.")


def run(dry_run: bool) -> tuple[list[Classification], int, int, dict[str, Path]]:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")

    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or str(integrity[0]).lower() != "ok":
            raise RuntimeError(f"Database integrity check failed: {integrity}")

        markets = load_markets(connection)
        classifications = [classify_market(record) for record in markets]
        validate_classifications(classifications)

        inserted = 0
        updated = 0

        if not dry_run:
            with connection:
                ensure_schema(connection)
                inserted, updated = persist(connection, classifications)

        reports = write_reports(
            classifications,
            dry_run=dry_run,
            inserted=inserted,
            updated=updated,
        )
        return classifications, inserted, updated, reports
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify Polymarket markets into a controlled taxonomy."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    items, inserted, updated, reports = run(args.dry_run)
    summary = summarize(items)

    print()
    print("=" * 110)
    print("POLYMARKET MARKET CLASSIFICATION ENGINE")
    print("=" * 110)
    print(f"Mode:                       {'DRY RUN' if args.dry_run else 'EXECUTION'}")
    print(f"Markets classified:         {len(items)}")
    print(f"Primary categories:         {len(summary['primary_categories'])}")
    print(f"Market types:               {len(summary['market_types'])}")
    print(f"Unclassified/refinement:    {summary['unclassified_count']}")
    print(f"Inserted:                   {inserted}")
    print(f"Updated:                    {updated}")
    print(f"Latest HTML:                {reports['latest_html']}")
    print(f"Latest CSV:                 {reports['latest_csv']}")
    print(f"Latest JSON:                {reports['latest_json']}")
    print(f"Database modified:          {'NO' if args.dry_run else 'YES - classification table only'}")
    print("Existing market data changed: NO")
    print("=" * 110)

    if not args.no_open and reports["latest_html"].exists():
        os.startfile(str(reports["latest_html"]))


if __name__ == "__main__":
    main()

'@

$runnerCode = @'
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python .\src\market_classifier.py @args
exit $LASTEXITCODE

'@

$manifestCode = @'
{
  "id": "market_classifier",
  "name": "Market Classification Engine",
  "version": "1.0.0",
  "runner": "run_market_classifier.ps1",
  "enabled": true,
  "required": true,
  "stage": "intelligence",
  "order": 42,
  "dependencies": [
    "elite_wallet_database"
  ],
  "latest_report": "reports/market_classification/latest.html",
  "timeout_seconds": 900
}
'@

$taxonomyCode = @'
{
  "version": "1.0.0",
  "primary_categories": [
    "Sports",
    "Politics",
    "Crypto",
    "Economics",
    "Finance",
    "Technology",
    "Entertainment",
    "World Events",
    "Science",
    "Other"
  ],
  "sports": [
    "Soccer",
    "Basketball",
    "Baseball",
    "American Football",
    "MMA",
    "Tennis",
    "Ice Hockey",
    "Golf",
    "Motorsport",
    "Cricket",
    "Boxing",
    "Esports"
  ],
  "market_types": [
    "Moneyline",
    "Spread",
    "Total",
    "Player Prop",
    "Both Teams To Score",
    "Exact Score",
    "Outright/Future",
    "Margin of Victory",
    "Resolution Event",
    "Yes/No",
    "Unclassified"
  ]
}
'@

if (Test-Path $enginePath) {
    $engineBackup = "$enginePath.backup.$timestamp"
    Copy-Item $enginePath $engineBackup -Force
    Write-Host "Existing classifier backed up:"
    Write-Host $engineBackup
}

Set-Content -Path $enginePath -Value $engineCode -Encoding UTF8
Set-Content -Path $runnerPath -Value $runnerCode -Encoding UTF8
Set-Content -Path $manifestPath -Value $manifestCode -Encoding UTF8
Set-Content -Path $packageInitPath -Value '"""Market classification package."""' -Encoding UTF8
Set-Content -Path $taxonomyPath -Value $taxonomyCode -Encoding UTF8

Write-Host ""
Write-Host "Running compile check..."
python -m py_compile $enginePath
if ($LASTEXITCODE -ne 0) {
    throw "Market Classification Engine compile check failed."
}

Write-Host "Compile check passed."

Write-Host ""
Write-Host "Running classifier self-test..."
& $runnerPath --self-test
if ($LASTEXITCODE -ne 0) {
    throw "Market Classification Engine self-test failed."
}

Write-Host ""
Write-Host "Running database-aware dry run..."
& $runnerPath --dry-run --no-open
if ($LASTEXITCODE -ne 0) {
    throw "Market Classification Engine dry run failed."
}

Write-Host ""
Write-Host ("=" * 110)
Write-Host "MARKET CLASSIFICATION ENGINE INSTALLED"
Write-Host ("=" * 110)
Write-Host "Engine:          $enginePath"
Write-Host "Runner:          $runnerPath"
Write-Host "Manifest:        $manifestPath"
Write-Host "Taxonomy:        $taxonomyPath"
Write-Host "Reports:         $reportDir"
Write-Host "Database backup: $databaseBackup"
Write-Host ""
Write-Host "Run production classification:"
Write-Host ".\run_market_classifier.ps1"
Write-Host ""
Write-Host "Then refresh wallet profiles:"
Write-Host ".\run_wallet_profiler.ps1"
Write-Host ""
Write-Host "Then run the complete platform:"
Write-Host ".\run_platform.ps1"
Write-Host ""
Write-Host "Installation changed production data: NO"
Write-Host "Dry-run reports generated: YES"
Write-Host ("=" * 110)