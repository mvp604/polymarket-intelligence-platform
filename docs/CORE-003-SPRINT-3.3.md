# CORE-003 Sprint 3.3 — Live Snapshot Integration

Implemented:

- Live SQLite adapter for current wallet positions
- Market-state construction with metadata fallback
- Latest consensus-history adapter
- Deterministic source fingerprinting
- Duplicate-run protection
- Live snapshot orchestration service
- Snapshot create, list, and inspect CLI
- Live integration test coverage

Commands:

```powershell
python snapshot_manage.py create
python snapshot_manage.py list
python snapshot_manage.py inspect <snapshot-id>
```

Optional custom database:

```powershell
python snapshot_manage.py --database database/polymarket.db create
```
