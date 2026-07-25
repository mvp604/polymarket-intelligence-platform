from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import statistics
import sys
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.platform_events import PlatformEvent, build_deduplication_key, create_event_tables, publish_event

DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "006_elite_wallet_intelligence.sql"
ENGINE_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def ensure_schema(connection: sqlite3.Connection) -> None:
    if not MIGRATION_PATH.exists():
        raise RuntimeError(f"Migration not found: {MIGRATION_PATH}")
    connection.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
    create_event_tables(connection)


def infer_category(title: str) -> str:
    value = (title or "").lower()
    groups = {
        "SOCCER": ("world cup", "corners", "team to advance", "both teams to score", "premier league", "la liga"),
        "BASKETBALL": ("nba", "wnba", "basketball", "rebounds"),
        "BASEBALL": ("mlb", "baseball", "home run", "strikeouts"),
        "FOOTBALL": ("nfl", "super bowl", "touchdown"),
        "HOCKEY": ("nhl", "stanley cup", "hockey"),
        "COMBAT": ("ufc", "mma", "boxing"),
        "TENNIS": ("tennis", "wimbledon", "us open"),
        "POLITICS": ("president", "election", "nomination", "senate", "governor"),
        "CRYPTO": ("bitcoin", "ethereum", "solana", "crypto", "btc", "eth"),
        "ECONOMY": ("fed", "interest rate", "inflation", "cpi", "gdp"),
    }
    for category, terms in groups.items():
        if any(term in value for term in terms):
            return category
    if " vs. " in value or " vs " in value:
        return "SOCCER"
    return "OTHER"


