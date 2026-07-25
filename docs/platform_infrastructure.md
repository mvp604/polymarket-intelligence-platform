# Platform Infrastructure and Migration Framework

This phase adds safe database operations before additional intelligence engines
are introduced.

## Included commands

### Repair the partially applied Elite Wallet schema

```powershell
python tools/repair_elite_wallet_schema.py
```

The repair preserves an incompatible existing table by renaming it to:

```text
elite_wallet_profiles_legacy_YYYYMMDD_HHMMSS
```

It does not silently delete the earlier data.

### Apply migrations transactionally

```powershell
python src/migration_runner.py
```

The runner:

- discovers SQL migrations in filename order
- records checksums
- rejects modified migrations already applied
- applies each migration in a transaction
- rolls back the entire migration on failure
- stores every success and failure attempt

### Inspect the database

```powershell
python src/database_inspector.py
```

### Inspect platform events and consumers

```powershell
python src/event_bus_inspector.py
```

### Run all platform health checks

```powershell
python src/platform_health.py
```

## First repair sequence

Your database already contains migrations 001–005 but did not previously track
them. Baseline those existing migrations before applying migration 006.

```powershell
python tools/baseline_existing_migrations.py
python tools/repair_elite_wallet_schema.py
python src/migration_runner.py
python src/elite_wallet_intelligence_engine.py
python src/elite_wallet_intelligence_health.py
python src/database_inspector.py
python src/event_bus_inspector.py
python src/platform_health.py
```

## Important

Do not edit an already applied migration after the migration runner has recorded
its checksum. Add a new numbered migration instead.
