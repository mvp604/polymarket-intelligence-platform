from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.project_builder import BuildError, ProjectBuilder


class ProjectBuilderTests(unittest.TestCase):
    def test_create_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()

            manifest = root / "sprint.json"
            manifest.write_text(json.dumps({
                "version": "1.0",
                "name": "Test",
                "actions": [{
                    "type": "create_file",
                    "path": "example.txt",
                    "content": "success\\n"
                }]
            }), encoding="utf-8")

            ProjectBuilder(root).execute(manifest)

            self.assertEqual(
                (root / "example.txt").read_text(encoding="utf-8"),
                "success\\n"
            )

    def test_existing_file_is_protected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            (root / "example.txt").write_text("original", encoding="utf-8")

            manifest = root / "sprint.json"
            manifest.write_text(json.dumps({
                "version": "1.0",
                "name": "Safety test",
                "actions": [{
                    "type": "create_file",
                    "path": "example.txt",
                    "content": "replacement"
                }]
            }), encoding="utf-8")

            with self.assertRaises(BuildError):
                ProjectBuilder(root).execute(manifest)

            self.assertEqual(
                (root / "example.txt").read_text(encoding="utf-8"),
                "original"
            )


if __name__ == "__main__":
    unittest.main()
