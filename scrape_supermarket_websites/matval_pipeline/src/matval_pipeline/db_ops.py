from __future__ import annotations

import json
from typing import Any

from matval_core.db.connector import PostgresConnector
from psycopg import sql

from .normalizers import normalize_availability, normalize_currency, normalize_float

LOOKUP_ID_COLUMNS = {
    "quantity_types": "quantity_type_id",
    "units": "unit_id",
    "availability_statuses": "availability_status_id",
}


class DBOps:
    def __init__(self, connector: PostgresConnector) -> None:
        self._conn = connector
        self._supermarket_cache: dict[str, int] = {}
        self._category_cache: dict[tuple[str | None, str | None], int | None] = {}
        self._product_cache: dict[tuple[str, int | None], int] = {}
        self._unit_cache: dict[str, int] = {}
        self._lookup_cache: dict[tuple[str, str | None], int | None] = {}
        self._currency_seen: set[str] = set()

    def get_or_create_supermarket(self, name: str) -> int:
        if name in self._supermarket_cache:
            return self._supermarket_cache[name]

        row = self._conn.sql_query(
            """WITH ins AS (
                   INSERT INTO supermarkets (name) VALUES (%s)
                   ON CONFLICT (name) DO NOTHING
                   RETURNING supermarket_id
               )
               SELECT supermarket_id FROM ins
               UNION ALL
               SELECT supermarket_id FROM supermarkets WHERE name = %s
               LIMIT 1""",
            (name, name),
        )
        sid = int(row[0]["supermarket_id"])
        self._supermarket_cache[name] = sid
        return sid

    def get_or_create_category(self, name: str | None, parent_name: str | None) -> int | None:
        if not name:
            return None

        key = (name, parent_name)
        if key in self._category_cache:
            return self._category_cache[key]

        parent_id = self.get_or_create_category(parent_name, None) if parent_name else None

        row = self._conn.sql_query(
            """WITH ins AS (
                   INSERT INTO categories (name, parent_category_id) VALUES (%s, %s)
                   ON CONFLICT ON CONSTRAINT uq_categories_name_parent DO NOTHING
                   RETURNING category_id
               )
               SELECT category_id FROM ins
               UNION ALL
               SELECT category_id FROM categories
               WHERE name = %s AND COALESCE(parent_category_id, 0) = COALESCE(%s, 0)
               LIMIT 1""",
            (name, parent_id, name, parent_id),
        )
        cat_id = int(row[0]["category_id"])
        self._category_cache[key] = cat_id
        return cat_id

    def get_or_create_product(self, name: str, category_id: int | None) -> int:
        key = (name, category_id)
        if key in self._product_cache:
            return self._product_cache[key]

        row = self._conn.sql_query(
            """WITH ins AS (
                   INSERT INTO products (name, category_id) VALUES (%s, %s)
                   ON CONFLICT ON CONSTRAINT uq_products_name_category DO NOTHING
                   RETURNING product_id
               )
               SELECT product_id FROM ins
               UNION ALL
               SELECT product_id FROM products
               WHERE name = %s AND COALESCE(category_id, 0) = COALESCE(%s, 0)
               LIMIT 1""",
            (name, category_id, name, category_id),
        )
        pid = int(row[0]["product_id"])
        self._product_cache[key] = pid
        return pid

    def get_or_create_lookup(self, table: str, column: str, value: str | None) -> int | None:
        if value is None:
            return None

        key = (table, value)
        if key in self._lookup_cache:
            return self._lookup_cache[key]

        id_column = LOOKUP_ID_COLUMNS.get(table)
        if not id_column:
            raise ValueError(f"Lookup table '{table}' not registered in LOOKUP_ID_COLUMNS")

        query = sql.SQL("""WITH ins AS (
                            INSERT INTO {table} ({column}) VALUES (%s)
                            ON CONFLICT ({column}) DO NOTHING
                            RETURNING {id_column}
                        )
                        SELECT {id_column} FROM ins
                        UNION ALL
                        SELECT {id_column} FROM {table} WHERE {column} = %s
                        LIMIT 1""").format(
            table=sql.Identifier(table),
            column=sql.Identifier(column),
            id_column=sql.Identifier(id_column),
        )
        row = self._conn.sql_query(
            query,
            (value, value),
        )
        lid = int(row[0][id_column])
        self._lookup_cache[key] = lid
        return lid

    def get_or_create_unit(self, name: str, abbreviation: str) -> int:
        key = abbreviation
        if key in self._unit_cache:
            return self._unit_cache[key]

        row = self._conn.sql_query(
            """WITH ins AS (
                   INSERT INTO units (name, abbreviation) VALUES (%s, %s)
                   ON CONFLICT (abbreviation) DO NOTHING
                   RETURNING unit_id
               )
               SELECT unit_id FROM ins
               UNION ALL
               SELECT unit_id FROM units WHERE abbreviation = %s
               LIMIT 1""",
            (name, abbreviation, abbreviation),
        )
        uid = int(row[0]["unit_id"])
        self._unit_cache[key] = uid
        return uid

    def ensure_currency(self, code: str | None) -> str | None:
        if code is None:
            return None
        if code in self._currency_seen:
            return code

        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO currencies (currency_code, name) VALUES (%s, %s) \
                    ON CONFLICT (currency_code) DO NOTHING",
                (code, code),
            )
        self._currency_seen.add(code)
        return code

    def upsert_store_product(
        self,
        supermarket_id: int,
        product_id: int,
        *,
        url: str | None = None,
        price: Any = None,
        unit_price: Any = None,
        unit_quantity: Any = None,
        unit_quantity_name: str | None = None,
        unit_quantity_abbrev: str | None = None,
        currency: Any = None,
        quantity_type: str | None = None,
        availability: Any = None,
        nutrition_raw: Any = None,
    ) -> None:
        currency_code = self.ensure_currency(normalize_currency(currency))
        norm_price = normalize_float(price)
        norm_unit_price = normalize_float(unit_price)
        norm_unit_quantity = normalize_float(unit_quantity)

        quantity_type_id = self.get_or_create_lookup("quantity_types", "name", quantity_type)

        unit_id = None
        if unit_quantity_name or unit_quantity_abbrev:
            unit_key = unit_quantity_name or unit_quantity_abbrev

            if unit_key is None:
                raise RuntimeError("unit_key is unexpectedly None")

            unit_id = self.get_or_create_unit(unit_key, unit_quantity_abbrev or unit_key)

        availability_status_id = self.get_or_create_lookup(
            "availability_statuses", "name", normalize_availability(availability)
        )

        self._conn.non_sql_query(
            """
            INSERT INTO store_products (
                supermarket_id, product_id, url, currency_code, price, unit_price,
                unit_quantity, unit_id, quantity_type_id, availability_status_id,
                nutrition_raw, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (supermarket_id, product_id) DO UPDATE SET
                url = EXCLUDED.url,
                currency_code = EXCLUDED.currency_code,
                price = EXCLUDED.price,
                unit_price = EXCLUDED.unit_price,
                unit_quantity = EXCLUDED.unit_quantity,
                unit_id = EXCLUDED.unit_id,
                quantity_type_id = EXCLUDED.quantity_type_id,
                availability_status_id = EXCLUDED.availability_status_id,
                nutrition_raw = EXCLUDED.nutrition_raw,
                notes = EXCLUDED.notes,
                last_seen_at = NOW()
            """,
            (
                supermarket_id,
                product_id,
                url,
                currency_code,
                norm_price,
                norm_unit_price,
                norm_unit_quantity,
                unit_id,
                quantity_type_id,
                availability_status_id,
                json.dumps(nutrition_raw) if nutrition_raw is not None else None,
                None,
            ),
        )
