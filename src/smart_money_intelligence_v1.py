from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
CONFIG_PATH = PROJECT_ROOT / "config" / "smart_money_intelligence_v1.json"
SQL_PATH = PROJECT_ROOT / "migrations" / "smart_money_intelligence_v1.sql"
ENGINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class MarketSignal:
    market_id: str
    title: str
    outcome: str
    category: str
    wallet_count: int
    elite_wallet_count: int
    consensus_wallet_count: int
    combined_capital: float
    weighted_capital: float
    agreement_ratio: float
    disagreement_ratio: float
    average_wallet_score: float
    leader_wallet: str | None
    leader_score: float
    heat_score: float
    signal_grade: str
    signal_status: str
    rationale_json: str
    evidence_json: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def require_schema(connection: sqlite3.Connection) -> None:
    required = {
        "positions": {
            "wallet", "market_id", "title", "outcome", "current_value",
            "average_price", "current_price",
        },
        "elite_wallet_profiles": {
            "wallet", "confidence_adjusted_score", "influence_weight",
            "consensus_eligible", "elite_eligible", "elite_tier",
            "overall_grade",
        },
    }
    failures: list[str] = []
    for table_name, required_columns in required.items():
        actual = table_columns(connection, table_name)
        if not actual:
            failures.append(f"missing table: {table_name}")
            continue
        failures.extend(
            f"missing column: {table_name}.{column}"
            for column in sorted(required_columns - actual)
        )
    if failures:
        raise RuntimeError("; ".join(failures))


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SQL_PATH.read_text(encoding="utf-8"))


def category_from_title(title: str) -> str:
    text = (title or "").lower()
    mapping = {
        "Soccer": ("soccer", "football", "fifa", "world cup", "premier league", "champions league"),
        "Basketball": ("nba", "wnba", "basketball", "ncaa"),
        "Baseball": ("mlb", "baseball"),
        "UFC": ("ufc", "mma", "fight"),
        "Politics": ("president", "election", "nomination", "senate", "congress", "governor"),
        "Crypto": ("bitcoin", "ethereum", "crypto", "solana", "btc", "eth"),
        "Economics": ("cpi", "inflation", "fed", "interest rate", "gdp", "unemployment"),
        "Entertainment": ("movie", "oscars", "grammy", "box office", "album"),
    }
    for category, terms in mapping.items():
        if any(term in text for term in terms):
            return category
    return "Other"


def score_to_grade(score: float) -> str:
    if score >= 85:
        return "S+"
    if score >= 75:
        return "S"
    if score >= 65:
        return "A"
    if score >= 55:
        return "B"
    if score >= 45:
        return "WATCH"
    return "PASS"


def score_to_status(
    score: float,
    agreement_ratio: float,
    disagreement_ratio: float,
    config: dict[str, Any],
) -> str:
    if (
        score >= float(config["strong_consensus_score"])
        and agreement_ratio >= float(config["strong_consensus_agreement"])
    ):
        return "STRONG_ELITE_CONSENSUS"
    if disagreement_ratio >= float(config["high_disagreement_threshold"]):
        return "ELITE_DISAGREEMENT"
    if score >= float(config["watch_score"]):
        return "SMART_MONEY_WATCH"
    return "LOW_SIGNAL"


def load_wallet_profiles(
    connection: sqlite3.Connection,
) -> dict[str, sqlite3.Row]:
    rows = connection.execute(
        """
        SELECT wallet, confidence_adjusted_score, influence_weight,
               consensus_eligible, elite_eligible, elite_tier, overall_grade
        FROM elite_wallet_profiles
        """
    ).fetchall()
    return {str(row["wallet"]): row for row in rows}


def load_position_groups(
    connection: sqlite3.Connection,
) -> dict[tuple[str, str], list[sqlite3.Row]]:
    rows = connection.execute(
        """
        SELECT wallet, market_id, title, outcome, current_value,
               average_price, current_price
        FROM positions
        WHERE wallet IS NOT NULL
          AND TRIM(wallet) <> ''
          AND market_id IS NOT NULL
          AND outcome IS NOT NULL
        """
    ).fetchall()
    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        key = (str(row["market_id"]), str(row["outcome"]))
        groups.setdefault(key, []).append(row)
    return groups


