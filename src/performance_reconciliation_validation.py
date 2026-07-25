from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def print_rows(title: str, rows: list[sqlite3.Row]) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)

    if not rows:
        print("No rows.")
        return

    columns = rows[0].keys()
    for index, row in enumerate(rows, start=1):
        print(f"\nRow {index}")
        for column in columns:
            print(f"  {column}: {row[column]}")


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    connection = connect()

    try:
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS reconciled_rows,
                SUM(
                    CASE
                        WHEN source_outcome_won IN (0, 1)
                        THEN 1 ELSE 0
                    END
                ) AS resolved_rows,
                SUM(
                    CASE
                        WHEN source_outcome_won IS NULL
                        THEN 1 ELSE 0
                    END
                ) AS unresolved_rows,
                COUNT(DISTINCT wallet) AS wallets,
                COUNT(DISTINCT condition_id) AS markets
            FROM wallet_performance_markets
            WHERE performance_market_key LIKE 'closed_snapshot:%'
            """
        ).fetchone()

        print("\n" + "=" * 100)
        print("PERFORMANCE RECONCILIATION VALIDATION AUDIT")
        print("=" * 100)
        print(f"Database: {DATABASE_PATH}")
        print(f"Reconciled rows: {summary['reconciled_rows']}")
        print(f"Resolved rows: {summary['resolved_rows']}")
        print(f"Unresolved rows: {summary['unresolved_rows']}")
        print(f"Wallets represented: {summary['wallets']}")
        print(f"Unique markets represented: {summary['markets']}")

        resolution_statuses = connection.execute(
            """
            SELECT
                resolution_status,
                COUNT(*) AS total
            FROM wallet_performance_markets
            WHERE performance_market_key LIKE 'closed_snapshot:%'
            GROUP BY resolution_status
            ORDER BY total DESC, resolution_status
            """
        ).fetchall()
        print_rows("RESOLUTION STATUS COUNTS", resolution_statuses)

        resolution_methods = connection.execute(
            """
            SELECT
                match_method,
                ROUND(match_confidence, 2) AS match_confidence,
                COUNT(*) AS total
            FROM wallet_performance_markets
            WHERE performance_market_key LIKE 'closed_snapshot:%'
            GROUP BY match_method, ROUND(match_confidence, 2)
            ORDER BY total DESC, match_method
            """
        ).fetchall()
        print_rows("RESOLUTION METHOD COUNTS", resolution_methods)

        unresolved = connection.execute(
            """
            SELECT
                wallet,
                condition_id,
                title,
                selected_outcome,
                resolution_status,
                match_method,
                match_confidence,
                average_entry_price,
                shares,
                cost_basis
            FROM wallet_performance_markets
            WHERE performance_market_key LIKE 'closed_snapshot:%'
              AND source_outcome_won IS NULL
            ORDER BY cost_basis DESC
            """
        ).fetchall()
        print_rows("UNRESOLVED POSITIONS", unresolved)

        wallet_totals = connection.execute(
            """
            SELECT
                wallet,
                mapped_market_count,
                resolved_positions,
                unresolved_mapped_positions,
                wins,
                losses,
                ROUND(win_rate * 100, 2) AS win_rate_percent,
                ROUND(estimated_roi * 100, 2) AS roi_percent,
                ROUND(estimated_profit, 2) AS estimated_profit,
                ROUND(total_cost_basis, 2) AS total_cost_basis,
                ROUND(performance_score, 2) AS performance_score,
                performance_grade,
                data_confidence
            FROM wallet_performance
            WHERE mapped_market_count > 0
            ORDER BY performance_score DESC
            """
        ).fetchall()
        print_rows("ACTIVE RECONCILED WALLET PERFORMANCE", wallet_totals)

        stale_wallets = connection.execute(
            """
            SELECT
                wallet,
                resolved_positions,
                mapped_market_count,
                performance_grade,
                data_confidence,
                calculated_at
            FROM wallet_performance
            WHERE mapped_market_count = 0
            ORDER BY wallet
            """
        ).fetchall()

        print("\n" + "=" * 100)
        print("STALE / NOT-YET-RECONCILED WALLET ROWS")
        print("=" * 100)
        print(f"Count: {len(stale_wallets)}")
        print(
            "These rows were retained from the earlier engine and should "
            "not be consumed by Elite Wallet rankings unless "
            "mapped_market_count > 0."
        )

        duplicates = connection.execute(
            """
            SELECT
                wallet,
                condition_id,
                selected_outcome,
                COUNT(*) AS total
            FROM wallet_performance_markets
            WHERE performance_market_key LIKE 'closed_snapshot:%'
            GROUP BY wallet, condition_id, selected_outcome
            HAVING COUNT(*) > 1
            ORDER BY total DESC
            """
        ).fetchall()
        print_rows("DUPLICATE RECONCILED KEYS", duplicates)

        extreme_roi = connection.execute(
            """
            SELECT
                wallet,
                condition_id,
                title,
                selected_outcome,
                source_outcome_won,
                ROUND(cost_basis, 2) AS cost_basis,
                ROUND(estimated_profit, 2) AS estimated_profit,
                ROUND(estimated_roi * 100, 2) AS roi_percent,
                match_method,
                match_confidence
            FROM wallet_performance_markets
            WHERE performance_market_key LIKE 'closed_snapshot:%'
              AND estimated_roi IS NOT NULL
              AND (
                    estimated_roi > 10
                 OR estimated_roi < -1.01
              )
            ORDER BY ABS(estimated_roi) DESC
            LIMIT 50
            """
        ).fetchall()
        print_rows("EXTREME ROI OUTLIERS", extreme_roi)

        consistency_check = connection.execute(
            """
            SELECT
                wp.wallet,
                wp.resolved_positions AS wallet_resolved,
                SUM(
                    CASE
                        WHEN wpm.source_outcome_won IN (0, 1)
                        THEN 1 ELSE 0
                    END
                ) AS market_resolved,
                wp.wins AS wallet_wins,
                SUM(
                    CASE
                        WHEN wpm.source_outcome_won = 1
                        THEN 1 ELSE 0
                    END
                ) AS market_wins,
                wp.losses AS wallet_losses,
                SUM(
                    CASE
                        WHEN wpm.source_outcome_lost = 1
                        THEN 1 ELSE 0
                    END
                ) AS market_losses
            FROM wallet_performance AS wp
            JOIN wallet_performance_markets AS wpm
              ON wpm.wallet = wp.wallet
             AND wpm.performance_market_key LIKE 'closed_snapshot:%'
            WHERE wp.mapped_market_count > 0
            GROUP BY wp.wallet
            HAVING
                   wp.resolved_positions != market_resolved
                OR wp.wins != market_wins
                OR wp.losses != market_losses
            """
        ).fetchall()
        print_rows("AGGREGATION CONSISTENCY FAILURES", consistency_check)

        print("\n" + "=" * 100)
        print("VALIDATION RESULT")
        print("=" * 100)

        failures = 0
        if duplicates:
            failures += 1
            print("[FAIL] Duplicate reconciled position keys found.")
        else:
            print("[PASS] No duplicate reconciled position keys.")

        if consistency_check:
            failures += 1
            print("[FAIL] Wallet aggregates do not match market rows.")
        else:
            print("[PASS] Wallet aggregates match reconciled market rows.")

        if summary["resolved_rows"] == 0:
            failures += 1
            print("[FAIL] No resolved positions were produced.")
        else:
            print("[PASS] Resolved positions were produced.")

        if extreme_roi:
            print(
                "[REVIEW] Extreme ROI rows exist. Inspect them before "
                "feeding performance into Elite Wallet rankings."
            )
        else:
            print("[PASS] No extreme ROI rows beyond audit thresholds.")

        print(
            f"\nAudit completed with {failures} structural failure(s)."
        )
        print(
            "Elite Wallet integration is allowed only after structural "
            "failures equal zero and ROI outliers are reviewed."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()