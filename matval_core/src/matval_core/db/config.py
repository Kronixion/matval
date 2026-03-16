from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True, slots=True)
class PostgresConfig:
    """DB connection settings, read from environment variables."""

    host: str = "localhost"
    port: int = 5432
    dbname: str = "supermarket_items"
    user: str = "postgres"
    password: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> PostgresConfig:
        return cls(
            host = os.getenv("POSTGRES_HOST", "localhost"),
            port = int(os.getenv("POSTGRES_PORT", "5432")),
            dbname = os.getenv("POSTGRES_DB", "supermarket_items"),
            user = os.getenv("POSTGRES_USER", "postgres"),
            password = os.getenv("POSTGRES_PASSWORD", "")
        )

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
