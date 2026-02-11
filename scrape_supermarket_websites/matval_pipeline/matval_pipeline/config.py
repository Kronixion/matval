"""Environment-variable-based database configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

STORE_IDS: dict[str, int] = {
    "coop": 1,
    "hemkop": 2,
    "ica": 3,
    "mathem": 4,
    "willys": 5,
}


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """DB connection settings, read from environment variables."""

    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    dbname: str = os.getenv("POSTGRES_DB", "supermarket_items")
    user: str = os.getenv("POSTGRES_USER", "postgres")
    password: str = os.getenv("POSTGRES_PASSWORD", "")
