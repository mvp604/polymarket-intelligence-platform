# Repository Compatibility & Schema Discovery

This phase does not alter the live database schema. It inventories the
repository and database exactly as they exist before any further repair.

## Why this phase exists

The live project contains historical schemas that differ from newer assumptions:

- `schema_migrations` exists without `migration_id`
- `event_consumers` exists without `enabled`
- legacy and backup tables are present
- the Elite Wallet schema is partially incompatible

The compatibility layer therefore discovers names and columns instead of
assuming them.

## Commands

Create a safe SQLite backup:

```powershell
python tools/create_repository_snapshot.py
```

Discover the entire schema:

```powershell
python src/repository_schema_discovery.py
```

This creates:

```text
reports/repository_compatibility.json
```

Print the compatibility report:

```powershell
python src/repository_compatibility_report.py
```

Validate engine requirements:

```powershell
python src/engine_capability_validator.py
```

A blocked result is expected until the Elite Wallet schema is repaired. The
validator is diagnostic and does not modify data.

## Tests

```powershell
python -m pytest tests/test_repository_compatibility.py -q
```

## Safety

No tool in this phase drops, renames, or changes live tables. The only write
operation is creating a database backup and writing reports.