def opposing_outcomes(
    groups: dict[tuple[str, str], list[sqlite3.Row]],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for market_id, outcome in groups:
        result.setdefault(market_id, set()).add(outcome)
    return result


def compute_signal(
    key: tuple[str, str],
    rows: list[sqlite3.Row],
    profiles: dict[str, sqlite3.Row],
    outcome_map: dict[str, set[str]],
    config: dict[str, Any],
) -> MarketSignal | None:
    market_id, outcome = key
    qualified: list[tuple[sqlite3.Row, sqlite3.Row]] = []
    for row in rows:
        profile = profiles.get(str(row["wallet"]))
        if not profile:
            continue
        if not int(profile["consensus_eligible"] or 0):
            continue
        qualified.append((row, profile))

    if len(qualified) < int(config["minimum_wallets"]):
        return None

    title = str(qualified[0][0]["title"] or "")
    category = category_from_title(title)
    wallet_count = len(qualified)
    elite_wallet_count = sum(
        int(profile["elite_eligible"] or 0)
        for _, profile in qualified
    )
    consensus_wallet_count = wallet_count

    combined_capital = sum(
        max(float(row["current_value"] or 0.0), 0.0)
        for row, _ in qualified
    )
    weighted_capital = sum(
        max(float(row["current_value"] or 0.0), 0.0)
        * max(float(profile["influence_weight"] or 0.0), 0.0)
        for row, profile in qualified
    )
    scores = [
        float(profile["confidence_adjusted_score"] or 0.0)
        for _, profile in qualified
    ]
    average_wallet_score = sum(scores) / len(scores)

    all_outcomes = outcome_map.get(market_id, {outcome})
    agreement_ratio = 1.0 / max(len(all_outcomes), 1)
    same_market_wallets = sum(
        len(groups_rows)
        for (group_market, _), groups_rows in config["_groups"].items()
        if group_market == market_id
    )
    disagreement_ratio = (
        1.0 - (wallet_count / same_market_wallets)
        if same_market_wallets > 0 else 0.0
    )

    leader_row, leader_profile = max(
        qualified,
        key=lambda item: (
            float(item[1]["confidence_adjusted_score"] or 0.0),
            float(item[0]["current_value"] or 0.0),
        ),
    )
    leader_wallet = str(leader_row["wallet"])
    leader_score = float(
        leader_profile["confidence_adjusted_score"] or 0.0
    )

    capital_score = clamp(
        math.log10(max(weighted_capital, 1.0))
        / float(config["capital_log_divisor"]) * 100.0
    )
    wallet_count_score = clamp(
        wallet_count / float(config["wallet_count_full_score"]) * 100.0
    )
    elite_share = elite_wallet_count / max(wallet_count, 1)
    agreement_score = clamp((1.0 - disagreement_ratio) * 100.0)
    heat_score = clamp(
        average_wallet_score * 0.30
        + capital_score * 0.25
        + wallet_count_score * 0.20
        + elite_share * 100.0 * 0.15
        + agreement_score * 0.10
    )
    grade = score_to_grade(heat_score)
    status = score_to_status(
        heat_score,
        agreement_ratio,
        disagreement_ratio,
        config,
    )

    rationale = {
        "summary": (
            f"{wallet_count} consensus-eligible wallets support {outcome} "
            f"with ${combined_capital:,.2f} combined capital."
        ),
        "drivers": {
            "average_wallet_score": round(average_wallet_score, 4),
            "weighted_capital": round(weighted_capital, 4),
            "elite_wallet_share": round(elite_share, 4),
            "agreement_ratio": round(agreement_ratio, 4),
            "disagreement_ratio": round(disagreement_ratio, 4),
        },
        "leader": {
            "wallet": leader_wallet,
            "score": round(leader_score, 4),
        },
    }
    evidence = {
        "wallets": [
            {
                "wallet": str(row["wallet"]),
                "capital": round(float(row["current_value"] or 0.0), 4),
                "score": round(
                    float(profile["confidence_adjusted_score"] or 0.0), 4
                ),
                "elite_eligible": int(profile["elite_eligible"] or 0),
                "tier": profile["elite_tier"],
                "grade": profile["overall_grade"],
            }
            for row, profile in sorted(
                qualified,
                key=lambda item: float(
                    item[1]["confidence_adjusted_score"] or 0.0
                ),
                reverse=True,
            )
        ]
    }

    return MarketSignal(
        market_id=market_id,
        title=title,
        outcome=outcome,
        category=category,
        wallet_count=wallet_count,
        elite_wallet_count=elite_wallet_count,
        consensus_wallet_count=consensus_wallet_count,
        combined_capital=round(combined_capital, 4),
        weighted_capital=round(weighted_capital, 4),
        agreement_ratio=round(agreement_ratio, 6),
        disagreement_ratio=round(disagreement_ratio, 6),
        average_wallet_score=round(average_wallet_score, 4),
        leader_wallet=leader_wallet,
        leader_score=round(leader_score, 4),
        heat_score=round(heat_score, 4),
        signal_grade=grade,
        signal_status=status,
        rationale_json=json.dumps(rationale, sort_keys=True),
        evidence_json=json.dumps(evidence, sort_keys=True),
    )


def signal_checksum(signal: MarketSignal) -> str:
    payload = json.dumps(signal.__dict__, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def upsert_signal(
    connection: sqlite3.Connection,
    signal: MarketSignal,
    observed_at: str,
) -> None:
    checksum = signal_checksum(signal)
    connection.execute(
        """
        INSERT INTO smart_money_market_signals (
            market_id, title, outcome, category, wallet_count,
            elite_wallet_count, consensus_wallet_count, combined_capital,
            weighted_capital, agreement_ratio, disagreement_ratio,
            average_wallet_score, leader_wallet, leader_score, heat_score,
            signal_grade, signal_status, rationale_json, evidence_json,
            signal_checksum, engine_version, first_observed_at,
            last_observed_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        ON CONFLICT(market_id, outcome) DO UPDATE SET
            title=excluded.title,
            category=excluded.category,
            wallet_count=excluded.wallet_count,
            elite_wallet_count=excluded.elite_wallet_count,
            consensus_wallet_count=excluded.consensus_wallet_count,
            combined_capital=excluded.combined_capital,
            weighted_capital=excluded.weighted_capital,
            agreement_ratio=excluded.agreement_ratio,
            disagreement_ratio=excluded.disagreement_ratio,
            average_wallet_score=excluded.average_wallet_score,
            leader_wallet=excluded.leader_wallet,
            leader_score=excluded.leader_score,
            heat_score=excluded.heat_score,
            signal_grade=excluded.signal_grade,
            signal_status=excluded.signal_status,
            rationale_json=excluded.rationale_json,
            evidence_json=excluded.evidence_json,
            signal_checksum=excluded.signal_checksum,
            engine_version=excluded.engine_version,
            last_observed_at=excluded.last_observed_at,
            updated_at=excluded.updated_at
        """,
        (
            signal.market_id, signal.title, signal.outcome, signal.category,
            signal.wallet_count, signal.elite_wallet_count,
            signal.consensus_wallet_count, signal.combined_capital,
            signal.weighted_capital, signal.agreement_ratio,
            signal.disagreement_ratio, signal.average_wallet_score,
            signal.leader_wallet, signal.leader_score, signal.heat_score,
            signal.signal_grade, signal.signal_status,
            signal.rationale_json, signal.evidence_json, checksum,
            ENGINE_VERSION, observed_at, observed_at, observed_at,
        ),
    )

    existing = connection.execute(
        """
        SELECT 1
        FROM smart_money_signal_history
        WHERE market_id=? AND outcome=? AND signal_checksum=?
        LIMIT 1
        """,
        (signal.market_id, signal.outcome, checksum),
    ).fetchone()
    if not existing:
        connection.execute(
            """
            INSERT INTO smart_money_signal_history (
                market_id, title, outcome, category, wallet_count,
                elite_wallet_count, combined_capital, weighted_capital,
                agreement_ratio, disagreement_ratio, average_wallet_score,
                leader_wallet, leader_score, heat_score, signal_grade,
                signal_status, rationale_json, evidence_json,
                signal_checksum, engine_version, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.market_id, signal.title, signal.outcome,
                signal.category, signal.wallet_count,
                signal.elite_wallet_count, signal.combined_capital,
                signal.weighted_capital, signal.agreement_ratio,
                signal.disagreement_ratio, signal.average_wallet_score,
                signal.leader_wallet, signal.leader_score,
                signal.heat_score, signal.signal_grade,
                signal.signal_status, signal.rationale_json,
                signal.evidence_json, checksum, ENGINE_VERSION,
                observed_at,
            ),
        )


def publish_event(
    connection: sqlite3.Connection,
    signal: MarketSignal,
    observed_at: str,
) -> None:
    columns = table_columns(connection, "platform_events")
    required = {
        "event_id", "event_type", "source_engine", "source_version",
        "aggregate_type", "aggregate_id", "payload_json", "occurred_at",
        "stored_at", "deduplication_key", "status"
    }
    if not required.issubset(columns):
        return

    event_type = {
        "STRONG_ELITE_CONSENSUS": "StrongEliteConsensusDetected",
        "ELITE_DISAGREEMENT": "EliteDisagreementDetected",
        "SMART_MONEY_WATCH": "SmartMoneyWatchDetected",
    }.get(signal.signal_status)
    if not event_type:
        return

    checksum = signal_checksum(signal)
    event_id = hashlib.sha256(
        f"{event_type}:{signal.market_id}:{signal.outcome}:{checksum}".encode()
    ).hexdigest()
    payload = json.dumps({
        "market_id": signal.market_id,
        "title": signal.title,
        "outcome": signal.outcome,
        "heat_score": signal.heat_score,
        "signal_grade": signal.signal_grade,
        "signal_status": signal.signal_status,
        "wallet_count": signal.wallet_count,
        "elite_wallet_count": signal.elite_wallet_count,
        "combined_capital": signal.combined_capital,
        "leader_wallet": signal.leader_wallet,
    }, sort_keys=True)

    connection.execute(
        """
        INSERT OR IGNORE INTO platform_events (
            event_id, event_type, source_engine, source_version,
            aggregate_type, aggregate_id, payload_json, occurred_at,
            stored_at, deduplication_key, status, processing_attempts
        ) VALUES (?, ?, ?, ?, 'market', ?, ?, ?, ?, ?, 'PENDING', 0)
        """,
        (
            event_id, event_type, "smart_money_intelligence_v1",
            ENGINE_VERSION, signal.market_id, payload, observed_at,
            observed_at, event_id,
        ),
    )


def print_board(connection: sqlite3.Connection, limit: int) -> None:
    rows = connection.execute(
        """
        SELECT market_id, title, outcome, category, wallet_count,
               elite_wallet_count, combined_capital, heat_score,
               signal_grade, signal_status, leader_wallet
        FROM ranked_smart_money_signals
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    print()
    print("SMART MONEY INTELLIGENCE v1 BOARD")
    print("-" * 160)
    for index, row in enumerate(rows, start=1):
        title = str(row["title"] or "")
        title = title if len(title) <= 58 else title[:55] + "..."
        leader = str(row["leader_wallet"] or "")
        leader = leader[:8] + "..." + leader[-6:] if len(leader) > 18 else leader
        print(
            f"{index:>3} "
            f"{float(row['heat_score'] or 0):>6.2f} "
            f"{str(row['signal_grade'] or ''):<6} "
            f"{str(row['signal_status'] or ''):<25} "
            f"W:{int(row['wallet_count'] or 0):>3} "
            f"E:{int(row['elite_wallet_count'] or 0):>3} "
            f"${float(row['combined_capital'] or 0):>12,.2f} "
            f"{str(row['outcome'] or ''):<10} "
            f"{title:<58} "
            f"{leader}"
        )
    print("-" * 160)


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1

    observed_at = utc_now()
    config = load_config()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        require_schema(connection)
        ensure_schema(connection)

        profiles = load_wallet_profiles(connection)
        groups = load_position_groups(connection)
        outcome_map = opposing_outcomes(groups)
        config["_groups"] = groups

        written = 0
        history_before = connection.execute(
            "SELECT COUNT(*) FROM smart_money_signal_history"
        ).fetchone()[0]
        events_before = connection.execute(
            """
            SELECT COUNT(*)
            FROM platform_events
            WHERE source_engine='smart_money_intelligence_v1'
            """
        ).fetchone()[0] if table_columns(connection, "platform_events") else 0

        for key, rows in groups.items():
            signal = compute_signal(
                key, rows, profiles, outcome_map, config
            )
            if not signal:
                continue
            upsert_signal(connection, signal, observed_at)
            publish_event(connection, signal, observed_at)
            written += 1

        connection.commit()

        history_after = connection.execute(
            "SELECT COUNT(*) FROM smart_money_signal_history"
        ).fetchone()[0]
        events_after = connection.execute(
            """
            SELECT COUNT(*)
            FROM platform_events
            WHERE source_engine='smart_money_intelligence_v1'
            """
        ).fetchone()[0] if table_columns(connection, "platform_events") else 0

        print_board(connection, int(config["board_limit"]))
        print()
        print("=" * 88)
        print(f"SMART MONEY INTELLIGENCE v{ENGINE_VERSION}")
        print("=" * 88)
        print(f"Signals evaluated and stored: {written:,}")
        print(f"History rows created:         {history_after - history_before:,}")
        print(f"Events published:             {events_after - events_before:,}")
        print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
