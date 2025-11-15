"""FastAPI routers exposing Lotto endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes_analysis import router as analysis_router
from app.api.routes_lotto import router as lotto_router
from app.api.routes_system import router as system_router

router = APIRouter()
router.include_router(system_router)
router.include_router(lotto_router)
router.include_router(analysis_router)

__all__ = ["router"]
