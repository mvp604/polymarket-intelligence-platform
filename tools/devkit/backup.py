"""Backup utilities for automated project changes."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def backup_files(
    project_root: Path,
    paths: list[Path],
) -> Path | None:
    """Back up existing files while preserving project-relative paths."""

    existing_paths = [
        path
        for path in paths
        if path.exists() and path.is_file()
    ]

    if not existing_paths:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_root = (
        project_root
        / ".devkit_backups"
        / timestamp
    )

    backup_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    for source in existing_paths:
        relative_path = source.resolve().relative_to(
            project_root.resolve()
        )

        destination = backup_root / relative_path

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

    return backup_root
