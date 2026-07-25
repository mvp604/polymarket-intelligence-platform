from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import HealthCheckResult, HealthStatus


def directory_exists(name: str, path: Path):
    def check() -> HealthCheckResult:
        if path.is_dir():
            return HealthCheckResult(name, HealthStatus.HEALTHY, f"Directory exists: {path}")
        return HealthCheckResult(name, HealthStatus.UNHEALTHY, f"Missing directory: {path}")
    return check


def file_exists(name: str, path: Path):
    def check() -> HealthCheckResult:
        if path.is_file():
            return HealthCheckResult(name, HealthStatus.HEALTHY, f"File exists: {path}")
        return HealthCheckResult(name, HealthStatus.UNHEALTHY, f"Missing file: {path}")
    return check


def sqlite_database_accessible(name: str, path: Path):
    def check() -> HealthCheckResult:
        if not path.is_file():
            return HealthCheckResult(name, HealthStatus.DEGRADED, f"Database file not found: {path}")
        try:
            with sqlite3.connect(path) as connection:
                connection.execute("SELECT 1").fetchone()
            return HealthCheckResult(name, HealthStatus.HEALTHY, f"SQLite accessible: {path}")
        except sqlite3.Error as exc:
            return HealthCheckResult(name, HealthStatus.UNHEALTHY, f"SQLite error: {exc}")
    return check
