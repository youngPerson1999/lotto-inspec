"""Recommendation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.dto import (
    RecommendationBatchResponse,
    RecommendationResponse,
    RecommendationStrategy,
    UserRecommendationRequest,
    UserRecommendationResponse,
)
from app.services.auth import require_access_token
from app.services.recommendation import (
    RecommendationError,
    create_user_recommendation,
    get_recommendation,
    get_all_recommendations,
)

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"],
    dependencies=[Depends(require_access_token)],
)


@router.get(
    "",
    response_model=RecommendationResponse,
    summary="번호 추천 결과 조회",
)
def getRecommendations(
    strategy: RecommendationStrategy = Query(
        default=RecommendationStrategy.random,
        description="추천 전략",
    ),
) -> RecommendationResponse:
    try:
        payload = get_recommendation(strategy.value)
    except RecommendationError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    return RecommendationResponse(**payload)


@router.post(
    "",
    response_model=UserRecommendationResponse,
    summary="사용자 맞춤 추천 저장",
)
def postRecommendation(
    payload: UserRecommendationRequest,
) -> UserRecommendationResponse:
    try:
        saved = create_user_recommendation(payload.userId, payload.strategy.value)
    except RecommendationError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    return UserRecommendationResponse(
        id=saved["id"],
        userId=saved["userId"],
        strategy=payload.strategy,
        numbers=saved["numbers"],
        draw_no=saved["draw_no"],
        created_at=saved.get("created_at"),
        evaluation=saved.get("evaluation"),
    )


@router.get(
    "/all",
    response_model=RecommendationBatchResponse,
    summary="모든 전략에 대한 추천 결과",
)
def getAllRecommendations() -> RecommendationBatchResponse:
    try:
        payload = get_all_recommendations()
    except RecommendationError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    return RecommendationBatchResponse(
        recommendations=[RecommendationResponse(**item) for item in payload]
    )


__all__ = ["router"]
