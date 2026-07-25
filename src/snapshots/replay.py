from __future__ import annotations

from datetime import datetime
from typing import Iterator

from .exceptions import SnapshotReplayError
from .models import Snapshot
from .storage import SQLiteSnapshotStorage


class SnapshotReplay:
    def __init__(self, storage: SQLiteSnapshotStorage) -> None:
        self.storage = storage

    def iterate(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Iterator[Snapshot]:
        for metadata in self.storage.list_metadata():
            if start is not None and metadata.created_at < start:
                continue
            if end is not None and metadata.created_at > end:
                continue
            try:
                yield self.storage.load(str(metadata.snapshot_id))
            except Exception as exc:
                raise SnapshotReplayError(
                    f"failed replay at snapshot {metadata.snapshot_id}: {exc}"
                ) from exc
