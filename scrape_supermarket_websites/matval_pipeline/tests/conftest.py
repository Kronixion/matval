from testcontainers.postgres import PostgresContainer
import pytest

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16") as pg:
        yield pg