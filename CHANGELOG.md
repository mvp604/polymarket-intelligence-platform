# Changelog

## 0.1.0
Initial project framework.

## CORE-003 Sprint 3.0

- Added Platform Capability Registry.
- Added dependency validation and health checks.
- Added features, health, doctor, and test commands.

## CORE-003 Sprint 3.1

- Restricted pytest discovery to active tests.
- Excluded backups and sprint payloads.
- Hardened `python manage.py test`.

## CORE-003 Sprint 3.2 Phase 1

- Added immutable snapshot domain models.
- Added snapshot exceptions and typed identifiers.
- Added validation, serialization, and tests.

## CORE-003 Sprint 3.2 Phase 2

- Added loader, validator, storage, index, replay, and tests.

## CORE-003 Sprint 3.3

- Connected live positions and consensus data to snapshots.
- Added deterministic duplicate-run protection.
- Added create, list, and inspect snapshot commands.
- Added live SQLite integration tests.
