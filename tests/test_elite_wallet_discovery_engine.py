"""Tests for the elite wallet discovery engine."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.elite_wallet_discovery_engine import (
    EliteWalletDiscoveryEngine,
    LeaderboardEntry,
)


def make_entry(
    *,
    wallet: str,
    rank: int,
    pnl: float,
    volume: float,
    category: str = "SPORTS",
    time_period: str = "MONTH",
    username: str = "test-wallet",
    verified_badge: int = 0,
) -> LeaderboardEntry:
    """Create a valid leaderboard entry for tests."""

    return LeaderboardEntry(
        wallet=wallet,
        username=username,
        rank=rank,
        volume=volume,
        pnl=pnl,
        category=category,
        time_period=time_period,
        order_by="PNL",
        verified_badge=verified_badge,
        x_username="",
        profile_image="",
    )


class FakeLeaderboardClient:
    """Deterministic leaderboard client with no network access."""

    def __init__(
        self,
        responses: dict[
            tuple[str, str],
            list[LeaderboardEntry],
        ],
    ) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, str, int, int]] = []

    def fetch_leaderboard(
        self,
        *,
        category: str,
        time_period: str,
        order_by: str,
        limit: int,
        offset: int = 0,
    ) -> list[LeaderboardEntry]:
        self.calls.append(
            (
                category,
                time_period,
                order_by,
                limit,
                offset,
            )
        )

        return list(
            self.responses.get(
                (category, time_period),
                [],
            )
        )


class EliteWalletDiscoveryEngineTests(
    unittest.TestCase
):
    WALLET_ONE = (
        "0x1111111111111111111111111111111111111111"
    )

    WALLET_TWO = (
        "0x2222222222222222222222222222222222222222"
    )

    def create_engine(
        self,
        database_path: Path,
        *,
        categories: tuple[str, ...] = ("SPORTS",),
        periods: tuple[str, ...] = ("MONTH",),
    ) -> EliteWalletDiscoveryEngine:
        """Create an isolated discovery engine."""

        return EliteWalletDiscoveryEngine(
            database_path=database_path,
            categories=categories,
            periods=periods,
            leaderboard_limit=50,
        )

    def test_grade_boundaries(self) -> None:
        """Scores should map to documented wallet grades."""

        engine = self.create_engine(
            Path("unused.db")
        )

        cases = (
            (95.0, "S+"),
            (90.0, "S+"),
            (89.9, "S"),
            (82.0, "S"),
            (74.0, "A+"),
            (66.0, "A"),
            (58.0, "B+"),
            (50.0, "B"),
            (40.0, "C"),
            (39.9, "WATCH"),
        )

        for score, expected_grade in cases:
            with self.subTest(score=score):
                self.assertEqual(
                    engine.grade(score),
                    expected_grade,
                )

    def test_aggregate_combines_wallet_appearances(
        self,
    ) -> None:
        """Repeated appearances should become one wallet profile."""

        with tempfile.TemporaryDirectory() as directory:
            database_path = (
                Path(directory)
                / "polymarket.db"
            )

            engine = self.create_engine(
                database_path,
                categories=("SPORTS", "POLITICS"),
                periods=("WEEK", "MONTH"),
            )

            entries = [
                make_entry(
                    wallet=self.WALLET_ONE,
                    rank=1,
                    pnl=10_000,
                    volume=50_000,
                    category="SPORTS",
                    time_period="WEEK",
                    verified_badge=1,
                ),
                make_entry(
                    wallet=self.WALLET_ONE,
                    rank=3,
                    pnl=7_500,
                    volume=40_000,
                    category="SPORTS",
                    time_period="MONTH",
                    verified_badge=1,
                ),
                make_entry(
                    wallet=self.WALLET_ONE,
                    rank=5,
                    pnl=4_000,
                    volume=30_000,
                    category="POLITICS",
                    time_period="MONTH",
                    verified_badge=1,
                ),
            ]

            wallets, specialties = (
                engine.aggregate(entries)
            )

            self.assertEqual(
                len(wallets),
                1,
            )

            wallet = wallets[0]

            self.assertEqual(
                wallet.wallet,
                self.WALLET_ONE,
            )

            self.assertEqual(
                wallet.appearances,
                3,
            )

            self.assertEqual(
                wallet.categories_seen,
                2,
            )

            self.assertEqual(
                wallet.periods_seen,
                2,
            )

            self.assertEqual(
                wallet.best_rank,
                1,
            )

            self.assertEqual(
                wallet.verified_badge,
                1,
            )

            self.assertGreater(
                wallet.elite_score,
                0,
            )

            self.assertIn(
                (
                    self.WALLET_ONE,
                    "SPORTS",
                ),
                specialties,
            )

            self.assertIn(
                (
                    self.WALLET_ONE,
                    "POLITICS",
                ),
                specialties,
            )

    def test_collect_queries_each_category_period_pair(
        self,
    ) -> None:
        """Collection should query every configured board."""

        with tempfile.TemporaryDirectory() as directory:
            engine = self.create_engine(
                Path(directory) / "polymarket.db",
                categories=("SPORTS", "POLITICS"),
                periods=("DAY", "WEEK"),
            )

            fake_client = FakeLeaderboardClient(
                {
                    (
                        "SPORTS",
                        "DAY",
                    ): [
                        make_entry(
                            wallet=self.WALLET_ONE,
                            rank=1,
                            pnl=500,
                            volume=2_000,
                            category="SPORTS",
                            time_period="DAY",
                        )
                    ]
                }
            )

            engine.client = fake_client

            entries, query_count = engine.collect()

            self.assertEqual(
                query_count,
                4,
            )

            self.assertEqual(
                len(fake_client.calls),
                4,
            )

            self.assertEqual(
                len(entries),
                1,
            )

            queried_pairs = {
                (
                    call[0],
                    call[1],
                )
                for call in fake_client.calls
            }

            self.assertEqual(
                queried_pairs,
                {
                    ("SPORTS", "DAY"),
                    ("SPORTS", "WEEK"),
                    ("POLITICS", "DAY"),
                    ("POLITICS", "WEEK"),
                },
            )

    def test_apply_run_persists_results(
        self,
    ) -> None:
        """Apply mode should write discovery records."""

        with tempfile.TemporaryDirectory() as directory:
            database_path = (
                Path(directory)
                / "polymarket.db"
            )

            engine = self.create_engine(
                database_path
            )

            engine.client = FakeLeaderboardClient(
                {
                    (
                        "SPORTS",
                        "MONTH",
                    ): [
                        make_entry(
                            wallet=self.WALLET_ONE,
                            rank=2,
                            pnl=8_000,
                            volume=25_000,
                            verified_badge=1,
                        ),
                        make_entry(
                            wallet=self.WALLET_TWO,
                            rank=8,
                            pnl=3_000,
                            volume=15_000,
                            username="second-wallet",
                        ),
                    ]
                }
            )

            report = engine.run(
                apply=True
            )

            self.assertEqual(
                report["status"],
                "SUCCESS",
            )

            self.assertEqual(
                report["API_queries"],
                1,
            )

            self.assertEqual(
                report["leaderboard_rows"],
                2,
            )

            self.assertEqual(
                report["unique_wallets"],
                2,
            )

            self.assertEqual(
                report["snapshot_rows_inserted"],
                2,
            )

            self.assertEqual(
                report["wallet_rows_upserted"],
                2,
            )

            connection = sqlite3.connect(
                database_path
            )

            try:
                wallet_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM discovered_wallets
                    """
                ).fetchone()[0]

                snapshot_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM wallet_leaderboard_snapshots
                    """
                ).fetchone()[0]

                specialty_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM wallet_category_specialties
                    """
                ).fetchone()[0]

                run_status = connection.execute(
                    """
                    SELECT status
                    FROM wallet_discovery_runs
                    WHERE run_id = ?
                    """,
                    (report["run_id"],),
                ).fetchone()[0]

            finally:
                connection.close()

            self.assertEqual(
                wallet_count,
                2,
            )

            self.assertEqual(
                snapshot_count,
                2,
            )

            self.assertEqual(
                specialty_count,
                2,
            )

            self.assertEqual(
                run_status,
                "SUCCESS",
            )

    def test_dry_run_does_not_persist_wallet_data(
        self,
    ) -> None:
        """Dry-run mode should evaluate but not store results."""

        with tempfile.TemporaryDirectory() as directory:
            database_path = (
                Path(directory)
                / "polymarket.db"
            )

            engine = self.create_engine(
                database_path
            )

            engine.client = FakeLeaderboardClient(
                {
                    (
                        "SPORTS",
                        "MONTH",
                    ): [
                        make_entry(
                            wallet=self.WALLET_ONE,
                            rank=1,
                            pnl=5_000,
                            volume=20_000,
                        )
                    ]
                }
            )

            report = engine.run(
                apply=False
            )

            self.assertEqual(
                report["status"],
                "SUCCESS",
            )

            self.assertEqual(
                report["leaderboard_rows"],
                1,
            )

            self.assertEqual(
                report["unique_wallets"],
                1,
            )

            self.assertEqual(
                report["snapshot_rows_inserted"],
                0,
            )

            self.assertEqual(
                report["wallet_rows_upserted"],
                0,
            )

            connection = sqlite3.connect(
                database_path
            )

            try:
                wallet_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM discovered_wallets
                    """
                ).fetchone()[0]

                snapshot_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM wallet_leaderboard_snapshots
                    """
                ).fetchone()[0]

                run = connection.execute(
                    """
                    SELECT mode, status
                    FROM wallet_discovery_runs
                    WHERE run_id = ?
                    """,
                    (report["run_id"],),
                ).fetchone()

            finally:
                connection.close()

            self.assertEqual(
                wallet_count,
                0,
            )

            self.assertEqual(
                snapshot_count,
                0,
            )

            self.assertEqual(
                run,
                (
                    "DRY RUN",
                    "SUCCESS",
                ),
            )


if __name__ == "__main__":
    unittest.main()