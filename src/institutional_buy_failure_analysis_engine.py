
from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
import sqlite3
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENGINE_VERSION = "1.0"

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

DEFAULT_DATABASE = (
    ROOT
    / "database"
    / "polymarket.db"
)

DEFAULT_REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "buy_failure_analysis"
)

BUY_FIELDS = (
    "score",
    "actionability",
    "confidence",
    "entry",
    "structure",
    "trust",
    "wallet_count",
    "data_quality",
)


COLUMN_ALIASES: dict[
    str,
    tuple[str, ...],
] = {
    "decision_id": (
        "decision_id",
        "id",
        "observation_id",
    ),
    "run_id": (
        "run_id",
        "decision_run_id",
        "source_run_id",
    ),
    "market_id": (
        "market_id",
        "condition_id",
        "token_id",
        "slug",
    ),
    "title": (
        "title",
        "market_title",
        "question",
        "market_question",
    ),
    "market_type": (
        "market_type",
        "category",
        "market_category",
        "profile_name",
        "decision_profile",
    ),
    "decision_action": (
        "decision_action",
        "action",
        "recommendation",
        "final_action",
    ),
    "score": (
        "score",
        "decision_score",
        "institutional_score",
        "master_score",
        "composite_score",
    ),
    "actionability": (
        "actionability",
        "actionability_score",
    ),
    "confidence": (
        "confidence",
        "confidence_score",
        "decision_confidence",
    ),
    "entry": (
        "entry",
        "entry_score",
        "entry_quality",
        "entry_quality_score",
    ),
    "structure": (
        "structure",
        "structure_score",
        "market_structure",
        "market_structure_score",
    ),
    "trust": (
        "trust",
        "trust_score",
        "wallet_trust",
        "wallet_trust_score",
    ),
    "wallet_count": (
        "wallet_count",
        "matching_wallets",
        "agreeing_wallets",
        "consensus_wallet_count",
    ),
    "data_quality": (
        "data_quality",
        "data_quality_score",
        "quality_score",
    ),
    "hard_veto": (
        "hard_veto",
        "veto",
        "is_vetoed",
        "veto_flag",
    ),
    "created_at": (
        "created_at",
        "decision_at",
        "scanned_at",
        "observed_at",
        "timestamp",
    ),
}


@dataclass(frozen=True)
class ThresholdSet:
    profile_name: str

    buy_score: float
    buy_actionability: float
    buy_confidence: float
    buy_entry: float
    buy_structure: float
    buy_trust: float
    buy_wallet_count: int
    buy_data_quality: float

    def requirements(
        self,
    ) -> dict[str, float]:
        return {
            "score": self.buy_score,
            "actionability": (
                self.buy_actionability
            ),
            "confidence": (
                self.buy_confidence
            ),
            "entry": self.buy_entry,
            "structure": (
                self.buy_structure
            ),
            "trust": self.buy_trust,
            "wallet_count": float(
                self.buy_wallet_count
            ),
            "data_quality": (
                self.buy_data_quality
            ),
        }


@dataclass
class DecisionAnalysis:
    source_table: str

    decision_id: str
    run_id: str
    market_id: str
    title: str
    market_type: str

    profile_name: str
    current_action: str
    hard_veto: bool

    score: float | None
    actionability: float | None
    confidence: float | None
    entry: float | None
    structure: float | None
    trust: float | None
    wallet_count: float | None
    data_quality: float | None

    score_required: float
    actionability_required: float
    confidence_required: float
    entry_required: float
    structure_required: float
    trust_required: float
    wallet_count_required: float
    data_quality_required: float

    buy_failed_count: int
    buy_passed_count: int

    buy_ready: bool
    near_buy: bool

    primary_blocker: str
    primary_gap: float | None
    primary_gap_pct: float | None

    secondary_blocker: str
    secondary_gap: float | None
    secondary_gap_pct: float | None

    failed_fields: str
    passed_fields: str
    missing_fields: str

    created_at: str


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def clean_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def safe_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(number):
        return None

    return number


def safe_bool(
    value: Any,
) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(
        value,
        (int, float),
    ):
        return bool(value)

    return (
        clean_text(value).lower()
        in {
            "1",
            "true",
            "yes",
            "y",
            "veto",
            "blocked",
        }
    )


def quote_identifier(
    identifier: str,
) -> str:
    return (
        '"'
        + identifier.replace(
            '"',
            '""',
        )
        + '"'
    )


