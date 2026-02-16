"""MCP server exposing supermarket Postgres data tools."""

from __future__ import annotations

import asyncio, json, logging, os
from functools import partial
from typing import Any, Iterable, Mapping, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from matval_pipeline.connector import PostgresConfig, PostgresConnector


_LOG = logging.getLogger(__name__)


load_dotenv()


DEFAULT_CONFIG = PostgresConfig()


def _parse_options(raw: str | None) -> Mapping[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, Mapping):
            return parsed
        raise ValueError("options JSON must be an object")
    except json.JSONDecodeError as exc:
        raise ValueError("options must be valid JSON") from exc


def load_config() -> PostgresConfig:
    """Load connector configuration from environment variables."""

    options = _parse_options(os.getenv("SHELFWATCH_DB_OPTIONS"))

    return PostgresConfig(
        host=os.getenv("SHELFWATCH_DB_HOST", DEFAULT_CONFIG.host),
        port=int(os.getenv("SHELFWATCH_DB_PORT", DEFAULT_CONFIG.port)),
        dbname=os.getenv("SHELFWATCH_DB_NAME", DEFAULT_CONFIG.dbname),
        user=os.getenv("SHELFWATCH_DB_USER", DEFAULT_CONFIG.user),
        password=os.getenv("SHELFWATCH_DB_PASSWORD", DEFAULT_CONFIG.password),
        options=dict(options) or DEFAULT_CONFIG.options.copy(),
    )


def _create_connector() -> PostgresConnector:
    config = load_config()
    autocommit = os.getenv("SHELFWATCH_DB_AUTOCOMMIT", "false").lower() in {"1", "true", "yes"}
    return PostgresConnector(config=config, autocommit=autocommit)


_connector = _create_connector()


