# ruff: noqa: S101, PT009
import asyncio

from shelfwatch.server import (
    execute_query,
    get_categories,
    get_cheapest,
    search_products,
)


class TestExecuteQuery:
    """Test the execute_query tool."""

    def test_execute_query_basic_select(self, seed_data: None) -> None:
        result = asyncio.run(execute_query("SELECT 1 AS value"))
        assert len(result) == 1
        assert result[0]["value"] == 1

    def test_execute_query_with_dict_params(self, seed_data: None) -> None:
        result = asyncio.run(execute_query("SELECT %(val)s AS value", {"val": 42}))
        assert result[0]["value"] == 42

    def test_execute_query_with_list_params(self, seed_data: None) -> None:
        result = asyncio.run(execute_query("SELECT %s AS value", [99]))
        assert result[0]["value"] == 99

    def test_execute_query_returns_dicts(self, seed_data: None) -> None:
        result = asyncio.run(execute_query("SELECT * FROM supermarkets LIMIT 1"))
        assert len(result) > 0
        assert isinstance(result[0], dict)
        assert "name" in result[0]

    def test_execute_query_empty_result(self, seed_data: None) -> None:
        result = asyncio.run(execute_query("SELECT * FROM supermarkets WHERE name = %s", ["NonexistentStore"]))
        assert result == []

    def test_execute_query_with_none_params(self, seed_data: None) -> None:
        result = asyncio.run(execute_query("SELECT 1 AS value", None))
        assert result[0]["value"] == 1


class TestSearchProducts:
    """Test the search_products tool."""

    def test_search_products_basic(self, seed_data: None) -> None:
        result = asyncio.run(search_products("juice"))
        assert isinstance(result, list)
        if result:
            assert any("juice" in r["product_name"].lower() for r in result)

    def test_search_products_case_insensitive(self, seed_data: None) -> None:
        result_lower = asyncio.run(search_products("MILK"))
        result_upper = asyncio.run(search_products("milk"))
        assert len(result_lower) > 0
        assert len(result_upper) > 0

    def test_search_products_with_store_filter(self, seed_data: None) -> None:
        result_filtered = asyncio.run(search_products("juice", store_name="ica"))
        assert all(r["store_name"] == "ica" for r in result_filtered)

    def test_search_products_with_limit(self, seed_data: None) -> None:
        result_limited = asyncio.run(search_products("milk", limit=1))
        assert len(result_limited) <= 1

    def test_search_products_ordered_by_price(self, seed_data: None) -> None:
        result = asyncio.run(search_products("juice"))
        prices = [r["price"] for r in result if r["price"] is not None]
        if prices:
            assert prices == sorted(prices)

    def test_search_products_no_results(self, seed_data: None) -> None:
        result = asyncio.run(search_products("nonexistent_product_zzz_xyz_abc"))
        assert result == []

    def test_search_products_returns_correct_fields(self, seed_data: None) -> None:
        result = asyncio.run(search_products("juice"))
        assert len(result) > 0
        row = result[0]
        assert "product_name" in row
        assert "store_name" in row
        assert "price" in row
        assert "currency_code" in row
        assert "url" in row
        assert "category" in row


class TestGetCheapest:
    """Test the get_cheapest tool."""

    def test_get_cheapest_basic(self, seed_data: None) -> None:
        result = asyncio.run(get_cheapest("juice"))
        assert len(result) > 0

    def test_get_cheapest_ordered_ascending(self, seed_data: None) -> None:
        result = asyncio.run(get_cheapest("juice"))
        prices = [r["price"] for r in result if r["price"] is not None]
        assert prices == sorted(prices)

    def test_get_cheapest_with_limit(self, seed_data: None) -> None:
        result = asyncio.run(get_cheapest("juice", limit=1))
        assert len(result) <= 1

    def test_get_cheapest_default_limit(self, seed_data: None) -> None:
        result = asyncio.run(get_cheapest("juice"))
        assert len(result) <= 10

    def test_get_cheapest_nonexistent(self, seed_data: None) -> None:
        result = asyncio.run(get_cheapest("nonexistent_xyz"))
        assert result == []

    def test_get_cheapest_returns_correct_fields(self, seed_data: None) -> None:
        result = asyncio.run(get_cheapest("juice", limit=1))
        assert len(result) > 0
        row = result[0]
        assert "product_name" in row
        assert "store_name" in row
        assert "price" in row
        assert "currency_code" in row
        assert "url" in row


class TestAsyncExecution:
    """Test async execution of tools."""

    def test_multiple_concurrent_queries(self, seed_data: None) -> None:
        async def run_concurrent() -> None:
            results = await asyncio.gather(
                search_products("juice"),
                search_products("milk"),
                get_categories(),
            )
            return results

        results = asyncio.run(run_concurrent())
        assert len(results) == 3
        assert len(results[0]) > 0
        assert len(results[1]) > 0
        assert len(results[2]) > 0
