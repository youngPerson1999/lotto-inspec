"""System category endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def getHealth() -> HealthResponse:
    """Lightweight liveness probe endpoint."""

    return HealthResponse(status="ok")


__all__ = ["router"]
