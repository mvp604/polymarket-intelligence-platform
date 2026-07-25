from __future__ import annotations

from datetime import datetime

from .models import SnapshotMetadata
from .storage import SQLiteSnapshotStorage


class SnapshotIndex:
    def __init__(self, storage: SQLiteSnapshotStorage) -> None:
        self.storage = storage

    def all(self) -> tuple[SnapshotMetadata, ...]:
        return self.storage.list_metadata()

    def between(self, start: datetime, end: datetime) -> tuple[SnapshotMetadata, ...]:
        return tuple(item for item in self.all() if start <= item.created_at <= end)

    def latest(self) -> SnapshotMetadata | None:
        items = self.all()
        return items[-1] if items else None

    def find(self, snapshot_id: str) -> SnapshotMetadata | None:
        return next(
            (item for item in self.all() if str(item.snapshot_id) == snapshot_id),
            None,
        )
