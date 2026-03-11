# assert is idiomatic in pytest, hence S101 is not a concern in tests
# ruff: noqa: S101

import pytest
from matval_pipeline.config import PostgresConfig


def test_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSTGRES_HOST", raising=False)                                                             
    monkeypatch.delenv("POSTGRES_PORT", raising=False)                                                           
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    cfg = PostgresConfig()
    assert cfg.host == "localhost"
    assert cfg.port == 5432
    assert cfg.dbname == "supermarket_items"
    assert cfg.user == "postgres"
    assert cfg.password == ""

def test_from_env_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "192.168.0.10")                                                             
    monkeypatch.setenv("POSTGRES_PORT", "5433")                                                           
    monkeypatch.setenv("POSTGRES_DB", "grocery_items")
    monkeypatch.setenv("POSTGRES_USER", "grocery_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "grocery_password")

    cfg = PostgresConfig.from_env()
    assert cfg.host == "192.168.0.10"
    assert cfg.port == 5433
    assert cfg.dbname == "grocery_items"
    assert cfg.user == "grocery_user"
    assert cfg.password == "grocery_password" #noqa: S105, dummy password