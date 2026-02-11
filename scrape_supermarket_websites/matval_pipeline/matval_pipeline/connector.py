"""PostgreSQL connector — consolidated from the existing codebase."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Mapping, MutableMapping, Optional, Sequence

import psycopg
from psycopg import Connection, Cursor
from psycopg.rows import RowFactory, dict_row


@dataclass(frozen=True, slots=True)
class PostgresConfig:
    """Connection information for the PostgreSQL instance."""

    host: str = "localhost"
    port: int = 5432
    dbname: str = "supermarket_items"
    user: str = "postgres"
    password: str = ""
    options: MutableMapping[str, Any] = field(default_factory=dict)

    def to_connection_kwargs(self) -> Mapping[str, Any]:
        base: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
        }
        if self.options:
            base.update(self.options)
        return base


class PostgresConnector:
    """Lightweight convenience wrapper around ``psycopg.Connection``."""

    def __init__(
        self,
        config: Optional[PostgresConfig] = None,
        *,
        row_factory: Optional[RowFactory] = dict_row,
        autocommit: bool = False,
    ) -> None:
        self._config = config or PostgresConfig()
        self._row_factory = row_factory
        self._autocommit = autocommit
        self._connection: Optional[Connection[Any]] = None

    @property
    def connection(self) -> Connection[Any]:
        if self._connection is None or self._connection.closed:
            self._connection = psycopg.connect(**self._config.to_connection_kwargs())
            self._connection.autocommit = self._autocommit
        return self._connection

    def close(self) -> None:
        if self._connection is not None and not self._connection.closed:
            self._connection.close()

    def __enter__(self) -> "PostgresConnector":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc and self._connection is not None and not self.connection.autocommit:
            self._connection.rollback()
        self.close()

    @contextmanager
    def cursor(self, *, row_factory: Optional[RowFactory] = None) -> Iterator[Cursor[Any]]:
        factory = row_factory or self._row_factory
        with self.connection.cursor(row_factory=factory) as cur:
            yield cur

    def sql_query(
        self,
        sql: str,
        params: Optional[Iterable[Any] | Mapping[str, Any]] = None,
        *,
        row_factory: Optional[RowFactory] = None,
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
        params: Optional[Iterable[Any] | Mapping[str, Any]] = None,
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
        params: Optional[Iterable[Any] | Mapping[str, Any]] = None,
    ) -> int:
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def execute_many(
        self,
        sql: str,
        param_list: Iterable[Iterable[Any] | Mapping[str, Any]],
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
    def transaction(self) -> Iterator[Connection[Any]]:
        with self.connection.transaction() as tx:
            yield tx


__all__ = ["PostgresConnector", "PostgresConfig"]
