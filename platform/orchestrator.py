from __future__ import annotations

import argparse
import html
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "platform_pipeline.json"
LOG_DIR = ROOT / "logs" / "platform"
REPORT_DIR = ROOT / "reports" / "platform"
DATABASE_PATH = ROOT / "database" / "polymarket.db"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


@dataclass
class StepResult:
    name: str
    runner: str
    status: str
    required: bool
    started_at: str
    finished_at: str
    duration_seconds: float
    return_code: int | None
    stdout_log: str
    stderr_log: str
    message: str


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Platform configuration not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def database_integrity(database_path: Path) -> tuple[bool, str]:
    if not database_path.exists():
        return False, f"Database not found: {database_path}"

    try:
        connection = sqlite3.connect(str(database_path))
        try:
            result = connection.execute("PRAGMA quick_check").fetchone()
            status = str(result[0]) if result else "unknown"
            return status.lower() == "ok", status
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return False, str(exc)


def health_check(config: dict[str, Any]) -> dict[str, Any]:
    disk = shutil.disk_usage(ROOT)
    database_ok, database_message = database_integrity(DATABASE_PATH)

    checks = {
        "generated_at": iso_now(),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "operating_system": platform.platform(),
        "project_root": str(ROOT),
        "virtual_environment_active": bool(os.environ.get("VIRTUAL_ENV")),
        "database_exists": DATABASE_PATH.exists(),
        "database_integrity_ok": database_ok,
        "database_integrity_message": database_message,
        "free_disk_gb": round(disk.free / (1024**3), 2),
        "config_exists": CONFIG_PATH.exists(),
        "src_exists": (ROOT / "src").exists(),
        "reports_exists": (ROOT / "reports").exists(),
        "logs_exists": (ROOT / "logs").exists(),
    }

    minimum_free_gb = float(config.get("health", {}).get("minimum_free_disk_gb", 1.0))
    checks["disk_space_ok"] = checks["free_disk_gb"] >= minimum_free_gb

    failures = [
        key
        for key in (
            "database_exists",
            "database_integrity_ok",
            "config_exists",
            "src_exists",
            "disk_space_ok",
        )
        if not checks.get(key)
    ]

    checks["status"] = "PASS" if not failures else "FAIL"
    checks["failures"] = failures
    return checks


def safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in "_-" else "_" for character in value)


def execute_step(
    step: dict[str, Any],
    run_id: str,
    dry_run: bool,
) -> StepResult:
    name = str(step.get("name") or "unnamed_step")
    runner_value = str(step.get("runner") or "")
    runner_path = (ROOT / runner_value).resolve()
    required = bool(step.get("required", False))
    enabled = bool(step.get("enabled", True))
    timeout_seconds = int(step.get("timeout_seconds", 900))

    started = utc_now()
    log_stem = f"{run_id}_{safe_name(name)}"
    stdout_path = LOG_DIR / f"{log_stem}.stdout.log"
    stderr_path = LOG_DIR / f"{log_stem}.stderr.log"

    if not enabled:
        finished = utc_now()
        return StepResult(
            name=name,
            runner=runner_value,
            status="DISABLED",
            required=required,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            duration_seconds=0.0,
            return_code=None,
            stdout_log="",
            stderr_log="",
            message="Step disabled in configuration.",
        )

    if not runner_path.exists():
        finished = utc_now()
        return StepResult(
            name=name,
            runner=runner_value,
            status="MISSING",
            required=required,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            duration_seconds=round((finished - started).total_seconds(), 3),
            return_code=None,
            stdout_log="",
            stderr_log="",
            message=f"Runner not found: {runner_path}",
        )

    if dry_run:
        finished = utc_now()
        return StepResult(
            name=name,
            runner=runner_value,
            status="DRY_RUN",
            required=required,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            duration_seconds=round((finished - started).total_seconds(), 3),
            return_code=None,
            stdout_log="",
            stderr_log="",
            message="Validated runner without executing it.",
        )

    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(runner_path),
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")

        finished = utc_now()
        status = "SUCCESS" if completed.returncode == 0 else "FAILED"
        message = (
            "Completed successfully."
            if completed.returncode == 0
            else f"Runner exited with code {completed.returncode}."
        )

        return StepResult(
            name=name,
            runner=runner_value,
            status=status,
            required=required,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            duration_seconds=round((finished - started).total_seconds(), 3),
            return_code=completed.returncode,
            stdout_log=str(stdout_path),
            stderr_log=str(stderr_path),
            message=message,
        )
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_text(exc.stdout or "", encoding="utf-8")
        stderr_path.write_text(exc.stderr or "", encoding="utf-8")
        finished = utc_now()
        return StepResult(
            name=name,
            runner=runner_value,
            status="TIMEOUT",
            required=required,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            duration_seconds=round((finished - started).total_seconds(), 3),
            return_code=None,
            stdout_log=str(stdout_path),
            stderr_log=str(stderr_path),
            message=f"Timed out after {timeout_seconds} seconds.",
        )
    except OSError as exc:
        finished = utc_now()
        return StepResult(
            name=name,
            runner=runner_value,
            status="ERROR",
            required=required,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            duration_seconds=round((finished - started).total_seconds(), 3),
            return_code=None,
            stdout_log=str(stdout_path),
            stderr_log=str(stderr_path),
            message=str(exc),
        )


