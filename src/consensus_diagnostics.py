from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database/polymarket.db")
MIN_POSITION_VALUE = 500.0


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    query = """
        WITH latest_scans AS (
            SELECT wallet, MAX(id) AS latest_scan_id
            FROM wallet_scans
            GROUP BY wallet
        )
        SELECT
            p.market_id,
            p.title,
            p.outcome,
            COUNT(DISTINCT p.wallet) AS wallet_count,
            SUM(COALESCE(p.shares, 0)) AS combined_shares,
            SUM(COALESCE(p.current_value, 0)) AS combined_value,
            GROUP_CONCAT(DISTINCT p.wallet) AS wallets
        FROM positions AS p
        INNER JOIN latest_scans AS latest
            ON p.wallet = latest.wallet
           AND p.scan_id = latest.latest_scan_id
        WHERE
            p.market_id IS NOT NULL
            AND TRIM(p.market_id) != ''
            AND COALESCE(p.current_value, 0) >= ?
        GROUP BY
            p.market_id,
            LOWER(TRIM(COALESCE(p.outcome, '')))
        ORDER BY
            wallet_count DESC,
            combined_value DESC
        LIMIT 30
    """

    rows = connection.execute(query, (MIN_POSITION_VALUE,)).fetchall()
    connection.close()

    print()
    print("=" * 90)
    print("CONSENSUS DIAGNOSTICS — TOP LATEST POSITION GROUPS")
    print("=" * 90)
    print(f"Minimum individual position value: ${MIN_POSITION_VALUE:,.2f}")
    print(f"Groups found: {len(rows)}")

    if not rows:
        print("No qualifying latest positions were found.")
        return

    for number, row in enumerate(rows, start=1):
        print()
        print("-" * 90)
        print(f"{number}. {row['title']}")
        print(f"Outcome: {row['outcome']}")
        print(f"Market ID: {row['market_id']}")
        print(f"Matching wallets: {row['wallet_count']}")
        print(f"Combined shares: {float(row['combined_shares'] or 0):,.2f}")
        print(f"Combined value: ${float(row['combined_value'] or 0):,.2f}")
        print(f"Wallets: {row['wallets']}")

    print()
    print("=" * 90)

    matches = [row for row in rows if int(row["wallet_count"]) >= 2]

    print(f"Groups with at least two matching wallets: {len(matches)}")


if __name__ == "__main__":
    main()