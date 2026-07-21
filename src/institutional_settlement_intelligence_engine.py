"""
===============================================================================

Institutional Settlement Intelligence Engine
Version: 2.0

Purpose
-------
Determine and record verified Polymarket settlement facts.

Authoritative hierarchy
-----------------------
1. Existing locally verified settlement records
2. Polymarket CLOB market data
3. Gamma metadata for supporting context only

Required verification
---------------------
- Exact condition ID
- Exact outcome name
- closed=true
- accepting_orders=false
- Exactly one outcome marked winner=true

Responsibilities
----------------
- Load eligible unresolved BUY and AVOID observations
- Verify official market settlement
- Record the official winning outcome
- Record whether the selected outcome won or lost
- Write settlement audit records
- Cache authoritative CLOB responses
- Quarantine conflicting or suspicious records
- Preserve unresolved markets without guessing

Strict safety boundaries
------------------------
This engine does not:

- Evaluate whether a BUY or AVOID recommendation was correct
- Modify actual_result
- Modify is_correct
- Calculate ROI
- Calculate prediction calibration
- Change model methodology
- Change wallet rankings
- Perform institutional learning
- Use title matching or fuzzy market matching

Default mode is DRY RUN.
Database writes require the --apply argument.

===============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import urllib.error
import urllib.request
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENGINE_VERSION = "2.0"

DATABASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "polymarket.db"
)

CLOB_MARKET_URL = (
    "https://clob.polymarket.com/markets/{condition_id}"
)

DEFAULT_LIMIT = 500
DEFAULT_DISPLAY_LIMIT = 50
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_REQUEST_DELAY_SECONDS = 0.10

MINIMUM_LOCAL_MATCH_CONFIDENCE = 0.999

RESOLVED_LOCAL_STATUSES = {
    "RESOLVED",
    "LIKELY_RESOLVED",
    "FINAL",
    "SETTLED",
    "COMPLETE",
}


# =============================================================================
# GENERIC HELPERS
# =============================================================================


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value)
        .strip()
        .casefold()
        .split()
    )


def normalize_status(value: Any) -> str:
    return (
        normalize_text(value)
        .upper()
        .replace(" ", "_")
    )


def to_int(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def to_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def parse_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return value != 0

    return normalize_text(value) in {
        "1",
        "true",
        "yes",
        "y",
    }


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (
            table_name,
        ),
    ).fetchone()

    return row is not None


def validate_required_tables(
    connection: sqlite3.Connection,
) -> None:
    required_tables = (
        "institutional_learning_observations",
        "mapped_market_results",
        "market_resolutions",
    )

    missing_tables = [
        table_name
        for table_name in required_tables
        if not table_exists(
            connection,
            table_name,
        )
    ]

    if missing_tables:
        raise RuntimeError(
            "Missing required tables: "
            + ", ".join(
                missing_tables
            )
        )


# =============================================================================
# ENGINE DATABASE TABLES
# =============================================================================


def create_engine_tables(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS
        institutional_settlement_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,

            observations_loaded INTEGER
                NOT NULL DEFAULT 0,

            local_verified INTEGER
                NOT NULL DEFAULT 0,

            clob_verified INTEGER
                NOT NULL DEFAULT 0,

            pending_count INTEGER
                NOT NULL DEFAULT 0,

            unavailable_count INTEGER
                NOT NULL DEFAULT 0,

            quarantined_count INTEGER
                NOT NULL DEFAULT 0,

            api_error_count INTEGER
                NOT NULL DEFAULT 0,

            external_requests INTEGER
                NOT NULL DEFAULT 0,

            learning_rows_updated INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,

            status TEXT NOT NULL,

            error_message TEXT
        );


        CREATE TABLE IF NOT EXISTS
        institutional_settlement_intelligence_audit (
            audit_key TEXT PRIMARY KEY,

            run_id TEXT NOT NULL,

            observation_key TEXT NOT NULL,

            market_id TEXT NOT NULL,

            title TEXT NOT NULL,

            selected_outcome TEXT NOT NULL,

            decision_action TEXT NOT NULL,

            settlement_status TEXT NOT NULL,

            settlement_source TEXT NOT NULL,

            winning_outcome TEXT,

            selected_settlement_price REAL,

            source_outcome_won INTEGER,

            source_outcome_lost INTEGER,

            resolved_at TEXT,

            match_method TEXT,

            match_confidence REAL NOT NULL,

            evidence_json TEXT NOT NULL,

            conflict_reason TEXT,

            external_request_made INTEGER
                NOT NULL DEFAULT 0,

            created_at TEXT NOT NULL
        );


        CREATE INDEX IF NOT EXISTS
        idx_settlement_audit_status
        ON institutional_settlement_intelligence_audit (
            settlement_status,
            market_id
        );


        CREATE INDEX IF NOT EXISTS
        idx_settlement_audit_observation
        ON institutional_settlement_intelligence_audit (
            observation_key,
            created_at
        );


        CREATE TABLE IF NOT EXISTS
        institutional_settlement_quarantine (
            quarantine_key TEXT PRIMARY KEY,

            observation_key TEXT NOT NULL,

            market_id TEXT NOT NULL,

            title TEXT NOT NULL,

            selected_outcome TEXT NOT NULL,

            quarantine_reason TEXT NOT NULL,

            evidence_json TEXT NOT NULL,

            first_seen_at TEXT NOT NULL,

            last_seen_at TEXT NOT NULL,

            occurrence_count INTEGER
                NOT NULL DEFAULT 1,

            resolved_from_quarantine INTEGER
                NOT NULL DEFAULT 0,

            resolution_note TEXT
        );


        CREATE INDEX IF NOT EXISTS
        idx_settlement_quarantine_market
        ON institutional_settlement_quarantine (
            market_id,
            resolved_from_quarantine
        );


        CREATE TABLE IF NOT EXISTS
        institutional_clob_market_cache (
            condition_id TEXT PRIMARY KEY,

            question TEXT,

            active INTEGER,

            closed INTEGER,

            archived INTEGER,

            accepting_orders INTEGER,

            game_start_time TEXT,

            end_date_iso TEXT,

            winning_outcome TEXT,

            token_count INTEGER
                NOT NULL DEFAULT 0,

            raw_payload_json TEXT NOT NULL,

            fetched_at TEXT NOT NULL,

            updated_at TEXT NOT NULL
        );
        """
    )


