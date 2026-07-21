from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_DIR = ROOT / "automation"
TEMPLATES_DIR = AUTOMATION_DIR / "templates"
REGISTRY_PATH = AUTOMATION_DIR / "engine_registry.json"
SRC_DIR = ROOT / "src"
REPORTS_DIR = ROOT / "reports"

ENGINE_TEMPLATE = TEMPLATES_DIR / "engine_template.py.txt"
RUNNER_TEMPLATE = TEMPLATES_DIR / "runner_template.ps1.txt"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_ -]+", "", value)
    value = re.sub(r"[\s-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        raise ValueError("Engine name cannot be empty.")
    if value[0].isdigit():
        value = f"engine_{value}"
    return value


def class_name(slug: str) -> str:
    return "".join(part.capitalize() for part in slug.split("_"))


def title_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("_"))


def read_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text(encoding="utf-8")


def render(template: str, values: dict[str, str]) -> str:
    output = template
    for key, value in values.items():
        output = output.replace(f"{{{{{key}}}}}", value)
    return output


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"version": 1, "engines": []}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "engines": []}


def save_registry(registry: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def register_engine(
    slug: str,
    title: str,
    engine_path: Path,
    runner_path: Path,
    report_dir: Path,
) -> None:
    registry = load_registry()
    engines = registry.setdefault("engines", [])

    record = {
        "slug": slug,
        "title": title,
        "engine_path": str(engine_path.relative_to(ROOT)),
        "runner_path": str(runner_path.relative_to(ROOT)),
        "report_directory": str(report_dir.relative_to(ROOT)),
        "created_at": utc_now(),
        "enabled": True,
    }

    replaced = False
    for index, existing in enumerate(engines):
        if existing.get("slug") == slug:
            record["created_at"] = existing.get("created_at", record["created_at"])
            record["updated_at"] = utc_now()
            engines[index] = record
            replaced = True
            break

    if not replaced:
        engines.append(record)

    engines.sort(key=lambda item: item.get("slug", ""))
    save_registry(registry)


def compile_check(engine_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(engine_path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Compile check failed:\n"
            + (result.stderr or result.stdout or "Unknown compile error")
        )


def create_engine(
    raw_name: str,
    description: str,
    force: bool,
    run_after: bool,
) -> None:
    slug = slugify(raw_name)
    title = title_name(slug)
    cls = class_name(slug)

    engine_path = SRC_DIR / f"{slug}.py"
    runner_path = ROOT / f"run_{slug}.ps1"
    report_dir = REPORTS_DIR / slug

    for path in (engine_path, runner_path):
        if path.exists() and not force:
            raise FileExistsError(
                f"Refusing to overwrite existing file: {path}\n"
                "Use --force only after reviewing the existing module."
            )

    SRC_DIR.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    values = {
        "ENGINE_SLUG": slug,
        "ENGINE_TITLE": title,
        "ENGINE_CLASS": cls,
        "ENGINE_DESCRIPTION": description.strip() or f"{title} generated engine.",
        "REPORT_FOLDER": slug,
        "CREATED_AT": utc_now(),
    }

    engine_code = render(read_template(ENGINE_TEMPLATE), values)
    runner_code = render(read_template(RUNNER_TEMPLATE), values)

    engine_path.write_text(engine_code, encoding="utf-8")
    runner_path.write_text(runner_code, encoding="utf-8")

    compile_check(engine_path)
    register_engine(slug, title, engine_path, runner_path, report_dir)

    print()
    print("=" * 100)
    print("ENGINE AUTOMATION FRAMEWORK")
    print("=" * 100)
    print(f"Created engine:     {engine_path}")
    print(f"Created runner:     {runner_path}")
    print(f"Created reports:    {report_dir}")
    print(f"Compile check:      PASSED")
    print(f"Registered:         {REGISTRY_PATH}")
    print(f"Existing database:  NOT MODIFIED")
    print("=" * 100)

    if run_after:
        subprocess.run(
            [
                sys.executable,
                str(engine_path),
            ],
            cwd=str(ROOT),
            check=True,
        )


def list_engines() -> None:
    registry = load_registry()
    engines = registry.get("engines", [])

    print()
    print("=" * 100)
    print("REGISTERED ENGINES")
    print("=" * 100)

    if not engines:
        print("No generated engines registered.")
        return

    for index, engine in enumerate(engines, start=1):
        print(
            f"{index:>3}. {engine.get('slug', ''):<40} "
            f"enabled={engine.get('enabled', True)}"
        )
        print(f"     {engine.get('engine_path', '')}")
        print(f"     {engine.get('runner_path', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate consistent Polymarket engine modules and runners."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("name")
    create_parser.add_argument("--description", default="")
    create_parser.add_argument("--force", action="store_true")
    create_parser.add_argument("--run", action="store_true")

    subparsers.add_parser("list")

    args = parser.parse_args()

    if args.command == "create":
        create_engine(
            raw_name=args.name,
            description=args.description,
            force=bool(args.force),
            run_after=bool(args.run),
        )
    elif args.command == "list":
        list_engines()


if __name__ == "__main__":
    main()

