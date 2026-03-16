# ruff: noqa: S101
import psycopg
import pytest
from matval_core.db.config import PostgresConfig
from matval_core.db.connector import PostgresConnector


@pytest.fixture(scope="session", autouse=False)
def _temp_table(pg_connector: PostgresConnector) -> None:
    pg_connector.non_sql_query(
        "CREATE TEMP TABLE IF NOT EXISTS _connector_test (id INT, label TEXT)"
    )

def test_ping(pg_connector: PostgresConnector) -> None:
    assert pg_connector.ping()

def test_ping_returns_false_when_unreachable() -> None:
    config = PostgresConfig(host="localhost", port=9999)
    connector = PostgresConnector(config)
    assert connector.ping() is False

def test_sql_query_returns_list(pg_connector: PostgresConnector) -> None:
    result = pg_connector.sql_query("SELECT 1 AS value")
    assert result == [{"value": 1}]

def test_sql_query_raises_on_bad_sql(pg_connector: PostgresConnector) -> None:
    with pytest.raises(psycopg.Error):
        pg_connector.sql_query("SELECT * FROM nonexistent_table_xyz")

def test_scalar_query_returns_value(pg_connector: PostgresConnector) -> None:
    result = pg_connector.scalar_query("SELECT 42")
    assert result == 42

def test_scalar_query_returns_none_on_empty(pg_connector: PostgresConnector) -> None:
    result = pg_connector.scalar_query("SELECT 1 WHERE false")
    assert result is None

def test_scalar_query_raises_on_bad_sql(pg_connector: PostgresConnector) -> None:
    with pytest.raises(psycopg.Error):
        pg_connector.scalar_query("SELECT * FROM nonexistent_table_xyz")

# _temp_table is not used intentionally inside the functions
#  It's only defined to be seen by pytest such that it knows to run the fixture
def test_non_sql_query_returns_rowcount(pg_connector: PostgresConnector, _temp_table: None) -> None:
    rowcount = pg_connector.non_sql_query("INSERT INTO _connector_test VALUES (1, 'a')")
    assert rowcount == 1

def test_execute_many_returns_rowcount(pg_connector: PostgresConnector, _temp_table: None) -> None:
    rowcount = pg_connector.execute_many(
        "INSERT INTO _connector_test VALUES (%s, %s)",
        [(2, "b"), (3, "c"), (4, "d")],
    )
    assert rowcount == 3

def test_transaction_commit(pg_connector: PostgresConnector, _temp_table: None) -> None:
    with pg_connector.transaction():
        pg_connector.non_sql_query("INSERT INTO _connector_test VALUES (99, 'tx')")

    result = pg_connector.scalar_query("SELECT COUNT(*) FROM _connector_test WHERE id = 99")
    assert result == 1

def _force_rollback(pg_connector: PostgresConnector) -> None:
    with pg_connector.transaction():
        pg_connector.non_sql_query("INSERT INTO _connector_test VALUES (100, 'will rollback')")
        raise RuntimeError("forced rollback")

def test_transaction_rollback_on_error(pg_connector: PostgresConnector, _temp_table: None) -> None:
    with pytest.raises(RuntimeError, match="forced rollback"):
        _force_rollback(pg_connector)

    result = pg_connector.scalar_query("SELECT COUNT(*) FROM _connector_test WHERE id = 100")
    assert result == 0

def test_exit_rolls_back_on_exception(pg_config: PostgresConfig, pg_connector: PostgresConnector, apply_schema: None) -> None:
    with pytest.raises(RuntimeError):
        with PostgresConnector(pg_config) as conn:
            conn.non_sql_query("INSERT INTO supermarkets (name) VALUES ('RollbackMart')")
            raise RuntimeError("trigger __exit__")

    count = pg_connector.scalar_query("SELECT COUNT(*) FROM supermarkets WHERE name = 'RollbackMart'")
    assert count == 0
