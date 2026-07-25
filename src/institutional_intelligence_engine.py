from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from src.wallet_intelligence_source import WalletIntelligenceSource
from src.wallet_metrics import WalletMetricsEngine, WalletRawMetrics
from src.wallet_scoring import (
    SCORE_MODEL_VERSION,
    WalletScore,
    WalletScoringEngine,
)


INSTITUTIONAL_ENGINE_VERSION = "1.0.0"
METRICS_MODEL_VERSION = "1.0.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )


def normalize_wallet(wallet: str) -> str:
    return str(wallet or "").strip().lower()


@dataclass(frozen=True, slots=True)
class InstitutionalWalletProfile:
    metrics: WalletRawMetrics
    score: WalletScore


@dataclass(frozen=True, slots=True)
class InstitutionalRunSummary:
    generated_at: str
    wallets_requested: int
    wallets_loaded: int
    wallets_skipped: int
    production_wallets: int
    legacy_wallets: int
    source_model: str
    metrics_model: str
    scoring_model: str


@dataclass(frozen=True, slots=True)
class InstitutionalIntelligenceReport:
    summary: InstitutionalRunSummary
    profiles: tuple[InstitutionalWalletProfile, ...]


class InstitutionalIntelligenceEngine:
    """
    Read-only orchestrator connecting the wallet source,
    metrics engine, and scoring engine.
    """

    def __init__(
        self,
        source: WalletIntelligenceSource | None = None,
        metrics_engine: WalletMetricsEngine | None = None,
        scoring_engine: WalletScoringEngine | None = None,
    ) -> None:
        self.source = source or WalletIntelligenceSource()
        self.metrics_engine = (
            metrics_engine or WalletMetricsEngine()
        )
        self.scoring_engine = (
            scoring_engine or WalletScoringEngine()
        )

    def run(
        self,
        wallets: Iterable[str] | None = None,
    ) -> InstitutionalIntelligenceReport:
        requested_wallets = self._resolve_wallets(wallets)

        metrics_results: list[WalletRawMetrics] = []
        skipped = 0

        for wallet in requested_wallets:
            source_result = self.source.load_wallet(wallet)

            if source_result is None:
                skipped += 1
                continue

            metrics = self.metrics_engine.calculate(
                source_result
            )
            metrics_results.append(metrics)

        scores = self.scoring_engine.score_population(
            metrics_results
        )

        metrics_by_wallet = {
            normalize_wallet(item.wallet): item
            for item in metrics_results
        }

        profiles: list[InstitutionalWalletProfile] = []

        for score in scores:
            metrics = metrics_by_wallet.get(
                normalize_wallet(score.wallet)
            )

            if metrics is None:
                continue

            profiles.append(
                InstitutionalWalletProfile(
                    metrics=metrics,
                    score=score,
                )
            )

        production_wallets = sum(
            1
            for profile in profiles
            if profile.metrics.source_name == "production"
        )

        legacy_wallets = sum(
            1
            for profile in profiles
            if profile.metrics.source_name == "legacy"
        )

        summary = InstitutionalRunSummary(
            generated_at=utc_now_iso(),
            wallets_requested=len(requested_wallets),
            wallets_loaded=len(profiles),
            wallets_skipped=skipped,
            production_wallets=production_wallets,
            legacy_wallets=legacy_wallets,
            source_model="wallet-intelligence-source",
            metrics_model=METRICS_MODEL_VERSION,
            scoring_model=SCORE_MODEL_VERSION,
        )

        return InstitutionalIntelligenceReport(
            summary=summary,
            profiles=tuple(profiles),
        )

    def _resolve_wallets(
        self,
        wallets: Iterable[str] | None,
    ) -> list[str]:
        if wallets is None:
            candidates = self.source.available_wallets()
        else:
            candidates = wallets

        normalized: set[str] = set()

        for wallet in candidates:
            clean_wallet = normalize_wallet(wallet)

            if clean_wallet:
                normalized.add(clean_wallet)

        return sorted(normalized)
