"""MongoDB client helpers."""

from __future__ import annotations

from pymongo import MongoClient
from pymongo.collection import Collection

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


def get_draw_collection() -> Collection:
    """Return the MongoDB collection storing Lotto draw documents."""

    settings = get_settings()
    client = get_mongo_client()
    return client[settings.mongo_db_name][settings.mongo_collection_name]


def ping_mongo() -> tuple[bool, int | None]:
    """Lightweight 연결 점검: ping 후 추정 도큐먼트 수를 반환."""

    collection = get_draw_collection()
    collection.database.client.admin.command("ping")
    total = collection.estimated_document_count()
    return True, int(total)


__all__ = ["get_draw_collection", "get_mongo_client", "ping_mongo"]