def latest_report_link(step: dict[str, Any]) -> str:
    report = str(step.get("latest_report") or "")
    if not report:
        return ""
    report_path = (ROOT / report).resolve()
    return report_path.as_uri() if report_path.exists() else ""


def write_master_report(
    run_id: str,
    health: dict[str, Any],
    results: list[StepResult],
    config: dict[str, Any],
    started_at: str,
    finished_at: str,
) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    config_steps = {
        str(step.get("name")): step for step in config.get("pipeline", [])
    }

    rows = []
    for result in results:
        report_url = latest_report_link(config_steps.get(result.name, {}))
        report_cell = (
            f'<a href="{html.escape(report_url)}">Open latest report</a>'
            if report_url
            else "â€”"
        )
        rows.append(
            f"""
            <tr>
              <td>{html.escape(result.name)}</td>
              <td>{html.escape(result.status)}</td>
              <td>{'Yes' if result.required else 'No'}</td>
              <td>{result.duration_seconds:.3f}</td>
              <td>{html.escape(result.message)}</td>
              <td>{report_cell}</td>
            </tr>
            """
        )

    health_rows = "".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
        for key, value in health.items()
    )

    successful = sum(result.status == "SUCCESS" for result in results)
    failed = sum(result.status in {"FAILED", "TIMEOUT", "ERROR"} for result in results)
    missing = sum(result.status == "MISSING" for result in results)
    skipped = sum(result.status in {"DISABLED", "DRY_RUN", "SKIPPED"} for result in results)

    required_failure = any(
        result.required and result.status not in {"SUCCESS", "DRY_RUN"}
        for result in results
    )
    overall = "FAILED" if health["status"] != "PASS" or required_failure else "COMPLETED"

    payload = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "overall_status": overall,
        "health": health,
        "results": [asdict(result) for result in results],
        "summary": {
            "successful": successful,
            "failed": failed,
            "missing": missing,
            "skipped": skipped,
        },
        "database_modified_by_orchestrator": False,
    }

    json_path = REPORT_DIR / f"platform_run_{run_id}.json"
    html_path = REPORT_DIR / f"platform_run_{run_id}.html"

    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    html_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Polymarket Institutional Command Center</title>
