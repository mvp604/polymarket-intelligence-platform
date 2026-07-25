from __future__ import annotations

import ast
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT_MARKERS = ("src", "tests", "manage.py")

FILES: dict[str, str] = {}

FILES["src/snapshots/live_adapter.py"] = '''from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from .models import SnapshotConsensus, SnapshotMarket, SnapshotWallet


def _decimal(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


class LiveSnapshotAdapter:
    """Reads current platform state from the existing SQLite database."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def load_wallets(self) -> tuple[SnapshotWallet, ...]:
        with self._connect() as connection:
            columns = self._columns(connection, "positions")
            if not columns:
                return ()

            rows = connection.execute(
                """
                SELECT p.*
                FROM positions p
                JOIN (
                    SELECT wallet, MAX(scan_id) AS max_scan_id
                    FROM positions
                    GROUP BY wallet
                ) latest
                  ON latest.wallet = p.wallet
                 AND latest.max_scan_id = p.scan_id
                ORDER BY p.wallet, p.market_id, p.outcome
                """
            ).fetchall()

        results: list[SnapshotWallet] = []
        for row in rows:
            item = dict(row)
            results.append(
                SnapshotWallet(
                    wallet_id=str(item.get("wallet", "")),
                    market_id=str(item.get("market_id", "")),
                    outcome=str(item.get("outcome", "")),
                    shares=_decimal(item.get("shares")),
                    average_price=_decimal(item.get("average_price")),
                    current_price=_decimal(item.get("current_price")),
                    current_value=_decimal(item.get("current_value")),
                    cash_pnl=_decimal(item.get("cash_pnl")),
                    percent_pnl=_decimal(item.get("percent_pnl")),
                )
            )
        return tuple(results)

    def load_markets(
        self,
        wallets: Iterable[SnapshotWallet],
    ) -> tuple[SnapshotMarket, ...]:
        wallet_market_ids = sorted({str(item.market_id) for item in wallets})
        if not wallet_market_ids:
            return ()

        with self._connect() as connection:
            metadata_table = self._first_existing_table(
                connection,
                ("markets", "market_metadata", "polymarket_markets"),
            )

            metadata_by_id: dict[str, dict[str, Any]] = {}
            if metadata_table:
                placeholders = ",".join("?" for _ in wallet_market_ids)
                table_columns = self._columns(connection, metadata_table)
                market_key = self._first_present(
                    table_columns,
                    ("market_id", "id", "condition_id", "conditionId"),
                )
                if market_key:
                    rows = connection.execute(
                        f"SELECT * FROM {metadata_table} "
                        f"WHERE {market_key} IN ({placeholders})",
                        wallet_market_ids,
                    ).fetchall()
                    metadata_by_id = {
                        str(dict(row).get(market_key)): dict(row) for row in rows
                    }

            position_rows = connection.execute(
                """
                SELECT market_id, MAX(title) AS title,
                       MAX(current_price) AS current_price
                FROM positions
                WHERE market_id IN ({})
                GROUP BY market_id
                """.format(",".join("?" for _ in wallet_market_ids)),
                wallet_market_ids,
            ).fetchall()

        position_by_id = {str(row["market_id"]): dict(row) for row in position_rows}
        results: list[SnapshotMarket] = []

        for market_id in wallet_market_ids:
            metadata = metadata_by_id.get(market_id, {})
            position = position_by_id.get(market_id, {})
            title = str(
                metadata.get("title")
                or metadata.get("question")
                or position.get("title")
                or market_id
            )
            category = str(
                metadata.get("category")
                or metadata.get("sport")
                or metadata.get("series")
                or "unknown"
            )
            status = str(
                metadata.get("status")
                or ("closed" if metadata.get("closed") else "active")
            )
            yes_price = self._optional_decimal(
                metadata.get("yes_price")
                or metadata.get("yesPrice")
                or metadata.get("current_price")
                or position.get("current_price")
            )
            no_price = self._optional_decimal(
                metadata.get("no_price") or metadata.get("noPrice")
            )
            if no_price is None and yes_price is not None and Decimal("0") <= yes_price <= Decimal("1"):
                no_price = Decimal("1") - yes_price

            results.append(
                SnapshotMarket(
                    market_id=market_id,
                    title=title,
                    category=category,
                    status=status,
                    yes_price=yes_price,
                    no_price=no_price,
                )
            )
        return tuple(results)

    def load_consensus(self) -> tuple[SnapshotConsensus, ...]:
        with self._connect() as connection:
            columns = self._columns(connection, "consensus_history")
            if not columns:
                return ()

            order_column = "scanned_at" if "scanned_at" in columns else "id"
            rows = connection.execute(
                f"""
                SELECT c.*
                FROM consensus_history c
                JOIN (
                    SELECT market_id, outcome, MAX({order_column}) AS latest_value
                    FROM consensus_history
                    GROUP BY market_id, outcome
                ) latest
                  ON latest.market_id = c.market_id
                 AND latest.outcome = c.outcome
                 AND latest.latest_value = c.{order_column}
                ORDER BY c.market_id, c.outcome
                """
            ).fetchall()

        results: list[SnapshotConsensus] = []
        for row in rows:
            item = dict(row)
            results.append(
                SnapshotConsensus(
                    market_id=str(item.get("market_id", "")),
                    outcome=str(item.get("outcome", "")),
                    wallet_count=int(item.get("wallet_count") or 0),
                    combined_shares=_decimal(item.get("combined_shares")),
                    combined_value=_decimal(item.get("combined_value")),
                    combined_pnl=_decimal(item.get("combined_pnl")),
                    conviction_score=_decimal(item.get("conviction_score")),
                    conviction_grade=str(item.get("conviction_grade") or "UNRATED"),
                )
            )
        return tuple(results)

    def source_fingerprint(self) -> str:
        with self._connect() as connection:
            scan_row = connection.execute(
                "SELECT MAX(id), MAX(scanned_at) FROM wallet_scans"
            ).fetchone() if self._columns(connection, "wallet_scans") else None
            consensus_row = connection.execute(
                "SELECT MAX(id), MAX(scanned_at) FROM consensus_history"
            ).fetchone() if self._columns(connection, "consensus_history") else None

        scan_part = "none:none" if scan_row is None else f"{scan_row[0]}:{scan_row[1]}"
        consensus_part = (
            "none:none"
            if consensus_row is None
            else f"{consensus_row[0]}:{consensus_row[1]}"
        )
        return f"wallet_scans={scan_part}|consensus_history={consensus_part}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if row is None:
            return set()
        return {
            str(item["name"])
            for item in connection.execute(f"PRAGMA table_info({table})")
        }

    def _first_existing_table(
        self,
        connection: sqlite3.Connection,
        candidates: tuple[str, ...],
    ) -> str | None:
        for table in candidates:
            if self._columns(connection, table):
                return table
        return None

    @staticmethod
    def _first_present(columns: set[str], candidates: tuple[str, ...]) -> str | None:
        return next((item for item in candidates if item in columns), None)

    @staticmethod
    def _optional_decimal(value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            result = Decimal(str(value))
        except Exception:
            return None
        return result if Decimal("0") <= result <= Decimal("1") else None
'''

