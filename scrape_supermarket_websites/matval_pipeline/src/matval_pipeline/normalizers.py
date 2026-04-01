from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()
_config_path = os.path.join(str(os.getenv("MATVAL_CONFIG_DIR")), "currency_aliases.json")
with open(_config_path) as config_file:
    CURRENCY_MAP = json.load(config_file)


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
    result = CURRENCY_MAP.get(value_str)
    return result if result is not None else None


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
