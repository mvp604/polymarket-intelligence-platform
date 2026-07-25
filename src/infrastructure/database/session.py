from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from src.core.exceptions import DatabaseError

from .connection import DatabaseConnectionFactory


class DatabaseSession:
    """
    Manages short-lived database connections.

    A normal connection does not commit automatically.
    A session transaction commits on success and rolls back on failure.
    """

    def __init__(
        self,
        connection_factory: DatabaseConnectionFactory | None = None,
    ) -> None:
        self._connection_factory = (
            connection_factory or DatabaseConnectionFactory()
        )

    @property
    def connection_factory(self) -> DatabaseConnectionFactory:
        return self._connection_factory

    @contextmanager
    def connection(
        self,
        *,
        read_only: bool = False,
    ) -> Iterator[sqlite3.Connection]:
        connection = self._connection_factory.create(
            read_only=read_only
        )

        try:
            yield connection

        except sqlite3.Error as error:
            raise DatabaseError(
                f"Database session failed: {error}"
            ) from error

        finally:
            connection.close()

    @contextmanager
    def transaction(
        self,
        *,
        immediate: bool = True,
    ) -> Iterator[sqlite3.Connection]:
        connection = self._connection_factory.create()

        try:
            connection.execute(
                "BEGIN IMMEDIATE" if immediate else "BEGIN"
            )

            yield connection

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()


_default_session = DatabaseSession()


@contextmanager
def database_connection(
    *,
    read_only: bool = False,
) -> Iterator[sqlite3.Connection]:
    """Open a connection using the default platform database session."""

    with _default_session.connection(
        read_only=read_only
    ) as connection:
        yield connection


@contextmanager
def database_session(
    *,
    immediate: bool = True,
) -> Iterator[sqlite3.Connection]:
    """
    Open a transaction using the default platform database session.

    Retained as the concise public transaction interface.
    """

    with _default_session.transaction(
        immediate=immediate
    ) as connection:
        yield connection