FILES["src/snapshots/service.py"] = '''from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .exceptions import SnapshotStorageError
from .live_adapter import LiveSnapshotAdapter
from .loader import SnapshotLoader
from .models import Snapshot
from .storage import SQLiteSnapshotStorage


class LiveSnapshotService:
    """Creates persisted historical snapshots from the live platform database."""

    def __init__(
        self,
        source_database: str | Path,
        snapshot_database: str | Path | None = None,
        *,
        schema_version: str = "1.0",
        platform_version: str = "0.1",
    ) -> None:
        self.source_database = Path(source_database)
        self.snapshot_database = Path(snapshot_database or source_database)
        self.adapter = LiveSnapshotAdapter(self.source_database)
        self.loader = SnapshotLoader(
            schema_version=schema_version,
            platform_version=platform_version,
        )
        self.storage = SQLiteSnapshotStorage(self.snapshot_database)

    def create(self, *, force: bool = False) -> Snapshot:
        fingerprint = self.adapter.source_fingerprint()
        snapshot_id = self._snapshot_id(fingerprint)

        existing = self._find_existing(snapshot_id)
        if existing is not None and not force:
            raise SnapshotStorageError(
                "snapshot already exists for the latest source state: "
                f"{snapshot_id}. Use force=True only for diagnostics."
            )
        if existing is not None and force:
            snapshot_id = self._snapshot_id(
                fingerprint + "|forced=" + datetime.now(timezone.utc).isoformat()
            )

        wallets = self.adapter.load_wallets()
        markets = self.adapter.load_markets(wallets)
        consensus = self.adapter.load_consensus()

        snapshot = self.loader.build(
            snapshot_id=snapshot_id,
            wallets=wallets,
            markets=markets,
            consensus=consensus,
            attributes={
                "source_database": str(self.source_database),
                "source_fingerprint": fingerprint,
                "capture_mode": "live",
            },
        )
        self.storage.save(snapshot)
        return snapshot

    def _find_existing(self, snapshot_id: str):
        return next(
            (
                item
                for item in self.storage.list_metadata()
                if str(item.snapshot_id) == snapshot_id
            ),
            None,
        )

    @staticmethod
    def _snapshot_id(fingerprint: str) -> str:
        digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]
        return f"live-{digest}"
'''

