# ruff: noqa: S101
from unittest.mock import MagicMock

import pytest

from matval_pipeline.connector import PostgresConnector
from matval_pipeline.config import PostgresConfig
from matval_pipeline.db_ops import DBOps
from matval_pipeline.pipeline import PostgresPipeline

@pytest.fixture()
def pipeline(pg_connector: PostgresConnector, apply_schema: None) -> PostgresPipeline:
    """Pipeline with dependencies injected directly — no open_spider needed."""
    p = PostgresPipeline("PipelineMart")
    p._connector = pg_connector
    p._ops = DBOps(pg_connector)
    p.supermarket_id = p._ops.get_or_create_supermarket("PipelineMart")
    return p

def test_from_crawler_sets_store_name() -> None:
    crawler = MagicMock()
    crawler.settings.get.return_value = "MyStore"
    p = PostgresPipeline.from_crawler(crawler)
    assert p.store_name == "MyStore"

def test_from_crawler_raises_if_store_name_missing() -> None:
    crawler = MagicMock()
    crawler.settings.get.return_value = None
    with pytest.raises(ValueError, match="STORE_NAME"):
        PostgresPipeline.from_crawler(crawler)

def test_open_spider_initializes_pipeline(
    pg_config: PostgresConfig,
    monkeypatch: pytest.MonkeyPatch,
    apply_schema: None,
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", pg_config.host)
    monkeypatch.setenv("POSTGRES_PORT", str(pg_config.port))
    monkeypatch.setenv("POSTGRES_DB", pg_config.dbname)
    monkeypatch.setenv("POSTGRES_USER", pg_config.user)
    monkeypatch.setenv("POSTGRES_PASSWORD", pg_config.password)

    p = PostgresPipeline("OpenSpiderMart")
    p.open_spider(None)

    assert p._connector is not None
    assert p._ops is not None
    assert isinstance(p.supermarket_id, int)

    p._connector.close()

def test_process_item_returns_item(pipeline: PostgresPipeline) -> None:
    item = {"name": "Milk", "price": "10.00", "currency": "SEK"}
    result = pipeline.process_item(item, None)
    assert result is item


def test_process_item_skips_item_without_name(pipeline: PostgresPipeline) -> None:
    item = {"price": "10.00"}
    result = pipeline.process_item(item, None)
    assert result is item 

def test_process_item_raises_if_not_initialized() -> None:
    p = PostgresPipeline("UninitMart")  
    with pytest.raises(RuntimeError, match="not properly initialized"):
        p.process_item({"name": "Milk"}, None)

def test_process_item_increments_count(pipeline: PostgresPipeline) -> None:
    pipeline.process_item({"name": "Bread", "currency": "SEK"}, None)
    assert pipeline._count == 1

def test_process_item_commits_every_100_items(pipeline: PostgresPipeline) -> None:
    for i in range(100):
        pipeline.process_item({"name": f"Product {i}", "currency": "SEK"}, None)
    assert pipeline._count == 100

def test_process_item_handles_db_exception_gracefully(pipeline: PostgresPipeline) -> None:
    pipeline._ops = MagicMock()
    pipeline._ops.get_or_create_category.side_effect = RuntimeError("db exploded")

    item = {"name": "FaultyProduct"}
    result = pipeline.process_item(item, None)
    assert result is item

def test_close_spider_closes_connector(pg_config: PostgresConfig, apply_schema: None) -> None:
    p = PostgresPipeline("CloseMart")
    p._connector = PostgresConnector(pg_config)
    p._ops = DBOps(p._connector)
    p.supermarket_id = p._ops.get_or_create_supermarket("CloseMart")

    p.close_spider(None)

    assert p._connector._connection.closed  # use private attr

def test_close_spider_with_no_connector_does_not_raise() -> None:
    p = PostgresPipeline("NeverOpenedMart")
    p.close_spider(None) 
