# ruff: noqa: S101, PT009
import pytest
from shelfwatch.server import (
    _normalize_params,
    _parse_options,
    _rows_to_dicts,
    load_config,
)


class TestParseOptions:
    """Test the _parse_options helper function."""

    def test_parse_options_with_none(self) -> None:
        result = _parse_options(None)
        assert result == {}

    def test_parse_options_with_empty_string(self) -> None:
        result = _parse_options("")
        assert result == {}

    def test_parse_options_with_valid_json(self) -> None:
        result = _parse_options('{"key": "value", "number": 42}')
        assert result == {"key": "value", "number": 42}

    def test_parse_options_with_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="options must be valid JSON"):
            _parse_options('{"invalid": json}')

    def test_parse_options_with_non_object_raises(self) -> None:
        with pytest.raises(ValueError, match="options JSON must be an object"):
            _parse_options('["array", "not", "object"]')


class TestNormalizeParams:
    """Test the _normalize_params helper function."""

    def test_normalize_params_with_none(self) -> None:
        result = _normalize_params(None)
        assert result is None

    def test_normalize_params_with_dict(self) -> None:
        input_dict = {"key": "value", "number": 42}
        result = _normalize_params(input_dict)
        assert result == {"key": "value", "number": 42}
        assert isinstance(result, dict)

    def test_normalize_params_with_list(self) -> None:
        input_list = [1, 2, 3, "hello"]
        result = _normalize_params(input_list)
        assert result == [1, 2, 3, "hello"]
        assert isinstance(result, list)

    def test_normalize_params_with_tuple(self) -> None:
        input_tuple = (1, 2, 3)
        result = _normalize_params(input_tuple)
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_normalize_params_with_string_raises(self) -> None:
        with pytest.raises(ValueError, match="params must be an object or array"):
            _normalize_params("string")

    def test_normalize_params_with_bytes_raises(self) -> None:
        with pytest.raises(ValueError, match="params must be an object or array"):
            _normalize_params(b"bytes")


class TestRowsToDicts:
    """Test the _rows_to_dicts helper function."""

    def test_rows_to_dicts_converts_row_objects(self) -> None:
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        result = _rows_to_dicts(rows)
        assert result == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    def test_rows_to_dicts_with_empty_list(self) -> None:
        result = _rows_to_dicts([])
        assert result == []


class TestLoadConfig:
    """Test the load_config function."""

    def test_load_config_returns_config(self) -> None:
        config = load_config()
        assert config is not None
        assert hasattr(config, "host")
        assert hasattr(config, "port")
        assert hasattr(config, "dbname")
        assert hasattr(config, "user")
        assert hasattr(config, "password")