FILES["src/snapshots/cli.py"] = '''from __future__ import annotations

import argparse
import json
from pathlib import Path

from .service import LiveSnapshotService
from .storage import SQLiteSnapshotStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="snapshot")
    parser.add_argument(
        "--database",
        default="database/polymarket.db",
        help="SQLite database path",
    )
    subparsers = parser.add_subparsers(dest="snapshot_command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a live snapshot")
    create_parser.add_argument("--force", action="store_true")

    subparsers.add_parser("list", help="List stored snapshots")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect one snapshot")
    inspect_parser.add_argument("snapshot_id")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database = Path(args.database)

    if args.snapshot_command == "create":
        snapshot = LiveSnapshotService(database).create(force=args.force)
        print(f"Snapshot created: {snapshot.metadata.snapshot_id}")
        print(f"Created UTC: {snapshot.metadata.created_at.isoformat()}")
        print(f"Wallet positions: {snapshot.metadata.wallet_count}")
        print(f"Markets: {snapshot.metadata.market_count}")
        print(f"Consensus records: {snapshot.metadata.consensus_count}")
        print(f"Checksum: {snapshot.metadata.checksum}")
        return 0

    storage = SQLiteSnapshotStorage(database)

    if args.snapshot_command == "list":
        items = storage.list_metadata()
        if not items:
            print("No historical snapshots found.")
            return 0
        for item in items:
            print(
                f"{item.snapshot_id} | {item.created_at.isoformat()} | "
                f"wallets={item.wallet_count} markets={item.market_count} "
                f"consensus={item.consensus_count}"
            )
        return 0

    if args.snapshot_command == "inspect":
        snapshot = storage.load(args.snapshot_id)
        print(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(run())
'''

FILES["snapshot_manage.py"] = '''from src.snapshots.cli import run


if __name__ == "__main__":
    raise SystemExit(run())
'''

