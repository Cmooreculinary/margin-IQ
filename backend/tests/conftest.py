import pytest

from app.db import SQLiteDatabase, set_test_database


@pytest.fixture
def db():
    database = SQLiteDatabase(":memory:")
    set_test_database(database)
    yield database
    set_test_database(None)
    database.close()
