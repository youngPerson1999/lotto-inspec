"""Statistical analysis helpers for Lotto draw data."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import sqrt
from typing import Dict, List, Sequence

from scipy import stats

from lottery import LottoDraw, load_stored_draws

TOTAL_BALLS = 45
BALLS_PER_DRAW = 6


@dataclass
class ChiSquareResult:
    statistic: float
    p_value: float
    observed: List[int]
    expected: List[float]


@dataclass
class RunsTestResult:
    runs: int
    expected_runs: float
    z_score: float
    p_value: float
    total_observations: int


def _flatten_numbers(draws: Sequence[LottoDraw]) -> List[int]:
    numbers: List[int] = []
    for draw in draws:
        numbers.extend(draw.numbers)
    return numbers


def calculate_number_frequencies(draws: Sequence[LottoDraw]) -> Dict[int, int]:
    """Count how many times each number (1~45) appears."""

    counts = Counter()
    for number in _flatten_numbers(draws):
        counts[number] += 1

    for num in range(1, TOTAL_BALLS + 1):
        counts.setdefault(num, 0)

    return dict(sorted(counts.items()))


def chi_square_uniformity_test(draws: Sequence[LottoDraw]) -> ChiSquareResult:
    """Chi-square goodness-of-fit test against a uniform distribution."""

    if not draws:
        raise ValueError("No draw data available for chi-square test.")

    frequencies = calculate_number_frequencies(draws)
    observed = [frequencies[num] for num in range(1, TOTAL_BALLS + 1)]
    total_observations = len(draws) * BALLS_PER_DRAW
    expected_count = total_observations / TOTAL_BALLS
    expected = [expected_count] * TOTAL_BALLS

    statistic, p_value = stats.chisquare(f_obs=observed, f_exp=expected)

    return ChiSquareResult(
        statistic=float(statistic),
        p_value=float(p_value),
        observed=observed,
        expected=expected,
    )


def runs_test_even_odd(draws: Sequence[LottoDraw]) -> RunsTestResult:
    """Runs test on the parity sequence (even vs odd)."""

    sequence = [num % 2 for num in _flatten_numbers(draws)]
    if len(sequence) < 2:
        raise ValueError("At least two numbers are required for the runs test.")

    runs = 1
    for prev, curr in zip(sequence, sequence[1:]):
        if prev != curr:
            runs += 1

    n1 = sum(sequence)  # count of odd numbers (1s)
    n0 = len(sequence) - n1  # evens

    if n0 == 0 or n1 == 0:
        raise ValueError("Parity sequence must contain both even and odd numbers.")

    expected_runs = ((2 * n0 * n1) / (n0 + n1)) + 1
    variance = (
        (2 * n0 * n1 * (2 * n0 * n1 - n0 - n1))
        / (((n0 + n1) ** 2) * (n0 + n1 - 1))
    )
    z_score = (runs - expected_runs) / sqrt(variance)
    p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))

    return RunsTestResult(
        runs=runs,
        expected_runs=expected_runs,
        z_score=float(z_score),
        p_value=float(p_value),
        total_observations=len(sequence),
    )


def gap_histogram(draws: Sequence[LottoDraw]) -> Dict[int, int]:
    """Histogram of gaps between sorted numbers within each draw."""

    histogram: Counter[int] = Counter()
    for draw in draws:
        sorted_numbers = sorted(draw.numbers)
        for prev, curr in zip(sorted_numbers, sorted_numbers[1:]):
            histogram[curr - prev] += 1
    return dict(sorted(histogram.items()))


def summarize_draws() -> Dict[str, object]:
    """Convenience helper returning common analysis outputs."""

    draws = load_stored_draws()
    if not draws:
        raise ValueError("No draws found locally. Run /lotto/sync first.")

    chi_square = chi_square_uniformity_test(draws)
    runs = runs_test_even_odd(draws)

    return {
        "total_draws": len(draws),
        "chi_square": chi_square,
        "runs_test": runs,
        "gap_histogram": gap_histogram(draws),
        "frequency": calculate_number_frequencies(draws),
    }
