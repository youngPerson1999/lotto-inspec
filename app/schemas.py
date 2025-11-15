"""Pydantic schemas shared by the FastAPI endpoints."""

from typing import Dict, List

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="서버 상태 플래그 (ok)")


class LottoDrawResponse(BaseModel):
    draw_no: int = Field(..., description="회차 번호")
    draw_date: str = Field(..., description="추첨 날짜 (YYYY-MM-DD)")
    numbers: List[int] = Field(
        ...,
        description="당첨 번호 6개 (오름차순이 아닐 수 있음)",
        min_length=6,
        max_length=6,
    )
    bonus: int = Field(..., description="보너스 번호")


class LottoSyncResponse(BaseModel):
    previous_max: int = Field(
        ..., description="동기화 전 마지막 저장 회차 (없으면 0)"
    )
    latest: int = Field(..., description="DhLottery 기준 최신 회차")
    inserted: int = Field(..., description="이번 동기화로 새로 추가된 회차 수")
    draws: List[LottoDrawResponse] = Field(
        ...,
        description="추가된 회차 목록 (최신 순서)",
    )


class ChiSquareAnalysisResponse(BaseModel):
    statistic: float = Field(..., description="카이제곱 통계량")
    p_value: float = Field(..., description="균등분포 가설의 p-value")
    observed: List[int] = Field(
        ..., description="번호별 관측 빈도 (1~45)", min_length=45, max_length=45
    )
    expected: List[float] = Field(
        ..., description="번호별 기대 빈도 (1~45)", min_length=45, max_length=45
    )


class RunsTestAnalysisResponse(BaseModel):
    runs: int = Field(..., description="실제 관측된 런 수")
    expected_runs: float = Field(..., description="기대되는 런 수")
    z_score: float = Field(..., description="Z 점수")
    p_value: float = Field(..., description="런 검정 p-value")
    total_observations: int = Field(..., description="전체 관측값 개수")


class LottoAnalysisResponse(BaseModel):
    total_draws: int = Field(..., description="저장된 회차 총 개수")
    chi_square: ChiSquareAnalysisResponse = Field(
        ..., description="번호 균등분포 카이제곱 검정 결과"
    )
    runs_test: RunsTestAnalysisResponse = Field(
        ..., description="짝/홀 패리티 시퀀스 런 검정 결과"
    )
    gap_histogram: Dict[int, int] = Field(
        ..., description="개별 회차 내 번호 간 간격 히스토그램"
    )
    frequency: Dict[int, int] = Field(
        ..., description="번호별 출현 빈도 (1~45)"
    )


class StorageHealthResponse(BaseModel):
    backend: str = Field(..., description="현재 사용 중인 저장 백엔드 (file/mongo)")
    connected: bool = Field(..., description="백엔드 연결 성공 여부")
    message: str = Field(..., description="상세 상태 메시지")
    total_draws: int | None = Field(
        None,
        description="MongoDB 사용 시 추정된 저장 회차 수",
    )