FILES["tests/snapshots/test_live_integration.py"] = '''from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.snapshots.exceptions import SnapshotStorageError
from src.snapshots.live_adapter import LiveSnapshotAdapter
from src.snapshots.service import LiveSnapshotService
from src.snapshots.storage import SQLiteSnapshotStorage


def build_live_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE wallet_scans (
                id INTEGER PRIMARY KEY,
                wallet TEXT NOT NULL,
                scanned_at TEXT NOT NULL
            );

            CREATE TABLE positions (
                id INTEGER PRIMARY KEY,
                scan_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                shares REAL NOT NULL,
                average_price REAL NOT NULL,
                current_price REAL NOT NULL,
                current_value REAL NOT NULL,
                cash_pnl REAL NOT NULL,
                percent_pnl REAL NOT NULL
            );

            CREATE TABLE consensus_history (
                id INTEGER PRIMARY KEY,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                wallet_count INTEGER NOT NULL,
                combined_shares REAL NOT NULL,
                combined_value REAL NOT NULL,
                combined_pnl REAL NOT NULL,
                conviction_score REAL NOT NULL,
                conviction_grade TEXT NOT NULL,
                average_entry_price REAL,
                average_current_price REAL,
                observed_price_move REAL,
                scanned_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO wallet_scans VALUES (1, '0xabc', '2026-07-24T12:00:00+00:00')"
        )
        connection.execute(
            """
            INSERT INTO positions VALUES (
                1, 1, '0xabc', 'market-1', 'Example market', 'YES',
                10, 0.4, 0.55, 5.5, 1.5, 37.5
            )
            """
        )
        connection.execute(
            """
            INSERT INTO consensus_history VALUES (
                1, 'market-1', 'Example market', 'YES', 1,
                10, 5.5, 1.5, 82.5, 'A', 0.4, 0.55, 0.15,
                '2026-07-24T12:00:00+00:00'
            )
            """
        )


def test_live_adapter_reads_current_state(tmp_path):
    database = tmp_path / "live.db"
    build_live_database(database)
    adapter = LiveSnapshotAdapter(database)

    wallets = adapter.load_wallets()
    markets = adapter.load_markets(wallets)
    consensus = adapter.load_consensus()

    assert len(wallets) == 1
    assert len(markets) == 1
    assert markets[0].title == "Example market"
    assert len(consensus) == 1


def test_live_service_creates_persisted_snapshot(tmp_path):
    database = tmp_path / "live.db"
    build_live_database(database)

    snapshot = LiveSnapshotService(database).create()
    restored = SQLiteSnapshotStorage(database).load(
        str(snapshot.metadata.snapshot_id)
    )

    assert restored.metadata.wallet_count == 1
    assert restored.metadata.market_count == 1
    assert restored.metadata.consensus_count == 1
    assert restored.attributes["capture_mode"] == "live"


def test_duplicate_source_state_is_rejected(tmp_path):
    database = tmp_path / "live.db"
    build_live_database(database)
    service = LiveSnapshotService(database)
    service.create()

    with pytest.raises(SnapshotStorageError, match="already exists"):
        service.create()


def test_force_creates_diagnostic_duplicate(tmp_path):
    database = tmp_path / "live.db"
    build_live_database(database)
    service = LiveSnapshotService(database)
    first = service.create()
    second = service.create(force=True)

    assert first.metadata.snapshot_id != second.metadata.snapshot_id
    assert len(SQLiteSnapshotStorage(database).list_metadata()) == 2
'''

FILES["docs/CORE-003-SPRINT-3.3.md"] = '''# CORE-003 Sprint 3.3 — Live Snapshot Integration

Implemented:

- Live SQLite adapter for current wallet positions
- Market-state construction with metadata fallback
- Latest consensus-history adapter
- Deterministic source fingerprinting
- Duplicate-run protection
- Live snapshot orchestration service
- Snapshot create, list, and inspect CLI
- Live integration test coverage

Commands:

```powershell
python snapshot_manage.py create
python snapshot_manage.py list
python snapshot_manage.py inspect <snapshot-id>
```

Optional custom database:

```powershell
python snapshot_manage.py --database database/polymarket.db create
```
'''


