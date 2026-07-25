"""Tests for the wallet profile collection engine."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.wallet_profile_collector import (
    CandidateWallet,
    PublicDataAPIClient,
    WalletCollection,
    WalletProfileCollector,
)


WALLET_ONE = (
    "0x1111111111111111111111111111111111111111"
)

WALLET_TWO = (
    "0x2222222222222222222222222222222222222222"
)

WALLET_THREE = (
    "0x3333333333333333333333333333333333333333"
)

CONDITION_ID = "0x" + ("a" * 64)


def create_discovered_wallets_table(
    database_path: Path,
) -> None:
    """Create the discovery dependency used by the collector."""

    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            CREATE TABLE discovered_wallets (
                wallet TEXT PRIMARY KEY,
                username TEXT,
                elite_score REAL NOT NULL DEFAULT 0,
                elite_grade TEXT,
                primary_category TEXT,
                active_watchlist INTEGER NOT NULL DEFAULT 0,
                manually_approved INTEGER NOT NULL DEFAULT 0,
                best_rank INTEGER
            )
            """
        )

        connection.commit()

    finally:
        connection.close()


def insert_discovered_wallet(
    database_path: Path,
    *,
    wallet: str,
    username: str,
    elite_score: float,
    elite_grade: str = "A",
    primary_category: str = "SPORTS",
    active_watchlist: int = 0,
    manually_approved: int = 0,
    best_rank: int = 10,
) -> None:
    """Insert one candidate into discovered_wallets."""

    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            INSERT INTO discovered_wallets (
                wallet,
                username,
                elite_score,
                elite_grade,
                primary_category,
                active_watchlist,
                manually_approved,
                best_rank
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                wallet,
                username,
                elite_score,
                elite_grade,
                primary_category,
                active_watchlist,
                manually_approved,
                best_rank,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def make_candidate(
    *,
    wallet: str = WALLET_ONE,
    username: str = "elite-wallet",
    elite_score: float = 88.0,
    elite_grade: str = "S",
    primary_category: str = "SPORTS",
    active_watchlist: int = 1,
    manually_approved: int = 0,
) -> CandidateWallet:
    """Create a candidate wallet for deterministic tests."""

    return CandidateWallet(
        wallet=wallet,
        username=username,
        elite_score=elite_score,
        elite_grade=elite_grade,
        primary_category=primary_category,
        active_watchlist=active_watchlist,
        manually_approved=manually_approved,
    )


def make_collection(
    candidate: CandidateWallet,
    *,
    errors: list[str] | None = None,
) -> WalletCollection:
    """Create a complete wallet collection without API access."""

    return WalletCollection(
        candidate=candidate,
        position_value=12_500.0,
        total_markets_traded=27,
        current_positions=[
            {
                "asset": "asset-current",
                "conditionId": CONDITION_ID,
                "size": 100,
                "avgPrice": 0.40,
                "initialValue": 40,
                "currentValue": 55,
                "cashPnl": 15,
                "percentPnl": 37.5,
                "totalBought": 100,
                "realizedPnl": 0,
                "percentRealizedPnl": 0,
                "curPrice": 0.55,
                "redeemable": False,
                "mergeable": False,
                "title": "Example current market",
                "slug": "example-current-market",
                "eventSlug": "example-event",
                "outcome": "Yes",
                "outcomeIndex": 0,
                "oppositeOutcome": "No",
                "oppositeAsset": "asset-opposite",
                "endDate": "2026-12-31T00:00:00Z",
                "negativeRisk": False,
            }
        ],
        closed_positions=[
            {
                "asset": "asset-closed",
                "conditionId": CONDITION_ID,
                "avgPrice": 0.30,
                "totalBought": 200,
                "realizedPnl": 42,
                "curPrice": 1.0,
                "timestamp": 1_750_000_000,
                "title": "Example closed market",
                "slug": "example-closed-market",
                "eventSlug": "example-event",
                "outcome": "Yes",
                "outcomeIndex": 0,
                "oppositeOutcome": "No",
                "oppositeAsset": "asset-opposite",
                "endDate": "2026-01-01T00:00:00Z",
            }
        ],
        trades=[
            {
                "side": "buy",
                "asset": "asset-trade",
                "conditionId": CONDITION_ID,
                "size": 75,
                "price": 0.44,
                "timestamp": 1_750_000_100,
                "title": "Example trade",
                "slug": "example-trade",
                "eventSlug": "example-event",
                "outcome": "Yes",
                "outcomeIndex": 0,
                "transactionHash": "0xtrade",
            }
        ],
        activity=[
            {
                "timestamp": 1_750_000_200,
                "conditionId": CONDITION_ID,
                "type": "trade",
                "size": 75,
                "usdcSize": 33,
                "transactionHash": "0xactivity",
                "price": 0.44,
                "asset": "asset-activity",
                "side": "buy",
                "outcomeIndex": 0,
                "title": "Example activity",
                "slug": "example-activity",
                "eventSlug": "example-event",
                "outcome": "Yes",
            }
        ],
        API_queries=6,
        errors=list(errors or []),
    )


class FakePaginatedClient(PublicDataAPIClient):
    """API client that serves deterministic pages."""

    def __init__(
        self,
        pages: dict[int, list[dict[str, Any]]],
    ) -> None:
        super().__init__(
            pause_seconds=0,
        )

        self.pages = pages
        self.calls: list[dict[str, Any]] = []

    def get_json(
        self,
        path: str,
        params: dict[str, Any],
    ) -> Any:
        self.calls.append(
            {
                "path": path,
                "params": dict(params),
            }
        )

        offset = int(
            params.get(
                "offset",
                0,
            )
        )

        return list(
            self.pages.get(
                offset,
                [],
            )
        )


class WalletProfileCollectorTests(
    unittest.TestCase
):
    """Production-hardening tests for profile collection."""

    def create_collector(
        self,
        database_path: Path,
        *,
        candidate_limit: int = 10,
        min_elite_score: float = 50.0,
        watchlist_only: bool = False,
    ) -> WalletProfileCollector:
        """Create an isolated collector."""

        return WalletProfileCollector(
            database_path=database_path,
            candidate_limit=candidate_limit,
            min_elite_score=min_elite_score,
            include_watchlist_only=watchlist_only,
            max_closed_positions=100,
            max_trades=100,
            max_activity=100,
        )

    def test_missing_discovery_dependency_is_rejected(
        self,
    ) -> None:
        """The collector must not run before wallet discovery."""

        with tempfile.TemporaryDirectory() as directory:
            database_path = (
                Path(directory)
                / "polymarket.db"
            )

            collector = self.create_collector(
                database_path
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "discovered_wallets does not exist",
            ):
                collector.validate_dependencies()

    def test_candidate_selection_respects_score_and_order(
        self,
    ) -> None:
        """Only eligible wallets should be selected in priority order."""

        with tempfile.TemporaryDirectory() as directory:
            database_path = (
                Path(directory)
                / "polymarket.db"
            )

            create_discovered_wallets_table(
                database_path
            )

            insert_discovered_wallet(
                database_path,
                wallet=WALLET_ONE,
                username="ordinary",
                elite_score=75,
                active_watchlist=0,
                manually_approved=0,
                best_rank=2,
            )

            insert_discovered_wallet(
                database_path,
                wallet=WALLET_TWO,
                username="watchlisted",
                elite_score=80,
                active_watchlist=1,
                manually_approved=0,
                best_rank=8,
            )

            insert_discovered_wallet(
                database_path,
                wallet=WALLET_THREE,
                username="approved",
                elite_score=70,
                active_watchlist=0,
                manually_approved=1,
                best_rank=20,
            )

            collector = self.create_collector(
                database_path,
                candidate_limit=2,
                min_elite_score=72,
            )

            candidates = collector.select_candidates()

            self.assertEqual(
                len(candidates),
                2,
            )

            self.assertEqual(
                candidates[0].wallet,
                WALLET_TWO,
            )

            self.assertEqual(
                candidates[1].wallet,
                WALLET_ONE,
            )

    def test_watchlist_only_excludes_unapproved_wallets(
        self,
    ) -> None:
        """Watchlist mode should enforce approval flags."""

        with tempfile.TemporaryDirectory() as directory:
            database_path = (
                Path(directory)
                / "polymarket.db"
            )

            create_discovered_wallets_table(
                database_path
            )

            insert_discovered_wallet(
                database_path,
                wallet=WALLET_ONE,
                username="not-watched",
                elite_score=95,
            )

            insert_discovered_wallet(
                database_path,
                wallet=WALLET_TWO,
                username="watched",
                elite_score=80,
                active_watchlist=1,
            )

            collector = self.create_collector(
                database_path,
                watchlist_only=True,
            )

            candidates = collector.select_candidates()

            self.assertEqual(
                [
                    candidate.wallet
                    for candidate in candidates
                ],
                [WALLET_TWO],
            )

    def test_paginated_fetch_stops_after_short_page(
        self,
    ) -> None:
        """Pagination should stop when the API returns a short page."""

        client = FakePaginatedClient(
            {
                0: [
                    {"id": 1},
                    {"id": 2},
                ],
                2: [
                    {"id": 3},
                ],
            }
        )

        rows, query_count = (
            client.fetch_paginated_list(
                "/trades",
                params={
                    "user": WALLET_ONE,
                },
                page_size=2,
                max_rows=10,
            )
        )

        self.assertEqual(
            rows,
            [
                {"id": 1},
                {"id": 2},
                {"id": 3},
            ],
        )

        self.assertEqual(
            query_count,
            2,
        )

        self.assertEqual(
            [
                call["params"]["offset"]
                for call in client.calls
            ],
            [0, 2],
        )

    def test_apply_run_persists_all_snapshot_types(
        self,
    ) -> None:
        """Apply mode should persist profiles and raw snapshots."""

        with tempfile.TemporaryDirectory() as directory:
            database_path = (
                Path(directory)
                / "polymarket.db"
            )

            create_discovered_wallets_table(
                database_path
            )

            insert_discovered_wallet(
                database_path,
                wallet=WALLET_ONE,
                username="elite-wallet",
                elite_score=88,
                elite_grade="S",
                active_watchlist=1,
            )

            collector = self.create_collector(
                database_path
            )

            candidate = make_candidate()

            collector.collect_wallet = (
                lambda selected: make_collection(
                    selected
                )
            )

            report = collector.run(
                apply=True
            )

            self.assertEqual(
                report["status"],
                "SUCCESS",
            )

            self.assertEqual(
                report["wallets_selected"],
                1,
            )

            self.assertEqual(
                report["wallets_completed"],
                1,
            )

            self.assertEqual(
                report["wallets_failed"],
                0,
            )

            self.assertEqual(
                report["API_queries"],
                6,
            )

            self.assertEqual(
                report["profile_rows_upserted"],
                1,
            )

            connection = sqlite3.connect(
                database_path
            )

            try:
                table_counts = {}

                for table_name in (
                    "wallet_profiles_raw",
                    "wallet_current_position_snapshots",
                    "wallet_closed_position_snapshots",
                    "wallet_trade_snapshots",
                    "wallet_activity_snapshots",
                ):
                    table_counts[table_name] = (
                        connection.execute(
                            f"""
                            SELECT COUNT(*)
                            FROM {table_name}
                            """
                        ).fetchone()[0]
                    )

                profile = connection.execute(
                    """
                    SELECT
                        position_value,
                        total_markets_traded,
                        latest_collection_status,
                        profile_scan_count
                    FROM wallet_profiles_raw
                    WHERE wallet = ?
                    """,
                    (candidate.wallet,),
                ).fetchone()

                run = connection.execute(
                    """
                    SELECT
                        mode,
                        status,
                        wallets_completed,
                        wallets_failed
                    FROM wallet_profile_collection_runs
                    WHERE run_id = ?
                    """,
                    (report["run_id"],),
                ).fetchone()

            finally:
                connection.close()

            self.assertEqual(
                table_counts,
                {
                    "wallet_profiles_raw": 1,
                    "wallet_current_position_snapshots": 1,
                    "wallet_closed_position_snapshots": 1,
                    "wallet_trade_snapshots": 1,
                    "wallet_activity_snapshots": 1,
                },
            )

            self.assertEqual(
                profile,
                (
                    12_500.0,
                    27,
                    "SUCCESS",
                    1,
                ),
            )

            self.assertEqual(
                run,
                (
                    "APPLY",
                    "SUCCESS",
                    1,
                    0,
                ),
            )

    def test_dry_run_collects_without_persisting_profiles(
        self,
    ) -> None:
        """Dry-run mode should collect but not persist wallet data."""

        with tempfile.TemporaryDirectory() as directory:
            database_path = (
                Path(directory)
                / "polymarket.db"
            )

            create_discovered_wallets_table(
                database_path
            )

            insert_discovered_wallet(
                database_path,
                wallet=WALLET_ONE,
                username="elite-wallet",
                elite_score=88,
                elite_grade="S",
            )

            collector = self.create_collector(
                database_path
            )

            collector.collect_wallet = (
                lambda selected: make_collection(
                    selected
                )
            )

            report = collector.run(
                apply=False
            )

            self.assertEqual(
                report["status"],
                "SUCCESS",
            )

            self.assertEqual(
                report["mode"],
                "DRY RUN",
            )

            self.assertEqual(
                report["wallets_completed"],
                1,
            )

            self.assertEqual(
                report["profile_rows_upserted"],
                0,
            )

            connection = sqlite3.connect(
                database_path
            )

            try:
                profile_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM wallet_profiles_raw
                    """
                ).fetchone()[0]

                current_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM wallet_current_position_snapshots
                    """
                ).fetchone()[0]

                run = connection.execute(
                    """
                    SELECT mode, status
                    FROM wallet_profile_collection_runs
                    WHERE run_id = ?
                    """,
                    (report["run_id"],),
                ).fetchone()

            finally:
                connection.close()

            self.assertEqual(
                profile_count,
                0,
            )

            self.assertEqual(
                current_count,
                0,
            )

            self.assertEqual(
                run,
                (
                    "DRY RUN",
                    "SUCCESS",
                ),
            )

    def test_partial_collection_is_recorded(
        self,
    ) -> None:
        """A wallet with API errors should be recorded as partial."""

        with tempfile.TemporaryDirectory() as directory:
            database_path = (
                Path(directory)
                / "polymarket.db"
            )

            create_discovered_wallets_table(
                database_path
            )

            insert_discovered_wallet(
                database_path,
                wallet=WALLET_ONE,
                username="partial-wallet",
                elite_score=88,
            )

            collector = self.create_collector(
                database_path
            )

            collector.collect_wallet = (
                lambda selected: make_collection(
                    selected,
                    errors=[
                        "activity: simulated failure",
                    ],
                )
            )

            report = collector.run(
                apply=True
            )

            self.assertEqual(
                report["status"],
                "FAILED",
            )

            self.assertEqual(
                report["wallets_completed"],
                0,
            )

            self.assertEqual(
                report["wallets_failed"],
                1,
            )

            connection = sqlite3.connect(
                database_path
            )

            try:
                profile = connection.execute(
                    """
                    SELECT
                        latest_collection_status,
                        latest_error_message
                    FROM wallet_profiles_raw
                    WHERE wallet = ?
                    """,
                    (WALLET_ONE,),
                ).fetchone()

            finally:
                connection.close()

            self.assertEqual(
                profile[0],
                "PARTIAL",
            )

            self.assertIn(
                "simulated failure",
                profile[1],
            )


if __name__ == "__main__":
    unittest.main()