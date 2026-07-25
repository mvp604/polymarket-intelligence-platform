from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
TABLES = (
    "elite_wallet_intelligence_runs", "elite_wallet_profiles",
    "elite_wallet_profile_history", "elite_wallet_category_profiles",
)
VIEWS = ("ranked_elite_wallets", "ranked_elite_wallet_categories")


def exists(connection: sqlite3.Connection, kind: str, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type=? AND name=?", (kind, name)
    ).fetchone() is not None


def main() -> int:
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}", file=sys.stderr)
        return 1
    healthy = True
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        print("=" * 82)
        print("ELITE WALLET INTELLIGENCE HEALTH")
        print("=" * 82)
        for table in TABLES:
            ok = exists(connection, "table", table)
            healthy &= ok
            print(f"{table:<48} {'OK' if ok else 'MISSING'}")
        for view in VIEWS:
            ok = exists(connection, "view", view)
            healthy &= ok
            print(f"{view:<48} {'OK' if ok else 'MISSING'}")
        if exists(connection, "table", "elite_wallet_profiles"):
            metrics = connection.execute(
                """SELECT COUNT(*) total,
                SUM(CASE WHEN elite_status='ELITE' THEN 1 ELSE 0 END) elite,
                SUM(CASE WHEN elite_status='QUALIFIED' THEN 1 ELSE 0 END) qualified,
                SUM(CASE WHEN elite_status='WATCHLIST' THEN 1 ELSE 0 END) watchlist,
                AVG(data_quality_score) quality
                FROM elite_wallet_profiles"""
            ).fetchone()
            duplicates = connection.execute(
                """SELECT COUNT(*) FROM (
                SELECT wallet, profile_checksum, COUNT(*) n
                FROM elite_wallet_profile_history
                GROUP BY wallet, profile_checksum HAVING n > 1)"""
            ).fetchone()[0]
            print(f"{'Wallet profiles':<48} {metrics['total'] or 0:,}")
            print(f"{'Elite wallets':<48} {metrics['elite'] or 0:,}")
            print(f"{'Qualified wallets':<48} {metrics['qualified'] or 0:,}")
            print(f"{'Watchlist wallets':<48} {metrics['watchlist'] or 0:,}")
            print(f"{'Average data quality':<48} {metrics['quality'] or 0:.2f}")
            print(f"{'Duplicate profile states':<48} {duplicates:,}")
            healthy &= duplicates == 0
        latest = None
        if exists(connection, "table", "elite_wallet_intelligence_runs"):
            latest = connection.execute(
                "SELECT * FROM elite_wallet_intelligence_runs "
                "ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        if latest:
            print("-" * 82)
            print(f"{'Latest run status':<48} {latest['status']}")
            print(f"{'Wallets read':<48} {latest['wallets_read']:,}")
            print(f"{'Profiles created':<48} {latest['profiles_created']:,}")
            print(f"{'Profiles updated':<48} {latest['profiles_updated']:,}")
            print(f"{'Profiles unchanged':<48} {latest['profiles_unchanged']:,}")
            print(f"{'Events published':<48} {latest['events_published']:,}")
            print(f"{'Error':<48} {latest['error_message'] or 'NONE'}")
            healthy &= latest["status"] == "SUCCESS"
    print("=" * 82)
    print(f"OVERALL STATUS: {'HEALTHY' if healthy else 'ATTENTION REQUIRED'}")
    print("=" * 82)
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
