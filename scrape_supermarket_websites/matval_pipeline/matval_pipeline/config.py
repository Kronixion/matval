"""Environment-variable-based database configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """DB connection settings, read from environment variables."""

    host: str = "localhost"
    port: int = 5432
    dbname: str = "supermarket_items"
    user: str = "postgres"
    password: str = ""

    @classmethod
    def from_env(cls: PipelineConfig) -> PipelineConfig:
        return cls(
            host = os.getenv("POSTGRES_HOST", "localhost"),
            port = int(os.getenv("POSTGRES_PORT", "5432")),
            dbname = os.getenv("POSTGRES_DB", "supermarket_items"),
            user = os.getenv("POSTGRES_USER", "postgres"),
            password = os.getenv("POSTGRES_PASSWORD", "")
        )