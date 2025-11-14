"""FastAPI routers exposing Lotto endpoints."""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException, Path

from app.schemas import LottoDrawResponse, LottoSyncResponse
from app.services.lotto import (
    LottoDraw,
    LottoSyncResult,
    fetch_draw_info,
    fetch_latest_draw_info,
    sync_draw_storage,
)

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> Dict[str, str]:
    """Lightweight liveness probe endpoint."""

    return {"status": "ok"}


@router.get("/lotto/latest", response_model=LottoDrawResponse, tags=["lotto"])
def latest_draw() -> LottoDrawResponse:
    """Return the most recent Lotto draw as published by DhLottery."""

    try:
        draw: LottoDraw = fetch_latest_draw_info()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc

    return LottoDrawResponse(
        draw_no=draw.draw_no,
        draw_date=draw.draw_date,
        numbers=draw.numbers,
        bonus=draw.bonus,
    )


@router.get(
    "/lotto/{draw_no}",
    response_model=LottoDrawResponse,
    tags=["lotto"],
    summary="Fetch a specific Lotto draw by number",
)
def draw_by_number(
    draw_no: int = Path(..., gt=0, description="Target draw number, e.g., 1197."),
) -> LottoDrawResponse:
    """Return Lotto result data for the provided drawing number."""

    try:
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
    "/lotto/sync",
    response_model=LottoSyncResponse,
    tags=["lotto"],
    summary="Synchronize local draw storage up to the latest 회차",
)
def sync_lotto_storage() -> LottoSyncResponse:
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

