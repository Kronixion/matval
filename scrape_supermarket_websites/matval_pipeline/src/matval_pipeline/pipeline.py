from __future__ import annotations

import logging
from typing import Any

from itemadapter import ItemAdapter

from matval_core.db.config import PostgresConfig
from matval_core.db.connector import PostgresConnector
from .db_ops import DBOps

_LOG = logging.getLogger(__name__)


class PostgresPipeline:

    def __init__(self, store_name: str) -> None:
        self.store_name = store_name
        self.supermarket_id: int | None = None
        self._connector: PostgresConnector | None = None
        self._ops: DBOps | None = None
        self._count = 0

    @classmethod
    def from_crawler(cls, crawler: Any) -> PostgresPipeline:
        store_name = crawler.settings.get("STORE_NAME")
        if not store_name:
            raise ValueError("STORE_NAME must be set in Scrapy settings")
        return cls(store_name)

    def open_spider(self, spider: Any) -> None:
        pg_config = PostgresConfig.from_env()
        self._connector = PostgresConnector(config=pg_config, autocommit=False)
        self._ops = DBOps(self._connector)
        self.supermarket_id = self._ops.get_or_create_supermarket(self.store_name)
        _LOG.info("PostgresPipeline opened for store=%s (id=%d)", self.store_name, self.supermarket_id)

    def process_item(self, item: Any, _spider: Any) -> Any:
        adapter = ItemAdapter(item)

        name = adapter.get("name")
        if not name:
            _LOG.warning("Skipping item without a name: %s", item)
            return item

        if self._ops is None or self._connector is None or self.supermarket_id is None:
            raise RuntimeError("Pipeline not properly initialized")

        try:
            category_id = self._ops.get_or_create_category(
                adapter.get("subcategory"), adapter.get("category")
            )
            product_id = self._ops.get_or_create_product(name, category_id)
            self._ops.upsert_store_product(
                self.supermarket_id,
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

    def close_spider(self, _spider: Any) -> None:
        if self._connector is not None:
            try:
                self._connector.connection.commit()
            except Exception:
                _LOG.exception("Failed final commit")
            self._connector.close()
        _LOG.info("PostgresPipeline closed — total items processed: %d", self._count)
