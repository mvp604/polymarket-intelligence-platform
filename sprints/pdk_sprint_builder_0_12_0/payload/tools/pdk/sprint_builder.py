"""Generate repeatable sprint packages."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


class SprintBuilderError(RuntimeError):
    """Base sprint builder error."""


class SprintAlreadyExistsError(SprintBuilderError):
    """Raised when a sprint already exists."""


@dataclass(frozen=True, slots=True)
class SprintPaths:
    root: Path
    manifest: Path
    source: Path
    test: Path
    readme: Path


class SprintBuilder:
    """Generate deterministic runtime sprint packages."""

    NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
    VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

    def __init__(self, repository_root: Path) -> None:
        root = repository_root.resolve()

        if not root.is_dir():
            raise ValueError(
                f"Invalid repository root: {root}"
            )

        self.repository_root = root

    def create_runtime_module(
        self,
        module_name: str,
        *,
        version: str,
        overwrite: bool = False,
    ) -> SprintPaths:
        name = self._normalize_name(module_name)
        version = self._normalize_version(version)

        sprint_name = (
            f"runtime_{name}_"
            f"{version.replace('.', '_')}"
        )

        sprint_root = (
            self.repository_root
            / "sprints"
            / sprint_name
        )

        if sprint_root.exists():
            if not overwrite:
                raise SprintAlreadyExistsError(
                    f"Sprint already exists: {sprint_root}"
                )

            shutil.rmtree(sprint_root)

        runtime_payload = (
            sprint_root
            / "payload"
            / "src"
            / "runtime"
        )

        test_payload = (
            sprint_root
            / "payload"
            / "tests"
            / "runtime"
        )

        runtime_payload.mkdir(
            parents=True,
            exist_ok=True,
        )

        test_payload.mkdir(
            parents=True,
            exist_ok=True,
        )

        source = runtime_payload / f"{name}.py"
        test = test_payload / f"test_{name}.py"
        manifest = sprint_root / "manifest.json"
        readme = sprint_root / "README.md"

        source.write_text(
            self._source_template(name),
            encoding="utf-8",
        )

        test.write_text(
            self._test_template(name),
            encoding="utf-8",
        )

        readme.write_text(
            self._readme_template(
                sprint_name,
                name,
                version,
            ),
            encoding="utf-8",
        )

        self._write_manifest(
            manifest,
            sprint_name,
            name,
        )

        return SprintPaths(
            root=sprint_root,
            manifest=manifest,
            source=source,
            test=test,
            readme=readme,
        )

    def validation_commands(
        self,
    ) -> tuple[tuple[str, ...], ...]:
        return (
            (
                "python",
                "-m",
                "compileall",
                "-q",
                "src",
                "tools",
                "tests",
            ),
            (
                "python",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-v",
            ),
        )

    def _write_manifest(
        self,
        path: Path,
        sprint_name: str,
        module_name: str,
    ) -> None:
        manifest = {
            "name": sprint_name,
            "files": [
                {
                    "source": (
                        "payload/src/runtime/"
                        f"{module_name}.py"
                    ),
                    "target": (
                        "src/runtime/"
                        f"{module_name}.py"
                    ),
                },
                {
                    "source": (
                        "payload/tests/runtime/"
                        f"test_{module_name}.py"
                    ),
                    "target": (
                        "tests/runtime/"
                        f"test_{module_name}.py"
                    ),
                },
            ],
            "commands": [
                [
                    "python",
                    "-m",
                    "py_compile",
                    f"src/runtime/{module_name}.py",
                    (
                        "tests/runtime/"
                        f"test_{module_name}.py"
                    ),
                ],
                [
                    "python",
                    "-m",
                    "unittest",
                    (
                        "tests.runtime."
                        f"test_{module_name}"
                    ),
                    "-v",
                ],
                [
                    "python",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-v",
                ],
            ],
        }

        path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def _normalize_name(
        cls,
        value: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                "module_name must be a string."
            )

        normalized = (
            value.strip()
            .lower()
            .replace("-", "_")
        )

        if not cls.NAME_PATTERN.fullmatch(
            normalized
        ):
            raise ValueError(
                "Invalid runtime module name."
            )

        return normalized

    @classmethod
    def _normalize_version(
        cls,
        value: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                "version must be a string."
            )

        normalized = value.strip()

        if not cls.VERSION_PATTERN.fullmatch(
            normalized
        ):
            raise ValueError(
                "Version must use MAJOR.MINOR.PATCH."
            )

        return normalized

    @staticmethod
    def _class_name(
        module_name: str,
    ) -> str:
        return "".join(
            part.capitalize()
            for part in module_name.split("_")
        )

    @classmethod
    def _source_template(
        cls,
        module_name: str,
    ) -> str:
        class_name = cls._class_name(
            module_name
        )

        return f'''"""{class_name} runtime component."""

from __future__ import annotations


class {class_name}:
    """TODO: Implement the {module_name} component."""

    def validate(self) -> None:
        """Validate the component."""
'''

    @classmethod
    def _test_template(
        cls,
        module_name: str,
    ) -> str:
        class_name = cls._class_name(
            module_name
        )

        return f'''"""Tests for {module_name}."""

import unittest

from src.runtime.{module_name} import {class_name}


class {class_name}Tests(unittest.TestCase):
    def test_component_can_be_created(self) -> None:
        component = {class_name}()

        self.assertIsInstance(
            component,
            {class_name},
        )

    def test_validate_completes(self) -> None:
        component = {class_name}()

        self.assertIsNone(
            component.validate()
        )


if __name__ == "__main__":
    unittest.main()
'''

    @staticmethod
    def _readme_template(
        sprint_name: str,
        module_name: str,
        version: str,
    ) -> str:
        return (
            f"# {sprint_name}\n\n"
            f"Module: `{module_name}`\n\n"
            f"Version: `{version}`\n"
        )