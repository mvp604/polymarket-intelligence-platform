from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT_MARKERS = ("src", "tests", "manage.py")

PYTEST_INI = """[pytest]
minversion = 8.0
testpaths =
    tests
python_files =
    test_*.py
python_classes =
    Test*
python_functions =
    test_*
norecursedirs =
    .git
    .venv
    __pycache__
    backups
    artifacts
    reports
    docs
    runtime
    sprints
addopts =
    --strict-markers
"""

SPRINT_DOC = """# CORE-003 — Sprint 3.1

## Engineering Stabilization

Status: Implemented

- Restricts pytest discovery to active tests.
- Excludes backups and generated sprint payloads.
- Hardens `python manage.py test`.
- Tracks pytest in development requirements.

## Validation

```powershell
python manage.py test
```
"""

def find_root() -> Path:
    root = Path.cwd().resolve()
    missing = [item for item in ROOT_MARKERS if not (root / item).exists()]
    if missing:
        raise SystemExit("Run from project root. Missing: " + ", ".join(missing))
    return root

def backup(root: Path) -> Path:
    dst = root / "backups" / (
        "core_003_sprint_3_1_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    dst.mkdir(parents=True, exist_ok=False)
    for rel in (
        "manage.py", "pytest.ini", "requirements-dev.txt",
        "CURRENT_SPRINT.md", "PROJECT_STATUS.md",
        "NEXT_TASK.md", "CHANGELOG.md",
        "docs/CORE-003-SPRINT-3.1.md",
    ):
        src = root / rel
        if src.is_file():
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    return dst

def patch_manage(root: Path) -> None:
    path = root / "manage.py"
    text = path.read_text(encoding="utf-8")
    old = '[sys.executable, "-m", "pytest", "-q"],'
    new = '[sys.executable, "-m", "pytest", "tests", "-q"],'
    if new in text:
        print("manage.py already stabilized")
    elif old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
        print("Updated manage.py")
    else:
        raise SystemExit("Could not safely locate pytest command in manage.py.")

def requirements(root: Path) -> None:
    path = root / "requirements-dev.txt"
    if not path.exists():
        path.write_text("pytest>=9.1,<10\n", encoding="utf-8", newline="\n")
        print("Created requirements-dev.txt")
        return
    text = path.read_text(encoding="utf-8")
    if not any(line.strip().lower().startswith("pytest") for line in text.splitlines()):
        path.write_text(text.rstrip() + "\npytest>=9.1,<10\n", encoding="utf-8", newline="\n")
        print("Added pytest to requirements-dev.txt")
    else:
        print("requirements-dev.txt already includes pytest")

def update_docs(root: Path) -> None:
    (root / "CURRENT_SPRINT.md").write_text(
        "# Current Sprint\n\nCORE-003 Sprint 3.2 — Historical Snapshot Framework\n",
        encoding="utf-8", newline="\n"
    )
    (root / "NEXT_TASK.md").write_text(
        "# Next Task\n\nBuild CORE-003 Sprint 3.2 — Historical Snapshot Framework.\n",
        encoding="utf-8", newline="\n"
    )
    (root / "PROJECT_STATUS.md").write_text(
        "# Project Status\n\n"
        "- CORE-001: Complete\n"
        "- CORE-002: Complete\n"
        "- CORE-003: Active\n"
        "- Sprint 3.0 Capability Registry: Complete\n"
        "- Sprint 3.1 Engineering Stabilization: Implemented; awaiting validation\n",
        encoding="utf-8", newline="\n"
    )
    changelog = root / "CHANGELOG.md"
    existing = changelog.read_text(encoding="utf-8") if changelog.exists() else "# Changelog\n"
    if "## CORE-003 Sprint 3.1" not in existing:
        existing = existing.rstrip() + (
            "\n\n## CORE-003 Sprint 3.1\n\n"
            "- Restricted pytest discovery to active tests.\n"
            "- Excluded backups and sprint payloads.\n"
            "- Hardened `python manage.py test`.\n"
        )
        changelog.write_text(existing + "\n", encoding="utf-8", newline="\n")
    print("Updated sprint documentation")

def main() -> int:
    root = find_root()
    print(f"Backup created: {backup(root)}")
    (root / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8", newline="\n")
    print("Installed pytest.ini")
    requirements(root)
    patch_manage(root)
    doc = root / "docs" / "CORE-003-SPRINT-3.1.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(SPRINT_DOC, encoding="utf-8", newline="\n")
    print("Installed sprint document")
    update_docs(root)
    print("\nCORE-003 Sprint 3.1 installed.")
    print("Run: python manage.py test")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())