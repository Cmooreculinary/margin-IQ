"""Mongo connection. Swappable for mongomock-motor in tests via `set_test_database`."""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConfigurationError, PyMongoError

from app.config import settings

_client: AsyncIOMotorClient | None = None
_db = None


def get_database():
    global _client, _db
    if _db is None:
        try:
            _client = AsyncIOMotorClient(settings.mongo_url)
        except (ValueError, ConfigurationError) as exc:
            # Not chained and no parser detail: both the URL and pymongo's
            # parse error can contain the database password, and this message
            # ends up in deploy logs.
            raise RuntimeError(
                "MONGO_URL is not a valid MongoDB connection string "
                f"({type(exc).__name__} while parsing it; detail withheld "
                "because it may contain credentials). Expected format: "
                "mongodb+srv://USER:PASSWORD@HOST/ -- check that the '@' "
                "between the password and the hostname is present and that "
                "any special characters in the username or password are "
                "URL-encoded (urllib.parse.quote_plus)."
            ) from None
        _db = _client[settings.mongo_db_name]
    return _db


async def verify_database_connection() -> None:
    """Fail startup with a clear error before seed logic touches collections."""
    db = get_database()
    try:
        await db.command("ping")
    except PyMongoError as exc:
        raise RuntimeError(
            "MongoDB connection failed. Check Render MONGO_URL, MongoDB Atlas "
            "Network Access allowlist, database user credentials, and TLS/CA "
            f"configuration. Original error: {exc}"
        ) from exc


def set_test_database(db) -> None:
    """Used by the test suite to inject a mongomock-backed database."""
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
]
