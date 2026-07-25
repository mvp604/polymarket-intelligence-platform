from __future__ import annotations

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


def backup_file(root: Path, target: Path) -> Path:
    destination = root / "backups" / (
        "core_003_schema_audit_fix_" +
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    destination.mkdir(parents=True, exist_ok=False)
    backup_target = destination / target
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / target, backup_target)
    return destination


def patch_test(root: Path) -> None:
    target = root / TARGET
    if not target.exists():
        raise SystemExit(f"Missing expected test file: {target}")

    text = target.read_text(encoding="utf-8")

    if "sys.modules[module_spec.name] = module" in text:
        print("Schema-audit import is already patched.")
        return

    if "import sys" not in text:
        lines = text.splitlines()
        insert_at = 0
        while insert_at < len(lines) and (
            lines[insert_at].startswith("from __future__")
            or not lines[insert_at].strip()
        ):
            insert_at += 1
        lines.insert(insert_at, "import sys")
        text = "\n".join(lines) + "\n"

    candidates = [
        "module_spec.loader.exec_module(module)",
        "module_spec.loader.exec_module(audit_module)",
        "module_spec.loader.exec_module(schema_audit_module)",
    ]

    replacement_done = False
    for candidate in candidates:
        if candidate in text:
            module_var = candidate.removeprefix("module_spec.loader.exec_module(").removesuffix(")")
            replacement = (
                f"sys.modules[module_spec.name] = {module_var}\n"
                f"module_spec.loader.exec_module({module_var})"
            )
            text = text.replace(candidate, replacement, 1)
            replacement_done = True
            break

    if not replacement_done:
        marker = "module_spec.loader.exec_module("
        index = text.find(marker)
        if index == -1:
            raise SystemExit(
                "Could not safely locate module_spec.loader.exec_module(...) "
                "inside tests/schema_audit/test_schema_audit.py."
            )

        line_start = text.rfind("\n", 0, index) + 1
        line_end = text.find("\n", index)
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end]
        indent = line[: len(line) - len(line.lstrip())]
        argument = line[line.find("(") + 1 : line.rfind(")")].strip()

        replacement = (
            f"{indent}sys.modules[module_spec.name] = {argument}\n"
            f"{line}"
        )
        text = text[:line_start] + replacement + text[line_end:]

    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"Patched {TARGET}")


def main() -> int:
    root = find_root()
    destination = backup_file(root, TARGET)
    print(f"Backup created: {destination}")
    patch_test(root)

    print("\nSchema-audit import fix installed.")
    print("Run:")
    print("  python manage.py test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())