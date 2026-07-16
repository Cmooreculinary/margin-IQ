"""SQLite-backed document store.

Exposes the (small) subset of the async MongoDB API this app actually uses --
`db.collection.find_one/find/insert_one/...` -- so routers, services, and seed
scripts read exactly as they did against Motor. Each collection is a table of
(id, doc-as-JSON) rows; filtering happens in Python, which is plenty for the
per-tenant data volumes this app handles.

Swappable for an in-memory database in tests via `set_test_database`.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

_db = None


# --- JSON round-tripping ----------------------------------------------------
# Documents carry datetime values (period bounds, run_at, created_at). They are
# stored as {"$dt": iso-string} so they come back as datetime objects. Like the
# Mongo driver, aware datetimes are normalized to UTC and returned naive, so
# downstream consumers (e.g. openpyxl, which rejects tz-aware datetimes) see
# exactly what they saw before.

_DT_MARKER = "$dt"


def _json_default(value: Any):
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return {_DT_MARKER: value.isoformat()}
    raise TypeError(f"Cannot store value of type {type(value).__name__} in the database")


def _json_object_hook(obj: dict):
    if len(obj) == 1 and _DT_MARKER in obj:
        return datetime.fromisoformat(obj[_DT_MARKER])
    return obj


def _dumps(doc: dict) -> str:
    return json.dumps(doc, default=_json_default)


def _loads(raw: str) -> dict:
    return json.loads(raw, object_hook=_json_object_hook)


# --- query matching ---------------------------------------------------------

def _as_comparable(value: Any) -> Any:
    """Mongo treats naive datetimes as UTC; normalize so naive/aware compare."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _compare(doc_value: Any, op: str, cond_value: Any) -> bool:
    a, b = _as_comparable(doc_value), _as_comparable(cond_value)
    try:
        if op == "$gte":
            return a is not None and a >= b
        if op == "$lte":
            return a is not None and a <= b
        if op == "$gt":
            return a is not None and a > b
        if op == "$lt":
            return a is not None and a < b
    except TypeError:
        return False
    raise ValueError(f"Unsupported query operator: {op}")


def _matches_condition(doc_value: Any, condition: Any) -> bool:
    if isinstance(condition, dict) and any(k.startswith("$") for k in condition):
        for op, cond_value in condition.items():
            if op == "$ne":
                if _as_comparable(doc_value) == _as_comparable(cond_value):
                    return False
            elif op == "$in":
                if doc_value not in cond_value:
                    return False
            elif op == "$nin":
                if doc_value in cond_value:
                    return False
            elif op in ("$gte", "$lte", "$gt", "$lt"):
                if not _compare(doc_value, op, cond_value):
                    return False
            else:
                raise ValueError(f"Unsupported query operator: {op}")
        return True
    return _as_comparable(doc_value) == _as_comparable(condition)


def _matches(doc: dict, query: dict) -> bool:
    for key, condition in query.items():
        if key == "$or":
            if not any(_matches(doc, sub) for sub in condition):
                return False
        elif key == "$and":
            if not all(_matches(doc, sub) for sub in condition):
                return False
        elif not _matches_condition(doc.get(key), condition):
            return False
    return True


# --- result / cursor objects ------------------------------------------------

class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class InsertManyResult:
    def __init__(self, inserted_ids):
        self.inserted_ids = inserted_ids


