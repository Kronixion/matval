from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from types import TracebackType
from typing import Any

import psycopg
from psycopg import Connection, Cursor, Transaction
from psycopg.rows import DictRow, RowFactory, dict_row
from psycopg.sql import SQL, Composed

from matval_core.db.config import PostgresConfig


class PostgresConnector:
    def __init__(
        self,
        config: PostgresConfig | None = None,
        *,
        row_factory: RowFactory[DictRow] = dict_row,
        autocommit: bool = False,
    ) -> None:
        self._config = config or PostgresConfig()
        self._row_factory = row_factory
        self._autocommit = autocommit
        self._connection: Connection[Any] | None = None

    @property
    def connection(self) -> Connection[Any]:
        if self._connection is None or self._connection.closed:
            self._connection = psycopg.connect(**self._config.to_connection_kwargs())
            self._connection.autocommit = self._autocommit
        return self._connection

    def close(self) -> None:
        if self._connection is not None and not self._connection.closed:
            self._connection.close()

    def __enter__(self) -> PostgresConnector:
        return self

    def __exit__(self, exc_type: type[BaseException], exc: BaseException, tb: TracebackType) -> None:
        if exc and self._connection is not None and not self.connection.autocommit:
            self._connection.rollback()
        self.close()

    @contextmanager
    def cursor(self, *, row_factory: RowFactory | None = None) -> Iterator[Cursor[Any]]:
        factory = row_factory or self._row_factory
        with self.connection.cursor(row_factory=factory) as cur:
            yield cur

    def sql_query(
        self,
        sql: str | bytes | SQL | Composed,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
        *,
        row_factory: RowFactory | None = None,
    ) -> list[Any]:
        try:
            with self.cursor(row_factory=row_factory) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        except psycopg.Error:
            if not self.connection.autocommit:
                self.connection.rollback()
            raise

    def scalar_query(
        self,
        sql: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> Any:
        try:
            with self.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                if row is None:
                    return None
                if isinstance(row, Mapping):
                    return next(iter(row.values()))
                if isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
                    return row[0]
                return row
        except psycopg.Error:
            if not self.connection.autocommit:
                self.connection.rollback()
            raise

    def non_sql_query(
        self,
        sql: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> int:
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def execute_many(
        self,
        sql: str,
        param_list: Iterable[Sequence[Any] | Mapping[str, Any]],
    ) -> int:
        with self.cursor() as cur:
            cur.executemany(sql, param_list)
            return cur.rowcount

    def ping(self) -> bool:
        try:
            self.scalar_query("SELECT 1")
        except psycopg.Error:
            return False
        return True

    @contextmanager
    def transaction(self) -> Iterator[Transaction]:
        with self.connection.transaction() as tx:
            yield tx


__all__ = ["PostgresConnector", "PostgresConfig"]
