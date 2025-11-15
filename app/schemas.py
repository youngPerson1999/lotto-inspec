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


class AutocorrelationLagResponse(BaseModel):
    lag: int = Field(..., description="시차 (lag)")
    coefficient: float = Field(..., description="자기상관 계수")
    sample_size: int = Field(..., description="계산에 사용된 표본 수")


class NumberAutocorrelationResponse(BaseModel):
    number: int = Field(..., description="분석 대상 번호 (1~45)")
    lags: List[AutocorrelationLagResponse] = Field(
        ..., description="lag별 자기상관 결과"
    )
    ljung_box_q: float | None = Field(
        None,
        description="Ljung-Box Q 통계량 (lag 전체 기반)",
    )
    p_value: float | None = Field(
        None,
        description="Ljung-Box 독립성 검정 p-value",
    )


class CarryOverDependencyResponse(BaseModel):
    previous_hit_probability: float = Field(
        ...,
        description="직전 회차에 나왔던 번호의 재등장 비율",
    )
    previous_miss_probability: float = Field(
        ...,
        description="직전 회차에 없었던 번호의 등장 비율",
    )
    chi_square_statistic: float = Field(
        ..., description="2x2 독립성 검정 카이제곱 통계량"
    )
    p_value: float = Field(..., description="카이제곱 독립성 검정 p-value")
    contingency_table: List[List[int]] = Field(
        ...,
        description="[[직전 등장·이번 등장, 직전 등장·이번 미등장], [직전 미등장·이번 등장, 직전 미등장·이번 미등장]]",
    )


class DependencyAnalysisResponse(BaseModel):
    autocorrelation: List[NumberAutocorrelationResponse] = Field(
        ..., description="번호별 자기상관 및 Ljung-Box 결과"
    )
    carry_over: CarryOverDependencyResponse = Field(
        ..., description="직전 회차 등장 여부에 따른 비율 비교"
    )


class SumRunsTestResponse(BaseModel):
    runs: int = Field(..., description="관측된 런 수")
    expected_runs: float = Field(..., description="기대 런 수")
    z_score: float = Field(..., description="Z 점수")
    p_value: float = Field(..., description="런 검정 p-value")
    total_observations: int = Field(..., description="시퀀스 길이")
    median_threshold: float = Field(
        ..., description="합계 시퀀스 이진화를 위한 중앙값 임계치"
    )


class PatternChiSquareResponse(BaseModel):
    statistic: float = Field(..., description="카이제곱 통계량")
    p_value: float = Field(..., description="p-value")
    observed: Dict[str, int] = Field(
        ..., description="카테고리별 관측 빈도", example={"3:3": 100}
    )
    expected: Dict[str, float] = Field(
        ..., description="카테고리별 기대 빈도", example={"3:3": 95.4}
    )


class PatternAnalysisResponse(BaseModel):
    parity: PatternChiSquareResponse = Field(
        ..., description="홀짝 조합 빈도에 대한 χ² 결과 (odd:even)"
    )
    low_high: PatternChiSquareResponse = Field(
        ..., description="저(1~22)/고(23~45) 조합 χ² 결과 (low:high)"
    )
    last_digit: PatternChiSquareResponse = Field(
        ..., description="번호 일의자리(0~9) 분포 χ² 결과"
    )


class DistributionComparisonResponse(BaseModel):
    chi_square_statistic: float = Field(..., description="χ² 통계량")
    chi_square_p_value: float = Field(..., description="χ² p-value")
    ks_statistic: float = Field(..., description="Kolmogorov-Smirnov 통계량")
    ks_p_value: float = Field(..., description="KS p-value")
    observed_histogram: Dict[str, float] = Field(
        ..., description="실제 데이터 히스토그램 (키는 합계 혹은 간격)"
    )
    expected_histogram: Dict[str, float] = Field(
        ..., description="시뮬레이션 기반 기대 히스토그램"
    )


class DistributionAnalysisResponse(BaseModel):
    sum: DistributionComparisonResponse = Field(
        ..., description="회차 합계 분포 비교 결과"
    )
    gap: DistributionComparisonResponse = Field(
        ..., description="번호 간 간격 분포 비교 결과"
    )


class RandomnessTestResultResponse(BaseModel):
    name: str = Field(..., description="검정 이름")
    statistic: float | None = Field(
        None,
        description="검정 통계량 (해당되는 경우)",
    )
    p_value: float | None = Field(
        None,
        description="주요 p-value",
    )
    passed: bool = Field(..., description="유의수준 1% 기준 통과 여부")
    detail: Dict[str, float] | None = Field(
        None,
        description="추가 파생 값 (2차 p-value 등)",
    )


class RandomnessSuiteResponse(BaseModel):
    encoding: str = Field(..., description="비트열 인코딩 모드")
    total_bits: int = Field(..., description="생성된 전체 비트 수")
    tests: List[RandomnessTestResultResponse] = Field(
        ..., description="실행된 난수 검정 결과 목록"
    )


class LottoAnalysisSnapshotResponse(BaseModel):
    draw_no: int = Field(..., description="분석에 사용된 마지막 회차 번호")
    result: LottoAnalysisResponse


class DependencyAnalysisSnapshotResponse(BaseModel):
    draw_no: int = Field(..., description="분석에 사용된 마지막 회차 번호")
    result: DependencyAnalysisResponse


class SumRunsTestSnapshotResponse(BaseModel):
    draw_no: int = Field(..., description="분석에 사용된 마지막 회차 번호")
    result: SumRunsTestResponse


class PatternAnalysisSnapshotResponse(BaseModel):
    draw_no: int = Field(..., description="분석에 사용된 마지막 회차 번호")
    result: PatternAnalysisResponse


class RandomnessSuiteSnapshotResponse(BaseModel):
    draw_no: int = Field(..., description="분석에 사용된 마지막 회차 번호")
    result: RandomnessSuiteResponse


class RecommendationResponse(BaseModel):
    strategy: str = Field(..., description="사용된 추천 전략 키")
    numbers: List[int] = Field(
        ...,
        description="추천된 번호 6개",
        min_length=6,
        max_length=6,
    )
    explanation: str = Field(..., description="추천 근거 또는 설명")
    draw_no: int | None = Field(
        None,
        description="추천이 기반한 최신 회차 (존재하지 않을 수도 있음)",
    )
