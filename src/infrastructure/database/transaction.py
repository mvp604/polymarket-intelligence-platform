from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .session import DatabaseSession


class TransactionManager:
    """
    Explicit transaction boundary used by repositories and services.
    """

    def __init__(
        self,
        session: DatabaseSession | None = None,
    ) -> None:
        self._session = session or DatabaseSession()

    @contextmanager
    def transaction(
        self,
        *,
        immediate: bool = True,
    ) -> Iterator[sqlite3.Connection]:
        with self._session.transaction(
            immediate=immediate
        ) as connection:
            yield connection