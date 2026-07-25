# Outcome Resolution & End-of-Day Reporting v1

This phase closes the intelligence loop by attaching final market outcomes to
signals and producing a complete daily performance report.

## Capabilities

- Final market outcome storage
- Signal result grading
- HIT / MISS / VOID / NO_ACTION classification
- Daily hit-rate reporting
- Grade-level performance
- Category-level performance
- Highest-conviction wins and misses
- Markdown daily reports
- Report history in SQLite
- Report-generated platform events

## Recommended data flow

1. Import or sync final market resolutions.
2. Settle matching Smart Money signals.
3. Generate the report for the resolved date.
4. Review high-conviction misses before changing thresholds.

## Installation

```powershell
python tools/create_repository_snapshot.py
python tools/install_outcome_resolution_eod_v1.py
python -m pytest tests/test_outcome_resolution_eod_v1.py -q
```

## Import final outcomes

Prepare a CSV using the included example:

```powershell
python tools/import_market_resolutions.py data/market_resolutions.csv
```

Required columns:

- market_id
- outcome
- final_result
- resolution_status
- resolution_source
- resolved_at

Accepted final results include:

- WIN
- LOSS
- VOID
- UNRESOLVED

## Generate a report

For today:

```powershell
python src/outcome_resolution_eod_reporting_v1.py
```

For a specific UTC report date:

```powershell
python src/outcome_resolution_eod_reporting_v1.py 2026-07-25
```

Generated reports are written to:

```text
reports/daily/polymarket_daily_report_YYYY-MM-DD.md
```

## Health check

```powershell
python src/outcome_resolution_eod_reporting_v1_health.py
```

## Future automation

The next phase should connect directly to official Polymarket resolution data
and schedule the report in the user's local timezone. Until that integration is
added, the included CSV importer provides a safe and auditable resolution path.
