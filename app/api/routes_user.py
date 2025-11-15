"""User-specific endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import (
    RecommendationStrategy,
    UserRecommendationResponse,
)
from app.services.auth import require_access_token
from app.services.recommendation import (
    RecommendationError,
    get_user_recommendations,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.get(
    "/recommendations",
    response_model=List[UserRecommendationResponse],
    summary="사용자 추천 이력 조회",
)
def get_user_recommendation_history(
    user=Depends(require_access_token),
) -> List[UserRecommendationResponse]:
    try:
        history = get_user_recommendations(user["user_id"])
    except RecommendationError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    responses: List[UserRecommendationResponse] = []
    for item in history:
        try:
            strategy = RecommendationStrategy(item["strategy"])
        except ValueError as exc:
            raise HTTPException(
                status_code=500,
                detail={"message": f"알 수 없는 전략입니다: {item['strategy']}"},
            ) from exc

        responses.append(
            UserRecommendationResponse(
                userId=item["userId"],
                strategy=strategy,
                numbers=item["numbers"],
                draw_no=item.get("draw_no"),
                created_at=item.get("created_at"),
            )
        )
    return responses


__all__ = ["router"]
