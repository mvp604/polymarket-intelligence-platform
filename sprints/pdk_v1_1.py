"""Upgrade the Platform Development Kit with template rendering."""

from tools.pdk import Sprint


ACTIONS_SOURCE = '''"""Typed actions supported by the Platform Development Kit."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class CreateFile:
    """Create or safely overwrite a UTF-8 source file."""

    path: Path
    content: str
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class RenderTemplate:
    """Render a template into a UTF-8 output file."""

    template_path: Path
    output_path: Path
    values: Mapping[str, object]
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class CompilePython:
    """Compile Python paths to validate syntax."""

    paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class RunTests:
    """Run unittest discovery."""

    directory: Path
    pattern: str = "test*.py"
    verbose: bool = True


@dataclass(frozen=True, slots=True)
class GitDiffCheck:
    """Run Git whitespace validation."""


SprintAction = (
    CreateFile
    | RenderTemplate
    | CompilePython
    | RunTests
    | GitDiffCheck
)
'''


TEMPLATES_SOURCE = '''"""Template loading and deterministic rendering."""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Mapping


class TemplateRenderError(RuntimeError):
    """Raised when a template cannot be rendered safely."""


def render_template(
    template_path: Path,
    values: Mapping[str, object],
) -> str:
    """Render a UTF-8 template using strict dollar substitutions."""

    if not template_path.exists():
        raise TemplateRenderError(
            f"Template does not exist: {template_path}"
        )

    if not template_path.is_file():
        raise TemplateRenderError(
            f"Template path is not a file: {template_path}"
        )

    try:
        source = template_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise TemplateRenderError(
            f"Template is not valid UTF-8: {template_path}"
        ) from error

    normalized_values = {
        str(key): str(value)
        for key, value in values.items()
    }

    try:
        return Template(source).substitute(normalized_values)
    except KeyError as error:
        missing_name = str(error.args[0])

        raise TemplateRenderError(
            f"Missing template value '{missing_name}' "
            f"for {template_path}"
        ) from error
    except ValueError as error:
        raise TemplateRenderError(
            f"Invalid template syntax in {template_path}: {error}"
        ) from error
'''


EXECUTOR_SOURCE = '''"""Safe sprint execution with automatic rollback."""

from __future__ import annotations

import compileall
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .actions import (
    CompilePython,
    CreateFile,
    GitDiffCheck,
    RenderTemplate,
    RunTests,
    SprintAction,
)
from .templates import render_template


class SprintExecutionError(RuntimeError):
    """Raised when a PDK sprint cannot be completed safely."""


@dataclass(slots=True)
class _FileBackup:
    path: Path
    existed: bool
    content: bytes | None


class SprintExecutor:
    """Execute a collection of typed sprint actions."""

    def __init__(self, root: Path | str = ".") -> None:
        self.root = Path(root).resolve()
        self._backups: list[_FileBackup] = []

    def execute(
        self,
        *,
        name: str,
        version: str,
        actions: tuple[SprintAction, ...],
    ) -> None:
        """Execute all actions and roll back writes on failure."""

        print()
        print(f"Sprint {version}: {name}")
        print("=" * max(20, len(name) + len(version) + 10))

        try:
            total = len(actions)

            for index, action in enumerate(actions, start=1):
                print(
                    f"[{index}/{total}] "
                    f"{type(action).__name__}"
                )
                self._execute_action(action)

        except Exception as error:
            print()
            print("Sprint failed. Rolling back file changes...")
            self._rollback()

            if isinstance(error, SprintExecutionError):
                raise

            raise SprintExecutionError(str(error)) from error

        self._backups.clear()

        print()
        print("Sprint completed successfully.")

    def _execute_action(self, action: SprintAction) -> None:
        if isinstance(action, CreateFile):
            self._create_file(action)
            return

        if isinstance(action, RenderTemplate):
            self._render_template(action)
            return

        if isinstance(action, CompilePython):
            self._compile_python(action)
            return

        if isinstance(action, RunTests):
            self._run_tests(action)
            return

        if isinstance(action, GitDiffCheck):
            self._git_diff_check()
            return

        raise SprintExecutionError(
            f"Unsupported sprint action: {type(action).__name__}"
        )

    def _create_file(self, action: CreateFile) -> None:
        path = self._resolve(action.path)

        self._write_file(
            path=path,
            content=action.content,
            overwrite=action.overwrite,
            display_path=action.path,
        )

    def _render_template(
        self,
        action: RenderTemplate,
    ) -> None:
        template_path = self._resolve(action.template_path)
        output_path = self._resolve(action.output_path)

        content = render_template(
            template_path,
            action.values,
        )

        self._write_file(
            path=output_path,
            content=content,
            overwrite=action.overwrite,
            display_path=action.output_path,
        )

    def _write_file(
        self,
        *,
        path: Path,
        content: str,
        overwrite: bool,
        display_path: Path,
    ) -> None:
        if path.exists() and not overwrite:
            raise SprintExecutionError(
                "File already exists and overwrite is disabled: "
                f"{display_path}"
            )

        self._backups.append(
            _FileBackup(
                path=path,
                existed=path.exists(),
                content=path.read_bytes() if path.exists() else None,
            )
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            content,
            encoding="utf-8",
            newline="\n",
        )

    def _compile_python(self, action: CompilePython) -> None:
        for relative_path in action.paths:
            path = self._resolve(relative_path)

            if not path.exists():
                raise SprintExecutionError(
                    f"Compile path does not exist: {relative_path}"
                )

            if path.is_file():
                success = compileall.compile_file(
                    str(path),
                    quiet=1,
                    force=True,
                )
            else:
                success = compileall.compile_dir(
                    str(path),
                    quiet=1,
                    force=True,
                )

            if not success:
                raise SprintExecutionError(
                    f"Python compilation failed: {relative_path}"
                )

    def _run_tests(self, action: RunTests) -> None:
        directory = self._resolve(action.directory)

        if not directory.exists():
            raise SprintExecutionError(
                f"Test directory does not exist: {action.directory}"
            )

        command = [
            "python",
            "-m",
            "unittest",
            "discover",
            "-s",
            str(directory),
            "-p",
            action.pattern,
        ]

        if action.verbose:
            command.append("-v")

        self._run_command(command, "Project tests failed.")

    def _git_diff_check(self) -> None:
        self._run_command(
            ["git", "diff", "--check"],
            "Git whitespace validation failed.",
        )

    def _run_command(
        self,
        command: list[str],
        failure_message: str,
    ) -> None:
        result = subprocess.run(
            command,
            cwd=self.root,
            check=False,
        )

        if result.returncode != 0:
            raise SprintExecutionError(failure_message)

    def _resolve(self, relative_path: Path) -> Path:
        candidate = (self.root / relative_path).resolve()

        try:
            candidate.relative_to(self.root)
        except ValueError as error:
            raise SprintExecutionError(
                f"Path escapes the repository root: {relative_path}"
            ) from error

        return candidate

    def _rollback(self) -> None:
        for backup in reversed(self._backups):
            if backup.existed:
                if backup.content is None:
                    raise SprintExecutionError(
                        f"Missing backup data for {backup.path}"
                    )

                backup.path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                backup.path.write_bytes(backup.content)
            elif backup.path.exists():
                backup.path.unlink()

        self._backups.clear()
'''


