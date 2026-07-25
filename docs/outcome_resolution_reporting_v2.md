# Outcome Resolution & Reporting v2

Version 2 repairs the two integration failures observed in v1:

1. A partially created `market_resolutions` table caused the migration to fail
   when an index referenced the missing `resolved_at` column.
2. Direct execution of the CSV importer could not import the `src` package.

## Improvements

- Repairs missing columns in partially created v1 tables
- Idempotent schema installation
- Direct-script import path support
- Daily, weekly, and monthly reports
- Signal settlement and hit-rate views
- Clean adapter boundary for official Polymarket resolution syncing
- Health checks that repair before validating

## Install and repair

```powershell
python tools/create_repository_snapshot.py
python tools/install_outcome_resolution_reporting_v2.py
python -m pytest tests/test_outcome_resolution_reporting_v2.py -q
python src/outcome_resolution_reporting_v2_health.py
```

## Import existing CSV outcomes

```powershell
python tools/import_market_resolutions_v2.py data/market_resolutions.csv
```

## Generate reports

Daily:

```powershell
python src/outcome_resolution_reporting_v2.py --report-type DAILY --date 2026-07-25
```

Weekly:

```powershell
python src/outcome_resolution_reporting_v2.py --report-type WEEKLY --date 2026-07-25
```

Monthly:

```powershell
python src/outcome_resolution_reporting_v2.py --report-type MONTHLY --date 2026-07-25
```

Reports are written to:

```text
reports/performance/
```

## Official resolution sync

`src/polymarket_resolution_sync_v2.py` is the repository adapter boundary.
Connect it to the project's tested official Polymarket API client. This keeps
external API details separate from settlement and reporting logic.
