# Platform v0.5.0 — Database Schema Audit

## Purpose

This milestone audits the actual Polymarket Intelligence Platform SQLite database before repository classes are generated.

## Safety

- The live database is opened using SQLite read-only mode.
- `PRAGMA query_only = ON` is enabled.
- No schema migrations are performed.
- No production rows are inserted, updated, or deleted.
- Existing files changed by the installer are backed up automatically.
- Files are written atomically using temporary files.

## Generated Outputs

- `docs/database_schema_specification_v1.md`
- `artifacts/database_schema_specification_v1.json`

## Audit Coverage

- SQLite integrity check
- Table names
- Table row counts
- Columns
- Declared data types
- Primary keys
- Default values
- Null constraints
- Foreign keys
- Delete and update behavior
- Indexes
- Views
- Triggers
- Original create SQL
- Source-code references to each table

## Repository Gate

The repository implementation package must use the generated specification rather than assumed table or column names.