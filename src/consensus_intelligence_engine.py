from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "polymarket.db"
ENGINE_VERSION = "1.0.1"

MIN_ACTIONABLE_WALLETS = 2
MIN_ACTIONABLE_EFFECTIVE_WALLETS = 1.50
MIN_ACTIONABLE_CONFIDENCE = 55.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"consensus_run:{stamp}"


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA busy_timeout = 30000;")
    return connection


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table)})"
        ).fetchall()
    }


def first_present(columns: set[str], candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def normalize_outcome(value: Any) -> str:
    text = str(value or "UNKNOWN").strip()
    return text.upper() if text else "UNKNOWN"


def normalize_wallet(value: Any) -> str:
    return str(value or "").strip().lower()


def log_score(value: float, reference: float) -> float:
    if value <= 0 or reference <= 0:
        return 0.0
    return clamp(100.0 * math.log1p(value) / math.log1p(reference))


def effective_sample_size(weights: list[float]) -> float:
    positive = [max(0.0, w) for w in weights if w > 0]
    if not positive:
        return 0.0
    numerator = sum(positive) ** 2
    denominator = sum(w * w for w in positive)
    return numerator / denominator if denominator > 0 else 0.0


def weighted_choice(rows: list["VoteContribution"], field: str) -> tuple[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        weight = safe_float(getattr(row, field))
        totals[row.outcome] += max(0.0, weight)
    total = sum(totals.values())
    if total <= 0 or not totals:
        return "UNKNOWN", 0.0
    outcome, amount = max(totals.items(), key=lambda item: (item[1], item[0]))
    return outcome, 100.0 * amount / total


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_consensus (
            condition_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            market_title TEXT NOT NULL,
            domain TEXT NOT NULL,
            subdomain TEXT NOT NULL,
            leading_outcome TEXT NOT NULL,
            runner_up_outcome TEXT,
            wallet_count INTEGER NOT NULL,
            outcome_count INTEGER NOT NULL,
            effective_wallet_count REAL NOT NULL,
            total_capital_committed REAL NOT NULL,
            leading_wallet_count INTEGER NOT NULL,
            raw_agreement_pct REAL NOT NULL,
            influence_agreement_pct REAL NOT NULL,
            capital_agreement_pct REAL NOT NULL,
            specialist_agreement_pct REAL NOT NULL,
            institutional_outcome TEXT,
            institutional_agreement_pct REAL NOT NULL,
            institutional_wallet_count INTEGER NOT NULL,
            standard_outcome TEXT,
            standard_agreement_pct REAL NOT NULL,
            standard_wallet_count INTEGER NOT NULL,
            institutional_retail_divergence INTEGER NOT NULL,
            consensus_score REAL NOT NULL,
            consensus_confidence REAL NOT NULL,
            consensus_grade TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            pass_reason TEXT,
            explanation_json TEXT NOT NULL,
            source_mode TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(condition_id) REFERENCES market_domain_classification(condition_id),
            FOREIGN KEY(event_id) REFERENCES market_events(event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_market_consensus_rank
        ON market_consensus(consensus_grade, consensus_score DESC);

        CREATE INDEX IF NOT EXISTS idx_market_consensus_domain
        ON market_consensus(domain, subdomain, consensus_score DESC);

        CREATE TABLE IF NOT EXISTS consensus_votes (
            condition_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            wallet TEXT NOT NULL,
            outcome TEXT NOT NULL,
            domain TEXT NOT NULL,
            subdomain TEXT NOT NULL,
            wallet_grade TEXT NOT NULL,
            domain_grade TEXT NOT NULL,
            position_count INTEGER NOT NULL,
            capital_committed REAL NOT NULL,
            wallet_market_allocation_pct REAL NOT NULL,
            base_influence_score REAL NOT NULL,
            domain_score REAL NOT NULL,
            sample_confidence REAL NOT NULL,
            event_influence_weight REAL NOT NULL,
            capital_weight REAL NOT NULL,
            influence_weight REAL NOT NULL,
            specialist_weight REAL NOT NULL,
            effective_weight REAL NOT NULL,
            institutional_flag INTEGER NOT NULL,
            source_mode TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(condition_id, wallet, outcome)
        );

        CREATE INDEX IF NOT EXISTS idx_consensus_votes_market
        ON consensus_votes(condition_id, effective_weight DESC);

        CREATE INDEX IF NOT EXISTS idx_consensus_votes_wallet
        ON consensus_votes(wallet, effective_weight DESC);

        CREATE TABLE IF NOT EXISTS consensus_signal_history (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            condition_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            leading_outcome TEXT NOT NULL,
            consensus_score REAL NOT NULL,
            consensus_confidence REAL NOT NULL,
            consensus_grade TEXT NOT NULL,
            wallet_count INTEGER NOT NULL,
            effective_wallet_count REAL NOT NULL,
            total_capital_committed REAL NOT NULL,
            influence_agreement_pct REAL NOT NULL,
            institutional_outcome TEXT,
            standard_outcome TEXT,
            institutional_retail_divergence INTEGER NOT NULL,
            observed_price REAL,
            source_mode TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_consensus_signal_history_market
        ON consensus_signal_history(condition_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS consensus_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            markets_analyzed INTEGER NOT NULL,
            votes_created INTEGER NOT NULL,
            actionable_signals INTEGER NOT NULL,
            pass_markets INTEGER NOT NULL,
            divergent_markets INTEGER NOT NULL,
            total_capital_analyzed REAL NOT NULL,
            source_mode TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


@dataclass
class PositionSource:
    market_column: str
    wallet_column: str
    outcome_column: str
    capital_expression: str
    position_count_expression: str
    source_mode: str


@dataclass
class RawPosition:
    condition_id: str
    wallet: str
    outcome: str
    capital: float
    position_count: int


@dataclass
class MarketMeta:
    condition_id: str
    event_id: str
    title: str
    domain: str
    subdomain: str
    classification_confidence: float


@dataclass
class VoteContribution:
    condition_id: str
    event_id: str
    wallet: str
    outcome: str
    domain: str
    subdomain: str
    wallet_grade: str
    domain_grade: str
    position_count: int
    capital: float
    wallet_market_allocation_pct: float
    base_influence_score: float
    domain_score: float
    sample_confidence: float
    event_influence_weight: float
    capital_weight: float
    influence_weight: float
    specialist_weight: float
    effective_weight: float
    institutional_flag: int
    source_mode: str


def discover_position_source(connection: sqlite3.Connection) -> PositionSource:
    if not table_exists(connection, "positions"):
        raise RuntimeError("positions is missing. Run the wallet/position collection pipeline first.")

    columns = table_columns(connection, "positions")
    market_col = first_present(columns, ("condition_id", "market_id", "market_slug", "market"))
    wallet_col = first_present(columns, ("wallet", "proxy_wallet", "user", "address"))
    outcome_col = first_present(columns, ("outcome", "side", "position_outcome"))

    missing = [
        name
        for name, value in (
            ("market identifier", market_col),
            ("wallet", wallet_col),
            ("outcome", outcome_col),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError("positions is missing: " + ", ".join(missing))

    explicit_capital = first_present(
        columns,
        ("capital_committed", "cost_basis", "initial_value", "invested_value", "amount_invested"),
    )
    shares_col = first_present(columns, ("shares", "size", "quantity"))
    avg_price_col = first_present(columns, ("average_price", "avg_price", "entry_price"))
    current_value_col = first_present(columns, ("current_value", "value", "position_value"))

    if explicit_capital:
        capital_expression = f"MAX(0.0, COALESCE({quote_identifier(explicit_capital)}, 0.0))"
        source_mode = f"POSITIONS:{explicit_capital}"
    elif shares_col and avg_price_col:
        capital_expression = (
            f"MAX(0.0, COALESCE({quote_identifier(shares_col)}, 0.0) "
            f"* COALESCE({quote_identifier(avg_price_col)}, 0.0))"
        )
        source_mode = f"POSITIONS:{shares_col}_X_{avg_price_col}"
    elif current_value_col:
        capital_expression = f"MAX(0.0, COALESCE({quote_identifier(current_value_col)}, 0.0))"
        source_mode = f"POSITIONS:{current_value_col}"
    elif shares_col:
        capital_expression = f"MAX(0.0, COALESCE({quote_identifier(shares_col)}, 0.0))"
        source_mode = f"POSITIONS:{shares_col}_PROXY"
    else:
        capital_expression = "1.0"
        source_mode = "POSITIONS:ROW_COUNT_PROXY"

    return PositionSource(
        market_column=market_col or "",
        wallet_column=wallet_col or "",
        outcome_column=outcome_col or "",
        capital_expression=capital_expression,
        position_count_expression="COUNT(*)",
        source_mode=source_mode,
    )


def load_market_meta(connection: sqlite3.Connection) -> dict[str, MarketMeta]:
    required = ("market_domain_classification", "market_event_links")
    for table in required:
        if not table_exists(connection, table):
            raise RuntimeError(
                f"{table} is missing. Run python -m src.domain_intelligence_engine first."
            )

    rows = connection.execute(
        """
        SELECT
            mdc.condition_id,
            mdc.event_id,
            mdc.market_title,
            mdc.domain,
            mdc.subdomain,
            mdc.classification_confidence
        FROM market_domain_classification mdc
        """
    ).fetchall()

    return {
        str(row["condition_id"]): MarketMeta(
            condition_id=str(row["condition_id"]),
            event_id=str(row["event_id"]),
            title=str(row["market_title"] or ""),
            domain=str(row["domain"] or "OTHER"),
            subdomain=str(row["subdomain"] or "UNCLASSIFIED"),
            classification_confidence=clamp(safe_float(row["classification_confidence"]) * 100.0),
        )
        for row in rows
    }


def load_raw_positions(
    connection: sqlite3.Connection,
    source: PositionSource,
    market_meta: dict[str, MarketMeta],
) -> list[RawPosition]:
    query = f"""
        SELECT
            CAST({quote_identifier(source.market_column)} AS TEXT) AS market_key,
            LOWER(TRIM(CAST({quote_identifier(source.wallet_column)} AS TEXT))) AS wallet,
            UPPER(TRIM(CAST({quote_identifier(source.outcome_column)} AS TEXT))) AS outcome,
            SUM({source.capital_expression}) AS capital,
            {source.position_count_expression} AS position_count
        FROM positions
        WHERE {quote_identifier(source.wallet_column)} IS NOT NULL
          AND TRIM(CAST({quote_identifier(source.wallet_column)} AS TEXT)) <> ''
          AND {quote_identifier(source.outcome_column)} IS NOT NULL
        GROUP BY market_key, wallet, outcome
    """

    exact_keys = set(market_meta)
    title_to_condition = {
        meta.title.strip().lower(): condition_id
        for condition_id, meta in market_meta.items()
        if meta.title.strip()
    }

    rows: list[RawPosition] = []
    for row in connection.execute(query).fetchall():
        raw_key = str(row["market_key"] or "").strip()
        condition_id = raw_key if raw_key in exact_keys else title_to_condition.get(raw_key.lower())
        if not condition_id:
            continue

        wallet = normalize_wallet(row["wallet"])
        outcome = normalize_outcome(row["outcome"])
        if not wallet or outcome == "UNKNOWN":
            continue

        rows.append(
            RawPosition(
                condition_id=condition_id,
                wallet=wallet,
                outcome=outcome,
                capital=max(0.0, safe_float(row["capital"])),
                position_count=max(1, int(safe_float(row["position_count"], 1))),
            )
        )
    return rows


def load_wallet_profiles(connection: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    if not table_exists(connection, "wallet_influence"):
        raise RuntimeError(
            "wallet_influence is missing. Run python -m src.wallet_influence_engine first."
        )
    return {
        normalize_wallet(row["wallet"]): row
        for row in connection.execute("SELECT * FROM wallet_influence").fetchall()
    }


def load_domain_profiles(
    connection: sqlite3.Connection,
) -> dict[tuple[str, str, str], sqlite3.Row]:
    if not table_exists(connection, "wallet_domain_profiles"):
        raise RuntimeError(
            "wallet_domain_profiles is missing. Run python -m src.domain_intelligence_engine first."
        )
    return {
        (
            normalize_wallet(row["wallet"]),
            str(row["domain"]),
            str(row["subdomain"]),
        ): row
        for row in connection.execute("SELECT * FROM wallet_domain_profiles").fetchall()
    }


def load_event_profiles(
    connection: sqlite3.Connection,
) -> dict[tuple[str, str], sqlite3.Row]:
    if not table_exists(connection, "wallet_event_influence"):
        raise RuntimeError(
            "wallet_event_influence is missing. Run python -m src.wallet_influence_engine first."
        )
    return {
        (str(row["event_id"]), normalize_wallet(row["wallet"])): row
        for row in connection.execute("SELECT * FROM wallet_event_influence").fetchall()
    }


def build_votes(
    raw_positions: list[RawPosition],
    market_meta: dict[str, MarketMeta],
    wallet_profiles: dict[str, sqlite3.Row],
    domain_profiles: dict[tuple[str, str, str], sqlite3.Row],
    event_profiles: dict[tuple[str, str], sqlite3.Row],
    source_mode: str,
) -> list[VoteContribution]:
    wallet_total_capital: dict[str, float] = defaultdict(float)
    market_total_capital: dict[str, float] = defaultdict(float)

    for row in raw_positions:
        wallet_total_capital[row.wallet] += row.capital
        market_total_capital[row.condition_id] += row.capital

    max_market_capital = max(market_total_capital.values(), default=1.0)
    votes: list[VoteContribution] = []

    for row in raw_positions:
        meta = market_meta[row.condition_id]
        wallet_profile = wallet_profiles.get(row.wallet)
        domain_profile = domain_profiles.get((row.wallet, meta.domain, meta.subdomain))
        event_profile = event_profiles.get((meta.event_id, row.wallet))

        base_influence = clamp(
            safe_float(wallet_profile["influence_score"]) if wallet_profile else 25.0
        )
        wallet_grade = (
            str(wallet_profile["influence_grade"]) if wallet_profile else "UNRANKED"
        )

        domain_score = clamp(
            safe_float(domain_profile["domain_score"]) if domain_profile else base_influence * 0.55
        )
        sample_confidence = clamp(
            safe_float(domain_profile["sample_confidence"]) if domain_profile else 5.0
        )
        domain_grade = (
            str(domain_profile["domain_grade"]) if domain_profile else "UNPROVEN"
        )

        event_influence_weight = clamp(
            safe_float(event_profile["event_influence_weight"]) if event_profile else base_influence
        )

        wallet_total = wallet_total_capital[row.wallet]
        wallet_market_allocation_pct = (
            100.0 * row.capital / wallet_total if wallet_total > 0 else 0.0
        )

        capital_weight = log_score(row.capital, max_market_capital)
        influence_weight = clamp(
            0.62 * base_influence + 0.38 * event_influence_weight
        )
        specialist_weight = clamp(
            0.65 * domain_score
            + 0.25 * sample_confidence
            + 0.10 * meta.classification_confidence
        )

        allocation_multiplier = 0.80 + min(0.70, math.sqrt(max(0.0, wallet_market_allocation_pct)) / 10.0)
        capital_multiplier = 0.75 + 0.50 * (capital_weight / 100.0)

        effective_weight = max(
            0.01,
            (
                0.42 * influence_weight
                + 0.38 * specialist_weight
                + 0.20 * capital_weight
            )
            * allocation_multiplier
            * capital_multiplier,
        )

        institutional_flag = int(
            wallet_grade in {"TITAN", "INSTITUTIONAL", "ELITE", "PROFESSIONAL"}
            and domain_grade != "UNPROVEN"
            and sample_confidence >= 35.0
        )

        votes.append(
            VoteContribution(
                condition_id=row.condition_id,
                event_id=meta.event_id,
                wallet=row.wallet,
                outcome=row.outcome,
                domain=meta.domain,
                subdomain=meta.subdomain,
                wallet_grade=wallet_grade,
                domain_grade=domain_grade,
                position_count=row.position_count,
                capital=row.capital,
                wallet_market_allocation_pct=wallet_market_allocation_pct,
                base_influence_score=base_influence,
                domain_score=domain_score,
                sample_confidence=sample_confidence,
                event_influence_weight=event_influence_weight,
                capital_weight=capital_weight,
                influence_weight=influence_weight,
                specialist_weight=specialist_weight,
                effective_weight=effective_weight,
                institutional_flag=institutional_flag,
                source_mode=source_mode,
            )
        )

    return votes


def consensus_grade(score: float, confidence: float, actionable: bool) -> str:
    if not actionable:
        return "PASS"
    if score >= 88 and confidence >= 82:
        return "S+"
    if score >= 80 and confidence >= 74:
        return "S"
    if score >= 70 and confidence >= 65:
        return "A"
    if score >= 62 and confidence >= 58:
        return "B"
    return "PASS"


def analyze_market(
    meta: MarketMeta,
    rows: list[VoteContribution],
) -> dict[str, Any]:
    outcomes = sorted({row.outcome for row in rows})
    wallets = sorted({row.wallet for row in rows})
    total_capital = sum(row.capital for row in rows)

    raw_outcome, raw_agreement = weighted_choice(rows, "position_count")
    influence_outcome, influence_agreement = weighted_choice(rows, "effective_weight")
    capital_outcome, capital_agreement = weighted_choice(rows, "capital")
    specialist_outcome, specialist_agreement = weighted_choice(rows, "specialist_weight")

    leading_outcome = influence_outcome
    by_outcome_weight: dict[str, float] = defaultdict(float)
    by_outcome_wallets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_outcome_weight[row.outcome] += row.effective_weight
        by_outcome_wallets[row.outcome].add(row.wallet)

    ordered_outcomes = sorted(
        by_outcome_weight.items(), key=lambda item: (-item[1], item[0])
    )
    runner_up = ordered_outcomes[1][0] if len(ordered_outcomes) > 1 else None
    leading_wallet_count = len(by_outcome_wallets.get(leading_outcome, set()))

    institutional_rows = [row for row in rows if row.institutional_flag]
    standard_rows = [row for row in rows if not row.institutional_flag]

    institutional_outcome, institutional_agreement = weighted_choice(
        institutional_rows, "effective_weight"
    )
    standard_outcome, standard_agreement = weighted_choice(
        standard_rows, "effective_weight"
    )

    divergence = int(
        institutional_outcome != "UNKNOWN"
        and standard_outcome != "UNKNOWN"
        and institutional_outcome != standard_outcome
    )

    weights = [row.effective_weight for row in rows]
    ess = effective_sample_size(weights)
    wallet_count = len(wallets)

    agreement_score = (
        0.42 * influence_agreement
        + 0.23 * capital_agreement
        + 0.20 * specialist_agreement
        + 0.15 * raw_agreement
    )

    independent_confirmation = clamp(
        100.0 * min(1.0, math.log1p(wallet_count) / math.log(7.0))
    )
    effective_confirmation = clamp(
        100.0 * min(1.0, math.log1p(ess) / math.log(5.0))
    )
    classification_quality = meta.classification_confidence

    confidence = clamp(
        0.38 * independent_confirmation
        + 0.28 * effective_confirmation
        + 0.19 * classification_quality
        + 0.15 * min(influence_agreement, specialist_agreement)
        - (8.0 if divergence else 0.0)
    )

    score = clamp(
        0.72 * agreement_score
        + 0.18 * confidence
        + 0.10 * max(institutional_agreement, standard_agreement)
    )

    pass_reasons: list[str] = []
    if wallet_count < MIN_ACTIONABLE_WALLETS:
        pass_reasons.append("insufficient independent wallets")
    if ess < MIN_ACTIONABLE_EFFECTIVE_WALLETS:
        pass_reasons.append("one wallet dominates effective weight")
    if confidence < MIN_ACTIONABLE_CONFIDENCE:
        pass_reasons.append("consensus confidence below minimum")
    if leading_outcome == "UNKNOWN":
        pass_reasons.append("no valid leading outcome")
    if len(outcomes) < 2:
        pass_reasons.append("only one observed outcome side")
    if divergence and institutional_agreement < 65.0:
        pass_reasons.append("institutional and standard wallets disagree")

    actionable = not pass_reasons
    grade = consensus_grade(score, confidence, actionable)
    if grade == "PASS" and not pass_reasons:
        pass_reasons.append("signal strength below actionable grade")

    recommendation = leading_outcome if grade != "PASS" else "PASS"

    explanation = {
        "leading_outcome": leading_outcome,
        "agreement": {
            "raw_wallet": round(raw_agreement, 2),
            "influence_weighted": round(influence_agreement, 2),
            "capital_weighted": round(capital_agreement, 2),
            "specialist_weighted": round(specialist_agreement, 2),
        },
        "evidence": {
            "wallets": wallet_count,
            "effective_wallets": round(ess, 3),
            "capital": round(total_capital, 2),
            "institutional_wallets": len({r.wallet for r in institutional_rows}),
            "standard_wallets": len({r.wallet for r in standard_rows}),
            "domain": meta.domain,
            "subdomain": meta.subdomain,
            "classification_confidence": round(meta.classification_confidence, 2),
        },
        "institutional_consensus": {
            "outcome": institutional_outcome,
            "agreement": round(institutional_agreement, 2),
        },
        "standard_consensus": {
            "outcome": standard_outcome,
            "agreement": round(standard_agreement, 2),
        },
        "divergence": bool(divergence),
        "pass_reasons": pass_reasons,
    }

    return {
        "condition_id": meta.condition_id,
        "event_id": meta.event_id,
        "market_title": meta.title,
        "domain": meta.domain,
        "subdomain": meta.subdomain,
        "leading_outcome": leading_outcome,
        "runner_up_outcome": runner_up,
        "wallet_count": wallet_count,
        "outcome_count": len(outcomes),
        "effective_wallet_count": ess,
        "total_capital_committed": total_capital,
        "leading_wallet_count": leading_wallet_count,
        "raw_agreement_pct": raw_agreement,
        "influence_agreement_pct": influence_agreement,
        "capital_agreement_pct": capital_agreement,
        "specialist_agreement_pct": specialist_agreement,
        "institutional_outcome": institutional_outcome,
        "institutional_agreement_pct": institutional_agreement,
        "institutional_wallet_count": len({r.wallet for r in institutional_rows}),
        "standard_outcome": standard_outcome,
        "standard_agreement_pct": standard_agreement,
        "standard_wallet_count": len({r.wallet for r in standard_rows}),
        "institutional_retail_divergence": divergence,
        "consensus_score": score,
        "consensus_confidence": confidence,
        "consensus_grade": grade,
        "recommendation": recommendation,
        "pass_reason": "; ".join(pass_reasons) if pass_reasons else None,
        "explanation_json": json.dumps(explanation, sort_keys=True),
        "source_mode": rows[0].source_mode if rows else "UNKNOWN",
    }


def observed_price_expression(connection: sqlite3.Connection) -> str | None:
    columns = table_columns(connection, "positions")
    price_col = first_present(columns, ("current_price", "price", "average_price", "avg_price"))
    return price_col


def write_results(
    connection: sqlite3.Connection,
    current_run_id: str,
    votes: list[VoteContribution],
    results: list[dict[str, Any]],
    source_mode: str,
) -> None:
    now = utc_now()

    with connection:
        connection.execute("DELETE FROM consensus_votes")
        connection.execute("DELETE FROM market_consensus")

        connection.executemany(
            """
            INSERT INTO consensus_votes (
                condition_id, event_id, wallet, outcome, domain, subdomain,
                wallet_grade, domain_grade, position_count, capital_committed,
                wallet_market_allocation_pct, base_influence_score, domain_score,
                sample_confidence, event_influence_weight, capital_weight,
                influence_weight, specialist_weight, effective_weight,
                institutional_flag, source_mode, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    row.condition_id,
                    row.event_id,
                    row.wallet,
                    row.outcome,
                    row.domain,
                    row.subdomain,
                    row.wallet_grade,
                    row.domain_grade,
                    row.position_count,
                    row.capital,
                    row.wallet_market_allocation_pct,
                    row.base_influence_score,
                    row.domain_score,
                    row.sample_confidence,
                    row.event_influence_weight,
                    row.capital_weight,
                    row.influence_weight,
                    row.specialist_weight,
                    row.effective_weight,
                    row.institutional_flag,
                    row.source_mode,
                    now,
                )
                for row in votes
            ],
        )

        connection.executemany(
            """
            INSERT INTO market_consensus (
                condition_id, event_id, market_title, domain, subdomain,
                leading_outcome, runner_up_outcome, wallet_count, outcome_count,
                effective_wallet_count, total_capital_committed, leading_wallet_count,
                raw_agreement_pct, influence_agreement_pct, capital_agreement_pct,
                specialist_agreement_pct, institutional_outcome,
                institutional_agreement_pct, institutional_wallet_count,
                standard_outcome, standard_agreement_pct, standard_wallet_count,
                institutional_retail_divergence, consensus_score,
                consensus_confidence, consensus_grade, recommendation,
                pass_reason, explanation_json, source_mode, engine_version, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    result["condition_id"],
                    result["event_id"],
                    result["market_title"],
                    result["domain"],
                    result["subdomain"],
                    result["leading_outcome"],
                    result["runner_up_outcome"],
                    result["wallet_count"],
                    result["outcome_count"],
                    result["effective_wallet_count"],
                    result["total_capital_committed"],
                    result["leading_wallet_count"],
                    result["raw_agreement_pct"],
                    result["influence_agreement_pct"],
                    result["capital_agreement_pct"],
                    result["specialist_agreement_pct"],
                    result["institutional_outcome"],
                    result["institutional_agreement_pct"],
                    result["institutional_wallet_count"],
                    result["standard_outcome"],
                    result["standard_agreement_pct"],
                    result["standard_wallet_count"],
                    result["institutional_retail_divergence"],
                    result["consensus_score"],
                    result["consensus_confidence"],
                    result["consensus_grade"],
                    result["recommendation"],
                    result["pass_reason"],
                    result["explanation_json"],
                    result["source_mode"],
                    ENGINE_VERSION,
                    now,
                )
                for result in results
            ],
        )

        connection.executemany(
            """
            INSERT INTO consensus_signal_history (
                run_id, condition_id, event_id, leading_outcome,
                consensus_score, consensus_confidence, consensus_grade,
                wallet_count, effective_wallet_count, total_capital_committed,
                influence_agreement_pct, institutional_outcome, standard_outcome,
                institutional_retail_divergence, observed_price, source_mode, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    current_run_id,
                    result["condition_id"],
                    result["event_id"],
                    result["leading_outcome"],
                    result["consensus_score"],
                    result["consensus_confidence"],
                    result["consensus_grade"],
                    result["wallet_count"],
                    result["effective_wallet_count"],
                    result["total_capital_committed"],
                    result["influence_agreement_pct"],
                    result["institutional_outcome"],
                    result["standard_outcome"],
                    result["institutional_retail_divergence"],
                    None,
                    result["source_mode"],
                    now,
                )
                for result in results
            ],
        )

        actionable = sum(1 for result in results if result["consensus_grade"] != "PASS")
        divergent = sum(
            int(result["institutional_retail_divergence"]) for result in results
        )
        total_capital = sum(result["total_capital_committed"] for result in results)

        connection.execute(
            """
            INSERT INTO consensus_intelligence_runs (
                run_id, engine_version, markets_analyzed, votes_created,
                actionable_signals, pass_markets, divergent_markets,
                total_capital_analyzed, source_mode, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current_run_id,
                ENGINE_VERSION,
                len(results),
                len(votes),
                actionable,
                len(results) - actionable,
                divergent,
                total_capital,
                source_mode,
                now,
            ),
        )


def print_report(
    current_run_id: str,
    source_mode: str,
    votes: list[VoteContribution],
    results: list[dict[str, Any]],
) -> None:
    actionable = [r for r in results if r["consensus_grade"] != "PASS"]
    divergent = [r for r in results if r["institutional_retail_divergence"]]
    total_capital = sum(r["total_capital_committed"] for r in results)

    print("=" * 122)
    print("CONSENSUS INTELLIGENCE ENGINE COMPLETE")
    print("=" * 122)
    print(f"Database: {DATABASE_PATH}")
    print(f"Markets analyzed: {len(results)}")
    print(f"Wallet-outcome votes: {len(votes)}")
    print(f"Actionable signals: {len(actionable)}")
    print(f"PASS markets: {len(results) - len(actionable)}")
    print(f"Institutional/standard divergences: {len(divergent)}")
    print(f"Historical capital represented: ${total_capital:,.2f}")
    print(f"Position valuation source: {source_mode}")
    print(f"Run ID: {current_run_id}")

    print()
    print("Top consensus signals:")
    ranked = sorted(
        results,
        key=lambda r: (
            r["consensus_grade"] == "PASS",
            -r["consensus_score"],
            -r["consensus_confidence"],
            -r["wallet_count"],
        ),
    )[:30]
    for index, row in enumerate(ranked, start=1):
        reason = f" | pass={row['pass_reason']}" if row["pass_reason"] else ""
        print(
            f"{index:>2}. {row['market_title'][:54]:<54} | "
            f"{row['leading_outcome']:<12} | {row['consensus_grade']:<4} | "
            f"score={row['consensus_score']:6.2f} | "
            f"confidence={row['consensus_confidence']:6.2f} | "
            f"wallets={row['wallet_count']:>2} | "
            f"effective={row['effective_wallet_count']:5.2f} | "
            f"agreement={row['influence_agreement_pct']:6.2f}% | "
            f"capital=${row['total_capital_committed']:,.2f}"
            f"{reason}"
        )

    if divergent:
        print()
        print("Institutional versus standard divergences:")
        for index, row in enumerate(
            sorted(divergent, key=lambda r: -r["consensus_score"])[:20], start=1
        ):
            print(
                f"{index:>2}. {row['market_title'][:58]:<58} | "
                f"institutional={row['institutional_outcome']} "
                f"({row['institutional_agreement_pct']:.2f}%) | "
                f"standard={row['standard_outcome']} "
                f"({row['standard_agreement_pct']:.2f}%) | "
                f"grade={row['consensus_grade']}"
            )

    print()
    print("Next command:")
    print(
        "  python -m src.consensus_intelligence_engine 2>&1 "
        "| Tee-Object -FilePath consensus_intelligence_output.txt"
    )


def main() -> None:
    connection = connect_database()
    try:
        ensure_schema(connection)
        source = discover_position_source(connection)
        market_meta = load_market_meta(connection)
        raw_positions = load_raw_positions(connection, source, market_meta)
        wallet_profiles = load_wallet_profiles(connection)
        domain_profiles = load_domain_profiles(connection)
        event_profiles = load_event_profiles(connection)

        votes = build_votes(
            raw_positions=raw_positions,
            market_meta=market_meta,
            wallet_profiles=wallet_profiles,
            domain_profiles=domain_profiles,
            event_profiles=event_profiles,
            source_mode=source.source_mode,
        )

        grouped: dict[str, list[VoteContribution]] = defaultdict(list)
        for vote in votes:
            grouped[vote.condition_id].append(vote)

        results = [
            analyze_market(market_meta[condition_id], rows)
            for condition_id, rows in grouped.items()
        ]

        current_run_id = run_id()
        write_results(
            connection=connection,
            current_run_id=current_run_id,
            votes=votes,
            results=results,
            source_mode=source.source_mode,
        )
        print_report(current_run_id, source.source_mode, votes, results)
    finally:
        connection.close()


if __name__ == "__main__":
    main()