from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"
CONDITION_ID_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


def configure_utf8() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize(value: Any) -> str:
    value = unicodedata.normalize("NFKD", text(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = (
        value.replace("–", "-")
        .replace("—", "-")
        .replace("’", "'")
        .casefold()
    )
    value = re.sub(r"\bversus\b|\bv\.\b", " vs ", value)
    value = re.sub(r"\bover\s*/\s*under\b", " o/u ", value)
    value = re.sub(r"\bboth teams to score\b", " btts ", value)
    value = re.sub(r"[^a-z0-9.+/' -]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(value)).strip("-")


def hash_key(*parts: Any) -> str:
    raw = "\x1f".join(text(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def similarity(left: Any, right: Any) -> float:
    left_n = normalize(left)
    right_n = normalize(right)

    if not left_n or not right_n:
        return 0.0

    if left_n == right_n:
        return 100.0

    seq = difflib.SequenceMatcher(None, left_n, right_n).ratio()

    left_tokens = set(left_n.split())
    right_tokens = set(right_n.split())
    union = left_tokens | right_tokens

    jaccard = (
        len(left_tokens & right_tokens) / len(union)
        if union
        else 0.0
    )

    return max(0.0, min(100.0, seq * 65.0 + jaccard * 35.0))


def extract_participants(title: Any) -> tuple[str, ...]:
    normalized = normalize(title)
    match = re.search(r"^(?:will\s+)?(.+?)\s+vs\s+(.+?)(?:\?|:|$)", normalized)

    if not match:
        return ()

    return tuple(part.strip(" -?:") for part in match.groups())


def market_type(title: Any) -> str:
    value = normalize(title)

    if "exact score" in value:
        return "EXACT_SCORE"
    if "total corners" in value:
        return "CORNERS_TOTAL"
    if "o/u" in value:
        return "TOTAL"
    if "btts" in value:
        return "BTTS"
    if "spread:" in value:
        return "SPREAD"
    if "team to advance" in value:
        return "ADVANCE"
    if value.startswith("will ") and " win " in value:
        return "MONEYLINE"
    if " vs " in value:
        return "MATCH"

    return "OTHER"


def connect() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def columns(connection: sqlite3.Connection, name: str) -> set[str]:
    if not table_exists(connection, name):
        return set()
    return {
        text(row["name"])
        for row in connection.execute(f'PRAGMA table_info("{name}")')
    }


def create_tables() -> None:
    connection = connect()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_identities (
                canonical_key TEXT PRIMARY KEY,
                canonical_condition_id TEXT,
                gamma_market_id TEXT,
                gamma_event_id TEXT,
                market_slug TEXT,
                event_slug TEXT,
                canonical_title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                outcome TEXT,
                normalized_outcome TEXT,
                market_type TEXT,
                participant_one TEXT,
                participant_two TEXT,
                game_start_time TEXT,
                active INTEGER,
                closed INTEGER,
                resolved INTEGER,
                payload_json TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_market_identities_condition
            ON market_identities(canonical_condition_id);

            CREATE INDEX IF NOT EXISTS idx_market_identities_title
            ON market_identities(normalized_title);

            CREATE TABLE IF NOT EXISTS market_identity_aliases (
                alias_key TEXT PRIMARY KEY,
                canonical_key TEXT NOT NULL,
                alias_type TEXT NOT NULL,
                alias_value TEXT NOT NULL,
                normalized_alias TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 100,
                source_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_market_identity_aliases_lookup
            ON market_identity_aliases(alias_type, normalized_alias);

            CREATE TABLE IF NOT EXISTS market_identity_matches (
                source_key TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                source_market_id TEXT,
                source_title TEXT NOT NULL,
                source_outcome TEXT,
                canonical_key TEXT,
                matched_condition_id TEXT,
                matched_title TEXT,
                match_method TEXT NOT NULL,
                match_confidence REAL NOT NULL DEFAULT 0,
                accepted INTEGER NOT NULL DEFAULT 0,
                review_required INTEGER NOT NULL DEFAULT 0,
                rejection_reason TEXT,
                details_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_market_identity_matches_result
            ON market_identity_matches(accepted, match_method, match_confidence DESC);

            CREATE TABLE IF NOT EXISTS market_identity_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                gamma_events_loaded INTEGER NOT NULL DEFAULT 0,
                gamma_markets_loaded INTEGER NOT NULL DEFAULT 0,
                local_sources_loaded INTEGER NOT NULL DEFAULT 0,
                accepted_matches INTEGER NOT NULL DEFAULT 0,
                review_matches INTEGER NOT NULL DEFAULT 0,
                unresolved_sources INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def fetch_gamma_events(limit: int, max_pages: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for page in range(max_pages):
        query = urllib.parse.urlencode(
            {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": page * limit,
            }
        )

        request = urllib.request.Request(
            f"{GAMMA_EVENTS_URL}?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": "Polymarket-Intelligence-Platform/1.0",
            },
        )

        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)

        if not isinstance(payload, list):
            break

        batch = [item for item in payload if isinstance(item, dict)]
        events.extend(batch)

        if len(batch) < limit:
            break

    return events


def flatten_markets(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for event in events:
        for market in event.get("markets") or []:
            if not isinstance(market, dict):
                continue

            item = dict(market)
            item["_event_id"] = text(event.get("id"))
            item["_event_slug"] = text(event.get("slug"))
            item["_event_title"] = text(event.get("title") or event.get("question"))
            item["_event_start"] = text(
                event.get("startDate")
                or event.get("startTime")
                or event.get("gameStartTime")
            )
            output.append(item)

    return output


def save_gamma_markets(markets: list[dict[str, Any]]) -> None:
    connection = connect()
    timestamp = now_iso()

    try:
        connection.execute("BEGIN IMMEDIATE")

        for market in markets:
            condition_id = text(
                market.get("conditionId") or market.get("condition_id")
            ).lower()
            gamma_market_id = text(market.get("id"))
            title = text(
                market.get("question")
                or market.get("title")
                or market.get("_event_title")
            )
            outcome = text(market.get("outcome"))
            participants = extract_participants(title)

            canonical_key = (
                condition_id
                if CONDITION_ID_RE.match(condition_id)
                else (
                    f"gamma:{gamma_market_id}"
                    if gamma_market_id
                    else f"hash:{hash_key(title, outcome, market.get('_event_slug'))}"
                )
            )

            record = {
                "canonical_key": canonical_key,
                "canonical_condition_id": condition_id,
                "gamma_market_id": gamma_market_id,
                "gamma_event_id": text(market.get("_event_id")),
                "market_slug": text(market.get("slug")),
                "event_slug": text(market.get("_event_slug")),
                "canonical_title": title,
                "normalized_title": normalize(title),
                "outcome": outcome,
                "normalized_outcome": normalize(outcome),
                "market_type": market_type(title),
                "participant_one": participants[0] if len(participants) > 0 else "",
                "participant_two": participants[1] if len(participants) > 1 else "",
                "game_start_time": text(
                    market.get("gameStartTime")
                    or market.get("startDate")
                    or market.get("startTime")
                    or market.get("_event_start")
                ),
                "active": int(bool(market.get("active"))),
                "closed": int(bool(market.get("closed"))),
                "resolved": int(bool(market.get("resolved"))),
                "payload_json": json.dumps(market, ensure_ascii=False, default=str),
            }

            connection.execute(
                """
                INSERT INTO market_identities (
                    canonical_key, canonical_condition_id, gamma_market_id,
                    gamma_event_id, market_slug, event_slug, canonical_title,
                    normalized_title, outcome, normalized_outcome, market_type,
                    participant_one, participant_two, game_start_time,
                    active, closed, resolved, payload_json,
                    first_seen_at, last_seen_at, updated_at
                )
                VALUES (
                    :canonical_key, :canonical_condition_id, :gamma_market_id,
                    :gamma_event_id, :market_slug, :event_slug, :canonical_title,
                    :normalized_title, :outcome, :normalized_outcome, :market_type,
                    :participant_one, :participant_two, :game_start_time,
                    :active, :closed, :resolved, :payload_json,
                    :timestamp, :timestamp, :timestamp
                )
                ON CONFLICT(canonical_key) DO UPDATE SET
                    canonical_condition_id=excluded.canonical_condition_id,
                    gamma_market_id=excluded.gamma_market_id,
                    gamma_event_id=excluded.gamma_event_id,
                    market_slug=excluded.market_slug,
                    event_slug=excluded.event_slug,
                    canonical_title=excluded.canonical_title,
                    normalized_title=excluded.normalized_title,
                    outcome=excluded.outcome,
                    normalized_outcome=excluded.normalized_outcome,
                    market_type=excluded.market_type,
                    participant_one=excluded.participant_one,
                    participant_two=excluded.participant_two,
                    game_start_time=excluded.game_start_time,
                    active=excluded.active,
                    closed=excluded.closed,
                    resolved=excluded.resolved,
                    payload_json=excluded.payload_json,
                    last_seen_at=excluded.last_seen_at,
                    updated_at=excluded.updated_at
                """,
                {**record, "timestamp": timestamp},
            )

            for alias_type, alias_value in (
                ("CONDITION_ID", condition_id),
                ("MARKET_SLUG", record["market_slug"]),
                ("EVENT_SLUG", record["event_slug"]),
                ("TITLE", title),
                ("NORMALIZED_TITLE", record["normalized_title"]),
            ):
                if not alias_value:
                    continue

                normalized_alias = (
                    alias_value.lower()
                    if alias_type == "CONDITION_ID"
                    else normalize(alias_value)
                )

                connection.execute(
                    """
                    INSERT INTO market_identity_aliases (
                        alias_key, canonical_key, alias_type, alias_value,
                        normalized_alias, confidence, source_name,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 100, 'GAMMA', ?, ?)
                    ON CONFLICT(alias_key) DO UPDATE SET
                        alias_value=excluded.alias_value,
                        normalized_alias=excluded.normalized_alias,
                        updated_at=excluded.updated_at
                    """,
                    (
                        hash_key(canonical_key, alias_type, normalized_alias),
                        canonical_key,
                        alias_type,
                        alias_value,
                        normalized_alias,
                        timestamp,
                        timestamp,
                    ),
                )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def load_local_sources() -> list[dict[str, Any]]:
    connection = connect()
    output: dict[str, dict[str, Any]] = {}

    try:
        for table_name in (
            "opportunity_scores",
            "market_metadata",
            "consensus_history",
            "positions",
        ):
            if not table_exists(connection, table_name):
                continue

            available = columns(connection, table_name)

            if "market_id" not in available or "title" not in available:
                continue

            wanted = ["market_id", "title"]

            for optional in ("outcome", "game_start_time", "start_time", "slug"):
                if optional in available:
                    wanted.append(optional)

            rows = connection.execute(
                f"""
                SELECT {", ".join(wanted)}
                FROM "{table_name}"
                WHERE market_id IS NOT NULL
                  AND TRIM(CAST(market_id AS TEXT)) != ''
                  AND title IS NOT NULL
                  AND TRIM(CAST(title AS TEXT)) != ''
                """
            ).fetchall()

            for row in rows:
                market_id = text(row["market_id"]).lower()
                title = text(row["title"])
                outcome = text(row["outcome"]) if "outcome" in row.keys() else ""
                start_time = ""

                for field in ("game_start_time", "start_time"):
                    if field in row.keys():
                        start_time = text(row[field]) or start_time

                source = {
                    "source_name": table_name.upper(),
                    "market_id": market_id,
                    "title": title,
                    "outcome": outcome,
                    "normalized_title": normalize(title),
                    "normalized_outcome": normalize(outcome),
                    "market_type": market_type(title),
                    "participants": extract_participants(title),
                    "start_time": start_time,
                    "slug": text(row["slug"]) if "slug" in row.keys() else "",
                }

                source_key = hash_key(
                    source["source_name"],
                    market_id,
                    source["normalized_title"],
                    source["normalized_outcome"],
                )

                source["source_key"] = source_key
                output[source_key] = source

    finally:
        connection.close()

    return list(output.values())


def load_candidates() -> list[dict[str, Any]]:
    connection = connect()

    try:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM market_identities"
            ).fetchall()
        ]
    finally:
        connection.close()


def match_source(
    source: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    market_id = source["market_id"]

    if CONDITION_ID_RE.match(market_id):
        for candidate in candidates:
            if text(candidate.get("canonical_condition_id")).lower() == market_id:
                return result(source, candidate, "CONDITION_ID", 100.0, True)

    if source["slug"]:
        source_slug = slugify(source["slug"])

        for candidate in candidates:
            if source_slug in {
                slugify(candidate.get("market_slug")),
                slugify(candidate.get("event_slug")),
            }:
                return result(source, candidate, "SLUG", 99.0, True)

    normalized_matches = [
        candidate
        for candidate in candidates
        if text(candidate.get("normalized_title")) == source["normalized_title"]
    ]

    if len(normalized_matches) == 1:
        return result(
            source,
            normalized_matches[0],
            "NORMALIZED_TITLE",
            100.0,
            True,
        )

    ranked: list[tuple[float, dict[str, Any]]] = []

    for candidate in candidates:
        candidate_type = text(candidate.get("market_type"))

        if (
            source["market_type"] not in {"OTHER", "MATCH"}
            and candidate_type not in {
                source["market_type"],
                "OTHER",
                "MATCH",
            }
        ):
            continue

        score = similarity(
            source["title"],
            candidate.get("canonical_title"),
        )

        ranked.append((score, candidate))

    ranked.sort(key=lambda item: item[0], reverse=True)

    if not ranked:
        return result(source, None, "UNRESOLVED", 0.0, False)

    best_score, best_candidate = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
    margin = best_score - runner_up

    if best_score >= 94.0 and margin >= 4.0:
        return result(source, best_candidate, "FUZZY_FALLBACK", best_score, True)

    if best_score >= 84.0:
        return result(
            source,
            best_candidate,
            "REVIEW_REQUIRED",
            best_score,
            False,
            review_required=True,
            rejection_reason="Plausible match did not meet automatic threshold.",
        )

    return result(
        source,
        None,
        "UNRESOLVED",
        best_score,
        False,
        rejection_reason="No candidate met the minimum threshold.",
    )


def result(
    source: dict[str, Any],
    candidate: dict[str, Any] | None,
    method: str,
    confidence: float,
    accepted: bool,
    review_required: bool = False,
    rejection_reason: str = "",
) -> dict[str, Any]:
    timestamp = now_iso()

    return {
        "source_key": source["source_key"],
        "source_name": source["source_name"],
        "source_market_id": source["market_id"],
        "source_title": source["title"],
        "source_outcome": source["outcome"],
        "canonical_key": text(candidate.get("canonical_key")) if candidate else None,
        "matched_condition_id": (
            text(candidate.get("canonical_condition_id"))
            if candidate
            else ""
        ),
        "matched_title": (
            text(candidate.get("canonical_title"))
            if candidate
            else ""
        ),
        "match_method": method,
        "match_confidence": confidence,
        "accepted": int(accepted),
        "review_required": int(review_required),
        "rejection_reason": rejection_reason,
        "details_json": json.dumps(
            {
                "source_normalized_title": source["normalized_title"],
                "source_market_type": source["market_type"],
                "candidate_normalized_title": (
                    text(candidate.get("normalized_title"))
                    if candidate
                    else ""
                ),
                "title_similarity": (
                    similarity(source["title"], candidate.get("canonical_title"))
                    if candidate
                    else 0.0
                ),
            },
            ensure_ascii=False,
        ),
        "calculated_at": timestamp,
        "updated_at": timestamp,
    }


def save_matches(matches: list[dict[str, Any]]) -> None:
    connection = connect()
    columns_to_save = [
        "source_key",
        "source_name",
        "source_market_id",
        "source_title",
        "source_outcome",
        "canonical_key",
        "matched_condition_id",
        "matched_title",
        "match_method",
        "match_confidence",
        "accepted",
        "review_required",
        "rejection_reason",
        "details_json",
        "calculated_at",
        "updated_at",
    ]

    names = ", ".join(f'"{name}"' for name in columns_to_save)
    placeholders = ", ".join("?" for _ in columns_to_save)
    updates = ", ".join(
        f'"{name}"=excluded."{name}"'
        for name in columns_to_save
        if name != "source_key"
    )

    query = f"""
        INSERT INTO market_identity_matches ({names})
        VALUES ({placeholders})
        ON CONFLICT(source_key) DO UPDATE SET {updates}
    """

    try:
        connection.execute("BEGIN IMMEDIATE")

        for match in matches:
            connection.execute(
                query,
                tuple(match[name] for name in columns_to_save),
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def start_run() -> tuple[int, datetime]:
    started = datetime.now(timezone.utc)
    connection = connect()

    try:
        cursor = connection.execute(
            """
            INSERT INTO market_identity_runs(started_at, status)
            VALUES (?, 'RUNNING')
            """,
            (started.isoformat(),),
        )
        connection.commit()
        return cursor.lastrowid, started
    finally:
        connection.close()


def finish_run(
    run_id: int,
    started: datetime,
    status: str,
    event_count: int,
    market_count: int,
    source_count: int,
    matches: list[dict[str, Any]],
    error_message: str = "",
) -> None:
    finished = datetime.now(timezone.utc)
    accepted = sum(item["accepted"] for item in matches)
    reviews = sum(item["review_required"] for item in matches)
    unresolved = sum(
        1
        for item in matches
        if item["match_method"] == "UNRESOLVED"
    )

    connection = connect()

    try:
        connection.execute(
            """
            UPDATE market_identity_runs
            SET finished_at=?,
                elapsed_seconds=?,
                gamma_events_loaded=?,
                gamma_markets_loaded=?,
                local_sources_loaded=?,
                accepted_matches=?,
                review_matches=?,
                unresolved_sources=?,
                status=?,
                error_message=?
            WHERE id=?
            """,
            (
                finished.isoformat(),
                (finished - started).total_seconds(),
                event_count,
                market_count,
                source_count,
                accepted,
                reviews,
                unresolved,
                status,
                error_message,
                run_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create canonical Polymarket market identities."
    )
    parser.add_argument("--event-limit", type=int, default=500)
    parser.add_argument("--max-event-pages", type=int, default=4)
    parser.add_argument("--display-limit", type=int, default=30)
    parser.add_argument("--local-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    configure_utf8()
    args = parse_args()

    print()
    print("=" * 108)
    print("POLYMARKET MARKET IDENTITY ENGINE v1")
    print("=" * 108)
    print(f"Database: {DATABASE_PATH}")

    create_tables()
    run_id, started = start_run()

    events: list[dict[str, Any]] = []
    markets: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []

    try:
        if not args.local_only:
            events = fetch_gamma_events(
                max(args.event_limit, 1),
                max(args.max_event_pages, 1),
            )
            markets = flatten_markets(events)
            save_gamma_markets(markets)

        sources = load_local_sources()
        candidates = load_candidates()

        for index, source in enumerate(sources, start=1):
            match = match_source(source, candidates)
            matches.append(match)

            marker = (
                "OK"
                if match["accepted"]
                else (
                    "REVIEW"
                    if match["review_required"]
                    else "MISS"
                )
            )

            print(
                f"[{index}/{len(sources)}] "
                f"{marker:<7} "
                f"{match['match_method']:<20} "
                f"{source['title'][:58]}"
            )

        save_matches(matches)
        finish_run(
            run_id,
            started,
            "SUCCESS",
            len(events),
            len(markets),
            len(sources),
            matches,
        )

        counts = Counter(item["match_method"] for item in matches)

        print()
        print("=" * 108)
        print("MARKET IDENTITY SUMMARY")
        print("=" * 108)
        print(f"Gamma events loaded:            {len(events)}")
        print(f"Gamma markets loaded:           {len(markets)}")
        print(f"Local sources loaded:           {len(sources)}")
        print(f"Automatically accepted:         {sum(item['accepted'] for item in matches)}")
        print(f"Review required:                {sum(item['review_required'] for item in matches)}")
        print(f"Unresolved:                     {counts.get('UNRESOLVED', 0)}")
        print()
        print("MATCH METHOD COUNTS")

        for method, count in counts.most_common():
            print(f"{method:<36}{count:>8}")

        print("=" * 108)

        ranked = sorted(
            matches,
            key=lambda item: (
                item["accepted"],
                item["match_confidence"],
            ),
            reverse=True,
        )

        print()
        print("TOP MARKET IDENTITY MATCHES")

        for rank, match in enumerate(
            ranked[: max(args.display_limit, 1)],
            start=1,
        ):
            print()
            print("-" * 108)
            print(f"{rank}. {match['source_title']}")
            print("-" * 108)
            print(f"Method:                         {match['match_method']}")
            print(f"Confidence:                     {match['match_confidence']:.1f}/100")
            print(f"Accepted / review:              {bool(match['accepted'])} / {bool(match['review_required'])}")
            print(f"Matched title:                  {match['matched_title'] or '-'}")
            print(f"Condition ID:                   {match['matched_condition_id'] or '-'}")

        print()
        print("=" * 108)
        print("MARKET IDENTITY ENGINE COMPLETE")
        print("=" * 108)
        print("Canonical markets: market_identities")
        print("Aliases: market_identity_aliases")
        print("Matches: market_identity_matches")
        print("Run history: market_identity_runs")
        print("=" * 108)

    except Exception as error:
        finish_run(
            run_id,
            started,
            "FAILED",
            len(events),
            len(markets),
            len(sources),
            matches,
            f"{type(error).__name__}: {error}",
        )
        raise


if __name__ == "__main__":
    main()