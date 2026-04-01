# assert is idiomatic in pytest, hence S101 is not a concern in tests
# ruff: noqa: S101
from matval_pipeline.normalizers import normalize_availability, normalize_currency, normalize_float


# Test normalize_float()
def test_normalize_float_with_integer() -> None:
    assert normalize_float(5) == 5.0
    assert normalize_float(10) == 10.0
    assert normalize_float(-1) == -1.0


def test_normalize_float_with_none() -> None:
    assert normalize_float(None) is None


def test_normalize_float_with_string() -> None:
    assert normalize_float("") is None
    assert normalize_float("This should return None!") is None
    assert normalize_float("1.2") == 1.2
    assert normalize_float("23,2") == 23.2


def test_normalize_float_with_float() -> None:
    assert normalize_float(2.2) == 2.2
    assert normalize_float(3.0) == 3.0
    assert normalize_float(-12.2) == -12.2


# Test normalize_currency()


def test_normalize_currency_with_none() -> None:
    assert normalize_currency(None) is None


def test_normalize_currency_with_valid_iso_4217_code() -> None:
    assert normalize_currency("sek") == "SEK"
    assert normalize_currency("nok") == "NOK"
    assert normalize_currency("EUR") == "EUR"
    assert normalize_currency("usd") == "USD"
    assert normalize_currency("YEN") == "YEN"


def test_normalize_currency_with_sek_alias() -> None:
    assert normalize_currency("kr") == "SEK"
    assert normalize_currency("KR") == "SEK"
    assert normalize_currency(":-") == "SEK"


def test_normalize_currency_with_unknown() -> None:
    assert normalize_currency("UNKNOWN") is None


# Test normalize_availability()


def test_normalize_availability_with_none() -> None:
    assert normalize_availability(None) is None


def test_normalize_availability_with_bool() -> None:
    assert normalize_availability(True) == "available"
    assert normalize_availability(False) == "unavailable"


def test_normalize_availability_with_code() -> None:
    assert normalize_availability({"code": "IN_STOCK"}) == "IN_STOCK"
    assert normalize_availability({"code": "AVAI"}) == "AVAI"
    assert normalize_availability({"code": "UNAVAI"}) == "UNAVAI"


def test_normalize_availability_with_description() -> None:
    assert normalize_availability({"description": "ok"}) == "ok"
    assert normalize_availability({"description": "in stock"}) == "in stock"


def test_normalize_availability_with_string() -> None:
    assert normalize_availability("available") == "available"
    assert normalize_availability("unavailable") == "unavailable"
