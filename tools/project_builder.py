from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


class BuildError(RuntimeError):
    """Raised when a project build fails."""


class ProjectBuilder:
    """Safely executes project changes from a JSON sprint manifest."""

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        if not (self.root / ".git").exists():
            raise BuildError("Repository root was not found.")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.backup_root = self.root / ".project_builder_backups" / stamp
        self.created: list[Path] = []
        self.backups: dict[Path, Path] = {}

    def execute(self, manifest_path: str | Path) -> None:
        manifest = self._load_manifest(manifest_path)
        actions = manifest["actions"]

        print(f"\nSprint {manifest['version']}: {manifest['name']}")

        try:
            for number, action in enumerate(actions, start=1):
                action_type = action["type"]
                print(f"[{number}/{len(actions)}] {action_type}")
                self._execute_action(action)
        except Exception:
            print("Build failed. Rolling back changes...")
            self.rollback()
            raise

        print("\nBuild completed successfully.")
        subprocess.run(["git", "status", "--short"], cwd=self.root, capture_output=True, text=True)

    def _load_manifest(self, manifest_path: str | Path) -> dict:
        path = Path(manifest_path)
        if not path.is_file():
            raise BuildError(f"Manifest not found: {path}")

        payload = json.loads(path.read_text(encoding="utf-8-sig"))

        if not payload.get("version"):
            raise BuildError("Manifest version is required.")
        if not payload.get("name"):
            raise BuildError("Manifest name is required.")
        if not isinstance(payload.get("actions"), list):
            raise BuildError("Manifest actions must be a list.")

        return payload

    def _execute_action(self, action: dict) -> None:
        action_type = action["type"]

        if action_type == "create_file":
            self.create_file(action["path"], action["content"])
        elif action_type == "replace_file":
            self.replace_file(action["path"], action["content"])
        elif action_type == "compile_python":
            self.run_command(
                [sys.executable, "-m", "compileall", "-q", *action["paths"]]
            )
        elif action_type == "run_tests":
            self.run_command([
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                action.get("directory", "tests"),
                "-p",
                action.get("pattern", "test*.py"),
                "-v",
            ])
        else:
            raise BuildError(f"Unsupported action: {action_type}")

    def create_file(self, relative_path: str, content: str) -> None:
        target = self.safe_path(relative_path)
        if target.exists():
            raise BuildError(f"Refusing to overwrite existing file: {target}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8",  )
        self.created.append(target)

    def replace_file(self, relative_path: str, content: str) -> None:
        target = self.safe_path(relative_path)

        if target.exists():
            backup = self.backup_root / target.relative_to(self.root)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
            self.backups[target] = backup
        else:
            self.created.append(target)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8",  )

    def safe_path(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()

        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise BuildError("Path escapes repository root.") from exc

        return target

    def run_command(self, command: list[str]) -> None:
        result = subprocess.run(command, cwd=self.root)
        if result.returncode != 0:
            raise BuildError(f"Command failed: {command}")

    def rollback(self) -> None:
        for target in reversed(self.created):
            if target.exists():
                target.unlink()

        for target, backup in self.backups.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a Polymarket platform sprint manifest."
    )
    parser.add_argument("manifest")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    try:
        ProjectBuilder(args.root).execute(args.manifest)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