async def _run_db_call(func: callable, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(partial(func, *args, **kwargs))


mcp = FastMCP("shelfwatch")


_transport = os.getenv("SHELFWATCH_MCP_TRANSPORT", "stdio").strip().lower()
_host = os.getenv("SHELFWATCH_MCP_HOST")
_port_raw = os.getenv("SHELFWATCH_MCP_PORT")

if _host:
    mcp.settings.host = _host
if _port_raw:
    try:
        mcp.settings.port = int(_port_raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("SHELFWATCH_MCP_PORT must be an integer") from exc


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _normalize_params(params: Optional[Mapping[str, Any] | Iterable[Any]]) -> Optional[Any]:
    if params is None:
        return None
    if isinstance(params, Mapping):
        return dict(params)
    if isinstance(params, Iterable) and not isinstance(params, (str, bytes, bytearray)):
        return list(params)
    raise ValueError("params must be an object or array")


def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def execute_query(sql: str, params: Optional[Mapping[str, Any] | Iterable[Any]] = None) -> list[Mapping[str, Any]]:
    """Execute a raw SQL query — escape hatch for complex queries not covered by the other tools.

    Database schema (all in the public schema of supermarket_items):

    stores (store_id BIGINT PK, name TEXT UNIQUE, created_at, updated_at)
    categories (category_id BIGINT PK, name TEXT, parent_category_id BIGINT FK->categories, UNIQUE(name, parent_category_id))
    products (product_id BIGINT PK, name TEXT, category_id BIGINT FK->categories, description TEXT, sku TEXT, UNIQUE(name, category_id))
    quantity_types (quantity_type_id BIGINT PK, name TEXT UNIQUE)
    units (unit_id BIGINT PK, name TEXT UNIQUE, abbreviation TEXT UNIQUE)
    availability_statuses (availability_status_id BIGINT PK, name TEXT UNIQUE, description TEXT)
    currencies (currency_code CHAR(3) PK, name TEXT)
    store_products (store_product_id BIGINT PK, store_id FK->stores, product_id FK->products,
        external_store_sku TEXT, url TEXT, currency_code FK->currencies, price NUMERIC(12,2),
        unit_price NUMERIC(12,4), unit_quantity NUMERIC(12,4), unit_id FK->units,
        quantity_type_id FK->quantity_types, availability_status_id FK->availability_statuses,
        nutrition_raw JSONB, notes TEXT, first_seen_at TIMESTAMPTZ, last_seen_at TIMESTAMPTZ,
        UNIQUE(store_id, product_id))
    product_availability_history (history_id BIGINT PK, store_product_id FK->store_products,
        availability_status_id FK->availability_statuses, price NUMERIC(12,2), unit_price NUMERIC(12,4),
        recorded_at TIMESTAMPTZ)

    Stores: coop(1), hemkop(2), ica(3), mathem(4), willys(5).
    """

    normalized = _normalize_params(params)
    rows = await _run_db_call(_connector.sql_query, sql, normalized)
    return _rows_to_dicts(rows)


@mcp.tool()
async def search_products(keyword: str, store_name: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Search for products by keyword across all stores (or a specific store).

    Returns product name, store, price, URL, and category.
    """

    sql = """
        SELECT p.name AS product_name, s.name AS store_name,
               sp.price, sp.currency_code, sp.url,
               c.name AS category, pc.name AS parent_category
        FROM store_products sp
        JOIN products p ON p.product_id = sp.product_id
        JOIN stores s ON s.store_id = sp.store_id
        LEFT JOIN categories c ON c.category_id = p.category_id
        LEFT JOIN categories pc ON pc.category_id = c.parent_category_id
        WHERE p.name ILIKE %s
    """
    params: list[Any] = [f"%{keyword}%"]

    if store_name:
        sql += " AND s.name = %s"
        params.append(store_name.lower())

    sql += " ORDER BY sp.price ASC NULLS LAST LIMIT %s"
    params.append(limit)

    rows = await _run_db_call(_connector.sql_query, sql, params)
    return _rows_to_dicts(rows)


@mcp.tool()
async def compare_prices(keyword: str) -> list[dict[str, Any]]:
    """Compare prices for the same or similar products across all stores.

    Results are grouped by product name, showing each store's price.
    """

    sql = """
        SELECT p.name AS product_name, s.name AS store_name,
               sp.price, sp.currency_code, sp.unit_price,
               u.abbreviation AS unit_abbrev, sp.url
        FROM store_products sp
        JOIN products p ON p.product_id = sp.product_id
        JOIN stores s ON s.store_id = sp.store_id
        LEFT JOIN units u ON u.unit_id = sp.unit_id
        WHERE p.name ILIKE %s
        ORDER BY p.name, sp.price ASC NULLS LAST
    """

    rows = await _run_db_call(_connector.sql_query, sql, [f"%{keyword}%"])
    return _rows_to_dicts(rows)


@mcp.tool()
async def get_categories(store_name: str | None = None) -> list[dict[str, Any]]:
    """List categories with product counts, optionally filtered by store."""

    if store_name:
        sql = """
            SELECT c.name AS category, pc.name AS parent_category,
                   COUNT(*) AS product_count
            FROM store_products sp
            JOIN products p ON p.product_id = sp.product_id
            JOIN stores s ON s.store_id = sp.store_id
            JOIN categories c ON c.category_id = p.category_id
            LEFT JOIN categories pc ON pc.category_id = c.parent_category_id
            WHERE s.name = %s
            GROUP BY c.name, pc.name
            ORDER BY product_count DESC
        """
        params: list[Any] = [store_name.lower()]
    else:
        sql = """
            SELECT c.name AS category, pc.name AS parent_category,
                   COUNT(DISTINCT p.product_id) AS product_count
            FROM products p
            JOIN categories c ON c.category_id = p.category_id
            LEFT JOIN categories pc ON pc.category_id = c.parent_category_id
            GROUP BY c.name, pc.name
            ORDER BY product_count DESC
        """
        params = []

    rows = await _run_db_call(_connector.sql_query, sql, params or None)
    return _rows_to_dicts(rows)


@mcp.tool()
async def get_products_in_category(category_name: str, store_name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Browse products in a category, optionally filtered by store."""

    sql = """
        SELECT p.name AS product_name, s.name AS store_name,
               sp.price, sp.currency_code, sp.url
        FROM store_products sp
        JOIN products p ON p.product_id = sp.product_id
        JOIN stores s ON s.store_id = sp.store_id
        JOIN categories c ON c.category_id = p.category_id
        WHERE c.name ILIKE %s
    """
    params: list[Any] = [f"%{category_name}%"]

    if store_name:
        sql += " AND s.name = %s"
        params.append(store_name.lower())

    sql += " ORDER BY p.name, sp.price ASC NULLS LAST LIMIT %s"
    params.append(limit)

    rows = await _run_db_call(_connector.sql_query, sql, params)
    return _rows_to_dicts(rows)


@mcp.tool()
async def get_product_details(product_name: str, store_name: str | None = None) -> list[dict[str, Any]]:
    """Get full details for a product: price, unit pricing, nutrition, availability."""

    sql = """
        SELECT p.name AS product_name, s.name AS store_name,
               sp.price, sp.currency_code, sp.unit_price,
               sp.unit_quantity, u.name AS unit_name, u.abbreviation AS unit_abbrev,
               qt.name AS quantity_type, avs.name AS availability,
               sp.nutrition_raw, sp.url,
               c.name AS category, pc.name AS parent_category,
               sp.first_seen_at, sp.last_seen_at
        FROM store_products sp
        JOIN products p ON p.product_id = sp.product_id
        JOIN stores s ON s.store_id = sp.store_id
        LEFT JOIN categories c ON c.category_id = p.category_id
        LEFT JOIN categories pc ON pc.category_id = c.parent_category_id
        LEFT JOIN units u ON u.unit_id = sp.unit_id
        LEFT JOIN quantity_types qt ON qt.quantity_type_id = sp.quantity_type_id
        LEFT JOIN availability_statuses avs ON avs.availability_status_id = sp.availability_status_id
        WHERE p.name ILIKE %s
    """
    params: list[Any] = [f"%{product_name}%"]

    if store_name:
        sql += " AND s.name = %s"
        params.append(store_name.lower())

    sql += " ORDER BY s.name"

    rows = await _run_db_call(_connector.sql_query, sql, params)
    return _rows_to_dicts(rows)


@mcp.tool()
async def get_nutrition(product_name: str, store_name: str | None = None) -> list[dict[str, Any]]:
    """Get nutrition data for a product."""

    sql = """
        SELECT p.name AS product_name, s.name AS store_name,
               sp.nutrition_raw
        FROM store_products sp
        JOIN products p ON p.product_id = sp.product_id
        JOIN stores s ON s.store_id = sp.store_id
        WHERE p.name ILIKE %s AND sp.nutrition_raw IS NOT NULL
    """
    params: list[Any] = [f"%{product_name}%"]

    if store_name:
        sql += " AND s.name = %s"
        params.append(store_name.lower())

    sql += " ORDER BY s.name"

    rows = await _run_db_call(_connector.sql_query, sql, params)
    return _rows_to_dicts(rows)


@mcp.tool()
async def list_stores() -> list[dict[str, Any]]:
    """List all stores with product counts and data freshness."""

    sql = """
        SELECT s.name AS store_name,
               COUNT(sp.store_product_id) AS product_count,
               MIN(sp.first_seen_at) AS earliest_data,
               MAX(sp.last_seen_at) AS latest_data
        FROM stores s
        LEFT JOIN store_products sp ON sp.store_id = s.store_id
        GROUP BY s.store_id, s.name
        ORDER BY s.name
    """

    rows = await _run_db_call(_connector.sql_query, sql)
    return _rows_to_dicts(rows)


@mcp.tool()
async def get_cheapest(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    """Find the cheapest matching products across all stores."""

    sql = """
        SELECT p.name AS product_name, s.name AS store_name,
               sp.price, sp.currency_code, sp.unit_price,
               u.abbreviation AS unit_abbrev, sp.url
        FROM store_products sp
        JOIN products p ON p.product_id = sp.product_id
        JOIN stores s ON s.store_id = sp.store_id
        LEFT JOIN units u ON u.unit_id = sp.unit_id
        WHERE p.name ILIKE %s AND sp.price IS NOT NULL
        ORDER BY sp.price ASC
        LIMIT %s
    """

    rows = await _run_db_call(_connector.sql_query, sql, [f"%{keyword}%", limit])
    return _rows_to_dicts(rows)


@mcp.tool()
async def get_price_history(product_name: str, store_name: str | None = None, days: int = 30) -> list[dict[str, Any]]:
    """Get price and availability history for a product.

    Returns historical price/availability changes recorded by the database
    trigger whenever a scraper run detects a change. Each row shows the
    previous price, unit price, and availability status before the change.
    """

    sql = """
        SELECT p.name AS product_name, s.name AS store_name,
               pah.price, pah.unit_price,
               avs.name AS availability,
               pah.recorded_at,
               sp.price AS current_price, sp.unit_price AS current_unit_price
        FROM product_availability_history pah
        JOIN store_products sp ON sp.store_product_id = pah.store_product_id
        JOIN products p ON p.product_id = sp.product_id
        JOIN stores s ON s.store_id = sp.store_id
        LEFT JOIN availability_statuses avs ON avs.availability_status_id = pah.availability_status_id
        WHERE p.name ILIKE %s
          AND pah.recorded_at >= NOW() - INTERVAL '%s days'
    """
    params: list[Any] = [f"%{product_name}%", days]

    if store_name:
        sql += " AND s.name = %s"
        params.append(store_name.lower())

    sql += " ORDER BY pah.recorded_at DESC"

    rows = await _run_db_call(_connector.sql_query, sql, params)
    return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# Lifecycle & entrypoint
# ---------------------------------------------------------------------------

class ConnectorLifespan:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        _LOG.info("Closing Postgres connector")
        _connector.close()

mcp.settings.lifespan = lambda _: ConnectorLifespan()

def main() -> None:
    logging.basicConfig(level=os.getenv("SHELFWATCH_LOG_LEVEL", "INFO"))
    _LOG.info("Starting Shelfwatch MCP server")
    mcp.run(transport=_transport)

__all__ = ["main"]

if __name__ == "__main__":
    main()
