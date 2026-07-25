# Outcome Resolution & Reporting v2.1

This compatibility release repairs legacy SQLite tables that were created without
the composite uniqueness required by `ON CONFLICT(market_id, outcome)`.

## Repairs

- Adds missing v2 columns.
- Deduplicates legacy logical records, preserving the newest SQLite row.
- Creates unique indexes for market resolutions, resolved signals, and reports.
- Keeps installation idempotent.
- Adds a regression test that reproduces and verifies the original importer failure.

## Install

```powershell
python tools/install_outcome_resolution_reporting_v2.py
python -m pytest tests/test_outcome_resolution_reporting_v2.py -q
python tools/import_market_resolutions_v2.py data/market_resolutions.csv
python src/outcome_resolution_reporting_v2_health.py
```
