from __future__ import annotations

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
