"""Analysis category endpoints."""

from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from analysis import distribution_summary
from app.models.dto import (
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
from app.services.analysis_storage import get_latest_analysis_snapshot, save_analysis_snapshot
from app.services.analysis_tasks import (
    analysis_key,
    refresh_dependency_analysis,
    refresh_lotto_summary,
    refresh_pattern_analysis,
    refresh_randomness_suite,
    refresh_runs_sum_analysis,
)
from app.services.auth import require_access_token

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(require_access_token)],
)


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


SnapshotRefresher = Callable[[], object]


def _ensure_snapshot(name: str, refresher: SnapshotRefresher) -> Dict[str, Any]:
    try:
        return _load_snapshot_or_404(name)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        try:
            refresher()
        except ValueError as refresh_exc:
            raise HTTPException(
                status_code=400,
                detail={"message": str(refresh_exc)},
            ) from refresh_exc
        return _load_snapshot_or_404(name)


def _store_snapshot(name: str, payload: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> None:
    try:
        save_analysis_snapshot(name, payload, metadata=metadata)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc


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


@router.get(
    "",
    response_model=LottoAnalysisSnapshotResponse,
    summary="저장된 회차 기반 통계 분석 결과 조회",
)
def getLottoAnalysis() -> LottoAnalysisSnapshotResponse:
    snapshot = _ensure_snapshot("summary", refresh_lotto_summary)
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
        response = refresh_lotto_summary()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    return response


@router.get(
    "/dependency",
    response_model=DependencyAnalysisSnapshotResponse,
    summary="연속 회차 의존성 검정 결과",
)
def getLottoDependencyAnalysis() -> DependencyAnalysisSnapshotResponse:
    snapshot = _ensure_snapshot("dependency", refresh_dependency_analysis)
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
        response = refresh_dependency_analysis()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    return response


@router.get(
    "/runs/sum",
    response_model=SumRunsTestSnapshotResponse,
    summary="회차 합계 기반 런 검정",
)
def getLottoSumRunsTest() -> SumRunsTestSnapshotResponse:
    snapshot = _ensure_snapshot("runs_sum", refresh_runs_sum_analysis)
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
        response = refresh_runs_sum_analysis()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    return response


@router.get(
    "/patterns",
    response_model=PatternAnalysisSnapshotResponse,
    summary="홀짝/저고/끝자리 패턴 χ² 검정",
)
def getLottoPatternAnalysis() -> PatternAnalysisSnapshotResponse:
    snapshot = _ensure_snapshot("patterns", refresh_pattern_analysis)
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
        response = refresh_pattern_analysis()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

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
    key = analysis_key("distribution", sample_size=sample_size)
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
    key = analysis_key(
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
        try:
            refresh_randomness_suite(
                encoding=encoding,
                block_size=block_size,
                serial_block=serial_block,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
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
    try:
        return refresh_randomness_suite(
            encoding=encoding,
            block_size=block_size,
            serial_block=serial_block,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc


__all__ = ["router"]
