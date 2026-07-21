from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from data_access import DataAccess, DATABASE_PATH
    from dashboard_repository import DashboardRepository
except ImportError:
    from src.data_access import DataAccess, DATABASE_PATH
    from src.dashboard_repository import DashboardRepository


LOGGER = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_market_id(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_outcome(value: Any) -> str:
    text = str(value or "").strip()
    return text or "UNKNOWN"


def first_value(
    row: Mapping[str, Any] | None,
    keys: Sequence[str],
    default: Any = None,
) -> Any:
    if not row:
        return default

    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value

    return default


@dataclass(slots=True)
class BuildError:
    condition_id: str
    outcome: str
    error: str


@dataclass(slots=True)
class BuildSummary:
    mode: str
    source_markets: int = 0
    processed_rows: int = 0
    built_rows: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0
    history_rows: int = 0
    skipped_rows: int = 0
    unmatched_rows: int = 0
    error_count: int = 0
    run_id: str | None = None
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str | None = None
    duration_seconds: float = 0.0
    errors: list[BuildError] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "source_markets": self.source_markets,
            "processed_rows": self.processed_rows,
            "built_rows": self.built_rows,
            "inserted_rows": self.inserted_rows,
            "updated_rows": self.updated_rows,
            "history_rows": self.history_rows,
            "skipped_rows": self.skipped_rows,
            "unmatched_rows": self.unmatched_rows,
            "error_count": self.error_count,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "errors": [
                {
                    "condition_id": item.condition_id,
                    "outcome": item.outcome,
                    "error": item.error,
                }
                for item in self.errors
            ],
        }


