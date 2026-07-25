from __future__ import annotations

import sqlite3
from pathlib import Path

from src.config.database import (
    DATABASE_SETTINGS,
    DatabaseSettings,
)
from src.core.exceptions import ConfigurationError, DatabaseError


DEFAULT_BUSY_TIMEOUT_MS = 30_000


class DatabaseConnectionFactory:
    """
    Creates consistently configured SQLite connections.

    Repositories and engines should not call sqlite3.connect directly.
    """

    def __init__(
        self,
        settings: DatabaseSettings = DATABASE_SETTINGS,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        enable_wal: bool = True,
    ) -> None:
        if busy_timeout_ms < 0:
            raise ConfigurationError(
                "busy_timeout_ms cannot be negative."
            )

        self._settings = settings
        self._busy_timeout_ms = busy_timeout_ms
        self._enable_wal = enable_wal

    @property
    def database_path(self) -> Path:
        return Path(self._settings.sqlite_path)

    def create(
        self,
        *,
        read_only: bool = False,
    ) -> sqlite3.Connection:
        database_path = self.database_path

        if read_only and not database_path.exists():
            raise DatabaseError(
                f"Read-only database does not exist: {database_path}"
            )

        if not read_only:
            database_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        try:
            if read_only:
                connection = sqlite3.connect(
                    f"file:{database_path.resolve()}?mode=ro",
                    uri=True,
                    timeout=max(
                        1.0,
                        self._busy_timeout_ms / 1000,
                    ),
                )
            else:
                connection = sqlite3.connect(
                    database_path,
                    timeout=max(
                        1.0,
                        self._busy_timeout_ms / 1000,
                    ),
                )

            connection.row_factory = sqlite3.Row

            connection.execute(
                f"PRAGMA busy_timeout = {self._busy_timeout_ms}"
            )

            if self._settings.enable_foreign_keys:
                connection.execute("PRAGMA foreign_keys = ON")

            if self._enable_wal and not read_only:
                connection.execute("PRAGMA journal_mode = WAL")

            return connection

        except sqlite3.Error as error:
            raise DatabaseError(
                f"Unable to open database {database_path}: {error}"
            ) from error