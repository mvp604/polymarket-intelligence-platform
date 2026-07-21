#!/usr/bin/env python3
"""
Polymarket Intelligence Platform
Performance Analytics Engine v1.0

Purpose
-------
Transforms the latest successfully collected raw wallet snapshots into
repeatable performance features and institutional-style ratings.

Pipeline
--------
wallet_profiles_raw
    + wallet_current_position_snapshots
    + wallet_closed_position_snapshots
    + wallet_trade_snapshots
    + wallet_activity_snapshots
        -> wallet_performance_metrics
        -> wallet_profiles (compatibility/summary layer)

Important limitation
--------------------
Metrics are based on the locally collected sample. When collection limits are
used (for example 100 closed positions or 100 trades), results describe the
sample rather than the wallet's complete lifetime history.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


LOGGER = logging.getLogger(__name__)

RAW_PROFILES_TABLE = "wallet_profiles_raw"
CURRENT_TABLE = "wallet_current_position_snapshots"
CLOSED_TABLE = "wallet_closed_position_snapshots"
TRADES_TABLE = "wallet_trade_snapshots"
ACTIVITY_TABLE = "wallet_activity_snapshots"

RUNS_TABLE = "performance_analytics_runs"
METRICS_TABLE = "wallet_performance_metrics"
SUMMARY_TABLE = "wallet_profiles"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def median(values: Sequence[float]) -> float:
    return statistics.median(values) if values else 0.0


def pstdev(values: Sequence[float]) -> float:
    return statistics.pstdev(values) if len(values) >= 2 else 0.0


def grade_for_score(score: float) -> str:
    if score >= 90:
        return "S+"
    if score >= 85:
        return "S"
    if score >= 78:
        return "A+"
    if score >= 70:
        return "A"
    if score >= 62:
        return "B+"
    if score >= 54:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "SPORTS": (
        " vs ", "nba", "nfl", "nhl", "mlb", "ufc", "soccer", "football",
        "basketball", "baseball", "hockey", "tennis", "world cup", "champions",
        "premier league", "spread", "moneyline", "o/u", "over ", "under ",
    ),
    "POLITICS": (
        "president", "election", "senate", "congress", "governor", "nomination",
        "republican", "democrat", "trump", "cabinet", "minister", "parliament",
    ),
    "CRYPTO": (
        "bitcoin", "ethereum", "crypto", "solana", "xrp", "btc", "eth", "token",
    ),
    "MACRO": (
        "fed ", "interest rate", "inflation", "cpi", "gdp", "recession",
        "unemployment", "treasury", "central bank",
    ),
    "ENTERTAINMENT": (
        "oscar", "emmy", "grammy", "box office", "movie", "album", "celebrity",
        "tv show", "netflix",
    ),
}


def classify_title(title: str, fallback: str = "OTHER") -> str:
    value = f" {title.lower().strip()} "
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in value for keyword in keywords):
            return category
    normalized = fallback.upper().strip()
    return normalized if normalized in CATEGORY_KEYWORDS else "OTHER"


@dataclass
class WalletMetrics:
    wallet: str
    username: str
    source_run_id: str
    calculated_at: str
    source_elite_score: float
    source_elite_grade: str
    primary_category: str

    current_position_count: int
    closed_position_count: int
    trade_sample_count: int
    activity_sample_count: int
    total_markets_traded: int

    total_current_value: float
    total_open_pnl: float
    realized_pnl_sample: float
    gross_closed_cost_sample: float
    realized_roi_sample: float

    closed_win_count: int
    closed_loss_count: int
    closed_flat_count: int
    closed_win_rate: float
    profit_factor: float
    average_closed_pnl: float
    median_closed_pnl: float
    closed_pnl_volatility: float
    max_sample_drawdown: float

    profitable_open_position_rate: float
    average_position_value: float
    median_position_value: float
    largest_position_value: float
    concentration_ratio: float
    open_pnl_ratio: float

    buy_trade_count: int
    sell_trade_count: int
    trade_buy_ratio: float
    average_trade_notional: float
    median_trade_notional: float
    activity_notional_sample: float

    sports_exposure: float
    politics_exposure: float
    crypto_exposure: float
    macro_exposure: float
    entertainment_exposure: float
    other_exposure: float
    favorite_category: str
    specialization_score: float

    profitability_score: float
    consistency_score: float
    risk_control_score: float
    activity_score: float
    scale_score: float
    data_quality_score: float
    institutional_score: float
    institutional_grade: str
    risk_profile: str
    activity_style: str
    sample_limited: int
    methodology_version: str = "1.0"


class PerformanceAnalyticsEngine:
    def __init__(
        self,
        database_path: Path,
        wallet_limit: int,
        min_elite_score: float,
        min_closed_sample: int,
    ) -> None:
        self.database_path = database_path
        self.wallet_limit = wallet_limit
        self.min_elite_score = min_elite_score
        self.min_closed_sample = min_closed_sample
        self.api_queries = 0

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def require_tables(self) -> None:
        connection = self.connect()
        try:
            existing = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            required = {
                RAW_PROFILES_TABLE,
                CURRENT_TABLE,
                CLOSED_TABLE,
                TRADES_TABLE,
                ACTIVITY_TABLE,
            }
            missing = sorted(required - existing)
            if missing:
                raise RuntimeError(
                    "Required collector tables are missing: " + ", ".join(missing)
                )
        finally:
            connection.close()

    def create_tables(self) -> None:
        connection = self.connect()
        try:
            connection.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_identifier(RUNS_TABLE)} (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    wallet_limit INTEGER NOT NULL,
                    min_elite_score REAL NOT NULL,
                    min_closed_sample INTEGER NOT NULL,
                    wallets_selected INTEGER NOT NULL DEFAULT 0,
                    wallets_analyzed INTEGER NOT NULL DEFAULT 0,
                    wallets_failed INTEGER NOT NULL DEFAULT 0,
                    metrics_upserted INTEGER NOT NULL DEFAULT 0,
                    summaries_upserted INTEGER NOT NULL DEFAULT 0,
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS {quote_identifier(METRICS_TABLE)} (
                    wallet TEXT PRIMARY KEY,
                    username TEXT,
                    source_run_id TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    source_elite_score REAL NOT NULL DEFAULT 0,
                    source_elite_grade TEXT,
                    primary_category TEXT,

                    current_position_count INTEGER NOT NULL DEFAULT 0,
                    closed_position_count INTEGER NOT NULL DEFAULT 0,
                    trade_sample_count INTEGER NOT NULL DEFAULT 0,
                    activity_sample_count INTEGER NOT NULL DEFAULT 0,
                    total_markets_traded INTEGER NOT NULL DEFAULT 0,

                    total_current_value REAL NOT NULL DEFAULT 0,
                    total_open_pnl REAL NOT NULL DEFAULT 0,
                    realized_pnl_sample REAL NOT NULL DEFAULT 0,
                    gross_closed_cost_sample REAL NOT NULL DEFAULT 0,
                    realized_roi_sample REAL NOT NULL DEFAULT 0,

                    closed_win_count INTEGER NOT NULL DEFAULT 0,
                    closed_loss_count INTEGER NOT NULL DEFAULT 0,
                    closed_flat_count INTEGER NOT NULL DEFAULT 0,
                    closed_win_rate REAL NOT NULL DEFAULT 0,
                    profit_factor REAL NOT NULL DEFAULT 0,
                    average_closed_pnl REAL NOT NULL DEFAULT 0,
                    median_closed_pnl REAL NOT NULL DEFAULT 0,
                    closed_pnl_volatility REAL NOT NULL DEFAULT 0,
                    max_sample_drawdown REAL NOT NULL DEFAULT 0,

                    profitable_open_position_rate REAL NOT NULL DEFAULT 0,
                    average_position_value REAL NOT NULL DEFAULT 0,
                    median_position_value REAL NOT NULL DEFAULT 0,
                    largest_position_value REAL NOT NULL DEFAULT 0,
                    concentration_ratio REAL NOT NULL DEFAULT 0,
                    open_pnl_ratio REAL NOT NULL DEFAULT 0,

                    buy_trade_count INTEGER NOT NULL DEFAULT 0,
                    sell_trade_count INTEGER NOT NULL DEFAULT 0,
                    trade_buy_ratio REAL NOT NULL DEFAULT 0,
                    average_trade_notional REAL NOT NULL DEFAULT 0,
                    median_trade_notional REAL NOT NULL DEFAULT 0,
                    activity_notional_sample REAL NOT NULL DEFAULT 0,

                    sports_exposure REAL NOT NULL DEFAULT 0,
                    politics_exposure REAL NOT NULL DEFAULT 0,
                    crypto_exposure REAL NOT NULL DEFAULT 0,
                    macro_exposure REAL NOT NULL DEFAULT 0,
                    entertainment_exposure REAL NOT NULL DEFAULT 0,
                    other_exposure REAL NOT NULL DEFAULT 0,
                    favorite_category TEXT NOT NULL DEFAULT 'OTHER',
                    specialization_score REAL NOT NULL DEFAULT 0,

                    profitability_score REAL NOT NULL DEFAULT 0,
                    consistency_score REAL NOT NULL DEFAULT 0,
                    risk_control_score REAL NOT NULL DEFAULT 0,
                    activity_score REAL NOT NULL DEFAULT 0,
                    scale_score REAL NOT NULL DEFAULT 0,
                    data_quality_score REAL NOT NULL DEFAULT 0,
                    institutional_score REAL NOT NULL DEFAULT 0,
                    institutional_grade TEXT NOT NULL DEFAULT 'UNRATED',
                    risk_profile TEXT NOT NULL DEFAULT 'UNKNOWN',
                    activity_style TEXT NOT NULL DEFAULT 'UNKNOWN',
                    sample_limited INTEGER NOT NULL DEFAULT 1,
                    methodology_version TEXT NOT NULL DEFAULT '1.0'
                );

                CREATE INDEX IF NOT EXISTS idx_wallet_performance_rating
                    ON {quote_identifier(METRICS_TABLE)}(
                        institutional_score DESC,
                        closed_win_rate DESC
                    );

                CREATE INDEX IF NOT EXISTS idx_wallet_performance_category
                    ON {quote_identifier(METRICS_TABLE)}(
                        favorite_category,
                        specialization_score DESC
                    );
                """
            )
            self.ensure_summary_table(connection)
            connection.commit()
        finally:
            connection.close()

    def ensure_summary_table(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute(
                f"PRAGMA table_info({quote_identifier(SUMMARY_TABLE)})"
            )
        }
        expected = {
            "wallet", "wallet_score", "wallet_grade", "scan_count",
            "active_position_count", "meaningful_position_count",
            "total_current_value", "total_open_pnl", "open_pnl_ratio",
            "profitable_position_rate", "average_position_value",
            "median_position_value", "largest_position_value",
            "concentration_ratio", "average_entry_price",
            "average_current_price", "average_observed_move",
            "sports_exposure", "politics_exposure", "crypto_exposure",
            "macro_exposure", "entertainment_exposure", "other_exposure",
            "favorite_category", "activity_style", "risk_profile",
            "leader_score", "activity_score", "specialization_score",
            "dna_score", "dna_grade", "first_observed_at",
            "latest_observed_at", "calculated_at",
        }
        if not columns:
            connection.execute(
                f"""
                CREATE TABLE {quote_identifier(SUMMARY_TABLE)} (
                    wallet TEXT PRIMARY KEY,
                    wallet_score REAL NOT NULL DEFAULT 0,
                    wallet_grade TEXT NOT NULL DEFAULT 'UNRATED',
                    scan_count INTEGER NOT NULL DEFAULT 0,
                    active_position_count INTEGER NOT NULL DEFAULT 0,
                    meaningful_position_count INTEGER NOT NULL DEFAULT 0,
                    total_current_value REAL NOT NULL DEFAULT 0,
                    total_open_pnl REAL NOT NULL DEFAULT 0,
                    open_pnl_ratio REAL NOT NULL DEFAULT 0,
                    profitable_position_rate REAL NOT NULL DEFAULT 0,
                    average_position_value REAL NOT NULL DEFAULT 0,
                    median_position_value REAL NOT NULL DEFAULT 0,
                    largest_position_value REAL NOT NULL DEFAULT 0,
                    concentration_ratio REAL NOT NULL DEFAULT 0,
                    average_entry_price REAL NOT NULL DEFAULT 0,
                    average_current_price REAL NOT NULL DEFAULT 0,
                    average_observed_move REAL NOT NULL DEFAULT 0,
                    sports_exposure REAL NOT NULL DEFAULT 0,
                    politics_exposure REAL NOT NULL DEFAULT 0,
                    crypto_exposure REAL NOT NULL DEFAULT 0,
                    macro_exposure REAL NOT NULL DEFAULT 0,
                    entertainment_exposure REAL NOT NULL DEFAULT 0,
                    other_exposure REAL NOT NULL DEFAULT 0,
                    favorite_category TEXT NOT NULL DEFAULT 'Unknown',
                    activity_style TEXT NOT NULL DEFAULT 'Unknown',
                    risk_profile TEXT NOT NULL DEFAULT 'Unknown',
                    leader_score REAL NOT NULL DEFAULT 0,
                    activity_score REAL NOT NULL DEFAULT 0,
                    specialization_score REAL NOT NULL DEFAULT 0,
                    dna_score REAL NOT NULL DEFAULT 0,
                    dna_grade TEXT NOT NULL DEFAULT 'UNRATED',
                    first_observed_at TEXT,
                    latest_observed_at TEXT,
                    calculated_at TEXT NOT NULL
                )
                """
            )
            return

        missing = sorted(expected - columns)
        if missing:
            raise RuntimeError(
                f"{SUMMARY_TABLE} exists but is missing required columns: "
                + ", ".join(missing)
            )

    def select_wallets(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return list(
            connection.execute(
                f"""
                SELECT *
                FROM {quote_identifier(RAW_PROFILES_TABLE)}
                WHERE latest_collection_status = 'SUCCESS'
                  AND source_elite_score >= ?
                ORDER BY source_elite_score DESC, position_value DESC, wallet
                LIMIT ?
                """,
                (self.min_elite_score, self.wallet_limit),
            )
        )

    def rows_for_run(
        self,
        connection: sqlite3.Connection,
        table: str,
        wallet: str,
        run_id: str,
        order_by: str = "id",
    ) -> list[sqlite3.Row]:
        return list(
            connection.execute(
                f"""
                SELECT *
                FROM {quote_identifier(table)}
                WHERE wallet = ? AND run_id = ?
                ORDER BY {order_by}
                """,
                (wallet, run_id),
            )
        )

    @staticmethod
    def calculate_drawdown(closed_rows: Sequence[sqlite3.Row]) -> float:
        ordered = sorted(
            closed_rows,
            key=lambda row: (
                safe_int(row["closed_timestamp"], 0),
                safe_int(row["id"], 0),
            ),
        )
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for row in ordered:
            equity += safe_float(row["realized_pnl"])
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return max_drawdown

    def category_exposures(
        self,
        current_rows: Sequence[sqlite3.Row],
        closed_rows: Sequence[sqlite3.Row],
        trade_rows: Sequence[sqlite3.Row],
        primary_category: str,
    ) -> dict[str, float]:
        weights = {key: 0.0 for key in (*CATEGORY_KEYWORDS.keys(), "OTHER")}

        for row in current_rows:
            category = classify_title(
                str(row["title"] or ""),
                primary_category,
            )
            weight = max(safe_float(row["current_value"]), 1.0)
            weights[category] += weight

        for row in closed_rows:
            category = classify_title(
                str(row["title"] or ""),
                primary_category,
            )
            weight = max(
                safe_float(row["total_bought"]) * safe_float(row["avg_price"]),
                1.0,
            )
            weights[category] += weight

        for row in trade_rows:
            category = classify_title(
                str(row["title"] or ""),
                primary_category,
            )
            weight = max(
                safe_float(row["size"]) * safe_float(row["price"]),
                1.0,
            )
            weights[category] += weight

        total = sum(weights.values())
        if total <= 0:
            fallback = primary_category.upper()
            weights[fallback if fallback in weights else "OTHER"] = 1.0
            total = 1.0

        return {key: value / total for key, value in weights.items()}

    def analyze_wallet(
        self,
        connection: sqlite3.Connection,
        profile: sqlite3.Row,
    ) -> WalletMetrics:
        wallet = profile["wallet"]
        run_id = profile["last_run_id"]
        primary_category = str(profile["primary_category"] or "OTHER").upper()

        current_rows = self.rows_for_run(
            connection, CURRENT_TABLE, wallet, run_id
        )
        closed_rows = self.rows_for_run(
            connection, CLOSED_TABLE, wallet, run_id,
            "COALESCE(closed_timestamp, 0), id",
        )
        trade_rows = self.rows_for_run(
            connection, TRADES_TABLE, wallet, run_id,
            "COALESCE(trade_timestamp, 0), id",
        )
        activity_rows = self.rows_for_run(
            connection, ACTIVITY_TABLE, wallet, run_id,
            "COALESCE(activity_timestamp, 0), id",
        )

        current_values = [
            max(0.0, safe_float(row["current_value"]))
            for row in current_rows
        ]
        open_pnls = [safe_float(row["cash_pnl"]) for row in current_rows]
        closed_pnls = [safe_float(row["realized_pnl"]) for row in closed_rows]
        closed_costs = [
            max(
                0.0,
                safe_float(row["total_bought"]) * safe_float(row["avg_price"]),
            )
            for row in closed_rows
        ]

        total_current_value = sum(current_values)
        total_open_pnl = sum(open_pnls)
        realized_pnl = sum(closed_pnls)
        gross_closed_cost = sum(closed_costs)

        wins = sum(value > 1e-9 for value in closed_pnls)
        losses = sum(value < -1e-9 for value in closed_pnls)
        flats = len(closed_pnls) - wins - losses
        decisive = wins + losses

        gross_profit = sum(value for value in closed_pnls if value > 0)
        gross_loss = abs(sum(value for value in closed_pnls if value < 0))
        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else (10.0 if gross_profit > 0 else 0.0)
        )

        trade_notionals = [
            max(0.0, safe_float(row["size"]) * safe_float(row["price"]))
            for row in trade_rows
        ]
        buy_count = sum(str(row["side"] or "").upper() == "BUY" for row in trade_rows)
        sell_count = sum(str(row["side"] or "").upper() == "SELL" for row in trade_rows)

        activity_notional = sum(
            max(
                safe_float(row["usdc_size"]),
                safe_float(row["size"]) * safe_float(row["price"]),
                0.0,
            )
            for row in activity_rows
        )

        exposures = self.category_exposures(
            current_rows, closed_rows, trade_rows, primary_category
        )
        favorite_category = max(exposures, key=exposures.get)
        specialization = exposures[favorite_category] * 100.0

        average_position = mean(current_values)
        median_position = median(current_values)
        largest_position = max(current_values, default=0.0)
        concentration = ratio(largest_position, total_current_value)
        open_profit_rate = ratio(
            sum(value > 0 for value in open_pnls),
            len(open_pnls),
        )
        closed_win_rate = ratio(wins, decisive)
        realized_roi = ratio(realized_pnl, gross_closed_cost)
        open_pnl_ratio = ratio(total_open_pnl, total_current_value)

        # Component scoring. These scores prioritize repeatable profitability,
        # sample quality, and controlled risk—not leaderboard rank alone.
        profitability_score = clamp(
            45.0
            + 35.0 * math.tanh(realized_roi * 3.0)
            + 10.0 * math.tanh((profit_factor - 1.0) / 2.0)
            + 10.0 * (closed_win_rate - 0.5) * 2.0
        )

        pnl_volatility = pstdev(closed_pnls)
        normalized_volatility = ratio(
            pnl_volatility,
            abs(mean(closed_pnls)) + mean(closed_costs) * 0.10 + 1.0,
        )
        consistency_score = clamp(
            50.0
            + (closed_win_rate - 0.5) * 55.0
            + 12.0 * math.tanh((profit_factor - 1.0) / 2.0)
            - 18.0 * math.tanh(normalized_volatility)
        )

        max_drawdown = self.calculate_drawdown(closed_rows)
        drawdown_ratio = ratio(max_drawdown, gross_closed_cost)
        concentration_penalty = max(0.0, concentration - 0.35) * 70.0
        risk_control_score = clamp(
            82.0
            - 90.0 * min(drawdown_ratio, 0.75)
            - concentration_penalty
            + 8.0 * min(len(closed_rows) / 100.0, 1.0)
        )

        activity_score = clamp(
            20.0
            + 35.0 * min(len(trade_rows) / 100.0, 1.0)
            + 25.0 * min(len(activity_rows) / 100.0, 1.0)
            + 20.0 * math.tanh(activity_notional / 100_000.0)
        )

        scale_score = clamp(
            20.0
            + 32.0 * math.tanh(total_current_value / 250_000.0)
            + 28.0 * math.tanh(gross_closed_cost / 250_000.0)
            + 20.0 * min(safe_int(profile["total_markets_traded"]) / 1000.0, 1.0)
        )

        data_quality_score = clamp(
            15.0
            + 40.0 * min(len(closed_rows) / max(self.min_closed_sample, 1), 1.0)
            + 20.0 * min(len(trade_rows) / 100.0, 1.0)
            + 15.0 * min(len(activity_rows) / 100.0, 1.0)
            + 10.0 * min(len(current_rows) / 25.0, 1.0)
        )

        institutional_score = clamp(
            0.28 * profitability_score
            + 0.20 * consistency_score
            + 0.18 * risk_control_score
            + 0.10 * activity_score
            + 0.10 * scale_score
            + 0.08 * specialization
            + 0.06 * data_quality_score
        )

        if concentration >= 0.75 or drawdown_ratio >= 0.35:
            risk_profile = "AGGRESSIVE"
        elif concentration >= 0.45 or drawdown_ratio >= 0.18:
            risk_profile = "MODERATE-HIGH"
        elif concentration >= 0.25 or drawdown_ratio >= 0.08:
            risk_profile = "MODERATE"
        else:
            risk_profile = "CONTROLLED"

        trades_per_market = ratio(
            len(trade_rows),
            max(safe_int(profile["total_markets_traded"]), 1),
        )
        if len(trade_rows) >= 80 and trades_per_market >= 2.0:
            activity_style = "HIGH-FREQUENCY"
        elif specialization >= 70:
            activity_style = "SPECIALIST"
        elif len(current_rows) >= 100:
            activity_style = "HIGH-DIVERSIFICATION"
        elif len(trade_rows) >= 40:
            activity_style = "ACTIVE"
        else:
            activity_style = "SELECTIVE"

        sample_limited = int(
            len(closed_rows) < self.min_closed_sample
            or len(trade_rows) >= safe_int(profile["trade_sample_count"])
            and safe_int(profile["trade_sample_count"]) in {100, 200, 500, 1000}
        )

        return WalletMetrics(
            wallet=wallet,
            username=str(profile["username"] or ""),
            source_run_id=run_id,
            calculated_at=utc_now(),
            source_elite_score=safe_float(profile["source_elite_score"]),
            source_elite_grade=str(profile["source_elite_grade"] or ""),
            primary_category=primary_category,
            current_position_count=len(current_rows),
            closed_position_count=len(closed_rows),
            trade_sample_count=len(trade_rows),
            activity_sample_count=len(activity_rows),
            total_markets_traded=safe_int(profile["total_markets_traded"]),
            total_current_value=total_current_value,
            total_open_pnl=total_open_pnl,
            realized_pnl_sample=realized_pnl,
            gross_closed_cost_sample=gross_closed_cost,
            realized_roi_sample=realized_roi,
            closed_win_count=wins,
            closed_loss_count=losses,
            closed_flat_count=flats,
            closed_win_rate=closed_win_rate,
            profit_factor=profit_factor,
            average_closed_pnl=mean(closed_pnls),
            median_closed_pnl=median(closed_pnls),
            closed_pnl_volatility=pnl_volatility,
            max_sample_drawdown=max_drawdown,
            profitable_open_position_rate=open_profit_rate,
            average_position_value=average_position,
            median_position_value=median_position,
            largest_position_value=largest_position,
            concentration_ratio=concentration,
            open_pnl_ratio=open_pnl_ratio,
            buy_trade_count=buy_count,
            sell_trade_count=sell_count,
            trade_buy_ratio=ratio(buy_count, buy_count + sell_count),
            average_trade_notional=mean(trade_notionals),
            median_trade_notional=median(trade_notionals),
            activity_notional_sample=activity_notional,
            sports_exposure=exposures["SPORTS"],
            politics_exposure=exposures["POLITICS"],
            crypto_exposure=exposures["CRYPTO"],
            macro_exposure=exposures["MACRO"],
            entertainment_exposure=exposures["ENTERTAINMENT"],
            other_exposure=exposures["OTHER"],
            favorite_category=favorite_category,
            specialization_score=specialization,
            profitability_score=profitability_score,
            consistency_score=consistency_score,
            risk_control_score=risk_control_score,
            activity_score=activity_score,
            scale_score=scale_score,
            data_quality_score=data_quality_score,
            institutional_score=institutional_score,
            institutional_grade=grade_for_score(institutional_score),
            risk_profile=risk_profile,
            activity_style=activity_style,
            sample_limited=sample_limited,
        )

    def upsert_metrics(
        self,
        connection: sqlite3.Connection,
        metrics: WalletMetrics,
    ) -> None:
        values = asdict(metrics)
        columns = list(values)
        placeholders = ", ".join("?" for _ in columns)
        update_clause = ", ".join(
            f"{quote_identifier(column)} = excluded.{quote_identifier(column)}"
            for column in columns
            if column != "wallet"
        )
        connection.execute(
            f"""
            INSERT INTO {quote_identifier(METRICS_TABLE)}
                ({", ".join(quote_identifier(column) for column in columns)})
            VALUES ({placeholders})
            ON CONFLICT(wallet) DO UPDATE SET
                {update_clause}
            """,
            tuple(values[column] for column in columns),
        )

    def upsert_summary(
        self,
        connection: sqlite3.Connection,
        metrics: WalletMetrics,
    ) -> None:
        current_rows = self.rows_for_run(
            connection, CURRENT_TABLE, metrics.wallet, metrics.source_run_id
        )
        average_entry = mean([safe_float(row["avg_price"]) for row in current_rows])
        average_current = mean(
            [safe_float(row["current_price"]) for row in current_rows]
        )
        average_move = mean(
            [
                safe_float(row["current_price"]) - safe_float(row["avg_price"])
                for row in current_rows
            ]
        )
        meaningful_count = sum(
            safe_float(row["current_value"]) >= 500.0 for row in current_rows
        )

        connection.execute(
            f"""
            INSERT INTO {quote_identifier(SUMMARY_TABLE)} (
                wallet, wallet_score, wallet_grade, scan_count,
                active_position_count, meaningful_position_count,
                total_current_value, total_open_pnl, open_pnl_ratio,
                profitable_position_rate, average_position_value,
                median_position_value, largest_position_value,
                concentration_ratio, average_entry_price,
                average_current_price, average_observed_move,
                sports_exposure, politics_exposure, crypto_exposure,
                macro_exposure, entertainment_exposure, other_exposure,
                favorite_category, activity_style, risk_profile,
                leader_score, activity_score, specialization_score,
                dna_score, dna_grade, first_observed_at,
                latest_observed_at, calculated_at
            ) VALUES (
                ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(wallet) DO UPDATE SET
                wallet_score = excluded.wallet_score,
                wallet_grade = excluded.wallet_grade,
                scan_count = {quote_identifier(SUMMARY_TABLE)}.scan_count + 1,
                active_position_count = excluded.active_position_count,
                meaningful_position_count = excluded.meaningful_position_count,
                total_current_value = excluded.total_current_value,
                total_open_pnl = excluded.total_open_pnl,
                open_pnl_ratio = excluded.open_pnl_ratio,
                profitable_position_rate = excluded.profitable_position_rate,
                average_position_value = excluded.average_position_value,
                median_position_value = excluded.median_position_value,
                largest_position_value = excluded.largest_position_value,
                concentration_ratio = excluded.concentration_ratio,
                average_entry_price = excluded.average_entry_price,
                average_current_price = excluded.average_current_price,
                average_observed_move = excluded.average_observed_move,
                sports_exposure = excluded.sports_exposure,
                politics_exposure = excluded.politics_exposure,
                crypto_exposure = excluded.crypto_exposure,
                macro_exposure = excluded.macro_exposure,
                entertainment_exposure = excluded.entertainment_exposure,
                other_exposure = excluded.other_exposure,
                favorite_category = excluded.favorite_category,
                activity_style = excluded.activity_style,
                risk_profile = excluded.risk_profile,
                leader_score = excluded.leader_score,
                activity_score = excluded.activity_score,
                specialization_score = excluded.specialization_score,
                dna_score = excluded.dna_score,
                dna_grade = excluded.dna_grade,
                first_observed_at = COALESCE(
                    {quote_identifier(SUMMARY_TABLE)}.first_observed_at,
                    excluded.first_observed_at
                ),
                latest_observed_at = excluded.latest_observed_at,
                calculated_at = excluded.calculated_at
            """,
            (
                metrics.wallet,
                metrics.institutional_score,
                metrics.institutional_grade,
                metrics.current_position_count,
                meaningful_count,
                metrics.total_current_value,
                metrics.total_open_pnl,
                metrics.open_pnl_ratio,
                metrics.profitable_open_position_rate,
                metrics.average_position_value,
                metrics.median_position_value,
                metrics.largest_position_value,
                metrics.concentration_ratio,
                average_entry,
                average_current,
                average_move,
                metrics.sports_exposure,
                metrics.politics_exposure,
                metrics.crypto_exposure,
                metrics.macro_exposure,
                metrics.entertainment_exposure,
                metrics.other_exposure,
                metrics.favorite_category,
                metrics.activity_style,
                metrics.risk_profile,
                metrics.source_elite_score,
                metrics.activity_score,
                metrics.specialization_score,
                metrics.institutional_score,
                metrics.institutional_grade,
                metrics.calculated_at,
                metrics.calculated_at,
                metrics.calculated_at,
            ),
        )

    def run(self, apply: bool) -> dict[str, Any]:
        self.require_tables()
        self.create_tables()

        started = time.perf_counter()
        run_id = uuid.uuid4().hex
        mode = "APPLY" if apply else "DRY RUN"
        status = "SUCCESS"
        error_message: str | None = None
        analyzed: list[WalletMetrics] = []
        failures: list[dict[str, str]] = []

        connection = self.connect()
        try:
            profiles = self.select_wallets(connection)

            if apply:
                connection.execute(
                    f"""
                    INSERT INTO {quote_identifier(RUNS_TABLE)} (
                        run_id, started_at, mode, wallet_limit,
                        min_elite_score, min_closed_sample,
                        wallets_selected, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id, utc_now(), mode, self.wallet_limit,
                        self.min_elite_score, self.min_closed_sample,
                        len(profiles), "RUNNING",
                    ),
                )
                connection.commit()

            for index, profile in enumerate(profiles, start=1):
                wallet = str(profile["wallet"])
                LOGGER.info(
                    "Analyzing wallet=%s score=%.2f grade=%s",
                    wallet,
                    safe_float(profile["source_elite_score"]),
                    profile["source_elite_grade"],
                )
                try:
                    metrics = self.analyze_wallet(connection, profile)
                    analyzed.append(metrics)
                    if apply:
                        self.upsert_metrics(connection, metrics)
                        self.upsert_summary(connection, metrics)
                except Exception as exc:  # continue other wallets
                    LOGGER.exception("Wallet analysis failed: %s", wallet)
                    failures.append({"wallet": wallet, "error": str(exc)})

            if apply:
                connection.commit()

        except Exception as exc:
            status = "FAILED"
            error_message = str(exc)
            if apply:
                connection.rollback()
            raise
        finally:
            duration = time.perf_counter() - started
            if apply:
                try:
                    connection.execute(
                        f"""
                        UPDATE {quote_identifier(RUNS_TABLE)}
                        SET finished_at = ?,
                            wallets_analyzed = ?,
                            wallets_failed = ?,
                            metrics_upserted = ?,
                            summaries_upserted = ?,
                            duration_seconds = ?,
                            status = ?,
                            error_message = ?
                        WHERE run_id = ?
                        """,
                        (
                            utc_now(),
                            len(analyzed),
                            len(failures),
                            len(analyzed),
                            len(analyzed),
                            duration,
                            "SUCCESS" if not failures and status == "SUCCESS"
                            else "PARTIAL" if analyzed
                            else "FAILED",
                            json.dumps(failures) if failures else error_message,
                            run_id,
                        ),
                    )
                    connection.commit()
                except Exception:
                    LOGGER.exception("Unable to finalize analytics run record")
            connection.close()

        final_status = (
            "SUCCESS" if not failures
            else "PARTIAL" if analyzed
            else "FAILED"
        )
        report = {
            "database": str(self.database_path),
            "mode": mode,
            "run_id": run_id,
            "wallets_selected": len(analyzed) + len(failures),
            "wallets_analyzed": len(analyzed),
            "wallets_failed": len(failures),
            "metrics_upserted": len(analyzed) if apply else 0,
            "summaries_upserted": len(analyzed) if apply else 0,
            "duration": duration,
            "status": final_status,
            "wallets": analyzed,
            "failures": failures,
        }
        self.print_report(report)
        return report

    @staticmethod
    def print_report(report: dict[str, Any]) -> None:
        print()
        print("=" * 118)
        print("PERFORMANCE ANALYTICS ENGINE")
        print("=" * 118)
        fields = [
            ("Database", report["database"]),
            ("Mode", report["mode"]),
            ("Run ID", report["run_id"]),
            ("Wallets selected", report["wallets_selected"]),
            ("Wallets analyzed", report["wallets_analyzed"]),
            ("Wallets failed", report["wallets_failed"]),
            ("Metrics upserted", report["metrics_upserted"]),
            ("Summaries upserted", report["summaries_upserted"]),
            ("Duration", f'{report["duration"]:.3f}s'),
            ("Status", report["status"]),
        ]
        for label, value in fields:
            print(f"{label + ':':38}{value}")

        print()
        print("INSTITUTIONAL WALLET RATINGS")
        print("-" * 118)
        ranked = sorted(
            report["wallets"],
            key=lambda item: item.institutional_score,
            reverse=True,
        )
        for index, item in enumerate(ranked, start=1):
            sample_flag = " | SAMPLE-LIMITED" if item.sample_limited else ""
            print(
                f"{index:>3}. {item.institutional_grade:<3} "
                f"score={item.institutional_score:>6.2f} "
                f"{item.username or '(no username)'}{sample_flag}"
            )
            print(f"     {item.wallet}")
            print(
                "     "
                f"closed={item.closed_position_count} | "
                f"win rate={item.closed_win_rate * 100:,.1f}% | "
                f"sample ROI={item.realized_roi_sample * 100:,.2f}% | "
                f"realized PnL=${item.realized_pnl_sample:,.2f} | "
                f"profit factor={item.profit_factor:,.2f}"
            )
            print(
                "     "
                f"current value=${item.total_current_value:,.2f} | "
                f"risk={item.risk_profile} | "
                f"style={item.activity_style} | "
                f"specialty={item.favorite_category} "
                f"({item.specialization_score:,.1f}%)"
            )

        if report["failures"]:
            print()
            print("FAILURES")
            print("-" * 118)
            for failure in report["failures"]:
                print(f"{failure['wallet']}: {failure['error']}")

        print("=" * 118)


def resolve_database_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[1]
        path = project_root / path
    return path.resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate wallet performance and institutional ratings."
    )
    parser.add_argument(
        "--database",
        default="database/polymarket.db",
        help="SQLite database path relative to the project root.",
    )
    parser.add_argument(
        "--wallet-limit",
        type=int,
        default=25,
        help="Maximum number of successfully collected wallets to analyze.",
    )
    parser.add_argument(
        "--min-elite-score",
        type=float,
        default=0.0,
        help="Minimum source discovery score.",
    )
    parser.add_argument(
        "--min-closed-sample",
        type=int,
        default=30,
        help="Closed-position count considered minimally reliable.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist metrics and update the wallet_profiles summary table.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if args.wallet_limit <= 0:
        raise SystemExit("--wallet-limit must be greater than zero")
    if args.min_closed_sample <= 0:
        raise SystemExit("--min-closed-sample must be greater than zero")

    engine = PerformanceAnalyticsEngine(
        database_path=resolve_database_path(args.database),
        wallet_limit=args.wallet_limit,
        min_elite_score=args.min_elite_score,
        min_closed_sample=args.min_closed_sample,
    )
    engine.run(apply=args.apply)


if __name__ == "__main__":
    main()