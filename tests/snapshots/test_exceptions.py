from src.snapshots import SnapshotError, SnapshotIntegrityError, SnapshotReplayError, SnapshotStorageError, SnapshotValidationError


def test_snapshot_exception_hierarchy():
    assert issubclass(SnapshotValidationError, SnapshotError)
    assert issubclass(SnapshotStorageError, SnapshotError)
    assert issubclass(SnapshotReplayError, SnapshotError)
    assert issubclass(SnapshotIntegrityError, SnapshotError)
