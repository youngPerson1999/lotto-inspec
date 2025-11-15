"""FastAPI routers exposing Lotto endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes_analysis import router as analysis_router
from app.api.routes_auth import router as auth_router
from app.api.routes_lotto import router as lotto_router
from app.api.routes_system import router as system_router
from app.api.routes_recommendation import router as recommendation_router
from app.api.routes_user import router as user_router

router = APIRouter()
router.include_router(system_router)
router.include_router(lotto_router)
router.include_router(analysis_router)
router.include_router(recommendation_router)
router.include_router(auth_router)
router.include_router(user_router)

__all__ = ["router"]
