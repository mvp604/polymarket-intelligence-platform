from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_PATH = PROJECT_ROOT / "src" / "opportunity_intelligence_engine.py"

HISTORY_REQUIRED = {
    "id", "run_id", "market_id", "opportunity_score", "confidence_score",
    "recommendation", "signal_grade", "risk_level", "calculated_at",
}


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    ]


def validate_scores_key(connection: sqlite3.Connection) -> None:
    info = connection.execute('PRAGMA table_info("opportunity_scores")').fetchall()
    market_row = next((row for row in info if str(row[1]) == "market_id"), None)
    if market_row is None or int(row[5] if (row := market_row) else 0) == 0:
        raise RuntimeError("opportunity_scores.market_id is not a PRIMARY KEY.")
    print("SUCCESS: opportunity_scores.market_id primary key validated")


def repair_history_table(connection: sqlite3.Connection) -> None:
    create_sql = """
    CREATE TABLE opportunity_score_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        market_id TEXT NOT NULL,
        opportunity_score REAL NOT NULL,
        confidence_score REAL NOT NULL,
        recommendation TEXT NOT NULL,
        signal_grade TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        calculated_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES opportunity_engine_runs(run_id)
    )
    """

    if not table_exists(connection, "opportunity_score_history"):
        connection.execute(create_sql)
        print("SUCCESS: Created opportunity_score_history")
        return

    existing = set(columns(connection, "opportunity_score_history"))
    missing = HISTORY_REQUIRED - existing
    if not missing:
        print("SUCCESS: opportunity_score_history schema is already current")
        return

    suffix = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    legacy = f"opportunity_score_history_legacy_{suffix}"
    connection.execute(
        f'ALTER TABLE opportunity_score_history RENAME TO "{legacy}"'
    )
    connection.execute(create_sql)
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunity_history_market
        ON opportunity_score_history(market_id, calculated_at DESC)
        """
    )
    print(f"SUCCESS: Rebuilt history table; legacy preserved as {legacy}")


def patch_discovery_function() -> None:
    text = ENGINE_PATH.read_text(encoding="utf-8-sig")
    start = text.find("def discover_feature_source(")
    end = text.find("\ndef normalize_score(", start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not locate discover_feature_source()")

    replacement = """def discover_feature_source(
    connection: sqlite3.Connection,
) -> tuple[str, list[str], int]:
    excluded = {
        "opportunity_engine_runs",
        "opportunity_scores",
        "opportunity_score_history",
        "intelligence_wallets",
        "intelligence_markets",
        "intelligence_signals",
        "master_opportunity_history",
        "master_opportunities",
        "ranked_market_opportunities",
        "market_opportunity_history",
    }

    id_candidates = (
        "market_id", "condition_id", "token_id", "id", "slug",
    )
    feature_groups = (
        ("opportunity_score", "opportunity"),
        ("health_score", "market_health", "health"),
        ("risk_score", "risk"),
        ("wallet_score", "wallet_feature_score"),
        ("consensus_score", "conviction_score", "consensus_strength"),
        ("liquidity", "liquidity_num"),
        ("volume", "volume_num"),
        ("spread", "current_spread"),
        ("momentum_score", "price_momentum", "momentum"),
        ("yes_price", "current_price", "price", "last_price"),
        ("question", "title", "market_question"),
    )

    candidates: list[tuple[int, int, int, str, list[str]]] = []

    for table in table_names(connection):
        if table in excluded or table.startswith("opportunity_"):
            continue

        available = columns(connection, table)
        if find_column(available, id_candidates) is None:
            continue

        feature_hits = sum(
            find_column(available, group) is not None
            for group in feature_groups
        )
        if feature_hits < 2:
            continue

        count = row_count(connection, table)
        lowered = table.lower()
        name_bonus = 0
        if "feature" in lowered:
            name_bonus += 100
        if "market" in lowered:
            name_bonus += 30
        if "current" in lowered or "profile" in lowered:
            name_bonus += 20
        if "history" in lowered:
            name_bonus -= 50
        if "opportunit" in lowered:
            name_bonus -= 40

        size_bonus = min(count // 1000, 100)
        candidates.append(
            (feature_hits, name_bonus + size_bonus, count, table, available)
        )

    if not candidates:
        raise RuntimeError("No compatible market feature source was found.")

    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    best_hits = candidates[0][0]
    strongest = [
        item for item in candidates
        if item[0] >= max(2, best_hits - 1)
    ]
    strongest.sort(key=lambda item: (item[2], item[1]), reverse=True)
    feature_hits, _, count, table, available = strongest[0]

    print()
    print("FEATURE SOURCE DISCOVERY")
    print("-" * 124)
    for hits, score, rows, name, _ in sorted(
        candidates,
        key=lambda item: (item[2], item[0], item[1]),
        reverse=True,
    )[:15]:
        marker = "SELECTED" if name == table else "candidate"
        print(
            f"{marker:<9} rows={rows:>9,} "
            f"feature_hits={hits:>2} score={score:>4} | {name}"
        )
    print("-" * 124)
    return table, available, count

"""

    ENGINE_PATH.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    print("SUCCESS: Installed broad feature-source discovery")


def main() -> int:
    print("=" * 108)
    print("OPPORTUNITY INTELLIGENCE ENGINE V3 REPAIR")
    print("=" * 108)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("PRAGMA busy_timeout = 30000")
        validate_scores_key(connection)
        repair_history_table(connection)
        connection.commit()

    patch_discovery_function()
    print("=" * 108)
    print("V3 REPAIR COMPLETE")
    print("=" * 108)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
