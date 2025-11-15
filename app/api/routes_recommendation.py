"""Recommendation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import RecommendationResponse
from app.services.recommendation import (
    STRATEGIES,
    RecommendationError,
    get_recommendation,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get(
    "",
    response_model=RecommendationResponse,
    summary="번호 추천 결과 조회",
)
def getRecommendations(
    strategy: str = Query(
        default="random",
        description=f"추천 전략 ({', '.join(sorted(STRATEGIES))})",
    ),
) -> RecommendationResponse:
    try:
        payload = get_recommendation(strategy)
    except RecommendationError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    return RecommendationResponse(**payload)


__all__ = ["router"]