# =============================================================================
# OBSERVATION LOADING
# =============================================================================


def load_observations(
    connection: sqlite3.Connection,
    limit: int,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            observation_key,
            market_id,
            title,
            selected_outcome,
            decision_action,
            observed_at

        FROM institutional_learning_observations

        WHERE actual_result IS NULL

          AND COALESCE(
                resolution_status,
                ''
              ) != 'RESOLVED'

          AND UPPER(
                decision_action
              ) IN (
                'BUY',
                'AVOID'
              )

          AND TRIM(
                COALESCE(
                    market_id,
                    ''
                )
              ) != ''

          AND TRIM(
                COALESCE(
                    selected_outcome,
                    ''
                )
              ) != ''

        ORDER BY
            observed_at ASC,
            observation_key ASC

        LIMIT ?
        """,
        (
            limit,
        ),
    ).fetchall()


# =============================================================================
# RESULT CONSTRUCTION
# =============================================================================


def make_result(
    observation: sqlite3.Row,
    status: str,
    evidence: dict[str, Any],
    *,
    resolution_source: str = "LOCAL_DATABASE",
    winning_outcome: str | None = None,
    settlement_price: float | None = None,
    source_outcome_won: int | None = None,
    source_outcome_lost: int | None = None,
    resolved_at: str | None = None,
    match_method: str | None = None,
    match_confidence: float = 0.0,
    conflict_reason: str | None = None,
    external_request_made: int = 0,
) -> dict[str, Any]:
    return {
        "observation_key": (
            observation[
                "observation_key"
            ]
        ),

        "market_id": (
            observation[
                "market_id"
            ]
        ),

        "title": (
            observation[
                "title"
            ]
        ),

        "selected_outcome": (
            observation[
                "selected_outcome"
            ]
        ),

        "decision_action": (
            observation[
                "decision_action"
            ]
        ),

        "status": status,

        "resolution_source": (
            resolution_source
        ),

        "winning_outcome": (
            winning_outcome
        ),

        "settlement_price": (
            settlement_price
        ),

        "source_outcome_won": (
            source_outcome_won
        ),

        "source_outcome_lost": (
            source_outcome_lost
        ),

        "resolved_at": (
            resolved_at
        ),

        "match_method": (
            match_method
        ),

        "match_confidence": (
            match_confidence
        ),

        "evidence_json": json.dumps(
            evidence,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ),

        "conflict_reason": (
            conflict_reason
        ),

        "external_request_made": (
            external_request_made
        ),
    }


# =============================================================================
# LOCAL SETTLEMENT VERIFICATION
# =============================================================================


def load_local_mapped_rows(
    connection: sqlite3.Connection,
    observation: sqlite3.Row,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT *

        FROM mapped_market_results

        WHERE (
                LOWER(
                    TRIM(
                        source_market_id
                    )
                )
                =
                LOWER(
                    TRIM(?)
                )

             OR

                LOWER(
                    TRIM(
                        COALESCE(
                            condition_id,
                            ''
                        )
                    )
                )
                =
                LOWER(
                    TRIM(?)
                )
              )

          AND (
                LOWER(
                    TRIM(
                        COALESCE(
                            source_outcome,
                            ''
                        )
                    )
                )
                =
                LOWER(
                    TRIM(?)
                )

             OR

                LOWER(
                    TRIM(
                        COALESCE(
                            source_outcome_normalized,
                            ''
                        )
                    )
                )
                =
                LOWER(
                    TRIM(?)
                )
              )

        ORDER BY
            match_confidence DESC,
            updated_at DESC
        """,
        (
            observation[
                "market_id"
            ],
            observation[
                "market_id"
            ],
            observation[
                "selected_outcome"
            ],
            observation[
                "selected_outcome"
            ],
        ),
    ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def load_local_resolution_rows(
    connection: sqlite3.Connection,
    market_id: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT *

        FROM market_resolutions

        WHERE LOWER(
                TRIM(
                    COALESCE(
                        condition_id,
                        ''
                    )
                )
              )
              =
              LOWER(
                TRIM(?)
              )

        ORDER BY
            confidence_score DESC,
            updated_at DESC
        """,
        (
            market_id,
        ),
    ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def verify_local_observation(
    connection: sqlite3.Connection,
    observation: sqlite3.Row,
) -> dict[str, Any] | None:
    mapped_rows = load_local_mapped_rows(
        connection,
        observation,
    )

    resolution_rows = (
        load_local_resolution_rows(
            connection,
            str(
                observation[
                    "market_id"
                ]
            ),
        )
    )

    evidence = {
        "observation": dict(
            observation
        ),

        "mapped_market_results": (
            mapped_rows
        ),

        "market_resolutions": (
            resolution_rows
        ),

        "verified_at": utc_now(),

        "engine_version": (
            ENGINE_VERSION
        ),
    }

    if (
        not mapped_rows
        and not resolution_rows
    ):
        return None

    resolved_mapped_rows = [
        row
        for row in mapped_rows
        if (
            normalize_status(
                row.get(
                    "resolution_status"
                )
            )
            in RESOLVED_LOCAL_STATUSES

            and str(
                row.get(
                    "winning_outcome_name"
                )
                or ""
            ).strip()

            and to_int(
                row.get(
                    "source_outcome_won"
                )
            )
            in (
                0,
                1,
            )

            and to_int(
                row.get(
                    "source_outcome_lost"
                )
            )
            in (
                0,
                1,
            )
        )
    ]

    if not resolved_mapped_rows:
        return None

    mapped_winners = {
        normalize_text(
            row.get(
                "winning_outcome_name"
            )
        )
        for row in resolved_mapped_rows
    }

    result_flags = {
        (
            to_int(
                row.get(
                    "source_outcome_won"
                )
            ),

            to_int(
                row.get(
                    "source_outcome_lost"
                )
            ),
        )
        for row in resolved_mapped_rows
    }

    if len(mapped_winners) != 1:
        return make_result(
            observation,
            "QUARANTINED_LOCAL_WINNER_CONFLICT",
            evidence,
            conflict_reason=(
                "Local mapped rows report "
                "different winning outcomes."
            ),
        )

    if len(result_flags) != 1:
        return make_result(
            observation,
            "QUARANTINED_LOCAL_RESULT_CONFLICT",
            evidence,
            conflict_reason=(
                "Local mapped rows disagree "
                "on the selected outcome result."
            ),
        )

    primary = resolved_mapped_rows[0]

    source_outcome_won = to_int(
        primary.get(
            "source_outcome_won"
        )
    )

    source_outcome_lost = to_int(
        primary.get(
            "source_outcome_lost"
        )
    )

    match_confidence = (
        to_float(
            primary.get(
                "match_confidence"
            )
        )
        or 0.0
    )

    winning_outcome = str(
        primary.get(
            "winning_outcome_name"
        )
        or ""
    ).strip()

    if (
        source_outcome_won
        not in (
            0,
            1,
        )
        or source_outcome_lost
        not in (
            0,
            1,
        )
        or (
            source_outcome_won
            + source_outcome_lost
            != 1
        )
    ):
        return make_result(
            observation,
            "QUARANTINED_INVALID_LOCAL_FLAGS",
            evidence,

            winning_outcome=(
                winning_outcome
            ),

            source_outcome_won=(
                source_outcome_won
            ),

            source_outcome_lost=(
                source_outcome_lost
            ),

            match_confidence=(
                match_confidence
            ),

            conflict_reason=(
                "Local win/loss flags "
                "must be complementary "
                "binary values."
            ),
        )

    if (
        match_confidence
        < MINIMUM_LOCAL_MATCH_CONFIDENCE
    ):
        return make_result(
            observation,
            "QUARANTINED_LOW_LOCAL_CONFIDENCE",
            evidence,

            winning_outcome=(
                winning_outcome
            ),

            source_outcome_won=(
                source_outcome_won
            ),

            source_outcome_lost=(
                source_outcome_lost
            ),

            match_confidence=(
                match_confidence
            ),

            conflict_reason=(
                "Local match confidence "
                "is below the required "
                "threshold."
            ),
        )

    resolved_market_rows = [
        row
        for row in resolution_rows
        if (
            to_int(
                row.get(
                    "resolved"
                )
            )
            == 1

            and to_int(
                row.get(
                    "closed"
                )
            )
            == 1

            and normalize_status(
                row.get(
                    "resolution_status"
                )
            )
            in RESOLVED_LOCAL_STATUSES

            and str(
                row.get(
                    "winning_outcome_name"
                )
                or ""
            ).strip()
        )
    ]

    if resolved_market_rows:
        resolution_winners = {
            normalize_text(
                row.get(
                    "winning_outcome_name"
                )
            )
            for row in resolved_market_rows
        }

        if len(
            resolution_winners
        ) != 1:
            return make_result(
                observation,
                (
                    "QUARANTINED_"
                    "LOCAL_RESOLUTION_CONFLICT"
                ),
                evidence,
                conflict_reason=(
                    "market_resolutions "
                    "contains multiple winners "
                    "for the condition ID."
                ),
            )

        resolution_winner = next(
            iter(
                resolution_winners
            )
        )

        if (
            resolution_winner
            != normalize_text(
                winning_outcome
            )
        ):
            return make_result(
                observation,
                (
                    "QUARANTINED_"
                    "LOCAL_CROSS_TABLE_CONFLICT"
                ),
                evidence,
                conflict_reason=(
                    "mapped_market_results "
                    "and market_resolutions "
                    "disagree."
                ),
            )

    selected_settlement_price = (
        1.0
        if source_outcome_won == 1
        else 0.0
    )

    return make_result(
        observation,
        "VERIFIED_RESOLVED_LOCAL",
        evidence,

        resolution_source=(
            "LOCAL_DATABASE"
        ),

        winning_outcome=(
            winning_outcome
        ),

        settlement_price=(
            selected_settlement_price
        ),

        source_outcome_won=(
            source_outcome_won
        ),

        source_outcome_lost=(
            source_outcome_lost
        ),

        resolved_at=(
            str(
                primary.get(
                    "resolved_at_detected"
                )
                or ""
            ).strip()
            or utc_now()
        ),

        match_method=(
            str(
                primary.get(
                    "match_method"
                )
                or ""
            ).strip()
            or (
                "EXACT_LOCAL_"
                "CONDITION_ID_AND_OUTCOME"
            )
        ),

        match_confidence=(
            match_confidence
        ),
    )


# =============================================================================
# CLOB SETTLEMENT VERIFICATION
# =============================================================================


def fetch_clob_market(
    condition_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    url = CLOB_MARKET_URL.format(
        condition_id=condition_id
    )

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",

            "User-Agent": (
                "Polymarket-Intelligence-"
                "Settlement-Engine/2.0"
            ),
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout_seconds,
    ) as response:
        payload = json.loads(
            response.read().decode(
                "utf-8"
            )
        )

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "CLOB returned a "
            "non-object payload."
        )

    return payload


def verify_clob_market(
    observation: sqlite3.Row,
    payload: dict[str, Any],
) -> dict[str, Any]:
    expected_condition_id = str(
        observation[
            "market_id"
        ]
    ).strip()

    returned_condition_id = str(
        payload.get(
            "condition_id",
            "",
        )
    ).strip()

    evidence = {
        "observation": dict(
            observation
        ),

        "clob_market": payload,

        "verified_at": utc_now(),

        "engine_version": (
            ENGINE_VERSION
        ),
    }

    if (
        normalize_text(
            returned_condition_id
        )
        != normalize_text(
            expected_condition_id
        )
    ):
        return make_result(
            observation,
            "QUARANTINED_CLOB_ID_MISMATCH",
            evidence,

            resolution_source="CLOB",

            conflict_reason=(
                "Returned CLOB condition ID "
                "does not match the requested "
                "condition ID."
            ),

            external_request_made=1,
        )

    tokens = payload.get(
        "tokens"
    )

    if not isinstance(
        tokens,
        list,
    ):
        return make_result(
            observation,
            "QUARANTINED_CLOB_TOKENS_MISSING",
            evidence,

            resolution_source="CLOB",

            conflict_reason=(
                "CLOB response did not contain "
                "a valid token list."
            ),

            external_request_made=1,
        )

    closed = parse_boolean(
        payload.get(
            "closed"
        )
    )

    accepting_orders = (
        parse_boolean(
            payload.get(
                "accepting_orders"
            )
        )
    )

    if (
        not closed
        or accepting_orders
    ):
        return make_result(
            observation,
            "PENDING_CLOB_OPEN",
            evidence,

            resolution_source="CLOB",

            match_method=(
                "EXACT_CLOB_CONDITION_ID"
            ),

            match_confidence=1.0,

            external_request_made=1,
        )

    winning_tokens = [
        token
        for token in tokens
        if (
            isinstance(
                token,
                dict,
            )
            and parse_boolean(
                token.get(
                    "winner"
                )
            )
        )
    ]

    if len(
        winning_tokens
    ) != 1:
        return make_result(
            observation,
            "QUARANTINED_CLOB_WINNER_COUNT",
            evidence,

            resolution_source="CLOB",

            conflict_reason=(
                "A closed CLOB market must "
                "contain exactly one token "
                "with winner=true."
            ),

            external_request_made=1,
        )

    winning_token = (
        winning_tokens[0]
    )

    winning_outcome = str(
        winning_token.get(
            "outcome",
            "",
        )
    ).strip()

    if not winning_outcome:
        return make_result(
            observation,
            (
                "QUARANTINED_"
                "CLOB_WINNER_LABEL_MISSING"
            ),
            evidence,

            resolution_source="CLOB",

            conflict_reason=(
                "The winning CLOB token "
                "has no outcome label."
            ),

            external_request_made=1,
        )

    selected_outcome = str(
        observation[
            "selected_outcome"
        ]
    ).strip()

    selected_tokens = [
        token
        for token in tokens
        if (
            isinstance(
                token,
                dict,
            )
            and normalize_text(
                token.get(
                    "outcome"
                )
            )
            == normalize_text(
                selected_outcome
            )
        )
    ]

    if len(
        selected_tokens
    ) != 1:
        return make_result(
            observation,
            (
                "QUARANTINED_"
                "SELECTED_OUTCOME_NOT_FOUND"
            ),
            evidence,

            resolution_source="CLOB",

            winning_outcome=(
                winning_outcome
            ),

            conflict_reason=(
                "The selected outcome did "
                "not exactly match one "
                "CLOB token."
            ),

            external_request_made=1,
        )

    selected_token = (
        selected_tokens[0]
    )

    source_outcome_won = int(
        parse_boolean(
            selected_token.get(
                "winner"
            )
        )
    )

    source_outcome_lost = (
        1 - source_outcome_won
    )

    selected_price = to_float(
        selected_token.get(
            "price"
        )
    )

    if selected_price is None:
        selected_price = (
            1.0
            if source_outcome_won == 1
            else 0.0
        )

    if (
        source_outcome_won == 1
        and selected_price < 0.999
    ):
        return make_result(
            observation,
            (
                "QUARANTINED_"
                "CLOB_WINNER_PRICE_CONFLICT"
            ),
            evidence,

            resolution_source="CLOB",

            winning_outcome=(
                winning_outcome
            ),

            settlement_price=(
                selected_price
            ),

            source_outcome_won=(
                source_outcome_won
            ),

            source_outcome_lost=(
                source_outcome_lost
            ),

            conflict_reason=(
                "winner=true but the token "
                "price is below the final "
                "settlement threshold."
            ),

            external_request_made=1,
        )

    if (
        source_outcome_won == 0
        and selected_price > 0.001
    ):
        return make_result(
            observation,
            (
                "QUARANTINED_"
                "CLOB_LOSER_PRICE_CONFLICT"
            ),
            evidence,

            resolution_source="CLOB",

            winning_outcome=(
                winning_outcome
            ),

            settlement_price=(
                selected_price
            ),

            source_outcome_won=(
                source_outcome_won
            ),

            source_outcome_lost=(
                source_outcome_lost
            ),

            conflict_reason=(
                "winner=false but the token "
                "price is above the final "
                "settlement threshold."
            ),

            external_request_made=1,
        )

    selected_settlement_price = (
        1.0
        if source_outcome_won == 1
        else 0.0
    )

    return make_result(
        observation,
        "VERIFIED_RESOLVED_CLOB",
        evidence,

        resolution_source="CLOB",

        winning_outcome=(
            winning_outcome
        ),

        settlement_price=(
            selected_settlement_price
        ),

        source_outcome_won=(
            source_outcome_won
        ),

        source_outcome_lost=(
            source_outcome_lost
        ),

        resolved_at=utc_now(),

        match_method=(
            "EXACT_CLOB_CONDITION_ID_"
            "AND_TOKEN_OUTCOME"
        ),

        match_confidence=1.0,

        external_request_made=1,
    )


def resolve_with_clob(
    observation: sqlite3.Row,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        payload = fetch_clob_market(
            str(
                observation[
                    "market_id"
                ]
            ).strip(),
            timeout_seconds,
        )

    except urllib.error.HTTPError as error:
        response_body = ""

        try:
            response_body = (
                error.read()
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )

        except Exception:
            pass

        status = (
            "UNAVAILABLE_CLOB_NOT_FOUND"
            if error.code == 404
            else "API_ERROR_CLOB_HTTP"
        )

        return make_result(
            observation,
            status,
            {
                "observation": dict(
                    observation
                ),

                "http_status": (
                    error.code
                ),

                "http_reason": str(
                    error.reason
                ),

                "response_body": (
                    response_body[
                        :2000
                    ]
                ),

                "verified_at": (
                    utc_now()
                ),

                "engine_version": (
                    ENGINE_VERSION
                ),
            },

            resolution_source="CLOB",

            conflict_reason=(
                None
                if error.code == 404
                else (
                    f"HTTP {error.code}: "
                    f"{error.reason}"
                )
            ),

            external_request_made=1,
        )

    except urllib.error.URLError as error:
        return make_result(
            observation,
            "API_ERROR_CLOB_URL",
            {
                "observation": dict(
                    observation
                ),

                "error": str(
                    error.reason
                ),

                "verified_at": (
                    utc_now()
                ),

                "engine_version": (
                    ENGINE_VERSION
                ),
            },

            resolution_source="CLOB",

            conflict_reason=str(
                error.reason
            ),

            external_request_made=1,
        )

    except Exception as error:
        return make_result(
            observation,
            "API_ERROR_CLOB_OTHER",
            {
                "observation": dict(
                    observation
                ),

                "error_type": (
                    type(
                        error
                    ).__name__
                ),

                "error": str(
                    error
                ),

                "verified_at": (
                    utc_now()
                ),

                "engine_version": (
                    ENGINE_VERSION
                ),
            },

            resolution_source="CLOB",

            conflict_reason=(
                f"{type(error).__name__}: "
                f"{error}"
            ),

            external_request_made=1,
        )

    return verify_clob_market(
        observation,
        payload,
    )


# =============================================================================
# ORCHESTRATION
# =============================================================================


def resolve_observation(
    connection: sqlite3.Connection,
    observation: sqlite3.Row,
    *,
    local_only: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    local_result = (
        verify_local_observation(
            connection,
            observation,
        )
    )

    if local_result is not None:
        if (
            local_result[
                "status"
            ]
            == "VERIFIED_RESOLVED_LOCAL"
        ):
            return local_result

        if (
            local_result[
                "status"
            ].startswith(
                "QUARANTINED"
            )
        ):
            return local_result

    if local_only:
        return make_result(
            observation,
            "UNAVAILABLE_LOCAL_ONLY",
            {
                "observation": dict(
                    observation
                ),

                "verified_at": (
                    utc_now()
                ),

                "engine_version": (
                    ENGINE_VERSION
                ),
            },

            resolution_source=(
                "LOCAL_DATABASE"
            ),
        )

    return resolve_with_clob(
        observation,
        timeout_seconds,
    )


def result_bucket(
    status: str,
) -> str:
    if (
        status
        == "VERIFIED_RESOLVED_LOCAL"
    ):
        return "LOCAL_VERIFIED"

    if (
        status
        == "VERIFIED_RESOLVED_CLOB"
    ):
        return "CLOB_VERIFIED"

    if status.startswith(
        "PENDING"
    ):
        return "PENDING"

    if status.startswith(
        "UNAVAILABLE"
    ):
        return "UNAVAILABLE"

    if status.startswith(
        "API_ERROR"
    ):
        return "API_ERROR"

    return "QUARANTINED"


# =============================================================================
# PERSISTENCE
# =============================================================================


def make_audit_key(
    run_id: str,
    observation_key: str,
) -> str:
    return hashlib.sha256(
        (
            f"{run_id}|"
            f"{observation_key}"
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def make_quarantine_key(
    observation_key: str,
    status: str,
) -> str:
    return hashlib.sha256(
        (
            f"{observation_key}|"
            f"{status}"
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def save_clob_cache_row(
    connection: sqlite3.Connection,
    result: dict[str, Any],
) -> None:
    if (
        result[
            "resolution_source"
        ]
        != "CLOB"
    ):
        return

    try:
        evidence = json.loads(
            result[
                "evidence_json"
            ]
        )

    except json.JSONDecodeError:
        return

    payload = evidence.get(
        "clob_market"
    )

    if not isinstance(
        payload,
        dict,
    ):
        return

    tokens = payload.get(
        "tokens"
    )

    if not isinstance(
        tokens,
        list,
    ):
        tokens = []

    winning_tokens = [
        token
        for token in tokens
        if (
            isinstance(
                token,
                dict,
            )
            and parse_boolean(
                token.get(
                    "winner"
                )
            )
        )
    ]

    if len(
        winning_tokens
    ) == 1:
        winning_outcome = str(
            winning_tokens[0].get(
                "outcome",
                "",
            )
        ).strip()

    else:
        winning_outcome = None

    now = utc_now()

    connection.execute(
        """
        INSERT INTO institutional_clob_market_cache (
            condition_id,
            question,
            active,
            closed,
            archived,
            accepting_orders,
            game_start_time,
            end_date_iso,
            winning_outcome,
            token_count,
            raw_payload_json,
            fetched_at,
            updated_at
        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )

        ON CONFLICT(condition_id)

        DO UPDATE SET
            question =
                excluded.question,

            active =
                excluded.active,

            closed =
                excluded.closed,

            archived =
                excluded.archived,

            accepting_orders =
                excluded.accepting_orders,

            game_start_time =
                excluded.game_start_time,

            end_date_iso =
                excluded.end_date_iso,

            winning_outcome =
                excluded.winning_outcome,

            token_count =
                excluded.token_count,

            raw_payload_json =
                excluded.raw_payload_json,

            fetched_at =
                excluded.fetched_at,

            updated_at =
                excluded.updated_at
        """,
        (
            result[
                "market_id"
            ],

            str(
                payload.get(
                    "question",
                    "",
                )
            ),

            int(
                parse_boolean(
                    payload.get(
                        "active"
                    )
                )
            ),

            int(
                parse_boolean(
                    payload.get(
                        "closed"
                    )
                )
            ),

            int(
                parse_boolean(
                    payload.get(
                        "archived"
                    )
                )
            ),

            int(
                parse_boolean(
                    payload.get(
                        "accepting_orders"
                    )
                )
            ),

            str(
                payload.get(
                    "game_start_time",
                    "",
                )
            ),

            str(
                payload.get(
                    "end_date_iso",
                    "",
                )
            ),

            winning_outcome,

            len(
                tokens
            ),

            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ),

            now,

            now,
        ),
    )


def save_results(
    connection: sqlite3.Connection,
    run_id: str,
    results: list[
        dict[str, Any]
    ],
) -> int:
    now = utc_now()

    for result in results:
        connection.execute(
            """
            INSERT INTO
            institutional_settlement_intelligence_audit (
                audit_key,
                run_id,
                observation_key,
                market_id,
                title,
                selected_outcome,
                decision_action,
                settlement_status,
                settlement_source,
                winning_outcome,
                selected_settlement_price,
                source_outcome_won,
                source_outcome_lost,
                resolved_at,
                match_method,
                match_confidence,
                evidence_json,
                conflict_reason,
                external_request_made,
                created_at
            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                make_audit_key(
                    run_id,
                    result[
                        "observation_key"
                    ],
                ),

                run_id,

                result[
                    "observation_key"
                ],

                result[
                    "market_id"
                ],

                result[
                    "title"
                ],

                result[
                    "selected_outcome"
                ],

                result[
                    "decision_action"
                ],

                result[
                    "status"
                ],

                result[
                    "resolution_source"
                ],

                result[
                    "winning_outcome"
                ],

                result[
                    "settlement_price"
                ],

                result[
                    "source_outcome_won"
                ],

                result[
                    "source_outcome_lost"
                ],

                result[
                    "resolved_at"
                ],

                result[
                    "match_method"
                ],

                result[
                    "match_confidence"
                ],

                result[
                    "evidence_json"
                ],

                result[
                    "conflict_reason"
                ],

                result[
                    "external_request_made"
                ],

                now,
            ),
        )

        save_clob_cache_row(
            connection,
            result,
        )

        if (
            result_bucket(
                result[
                    "status"
                ]
            )
            == "QUARANTINED"
        ):
            quarantine_key = (
                make_quarantine_key(
                    result[
                        "observation_key"
                    ],
                    result[
                        "status"
                    ],
                )
            )

            connection.execute(
                """
                INSERT INTO
                institutional_settlement_quarantine (
                    quarantine_key,
                    observation_key,
                    market_id,
                    title,
                    selected_outcome,
                    quarantine_reason,
                    evidence_json,
                    first_seen_at,
                    last_seen_at,
                    occurrence_count,
                    resolved_from_quarantine
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0
                )

                ON CONFLICT(
                    quarantine_key
                )

                DO UPDATE SET
                    evidence_json =
                        excluded.evidence_json,

                    last_seen_at =
                        excluded.last_seen_at,

                    occurrence_count =
                        occurrence_count + 1
                """,
                (
                    quarantine_key,

                    result[
                        "observation_key"
                    ],

                    result[
                        "market_id"
                    ],

                    result[
                        "title"
                    ],

                    result[
                        "selected_outcome"
                    ],

                    (
                        result[
                            "conflict_reason"
                        ]
                        or result[
                            "status"
                        ]
                    ),

                    result[
                        "evidence_json"
                    ],

                    now,

                    now,
                ),
            )

    updated_rows = 0

    for result in results:
        if result[
            "status"
        ] not in {
            "VERIFIED_RESOLVED_LOCAL",
            "VERIFIED_RESOLVED_CLOB",
        }:
            continue

        cursor = connection.execute(
            """
            UPDATE
                institutional_learning_observations

            SET
                resolution_status =
                    'RESOLVED',

                resolution_evidence =
                    ?,

                winning_outcome =
                    ?,

                source_outcome_won =
                    ?,

                source_outcome_lost =
                    ?,

                settlement_price =
                    ?,

                resolved_at =
                    ?,

                match_method =
                    ?,

                match_confidence =
                    ?,

                updated_at =
                    ?

            WHERE observation_key = ?

              AND actual_result IS NULL

              AND COALESCE(
                    resolution_status,
                    ''
                  ) != 'RESOLVED'
            """,
            (
                result[
                    "evidence_json"
                ],

                result[
                    "winning_outcome"
                ],

                result[
                    "source_outcome_won"
                ],

                result[
                    "source_outcome_lost"
                ],

                result[
                    "settlement_price"
                ],

                (
                    result[
                        "resolved_at"
                    ]
                    or utc_now()
                ),

                result[
                    "match_method"
                ],

                result[
                    "match_confidence"
                ],

                utc_now(),

                result[
                    "observation_key"
                ],
            ),
        )

        updated_rows += (
            cursor.rowcount
        )

    return updated_rows


# =============================================================================
# REPORTING
# =============================================================================


def print_result(
    index: int,
    result: dict[str, Any],
) -> None:
    selected_result = "-"

    if (
        result[
            "source_outcome_won"
        ]
        == 1
    ):
        selected_result = "WON"

    elif (
        result[
            "source_outcome_lost"
        ]
        == 1
    ):
        selected_result = "LOST"

    print(
        f"{index:>3}. "
        f"{result['status']:<43} "
        f"{result['decision_action']:<6} "
        f"selected="
        f"{result['selected_outcome']:<24} "
        f"winner="
        f"{(result['winning_outcome'] or '-'):<24} "
        f"result="
        f"{selected_result}"
    )

    print(
        f"     market_id="
        f"{result['market_id']}"
    )

    print(
        f"     title="
        f"{result['title']}"
    )

    print(
        f"     source="
        f"{result['resolution_source']} "
        f"| method="
        f"{result['match_method'] or '-'}"
    )

    if result[
        "conflict_reason"
    ]:
        print(
            f"     note="
            f"{result['conflict_reason']}"
        )


def print_summary(
    mode: str,
    run_id: str,
    observations: list[
        sqlite3.Row
    ],
    results: list[
        dict[str, Any]
    ],
    updated_rows: int,
    duration_seconds: float,
    display_limit: int,
) -> None:
    buckets = [
        result_bucket(
            result[
                "status"
            ]
        )
        for result in results
    ]

    print()
    print(
        "=" * 165
    )

    print(
        "POLYMARKET INSTITUTIONAL "
        "SETTLEMENT INTELLIGENCE "
        "ENGINE v2.0"
    )

    print(
        "=" * 165
    )

    print(
        f"Database:                    "
        f"{DATABASE_PATH}"
    )

    print(
        f"Mode:                        "
        f"{mode}"
    )

    print(
        f"Run ID:                      "
        f"{run_id}"
    )

    print(
        f"Eligible observations:       "
        f"{len(observations):,}"
    )

    print(
        f"Local verified:              "
        f"{buckets.count('LOCAL_VERIFIED'):,}"
    )

    print(
        f"CLOB verified:               "
        f"{buckets.count('CLOB_VERIFIED'):,}"
    )

    print(
        f"Pending:                     "
        f"{buckets.count('PENDING'):,}"
    )

    print(
        f"Unavailable:                 "
        f"{buckets.count('UNAVAILABLE'):,}"
    )

    print(
        f"Quarantined:                 "
        f"{buckets.count('QUARANTINED'):,}"
    )

    print(
        f"API errors:                  "
        f"{buckets.count('API_ERROR'):,}"
    )

    print(
        f"External requests:           "
        f"{sum(result['external_request_made'] for result in results):,}"
    )

    print(
        f"Learning rows updated:       "
        f"{updated_rows:,}"
    )

    print(
        f"Duration:                    "
        f"{duration_seconds:.3f}s"
    )

    print(
        "=" * 165
    )

    print()
    print(
        "SETTLEMENT BOARD"
    )
    print(
        "-" * 165
    )

    for index, result in enumerate(
        results[
            :display_limit
        ],
        start=1,
    ):
        print_result(
            index,
            result,
        )

    if (
        len(results)
        > display_limit
    ):
        print()

        print(
            f"... "
            f"{len(results) - display_limit:,} "
            f"additional rows omitted."
        )

    print()
    print(
        "SAFETY INTERPRETATION"
    )
    print(
        "-" * 165
    )

    print(
        "Local matching:              "
        "EXACT CONDITION ID + OUTCOME"
    )

    print(
        "External authority:          "
        "CLOB MARKET BY CONDITION ID"
    )

    print(
        "Closed-market requirement:   "
        "closed=true and "
        "accepting_orders=false"
    )

    print(
        "Winner requirement:          "
        "EXACTLY ONE token "
        "winner=true"
    )

    print(
        "Title/fuzzy matching:        "
        "PROHIBITED"
    )

    print(
        "Cross-source conflicts:      "
        "QUARANTINED"
    )

    print(
        "actual_result/is_correct:    "
        "NOT MODIFIED"
    )

    print(
        "Model methodology:           "
        "NOT MODIFIED"
    )

    print(
        "=" * 165
    )

    if mode == "DRY RUN":
        print(
            "Dry run complete. "
            "No database records "
            "were modified."
        )

    else:
        print(
            "Verified settlement facts, "
            "audits, quarantine records "
            "and CLOB cache records "
            "were saved."
        )

    print(
        "=" * 165
    )


# =============================================================================
# COMMAND-LINE ARGUMENTS
# =============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify Polymarket settlements "
            "using local data and exact "
            "CLOB condition-ID lookups."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist audit, quarantine, "
            "cache and verified settlement "
            "records."
        ),
    )

    parser.add_argument(
        "--local-only",
        action="store_true",
        help=(
            "Disable all CLOB requests."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=(
            DEFAULT_DISPLAY_LIMIT
        ),
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=(
            DEFAULT_TIMEOUT_SECONDS
        ),
    )

    parser.add_argument(
        "--request-delay",
        type=float,
        default=(
            DEFAULT_REQUEST_DELAY_SECONDS
        ),
    )

    return parser.parse_args()


# =============================================================================
# MAIN ENGINE
# =============================================================================


def main() -> None:
    args = parse_args()

    mode = (
        "APPLY"
        if args.apply
        else "DRY RUN"
    )

    run_id = (
        uuid.uuid4().hex
    )

    started_at = (
        utc_now()
    )

    started_clock = (
        time.perf_counter()
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    run_saved = False

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        validate_required_tables(
            connection
        )

        if args.apply:
            create_engine_tables(
                connection
            )

            connection.execute(
                """
                INSERT INTO
                institutional_settlement_intelligence_runs (
                    run_id,
                    engine_version,
                    mode,
                    started_at,
                    status
                )

                VALUES (
                    ?, ?, ?, ?, 'RUNNING'
                )
                """,
                (
                    run_id,
                    ENGINE_VERSION,
                    mode,
                    started_at,
                ),
            )

            connection.commit()

            run_saved = True

        observations = load_observations(
            connection,
            max(
                args.limit,
                1,
            ),
        )

        results: list[
            dict[str, Any]
        ] = []

        for observation in observations:
            settlement_result = (
                resolve_observation(
                    connection,
                    observation,

                    local_only=(
                        args.local_only
                    ),

                    timeout_seconds=max(
                        args.timeout,
                        1.0,
                    ),
                )
            )

            results.append(
                settlement_result
            )

            if (
                settlement_result[
                    "external_request_made"
                ]
                == 1
                and args.request_delay
                > 0
            ):
                time.sleep(
                    max(
                        args.request_delay,
                        0.0,
                    )
                )

        updated_rows = 0

        if args.apply:
            connection.execute(
                "BEGIN"
            )

            updated_rows = save_results(
                connection,
                run_id,
                results,
            )

            buckets = [
                result_bucket(
                    result[
                        "status"
                    ]
                )
                for result in results
            ]

            duration_seconds = (
                time.perf_counter()
                - started_clock
            )

            connection.execute(
                """
                UPDATE
                    institutional_settlement_intelligence_runs

                SET
                    completed_at =
                        ?,

                    observations_loaded =
                        ?,

                    local_verified =
                        ?,

                    clob_verified =
                        ?,

                    pending_count =
                        ?,

                    unavailable_count =
                        ?,

                    quarantined_count =
                        ?,

                    api_error_count =
                        ?,

                    external_requests =
                        ?,

                    learning_rows_updated =
                        ?,

                    duration_seconds =
                        ?,

                    status =
                        'COMPLETE'

                WHERE run_id = ?
                """,
                (
                    utc_now(),

                    len(
                        observations
                    ),

                    buckets.count(
                        "LOCAL_VERIFIED"
                    ),

                    buckets.count(
                        "CLOB_VERIFIED"
                    ),

                    buckets.count(
                        "PENDING"
                    ),

                    buckets.count(
                        "UNAVAILABLE"
                    ),

                    buckets.count(
                        "QUARANTINED"
                    ),

                    buckets.count(
                        "API_ERROR"
                    ),

                    sum(
                        result[
                            "external_request_made"
                        ]
                        for result in results
                    ),

                    updated_rows,

                    duration_seconds,

                    run_id,
                ),
            )

            connection.commit()

        else:
            duration_seconds = (
                time.perf_counter()
                - started_clock
            )

        print_summary(
            mode,
            run_id,
            observations,
            results,
            updated_rows,
            duration_seconds,
            max(
                args.display_limit,
                1,
            ),
        )

    except Exception as error:
        connection.rollback()

        if (
            args.apply
            and run_saved
        ):
            try:
                connection.execute(
                    """
                    UPDATE
                        institutional_settlement_intelligence_runs

                    SET
                        completed_at =
                            ?,

                        duration_seconds =
                            ?,

                        status =
                            'FAILED',

                        error_message =
                            ?

                    WHERE run_id = ?
                    """,
                    (
                        utc_now(),

                        (
                            time.perf_counter()
                            - started_clock
                        ),

                        str(
                            error
                        ),

                        run_id,
                    ),
                )

                connection.commit()

            except Exception:
                connection.rollback()

        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()