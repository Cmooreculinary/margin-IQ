import pytest
from mongomock_motor import AsyncMongoMockClient

from app.db import set_test_database


@pytest.fixture
def db():
    client = AsyncMongoMockClient()
    database = client["margin_iq_test"]
    set_test_database(database)
    return database
