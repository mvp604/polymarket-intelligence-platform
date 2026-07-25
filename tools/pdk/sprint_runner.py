"""Safe, transactional sprint automation for repository changes.

A sprint is described by a JSON manifest containing staged source files,
target repository paths, and validation commands. Target files are written
atomically. If any operation or validation command fails, every changed file
is restored automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class SprintRunnerError(RuntimeError):
    """Base exception for sprint execution failures."""


class ManifestValidationError(SprintRunnerError):
    """Raised when a sprint manifest is malformed or unsafe."""


class SprintValidationError(SprintRunnerError):
    """Raised when a sprint validation command fails."""

    def __init__(
        self,
        command: tuple[str, ...],
        returncode: int,
    ) -> None:
        self.command = command
        self.returncode = returncode

        super().__init__(
            "Sprint validation failed with exit code "
            f"{returncode}: {' '.join(command)}"
        )


@dataclass(frozen=True, slots=True)
class FileOperation:
    """One staged source file copied to one repository target."""

    source: Path
    target: Path


@dataclass(frozen=True, slots=True)
class SprintManifest:
    """Validated sprint definition."""

    name: str
    files: tuple[FileOperation, ...]
    commands: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class SprintResult:
    """Summary of a successfully applied sprint."""

    name: str
    changed_files: tuple[Path, ...]
    commands_run: tuple[tuple[str, ...], ...]
    backup_directory: Path


class SprintRunner:
    """Apply repository changes transactionally and validate them."""

    def __init__(
        self,
        repository_root: Path,
        *,
        backup_root: Path | None = None,
    ) -> None:
        root = repository_root.resolve()

        if not root.exists():
            raise ValueError(
                f"Repository root does not exist: {root}"
            )

        if not root.is_dir():
            raise ValueError(
                f"Repository root is not a directory: {root}"
            )

        self._repository_root = root
        self._backup_root = (
            backup_root.resolve()
            if backup_root is not None
            else root / ".runtime_backups"
        )

    @property
    def repository_root(self) -> Path:
        return self._repository_root

    def load_manifest(self, manifest_path: Path) -> SprintManifest:
        """Load and validate a JSON sprint manifest."""

        absolute_manifest = self._resolve_existing_file(
            manifest_path,
            label="Manifest",
        )

        try:
            raw_data = json.loads(
                absolute_manifest.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ManifestValidationError(
                f"Invalid JSON manifest: {error}"
            ) from error

        if not isinstance(raw_data, dict):
            raise ManifestValidationError(
                "Sprint manifest must contain a JSON object."
            )

        return self.parse_manifest(
            raw_data,
            manifest_directory=absolute_manifest.parent,
        )

    def parse_manifest(
        self,
        data: Mapping[str, object],
        *,
        manifest_directory: Path,
    ) -> SprintManifest:
        """Validate an already-loaded manifest mapping."""

        name = data.get("name")

        if not isinstance(name, str) or not name.strip():
            raise ManifestValidationError(
                "Manifest field 'name' must be a non-empty string."
            )

        raw_files = data.get("files")

        if not isinstance(raw_files, list) or not raw_files:
            raise ManifestValidationError(
                "Manifest field 'files' must be a non-empty list."
            )

        operations: list[FileOperation] = []
        target_keys: set[str] = set()

        for index, raw_file in enumerate(raw_files):
            if not isinstance(raw_file, dict):
                raise ManifestValidationError(
                    f"Manifest file entry {index} must be an object."
                )

            source_value = raw_file.get("source")
            target_value = raw_file.get("target")

            if not isinstance(source_value, str) or not source_value.strip():
                raise ManifestValidationError(
                    f"Manifest file entry {index} has an invalid source."
                )

            if not isinstance(target_value, str) or not target_value.strip():
                raise ManifestValidationError(
                    f"Manifest file entry {index} has an invalid target."
                )

            source = self._safe_resolve(
                manifest_directory,
                Path(source_value),
                must_exist=True,
                label="Sprint source",
            )

            target = self._safe_resolve(
                self._repository_root,
                Path(target_value),
                must_exist=False,
                label="Sprint target",
            )

            target_key = os.path.normcase(str(target))

            if target_key in target_keys:
                raise ManifestValidationError(
                    f"Duplicate sprint target: {target_value}"
                )

            target_keys.add(target_key)
            operations.append(
                FileOperation(
                    source=source,
                    target=target,
                )
            )

        raw_commands = data.get("commands", [])

        if not isinstance(raw_commands, list):
            raise ManifestValidationError(
                "Manifest field 'commands' must be a list."
            )

        commands: list[tuple[str, ...]] = []

        for index, raw_command in enumerate(raw_commands):
            if (
                not isinstance(raw_command, list)
                or not raw_command
                or not all(
                    isinstance(argument, str) and argument
                    for argument in raw_command
                )
            ):
                raise ManifestValidationError(
                    f"Manifest command {index} must be a non-empty "
                    "list of non-empty strings."
                )

            commands.append(tuple(raw_command))

        return SprintManifest(
            name=name.strip(),
            files=tuple(operations),
            commands=tuple(commands),
        )

    def apply(
        self,
        manifest: SprintManifest,
    ) -> SprintResult:
        """Apply a sprint and roll it back automatically on failure."""

        backup_directory = Path(
            tempfile.mkdtemp(
                prefix=f"{self._safe_name(manifest.name)}_",
                dir=self._prepare_backup_root(),
            )
        )

        existing_backups: dict[Path, Path] = {}
        created_targets: list[Path] = []
        changed_targets: list[Path] = []

        try:
            for operation in manifest.files:
                target = operation.target

                if target.exists():
                    relative_target = target.relative_to(
                        self._repository_root
                    )
                    backup_path = backup_directory / relative_target
                    backup_path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    shutil.copy2(target, backup_path)
                    existing_backups[target] = backup_path
                else:
                    created_targets.append(target)

                self._atomic_copy(
                    operation.source,
                    target,
                )
                changed_targets.append(target)

            for command in manifest.commands:
                self._run_command(command)

        except BaseException:
            self._rollback(
                existing_backups=existing_backups,
                created_targets=created_targets,
            )
            raise

        return SprintResult(
            name=manifest.name,
            changed_files=tuple(changed_targets),
            commands_run=manifest.commands,
            backup_directory=backup_directory,
        )

    def apply_manifest_file(
        self,
        manifest_path: Path,
    ) -> SprintResult:
        """Load and apply a manifest in one operation."""

        return self.apply(
            self.load_manifest(manifest_path)
        )

    def _run_command(
        self,
        command: Sequence[str],
    ) -> None:
        completed = subprocess.run(
            tuple(command),
            cwd=self._repository_root,
            check=False,
        )

        if completed.returncode != 0:
            raise SprintValidationError(
                tuple(command),
                completed.returncode,
            )

    def _rollback(
        self,
        *,
        existing_backups: Mapping[Path, Path],
        created_targets: Iterable[Path],
    ) -> None:
        for target in reversed(tuple(created_targets)):
            if target.exists():
                target.unlink()
                self._remove_empty_parents(target.parent)

        for target, backup in existing_backups.items():
            self._atomic_copy(backup, target)

    def _remove_empty_parents(
        self,
        directory: Path,
    ) -> None:
        current = directory

        while current != self._repository_root:
            try:
                current.rmdir()
            except OSError:
                return

            current = current.parent

    def _atomic_copy(
        self,
        source: Path,
        target: Path,
    ) -> None:
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )

        temporary_path = Path(temporary_name)

        try:
            with os.fdopen(descriptor, "wb") as destination:
                with source.open("rb") as source_file:
                    shutil.copyfileobj(
                        source_file,
                        destination,
                    )

                destination.flush()
                os.fsync(destination.fileno())

            os.replace(
                temporary_path,
                target,
            )
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise

    def _resolve_existing_file(
        self,
        path: Path,
        *,
        label: str,
    ) -> Path:
        absolute_path = (
            path.resolve()
            if path.is_absolute()
            else (self._repository_root / path).resolve()
        )

        if not absolute_path.exists():
            raise ManifestValidationError(
                f"{label} does not exist: {absolute_path}"
            )

        if not absolute_path.is_file():
            raise ManifestValidationError(
                f"{label} is not a file: {absolute_path}"
            )

        return absolute_path

    @staticmethod
    def _safe_name(value: str) -> str:
        normalized = "".join(
            character
            if character.isalnum() or character in {"-", "_"}
            else "_"
            for character in value.strip()
        )

        return normalized or "sprint"

    def _safe_resolve(
        self,
        base_directory: Path,
        relative_path: Path,
        *,
        must_exist: bool,
        label: str,
    ) -> Path:
        if relative_path.is_absolute():
            raise ManifestValidationError(
                f"{label} must use a relative path: {relative_path}"
            )

        resolved_base = base_directory.resolve()
        resolved_path = (
            resolved_base / relative_path
        ).resolve()

        try:
            resolved_path.relative_to(resolved_base)
        except ValueError as error:
            raise ManifestValidationError(
                f"{label} escapes its allowed directory: "
                f"{relative_path}"
            ) from error

        if must_exist:
            if not resolved_path.exists():
                raise ManifestValidationError(
                    f"{label} does not exist: {resolved_path}"
                )

            if not resolved_path.is_file():
                raise ManifestValidationError(
                    f"{label} is not a file: {resolved_path}"
                )

        return resolved_path

    def _prepare_backup_root(self) -> str:
        self._backup_root.mkdir(
            parents=True,
            exist_ok=True,
        )
        return str(self._backup_root)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a staged coding sprint transactionally and run "
            "its validation commands."
        )
    )

    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to the sprint JSON manifest.",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Defaults to the current directory.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(argv)

    runner = SprintRunner(
        arguments.repository_root
    )

    try:
        result = runner.apply_manifest_file(
            arguments.manifest
        )
    except SprintRunnerError as error:
        print(
            f"Sprint failed: {error}",
            file=sys.stderr,
        )
        print(
            "All changed files were rolled back.",
            file=sys.stderr,
        )
        return 1

    print("")
    print("=" * 56)
    print(f"Sprint completed: {result.name}")
    print("=" * 56)
    print("")

    print("Changed files:")
    for changed_file in result.changed_files:
        print(
            "  "
            + str(
                changed_file.relative_to(
                    runner.repository_root
                )
            )
        )

    print("")
    print(f"Validation commands run: {len(result.commands_run)}")
    print(f"Backup directory: {result.backup_directory}")
    print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())