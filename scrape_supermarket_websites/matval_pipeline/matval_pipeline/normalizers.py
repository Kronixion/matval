"""Data normalization helpers — extracted from seed_tables.py."""

from __future__ import annotations

from typing import Any


def normalize_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def normalize_currency(value: Any) -> str | None:
    if value is None:
        return None
    value_str = str(value).strip().upper()
    if len(value_str) == 3 and value_str.isalpha():
        return value_str
    currency_map = {"KR": "SEK", "SEK": "SEK"}
    return currency_map.get(value_str)


def normalize_availability(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "available" if value else "unavailable"
    if isinstance(value, dict):
        code = value.get("code")
        if code:
            return str(code)
        description = value.get("description") or value.get("descriptionShort")
        if description:
            return str(description)
    return str(value)
