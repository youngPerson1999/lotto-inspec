"""System category endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.db import ping_mongo
from app.schemas import HealthResponse, StorageHealthResponse
from app.services.lotto import load_stored_draws

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def getHealth() -> HealthResponse:
    """Lightweight liveness probe endpoint."""

    return HealthResponse(status="ok")


@router.get(
    "/storage",
    response_model=StorageHealthResponse,
    summary="저장 백엔드 및 MongoDB 연결 상태 확인",
)
def getStorageHealth() -> StorageHealthResponse:
    """현재 저장 백엔드 상태와 MongoDB 연결 여부를 반환."""

    settings = get_settings()
    if not settings.use_mongo_storage:
        draws = load_stored_draws()
        return StorageHealthResponse(
            backend="file",
            connected=True,
            message=f"파일 백엔드 사용 중 (경로: {settings.draw_storage_path}).",
            total_draws=len(draws),
        )

    try:
        _, total = ping_mongo()
    except Exception as exc:  # noqa: BLE001  # surface the message to the client
        raise HTTPException(
            status_code=503,
            detail={"message": f"MongoDB 연결 실패: {exc}"},
        ) from exc

    return StorageHealthResponse(
        backend="mongo",
        connected=True,
        message=(
            f"MongoDB 연결 성공 (db={settings.mongo_db_name}, "
            f"collection={settings.mongo_collection_name})."
        ),
        total_draws=total,
    )


__all__ = ["router"]
