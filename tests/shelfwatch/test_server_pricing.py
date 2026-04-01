# ruff: noqa: S101, PT009
import asyncio

from shelfwatch.server import (
    compare_prices,
    get_price_history,
)


class TestComparePrices:
    """Test the compare_prices tool."""

    def test_compare_prices_basic(self, seed_data: None) -> None:
        result = asyncio.run(compare_prices("juice"))
        assert len(result) > 0

    def test_compare_prices_groups_by_product(self, seed_data: None) -> None:
        result = asyncio.run(compare_prices("juice"))
        if result:
            product_names = [r["product_name"] for r in result]
            assert any("juice" in p.lower() for p in product_names)

    def test_compare_prices_multiple_stores(self, seed_data: None) -> None:
        result = asyncio.run(compare_prices("juice"))
        if result:
            assert all("store_name" in r for r in result)

    def test_compare_prices_includes_unit_price(self, seed_data: None) -> None:
        result = asyncio.run(compare_prices("juice"))
        assert len(result) > 0
        assert "unit_price" in result[0]

    def test_compare_prices_no_results(self, seed_data: None) -> None:
        result = asyncio.run(compare_prices("nonexistent_xyz"))
        assert result == []


class TestGetPriceHistory:
    """Test the get_price_history tool."""

    def test_get_price_history_basic(self, seed_data: None) -> None:
        result = asyncio.run(get_price_history("juice"))
        assert isinstance(result, list)

    def test_get_price_history_with_store(self, seed_data: None) -> None:
        result = asyncio.run(get_price_history("juice", store_name="ica"))
        assert all(r["store_name"] == "ica" for r in result)

    def test_get_price_history_with_days_filter(self, seed_data: None) -> None:
        result = asyncio.run(get_price_history("juice", days=20))
        assert isinstance(result, list)

    def test_get_price_history_ordered_by_recorded_at_desc(self, seed_data: None) -> None:
        result = asyncio.run(get_price_history("juice"))
        if len(result) > 1:
            recorded_dates = [r["recorded_at"] for r in result]
            assert recorded_dates == sorted(recorded_dates, reverse=True)

    def test_get_price_history_includes_current_price(self, seed_data: None) -> None:
        result = asyncio.run(get_price_history("juice"))
        if result:
            row = result[0]
            assert "current_price" in row
            assert "current_unit_price" in row

    def test_get_price_history_nonexistent(self, seed_data: None) -> None:
        result = asyncio.run(get_price_history("nonexistent_zzz_xyz_abc"))
        assert result == []

    def test_get_price_history_returns_correct_fields(self, seed_data: None) -> None:
        result = asyncio.run(get_price_history("juice"))
        if result:
            row = result[0]
            assert "product_name" in row
            assert "store_name" in row
            assert "price" in row
            assert "recorded_at" in row
