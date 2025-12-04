"""Lotto category endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path

from app.core.config import get_settings
from app.models.dto import (
    RecommendationEvaluationRequest,
    RecommendationEvaluationResult,
    UserTicketRequest,
    UserTicketResponse,
    LottoCheckRequest,
    LottoCheckResponse,
    LottoDrawResponse,
    LottoSyncResponse,
)
from app.services.auth import require_access_token
from app.services.lotto import (
    LottoDraw,
    LottoSyncResult,
    evaluate_ticket,
    fetch_draw_info,
    fetch_latest_draw_info,
    get_latest_stored_draw,
    get_stored_draw,
    sync_draw_storage,
)
from app.services.recommendation import (
    RecommendationError,
    evaluate_user_recommendation,
)
from app.services.user_ticket import (
    save_user_ticket,
    get_user_tickets,
    UserTicketError,
)

router = APIRouter(
    prefix="/lotto",
    tags=["lotto"],
)


@router.get(
    "/latest",
    response_model=LottoDrawResponse,
)
def getLottoLatest(
    _: dict = Depends(require_access_token),
) -> LottoDrawResponse:
    """Return the most recent Lotto draw as published by DhLottery."""

    try:
        draw = fetch_latest_draw_info()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc

    return LottoDrawResponse(
        draw_no=draw.draw_no,
        draw_date=draw.draw_date,
        numbers=draw.numbers,
        bonus=draw.bonus,
    )


@router.post(
    "/tickets",
    response_model=UserTicketResponse,
    summary="사용자 입력 번호 저장 및 당첨 여부 기록",
)
def postUserTicket(
    payload: UserTicketRequest,
    user=Depends(require_access_token),
) -> UserTicketResponse:
    try:
        saved = save_user_ticket(user["user_id"], payload.draw_no, payload.numbers)
    except UserTicketError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc

    return UserTicketResponse(**saved)


@router.get(
    "/tickets",
    response_model=List[UserTicketResponse],
    summary="사용자가 입력/검증한 티켓 목록 조회",
)
def getUserTickets(
    user=Depends(require_access_token),
) -> List[UserTicketResponse]:
    tickets = get_user_tickets(user["user_id"])
    return [UserTicketResponse(**item) for item in tickets]


@router.get(
    "/{draw_no}",
    response_model=LottoDrawResponse,
    summary="Fetch a specific Lotto draw by number",
)
def getLottoDrawByNumber(
    draw_no: int = Path(..., gt=0, description="Target draw number, e.g., 1197."),
    _: dict = Depends(require_access_token),
) -> LottoDrawResponse:
    """Return Lotto result data for the provided drawing number."""

    try:
        settings = get_settings()
        draw = None
        if settings.use_database_storage:
            draw = get_stored_draw(draw_no)
        if draw is None:
            draw = fetch_draw_info(draw_no)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc

    return LottoDrawResponse(
        draw_no=draw.draw_no,
        draw_date=draw.draw_date,
        numbers=draw.numbers,
        bonus=draw.bonus,
    )


@router.post(
    "/check",
    response_model=LottoCheckResponse,
    summary="입력 번호가 당첨인지 확인",
)
def postLottoCheck(
    payload: LottoCheckRequest,
    _: dict = Depends(require_access_token),
) -> LottoCheckResponse:
    settings = get_settings()

    latest_known_no = None
    latest_stored = get_latest_stored_draw()
    if latest_stored is not None:
        latest_known_no = latest_stored.draw_no

    if latest_known_no is None:
        try:
            latest_known_no = fetch_latest_draw_info().draw_no
        except ValueError:
            latest_known_no = None

    if latest_known_no is not None and payload.draw_no > latest_known_no:
        message = (
            f"{payload.draw_no}회차는 아직 추첨되지 않았어요. "
            f"가장 최근 추첨은 {latest_known_no}회차입니다."
        )
        raise HTTPException(status_code=400, detail={"message": message})

    try:
        draw = None
        if settings.use_database_storage:
            draw = get_stored_draw(payload.draw_no)
        if draw is None:
            draw = fetch_draw_info(payload.draw_no)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc

    try:
        result = evaluate_ticket(draw, payload.numbers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    return LottoCheckResponse(**result)


@router.post(
    "/recommendations/evaluate",
    response_model=RecommendationEvaluationResult,
    summary="저장된 추천 번호 당첨 여부 확인",
)
def postRecommendationEvaluation(
    payload: RecommendationEvaluationRequest,
    user=Depends(require_access_token),
) -> LottoCheckResponse:
    try:
        result = evaluate_user_recommendation(
            user["user_id"],
            payload.recommendation_id,
            payload.draw_no,
            payload.numbers,
        )
    except RecommendationError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc

    return RecommendationEvaluationResult(
        rank=result.get("rank"),
        match_count=result.get("match_count"),
        matched_numbers=result.get("matched_numbers"),
        bonus_matched=result.get("bonus_matched"),
    )


@router.post(
    "/sync",
    response_model=LottoSyncResponse,
    summary="Synchronize local draw storage up to the latest 회차",
)
def postLottoSync(
    _: dict = Depends(require_access_token),
) -> LottoSyncResponse:
    """Trigger a synchronization run to download missing draw data."""

    try:
        result: LottoSyncResult = sync_draw_storage()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc

    return LottoSyncResponse(
        previous_max=result.previous_max,
        latest=result.latest,
        inserted=result.inserted,
        draws=[
            LottoDrawResponse(
                draw_no=draw.draw_no,
                draw_date=draw.draw_date,
                numbers=draw.numbers,
                bonus=draw.bonus,
            )
            for draw in result.draws
        ],
    )


__all__ = ["router"]
