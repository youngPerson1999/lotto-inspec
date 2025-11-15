"""Analysis category endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from analysis import (
    dependency_summary,
    distribution_summary,
    pattern_analysis_summary,
    randomness_suite_summary,
    sum_runs_summary,
    summarize_draws,
)
from app.schemas import (
    DependencyAnalysisResponse,
    DependencyAnalysisSnapshotResponse,
    DistributionAnalysisResponse,
    LottoAnalysisResponse,
    LottoAnalysisSnapshotResponse,
    PatternAnalysisResponse,
    PatternAnalysisSnapshotResponse,
    RandomnessSuiteResponse,
    RandomnessSuiteSnapshotResponse,
    SumRunsTestResponse,
    SumRunsTestSnapshotResponse,
)
from app.services.analysis_storage import (
    get_latest_analysis_snapshot,
    save_analysis_snapshot,
)
from app.services.auth import require_access_token

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(require_access_token)],
)


def _analysis_key(base: str, **params: Any) -> str:
    if not params:
        return base
    suffix = ",".join(f"{key}={params[key]}" for key in sorted(params))
    return f"{base}|{suffix}"


def _load_snapshot_or_404(name: str) -> Dict[str, Any]:
    try:
        snapshot = get_latest_analysis_snapshot(name)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"message": str(exc)},
        ) from exc

    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail={"message": f"저장된 분석 결과가 없습니다: {name}"},
        )
    return snapshot


def _store_snapshot(name: str, payload: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> None:
    try:
        save_analysis_snapshot(name, payload, metadata=metadata)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc


def _build_lotto_analysis_response(summary: Dict[str, Any]) -> LottoAnalysisResponse:
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


def _serialize_pattern_result(result):
    return {
        "statistic": result.statistic,
        "p_value": result.p_value,
        "observed": result.observed,
        "expected": result.expected,
    }


def _serialize_distribution_result(result):
    return {
        "chi_square_statistic": result.chi_square_statistic,
        "chi_square_p_value": result.chi_square_p_value,
        "ks_statistic": result.ks_statistic,
        "ks_p_value": result.ks_p_value,
        "observed_histogram": {
            str(key): value for key, value in result.observed_histogram.items()
        },
        "expected_histogram": {
            str(key): value for key, value in result.expected_histogram.items()
        },
    }


def _run_randomness_suite_analysis(
    *,
    encoding: str,
    block_size: int,
    serial_block: int,
) -> RandomnessSuiteResponse:
    try:
        summary = randomness_suite_summary(
            encoding=encoding,
            block_size=block_size,
            serial_block=serial_block,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    response = RandomnessSuiteResponse(**summary)
    key = _analysis_key(
        "randomness",
        encoding=encoding,
        block_size=block_size,
        serial_block=serial_block,
    )
    _store_snapshot(
        key,
        response.model_dump(),
        metadata={
            "encoding": encoding,
            "block_size": block_size,
            "serial_block": serial_block,
        },
    )
    return response


@router.get(
    "",
    response_model=LottoAnalysisSnapshotResponse,
    summary="저장된 회차 기반 통계 분석 결과 조회",
)
def getLottoAnalysis() -> LottoAnalysisSnapshotResponse:
    snapshot = _load_snapshot_or_404("summary")
    return LottoAnalysisSnapshotResponse(
        draw_no=snapshot["max_draw_no"],
        result=LottoAnalysisResponse(**snapshot["result"]),
    )


@router.post(
    "",
    response_model=LottoAnalysisResponse,
    summary="저장된 회차 기반 통계 분석 결과 갱신",
)
def postLottoAnalysis() -> LottoAnalysisResponse:
    try:
        summary = summarize_draws()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    response = _build_lotto_analysis_response(summary)
    _store_snapshot("summary", response.model_dump())
    return response


@router.get(
    "/dependency",
    response_model=DependencyAnalysisSnapshotResponse,
    summary="연속 회차 의존성 검정 결과",
)
def getLottoDependencyAnalysis() -> DependencyAnalysisSnapshotResponse:
    snapshot = _load_snapshot_or_404("dependency")
    return DependencyAnalysisSnapshotResponse(
        draw_no=snapshot["max_draw_no"],
        result=DependencyAnalysisResponse(**snapshot["result"]),
    )


@router.post(
    "/dependency",
    response_model=DependencyAnalysisResponse,
    summary="연속 회차 의존성 검정 갱신",
)
def postLottoDependencyAnalysis() -> DependencyAnalysisResponse:
    try:
        summary = dependency_summary()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    response = DependencyAnalysisResponse(**summary)
    _store_snapshot("dependency", response.model_dump())
    return response


@router.get(
    "/runs/sum",
    response_model=SumRunsTestSnapshotResponse,
    summary="회차 합계 기반 런 검정",
)
def getLottoSumRunsTest() -> SumRunsTestSnapshotResponse:
    snapshot = _load_snapshot_or_404("runs_sum")
    return SumRunsTestSnapshotResponse(
        draw_no=snapshot["max_draw_no"],
        result=SumRunsTestResponse(**snapshot["result"]),
    )


@router.post(
    "/runs/sum",
    response_model=SumRunsTestResponse,
    summary="회차 합계 기반 런 검정 갱신",
)
def postLottoSumRunsTest() -> SumRunsTestResponse:
    try:
        result = sum_runs_summary()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    response = SumRunsTestResponse(
        runs=result.runs,
        expected_runs=result.expected_runs,
        z_score=result.z_score,
        p_value=result.p_value,
        total_observations=result.total_observations,
        median_threshold=result.median_threshold,
    )
    _store_snapshot("runs_sum", response.model_dump())
    return response


@router.get(
    "/patterns",
    response_model=PatternAnalysisSnapshotResponse,
    summary="홀짝/저고/끝자리 패턴 χ² 검정",
)
def getLottoPatternAnalysis() -> PatternAnalysisSnapshotResponse:
    snapshot = _load_snapshot_or_404("patterns")
    return PatternAnalysisSnapshotResponse(
        draw_no=snapshot["max_draw_no"],
        result=PatternAnalysisResponse(**snapshot["result"]),
    )


@router.post(
    "/patterns",
    response_model=PatternAnalysisResponse,
    summary="홀짝/저고/끝자리 패턴 검정 갱신",
)
def postLottoPatternAnalysis() -> PatternAnalysisResponse:
    try:
        summary = pattern_analysis_summary()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    response = PatternAnalysisResponse(
        parity=_serialize_pattern_result(summary["parity"]),
        low_high=_serialize_pattern_result(summary["low_high"]),
        last_digit=_serialize_pattern_result(summary["last_digit"]),
    )
    _store_snapshot("patterns", response.model_dump())
    return response


@router.post(
    "/distribution",
    response_model=DistributionAnalysisResponse,
    summary="합계/간격 분포 적합도 검정 (POST 전용)",
)
def postLottoDistributionAnalysis(
    sample_size: int = Query(
        default=100_000,
        ge=10_000,
        le=500_000,
        description="시뮬레이션 샘플 수 (기본 100k)",
    ),
) -> DistributionAnalysisResponse:
    try:
        summary = distribution_summary(sample_size=sample_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    response = DistributionAnalysisResponse(
        sum=_serialize_distribution_result(summary["sum"]),
        gap=_serialize_distribution_result(summary["gap"]),
    )
    key = _analysis_key("distribution", sample_size=sample_size)
    _store_snapshot(
        key,
        response.model_dump(),
        metadata={"sample_size": sample_size},
    )
    return response


@router.get(
    "/randomness",
    response_model=RandomnessSuiteSnapshotResponse,
    summary="난수 검정 스위트 (NIST 스타일)",
)
def getLottoRandomnessSuite(
    encoding: str = Query(
        default="presence",
        description="비트 인코딩 (presence/parity/binary)",
    ),
    block_size: int = Query(
        default=128,
        ge=8,
        le=1024,
        description="Block frequency test용 블록 크기",
    ),
    serial_block: int = Query(
        default=2,
        ge=2,
        le=4,
        description="Serial test block length m",
    ),
) -> RandomnessSuiteSnapshotResponse:
    key = _analysis_key(
        "randomness",
        encoding=encoding,
        block_size=block_size,
        serial_block=serial_block,
    )
    try:
        snapshot = _load_snapshot_or_404(key)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        _run_randomness_suite_analysis(
            encoding=encoding,
            block_size=block_size,
            serial_block=serial_block,
        )
        snapshot = _load_snapshot_or_404(key)
    return RandomnessSuiteSnapshotResponse(
        draw_no=snapshot["max_draw_no"],
        result=RandomnessSuiteResponse(**snapshot["result"]),
    )


@router.post(
    "/randomness",
    response_model=RandomnessSuiteResponse,
    summary="난수 검정 스위트 갱신",
)
def postLottoRandomnessSuite(
    encoding: str = Query(
        default="presence",
        description="비트 인코딩 (presence/parity/binary)",
    ),
    block_size: int = Query(
        default=128,
        ge=8,
        le=1024,
        description="Block frequency test용 블록 크기",
    ),
    serial_block: int = Query(
        default=2,
        ge=2,
        le=4,
        description="Serial test block length m",
    ),
) -> RandomnessSuiteResponse:
    response = _run_randomness_suite_analysis(
        encoding=encoding,
        block_size=block_size,
        serial_block=serial_block,
    )
    return response


__all__ = ["router"]