def connect(
    database_path: Path,
) -> sqlite3.Connection:
    connection = sqlite3.connect(
        str(database_path)
    )

    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA query_only = ON"
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def list_tables(
    connection: sqlite3.Connection,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    return [
        clean_text(row["name"])
        for row in rows
    ]


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[str]:
    rows = connection.execute(
        f"""
        PRAGMA table_info(
            {quote_identifier(table_name)}
        )
        """
    ).fetchall()

    return [
        clean_text(row["name"])
        for row in rows
    ]


def resolve_columns(
    columns: list[str],
) -> dict[str, str]:
    actual_columns = {
        column.lower(): column
        for column in columns
    }

    resolved: dict[str, str] = {}

    for (
        logical_name,
        aliases,
    ) in COLUMN_ALIASES.items():
        for alias in aliases:
            actual = actual_columns.get(
                alias.lower()
            )

            if actual:
                resolved[
                    logical_name
                ] = actual

                break

    return resolved


def score_candidate_table(
    table_name: str,
    resolved: dict[str, str],
) -> int:
    score = 0

    table_lower = (
        table_name.lower()
    )

    if "decision" in table_lower:
        score += 20

    if "history" in table_lower:
        score += 5

    if "institutional" in table_lower:
        score += 5

    for field in BUY_FIELDS:
        if field in resolved:
            score += 10

    if "decision_action" in resolved:
        score += 20

    if "title" in resolved:
        score += 5

    if "market_id" in resolved:
        score += 5

    if "run_id" in resolved:
        score += 3

    if "created_at" in resolved:
        score += 2

    return score


def discover_decision_table(
    connection: sqlite3.Connection,
    requested_table: str | None,
) -> tuple[
    str,
    dict[str, str],
    list[tuple[str, int]],
]:
    tables = list_tables(
        connection
    )

    if requested_table:
        if requested_table not in tables:
            raise RuntimeError(
                "Requested table does not "
                f"exist: {requested_table}"
            )

        columns = table_columns(
            connection,
            requested_table,
        )

        resolved = resolve_columns(
            columns
        )

        missing = [
            field
            for field in BUY_FIELDS
            if field not in resolved
        ]

        if missing:
            raise RuntimeError(
                "Requested table is missing "
                "BUY score columns: "
                + ", ".join(missing)
            )

        return (
            requested_table,
            resolved,
            [
                (
                    requested_table,
                    999,
                )
            ],
        )

    candidates: list[
        tuple[
            int,
            str,
            dict[str, str],
        ]
    ] = []

    for table_name in tables:
        columns = table_columns(
            connection,
            table_name,
        )

        resolved = resolve_columns(
            columns
        )

        if not all(
            field in resolved
            for field in BUY_FIELDS
        ):
            continue

        candidate_score = (
            score_candidate_table(
                table_name,
                resolved,
            )
        )

        candidates.append(
            (
                candidate_score,
                table_name,
                resolved,
            )
        )

    if not candidates:
        raise RuntimeError(
            "No database table contains "
            "all required BUY fields: "
            + ", ".join(BUY_FIELDS)
        )

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    ranking = [
        (
            table_name,
            candidate_score,
        )
        for (
            candidate_score,
            table_name,
            _,
        ) in candidates
    ]

    (
        _,
        best_table,
        best_resolved,
    ) = candidates[0]

    return (
        best_table,
        best_resolved,
        ranking,
    )


def load_config_module() -> Any:
    if str(SRC) not in sys.path:
        sys.path.insert(
            0,
            str(SRC),
        )

    module_names = (
        "decision_engine_config",
    )

    errors: list[str] = []

    for module_name in module_names:
        try:
            return (
                importlib.import_module(
                    module_name
                )
            )

        except Exception as error:
            errors.append(
                f"{module_name}: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    raise RuntimeError(
        "Unable to load decision "
        "configuration.\n"
        + "\n".join(errors)
    )


def threshold_from_object(
    profile_name: str,
    threshold_object: Any,
) -> ThresholdSet:
    return ThresholdSet(
        profile_name=profile_name,
        buy_score=float(
            threshold_object.buy_score
        ),
        buy_actionability=float(
            threshold_object
            .buy_actionability
        ),
        buy_confidence=float(
            threshold_object
            .buy_confidence
        ),
        buy_entry=float(
            threshold_object.buy_entry
        ),
        buy_structure=float(
            threshold_object
            .buy_structure
        ),
        buy_trust=float(
            threshold_object.buy_trust
        ),
        buy_wallet_count=int(
            threshold_object
            .buy_wallet_count
        ),
        buy_data_quality=float(
            threshold_object
            .buy_data_quality
        ),
    )


def load_profiles(
    config_module: Any,
) -> tuple[
    dict[str, ThresholdSet],
    Any,
]:
    raw_profiles = getattr(
        config_module,
        "PROFILES",
        None,
    )

    if not isinstance(
        raw_profiles,
        dict,
    ):
        raise RuntimeError(
            "decision_engine_config.py "
            "does not expose PROFILES."
        )

    profiles: dict[
        str,
        ThresholdSet,
    ] = {}

    for (
        profile_key,
        profile_object,
    ) in raw_profiles.items():
        profile_name = clean_text(
            getattr(
                profile_object,
                "name",
                profile_key,
            )
        ).upper()

        threshold_object = getattr(
            profile_object,
            "thresholds",
            None,
        )

        if threshold_object is None:
            continue

        profiles[
            profile_name
        ] = threshold_from_object(
            profile_name,
            threshold_object,
        )

    if "DEFAULT" not in profiles:
        raise RuntimeError(
            "DEFAULT threshold profile "
            "was not found."
        )

    infer_function = getattr(
        config_module,
        "infer_profile_name",
        None,
    )

    return (
        profiles,
        infer_function,
    )


def infer_profile(
    market_type: str,
    title: str,
    profiles: dict[
        str,
        ThresholdSet,
    ],
    infer_function: Any,
) -> ThresholdSet:
    profile_name = "DEFAULT"

    if callable(infer_function):
        try:
            inferred = infer_function(
                market_type,
                title,
            )

            inferred_name = clean_text(
                inferred
            ).upper()

            if inferred_name in profiles:
                profile_name = (
                    inferred_name
                )

        except Exception:
            profile_name = "DEFAULT"

    else:
        combined = (
            f"{market_type} {title}"
            .lower()
        )

        fallback_terms = {
            "SPORTS": (
                "sport",
                "soccer",
                "football",
                "basketball",
                "baseball",
                "hockey",
                "tennis",
                "ufc",
                "nba",
                "nfl",
                "nhl",
                "mlb",
                "world cup",
            ),
            "POLITICS": (
                "election",
                "president",
                "senate",
                "congress",
                "politic",
                "nominee",
            ),
            "CRYPTO": (
                "bitcoin",
                "ethereum",
                "crypto",
                "btc",
                "eth",
            ),
            "MACRO": (
                "fed",
                "interest rate",
                "inflation",
                "cpi",
                "gdp",
                "recession",
            ),
        }

        for (
            candidate,
            terms,
        ) in fallback_terms.items():
            if candidate not in profiles:
                continue

            if any(
                term in combined
                for term in terms
            ):
                profile_name = candidate
                break

    return profiles.get(
        profile_name,
        profiles["DEFAULT"],
    )


def build_select_parts(
    resolved: dict[str, str],
) -> list[str]:
    parts: list[str] = []

    for logical_name in (
        "decision_id",
        "run_id",
        "market_id",
        "title",
        "market_type",
        "decision_action",
        *BUY_FIELDS,
        "hard_veto",
        "created_at",
    ):
        actual_name = resolved.get(
            logical_name
        )

        if actual_name:
            parts.append(
                f"{quote_identifier(actual_name)} "
                f"AS {quote_identifier(logical_name)}"
            )

        else:
            parts.append(
                f"NULL AS "
                f"{quote_identifier(logical_name)}"
            )

    return parts


def find_latest_run_id(
    connection: sqlite3.Connection,
    table_name: str,
    resolved: dict[str, str],
) -> Any:
    if "run_id" not in resolved:
        return None

    run_column = quote_identifier(
        resolved["run_id"]
    )

    if "created_at" in resolved:
        order_expression = (
            quote_identifier(
                resolved["created_at"]
            )
        )

    else:
        order_expression = "rowid"

    row = connection.execute(
        f"""
        SELECT
            {run_column} AS run_id
        FROM
            {quote_identifier(table_name)}
        WHERE
            {run_column} IS NOT NULL
            AND TRIM(
                CAST(
                    {run_column}
                    AS TEXT
                )
            ) <> ''
        ORDER BY
            {order_expression} DESC,
            rowid DESC
        LIMIT 1
        """
    ).fetchone()

    if row is None:
        return None

    return row["run_id"]


def select_rows(
    connection: sqlite3.Connection,
    table_name: str,
    resolved: dict[str, str],
    latest_run_only: bool,
    row_limit: int,
) -> tuple[
    list[sqlite3.Row],
    Any,
]:
    select_parts = (
        build_select_parts(
            resolved
        )
    )

    parameters: list[Any] = []
    where_clause = ""

    latest_run_id = None

    if latest_run_only:
        latest_run_id = (
            find_latest_run_id(
                connection,
                table_name,
                resolved,
            )
        )

        if latest_run_id is not None:
            run_column = (
                quote_identifier(
                    resolved["run_id"]
                )
            )

            where_clause = (
                f"WHERE {run_column} = ?"
            )

            parameters.append(
                latest_run_id
            )

    if "created_at" in resolved:
        order_clause = (
            "ORDER BY "
            f"{quote_identifier(resolved['created_at'])} "
            "DESC, rowid DESC"
        )

    else:
        order_clause = (
            "ORDER BY rowid DESC"
        )

    limit_clause = ""

    if row_limit > 0:
        limit_clause = "LIMIT ?"

        parameters.append(
            row_limit
        )

    query = f"""
        SELECT
            {", ".join(select_parts)}
        FROM
            {quote_identifier(table_name)}
        {where_clause}
        {order_clause}
        {limit_clause}
    """

    rows = connection.execute(
        query,
        parameters,
    ).fetchall()

    return (
        rows,
        latest_run_id,
    )


def calculate_gap(
    value: float | None,
    required: float,
) -> tuple[
    bool,
    float | None,
    float | None,
]:
    if value is None:
        return (
            False,
            None,
            100.0,
        )

    if value >= required:
        return (
            True,
            0.0,
            0.0,
        )

    gap = required - value

    if required > 0:
        gap_pct = (
            gap
            / required
            * 100.0
        )

    else:
        gap_pct = gap

    return (
        False,
        gap,
        gap_pct,
    )


def analyze_row(
    row: sqlite3.Row,
    source_table: str,
    profiles: dict[
        str,
        ThresholdSet,
    ],
    infer_function: Any,
    near_buy_max_failed: int,
    near_buy_max_gap_pct: float,
) -> DecisionAnalysis:
    title = clean_text(
        row["title"]
    )

    market_type = clean_text(
        row["market_type"]
    )

    thresholds = infer_profile(
        market_type,
        title,
        profiles,
        infer_function,
    )

    requirements = (
        thresholds.requirements()
    )

    values = {
        field: safe_float(
            row[field]
        )
        for field in BUY_FIELDS
    }

    passed_fields: list[str] = []
    failed_fields: list[str] = []
    missing_fields: list[str] = []

    blockers: list[
        tuple[
            float,
            float | None,
            str,
        ]
    ] = []

    for field in BUY_FIELDS:
        value = values[field]
        required = requirements[field]

        (
            passed,
            gap,
            gap_pct,
        ) = calculate_gap(
            value,
            required,
        )

        if passed:
            passed_fields.append(
                field
            )

            continue

        failed_fields.append(
            field
        )

        if value is None:
            missing_fields.append(
                field
            )

        blockers.append(
            (
                gap_pct
                if gap_pct is not None
                else 100.0,
                gap,
                field,
            )
        )

    blockers.sort(
        key=lambda item: (
            item[0],
            item[2],
        ),
        reverse=True,
    )

    primary_blocker = ""
    primary_gap = None
    primary_gap_pct = None

    secondary_blocker = ""
    secondary_gap = None
    secondary_gap_pct = None

    if blockers:
        (
            primary_gap_pct,
            primary_gap,
            primary_blocker,
        ) = blockers[0]

    if len(blockers) > 1:
        (
            secondary_gap_pct,
            secondary_gap,
            secondary_blocker,
        ) = blockers[1]

    hard_veto = safe_bool(
        row["hard_veto"]
    )

    buy_ready = (
        not hard_veto
        and not failed_fields
    )

    maximum_gap_pct = max(
        (
            blocker[0]
            for blocker in blockers
        ),
        default=0.0,
    )

    near_buy = (
        not hard_veto
        and not buy_ready
        and len(failed_fields)
        <= near_buy_max_failed
        and maximum_gap_pct
        <= near_buy_max_gap_pct
    )

    return DecisionAnalysis(
        source_table=source_table,

        decision_id=clean_text(
            row["decision_id"]
        ),
        run_id=clean_text(
            row["run_id"]
        ),
        market_id=clean_text(
            row["market_id"]
        ),
        title=title,
        market_type=market_type,

        profile_name=(
            thresholds.profile_name
        ),
        current_action=clean_text(
            row["decision_action"]
        ).upper(),
        hard_veto=hard_veto,

        score=values["score"],
        actionability=(
            values["actionability"]
        ),
        confidence=values[
            "confidence"
        ],
        entry=values["entry"],
        structure=values[
            "structure"
        ],
        trust=values["trust"],
        wallet_count=values[
            "wallet_count"
        ],
        data_quality=values[
            "data_quality"
        ],

        score_required=(
            requirements["score"]
        ),
        actionability_required=(
            requirements[
                "actionability"
            ]
        ),
        confidence_required=(
            requirements["confidence"]
        ),
        entry_required=(
            requirements["entry"]
        ),
        structure_required=(
            requirements["structure"]
        ),
        trust_required=(
            requirements["trust"]
        ),
        wallet_count_required=(
            requirements["wallet_count"]
        ),
        data_quality_required=(
            requirements[
                "data_quality"
            ]
        ),

        buy_failed_count=len(
            failed_fields
        ),
        buy_passed_count=len(
            passed_fields
        ),

        buy_ready=buy_ready,
        near_buy=near_buy,

        primary_blocker=(
            primary_blocker
        ),
        primary_gap=primary_gap,
        primary_gap_pct=(
            primary_gap_pct
        ),

        secondary_blocker=(
            secondary_blocker
        ),
        secondary_gap=(
            secondary_gap
        ),
        secondary_gap_pct=(
            secondary_gap_pct
        ),

        failed_fields="|".join(
            failed_fields
        ),
        passed_fields="|".join(
            passed_fields
        ),
        missing_fields="|".join(
            missing_fields
        ),

        created_at=clean_text(
            row["created_at"]
        ),
    )


def build_summary(
    analyses: list[
        DecisionAnalysis
    ],
) -> dict[str, Any]:
    primary_blockers = Counter()
    secondary_blockers = Counter()
    all_failed_fields = Counter()

    action_counts = Counter()
    profile_counts = Counter()

    buy_ready_by_profile = Counter()
    near_buy_by_profile = Counter()

    for analysis in analyses:
        action_counts[
            analysis.current_action
            or "UNKNOWN"
        ] += 1

        profile_counts[
            analysis.profile_name
        ] += 1

        if analysis.primary_blocker:
            primary_blockers[
                analysis.primary_blocker
            ] += 1

        if analysis.secondary_blocker:
            secondary_blockers[
                analysis.secondary_blocker
            ] += 1

        for field in (
            analysis.failed_fields
            .split("|")
        ):
            if field:
                all_failed_fields[
                    field
                ] += 1

        if analysis.buy_ready:
            buy_ready_by_profile[
                analysis.profile_name
            ] += 1

        if analysis.near_buy:
            near_buy_by_profile[
                analysis.profile_name
            ] += 1

    return {
        "engine_version": (
            ENGINE_VERSION
        ),
        "generated_at": (
            utc_now().isoformat(
                timespec="seconds"
            )
        ),
        "decisions_analyzed": len(
            analyses
        ),
        "buy_ready_count": sum(
            analysis.buy_ready
            for analysis in analyses
        ),
        "near_buy_count": sum(
            analysis.near_buy
            for analysis in analyses
        ),
        "hard_veto_count": sum(
            analysis.hard_veto
            for analysis in analyses
        ),
        "primary_blocker_counts": dict(
            primary_blockers
            .most_common()
        ),
        "secondary_blocker_counts": dict(
            secondary_blockers
            .most_common()
        ),
        "all_failed_requirement_counts": dict(
            all_failed_fields
            .most_common()
        ),
        "action_counts": dict(
            action_counts.most_common()
        ),
        "profile_counts": dict(
            profile_counts.most_common()
        ),
        "buy_ready_by_profile": dict(
            buy_ready_by_profile
            .most_common()
        ),
        "near_buy_by_profile": dict(
            near_buy_by_profile
            .most_common()
        ),
    }


def write_csv_report(
    path: Path,
    analyses: list[
        DecisionAnalysis
    ],
) -> None:
    field_names = list(
        DecisionAnalysis
        .__dataclass_fields__
        .keys()
    )

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=field_names,
        )

        writer.writeheader()

        for analysis in analyses:
            writer.writerow(
                asdict(analysis)
            )


