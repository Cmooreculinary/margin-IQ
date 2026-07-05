"""Startup behavior for malformed MONGO_URL values (e.g. missing '@' before host)."""
import pytest

import app.db as db_module


@pytest.fixture(autouse=True)
def reset_db_singletons():
    db_module._client = None
    db_module._db = None
    yield
    db_module._client = None
    db_module._db = None


def test_missing_at_sign_raises_clear_error_without_leaking_password(monkeypatch):
    # The '@' between password and host is missing, so pymongo parses
    # 'hunter2cluster0.abc.mongodb.net' as a port and raises ValueError.
    monkeypatch.setattr(
        db_module.settings, "mongo_url", "mongodb+srv://user:hunter2cluster0.abc.mongodb.net/"
    )
    with pytest.raises(RuntimeError) as excinfo:
        db_module.get_database()
    message = str(excinfo.value)
    assert "MONGO_URL is not a valid MongoDB connection string" in message
    assert "'@'" in message
    assert "hunter2" not in message  # never echo credentials into deploy logs
    assert excinfo.value.__cause__ is None and excinfo.value.__suppress_context__


def test_valid_url_still_constructs_client(monkeypatch):
    monkeypatch.setattr(db_module.settings, "mongo_url", "mongodb://localhost:27017")
    assert db_module.get_database() is not None
