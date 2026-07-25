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
        raise SystemExit("Run from the project root. Missing: " + ", ".join(missing))
    return root


def backup(root: Path) -> Path:
    destination = root / "backups" / (
        "core_003_schema_audit_active_fix_" +
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    destination.mkdir(parents=True, exist_ok=False)

    source = root / TARGET
    target = destination / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

    return destination


def ensure_import_sys(text: str) -> str:
    if re.search(r"^\s*import sys\s*$", text, re.MULTILINE):
        return text

    future = re.search(r"^from __future__ import .+$", text, re.MULTILINE)
    if future:
        pos = future.end()
        return text[:pos] + "\n\nimport sys" + text[pos:]

    return "import sys\n" + text


def detect_exec_variable(text: str) -> str:
    pattern = re.compile(
        r"module_spec\.loader\.exec_module\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise SystemExit(
            "Could not locate module_spec.loader.exec_module(<module variable>) "
            "in tests/schema_audit/test_schema_audit.py."
        )
    return match.group(1)


def repair(text: str) -> str:
    variable = detect_exec_variable(text)

    # Remove any malformed or previously inserted registration lines.
    text = re.sub(
        r"^[ \t]*sys\.modules\[module_spec\.name\]\s*=\s*(?:[A-Za-z_][A-Za-z0-9_]*)?[ \t]*\r?\n",
        "",
        text,
        flags=re.MULTILINE,
    )

    text = ensure_import_sys(text)

    exec_pattern = re.compile(
        r"(?P<indent>^[ \t]*)module_spec\.loader\.exec_module\(\s*"
        + re.escape(variable)
        + r"\s*\)",
        re.MULTILINE | re.DOTALL,
    )
    match = exec_pattern.search(text)
    if not match:
        raise SystemExit("Could not re-locate the exec_module call after cleanup.")

    registration = (
        f"{match.group('indent')}sys.modules[module_spec.name] = {variable}\n"
    )

    text = text[:match.start()] + registration + text[match.start():]
    return text


def main() -> int:
    root = find_root()
    target = root / TARGET
    if not target.is_file():
        raise SystemExit(f"Missing expected file: {target}")

    backup_dir = backup(root)
    print(f"Backup created: {backup_dir}")

    original = target.read_text(encoding="utf-8")
    fixed = repair(original)
    target.write_text(fixed, encoding="utf-8", newline="\n")

    print(f"Repaired active file: {TARGET}")
    print("\nRun:")
    print("  python manage.py test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())