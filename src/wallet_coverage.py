from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database/polymarket.db")


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    query = """
    WITH latest_scans AS (
        SELECT
            wallet,
            MAX(id) AS latest_scan_id,
            COUNT(*) AS scan_count,
            MAX(scanned_at) AS latest_scan_time
        FROM wallet_scans
        GROUP BY wallet
    )
    SELECT
        latest.wallet,
        latest.scan_count,
        latest.latest_scan_id,
        latest.latest_scan_time,
        COUNT(p.id) AS positions_in_latest_scan,
        SUM(
            CASE
                WHEN COALESCE(p.current_value, 0) >= 500
                THEN 1
                ELSE 0
            END
        ) AS qualifying_positions
    FROM latest_scans AS latest
    LEFT JOIN positions AS p
        ON p.scan_id = latest.latest_scan_id
       AND p.wallet = latest.wallet
    GROUP BY
        latest.wallet,
        latest.scan_count,
        latest.latest_scan_id,
        latest.latest_scan_time
    ORDER BY latest.latest_scan_id DESC
"""

    rows = connection.execute(query).fetchall()
    connection.close()

    print()
    print("=" * 90)
    print("WALLET DATABASE COVERAGE")
    print("=" * 90)
    print(f"Distinct wallets stored: {len(rows)}")

    for number, row in enumerate(rows, start=1):
        print()
        print("-" * 90)
        print(f"{number}. Wallet: {row['wallet']}")
        print(f"Stored scans: {row['scan_count']}")
        print(f"Latest scan ID: {row['latest_scan_id']}")
        print(f"Latest scan time: {row['latest_scan_time']}")
        print(f"Positions in latest scan: {row['positions_in_latest_scan']}")
        print(f"Positions worth $500+: {row['qualifying_positions']}")

    print()
    print("=" * 90)


if __name__ == "__main__":
    main()