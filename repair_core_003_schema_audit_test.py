from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

TARGET = Path("tests/schema_audit/test_schema_audit.py")


def find_root() -> Path:
    root = Path.cwd().resolve()
    required = ("src", "tests", "manage.py")
    missing = [name for name in required if not (root / name).exists()]
    if missing:
        raise SystemExit("Run this script from the project root. Missing: " + ", ".join(missing))
    return root


def find_latest_good_backup(root: Path) -> Path:
    candidates = []

    for directory in (root / "backups").glob("*"):
        candidate = directory / TARGET
        if not candidate.is_file():
            continue

        text = candidate.read_text(encoding="utf-8", errors="replace")

        # Reject the broken file produced by the previous patch.
        if re.search(r"sys\.modules\[module_spec\.name\]\s*=\s*(?:\n|$)", text):
            continue

        if "module_from_spec" in text and "exec_module" in text:
            candidates.append(candidate)

    if not candidates:
        raise SystemExit(
            "Could not find a clean backed-up copy of "
            "tests/schema_audit/test_schema_audit.py."
        )

    return max(candidates, key=lambda item: item.stat().st_mtime)


def create_safety_backup(root: Path) -> Path:
    destination = root / "backups" / (
        "core_003_schema_audit_repair_" +
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    destination.mkdir(parents=True, exist_ok=False)

    current = root / TARGET
    if current.is_file():
        target = destination / TARGET
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current, target)

    return destination


def patch_clean_source(text: str) -> str:
    # Match: variable_name = importlib.util.module_from_spec(module_spec)
    pattern = re.compile(
        r"^(?P<indent>[ \t]*)(?P<var>[A-Za-z_][A-Za-z0-9_]*)"
        r"\s*=\s*importlib\.util\.module_from_spec\(module_spec\)\s*$",
        re.MULTILINE,
    )
    match = pattern.search(text)

    if not match:
        # Also support: module_from_spec imported directly.
        pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?P<var>[A-Za-z_][A-Za-z0-9_]*)"
            r"\s*=\s*module_from_spec\(module_spec\)\s*$",
            re.MULTILINE,
        )
        match = pattern.search(text)

    if not match:
        raise SystemExit(
            "Could not locate the module_from_spec assignment in the clean backup."
        )

    variable = match.group("var")
    indent = match.group("indent")
    assignment_line = match.group(0)

    if "import sys" not in text:
        future_match = re.search(r"^from __future__ import .+$", text, re.MULTILINE)
        if future_match:
            insert_at = future_match.end()
            text = text[:insert_at] + "\n\nimport sys" + text[insert_at:]
        else:
            text = "import sys\n" + text

        # Re-find after changing offsets.
        match = pattern.search(text)
        if not match:
            raise SystemExit("Internal repair error while re-locating assignment.")
        assignment_line = match.group(0)
        variable = match.group("var")
        indent = match.group("indent")

    registration = f"{indent}sys.modules[module_spec.name] = {variable}"

    if registration not in text:
        text = text.replace(
            assignment_line,
            assignment_line + "\n" + registration,
            1,
        )

    return text


def main() -> int:
    root = find_root()
    safety = create_safety_backup(root)
    print(f"Current broken file backed up to: {safety}")

    clean_backup = find_latest_good_backup(root)
    print(f"Restoring clean source from: {clean_backup}")

    original = clean_backup.read_text(encoding="utf-8")
    repaired = patch_clean_source(original)

    destination = root / TARGET
    destination.write_text(repaired, encoding="utf-8", newline="\n")
    print(f"Repaired: {TARGET}")

    print("\nRun:")
    print("  python manage.py test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())