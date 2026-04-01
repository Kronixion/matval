# ruff: noqa: S101, PT009
import asyncio

from shelfwatch.server import (
    get_nutrition,
    get_product_details,
    get_products_in_category,
)


class TestGetProductDetails:
    """Test the get_product_details tool."""

    def test_get_product_details_basic(self, seed_data: None) -> None:
        result = asyncio.run(get_product_details("milk"))
        assert isinstance(result, list)

    def test_get_product_details_case_insensitive(self, seed_data: None) -> None:
        result_lower = asyncio.run(get_product_details("milk"))
        result_upper = asyncio.run(get_product_details("MILK"))
        assert isinstance(result_lower, list)
        assert isinstance(result_upper, list)

    def test_get_product_details_with_store(self, seed_data: None) -> None:
        result = asyncio.run(get_product_details("milk", store_name="ica"))
        assert all(r["store_name"] == "ica" for r in result)

    def test_get_product_details_includes_nutrition(self, seed_data: None) -> None:
        result = asyncio.run(get_product_details("milk"))
        if result:
            assert "nutrition_raw" in result[0]

    def test_get_product_details_includes_category(self, seed_data: None) -> None:
        result = asyncio.run(get_product_details("milk"))
        if result:
            assert "category" in result[0]

    def test_get_product_details_includes_unit_info(self, seed_data: None) -> None:
        result = asyncio.run(get_product_details("milk"))
        if result:
            assert "unit_name" in result[0]

    def test_get_product_details_nonexistent(self, seed_data: None) -> None:
        result = asyncio.run(get_product_details("nonexistent_product_xyz"))
        assert result == []

    def test_get_product_details_returns_all_fields(self, seed_data: None) -> None:
        result = asyncio.run(get_product_details("milk"))
        assert len(result) > 0
        row = result[0]
        expected_fields = [
            "product_name",
            "store_name",
            "price",
            "currency_code",
            "unit_price",
            "unit_quantity",
            "unit_name",
            "availability",
            "nutrition_raw",
            "url",
            "category",
        ]
        for field in expected_fields:
            assert field in row


class TestGetNutrition:
    """Test the get_nutrition tool."""

    def test_get_nutrition_basic(self, seed_data: None) -> None:
        result = asyncio.run(get_nutrition("juice"))
        assert len(result) > 0

    def test_get_nutrition_with_store(self, seed_data: None) -> None:
        result = asyncio.run(get_nutrition("juice", store_name="ica"))
        assert all(r["store_name"] == "ica" for r in result)

    def test_get_nutrition_only_returns_with_data(self, seed_data: None) -> None:
        result = asyncio.run(get_nutrition("coffee"))
        for row in result:
            assert row["nutrition_raw"] is not None

    def test_get_nutrition_nonexistent(self, seed_data: None) -> None:
        result = asyncio.run(get_nutrition("nonexistent_xyz"))
        assert result == []

    def test_get_nutrition_returns_correct_fields(self, seed_data: None) -> None:
        result = asyncio.run(get_nutrition("juice"))
        assert len(result) > 0
        row = result[0]
        assert "product_name" in row
        assert "store_name" in row
        assert "nutrition_raw" in row


class TestGetProductsInCategory:
    """Test the get_products_in_category tool."""

    def test_get_products_in_category_basic(self, seed_data: None) -> None:
        result = asyncio.run(get_products_in_category("beverage"))
        assert isinstance(result, list)

    def test_get_products_in_category_case_insensitive(self, seed_data: None) -> None:
        result_lower = asyncio.run(get_products_in_category("dairy"))
        result_upper = asyncio.run(get_products_in_category("DAIRY"))
        assert isinstance(result_lower, list)
        assert isinstance(result_upper, list)

    def test_get_products_in_category_with_store(self, seed_data: None) -> None:
        result = asyncio.run(get_products_in_category("dairy", store_name="ica"))
        assert all(r["store_name"] == "ica" for r in result)

    def test_get_products_in_category_with_limit(self, seed_data: None) -> None:
        result = asyncio.run(get_products_in_category("dairy", limit=1))
        assert len(result) <= 1

    def test_get_products_in_category_nonexistent(self, seed_data: None) -> None:
        result = asyncio.run(get_products_in_category("nonexistent_category_zzz_xyz_abc"))
        assert result == []

    def test_get_products_in_category_returns_correct_fields(self, seed_data: None) -> None:
        result = asyncio.run(get_products_in_category("dairy"))
        if result:
            row = result[0]
            assert "product_name" in row
            assert "store_name" in row
            assert "price" in row
            assert "currency_code" in row