def load_positions(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    if not table_exists(connection, "positions"):
        raise RuntimeError("Required positions table is missing.")
    available = columns(connection, "positions")
    required = {"wallet", "market_id", "title", "outcome"}
    missing = required - available
    if missing:
        raise RuntimeError("positions table missing: " + ", ".join(sorted(missing)))

    def expr(candidates: tuple[str, ...], alias: str, default: str = "NULL") -> str:
        for candidate in candidates:
            if candidate in available:
                return f'p."{candidate}" AS "{alias}"'
        return f'{default} AS "{alias}"'

    fields = [
        'p."wallet" AS "wallet"',
        'p."market_id" AS "market_id"',
        'p."title" AS "title"',
        'p."outcome" AS "outcome"',
        expr(("shares", "size", "position_size"), "shares", "0"),
        expr(("average_price", "avg_price", "entry_price"), "average_price"),
        expr(("current_price", "price"), "current_price"),
        expr(("current_value", "value", "position_value"), "current_value", "0"),
        expr(("cash_pnl", "realized_pnl", "pnl"), "cash_pnl", "0"),
        expr(("percent_pnl", "roi_percent", "pnl_percent"), "percent_pnl", "0"),
        expr(("scanned_at", "observed_at", "updated_at"), "observed_at"),
        expr(("resolved", "is_resolved"), "resolved_flag"),
        expr(("won", "is_winner"), "won_flag"),
    ]
    return connection.execute(
        f'SELECT {", ".join(fields)} FROM positions p '
        "WHERE p.wallet IS NOT NULL AND TRIM(p.wallet) <> '' ORDER BY p.wallet"
    ).fetchall()


def is_resolved(row: sqlite3.Row) -> bool:
    if row["resolved_flag"] is not None:
        return bool(int(safe_float(row["resolved_flag"])))
    if row["current_price"] is None:
        return False
    price = safe_float(row["current_price"])
    return price <= 0.01 or price >= 0.99


def is_win(row: sqlite3.Row) -> bool:
    if row["won_flag"] is not None:
        return bool(int(safe_float(row["won_flag"])))
    return is_resolved(row) and safe_float(row["cash_pnl"]) > 0


def position_value(row: sqlite3.Row) -> float:
    current = max(0.0, safe_float(row["current_value"]))
    if current > 0:
        return current
    return max(0.0, safe_float(row["shares"])) * max(0.0, safe_float(row["average_price"]))


def logarithmic_score(value: float, reference: float) -> float:
    if value <= 0:
        return 0.0
    return clamp(100.0 * math.log1p(value) / math.log1p(reference))


def grade(score: float) -> str:
    if score >= 90: return "S+"
    if score >= 82: return "S"
    if score >= 74: return "A"
    if score >= 66: return "B"
    if score >= 55: return "WATCH"
    return "PASS"


def status(score: float, resolved: int, pnl: float, quality: float) -> str:
    if score >= 82 and resolved >= 20 and pnl > 0 and quality >= 70:
        return "ELITE"
    if score >= 72 and resolved >= 12 and pnl > 0 and quality >= 55:
        return "QUALIFIED"
    if score >= 58 and resolved >= 5:
        return "WATCHLIST"
    return "UNVERIFIED"


def consistency_score(pnls: list[float], hit_rate: float) -> float:
    if not pnls:
        return 0.0
    if len(pnls) == 1:
        return clamp(hit_rate * 0.6)
    mean = statistics.fmean(pnls)
    deviation = statistics.pstdev(pnls)
    stability = 100.0 / (1.0 + deviation / (abs(mean) + 25.0))
    downside = sum(pnl < 0 for pnl in pnls) / len(pnls)
    return clamp(stability * 0.55 + hit_rate * 0.35 + (1.0 - downside) * 10.0)


def sizing_discipline(values: list[float]) -> float:
    positive = [v for v in values if v > 0]
    if not positive:
        return 0.0
    if len(positive) == 1:
        return 45.0
    mean = statistics.fmean(positive)
    deviation = statistics.pstdev(positive)
    return clamp(100.0 / (1.0 + deviation / mean)) if mean > 0 else 0.0


def specialization(counts: Counter[str]) -> tuple[str, float]:
    total = sum(counts.values())
    if not total:
        return "OTHER", 0.0
    primary, count = counts.most_common(1)[0]
    return primary, clamp(count / total * 100.0 - max(0, len(counts) - 1) * 2.5)


def profile_wallet(wallet: str, rows: list[sqlite3.Row]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    values = [position_value(row) for row in rows]
    resolved_rows = [row for row in rows if is_resolved(row)]
    wins = sum(is_win(row) for row in resolved_rows)
    losses = len(resolved_rows) - wins
    realized = sum(safe_float(row["cash_pnl"]) for row in resolved_rows)
    unrealized = sum(safe_float(row["cash_pnl"]) for row in rows if not is_resolved(row))
    total_pnl = realized + unrealized
    deployed = sum(values)
    roi = total_pnl / deployed * 100.0 if deployed else 0.0
    hit_rate = wins / len(resolved_rows) * 100.0 if resolved_rows else 0.0
    category_counts = Counter(infer_category(str(row["title"] or "")) for row in rows)
    primary, specialization_value = specialization(category_counts)
    consistency = consistency_score([safe_float(row["cash_pnl"]) for row in resolved_rows], hit_rate)
    discipline = sizing_discipline(values)
    average_value = statistics.fmean(values) if values else 0.0
    conviction = clamp(
        logarithmic_score(deployed, 1_000_000.0) * 0.55
        + logarithmic_score(average_value, 100_000.0) * 0.45
    )
    activity = logarithmic_score(len(rows), 100.0)
    entries = [safe_float(row["average_price"]) for row in rows if row["average_price"] is not None]
    currents = [safe_float(row["current_price"]) for row in rows if row["current_price"] is not None]
    quality_flags = [
        bool(resolved_rows), deployed > 0, bool(entries), bool(currents),
        any(abs(safe_float(row["cash_pnl"])) > 0 for row in rows),
        len(rows) >= 5, len(resolved_rows) >= 5,
        any(category != "OTHER" for category in category_counts),
    ]
    quality = 100.0 * sum(quality_flags) / len(quality_flags)
    profitability = clamp(
        logarithmic_score(max(total_pnl, 0.0), 500_000.0) * 0.55
        + clamp(max(roi, 0.0)) * 0.45
    )
    score = clamp(
        profitability * 0.24 + hit_rate * 0.18 + consistency * 0.16
        + conviction * 0.13 + discipline * 0.09 + specialization_value * 0.08
        + activity * 0.06 + quality * 0.06
    )
    timestamps = [str(row["observed_at"]) for row in rows if row["observed_at"]]
    evidence = {
        "profitability_score": round(profitability, 4),
        "category_distribution": dict(category_counts),
        "source_table": "positions",
        "resolved_inference_used": any(row["resolved_flag"] is None for row in rows),
        "win_inference_used": any(row["won_flag"] is None for row in rows),
    }
    profile = {
        "wallet": wallet, "wallet_score": round(score, 4), "wallet_grade": grade(score),
        "elite_status": status(score, len(resolved_rows), total_pnl, quality),
        "total_positions": len(rows), "resolved_positions": len(resolved_rows),
        "winning_positions": wins, "losing_positions": losses,
        "realized_pnl": round(realized, 6), "unrealized_pnl": round(unrealized, 6),
        "total_pnl": round(total_pnl, 6), "deployed_capital": round(deployed, 6),
        "roi_percent": round(roi, 6), "hit_rate": round(hit_rate, 4),
        "consistency_score": round(consistency, 4),
        "conviction_score": round(conviction, 4),
        "sizing_discipline_score": round(discipline, 4),
        "specialization_score": round(specialization_value, 4),
        "activity_score": round(activity, 4), "data_quality_score": round(quality, 4),
        "primary_category": primary, "category_count": len(category_counts),
        "average_position_value": round(average_value, 6),
        "largest_position_value": round(max(values, default=0.0), 6),
        "average_entry_price": round(statistics.fmean(entries), 6) if entries else None,
        "average_current_price": round(statistics.fmean(currents), 6) if currents else None,
        "first_seen_at": min(timestamps, default=None),
        "last_seen_at": max(timestamps, default=None),
        "evidence": evidence,
    }
    profile["profile_checksum"] = checksum(profile)

    category_profiles = []
    for category in category_counts:
        subset = [row for row in rows if infer_category(str(row["title"] or "")) == category]
        resolved_subset = [row for row in subset if is_resolved(row)]
        category_wins = sum(is_win(row) for row in resolved_subset)
        category_values = [position_value(row) for row in subset]
        category_capital = sum(category_values)
        category_pnl = sum(safe_float(row["cash_pnl"]) for row in subset)
        category_roi = category_pnl / category_capital * 100.0 if category_capital else 0.0
        category_hit = category_wins / len(resolved_subset) * 100.0 if resolved_subset else 0.0
        category_score = clamp(
            category_hit * 0.35 + clamp(max(category_roi, 0.0)) * 0.25
            + logarithmic_score(max(category_pnl, 0.0), 250_000.0) * 0.20
            + logarithmic_score(len(subset), 40.0) * 0.20
        )
        stamps = [str(row["observed_at"]) for row in subset if row["observed_at"]]
        item = {
            "wallet": wallet, "category": category, "position_count": len(subset),
            "resolved_positions": len(resolved_subset), "winning_positions": category_wins,
            "losing_positions": len(resolved_subset) - category_wins,
            "total_pnl": round(category_pnl, 6), "deployed_capital": round(category_capital, 6),
            "roi_percent": round(category_roi, 6), "hit_rate": round(category_hit, 4),
            "category_score": round(category_score, 4), "category_grade": grade(category_score),
            "first_seen_at": min(stamps, default=None), "last_seen_at": max(stamps, default=None),
            "evidence": {"share_of_wallet_activity": round(len(subset) / len(rows), 6)},
        }
        item["profile_checksum"] = checksum(item)
        category_profiles.append(item)
    return profile, category_profiles


def upsert_profile(connection: sqlite3.Connection, profile: dict[str, Any], categories: list[dict[str, Any]], run_id: str, observed_at: str) -> str:
    old = connection.execute(
        "SELECT profile_checksum, first_profiled_at FROM elite_wallet_profiles WHERE wallet=?",
        (profile["wallet"],),
    ).fetchone()
    state = "created" if old is None else ("updated" if old["profile_checksum"] != profile["profile_checksum"] else "unchanged")
    first_profiled = old["first_profiled_at"] if old else observed_at
    connection.execute(
        """INSERT INTO elite_wallet_profiles (
            wallet, profile_checksum, wallet_score, wallet_grade, elite_status,
            total_positions, resolved_positions, winning_positions, losing_positions,
            realized_pnl, unrealized_pnl, total_pnl, deployed_capital, roi_percent,
            hit_rate, consistency_score, conviction_score, sizing_discipline_score,
            specialization_score, activity_score, data_quality_score, primary_category,
            category_count, average_position_value, largest_position_value,
            average_entry_price, average_current_price, first_seen_at, last_seen_at,
            model_version, first_profiled_at, last_profiled_at, last_run_id, evidence_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(wallet) DO UPDATE SET
            profile_checksum=excluded.profile_checksum, wallet_score=excluded.wallet_score,
            wallet_grade=excluded.wallet_grade, elite_status=excluded.elite_status,
            total_positions=excluded.total_positions, resolved_positions=excluded.resolved_positions,
            winning_positions=excluded.winning_positions, losing_positions=excluded.losing_positions,
            realized_pnl=excluded.realized_pnl, unrealized_pnl=excluded.unrealized_pnl,
            total_pnl=excluded.total_pnl, deployed_capital=excluded.deployed_capital,
            roi_percent=excluded.roi_percent, hit_rate=excluded.hit_rate,
            consistency_score=excluded.consistency_score, conviction_score=excluded.conviction_score,
            sizing_discipline_score=excluded.sizing_discipline_score,
            specialization_score=excluded.specialization_score, activity_score=excluded.activity_score,
            data_quality_score=excluded.data_quality_score, primary_category=excluded.primary_category,
            category_count=excluded.category_count, average_position_value=excluded.average_position_value,
            largest_position_value=excluded.largest_position_value,
            average_entry_price=excluded.average_entry_price,
            average_current_price=excluded.average_current_price,
            first_seen_at=excluded.first_seen_at, last_seen_at=excluded.last_seen_at,
            model_version=excluded.model_version, last_profiled_at=excluded.last_profiled_at,
            last_run_id=excluded.last_run_id, evidence_json=excluded.evidence_json""",
        (
            profile["wallet"], profile["profile_checksum"], profile["wallet_score"],
            profile["wallet_grade"], profile["elite_status"], profile["total_positions"],
            profile["resolved_positions"], profile["winning_positions"], profile["losing_positions"],
            profile["realized_pnl"], profile["unrealized_pnl"], profile["total_pnl"],
            profile["deployed_capital"], profile["roi_percent"], profile["hit_rate"],
            profile["consistency_score"], profile["conviction_score"],
            profile["sizing_discipline_score"], profile["specialization_score"],
            profile["activity_score"], profile["data_quality_score"],
            profile["primary_category"], profile["category_count"],
            profile["average_position_value"], profile["largest_position_value"],
            profile["average_entry_price"], profile["average_current_price"],
            profile["first_seen_at"], profile["last_seen_at"], ENGINE_VERSION,
            first_profiled, observed_at, run_id, json.dumps(profile["evidence"], sort_keys=True),
        ),
    )
    if state in {"created", "updated"}:
        connection.execute(
            """INSERT OR IGNORE INTO elite_wallet_profile_history (
                wallet, observed_at, profile_checksum, wallet_score, wallet_grade,
                elite_status, total_positions, resolved_positions, winning_positions,
                losing_positions, total_pnl, deployed_capital, roi_percent, hit_rate,
                consistency_score, conviction_score, sizing_discipline_score,
                specialization_score, activity_score, data_quality_score,
                primary_category, evidence_json, run_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                profile["wallet"], observed_at, profile["profile_checksum"],
                profile["wallet_score"], profile["wallet_grade"], profile["elite_status"],
                profile["total_positions"], profile["resolved_positions"],
                profile["winning_positions"], profile["losing_positions"],
                profile["total_pnl"], profile["deployed_capital"], profile["roi_percent"],
                profile["hit_rate"], profile["consistency_score"], profile["conviction_score"],
                profile["sizing_discipline_score"], profile["specialization_score"],
                profile["activity_score"], profile["data_quality_score"],
                profile["primary_category"], json.dumps(profile["evidence"], sort_keys=True),
                run_id,
            ),
        )
    for item in categories:
        connection.execute(
            """INSERT INTO elite_wallet_category_profiles (
                wallet, category, profile_checksum, position_count, resolved_positions,
                winning_positions, losing_positions, total_pnl, deployed_capital,
                roi_percent, hit_rate, category_score, category_grade, first_seen_at,
                last_seen_at, last_run_id, evidence_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(wallet, category) DO UPDATE SET
                profile_checksum=excluded.profile_checksum, position_count=excluded.position_count,
                resolved_positions=excluded.resolved_positions,
                winning_positions=excluded.winning_positions,
                losing_positions=excluded.losing_positions, total_pnl=excluded.total_pnl,
                deployed_capital=excluded.deployed_capital, roi_percent=excluded.roi_percent,
                hit_rate=excluded.hit_rate, category_score=excluded.category_score,
                category_grade=excluded.category_grade, first_seen_at=excluded.first_seen_at,
                last_seen_at=excluded.last_seen_at, last_run_id=excluded.last_run_id,
                evidence_json=excluded.evidence_json""",
            (
                item["wallet"], item["category"], item["profile_checksum"],
                item["position_count"], item["resolved_positions"],
                item["winning_positions"], item["losing_positions"], item["total_pnl"],
                item["deployed_capital"], item["roi_percent"], item["hit_rate"],
                item["category_score"], item["category_grade"], item["first_seen_at"],
                item["last_seen_at"], run_id, json.dumps(item["evidence"], sort_keys=True),
            ),
        )
    return state


def publish_profile_event(connection: sqlite3.Connection, profile: dict[str, Any]) -> bool:
    key = build_deduplication_key(
        event_type="EliteWalletProfiled", aggregate_type="wallet",
        aggregate_id=profile["wallet"], state_value=profile["profile_checksum"]
    )
    event = PlatformEvent.create(
        event_type="EliteWalletProfiled", source_engine="elite_wallet_intelligence_engine",
        source_version=ENGINE_VERSION, aggregate_type="wallet",
        aggregate_id=profile["wallet"], payload=profile, deduplication_key=key
    )
    return publish_event(connection, event)


def print_board(connection: sqlite3.Connection, limit: int = 20) -> None:
    rows = connection.execute(
        """SELECT rank, wallet, wallet_score, wallet_grade, elite_status,
        resolved_positions, total_pnl, roi_percent, hit_rate, consistency_score,
        primary_category, data_quality_score
        FROM ranked_elite_wallets ORDER BY rank LIMIT ?""", (limit,)
    ).fetchall()
    print("\nELITE WALLET INTELLIGENCE BOARD")
    print("-" * 154)
    for row in rows:
        wallet = str(row["wallet"])
        short = wallet if len(wallet) <= 18 else f"{wallet[:10]}...{wallet[-6:]}"
        print(
            f"{row['rank']:>3} {row['wallet_score']:>6.2f} {row['wallet_grade']:<5} "
            f"{row['elite_status']:<10} R:{row['resolved_positions']:<4} "
            f"PnL:${row['total_pnl']:>12,.2f} ROI:{row['roi_percent']:>8.2f}% "
            f"H:{row['hit_rate']:>6.2f} C:{row['consistency_score']:>6.2f} "
            f"D:{row['data_quality_score']:>6.2f} {row['primary_category']:<10} {short}"
        )
    print("-" * 154)


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1
    run_id = f"elite-wallet:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:8]}"
    counts = {"wallets": 0, "created": 0, "updated": 0, "unchanged": 0, "events": 0}
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        ensure_schema(connection)
        connection.execute(
            "INSERT INTO elite_wallet_intelligence_runs "
            "(run_id, engine_version, started_at, status) VALUES (?, ?, ?, 'RUNNING')",
            (run_id, ENGINE_VERSION, utc_now()),
        )
        connection.commit()
        try:
            grouped = defaultdict(list)
            for row in load_positions(connection):
                grouped[str(row["wallet"])].append(row)
            counts["wallets"] = len(grouped)
            observed_at = utc_now()
            for wallet, rows in grouped.items():
                profile, categories = profile_wallet(wallet, rows)
                state = upsert_profile(connection, profile, categories, run_id, observed_at)
                counts[state] += 1
                if state in {"created", "updated"}:
                    connection.commit()
                    counts["events"] += int(publish_profile_event(connection, profile))
            connection.execute(
                """UPDATE elite_wallet_intelligence_runs SET completed_at=?,
                status='SUCCESS', wallets_read=?, profiles_created=?,
                profiles_updated=?, profiles_unchanged=?, events_published=?
                WHERE run_id=?""",
                (utc_now(), counts["wallets"], counts["created"], counts["updated"],
                 counts["unchanged"], counts["events"], run_id),
            )
            connection.commit()
            print_board(connection)
        except Exception as error:
            connection.rollback()
            connection.execute(
                "UPDATE elite_wallet_intelligence_runs SET completed_at=?, "
                "status='FAILED', error_message=? WHERE run_id=?",
                (utc_now(), str(error)[:4000], run_id),
            )
            connection.commit()
            raise
    print("\n" + "=" * 80)
    print(f"ELITE WALLET INTELLIGENCE ENGINE v{ENGINE_VERSION}")
    print("=" * 80)
    print(f"Wallets read:              {counts['wallets']:,}")
    print(f"Profiles created:          {counts['created']:,}")
    print(f"Profiles updated:          {counts['updated']:,}")
    print(f"Profiles unchanged:        {counts['unchanged']:,}")
    print(f"Events published:          {counts['events']:,}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
