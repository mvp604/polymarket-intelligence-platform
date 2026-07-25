class SnapshotError(Exception):
    """Base error for the snapshot subsystem."""


class SnapshotValidationError(SnapshotError):
    """Raised when a snapshot or snapshot component is invalid."""


class SnapshotStorageError(SnapshotError):
    """Raised when snapshot persistence fails."""


class SnapshotReplayError(SnapshotError):
    """Raised when historical replay cannot be completed."""


class SnapshotIntegrityError(SnapshotError):
    """Raised when snapshot integrity verification fails."""