class MasterIntelligenceDashboardBuilder:
    """
    Assemble one unified dashboard snapshot per market outcome.

    The builder contains no dashboard SQL. It reads through DataAccess and
    persists through DashboardRepository.
    """

    def __init__(
        self,
        data_access: DataAccess | None = None,
        repository: DashboardRepository | None = None,
        database_path: Path | str = DATABASE_PATH,
    ) -> None:
        self.data = data_access or DataAccess(database_path)
        self.repository = repository or DashboardRepository(
            data_access=self.data
        )
        self.repository.initialize_schema()

    def load_source_rows(
        self,
        *,
        mode: str = "focused",
        limit: int | None = None,
        minimum_master_score: float | None = None,
    ) -> list[dict[str, Any]]:
        normalized_mode = mode.strip().casefold()

        if normalized_mode == "focused":
            rows = self.data.get_master_opportunities(
                limit=limit or 100_000,
                minimum_score=minimum_master_score,
                include_inactive=True,
            )
            return rows

        if normalized_mode == "full":
            rows = self.data.get_tradable_markets(
                limit=limit,
            )
            return rows

        raise ValueError(
            "Unsupported mode. Use 'focused' or 'full'."
        )

    def resolve_identity(
        self,
        source_row: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        condition_id = normalize_market_id(
            first_value(
                source_row,
                (
                    "condition_id",
                    "market_id",
                    "canonical_condition_id",
                ),
            )
        )

        if condition_id:
            market = self.data.get_market(condition_id)
            if market:
                return market

        gamma_market_id = first_value(
            source_row,
            (
                "gamma_market_id",
                "gamma_id",
                "market_gamma_id",
            ),
        )

        if gamma_market_id not in (None, ""):
            market = self.data.get_market_by_gamma_id(
                str(gamma_market_id)
            )
            if market:
                return market

        return None

    def resolve_outcome(
        self,
        source_row: Mapping[str, Any],
    ) -> str:
        return normalize_outcome(
            first_value(
                source_row,
                (
                    "outcome",
                    "selected_outcome",
                    "side",
                    "position_outcome",
                ),
                "UNKNOWN",
            )
        )

    def build_snapshot(
        self,
        source_row: Mapping[str, Any],
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        identity = self.resolve_identity(source_row)

        if identity is None:
            condition_id = normalize_market_id(
                first_value(
                    source_row,
                    ("condition_id", "market_id"),
                )
            )
            raise LookupError(
                "No canonical identity found for "
                f"{condition_id or 'unknown market'}."
            )

        condition_id = normalize_market_id(
            identity.get("condition_id")
        )
        outcome = self.resolve_outcome(source_row)

        intelligence = self.data.get_market_intelligence(
            condition_id,
            None if outcome == "UNKNOWN" else outcome,
        )

        if not intelligence:
            intelligence = {
                "canonical": identity,
                "status": self.data.get_market_status(condition_id),
                "price_metrics": self.data.get_price_metrics(condition_id),
                "opportunity": dict(source_row),
                "institutional_consensus": (
                    self.data.get_institutional_consensus(
                        condition_id,
                        None if outcome == "UNKNOWN" else outcome,
                    )
                ),
                "position_evolution": (
                    self.data.get_position_evolution(
                        condition_id,
                        None if outcome == "UNKNOWN" else outcome,
                    )
                ),
                "closing_line_metrics": (
                    self.data.get_closing_line_metrics(
                        condition_id,
                        None if outcome == "UNKNOWN" else outcome,
                    )
                ),
                "positions": self.data.get_positions(condition_id),
                "consensus_history": (
                    self.data.get_consensus_history(
                        condition_id,
                        None if outcome == "UNKNOWN" else outcome,
                    )
                ),
                "alerts": self.data.get_alerts(
                    condition_id=condition_id
                ),
            }

        opportunity = intelligence.get("opportunity")
        if not isinstance(opportunity, Mapping) or not opportunity:
            intelligence["opportunity"] = dict(source_row)
        else:
            merged_opportunity = dict(source_row)
            merged_opportunity.update(dict(opportunity))
            intelligence["opportunity"] = merged_opportunity

        intelligence["canonical"] = identity
        intelligence["condition_id"] = condition_id
        intelligence["outcome"] = outcome
        intelligence["built_at"] = utc_now_iso()
        intelligence["source_updated_at"] = first_value(
            source_row,
            (
                "updated_at",
                "calculated_at",
                "ranked_at",
                "created_at",
            ),
        )
        intelligence["run_id"] = run_id

        self.validate_snapshot(intelligence)

        return intelligence

    def validate_snapshot(
        self,
        snapshot: Mapping[str, Any],
    ) -> None:
        condition_id = normalize_market_id(
            snapshot.get("condition_id")
        )
        canonical = snapshot.get("canonical")

        if not condition_id:
            raise ValueError("Snapshot is missing condition_id.")

        if not isinstance(canonical, Mapping):
            raise ValueError(
                "Snapshot is missing canonical identity data."
            )

        canonical_condition_id = normalize_market_id(
            canonical.get("condition_id")
        )

        if canonical_condition_id != condition_id:
            raise ValueError(
                "Snapshot condition_id does not match canonical identity."
            )

    def build_one(
        self,
        condition_id: str,
        *,
        outcome: str = "UNKNOWN",
        save_history: bool = True,
    ) -> dict[str, Any]:
        market_id = normalize_market_id(condition_id)
        identity = self.data.get_market(market_id)

        if identity is None:
            raise LookupError(
                f"Canonical market not found: {condition_id}"
            )

        source_row: dict[str, Any] = {
            "condition_id": market_id,
            "outcome": normalize_outcome(outcome),
        }

        opportunity = self.data.get_opportunity(
            market_id,
            None if outcome == "UNKNOWN" else outcome,
        )
        if opportunity:
            source_row.update(opportunity)

        run_id = self.repository.create_run(
            mode="single",
            source_markets=1,
            details={
                "condition_id": market_id,
                "outcome": normalize_outcome(outcome),
            },
        )

        started = time.perf_counter()

        try:
            snapshot = self.build_snapshot(
                source_row,
                run_id=run_id,
            )
            action = self.repository.save_snapshot(
                snapshot,
                run_id=run_id,
                save_history=save_history,
            )

            elapsed = time.perf_counter() - started

            self.repository.finish_run(
                run_id,
                success=True,
                processed_rows=1,
                inserted_rows=1 if action == "inserted" else 0,
                updated_rows=1 if action == "updated" else 0,
                history_rows=1 if save_history else 0,
                details={
                    "duration_seconds_precise": elapsed,
                },
            )

            return {
                "run_id": run_id,
                "action": action,
                "snapshot": snapshot,
            }

        except Exception as error:
            self.repository.finish_run(
                run_id,
                success=False,
                processed_rows=1,
                error_count=1,
                error_message=str(error),
            )
            raise

    def build_all(
        self,
        *,
        mode: str = "focused",
        limit: int | None = None,
        minimum_master_score: float | None = None,
        save_history: bool = True,
        continue_on_error: bool = True,
    ) -> BuildSummary:
        source_rows = self.load_source_rows(
            mode=mode,
            limit=limit,
            minimum_master_score=minimum_master_score,
        )

        summary = BuildSummary(
            mode=mode,
            source_markets=len(source_rows),
        )

        summary.run_id = self.repository.create_run(
            mode=mode,
            source_markets=len(source_rows),
            details={
                "limit": limit,
                "minimum_master_score": minimum_master_score,
                "save_history": save_history,
            },
        )

        started = time.perf_counter()

        try:
            for source_row in source_rows:
                summary.processed_rows += 1

                condition_id = normalize_market_id(
                    first_value(
                        source_row,
                        ("condition_id", "market_id"),
                    )
                )
                outcome = self.resolve_outcome(source_row)

                try:
                    snapshot = self.build_snapshot(
                        source_row,
                        run_id=summary.run_id,
                    )

                    action = self.repository.save_snapshot(
                        snapshot,
                        run_id=summary.run_id,
                        save_history=save_history,
                    )

                    summary.built_rows += 1
                    if action == "inserted":
                        summary.inserted_rows += 1
                    else:
                        summary.updated_rows += 1

                    if save_history:
                        summary.history_rows += 1

                except LookupError as error:
                    summary.unmatched_rows += 1
                    summary.error_count += 1
                    summary.errors.append(
                        BuildError(
                            condition_id=condition_id,
                            outcome=outcome,
                            error=str(error),
                        )
                    )
                    LOGGER.warning(
                        "Unmatched dashboard source row: %s | %s",
                        condition_id or "UNKNOWN",
                        outcome,
                    )
                    if not continue_on_error:
                        raise

                except Exception as error:
                    summary.error_count += 1
                    summary.errors.append(
                        BuildError(
                            condition_id=condition_id,
                            outcome=outcome,
                            error=str(error),
                        )
                    )
                    LOGGER.exception(
                        "Dashboard build failed for %s | %s",
                        condition_id or "UNKNOWN",
                        outcome,
                    )
                    if not continue_on_error:
                        raise

            summary.finished_at = utc_now_iso()
            summary.duration_seconds = (
                time.perf_counter() - started
            )

            self.repository.finish_run(
                summary.run_id,
                success=summary.success,
                processed_rows=summary.processed_rows,
                inserted_rows=summary.inserted_rows,
                updated_rows=summary.updated_rows,
                history_rows=summary.history_rows,
                skipped_rows=summary.skipped_rows,
                unmatched_rows=summary.unmatched_rows,
                error_count=summary.error_count,
                error_message=(
                    None
                    if summary.success
                    else (
                        f"{summary.error_count} row(s) failed "
                        "during dashboard build."
                    )
                ),
                details={
                    "built_rows": summary.built_rows,
                    "duration_seconds_precise": (
                        summary.duration_seconds
                    ),
                    "errors": [
                        {
                            "condition_id": item.condition_id,
                            "outcome": item.outcome,
                            "error": item.error,
                        }
                        for item in summary.errors[:100]
                    ],
                },
            )

            return summary

        except Exception as error:
            summary.finished_at = utc_now_iso()
            summary.duration_seconds = (
                time.perf_counter() - started
            )

            self.repository.finish_run(
                summary.run_id,
                success=False,
                processed_rows=summary.processed_rows,
                inserted_rows=summary.inserted_rows,
                updated_rows=summary.updated_rows,
                history_rows=summary.history_rows,
                skipped_rows=summary.skipped_rows,
                unmatched_rows=summary.unmatched_rows,
                error_count=max(1, summary.error_count),
                error_message=str(error),
                details={
                    "built_rows": summary.built_rows,
                    "duration_seconds_precise": (
                        summary.duration_seconds
                    ),
                },
            )
            raise

    def summarize(self, summary: BuildSummary) -> None:
        print()
        print("=" * 108)
        print("MASTER INTELLIGENCE DASHBOARD BUILDER")
        print("=" * 108)
        print(f"Mode:                 {summary.mode}")
        print(f"Run ID:               {summary.run_id}")
        print(f"Source rows:          {summary.source_markets}")
        print(f"Processed:            {summary.processed_rows}")
        print(f"Built:                {summary.built_rows}")
        print(f"Inserted:             {summary.inserted_rows}")
        print(f"Updated:              {summary.updated_rows}")
        print(f"History rows:         {summary.history_rows}")
        print(f"Skipped:              {summary.skipped_rows}")
        print(f"Unmatched:            {summary.unmatched_rows}")
        print(f"Errors:               {summary.error_count}")
        print(
            f"Duration:             "
            f"{summary.duration_seconds:.3f} seconds"
        )
        print(
            f"Status:               "
            f"{'SUCCESS' if summary.success else 'COMPLETED WITH ERRORS'}"
        )

        if summary.errors:
            print()
            print("ERROR PREVIEW")
            print("-" * 108)
            for item in summary.errors[:10]:
                print(
                    f"{item.condition_id or 'UNKNOWN'} | "
                    f"{item.outcome} | {item.error}"
                )

        print("=" * 108)


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Polymarket Master Intelligence Dashboard."
        )
    )

    parser.add_argument(
        "--mode",
        choices=("focused", "full"),
        default="focused",
        help=(
            "focused uses master_opportunities; "
            "full uses every tradable canonical market."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of source rows.",
    )
    parser.add_argument(
        "--minimum-master-score",
        type=float,
        default=None,
        help=(
            "Focused mode only: minimum master opportunity score."
        ),
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Do not append dashboard history snapshots.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately on the first row error.",
    )
    parser.add_argument(
        "--condition-id",
        default=None,
        help="Build one specific canonical market.",
    )
    parser.add_argument(
        "--outcome",
        default="UNKNOWN",
        help="Outcome for single-market mode.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    builder = MasterIntelligenceDashboardBuilder()

    if args.condition_id:
        result = builder.build_one(
            args.condition_id,
            outcome=args.outcome,
            save_history=not args.no_history,
        )

        print()
        print("=" * 108)
        print("MASTER INTELLIGENCE DASHBOARD BUILDER")
        print("=" * 108)
        print(f"Run ID:     {result['run_id']}")
        print(f"Action:     {result['action']}")
        print(
            f"Market:     "
            f"{result['snapshot']['condition_id']}"
        )
        print(
            f"Outcome:    "
            f"{result['snapshot']['outcome']}"
        )
        print("Status:     SUCCESS")
        print("=" * 108)
        return

    summary = builder.build_all(
        mode=args.mode,
        limit=args.limit,
        minimum_master_score=args.minimum_master_score,
        save_history=not args.no_history,
        continue_on_error=not args.fail_fast,
    )
    builder.summarize(summary)


if __name__ == "__main__":
    main()