#!/usr/bin/env python3
"""Institutional Wallet DNA Engine v1.0."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
METRICS_TABLE = "wallet_performance_metrics"
DNA_TABLE = "wallet_dna_profiles"
RUNS_TABLE = "wallet_dna_runs"
SUMMARY_TABLE = "wallet_profiles"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sf(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def si(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def grade(score: float) -> str:
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


@dataclass
class WalletDNA:
    wallet: str
    username: str
    calculated_at: str
    methodology_version: str
    primary_archetype: str
    secondary_archetype: str
    archetype_confidence: float
    conviction_score: float
    specialization_score: float
    activity_intensity_score: float
    diversification_score: float
    capital_scale_score: float
    profitability_quality_score: float
    consistency_score: float
    risk_control_score: float
    evidence_quality_score: float
    whale_score: float
    specialist_score: float
    selective_bettor_score: float
    active_trader_score: float
    diversified_portfolio_score: float
    aggressive_risk_taker_score: float
    disciplined_operator_score: float
    high_frequency_score: float
    dna_score: float
    dna_grade: str
    trust_tier: str
    follow_priority: str
    consensus_weight: float
    sample_limited: int
    warning_flags: str
    explanation: str


class WalletDNAEngine:
    def __init__(self, database: Path, wallet_limit: int, min_score: float) -> None:
        self.database = database
        self.wallet_limit = wallet_limit
        self.min_score = min_score

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def prepare(self) -> None:
        conn = self.connect()
        try:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if METRICS_TABLE not in tables:
                raise RuntimeError(
                    "wallet_performance_metrics is missing. "
                    "Run performance_analytics_engine.py --apply first."
                )

            conn.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS {q(RUNS_TABLE)} (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    wallet_limit INTEGER NOT NULL,
                    min_institutional_score REAL NOT NULL,
                    wallets_selected INTEGER NOT NULL DEFAULT 0,
                    wallets_analyzed INTEGER NOT NULL DEFAULT 0,
                    wallets_failed INTEGER NOT NULL DEFAULT 0,
                    dna_rows_upserted INTEGER NOT NULL DEFAULT 0,
                    summaries_updated INTEGER NOT NULL DEFAULT 0,
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS {q(DNA_TABLE)} (
                    wallet TEXT PRIMARY KEY,
                    username TEXT,
                    calculated_at TEXT NOT NULL,
                    methodology_version TEXT NOT NULL,
                    primary_archetype TEXT NOT NULL,
                    secondary_archetype TEXT NOT NULL,
                    archetype_confidence REAL NOT NULL DEFAULT 0,
                    conviction_score REAL NOT NULL DEFAULT 0,
                    specialization_score REAL NOT NULL DEFAULT 0,
                    activity_intensity_score REAL NOT NULL DEFAULT 0,
                    diversification_score REAL NOT NULL DEFAULT 0,
                    capital_scale_score REAL NOT NULL DEFAULT 0,
                    profitability_quality_score REAL NOT NULL DEFAULT 0,
                    consistency_score REAL NOT NULL DEFAULT 0,
                    risk_control_score REAL NOT NULL DEFAULT 0,
                    evidence_quality_score REAL NOT NULL DEFAULT 0,
                    whale_score REAL NOT NULL DEFAULT 0,
                    specialist_score REAL NOT NULL DEFAULT 0,
                    selective_bettor_score REAL NOT NULL DEFAULT 0,
                    active_trader_score REAL NOT NULL DEFAULT 0,
                    diversified_portfolio_score REAL NOT NULL DEFAULT 0,
                    aggressive_risk_taker_score REAL NOT NULL DEFAULT 0,
                    disciplined_operator_score REAL NOT NULL DEFAULT 0,
                    high_frequency_score REAL NOT NULL DEFAULT 0,
                    dna_score REAL NOT NULL DEFAULT 0,
                    dna_grade TEXT NOT NULL DEFAULT 'UNRATED',
                    trust_tier TEXT NOT NULL DEFAULT 'UNRATED',
                    follow_priority TEXT NOT NULL DEFAULT 'WATCH',
                    consensus_weight REAL NOT NULL DEFAULT 0,
                    sample_limited INTEGER NOT NULL DEFAULT 1,
                    warning_flags TEXT NOT NULL DEFAULT '[]',
                    explanation TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_wallet_dna_score
                    ON {q(DNA_TABLE)}(dna_score DESC, consensus_weight DESC);

                CREATE INDEX IF NOT EXISTS idx_wallet_dna_archetype
                    ON {q(DNA_TABLE)}(primary_archetype, dna_score DESC);
                """
            )
            conn.commit()
        finally:
            conn.close()

    def select_rows(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return list(
            conn.execute(
                f"""
                SELECT *
                FROM {q(METRICS_TABLE)}
                WHERE institutional_score >= ?
                ORDER BY institutional_score DESC, source_elite_score DESC
                LIMIT ?
                """,
                (self.min_score, self.wallet_limit),
            )
        )

    def analyze(self, row: sqlite3.Row) -> WalletDNA:
        current_count = si(row["current_position_count"])
        closed_count = si(row["closed_position_count"])
        trade_count = si(row["trade_sample_count"])
        activity_count = si(row["activity_sample_count"])
        total_markets = si(row["total_markets_traded"])

        institutional = sf(row["institutional_score"])
        profitability = sf(row["profitability_score"])
        consistency = sf(row["consistency_score"])
        risk_control = sf(row["risk_control_score"])
        specialization = sf(row["specialization_score"])
        activity = sf(row["activity_score"])
        scale = sf(row["scale_score"])
        data_quality = sf(row["data_quality_score"])
        concentration = sf(row["concentration_ratio"])
        win_rate = sf(row["closed_win_rate"])
        roi = sf(row["realized_roi_sample"])
        profit_factor = sf(row["profit_factor"])
        total_value = sf(row["total_current_value"])
        avg_trade = sf(row["average_trade_notional"])
        sample_limited = si(row["sample_limited"], 1)

        conviction = clamp(
            25 + 45 * min(concentration / 0.70, 1)
            + 20 * min(avg_trade / 25000, 1)
            + 10 * min(abs(roi) / 0.25, 1)
        )
        diversification = clamp(
            100 - specialization * 0.72
            + 18 * min(current_count / 100, 1)
        )
        activity_intensity = clamp(
            0.55 * activity
            + 25 * min(trade_count / 100, 1)
            + 20 * min(activity_count / 100, 1)
        )
        profitability_quality = clamp(
            0.55 * profitability
            + 22 * min(max(profit_factor, 0) / 2, 1)
            + 13 * min(max(win_rate - 0.50, 0) / 0.20, 1)
            + 10 * min(max(roi, 0) / 0.20, 1)
        )
        whale = clamp(
            0.60 * scale
            + 25 * min(total_value / 1_000_000, 1)
            + 15 * min(avg_trade / 50_000, 1)
        )
        specialist = clamp(
            0.72 * specialization
            + 18 * min(closed_count / 100, 1)
            + 10 * min(profitability_quality / 75, 1)
        )
        selective = clamp(
            75 - 35 * min(trade_count / 100, 1)
            - 20 * min(current_count / 100, 1)
            + 20 * min(conviction / 75, 1)
        )
        active = clamp(
            0.70 * activity_intensity
            + 20 * min(trade_count / 100, 1)
            + 10 * min(total_markets / 1000, 1)
        )
        diversified = clamp(
            0.70 * diversification
            + 20 * min(current_count / 100, 1)
            + 10 * min(total_markets / 1000, 1)
        )
        aggressive = clamp(
            0.55 * conviction
            + 30 * max(0, 1 - risk_control / 100)
            + 15 * min(concentration / 0.75, 1)
        )
        disciplined = clamp(
            0.34 * profitability_quality
            + 0.28 * consistency
            + 0.28 * risk_control
            + 0.10 * data_quality
        )
        high_frequency = clamp(
            0.55 * activity_intensity
            + 25 * min(trade_count / 100, 1)
            + 20 * min(total_markets / 10000, 1)
        )

        archetypes = {
            "WHALE": whale,
            "SPECIALIST": specialist,
            "SELECTIVE BETTOR": selective,
            "ACTIVE TRADER": active,
            "DIVERSIFIED PORTFOLIO": diversified,
            "AGGRESSIVE RISK TAKER": aggressive,
            "DISCIPLINED OPERATOR": disciplined,
            "HIGH-FREQUENCY TRADER": high_frequency,
        }
        ranked = sorted(archetypes.items(), key=lambda item: item[1], reverse=True)
        primary, primary_score = ranked[0]
        secondary, secondary_score = ranked[1]
        confidence = clamp(
            primary_score * 0.75 + max(primary_score - secondary_score, 0) * 2.5
        )

        evidence = clamp(
            data_quality
            - (18 if sample_limited else 0)
            + 8 * min(closed_count / 100, 1)
        )
        dna_score = clamp(
            0.23 * profitability_quality
            + 0.17 * consistency
            + 0.17 * risk_control
            + 0.10 * scale
            + 0.10 * specialization
            + 0.08 * activity_intensity
            + 0.08 * evidence
            + 0.07 * institutional
        )

        warnings: list[str] = []
        if sample_limited:
            warnings.append("SAMPLE_LIMITED")
        if closed_count < 30:
            warnings.append("LOW_CLOSED_POSITION_SAMPLE")
        if roi < 0:
            warnings.append("NEGATIVE_SAMPLED_ROI")
        if profit_factor < 1:
            warnings.append("PROFIT_FACTOR_BELOW_ONE")
        if concentration >= 0.70:
            warnings.append("HIGH_CONCENTRATION")
        if risk_control < 45:
            warnings.append("WEAK_RISK_CONTROL")
        if data_quality < 60:
            warnings.append("LOW_EVIDENCE_QUALITY")

        serious = {"NEGATIVE_SAMPLED_ROI", "PROFIT_FACTOR_BELOW_ONE"}
        if dna_score >= 80 and evidence >= 70 and not serious.intersection(warnings):
            trust_tier, priority = "ELITE", "PRIORITY"
        elif dna_score >= 68 and evidence >= 50:
            trust_tier, priority = "VERIFIED", "FOLLOW"
        elif dna_score >= 55:
            trust_tier, priority = "WATCHLIST", "WATCH"
        else:
            trust_tier, priority = "UNPROVEN", "LOW"

        penalty = 1.0
        if sample_limited:
            penalty *= 0.85
        if roi < 0:
            penalty *= 0.75
        if profit_factor < 1:
            penalty *= 0.80
        if closed_count < 30:
            penalty *= 0.75

        consensus_weight = clamp(
            dna_score * penalty * (0.65 + 0.35 * evidence / 100)
        )
        explanation = (
            f"{primary} with secondary traits of {secondary}. "
            f"Sampled win rate {win_rate * 100:.1f}%, ROI {roi * 100:.2f}%, "
            f"profit factor {profit_factor:.2f}, specialization "
            f"{specialization:.1f}%, institutional score {institutional:.2f}. "
            "Consensus weight is reduced for incomplete evidence or weak "
            "sampled profitability."
        )

        return WalletDNA(
            wallet=str(row["wallet"]),
            username=str(row["username"] or ""),
            calculated_at=utc_now(),
            methodology_version="1.0",
            primary_archetype=primary,
            secondary_archetype=secondary,
            archetype_confidence=confidence,
            conviction_score=conviction,
            specialization_score=specialization,
            activity_intensity_score=activity_intensity,
            diversification_score=diversification,
            capital_scale_score=scale,
            profitability_quality_score=profitability_quality,
            consistency_score=consistency,
            risk_control_score=risk_control,
            evidence_quality_score=evidence,
            whale_score=whale,
            specialist_score=specialist,
            selective_bettor_score=selective,
            active_trader_score=active,
            diversified_portfolio_score=diversified,
            aggressive_risk_taker_score=aggressive,
            disciplined_operator_score=disciplined,
            high_frequency_score=high_frequency,
            dna_score=dna_score,
            dna_grade=grade(dna_score),
            trust_tier=trust_tier,
            follow_priority=priority,
            consensus_weight=consensus_weight,
            sample_limited=sample_limited,
            warning_flags=json.dumps(warnings),
            explanation=explanation,
        )

    def upsert(self, conn: sqlite3.Connection, dna: WalletDNA) -> None:
        values = asdict(dna)
        columns = list(values)
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(
            f"{q(column)} = excluded.{q(column)}"
            for column in columns
            if column != "wallet"
        )
        conn.execute(
            f"""
            INSERT INTO {q(DNA_TABLE)}
                ({", ".join(q(column) for column in columns)})
            VALUES ({placeholders})
            ON CONFLICT(wallet) DO UPDATE SET {updates}
            """,
            tuple(values[column] for column in columns),
        )

        summary_columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({q(SUMMARY_TABLE)})")
        }
        if {"wallet", "dna_score", "dna_grade", "activity_style", "calculated_at"}.issubset(summary_columns):
            conn.execute(
                f"""
                UPDATE {q(SUMMARY_TABLE)}
                SET dna_score = ?, dna_grade = ?,
                    activity_style = ?, calculated_at = ?
                WHERE wallet = ?
                """,
                (
                    dna.dna_score,
                    dna.dna_grade,
                    dna.primary_archetype,
                    dna.calculated_at,
                    dna.wallet,
                ),
            )

    def run(self, apply: bool) -> None:
        self.prepare()
        started = time.perf_counter()
        run_id = uuid.uuid4().hex
        mode = "APPLY" if apply else "DRY RUN"
        results: list[WalletDNA] = []
        failures: list[dict[str, str]] = []

        conn = self.connect()
        try:
            rows = self.select_rows(conn)
            if apply:
                conn.execute(
                    f"""
                    INSERT INTO {q(RUNS_TABLE)} (
                        run_id, started_at, mode, wallet_limit,
                        min_institutional_score, wallets_selected, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 'RUNNING')
                    """,
                    (
                        run_id, utc_now(), mode, self.wallet_limit,
                        self.min_score, len(rows),
                    ),
                )
                conn.commit()

            for row in rows:
                wallet = str(row["wallet"])
                LOGGER.info(
                    "Building DNA wallet=%s institutional_score=%.2f",
                    wallet, sf(row["institutional_score"]),
                )
                try:
                    dna = self.analyze(row)
                    results.append(dna)
                    if apply:
                        self.upsert(conn, dna)
                except Exception as exc:
                    LOGGER.exception("DNA analysis failed for %s", wallet)
                    failures.append({"wallet": wallet, "error": str(exc)})

            if apply:
                conn.commit()

            duration = time.perf_counter() - started
            status = "SUCCESS" if not failures else "PARTIAL" if results else "FAILED"
            if apply:
                conn.execute(
                    f"""
                    UPDATE {q(RUNS_TABLE)}
                    SET finished_at = ?, wallets_analyzed = ?,
                        wallets_failed = ?, dna_rows_upserted = ?,
                        summaries_updated = ?, duration_seconds = ?,
                        status = ?, error_message = ?
                    WHERE run_id = ?
                    """,
                    (
                        utc_now(), len(results), len(failures), len(results),
                        len(results), duration, status,
                        json.dumps(failures) if failures else None, run_id,
                    ),
                )
                conn.commit()
        finally:
            conn.close()

        self.print_report(
            database=str(self.database),
            mode=mode,
            run_id=run_id,
            selected=len(results) + len(failures),
            results=results,
            failures=failures,
            upserted=len(results) if apply else 0,
            duration=time.perf_counter() - started,
        )

    @staticmethod
    def print_report(
        database: str,
        mode: str,
        run_id: str,
        selected: int,
        results: list[WalletDNA],
        failures: list[dict[str, str]],
        upserted: int,
        duration: float,
    ) -> None:
        status = "SUCCESS" if not failures else "PARTIAL" if results else "FAILED"
        print()
        print("=" * 118)
        print("INSTITUTIONAL WALLET DNA ENGINE")
        print("=" * 118)
        for label, value in [
            ("Database", database),
            ("Mode", mode),
            ("Run ID", run_id),
            ("Wallets selected", selected),
            ("Wallets analyzed", len(results)),
            ("Wallets failed", len(failures)),
            ("DNA rows upserted", upserted),
            ("Summaries updated", upserted),
            ("Duration", f"{duration:.3f}s"),
            ("Status", status),
        ]:
            print(f"{label + ':':38}{value}")

        print()
        print("WALLET DNA PROFILES")
        print("-" * 118)
        for index, item in enumerate(
            sorted(results, key=lambda value: value.dna_score, reverse=True), 1
        ):
            warnings = json.loads(item.warning_flags)
            flags = f" | {', '.join(warnings)}" if warnings else ""
            print(
                f"{index:>3}. {item.dna_grade:<3} DNA={item.dna_score:>6.2f} "
                f"weight={item.consensus_weight:>6.2f} "
                f"{item.username or '(no username)'}"
            )
            print(f"     {item.wallet}")
            print(
                f"     {item.primary_archetype} / {item.secondary_archetype} | "
                f"trust={item.trust_tier} | priority={item.follow_priority} | "
                f"confidence={item.archetype_confidence:.1f}%"
            )
            print(
                f"     conviction={item.conviction_score:.1f} | "
                f"specialization={item.specialization_score:.1f} | "
                f"risk control={item.risk_control_score:.1f} | "
                f"profit quality={item.profitability_quality_score:.1f} | "
                f"evidence={item.evidence_quality_score:.1f}{flags}"
            )
            print(f"     {item.explanation}")
        print("=" * 118)


def resolve_database(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="database/polymarket.db")
    parser.add_argument("--wallet-limit", type=int, default=25)
    parser.add_argument("--min-institutional-score", type=float, default=0.0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    if args.wallet_limit <= 0:
        raise SystemExit("--wallet-limit must be greater than zero")

    WalletDNAEngine(
        resolve_database(args.database),
        args.wallet_limit,
        args.min_institutional_score,
    ).run(args.apply)


if __name__ == "__main__":
    main()