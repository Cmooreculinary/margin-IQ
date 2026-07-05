"""Startup behavior for SQLITE_PATH values (unusable paths must fail clearly)."""
import pytest

import app.db as db_module


@pytest.fixture(autouse=True)
def reset_db_singleton():
    db_module._db = None
    yield
    if db_module._db is not None:
        db_module._db.close()
    db_module._db = None


def test_unusable_path_raises_clear_error(monkeypatch, tmp_path):
    # The parent "directory" is actually a file, so the database can never be
    # created there. Startup should explain the problem instead of crashing
    # with a raw sqlite/OS traceback.
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("occupied")
    monkeypatch.setattr(db_module.settings, "sqlite_path", str(blocker / "margin_iq.db"))
    with pytest.raises(RuntimeError) as excinfo:
        db_module.get_database()
    assert "SQLITE_PATH" in str(excinfo.value)


def test_valid_path_creates_database(monkeypatch, tmp_path):
    monkeypatch.setattr(db_module.settings, "sqlite_path", str(tmp_path / "data" / "margin_iq.db"))
    db = db_module.get_database()
    assert db is not None
    # Parent directories are created on demand so a fresh deploy just works.
    assert (tmp_path / "data" / "margin_iq.db").exists()


@pytest.mark.asyncio
async def test_documents_round_trip(monkeypatch, tmp_path):
    from datetime import datetime, timezone

    monkeypatch.setattr(db_module.settings, "sqlite_path", str(tmp_path / "margin_iq.db"))
    db = db_module.get_database()
    doc = {
        "_id": "t1",
        "slug": "demo",
        "created_at": datetime(2026, 1, 5, 12, 30, tzinfo=timezone.utc),
        "nested": {"tolerance": 2.0, "flags": [True, None, "x"]},
    }
    await db.tenants.insert_one(dict(doc))
    stored = await db.tenants.find_one({"slug": "demo"})
    # Aware datetimes come back naive UTC, matching the old Mongo driver behavior.
    assert stored == {**doc, "created_at": datetime(2026, 1, 5, 12, 30)}
