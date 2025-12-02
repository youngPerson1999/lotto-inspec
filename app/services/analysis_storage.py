"""Helpers for persisting analysis snapshots to MariaDB."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.models import AnalysisSnapshotORM
from app.services.lotto import get_latest_stored_draw


def _require_database_backend() -> None:
    settings = get_settings()
    if not settings.use_database_storage:
        raise RuntimeError(
            "MariaDB 저장소에서만 분석 결과를 보관하거나 조회할 수 있습니다. "
            "LOTTO_STORAGE_BACKEND=mariadb 환경을 설정하세요.",
        )


def _json_ready(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure payload keys/values are JSON/MariaDB friendly."""

    return json.loads(json.dumps(payload))


def save_analysis_snapshot(
    name: str,
    result: Dict[str, Any],
    metadata: Dict[str, Any] | None = None,
) -> str:
    """Store an analysis result document with draw coverage metadata."""

    _require_database_backend()
    latest = get_latest_stored_draw()
    document: Dict[str, Any] = {
        "name": name,
        "max_draw_no": latest.draw_no if latest else 0,
        "created_at": datetime.now(timezone.utc),
        "result": _json_ready(result),
        "metadata": _json_ready(metadata or {}),
    }

    with session_scope() as session:
        record = AnalysisSnapshotORM(
            name=document["name"],
            max_draw_no=document["max_draw_no"],
            created_at=document["created_at"],
            result=document["result"],
            metadata_json=document["metadata"],
        )
        session.add(record)
        session.flush()
        return str(record.id)


def get_latest_analysis_snapshot(name: str) -> Dict[str, Any] | None:
    """Return the newest snapshot for the given analysis name."""

    _require_database_backend()
    with session_scope() as session:
        snapshot = session.scalars(
            select(AnalysisSnapshotORM)
            .where(AnalysisSnapshotORM.name == name)
            .order_by(
                AnalysisSnapshotORM.max_draw_no.desc(),
                AnalysisSnapshotORM.created_at.desc(),
            )
        ).first()

    if not snapshot:
        return None

    created_at = snapshot.created_at
    return {
        "_id": str(snapshot.id),
        "name": snapshot.name,
        "max_draw_no": snapshot.max_draw_no,
        "created_at": created_at.isoformat()
        if isinstance(created_at, datetime)
        else created_at,
        "result": snapshot.result,
        "metadata": snapshot.metadata_json or {},
    }


__all__ = ["save_analysis_snapshot", "get_latest_analysis_snapshot"]