<style>
body {{ margin:0; font-family:Arial,sans-serif; background:#f4f6f8; color:#172033; }}
header {{ background:#111827; color:white; padding:28px; }}
main {{ max-width:1250px; margin:auto; padding:24px; }}
.metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }}
.metric, section, table {{ background:white; border-radius:12px; box-shadow:0 2px 10px rgba(0,0,0,.06); }}
.metric {{ padding:18px; }}
.metric strong {{ display:block; font-size:28px; }}
section {{ padding:20px; margin-top:20px; }}
table {{ width:100%; border-collapse:collapse; overflow:hidden; }}
th, td {{ text-align:left; padding:11px; border-bottom:1px solid #e5e7eb; vertical-align:top; }}
.status {{ font-weight:bold; }}
</style>
</head>
<body>
<header>
<h1>Polymarket Institutional Command Center</h1>
<div>Run ID: {html.escape(run_id)}</div>
<div>Status: {html.escape(overall)}</div>
<div>{html.escape(started_at)} â†’ {html.escape(finished_at)}</div>
</header>
<main>
<div class="metrics">
<div class="metric"><span>Successful</span><strong>{successful}</strong></div>
<div class="metric"><span>Failed</span><strong>{failed}</strong></div>
<div class="metric"><span>Missing</span><strong>{missing}</strong></div>
<div class="metric"><span>Skipped</span><strong>{skipped}</strong></div>
</div>

<section>
<h2>Pipeline execution</h2>
<table>
<thead><tr><th>Engine</th><th>Status</th><th>Required</th><th>Seconds</th><th>Message</th><th>Report</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</section>

<section>
<h2>System health</h2>
<table><tbody>{health_rows}</tbody></table>
</section>

<section>
<h2>Safety statement</h2>
<p>The orchestrator itself did not modify the SQLite database, production thresholds, or decision methodology. Individual configured engines retain their own behavior.</p>
</section>
</main>
</body>
</html>
""",
        encoding="utf-8",
    )

    (REPORT_DIR / "latest.json").write_bytes(json_path.read_bytes())
    (REPORT_DIR / "latest.html").write_bytes(html_path.read_bytes())
    return REPORT_DIR / "latest.html"


def run_platform(config: dict[str, Any], dry_run: bool) -> tuple[int, Path]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
    started_at = iso_now()
    health = health_check(config)

    results: list[StepResult] = []
    stop_on_required_failure = bool(
        config.get("execution", {}).get("stop_on_required_failure", True)
    )
    run_when_health_fails = bool(
        config.get("execution", {}).get("run_when_health_fails", False)
    )

    if health["status"] != "PASS" and not run_when_health_fails:
        finished_at = iso_now()
        report = write_master_report(
            run_id, health, results, config, started_at, finished_at
        )
        return 2, report

    pipeline = sorted(
        config.get("pipeline", []),
        key=lambda step: int(step.get("order", 9999)),
    )

    halted = False
    for step in pipeline:
        if halted:
            now = iso_now()
            results.append(
                StepResult(
                    name=str(step.get("name") or "unnamed_step"),
                    runner=str(step.get("runner") or ""),
                    status="SKIPPED",
                    required=bool(step.get("required", False)),
                    started_at=now,
                    finished_at=now,
                    duration_seconds=0.0,
                    return_code=None,
                    stdout_log="",
                    stderr_log="",
                    message="Skipped after a required pipeline failure.",
                )
            )
            continue

        result = execute_step(step, run_id, dry_run)
        results.append(result)

        if (
            stop_on_required_failure
            and result.required
            and result.status not in {"SUCCESS", "DRY_RUN"}
        ):
            halted = True

    finished_at = iso_now()
    report = write_master_report(
        run_id, health, results, config, started_at, finished_at
    )

    failed_required = any(
        result.required and result.status not in {"SUCCESS", "DRY_RUN"}
        for result in results
    )
    return (1 if failed_required else 0), report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_config(config_path)

    exit_code, report_path = run_platform(config, bool(args.dry_run))

    print()
    print("=" * 110)
    print("POLYMARKET INSTITUTIONAL PLATFORM ORCHESTRATOR")
    print("=" * 110)
    print(f"Mode:                  {'DRY RUN' if args.dry_run else 'EXECUTION'}")
    print(f"Master report:         {report_path}")
    print(f"Database modified:     NO (by orchestrator)")
    print(f"Exit code:             {exit_code}")
    print("=" * 110)

    if not args.no_open and report_path.exists():
        os.startfile(str(report_path))

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

