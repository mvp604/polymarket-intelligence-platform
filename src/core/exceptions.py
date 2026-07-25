from __future__ import annotations


class PlatformError(Exception):
    """Base exception for the Polymarket Intelligence Platform."""


class ConfigurationError(PlatformError):
    """Raised when platform configuration is invalid."""


class InfrastructureError(PlatformError):
    """Base exception for infrastructure-layer failures."""


class DatabaseError(InfrastructureError):
    """Raised when a database operation fails."""


class TransactionError(DatabaseError):
    """Raised when a database transaction cannot be completed."""


class RepositoryError(InfrastructureError):
    """Raised when a repository operation fails."""


class ValidationError(PlatformError):
    """Raised when platform input or state is invalid."""