# Smart Money Intelligence v1

This phase converts Elite Wallet Intelligence into market-level signals.

## Capabilities

- Elite consensus detection
- Market heat scoring
- Weighted elite capital
- Leader wallet identification
- Disagreement detection
- Signal history
- Trend views
- Platform events
- Repository capability validator update

## Installation

Create a database snapshot:

```powershell
python tools/create_repository_snapshot.py
```

Install the schema:

```powershell
python tools/install_smart_money_intelligence_v1.py
```

Run tests:

```powershell
python -m pytest tests/test_smart_money_intelligence_v1.py -q
```

Run the engine:

```powershell
python src/smart_money_intelligence_v1.py
```

Run health:

```powershell
python src/smart_money_intelligence_v1_health.py
```

Refresh repository discovery and validate:

```powershell
python src/repository_schema_discovery.py
python src/engine_capability_validator.py
```

The included `config/engine_capabilities.json` replaces the outdated Elite
Wallet v1 requirements with the repository-native Elite Wallet v2 contract.