class UpdateResult:
    def __init__(self, matched_count: int, modified_count: int, upserted_id=None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class DeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class Cursor:
    """Lazy find() result supporting the chaining the app uses:
    `find(q)`, `find(q).sort(key, -1)`, then `await ....to_list(length=N)`."""

    def __init__(self, collection: "Collection", query: dict):
        self._collection = collection
        self._query = query
        self._sort: tuple[str, int] | None = None
        self._limit: int | None = None

    def sort(self, key: str, direction: int = 1) -> "Cursor":
        self._sort = (key, direction)
        return self

    def limit(self, count: int) -> "Cursor":
        self._limit = count
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        docs = self._collection._find_all(self._query)
        if self._sort is not None:
            key, direction = self._sort
            docs.sort(
                key=lambda d: (d.get(key) is not None, _as_comparable(d.get(key))),
                reverse=direction < 0,
            )
        cap = self._limit if self._limit is not None else length
        return docs if cap is None else docs[:cap]

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for doc in await self.to_list():
            yield doc


# --- collections and database ------------------------------------------------

class Collection:
    def __init__(self, conn: sqlite3.Connection, name: str):
        self._conn = conn
        self._name = name
        conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{name}" (id TEXT PRIMARY KEY, doc TEXT NOT NULL)'
        )

    def _find_all(self, query: dict) -> list[dict]:
        # Fast path: direct _id equality lookups hit the primary key.
        id_value = query.get("_id")
        if isinstance(id_value, str):
            rows = self._conn.execute(
                f'SELECT doc FROM "{self._name}" WHERE id = ?', (id_value,)
            ).fetchall()
        else:
            rows = self._conn.execute(f'SELECT doc FROM "{self._name}"').fetchall()
        docs = [_loads(row[0]) for row in rows]
        return [d for d in docs if _matches(d, query)]

    def find(self, query: dict | None = None) -> Cursor:
        return Cursor(self, query or {})

    async def find_one(self, query: dict | None = None) -> dict | None:
        docs = self._find_all(query or {})
        return docs[0] if docs else None

    async def count_documents(self, query: dict | None = None) -> int:
        return len(self._find_all(query or {}))

    async def insert_one(self, doc: dict) -> InsertOneResult:
        doc.setdefault("_id", str(uuid.uuid4()))
        self._conn.execute(
            f'INSERT INTO "{self._name}" (id, doc) VALUES (?, ?)',
            (str(doc["_id"]), _dumps(doc)),
        )
        self._conn.commit()
        return InsertOneResult(doc["_id"])

    async def insert_many(self, docs: list[dict]) -> InsertManyResult:
        for doc in docs:
            doc.setdefault("_id", str(uuid.uuid4()))
        self._conn.executemany(
            f'INSERT INTO "{self._name}" (id, doc) VALUES (?, ?)',
            [(str(d["_id"]), _dumps(d)) for d in docs],
        )
        self._conn.commit()
        return InsertManyResult([d["_id"] for d in docs])

    def _apply_update(self, doc: dict, update: dict) -> dict:
        for op, fields in update.items():
            if op == "$set":
                doc.update(fields)
            elif op == "$unset":
                for field in fields:
                    doc.pop(field, None)
            else:
                raise ValueError(f"Unsupported update operator: {op}")
        return doc

    def _store(self, doc: dict) -> None:
        self._conn.execute(
            f'UPDATE "{self._name}" SET doc = ? WHERE id = ?',
            (_dumps(doc), str(doc["_id"])),
        )

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> UpdateResult:
        docs = self._find_all(query)
        if docs:
            updated = self._apply_update(docs[0], update)
            self._store(updated)
            self._conn.commit()
            return UpdateResult(matched_count=1, modified_count=1)
        if upsert:
            # Mongo upsert semantics: the new doc starts from the filter's
            # plain-equality fields, then the update is applied on top.
            base = {k: v for k, v in query.items() if not k.startswith("$") and not isinstance(v, dict)}
            new_doc = self._apply_update(base, update)
            result = await self.insert_one(new_doc)
            return UpdateResult(matched_count=0, modified_count=0, upserted_id=result.inserted_id)
        return UpdateResult(matched_count=0, modified_count=0)

    async def update_many(self, query: dict, update: dict) -> UpdateResult:
        docs = self._find_all(query)
        for doc in docs:
            self._store(self._apply_update(doc, update))
        self._conn.commit()
        return UpdateResult(matched_count=len(docs), modified_count=len(docs))

    async def delete_one(self, query: dict) -> DeleteResult:
        docs = self._find_all(query)
        if not docs:
            return DeleteResult(0)
        self._conn.execute(f'DELETE FROM "{self._name}" WHERE id = ?', (str(docs[0]["_id"]),))
        self._conn.commit()
        return DeleteResult(1)

    async def delete_many(self, query: dict) -> DeleteResult:
        docs = self._find_all(query)
        self._conn.executemany(
            f'DELETE FROM "{self._name}" WHERE id = ?', [(str(d["_id"]),) for d in docs]
        )
        self._conn.commit()
        return DeleteResult(len(docs))


class SQLiteDatabase:
    """Attribute access (`db.tenants`) returns a Collection, like Motor."""

    def __init__(self, path: str):
        self._path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._collections: dict[str, Collection] = {}

    def __getattr__(self, name: str) -> Collection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    def __getitem__(self, name: str) -> Collection:
        if name not in self._collections:
            self._collections[name] = Collection(self._conn, name)
        return self._collections[name]

    async def command(self, name: str) -> dict:
        if name == "ping":
            self._conn.execute("SELECT 1")
            return {"ok": 1}
        raise ValueError(f"Unsupported database command: {name}")

    def close(self) -> None:
        self._conn.close()


def get_database() -> SQLiteDatabase:
    global _db
    if _db is None:
        path = settings.sqlite_path
        if path != ":memory:":
            try:
                Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
            except (OSError, NotADirectoryError) as exc:
                raise RuntimeError(
                    f"SQLITE_PATH points at an unusable location ({path!r}): could not "
                    f"create its parent directory. Original error: {exc}"
                ) from exc
        try:
            _db = SQLiteDatabase(path)
        except sqlite3.Error as exc:
            raise RuntimeError(
                f"Could not open the SQLite database at SQLITE_PATH={path!r}. "
                f"Check that the path is writable. Original error: {exc}"
            ) from exc
    return _db


async def verify_database_connection() -> None:
    """Fail startup with a clear error before seed logic touches collections."""
    db = get_database()
    try:
        await db.command("ping")
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"SQLite database check failed for SQLITE_PATH={settings.sqlite_path!r}. "
            f"Check that the file is a valid SQLite database and is writable. "
            f"Original error: {exc}"
        ) from exc


def set_test_database(db) -> None:
    """Used by the test suite to inject an in-memory database."""
    global _db
    _db = db


COLLECTIONS = [
    "tenants",
    "locations",
    "menu_items",
    "pmix_records",
    "labor_matrix",
    "financials",
    "reconciliation_runs",
    "item_metrics",
    "competitors",
    "recommendations",
    "approval_log",
    "seasons",
    "baselines",
    "validation_runs",
    "engagement_plans",
    "drive_credentials",
    "supplier_price_comparisons",
    "supplier_catalog_items",
]