SPRINT_SOURCE = '''"""Fluent sprint-definition API."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .actions import (
    CompilePython,
    CreateFile,
    GitDiffCheck,
    RenderTemplate,
    RunTests,
    SprintAction,
)
from .executor import SprintExecutor


class Sprint:
    """Build and execute a repeatable development sprint."""

    def __init__(
        self,
        *,
        version: str,
        name: str,
        root: Path | str = ".",
    ) -> None:
        self.version = self._required_text(version, "version")
        self.name = self._required_text(name, "name")
        self.root = Path(root)
        self._actions: list[SprintAction] = []

    def create_file(
        self,
        path: Path | str,
        content: str,
        *,
        overwrite: bool = False,
    ) -> Sprint:
        """Add a safe UTF-8 file-creation action."""

        self._actions.append(
            CreateFile(
                path=Path(path),
                content=content,
                overwrite=overwrite,
            )
        )
        return self

    def create_from_template(
        self,
        template_path: Path | str,
        output_path: Path | str,
        *,
        values: Mapping[str, object] | None = None,
        overwrite: bool = False,
    ) -> Sprint:
        """Render a template into an output file."""

        self._actions.append(
            RenderTemplate(
                template_path=Path(template_path),
                output_path=Path(output_path),
                values=dict(values or {}),
                overwrite=overwrite,
            )
        )
        return self

    def compile_python(
        self,
        *paths: Path | str,
    ) -> Sprint:
        """Add Python syntax validation."""

        if not paths:
            raise ValueError(
                "compile_python requires at least one path."
            )

        self._actions.append(
            CompilePython(
                paths=tuple(Path(path) for path in paths)
            )
        )
        return self

    def run_tests(
        self,
        directory: Path | str = "tests",
        *,
        pattern: str = "test*.py",
        verbose: bool = True,
    ) -> Sprint:
        """Add unittest discovery."""

        self._actions.append(
            RunTests(
                directory=Path(directory),
                pattern=self._required_text(
                    pattern,
                    "test pattern",
                ),
                verbose=verbose,
            )
        )
        return self

    def git_diff_check(self) -> Sprint:
        """Add Git whitespace validation."""

        self._actions.append(GitDiffCheck())
        return self

    def execute(self) -> None:
        """Execute the configured sprint."""

        if not self._actions:
            raise ValueError(
                "A sprint must contain at least one action."
            )

        SprintExecutor(self.root).execute(
            name=self.name,
            version=self.version,
            actions=tuple(self._actions),
        )

    @property
    def actions(self) -> tuple[SprintAction, ...]:
        """Return the immutable action sequence."""

        return tuple(self._actions)

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string.")

        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} cannot be empty.")

        return normalized
'''


