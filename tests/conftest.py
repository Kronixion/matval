from collections.abc import Generator
from importlib.resources import files

import pytest
from matval_core.db.config import PostgresConfig
from matval_core.db.connector import PostgresConnector
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_container() -> Generator[PostgresContainer]:
    with PostgresContainer(image="postgres:16", username="test", password="test", dbname="test") as pg:  # noqa: S106
        yield pg


@pytest.fixture(scope="session")
def pg_config(pg_container: PostgresContainer) -> PostgresConfig:
    return PostgresConfig(
        host=pg_container.get_container_host_ip(),
        port=int(pg_container.get_exposed_port(5432)),
        dbname=pg_container.dbname,
        user=pg_container.username,
        password=pg_container.password,
    )


@pytest.fixture(scope="session")
def pg_connector(pg_config: PostgresConfig) -> Generator[PostgresConnector]:
    with PostgresConnector(pg_config) as connector:
        yield connector


@pytest.fixture(scope="session")
def apply_schema(pg_connector: PostgresConnector) -> None:
    schema_sql = files("matval_core.db").joinpath("schema.sql").read_text()
    pg_connector.connection.pgconn.exec_(schema_sql.encode())
    pg_connector.connection.commit()
