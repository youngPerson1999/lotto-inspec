"""Lotto category endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from app.core.config import get_settings
from app.schemas import LottoDrawResponse, LottoSyncResponse
from app.services.auth import require_access_token
from app.services.lotto import (
    LottoDraw,
    LottoSyncResult,
    fetch_draw_info,
    fetch_latest_draw_info,
    get_latest_stored_draw,
    get_stored_draw,
    sync_draw_storage,
)

router = APIRouter(
    prefix="/lotto",
    tags=["lotto"],
    dependencies=[Depends(require_access_token)],
)


@router.get(
    "/latest",
    response_model=LottoDrawResponse,
)
def getLottoLatest() -> LottoDrawResponse:
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


@router.get(
    "/{draw_no}",
    response_model=LottoDrawResponse,
    summary="Fetch a specific Lotto draw by number",
)
def getLottoDrawByNumber(
    draw_no: int = Path(..., gt=0, description="Target draw number, e.g., 1197."),
) -> LottoDrawResponse:
    """Return Lotto result data for the provided drawing number."""

    try:
        settings = get_settings()
        draw = None
        if settings.use_mongo_storage:
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
    "/sync",
    response_model=LottoSyncResponse,
    summary="Synchronize local draw storage up to the latest 회차",
)
def postLottoSync() -> LottoSyncResponse:
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
