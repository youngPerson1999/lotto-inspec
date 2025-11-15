"""FastAPI routers exposing Lotto endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from analysis import summarize_draws
from app.schemas import (
    HealthResponse,
    LottoAnalysisResponse,
    LottoDrawResponse,
    LottoSyncResponse,
)
from app.services.lotto import (
    LottoDraw,
    LottoSyncResult,
    fetch_draw_info,
    fetch_latest_draw_info,
    sync_draw_storage,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def getHealth() -> HealthResponse:
    """Lightweight liveness probe endpoint."""

    return HealthResponse(status="ok")


@router.get(
    "/lotto/latest",
    response_model=LottoDrawResponse,
    tags=["lotto"],
)
def getLottoLatest() -> LottoDrawResponse:
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
    "/lotto/analysis",
    response_model=LottoAnalysisResponse,
    tags=["lotto"],
    summary="저장된 회차 기반 통계 분석 결과 조회",
)
def getLottoAnalysis() -> LottoAnalysisResponse:
    """Return aggregate statistical insights about stored Lotto draws."""

    try:
        summary = summarize_draws()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    chi_square = summary["chi_square"]
    runs = summary["runs_test"]

    return LottoAnalysisResponse(
        total_draws=summary["total_draws"],
        chi_square={
            "statistic": chi_square.statistic,
            "p_value": chi_square.p_value,
            "observed": chi_square.observed,
            "expected": chi_square.expected,
        },
        runs_test={
            "runs": runs.runs,
            "expected_runs": runs.expected_runs,
            "z_score": runs.z_score,
            "p_value": runs.p_value,
            "total_observations": runs.total_observations,
        },
        gap_histogram=summary["gap_histogram"],
        frequency=summary["frequency"],
    )


@router.get(
    "/lotto/{draw_no}",
    response_model=LottoDrawResponse,
    tags=["lotto"],
    summary="Fetch a specific Lotto draw by number",
)
def getLottoDrawByNumber(
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
