from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Immutable SQLite configuration."""

    sqlite_path: Path
    enable_foreign_keys: bool = True

    @property
    def connection_string(self) -> str:
        return str(self.sqlite_path)


DATABASE_SETTINGS = DatabaseSettings(
    sqlite_path=Path("database") / "polymarket.db",
)
