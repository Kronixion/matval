import pytest
from testcontainers.postgres import PostgresContainer

import psycopg
from psycopg import Connection

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer(image="postgres:16", username="test", password="test", dbname="test") as pg: #noqa: S106, the password is a default for testing
        yield pg

@pytest.fixture(scope="session")
def pg_connection() -> Connection[any]:
    pg_connector = psycopg.connect()

    return pg_connector