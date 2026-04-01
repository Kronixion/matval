# ruff: noqa: S101
import json

import pytest
from matval_core.db.connector import PostgresConnector


@pytest.fixture(scope="session")
def seed_data(pg_connector: PostgresConnector, apply_schema: None) -> None:
    """Seed test data into the database."""
    # Clean up existing data (in reverse foreign key order)
    pg_connector.non_sql_query("DELETE FROM product_availability_history")
    pg_connector.non_sql_query("DELETE FROM store_products")
    pg_connector.non_sql_query("DELETE FROM supermarkets")
    pg_connector.non_sql_query("DELETE FROM products")
    pg_connector.non_sql_query("DELETE FROM categories")
    pg_connector.non_sql_query("DELETE FROM units")
    pg_connector.non_sql_query("DELETE FROM quantity_types")
    pg_connector.non_sql_query("DELETE FROM availability_statuses")
    pg_connector.non_sql_query("DELETE FROM currencies")
    pg_connector.connection.commit()

    # Insert supermarkets
    pg_connector.execute_many(
        "INSERT INTO supermarkets (name) VALUES (%s)",
        [("ica",), ("willys",), ("coop",)],
    )

    # Insert categories
    pg_connector.execute_many(
        "INSERT INTO categories (name, parent_category_id) VALUES (%s, %s)",
        [
            ("Beverages", None),
            ("Juices", 1),
            ("Coffee & Tea", 1),
            ("Dairy", None),
            ("Milk", 4),
            ("Cheese", 4),
            ("Produce", None),
            ("Fruits", 7),
            ("Vegetables", 7),
        ],
    )

    # Insert products
    pg_connector.execute_many(
        "INSERT INTO products (name, category_id, description) VALUES (%s, %s, %s)",
        [
            ("Orange Juice", 2, "Fresh orange juice"),
            ("Whole Milk", 5, "1 liter whole milk"),
            ("Swedish Coffee", 3, "Premium coffee beans"),
            ("Cheddar Cheese", 6, "Aged cheddar"),
            ("Organic Apples", 8, "Red apples"),
            ("Carrots", 9, "Fresh carrots"),
            ("Banana", 8, "Yellow bananas"),
            ("Tomatoes", 9, "Fresh tomatoes"),
        ],
    )

    # Insert units
    pg_connector.execute_many(
        "INSERT INTO units (name, abbreviation) VALUES (%s, %s)",
        [
            ("litre", "l"),
            ("kilogram", "kg"),
            ("gram", "g"),
            ("unit", "pcs"),
        ],
    )

    # Insert quantity types
    pg_connector.execute_many(
        "INSERT INTO quantity_types (name) VALUES (%s)",
        [("weight",), ("volume",), ("count",)],
    )

    # Insert availability statuses
    pg_connector.execute_many(
        "INSERT INTO availability_statuses (name, description) VALUES (%s, %s)",
        [
            ("available", "Item is available"),
            ("out_of_stock", "Item is out of stock"),
            ("discontinued", "Item has been discontinued"),
        ],
    )

    # Insert currencies
    pg_connector.execute_many(
        "INSERT INTO currencies (currency_code, name) VALUES (%s, %s)",
        [
            ("SEK", "Swedish Krona"),
            ("EUR", "Euro"),
            ("USD", "US Dollar"),
        ],
    )

    # Insert store_products with various prices and attributes
    pg_connector.execute_many(
        """
        INSERT INTO store_products
        (supermarket_id, product_id, price, currency_code, unit_price,
         unit_quantity, unit_id, quantity_type_id, availability_status_id,
         nutrition_raw, url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            # Orange Juice (product_id=1) across stores
            (
                1,
                1,
                29.99,
                "SEK",
                29.99,
                1,
                1,
                2,
                1,
                json.dumps({"vitamin_c": "100mg", "calories": 120}),
                "https://ica.se/orange-juice",
            ),
            (
                2,
                1,
                25.50,
                "SEK",
                25.50,
                1,
                1,
                2,
                1,
                json.dumps({"vitamin_c": "100mg", "calories": 120}),
                "https://willys.se/orange-juice",
            ),
            (
                3,
                1,
                27.99,
                "SEK",
                27.99,
                1,
                1,
                2,
                1,
                json.dumps({"vitamin_c": "100mg", "calories": 120}),
                "https://coop.se/orange-juice",
            ),
            # Whole Milk (product_id=2) across stores
            (
                1,
                2,
                15.99,
                "SEK",
                15.99,
                1,
                1,
                2,
                1,
                json.dumps({"protein": "8g", "calcium": "300mg", "calories": 160}),
                "https://ica.se/milk",
            ),
            (
                2,
                2,
                14.50,
                "SEK",
                14.50,
                1,
                1,
                2,
                1,
                json.dumps({"protein": "8g", "calcium": "300mg", "calories": 160}),
                "https://willys.se/milk",
            ),
            (
                3,
                2,
                16.50,
                "SEK",
                16.50,
                1,
                1,
                2,
                1,
                json.dumps({"protein": "8g", "calcium": "300mg", "calories": 160}),
                "https://coop.se/milk",
            ),
            # Swedish Coffee (product_id=3) across stores
            (
                1,
                3,
                79.99,
                "SEK",
                None,
                None,
                None,
                None,
                1,
                None,
                "https://ica.se/coffee",
            ),
            (
                2,
                3,
                75.50,
                "SEK",
                None,
                None,
                None,
                None,
                1,
                None,
                "https://willys.se/coffee",
            ),
            # Cheddar Cheese (product_id=4)
            (
                1,
                4,
                89.99,
                "SEK",
                None,
                None,
                None,
                None,
                1,
                json.dumps({"calcium": "800mg", "protein": "28g"}),
                "https://ica.se/cheddar",
            ),
            (
                2,
                4,
                85.00,
                "SEK",
                None,
                None,
                None,
                None,
                1,
                json.dumps({"calcium": "800mg", "protein": "28g"}),
                "https://willys.se/cheddar",
            ),
            # Organic Apples (product_id=5)
            (
                1,
                5,
                35.50,
                "SEK",
                None,
                None,
                None,
                None,
                1,
                json.dumps({"vitamin_c": "5mg", "fiber": "3g"}),
                "https://ica.se/apples",
            ),
            (
                2,
                5,
                32.99,
                "SEK",
                None,
                None,
                None,
                None,
                1,
                json.dumps({"vitamin_c": "5mg", "fiber": "3g"}),
                "https://willys.se/apples",
            ),
            # Carrots (product_id=6)
            (
                1,
                6,
                12.99,
                "SEK",
                12.99,
                1,
                2,
                1,
                1,
                json.dumps({"vitamin_a": "961µg", "fiber": "2.8g"}),
                "https://ica.se/carrots",
            ),
            (
                3,
                6,
                11.50,
                "SEK",
                11.50,
                1,
                2,
                1,
                1,
                json.dumps({"vitamin_a": "961µg", "fiber": "2.8g"}),
                "https://coop.se/carrots",
            ),
            # Banana (product_id=7)
            (
                2,
                7,
                19.99,
                "SEK",
                None,
                None,
                None,
                None,
                2,
                None,
                "https://willys.se/banana",
            ),
            # Tomatoes (product_id=8)
            (
                3,
                8,
                24.50,
                "SEK",
                None,
                None,
                None,
                None,
                3,
                None,
                "https://coop.se/tomatoes",
            ),
        ],
    )

    # Insert product availability history for price tracking
    pg_connector.execute_many(
        """
        INSERT INTO product_availability_history
        (store_product_id, availability_status_id, price, unit_price, recorded_at)
        VALUES (%s, %s, %s, %s, NOW() - INTERVAL '15 days')
        """,
        [
            (1, 1, 31.99, 31.99),  # Orange Juice at ICA, was more expensive
            (2, 1, 26.50, 26.50),  # Orange Juice at Willys, was slightly more
            (4, 1, 16.99, 16.99),  # Milk at ICA, was more expensive
        ],
    )

    pg_connector.connection.commit()