INIT_SOURCE = '''"""Platform Development Kit public API."""

from .executor import SprintExecutionError, SprintExecutor
from .sprint import Sprint
from .templates import TemplateRenderError, render_template

__all__ = [
    "Sprint",
    "SprintExecutionError",
    "SprintExecutor",
    "TemplateRenderError",
    "render_template",
]
'''


TEST_SOURCE = '''from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.pdk import (
    Sprint,
    SprintExecutionError,
    TemplateRenderError,
    render_template,
)
from tools.pdk.actions import RenderTemplate


class TemplateRenderingTests(unittest.TestCase):
    def test_render_template_substitutes_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "example.tmpl"
            template.write_text(
                "class $class_name:\\n"
                "    name = \\"$engine_name\\"\\n",
                encoding="utf-8",
            )

            rendered = render_template(
                template,
                {
                    "class_name": "WalletEngine",
                    "engine_name": "wallet",
                },
            )

            self.assertEqual(
                rendered,
                "class WalletEngine:\\n"
                "    name = \\"wallet\\"\\n",
            )

    def test_missing_template_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "example.tmpl"
            template.write_text(
                "Hello $name",
                encoding="utf-8",
            )

            with self.assertRaises(TemplateRenderError):
                render_template(template, {})

    def test_missing_template_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.tmpl"

            with self.assertRaises(TemplateRenderError):
                render_template(missing, {})


class TemplateSprintTests(unittest.TestCase):
    def test_fluent_api_creates_template_action(self) -> None:
        sprint = Sprint(
            version="1.1.0",
            name="Template action",
        ).create_from_template(
            "templates/example.tmpl",
            "generated/example.py",
            values={"name": "Example"},
        )

        self.assertEqual(len(sprint.actions), 1)
        self.assertIsInstance(
            sprint.actions[0],
            RenderTemplate,
        )

    def test_sprint_renders_template_to_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "templates" / "engine.py.tmpl"
            template.parent.mkdir(parents=True)
            template.write_text(
                "class $class_name:\\n"
                "    name = \\"$engine_name\\"\\n",
                encoding="utf-8",
            )

            (
                Sprint(
                    version="1.1.0",
                    name="Render engine",
                    root=root,
                )
                .create_from_template(
                    "templates/engine.py.tmpl",
                    "src/generated_engine.py",
                    values={
                        "class_name": "WalletEngine",
                        "engine_name": "wallet",
                    },
                )
                .execute()
            )

            generated = root / "src" / "generated_engine.py"

            self.assertEqual(
                generated.read_text(encoding="utf-8"),
                "class WalletEngine:\\n"
                "    name = \\"wallet\\"\\n",
            )

    def test_render_failure_rolls_back_prior_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.tmpl"
            template.write_text(
                "Hello $missing_value",
                encoding="utf-8",
            )

            sprint = (
                Sprint(
                    version="1.1.0",
                    name="Template rollback",
                    root=root,
                )
                .create_file("created.py", "VALUE = 1\\n")
                .create_from_template(
                    "template.tmpl",
                    "rendered.txt",
                )
            )

            with self.assertRaises(SprintExecutionError):
                sprint.execute()

            self.assertFalse((root / "created.py").exists())
            self.assertFalse((root / "rendered.txt").exists())


if __name__ == "__main__":
    unittest.main()
'''


def main() -> None:
    (
        Sprint(
            version="1.1.0",
            name="PDK Template System",
        )
        .create_file(
            "tools/pdk/actions.py",
            ACTIONS_SOURCE,
            overwrite=True,
        )
        .create_file(
            "tools/pdk/templates.py",
            TEMPLATES_SOURCE,
        )
        .create_file(
            "tools/pdk/executor.py",
            EXECUTOR_SOURCE,
            overwrite=True,
        )
        .create_file(
            "tools/pdk/sprint.py",
            SPRINT_SOURCE,
            overwrite=True,
        )
        .create_file(
            "tools/pdk/__init__.py",
            INIT_SOURCE,
            overwrite=True,
        )
        .create_file(
            "tests/test_pdk_templates.py",
            TEST_SOURCE,
        )
        .compile_python(
            "tools/pdk",
            "tests",
            "src",
        )
        .run_tests("tests")
        .git_diff_check()
        .execute()
    )


if __name__ == "__main__":
    main()