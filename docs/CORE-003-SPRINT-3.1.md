# CORE-003 — Sprint 3.1

## Engineering Stabilization

Status: Implemented

- Restricts pytest discovery to active tests.
- Excludes backups and generated sprint payloads.
- Hardens `python manage.py test`.
- Tracks pytest in development requirements.

## Validation

```powershell
python manage.py test
```
