from collections.abc import Generator

import pytest
from testcontainers.postgres import PostgresContainer

from matval_pipeline.config import PostgresConfig
from matval_pipeline.connector import PostgresConnector


@pytest.fixture(scope="session")
def pg_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer(image="postgres:16", username="test", password="test", dbname="test") as pg:  # noqa: S106
        yield pg


@pytest.fixture(scope="session")
def pg_config(pg_container: PostgresContainer) -> PostgresConfig:
    return PostgresConfig(
        host=pg_container.get_container_host_ip(),
        port=int(pg_container.get_exposed_port()),
        dbname=pg_container.dbname,
        user=pg_container.username,
        password=pg_container.password,
    )


@pytest.fixture(scope="session")
def pg_connector(pg_config: PostgresConfig) -> Generator[PostgresConnector, None, None]:
    with PostgresConnector(pg_config) as connector:
        yield connector