from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .exceptions import SnapshotStorageError
from .models import (
    Snapshot,
    SnapshotConsensus,
    SnapshotMarket,
    SnapshotMetadata,
    SnapshotWallet,
)
from .types import MarketId, SnapshotId, WalletId
from .validator import SnapshotValidator


class SQLiteSnapshotStorage:
    def __init__(
        self,
        database_path: str | Path,
        *,
        validator: SnapshotValidator | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.validator = validator or SnapshotValidator()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS historical_snapshots (
                        snapshot_id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        schema_version TEXT NOT NULL,
                        platform_version TEXT NOT NULL,
                        wallet_count INTEGER NOT NULL,
                        market_count INTEGER NOT NULL,
                        consensus_count INTEGER NOT NULL,
                        checksum TEXT NOT NULL,
                        attributes_json TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS historical_snapshot_wallets (
                        snapshot_id TEXT NOT NULL,
                        wallet_id TEXT NOT NULL,
                        market_id TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        shares TEXT NOT NULL,
                        average_price TEXT NOT NULL,
                        current_price TEXT NOT NULL,
                        current_value TEXT NOT NULL,
                        cash_pnl TEXT NOT NULL,
                        percent_pnl TEXT NOT NULL,
                        PRIMARY KEY (snapshot_id, wallet_id, market_id, outcome),
                        FOREIGN KEY (snapshot_id)
                          REFERENCES historical_snapshots(snapshot_id)
                          ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS historical_snapshot_markets (
                        snapshot_id TEXT NOT NULL,
                        market_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        category TEXT NOT NULL,
                        status TEXT NOT NULL,
                        yes_price TEXT,
                        no_price TEXT,
                        PRIMARY KEY (snapshot_id, market_id),
                        FOREIGN KEY (snapshot_id)
                          REFERENCES historical_snapshots(snapshot_id)
                          ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS historical_snapshot_consensus (
                        snapshot_id TEXT NOT NULL,
                        market_id TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        wallet_count INTEGER NOT NULL,
                        combined_shares TEXT NOT NULL,
                        combined_value TEXT NOT NULL,
                        combined_pnl TEXT NOT NULL,
                        conviction_score TEXT NOT NULL,
                        conviction_grade TEXT NOT NULL,
                        PRIMARY KEY (snapshot_id, market_id, outcome),
                        FOREIGN KEY (snapshot_id)
                          REFERENCES historical_snapshots(snapshot_id)
                          ON DELETE CASCADE
                    );
                    CREATE INDEX IF NOT EXISTS idx_historical_snapshots_created
                      ON historical_snapshots(created_at);
                    CREATE INDEX IF NOT EXISTS idx_historical_wallet_market
                      ON historical_snapshot_wallets(wallet_id, market_id);
                    CREATE INDEX IF NOT EXISTS idx_historical_consensus_market
                      ON historical_snapshot_consensus(market_id, outcome);
                    """
                )
        except sqlite3.Error as exc:
            raise SnapshotStorageError(
                f"failed to initialize snapshot storage: {exc}"
            ) from exc

    def save(self, snapshot: Snapshot) -> None:
        self.validator.validate(snapshot)
        self.initialize()
        sid = str(snapshot.metadata.snapshot_id)
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO historical_snapshots
                    (snapshot_id, created_at, schema_version, platform_version,
                     wallet_count, market_count, consensus_count, checksum,
                     attributes_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sid,
                        snapshot.metadata.created_at.isoformat(),
                        snapshot.metadata.schema_version,
                        snapshot.metadata.platform_version,
                        snapshot.metadata.wallet_count,
                        snapshot.metadata.market_count,
                        snapshot.metadata.consensus_count,
                        snapshot.metadata.checksum,
                        json.dumps(dict(snapshot.attributes), sort_keys=True, default=str),
                    ),
                )
                connection.executemany(
                    """INSERT INTO historical_snapshot_wallets
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            sid, str(item.wallet_id), str(item.market_id),
                            item.outcome, str(item.shares), str(item.average_price),
                            str(item.current_price), str(item.current_value),
                            str(item.cash_pnl), str(item.percent_pnl),
                        )
                        for item in snapshot.wallets
                    ],
                )
                connection.executemany(
                    """INSERT INTO historical_snapshot_markets
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            sid, str(item.market_id), item.title, item.category,
                            item.status,
                            None if item.yes_price is None else str(item.yes_price),
                            None if item.no_price is None else str(item.no_price),
                        )
                        for item in snapshot.markets
                    ],
                )
                connection.executemany(
                    """INSERT INTO historical_snapshot_consensus
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            sid, str(item.market_id), item.outcome,
                            item.wallet_count, str(item.combined_shares),
                            str(item.combined_value), str(item.combined_pnl),
                            str(item.conviction_score), item.conviction_grade,
                        )
                        for item in snapshot.consensus
                    ],
                )
        except sqlite3.IntegrityError as exc:
            raise SnapshotStorageError(
                f"snapshot already exists or violates integrity: {exc}"
            ) from exc
        except sqlite3.Error as exc:
            raise SnapshotStorageError(f"failed to save snapshot: {exc}") from exc

    def load(self, snapshot_id: str) -> Snapshot:
        self.initialize()
        try:
            with self._connect() as connection:
                m = connection.execute(
                    """SELECT snapshot_id, created_at, schema_version,
                    platform_version, wallet_count, market_count,
                    consensus_count, checksum, attributes_json
                    FROM historical_snapshots WHERE snapshot_id = ?""",
                    (snapshot_id,),
                ).fetchone()
                if m is None:
                    raise SnapshotStorageError(f"snapshot not found: {snapshot_id}")

                wallets = tuple(
                    SnapshotWallet(
                        wallet_id=WalletId(r[0]), market_id=MarketId(r[1]),
                        outcome=r[2], shares=Decimal(r[3]),
                        average_price=Decimal(r[4]), current_price=Decimal(r[5]),
                        current_value=Decimal(r[6]), cash_pnl=Decimal(r[7]),
                        percent_pnl=Decimal(r[8]),
                    )
                    for r in connection.execute(
                        """SELECT wallet_id, market_id, outcome, shares,
                        average_price, current_price, current_value,
                        cash_pnl, percent_pnl
                        FROM historical_snapshot_wallets
                        WHERE snapshot_id = ?
                        ORDER BY wallet_id, market_id, outcome""",
                        (snapshot_id,),
                    )
                )
                markets = tuple(
                    SnapshotMarket(
                        market_id=MarketId(r[0]), title=r[1], category=r[2],
                        status=r[3],
                        yes_price=None if r[4] is None else Decimal(r[4]),
                        no_price=None if r[5] is None else Decimal(r[5]),
                    )
                    for r in connection.execute(
                        """SELECT market_id, title, category, status,
                        yes_price, no_price
                        FROM historical_snapshot_markets
                        WHERE snapshot_id = ? ORDER BY market_id""",
                        (snapshot_id,),
                    )
                )
                consensus = tuple(
                    SnapshotConsensus(
                        market_id=MarketId(r[0]), outcome=r[1], wallet_count=r[2],
                        combined_shares=Decimal(r[3]),
                        combined_value=Decimal(r[4]), combined_pnl=Decimal(r[5]),
                        conviction_score=Decimal(r[6]), conviction_grade=r[7],
                    )
                    for r in connection.execute(
                        """SELECT market_id, outcome, wallet_count,
                        combined_shares, combined_value, combined_pnl,
                        conviction_score, conviction_grade
                        FROM historical_snapshot_consensus
                        WHERE snapshot_id = ? ORDER BY market_id, outcome""",
                        (snapshot_id,),
                    )
                )

            metadata = SnapshotMetadata(
                snapshot_id=SnapshotId(m[0]),
                created_at=datetime.fromisoformat(m[1]),
                schema_version=m[2],
                platform_version=m[3],
                wallet_count=m[4],
                market_count=m[5],
                consensus_count=m[6],
                checksum=m[7],
            )
            snapshot = Snapshot.create(
                metadata=metadata,
                wallets=wallets,
                markets=markets,
                consensus=consensus,
                attributes=json.loads(m[8]),
            )
            self.validator.validate(snapshot)
            return snapshot
        except SnapshotStorageError:
            raise
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise SnapshotStorageError(f"failed to load snapshot: {exc}") from exc

    def list_metadata(self) -> tuple[SnapshotMetadata, ...]:
        self.initialize()
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT snapshot_id, created_at, schema_version,
                    platform_version, wallet_count, market_count,
                    consensus_count, checksum
                    FROM historical_snapshots
                    ORDER BY created_at, snapshot_id"""
                ).fetchall()
            return tuple(
                SnapshotMetadata(
                    snapshot_id=SnapshotId(r[0]),
                    created_at=datetime.fromisoformat(r[1]),
                    schema_version=r[2],
                    platform_version=r[3],
                    wallet_count=r[4],
                    market_count=r[5],
                    consensus_count=r[6],
                    checksum=r[7],
                )
                for r in rows
            )
        except sqlite3.Error as exc:
            raise SnapshotStorageError(
                f"failed to list snapshot metadata: {exc}"
            ) from exc
