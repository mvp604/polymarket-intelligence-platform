from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"

TABLES_TO_INSPECT = [
    "opportunity_scores",
    "institutional_consensus",
    "position_evolution",
    "closing_line_metrics",
    "market_price_metrics",
    "market_metadata",
    "wallet_profiles",
    "portfolio_overlap",
]


def configure_utf8_output() -> None:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except (AttributeError, OSError):
        pass

    try:
        sys.stderr.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except (AttributeError, OSError):
        pass


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def table_row_count(
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    row = connection.execute(
        f'SELECT COUNT(*) AS total FROM "{table_name}"'
    ).fetchone()

    return int(row["total"] if row else 0)


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[sqlite3.Row]:
    return connection.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()


def print_table_schema(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    print()
    print("=" * 120)
    print(table_name.upper())
    print("=" * 120)

    if not table_exists(connection, table_name):
        print("TABLE DOES NOT EXIST")
        return

    columns = table_columns(
        connection,
        table_name,
    )

    print("COLUMNS")
    print("-" * 120)

    for column in columns:
        name = str(column["name"])
        data_type = str(column["type"] or "")
        not_null = int(column["notnull"] or 0)
        default_value = column["dflt_value"]
        primary_key = int(column["pk"] or 0)

        print(
            f"{name:<42}"
            f"{data_type:<18}"
            f"NOT NULL={not_null:<3}"
            f"PK={primary_key:<3}"
            f"DEFAULT={default_value}"
        )

    print()
    print(
        f"ROWS: {table_row_count(connection, table_name)}"
    )


def print_join_key_diagnostic(
    connection: sqlite3.Connection,
) -> None:
    print()
    print("=" * 120)
    print("JOIN KEY DIAGNOSTIC")
    print("=" * 120)

    tables = [
        "opportunity_scores",
        "institutional_consensus",
        "position_evolution",
        "closing_line_metrics",
        "market_price_metrics",
        "market_metadata",
    ]

    for table_name in tables:
        if not table_exists(
            connection,
            table_name,
        ):
            print(
                f"{table_name:<36}"
                f"TABLE MISSING"
            )
            continue

        column_names = {
            str(row["name"])
            for row in table_columns(
                connection,
                table_name,
            )
        }

        detected_keys = [
            key
            for key in (
                "opportunity_key",
                "consensus_key",
                "evolution_key",
                "market_id",
                "outcome",
                "title",
            )
            if key in column_names
        ]

        print(
            f"{table_name:<36}"
            f"{', '.join(detected_keys) or 'NO EXPECTED KEYS'}"
        )


def print_duplicate_key_diagnostic(
    connection: sqlite3.Connection,
) -> None:
    print()
    print("=" * 120)
    print("DUPLICATE KEY DIAGNOSTIC")
    print("=" * 120)

    checks = [
        (
            "opportunity_scores",
            "opportunity_key",
        ),
        (
            "institutional_consensus",
            "consensus_key",
        ),
        (
            "position_evolution",
            "evolution_key",
        ),
        (
            "closing_line_metrics",
            "opportunity_key",
        ),
        (
            "market_price_metrics",
            "market_id",
        ),
        (
            "market_metadata",
            "market_id",
        ),
    ]

    for table_name, key_column in checks:
        if not table_exists(
            connection,
            table_name,
        ):
            print(
                f"{table_name:<36}"
                f"TABLE MISSING"
            )
            continue

        column_names = {
            str(row["name"])
            for row in table_columns(
                connection,
                table_name,
            )
        }

        if key_column not in column_names:
            print(
                f"{table_name:<36}"
                f"MISSING KEY COLUMN: {key_column}"
            )
            continue

        row = connection.execute(
            f"""
            SELECT COUNT(*) AS duplicate_groups
            FROM (
                SELECT "{key_column}"
                FROM "{table_name}"
                WHERE "{key_column}" IS NOT NULL
                  AND TRIM(CAST("{key_column}" AS TEXT)) != ''
                GROUP BY "{key_column}"
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()

        duplicate_groups = int(
            row["duplicate_groups"]
            if row
            else 0
        )

        print(
            f"{table_name:<36}"
            f"{key_column:<24}"
            f"duplicate groups: {duplicate_groups}"
        )


def print_market_join_coverage(
    connection: sqlite3.Connection,
) -> None:
    print()
    print("=" * 120)
    print("MASTER JOIN COVERAGE")
    print("=" * 120)

    required_tables = [
        "opportunity_scores",
        "institutional_consensus",
        "position_evolution",
        "closing_line_metrics",
        "market_price_metrics",
        "market_metadata",
    ]

    missing = [
        table_name
        for table_name in required_tables
        if not table_exists(
            connection,
            table_name,
        )
    ]

    if missing:
        print(
            "Cannot calculate join coverage because "
            f"these tables are missing: {', '.join(missing)}"
        )
        return

    opportunity_columns = {
        str(row["name"])
        for row in table_columns(
            connection,
            "opportunity_scores",
        )
    }

    if "opportunity_key" not in opportunity_columns:
        print(
            "Cannot calculate join coverage because "
            "opportunity_scores.opportunity_key is missing."
        )
        return

    query = """
        SELECT
            COUNT(*) AS opportunity_rows,

            SUM(
                CASE
                    WHEN institutional_consensus.consensus_key
                         IS NOT NULL
                    THEN 1
                    ELSE 0
                END
            ) AS institutional_matches,

            SUM(
                CASE
                    WHEN position_evolution.evolution_key
                         IS NOT NULL
                    THEN 1
                    ELSE 0
                END
            ) AS evolution_matches,

            SUM(
                CASE
                    WHEN closing_line_metrics.opportunity_key
                         IS NOT NULL
                    THEN 1
                    ELSE 0
                END
            ) AS closing_line_matches,

            SUM(
                CASE
                    WHEN market_price_metrics.market_id
                         IS NOT NULL
                    THEN 1
                    ELSE 0
                END
            ) AS price_metric_matches,

            SUM(
                CASE
                    WHEN market_metadata.market_id
                         IS NOT NULL
                    THEN 1
                    ELSE 0
                END
            ) AS metadata_matches

        FROM opportunity_scores

        LEFT JOIN institutional_consensus
            ON institutional_consensus.consensus_key =
               opportunity_scores.opportunity_key

        LEFT JOIN position_evolution
            ON position_evolution.evolution_key =
               opportunity_scores.opportunity_key

        LEFT JOIN closing_line_metrics
            ON closing_line_metrics.opportunity_key =
               opportunity_scores.opportunity_key

        LEFT JOIN market_price_metrics
            ON LOWER(market_price_metrics.market_id) =
               LOWER(opportunity_scores.market_id)

        LEFT JOIN market_metadata
            ON LOWER(market_metadata.market_id) =
               LOWER(opportunity_scores.market_id)
    """

    row = connection.execute(
        query
    ).fetchone()

    if row is None:
        print("No coverage results were returned.")
        return

    opportunity_rows = int(
        row["opportunity_rows"] or 0
    )

    print(
        f"Opportunity rows:               "
        f"{opportunity_rows}"
    )

    coverage_fields = [
        (
            "Institutional consensus",
            int(row["institutional_matches"] or 0),
        ),
        (
            "Position evolution",
            int(row["evolution_matches"] or 0),
        ),
        (
            "Closing line metrics",
            int(row["closing_line_matches"] or 0),
        ),
        (
            "Price metrics",
            int(row["price_metric_matches"] or 0),
        ),
        (
            "Market metadata",
            int(row["metadata_matches"] or 0),
        ),
    ]

    for label, matched in coverage_fields:
        percentage = (
            matched / opportunity_rows * 100.0
            if opportunity_rows > 0
            else 0.0
        )

        print(
            f"{label:<32}"
            f"{matched:>8} matches "
            f"({percentage:6.1f}%)"
        )


def print_sample_joined_rows(
    connection: sqlite3.Connection,
) -> None:
    print()
    print("=" * 120)
    print("SAMPLE JOINED MASTER INPUTS")
    print("=" * 120)

    required_tables = [
        "opportunity_scores",
        "institutional_consensus",
        "position_evolution",
        "closing_line_metrics",
        "market_price_metrics",
        "market_metadata",
    ]

    if any(
        not table_exists(
            connection,
            table_name,
        )
        for table_name in required_tables
    ):
        print(
            "Sample join skipped because one or more "
            "required tables are missing."
        )
        return

    rows = connection.execute(
        """
        SELECT
            opportunity_scores.opportunity_key,
            opportunity_scores.title,
            opportunity_scores.outcome,
            opportunity_scores.opportunity_score,

            institutional_consensus.consensus_strength,
            institutional_consensus.confidence_grade
                AS institutional_grade,
            institutional_consensus.signal_status
                AS institutional_status,

            position_evolution.evolution_score,
            position_evolution.evolution_grade,
            position_evolution.evolution_status,

            closing_line_metrics.clv_score,
            closing_line_metrics.edge_remaining_score,
            closing_line_metrics.chase_risk_score,
            closing_line_metrics.recommendation
                AS closing_recommendation,

            market_price_metrics.steam_score,
            market_price_metrics.reversal_score,
            market_price_metrics.move_status,

            market_metadata.lifecycle_status,
            market_metadata.seconds_to_start

        FROM opportunity_scores

        LEFT JOIN institutional_consensus
            ON institutional_consensus.consensus_key =
               opportunity_scores.opportunity_key

        LEFT JOIN position_evolution
            ON position_evolution.evolution_key =
               opportunity_scores.opportunity_key

        LEFT JOIN closing_line_metrics
            ON closing_line_metrics.opportunity_key =
               opportunity_scores.opportunity_key

        LEFT JOIN market_price_metrics
            ON LOWER(market_price_metrics.market_id) =
               LOWER(opportunity_scores.market_id)

        LEFT JOIN market_metadata
            ON LOWER(market_metadata.market_id) =
               LOWER(opportunity_scores.market_id)

        ORDER BY
            opportunity_scores.opportunity_score DESC,
            institutional_consensus.consensus_strength DESC,
            position_evolution.evolution_score DESC

        LIMIT 20
        """
    ).fetchall()

    if not rows:
        print("No joined rows were returned.")
        return

    for index, row in enumerate(
        rows,
        start=1,
    ):
        print()
        print("-" * 120)
        print(
            f"{index}. {row['title']} — {row['outcome']}"
        )
        print("-" * 120)

        print(
            f"Opportunity score:          "
            f"{row['opportunity_score']}"
        )

        print(
            f"Institutional strength:     "
            f"{row['consensus_strength']}"
        )

        print(
            f"Institutional grade/status: "
            f"{row['institutional_grade']} / "
            f"{row['institutional_status']}"
        )

        print(
            f"Evolution score/status:     "
            f"{row['evolution_score']} / "
            f"{row['evolution_status']}"
        )

        print(
            f"CLV / edge / chase:         "
            f"{row['clv_score']} / "
            f"{row['edge_remaining_score']} / "
            f"{row['chase_risk_score']}"
        )

        print(
            f"Steam / reversal:           "
            f"{row['steam_score']} / "
            f"{row['reversal_score']}"
        )

        print(
            f"Lifecycle / T-minus:        "
            f"{row['lifecycle_status']} / "
            f"{row['seconds_to_start']}"
        )


def main() -> None:
    configure_utf8_output()

    print()
    print("=" * 120)
    print("MASTER OPPORTUNITY INPUT DIAGNOSTIC")
    print("=" * 120)
    print(f"Database: {DATABASE_PATH}")

    connection = connect_database()

    try:
        for table_name in TABLES_TO_INSPECT:
            print_table_schema(
                connection,
                table_name,
            )

        print_join_key_diagnostic(
            connection
        )

        print_duplicate_key_diagnostic(
            connection
        )

        print_market_join_coverage(
            connection
        )

        print_sample_joined_rows(
            connection
        )

    finally:
        connection.close()

    print()
    print("=" * 120)
    print("MASTER INPUT DIAGNOSTIC COMPLETE")
    print("=" * 120)


if __name__ == "__main__":
    main()