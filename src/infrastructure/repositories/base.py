from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from src.core.exceptions import RepositoryError
from src.infrastructure.database import DatabaseSession


SqlParameters = (
    Sequence[Any]
    | Mapping[str, Any]
)


class BaseRepository:
    """
    Shared repository foundation.

    Concrete repositories own SQL for one persistence concern.
    Intelligence engines should depend on repositories rather than
    executing SQL directly.
    """

    def __init__(
        self,
        session: DatabaseSession | None = None,
    ) -> None:
        self._session = session or DatabaseSession()

    @property
    def session(self) -> DatabaseSession:
        return self._session

    def fetch_one(
        self,
        query: str,
        parameters: SqlParameters = (),
    ) -> sqlite3.Row | None:
        try:
            with self._session.connection(
                read_only=True
            ) as connection:
                return connection.execute(
                    query,
                    parameters,
                ).fetchone()

        except Exception as error:
            raise RepositoryError(
                f"{type(self).__name__}.fetch_one failed: {error}"
            ) from error

    def fetch_all(
        self,
        query: str,
        parameters: SqlParameters = (),
    ) -> list[sqlite3.Row]:
        try:
            with self._session.connection(
                read_only=True
            ) as connection:
                rows = connection.execute(
                    query,
                    parameters,
                ).fetchall()

            return list(rows)

        except Exception as error:
            raise RepositoryError(
                f"{type(self).__name__}.fetch_all failed: {error}"
            ) from error

    def execute(
        self,
        query: str,
        parameters: SqlParameters = (),
    ) -> int:
        try:
            with self._session.transaction() as connection:
                cursor = connection.execute(
                    query,
                    parameters,
                )

                return cursor.rowcount

        except Exception as error:
            raise RepositoryError(
                f"{type(self).__name__}.execute failed: {error}"
            ) from error

    def execute_insert(
        self,
        query: str,
        parameters: SqlParameters = (),
    ) -> int:
        try:
            with self._session.transaction() as connection:
                cursor = connection.execute(
                    query,
                    parameters,
                )

                if cursor.lastrowid is None:
                    raise RepositoryError(
                        "Insert completed without a row identifier."
                    )

                return int(cursor.lastrowid)

        except RepositoryError:
            raise

        except Exception as error:
            raise RepositoryError(
                f"{type(self).__name__}.execute_insert failed: {error}"
            ) from error

    def execute_many(
        self,
        query: str,
        parameter_rows: Iterable[SqlParameters],
    ) -> int:
        rows = list(parameter_rows)

        if not rows:
            return 0

        try:
            with self._session.transaction() as connection:
                cursor = connection.executemany(
                    query,
                    rows,
                )

                return cursor.rowcount

        except Exception as error:
            raise RepositoryError(
                f"{type(self).__name__}.execute_many failed: {error}"
            ) from error

    def table_exists(self, table_name: str) -> bool:
        normalized_name = str(table_name or "").strip()

        if not normalized_name:
            raise ValueError("table_name cannot be empty.")

        row = self.fetch_one(
            """
            SELECT
                1
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name = ?
            LIMIT 1
            """,
            (normalized_name,),
        )

        return row is not None