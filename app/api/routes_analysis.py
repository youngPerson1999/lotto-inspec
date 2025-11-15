"""Analysis category endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from analysis import summarize_draws
from app.schemas import LottoAnalysisResponse

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get(
    "",
    response_model=LottoAnalysisResponse,
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


__all__ = ["router"]