def write_json_report(
    path: Path,
    metadata: dict[str, Any],
    summary: dict[str, Any],
    analyses: list[
        DecisionAnalysis
    ],
) -> None:
    payload = {
        "metadata": metadata,
        "summary": summary,
        "decisions": [
            asdict(analysis)
            for analysis in analyses
        ],
    }

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def format_count_section(
    title: str,
    values: dict[str, int],
    total: int,
) -> list[str]:
    lines = [
        title,
        "-" * 110,
    ]

    if not values:
        lines.extend(
            [
                "No results.",
                "",
            ]
        )

        return lines

    for (
        name,
        count,
    ) in values.items():
        percentage = (
            count
            / total
            * 100.0
            if total > 0
            else 0.0
        )

        lines.append(
            f"{name:<28} "
            f"{count:>8,} "
            f"({percentage:>6.2f}%)"
        )

    lines.append("")

    return lines


def write_text_report(
    path: Path,
    metadata: dict[str, Any],
    summary: dict[str, Any],
    analyses: list[
        DecisionAnalysis
    ],
    top_limit: int,
) -> None:
    lines: list[str] = [
        "=" * 110,
        "INSTITUTIONAL BUY FAILURE ANALYSIS",
        "=" * 110,
        (
            "Engine version:          "
            f"{ENGINE_VERSION}"
        ),
        (
            "Generated at:            "
            f"{summary['generated_at']}"
        ),
        (
            "Database:                "
            f"{metadata['database_path']}"
        ),
        (
            "Decision table:          "
            f"{metadata['source_table']}"
        ),
        (
            "Latest run only:         "
            f"{metadata['latest_run_only']}"
        ),
        (
            "Latest run ID:           "
            f"{metadata['latest_run_id']}"
        ),
        (
            "Decisions analyzed:      "
            f"{summary['decisions_analyzed']:,}"
        ),
        (
            "BUY-ready decisions:     "
            f"{summary['buy_ready_count']:,}"
        ),
        (
            "Near-BUY decisions:      "
            f"{summary['near_buy_count']:,}"
        ),
        (
            "Hard vetoes:              "
            f"{summary['hard_veto_count']:,}"
        ),
        "",
    ]

    lines.extend(
        format_count_section(
            "PRIMARY BUY BLOCKERS",
            summary[
                "primary_blocker_counts"
            ],
            summary[
                "decisions_analyzed"
            ],
        )
    )

    lines.extend(
        format_count_section(
            "SECONDARY BUY BLOCKERS",
            summary[
                "secondary_blocker_counts"
            ],
            summary[
                "decisions_analyzed"
            ],
        )
    )

    lines.extend(
        format_count_section(
            "ALL FAILED BUY REQUIREMENTS",
            summary[
                "all_failed_requirement_counts"
            ],
            summary[
                "decisions_analyzed"
            ],
        )
    )

    lines.extend(
        format_count_section(
            "CURRENT DECISION ACTIONS",
            summary["action_counts"],
            summary[
                "decisions_analyzed"
            ],
        )
    )

    lines.extend(
        format_count_section(
            "PROFILE DISTRIBUTION",
            summary["profile_counts"],
            summary[
                "decisions_analyzed"
            ],
        )
    )

    near_buy_rows = sorted(
        (
            analysis
            for analysis in analyses
            if analysis.near_buy
        ),
        key=lambda analysis: (
            analysis.buy_failed_count,
            (
                analysis.primary_gap_pct
                if (
                    analysis
                    .primary_gap_pct
                    is not None
                )
                else 999.0
            ),
            analysis.title,
        ),
    )

    lines.extend(
        [
            "TOP NEAR-BUY DECISIONS",
            "-" * 110,
        ]
    )

    if not near_buy_rows:
        lines.append(
            "No decisions satisfied "
            "the near-BUY proximity rules."
        )

    else:
        for (
            number,
            analysis,
        ) in enumerate(
            near_buy_rows[
                :top_limit
            ],
            start=1,
        ):
            display_name = (
                analysis.title
                or analysis.market_id
                or "<untitled market>"
            )

            lines.extend(
                [
                    (
                        f"[{number}] "
                        f"{display_name}"
                    ),
                    (
                        "    Profile:          "
                        f"{analysis.profile_name}"
                    ),
                    (
                        "    Current action:   "
                        f"{analysis.current_action}"
                    ),
                    (
                        "    Failed count:     "
                        f"{analysis.buy_failed_count}"
                    ),
                    (
                        "    Primary blocker:  "
                        f"{analysis.primary_blocker}"
                    ),
                    (
                        "    Primary gap:      "
                        f"{analysis.primary_gap}"
                    ),
                    (
                        "    Primary gap %:    "
                        f"{analysis.primary_gap_pct}"
                    ),
                    (
                        "    Secondary block:  "
                        f"{analysis.secondary_blocker}"
                    ),
                    (
                        "    Failed fields:    "
                        f"{analysis.failed_fields}"
                    ),
                    "",
                ]
            )

    lines.extend(
        [
            "=" * 110,
            "Source database modified:       NO",
            "Decision thresholds modified:   NO",
            "Decision actions modified:      NO",
            "Analysis reports saved:         YES",
            "=" * 110,
        ]
    )

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def print_summary(
    summary: dict[str, Any],
    metadata: dict[str, Any],
    report_paths: dict[
        str,
        Path,
    ],
) -> None:
    print()
    print("=" * 120)
    print(
        "INSTITUTIONAL BUY "
        "FAILURE ANALYSIS"
    )
    print("=" * 120)

    print(
        f"Decision table:          "
        f"{metadata['source_table']}"
    )

    print(
        f"Latest run ID:           "
        f"{metadata['latest_run_id']}"
    )

    print(
        f"Decisions analyzed:      "
        f"{summary['decisions_analyzed']:,}"
    )

    print(
        f"BUY-ready decisions:     "
        f"{summary['buy_ready_count']:,}"
    )

    print(
        f"Near-BUY decisions:      "
        f"{summary['near_buy_count']:,}"
    )

    print(
        f"Hard vetoes:              "
        f"{summary['hard_veto_count']:,}"
    )

    print()
    print("TOP PRIMARY BLOCKERS")
    print("-" * 120)

    blockers = list(
        summary[
            "primary_blocker_counts"
        ].items()
    )

    if not blockers:
        print(
            "No BUY blockers detected."
        )

    else:
        for (
            blocker,
            count,
        ) in blockers[:10]:
            print(
                f"{blocker:<28} "
                f"{count:>8,}"
            )

    print()
    print("TABLE DISCOVERY")
    print("-" * 120)

    for (
        table_name,
        candidate_score,
    ) in metadata[
        "table_discovery_ranking"
    ][:10]:
        selected = (
            "SELECTED"
            if (
                table_name
                == metadata[
                    "source_table"
                ]
            )
            else ""
        )

        print(
            f"{table_name:<60} "
            f"score={candidate_score:<4} "
            f"{selected}"
        )

    print()
    print("SAVED REPORTS")
    print("-" * 120)

    for (
        report_type,
        report_path,
    ) in report_paths.items():
        print(
            f"{report_type:<12} "
            f"{report_path.resolve()}"
        )

    print()
    print(
        "Database modified:       NO"
    )
    print(
        "Thresholds modified:     NO"
    )
    print(
        "Actions modified:        NO"
    )
    print("=" * 120)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Automatically analyze why "
            "institutional decisions fail "
            "the configured BUY requirements "
            "and save timestamped reports."
        )
    )

    parser.add_argument(
        "--database",
        default=str(
            DEFAULT_DATABASE
        ),
        help=(
            "SQLite database path."
        ),
    )

    parser.add_argument(
        "--table",
        default=None,
        help=(
            "Optional decision table. "
            "When omitted, the engine "
            "discovers the best table."
        ),
    )

    parser.add_argument(
        "--report-directory",
        default=str(
            DEFAULT_REPORT_DIRECTORY
        ),
        help=(
            "Directory for saved reports."
        ),
    )

    parser.add_argument(
        "--latest-run-only",
        action=(
            argparse
            .BooleanOptionalAction
        ),
        default=True,
        help=(
            "Analyze the newest run only "
            "when run_id is available."
        ),
    )

    parser.add_argument(
        "--row-limit",
        type=int,
        default=0,
        help=(
            "Maximum rows to analyze. "
            "Use 0 for all selected rows."
        ),
    )

    parser.add_argument(
        "--near-buy-max-failed",
        type=int,
        default=2,
        help=(
            "Maximum failed BUY "
            "requirements for near-BUY."
        ),
    )

    parser.add_argument(
        "--near-buy-max-gap-pct",
        type=float,
        default=10.0,
        help=(
            "Maximum normalized gap "
            "percentage for near-BUY."
        ),
    )

    parser.add_argument(
        "--top-limit",
        type=int,
        default=25,
        help=(
            "Maximum near-BUY records "
            "in the text report."
        ),
    )

    args = parser.parse_args()

    database_path = Path(
        args.database
    ).resolve()

    report_directory = Path(
        args.report_directory
    ).resolve()

    if not database_path.exists():
        raise FileNotFoundError(
            "Database not found: "
            f"{database_path}"
        )

    report_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    config_module = (
        load_config_module()
    )

    (
        profiles,
        infer_function,
    ) = load_profiles(
        config_module
    )

    connection = connect(
        database_path
    )

    try:
        (
            source_table,
            resolved_columns,
            table_ranking,
        ) = discover_decision_table(
            connection,
            args.table,
        )

        (
            rows,
            latest_run_id,
        ) = select_rows(
            connection,
            source_table,
            resolved_columns,
            bool(
                args.latest_run_only
            ),
            max(
                0,
                args.row_limit,
            ),
        )

    finally:
        connection.close()

    analyses = [
        analyze_row(
            row=row,
            source_table=source_table,
            profiles=profiles,
            infer_function=(
                infer_function
            ),
            near_buy_max_failed=max(
                0,
                args.near_buy_max_failed,
            ),
            near_buy_max_gap_pct=max(
                0.0,
                args
                .near_buy_max_gap_pct,
            ),
        )
        for row in rows
    ]

    analyses.sort(
        key=lambda analysis: (
            not analysis.buy_ready,
            not analysis.near_buy,
            analysis.buy_failed_count,
            (
                analysis.primary_gap_pct
                if (
                    analysis
                    .primary_gap_pct
                    is not None
                )
                else 999.0
            ),
            analysis.title,
        )
    )

    summary = build_summary(
        analyses
    )

    timestamp = utc_now().strftime(
        "%Y%m%dT%H%M%SZ"
    )

    report_stem = (
        "institutional_buy_"
        "failure_analysis_"
        f"{timestamp}"
    )

    csv_path = (
        report_directory
        / f"{report_stem}.csv"
    )

    json_path = (
        report_directory
        / f"{report_stem}.json"
    )

    text_path = (
        report_directory
        / f"{report_stem}.txt"
    )

    latest_json_path = (
        report_directory
        / "latest.json"
    )

    latest_text_path = (
        report_directory
        / "latest.txt"
    )

    metadata = {
        "engine_version": (
            ENGINE_VERSION
        ),
        "database_path": str(
            database_path
        ),
        "source_table": (
            source_table
        ),
        "resolved_columns": (
            resolved_columns
        ),
        "latest_run_only": bool(
            args.latest_run_only
        ),
        "latest_run_id": (
            clean_text(
                latest_run_id
            )
        ),
        "row_limit": max(
            0,
            args.row_limit,
        ),
        "near_buy_max_failed": max(
            0,
            args.near_buy_max_failed,
        ),
        "near_buy_max_gap_pct": max(
            0.0,
            args
            .near_buy_max_gap_pct,
        ),
        "profiles_loaded": sorted(
            profiles.keys()
        ),
        "table_discovery_ranking": (
            table_ranking
        ),
    }

    write_csv_report(
        csv_path,
        analyses,
    )

    write_json_report(
        json_path,
        metadata,
        summary,
        analyses,
    )

    write_text_report(
        text_path,
        metadata,
        summary,
        analyses,
        max(
            0,
            args.top_limit,
        ),
    )

    latest_json_path.write_text(
        json_path.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    latest_text_path.write_text(
        text_path.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    report_paths = {
        "CSV": csv_path,
        "JSON": json_path,
        "TEXT": text_path,
        "LATEST": latest_text_path,
    }

    print_summary(
        summary,
        metadata,
        report_paths,
    )


if __name__ == "__main__":
    main()
