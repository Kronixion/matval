# ruff: noqa: S101, PT009
import asyncio

from shelfwatch.server import (
    get_categories,
    list_supermarkets,
)


class TestListSupermarkets:

    def test_list_supermarkets_returns_all(self, seed_data: None) -> None:
        result = asyncio.run(list_supermarkets())
        assert len(result) > 0
        assert "store_name" in result[0]

    def test_list_supermarkets_includes_product_count(self, seed_data: None) -> None:
        result = asyncio.run(list_supermarkets())
        assert len(result) > 0
        row = result[0]
        assert "product_count" in row
        assert isinstance(row["product_count"], int)

    def test_list_supermarkets_includes_data_freshness(self, seed_data: None) -> None:
        result = asyncio.run(list_supermarkets())
        assert len(result) > 0
        row = result[0]
        assert "earliest_data" in row
        assert "latest_data" in row

    def test_list_supermarkets_ordered_by_name(self, seed_data: None) -> None:
        result = asyncio.run(list_supermarkets())
        names = [r["store_name"] for r in result]
        assert names == sorted(names, key=str.lower)


class TestGetCategories:

    def test_get_categories_all(self, seed_data: None) -> None:
        result = asyncio.run(get_categories())
        assert len(result) > 0
        assert "category" in result[0]
        assert "product_count" in result[0]

    def test_get_categories_with_store(self, seed_data: None) -> None:
        result = asyncio.run(get_categories(store_name="ica"))
        assert all("product_count" in r for r in result)

    def test_get_categories_includes_parent(self, seed_data: None) -> None:
        result = asyncio.run(get_categories())
        has_parent = any(r["parent_category"] is not None for r in result)
        assert has_parent

    def test_get_categories_nonexistent_store(self, seed_data: None) -> None:
        result = asyncio.run(get_categories(store_name="nonexistent"))
        assert result == []

    def test_get_categories_returns_product_count(self, seed_data: None) -> None:
        result = asyncio.run(get_categories())
        assert len(result) > 0
        assert "product_count" in result[0]
        assert isinstance(result[0]["product_count"], int)
