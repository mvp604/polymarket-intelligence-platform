$ErrorActionPreference = "Stop"

$root = "C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform"
$automation = Join-Path $root "automation"
$templates = Join-Path $automation "templates"

New-Item -ItemType Directory -Path $automation -Force | Out-Null
New-Item -ItemType Directory -Path $templates -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root "reports") -Force | Out-Null

$builderPath = Join-Path $automation "build_engine.py"
$engineTemplatePath = Join-Path $templates "engine_template.py.txt"
$runnerTemplatePath = Join-Path $templates "runner_template.ps1.txt"
$frameworkRunnerPath = Join-Path $root "engine_builder.ps1"
$registryPath = Join-Path $automation "engine_registry.json"

$builderCode = @'
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

'@

$engineTemplateCode = @'
from __future__ import annotations

"""
{{ENGINE_TITLE}}
{{ENGINE_DESCRIPTION}}

Generated by the Polymarket Engine Automation Framework.
Created: {{CREATED_AT}}
"""

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENGINE_VERSION = "1.0"
ENGINE_SLUG = "{{ENGINE_SLUG}}"
ENGINE_TITLE = "{{ENGINE_TITLE}}"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "database" / "polymarket.db"
DEFAULT_REPORT_DIRECTORY = ROOT / "reports" / "{{REPORT_FOLDER}}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def connect_read_only(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone() is not None


def analyze(connection: sqlite3.Connection) -> dict[str, Any]:
    """
    Replace this function with engine-specific analysis.

    Safety defaults:
    - database connection is read-only
    - no thresholds are changed
    - no methodology is changed
    """
    tables = [
        row["name"]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()
    ]

    return {
        "engine": ENGINE_SLUG,
        "generated_at": utc_now().isoformat(timespec="seconds"),
        "status": "SCAFFOLD_READY",
        "table_count": len(tables),
        "sample_tables": tables[:25],
        "message": "Replace analyze() with the approved engine logic.",
    }


def write_reports(
    report_directory: Path,
    payload: dict[str, Any],
) -> dict[str, Path]:
    report_directory.mkdir(parents=True, exist_ok=True)

    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    stem = f"{ENGINE_SLUG}_{timestamp}"

    json_path = report_directory / f"{stem}.json"
    text_path = report_directory / f"{stem}.txt"
    csv_path = report_directory / f"{stem}.csv"
    html_path = report_directory / f"{stem}.html"

    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    text_path.write_text(
        "\n".join(
            [
                "=" * 100,
                ENGINE_TITLE.upper(),
                "=" * 100,
                f"Version: {ENGINE_VERSION}",
                f"Generated: {payload.get('generated_at', '')}",
                f"Status: {payload.get('status', '')}",
                f"Message: {payload.get('message', '')}",
                "",
                json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                "",
                "Database modified: NO",
                "Thresholds modified: NO",
                "Methodology modified: NO",
                "=" * 100,
            ]
        ),
        encoding="utf-8",
    )

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["key", "value"])
        writer.writeheader()
        for key, value in payload.items():
            writer.writerow(
                {
                    "key": key,
                    "value": json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else value,
                }
            )

    html_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{ENGINE_TITLE}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 0; background: #f4f6f8; color: #172033; }}
header {{ background: #111827; color: white; padding: 28px; }}
main {{ max-width: 1000px; margin: auto; padding: 24px; }}
.card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header>
<h1>{ENGINE_TITLE}</h1>
<div>Version {ENGINE_VERSION}</div>
</header>
<main>
<section class="card">
<pre>{json.dumps(payload, indent=2, ensure_ascii=False, default=str)}</pre>
</section>
</main>
</body>
</html>
""",
        encoding="utf-8",
    )

    outputs = {
        "json": json_path,
        "text": text_path,
        "csv": csv_path,
        "html": html_path,
    }

    for extension, source in outputs.items():
        (report_directory / f"latest.{extension}").write_bytes(source.read_bytes())

    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--report-directory", default=str(DEFAULT_REPORT_DIRECTORY))
    args = parser.parse_args()

    database_path = Path(args.database).resolve()
    report_directory = Path(args.report_directory).resolve()

    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    connection = connect_read_only(database_path)
    try:
        payload = analyze(connection)
    finally:
        connection.close()

    outputs = write_reports(report_directory, payload)

    print()
    print("=" * 100)
    print(ENGINE_TITLE.upper())
    print("=" * 100)
    print(f"Status:             {payload.get('status', '')}")
    print(f"JSON:               {outputs['json']}")
    print(f"TEXT:               {outputs['text']}")
    print(f"CSV:                {outputs['csv']}")
    print(f"HTML:               {outputs['html']}")
    print(f"Database modified:  NO")
    print("=" * 100)


if __name__ == "__main__":
    main()

'@

$runnerTemplateCode = @'
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonFile = Join-Path `
    $projectRoot `
    "src\{{ENGINE_SLUG}}.py"

if (-not (Test-Path $pythonFile -PathType Leaf)) {
    throw "Engine not found: $pythonFile"
}

python $pythonFile

if ($LASTEXITCODE -ne 0) {
    throw "{{ENGINE_TITLE}} failed with exit code $LASTEXITCODE"
}

$reportPath = Join-Path `
    $projectRoot `
    "reports\{{REPORT_FOLDER}}\latest.html"

if (Test-Path $reportPath) {
    Start-Process $reportPath
}

Write-Host ""
Write-Host "{{ENGINE_TITLE}} complete."
Write-Host "Latest report:"
Write-Host $reportPath

'@

$frameworkRunnerCode = @'
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python `
    .\automation\build_engine.py `
    @args

'@

Set-Content -Path $builderPath -Value $builderCode -Encoding UTF8
Set-Content -Path $engineTemplatePath -Value $engineTemplateCode -Encoding UTF8
Set-Content -Path $runnerTemplatePath -Value $runnerTemplateCode -Encoding UTF8
Set-Content -Path $frameworkRunnerPath -Value $frameworkRunnerCode -Encoding UTF8

if (-not (Test-Path $registryPath -PathType Leaf)) {
    Set-Content `
        -Path $registryPath `
        -Value "{`"version`": 1, `"engines`": []}" `
        -Encoding UTF8
}

Write-Host ""
Write-Host "Created automation framework:"
Write-Host $builderPath
Write-Host $engineTemplatePath
Write-Host $runnerTemplatePath
Write-Host $frameworkRunnerPath
Write-Host $registryPath

python -m py_compile $builderPath

if ($LASTEXITCODE -ne 0) {
    throw "Automation framework compile check failed."
}

Write-Host ""
Write-Host "Compile check passed."

python $builderPath list

Write-Host ""
Write-Host ("=" * 100)
Write-Host "ENGINE AUTOMATION FRAMEWORK INSTALLED"
Write-Host ("=" * 100)
Write-Host "Create a scaffold:"
Write-Host '.\engine_builder.ps1 create threshold_optimizer --description "Analyzes threshold sensitivity."'
Write-Host ""
Write-Host "Create and immediately run a scaffold:"
Write-Host '.\engine_builder.ps1 create portfolio_builder --description "Builds portfolio candidates." --run'
Write-Host ""
Write-Host "List generated engines:"
Write-Host '.\engine_builder.ps1 list'
Write-Host ""
Write-Host "Existing source files were not moved or overwritten."
Write-Host ("=" * 100)