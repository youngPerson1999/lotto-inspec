"""Utilities to refresh analysis snapshots programmatically."""

from __future__ import annotations

from typing import Any, Dict

from analysis import (
    dependency_summary,
    pattern_analysis_summary,
    randomness_suite_summary,
    sum_runs_summary,
    summarize_draws,
)
from app.models.dto import (
    DependencyAnalysisResponse,
    LottoAnalysisResponse,
    PatternAnalysisResponse,
    RandomnessSuiteResponse,
    SumRunsTestResponse,
)
from app.services.analysis_storage import save_analysis_snapshot


def analysis_key(base: str, **params: Any) -> str:
    if not params:
        return base
    suffix = ",".join(f"{key}={params[key]}" for key in sorted(params))
    return f"{base}|{suffix}"


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


def refresh_lotto_summary() -> LottoAnalysisResponse:
    summary = summarize_draws()
    response = _build_lotto_analysis_response(summary)
    save_analysis_snapshot("summary", response.model_dump())
    return response


def refresh_dependency_analysis() -> DependencyAnalysisResponse:
    summary = dependency_summary()
    response = DependencyAnalysisResponse(**summary)
    save_analysis_snapshot("dependency", response.model_dump())
    return response


def refresh_runs_sum_analysis() -> SumRunsTestResponse:
    result = sum_runs_summary()
    response = SumRunsTestResponse(
        runs=result.runs,
        expected_runs=result.expected_runs,
        z_score=result.z_score,
        p_value=result.p_value,
        total_observations=result.total_observations,
        median_threshold=result.median_threshold,
    )
    save_analysis_snapshot("runs_sum", response.model_dump())
    return response


def refresh_pattern_analysis() -> PatternAnalysisResponse:
    summary = pattern_analysis_summary()
    response = PatternAnalysisResponse(
        parity=_serialize_pattern_result(summary["parity"]),
        low_high=_serialize_pattern_result(summary["low_high"]),
        last_digit=_serialize_pattern_result(summary["last_digit"]),
    )
    save_analysis_snapshot("patterns", response.model_dump())
    return response


def refresh_randomness_suite(
    *,
    encoding: str,
    block_size: int,
    serial_block: int,
) -> RandomnessSuiteResponse:
    summary = randomness_suite_summary(
        encoding=encoding,
        block_size=block_size,
        serial_block=serial_block,
    )
    response = RandomnessSuiteResponse(**summary)
    key = analysis_key(
        "randomness",
        encoding=encoding,
        block_size=block_size,
        serial_block=serial_block,
    )
    save_analysis_snapshot(
        key,
        response.model_dump(),
        metadata={
            "encoding": encoding,
            "block_size": block_size,
            "serial_block": serial_block,
        },
    )
    return response


__all__ = [
    "analysis_key",
    "refresh_dependency_analysis",
    "refresh_lotto_summary",
    "refresh_pattern_analysis",
    "refresh_randomness_suite",
    "refresh_runs_sum_analysis",
]
