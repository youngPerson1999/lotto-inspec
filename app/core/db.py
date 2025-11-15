"""MongoDB client helpers."""

from __future__ import annotations

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import CollectionInvalid

from app.core.config import get_settings

_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    """Return a singleton MongoClient instance."""

    global _client  # noqa: PLW0603  # retained to cache the client
    if _client is not None:
        return _client

    settings = get_settings()
    if not settings.mongo_uri:
        raise RuntimeError(
            "MONGO_URI must be set when LOTTO_STORAGE_BACKEND=mongo.",
        )

    _client = MongoClient(settings.mongo_uri)
    return _client


def _ensure_collection_exists() -> Collection:
    """Create 컬렉션/인덱스를 보장 후 핸들을 반환."""

    settings = get_settings()
    client = get_mongo_client()
    db = client[settings.mongo_db_name]
    coll_name = settings.mongo_collection_name

    try:
        if coll_name not in db.list_collection_names():
            db.create_collection(coll_name)
    except CollectionInvalid:
        pass  # already exists

    collection = db[coll_name]
    collection.create_index("draw_no", unique=True)
    return collection


def get_draw_collection() -> Collection:
    """Return the MongoDB collection storing Lotto draw documents."""

    return _ensure_collection_exists()


def ping_mongo() -> tuple[bool, int | None]:
    """Lightweight 연결 점검: ping 후 추정 도큐먼트 수를 반환."""

    collection = get_draw_collection()
    collection.database.client.admin.command("ping")
    total = collection.estimated_document_count()
    return True, int(total)


__all__ = ["get_draw_collection", "get_mongo_client", "ping_mongo"]