def find_root() -> Path:
    root = Path.cwd().resolve()
    missing = [name for name in ROOT_MARKERS if not (root / name).exists()]
    if missing:
        raise SystemExit(
            "Run this installer from the project root. Missing: "
            + ", ".join(missing)
        )
    return root


def create_backup(root: Path) -> Path:
    destination = root / "backups" / (
        "core_003_sprint_3_3_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    destination.mkdir(parents=True, exist_ok=False)

    tracked = list(FILES) + [
        "src/snapshots/__init__.py",
        "CURRENT_SPRINT.md",
        "PROJECT_STATUS.md",
        "NEXT_TASK.md",
        "CHANGELOG.md",
    ]
    for relative in tracked:
        source = root / relative
        if source.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return destination


def write_files(root: Path) -> None:
    for relative, content in FILES.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        print(f"Installed {relative}")


def update_snapshot_init(root: Path) -> None:
    path = root / "src/snapshots/__init__.py"
    text = path.read_text(encoding="utf-8")
    imports = [
        "from .live_adapter import LiveSnapshotAdapter",
        "from .service import LiveSnapshotService",
    ]
    missing_imports = [line for line in imports if line not in text]
    if missing_imports:
        text = "\n".join(missing_imports) + "\n" + text

    names = ["LiveSnapshotAdapter", "LiveSnapshotService"]
    if "__all__" in text:
        for name in names:
            if f'"{name}"' not in text:
                text = text.replace(
                    "__all__ = [",
                    f'__all__ = [\n    "{name}",',
                    1,
                )
    path.write_text(text, encoding="utf-8", newline="\n")
    print("Updated src/snapshots/__init__.py")


def validate_python(root: Path) -> None:
    paths = [root / relative for relative in FILES if relative.endswith(".py")]
    paths.append(root / "src/snapshots/__init__.py")
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print("Python syntax validation passed")


def update_docs(root: Path) -> None:
    (root / "CURRENT_SPRINT.md").write_text(
        "# Current Sprint\n\n"
        "CORE-003 Sprint 3.3 — Live Snapshot Integration\n"
        "Status: Implemented; awaiting validation\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "NEXT_TASK.md").write_text(
        "# Next Task\n\n"
        "Validate Sprint 3.3, create the first real historical snapshot, "
        "then add replay delta and accumulation analytics.\n",
        encoding="utf-8",
        newline="\n",
    )

    status_path = root / "PROJECT_STATUS.md"
    existing = status_path.read_text(encoding="utf-8") if status_path.exists() else "# Project Status\n"
    line = "- CORE-003 Sprint 3.3 Live Snapshot Integration: Implemented; awaiting validation"
    if line not in existing:
        status_path.write_text(existing.rstrip() + "\n" + line + "\n", encoding="utf-8", newline="\n")

    changelog = root / "CHANGELOG.md"
    existing = changelog.read_text(encoding="utf-8") if changelog.exists() else "# Changelog\n"
    marker = "## CORE-003 Sprint 3.3"
    if marker not in existing:
        entry = (
            "\n## CORE-003 Sprint 3.3\n\n"
            "- Connected live positions and consensus data to snapshots.\n"
            "- Added deterministic duplicate-run protection.\n"
            "- Added create, list, and inspect snapshot commands.\n"
            "- Added live SQLite integration tests.\n"
        )
        changelog.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8", newline="\n")
    print("Updated project documentation")


def main() -> int:
    root = find_root()
    backup = create_backup(root)
    print(f"Backup created: {backup}")
    write_files(root)
    update_snapshot_init(root)
    validate_python(root)
    update_docs(root)

    print("\nCORE-003 Sprint 3.3 installed.")
    print("Run:")
    print("  python manage.py test")
    print("  python -m pytest tests/snapshots -q")
    print("  python snapshot_manage.py create")
    print("  python snapshot_manage.py list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())