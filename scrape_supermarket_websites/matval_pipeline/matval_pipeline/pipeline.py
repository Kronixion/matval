"""Scrapy ItemPipeline that writes items directly to PostgreSQL."""

from __future__ import annotations

import logging
from typing import Any

from itemadapter import ItemAdapter

from .config import STORE_IDS, PipelineConfig
from .connector import PostgresConfig, PostgresConnector
from .db_ops import DBOps

_LOG = logging.getLogger(__name__)


class PostgresPipeline:
    """Scrapy pipeline: normalizes items and upserts them into the DB."""

    def __init__(self, store_name: str) -> None:
        self.store_name = store_name
        self.store_id = STORE_IDS[store_name]
        self._connector: PostgresConnector | None = None
        self._ops: DBOps | None = None
        self._count = 0

    # ------------------------------------------------------------------
    # Scrapy hooks
    # ------------------------------------------------------------------

    @classmethod
    def from_crawler(cls, crawler: Any) -> "PostgresPipeline":
        store_name = crawler.settings.get("STORE_NAME")
        if not store_name:
            raise ValueError("STORE_NAME must be set in Scrapy settings")
        if store_name not in STORE_IDS:
            raise ValueError(f"Unknown store: {store_name!r}. Valid: {list(STORE_IDS)}")
        return cls(store_name)

    def open_spider(self, spider: Any) -> None:
        cfg = PipelineConfig()
        pg_config = PostgresConfig(
            host=cfg.host,
            port=cfg.port,
            dbname=cfg.dbname,
            user=cfg.user,
            password=cfg.password,
        )
        self._connector = PostgresConnector(config=pg_config, autocommit=False)
        self._ops = DBOps(self._connector)
        _LOG.info("PostgresPipeline opened for store=%s (id=%d)", self.store_name, self.store_id)

    def process_item(self, item: Any, spider: Any) -> Any:
        adapter = ItemAdapter(item)

        name = adapter.get("name")
        if not name:
            _LOG.warning("Skipping item without a name: %s", item)
            return item

        try:
            category_id = self._ops.get_or_create_category(
                adapter.get("subcategory"), adapter.get("category")
            )
            product_id = self._ops.get_or_create_product(name, category_id)
            self._ops.upsert_store_product(
                self.store_id,
                product_id,
                url=adapter.get("url"),
                price=adapter.get("price"),
                unit_price=adapter.get("unit_price"),
                unit_quantity=adapter.get("unit_quantity"),
                unit_quantity_name=adapter.get("unit_quantity_name"),
                unit_quantity_abbrev=adapter.get("unit_quantity_abbrev"),
                currency=adapter.get("currency"),
                quantity_type=adapter.get("quantity_type"),
                availability=adapter.get("availability"),
                nutrition_raw=adapter.get("nutrition"),
            )

            self._count += 1
            if self._count % 100 == 0:
                self._connector.connection.commit()
                _LOG.info("Committed %d items so far", self._count)

        except Exception:
            _LOG.exception("Failed to process item: %s", name)

        return item

    def close_spider(self, spider: Any) -> None:
        if self._connector is not None:
            try:
                self._connector.connection.commit()
            except Exception:
                _LOG.exception("Failed final commit")
            self._connector.close()
        _LOG.info("PostgresPipeline closed — total items processed: %d", self._count)
