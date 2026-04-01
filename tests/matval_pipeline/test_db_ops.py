# ruff: noqa: S101
import pytest
from matval_core.db.connector import PostgresConnector
from matval_pipeline.db_ops import DBOps


@pytest.fixture(scope="session")
def db_ops(pg_connector: PostgresConnector, apply_schema: None) -> DBOps:
    return DBOps(pg_connector)


# Teting get or create a supermarket
def test_get_or_create_supermarket_returns_int(db_ops: DBOps) -> None:
    sid = db_ops.get_or_create_supermarket("TestMart")
    assert isinstance(sid, int)


def test_get_or_create_supermarket_same_id_from_cache(db_ops: DBOps) -> None:
    sid1 = db_ops.get_or_create_supermarket("CacheMart")
    sid2 = db_ops.get_or_create_supermarket("CacheMart")
    assert sid1 == sid2


def test_get_or_create_supermarket_same_id_from_db(pg_connector: PostgresConnector, apply_schema: None) -> None:
    sid1 = DBOps(pg_connector).get_or_create_supermarket("DBMart")
    sid2 = DBOps(pg_connector).get_or_create_supermarket("DBMart")  # fresh cache, must hit DB
    assert sid1 == sid2


# Testing get or create category
def test_get_or_create_category_without_parent(db_ops: DBOps) -> None:
    cid = db_ops.get_or_create_category("Dairy", None)
    assert isinstance(cid, int)


def test_get_or_create_category_with_parent(db_ops: DBOps) -> None:
    parent_id = db_ops.get_or_create_category("Beverages", None)
    child_id = db_ops.get_or_create_category("Juices", "Beverages")
    assert isinstance(child_id, int)
    assert child_id != parent_id


def test_get_or_create_category_none_name_returns_none(db_ops: DBOps) -> None:
    assert db_ops.get_or_create_category(None, None) is None


# Testing get or create product
def test_get_or_create_product_returns_int(db_ops: DBOps) -> None:
    pid = db_ops.get_or_create_product("Whole Milk", None)
    assert isinstance(pid, int)


def test_get_or_create_product_same_id_from_cache(db_ops: DBOps) -> None:
    pid1 = db_ops.get_or_create_product("Butter", None)
    pid2 = db_ops.get_or_create_product("Butter", None)
    assert pid1 == pid2


# Testing get or create unit
def test_get_or_create_unit_returns_int(db_ops: DBOps) -> None:
    uid = db_ops.get_or_create_unit("kilogram", "kg")
    assert isinstance(uid, int)


def test_get_or_create_unit_same_id_from_cache(db_ops: DBOps) -> None:
    uid1 = db_ops.get_or_create_unit("litre", "l")
    uid2 = db_ops.get_or_create_unit("litre", "l")
    assert uid1 == uid2


# Testing currency
def test_ensure_currency_returns_code(db_ops: DBOps) -> None:
    assert db_ops.ensure_currency("SEK") == "SEK"


def test_ensure_currency_none_returns_none(db_ops: DBOps) -> None:
    assert db_ops.ensure_currency(None) is None


# Test upserting store products
def test_upsert_store_product_inserts(db_ops: DBOps, pg_connector: PostgresConnector) -> None:
    sid = db_ops.get_or_create_supermarket("UpsertMart")
    pid = db_ops.get_or_create_product("Oat Milk", None)

    db_ops.upsert_store_product(sid, pid, price="12.50", currency="SEK", availability=True)

    row = pg_connector.scalar_query(
        "SELECT price FROM store_products WHERE supermarket_id = %s AND product_id = %s",
        (sid, pid),
    )
    assert float(row) == 12.50


def test_upsert_store_product_updates_price(db_ops: DBOps, pg_connector: PostgresConnector) -> None:
    sid = db_ops.get_or_create_supermarket("UpdateMart")
    pid = db_ops.get_or_create_product("Rice", None)

    db_ops.upsert_store_product(sid, pid, price="5.00", currency="SEK")
    db_ops.upsert_store_product(sid, pid, price="6.50", currency="SEK")

    row = pg_connector.scalar_query(
        "SELECT price FROM store_products WHERE supermarket_id = %s AND product_id = %s",
        (sid, pid),
    )
    assert float(row) == 6.50


def test_upsert_store_product_with_unit(db_ops: DBOps, pg_connector: PostgresConnector) -> None:
    sid = db_ops.get_or_create_supermarket("UnitMart")
    pid = db_ops.get_or_create_product("Flour", None)

    db_ops.upsert_store_product(
        sid,
        pid,
        price="15.00",
        currency="SEK",
        unit_quantity="1",
        unit_quantity_name="kilogram",
        unit_quantity_abbrev="kg",
    )

    row = pg_connector.scalar_query(
        "SELECT unit_quantity FROM store_products WHERE supermarket_id = %s AND product_id = %s",
        (sid, pid),
    )
    assert float(row) == 1.0


# Testing get or create lookups
def test_get_or_create_lookup_quantity_type(db_ops: DBOps) -> None:
    lid = db_ops.get_or_create_lookup("quantity_types", "name", "weight")
    assert isinstance(lid, int)


def test_get_or_create_lookup_none_returns_none(db_ops: DBOps) -> None:
    assert db_ops.get_or_create_lookup("quantity_types", "name", None) is None


def test_get_or_create_lookup_unknown_table_raises(db_ops: DBOps) -> None:
    with pytest.raises(ValueError, match="not registered"):
        db_ops.get_or_create_lookup("nonexistent_table", "name", "value")


def test_get_or_create_lookup_same_id_from_cache(pg_connector: PostgresConnector, apply_schema: None) -> None:
    ops = DBOps(pg_connector)
    lid1 = ops.get_or_create_lookup("quantity_types", "name", "volume")
    lid2 = ops.get_or_create_lookup("quantity_types", "name", "volume")  # hits cache
    assert lid1 == lid2
