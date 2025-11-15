"""Helpers for persisting analysis snapshots to MongoDB."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from bson import ObjectId

from app.core.config import get_settings
from app.core.db import get_mongo_client
from app.services.lotto import get_latest_stored_draw


def _require_mongo_collection():
    settings = get_settings()
    if not settings.use_mongo_storage:
        raise RuntimeError(
            "MongoDB 저장소에서만 분석 결과를 보관하거나 조회할 수 있습니다. "
            "LOTTO_STORAGE_BACKEND=mongo 환경을 설정하세요.",
        )

    client = get_mongo_client()
    return client[settings.mongo_db_name][settings.mongo_analysis_collection_name]


def _json_ready(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure payload keys/values are JSON/Mongo friendly."""

    return json.loads(json.dumps(payload))


def save_analysis_snapshot(
    name: str,
    result: Dict[str, Any],
    metadata: Dict[str, Any] | None = None,
) -> str:
    """Store an analysis result document with draw coverage metadata."""

    latest = get_latest_stored_draw()
    document: Dict[str, Any] = {
        "name": name,
        "max_draw_no": latest.draw_no if latest else 0,
        "created_at": datetime.now(timezone.utc),
        "result": _json_ready(result),
        "metadata": _json_ready(metadata or {}),
    }

    collection = _require_mongo_collection()
    inserted = collection.insert_one(document)
    return str(inserted.inserted_id or ObjectId())


def get_latest_analysis_snapshot(name: str) -> Dict[str, Any] | None:
    """Return the newest snapshot for the given analysis name."""

    collection = _require_mongo_collection()
    snapshot = collection.find_one(
        {"name": name},
        sort=[("max_draw_no", -1), ("created_at", -1)],
    )
    if not snapshot:
        return None

    snapshot["_id"] = str(snapshot["_id"])
    if isinstance(snapshot.get("created_at"), datetime):
        snapshot["created_at"] = snapshot["created_at"].isoformat()
    return snapshot


__all__ = ["save_analysis_snapshot", "get_latest_analysis_snapshot"]
