# Elite Wallet Intelligence v2

This phase aligns the Elite Wallet engine with the repository's existing
`elite_wallet_profiles` schema. It preserves that table and adds only the
missing supporting history, category, ranking, and trend objects.

## Important

Do not run the older Elite Wallet repair scripts before this phase. They were
written for a different schema and may rename the current profile table.

## Files

- `src/elite_wallet_intelligence_v2.py`
- `src/elite_wallet_intelligence_v2_health.py`
- `tools/install_elite_wallet_v2_schema.py`
- `migrations/elite_wallet_v2_supporting_schema.sql`
- `config/elite_wallet_v2.json`
- `tests/test_elite_wallet_intelligence_v2.py`

## Installation

Create a database snapshot first:

```powershell
python tools/create_repository_snapshot.py
```

Install only the supporting objects:

```powershell
python tools/install_elite_wallet_v2_schema.py
```

Run tests:

```powershell
python -m pytest tests/test_elite_wallet_intelligence_v2.py -q
```

Run the engine:

```powershell
python src/elite_wallet_intelligence_v2.py
```

Run health:

```powershell
python src/elite_wallet_intelligence_v2_health.py
```

Run capability validation again:

```powershell
python src/repository_schema_discovery.py
python src/engine_capability_validator.py
```

## Outputs

The engine updates the existing `elite_wallet_profiles`, writes deduplicated
history snapshots, calculates category profiles, publishes profile-update
events when the event schema is compatible, and provides ranking and trend
views.
