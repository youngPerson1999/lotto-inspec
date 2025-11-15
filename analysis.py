"""Statistical analysis helpers for Lotto draw data."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import accumulate
from math import comb, erfc, sqrt
from random import Random
from statistics import median
from typing import Dict, List, Sequence

from scipy import stats
from scipy.special import gammaincc

from app.services.lotto import LottoDraw, load_stored_draws

TOTAL_BALLS = 45
BALLS_PER_DRAW = 6
ODD_BALLS = 23
EVEN_BALLS = 22
LOW_BALLS = 22
HIGH_BALLS = 23
TOTAL_COMBINATIONS = comb(TOTAL_BALLS, BALLS_PER_DRAW)
DIGIT_COUNTS = Counter(num % 10 for num in range(1, TOTAL_BALLS + 1))
RANDOMNESS_ALPHA = 0.01
VALID_BIT_ENCODINGS = {"presence", "parity", "binary"}


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


@dataclass
class AutocorrelationLagResult:
    lag: int
    coefficient: float
    sample_size: int


@dataclass
class NumberAutocorrelationResult:
    number: int
    lags: List[AutocorrelationLagResult]
    ljung_box_q: float | None
    p_value: float | None


@dataclass
class CarryOverAnalysisResult:
    previous_hit_probability: float
    previous_miss_probability: float
    chi_square_statistic: float
    p_value: float
    contingency_table: List[List[int]]


@dataclass
class SumRunsTestResult(RunsTestResult):
    median_threshold: float


@dataclass
class PatternChiSquareResult:
    statistic: float
    p_value: float
    observed: Dict[str, int]
    expected: Dict[str, float]


@dataclass
class DistributionComparisonResult:
    chi_square_statistic: float
    chi_square_p_value: float
    ks_statistic: float
    ks_p_value: float
    observed_histogram: Dict[int, int]
    expected_histogram: Dict[int, float]


@dataclass
class RandomnessTestResult:
    name: str
    statistic: float | None
    p_value: float | None
    passed: bool
    detail: Dict[str, float] | None = None


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


def runs_test_on_sums(draws: Sequence[LottoDraw]) -> SumRunsTestResult:
    """회차 합계를 중앙값 기준 이진 시퀀스로 변환하여 런 검정."""

    sums = [sum(draw.numbers) for draw in draws]
    if len(sums) < 2:
        raise ValueError("At least two draws are required for sum runs test.")

    median_threshold = float(median(sums))
    sequence = [1 if draw_sum >= median_threshold else 0 for draw_sum in sums]

    runs = 1
    for prev, curr in zip(sequence, sequence[1:]):
        if prev != curr:
            runs += 1

    n1 = sum(sequence)
    n0 = len(sequence) - n1
    if n0 == 0 or n1 == 0:
        raise ValueError("Sequence must contain both sides of the median.")

    expected_runs = ((2 * n0 * n1) / (n0 + n1)) + 1
    variance = (
        (2 * n0 * n1 * (2 * n0 * n1 - n0 - n1))
        / (((n0 + n1) ** 2) * (n0 + n1 - 1))
    )
    z_score = (runs - expected_runs) / sqrt(variance)
    p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))

    return SumRunsTestResult(
        runs=runs,
        expected_runs=expected_runs,
        z_score=float(z_score),
        p_value=float(p_value),
        total_observations=len(sequence),
        median_threshold=median_threshold,
    )


def _binary_series_for_number(draws: Sequence[LottoDraw], number: int) -> List[int]:
    return [1 if number in draw.numbers else 0 for draw in draws]


def _autocorrelation(series: Sequence[int], lag: int) -> float | None:
    n = len(series)
    if lag <= 0 or lag >= n:
        return None

    mean = sum(series) / n
    numerator = 0.0
    for i in range(n - lag):
        numerator += (series[i] - mean) * (series[i + lag] - mean)

    denominator = sum((value - mean) ** 2 for value in series)
    if denominator == 0:
        return 0.0

    return numerator / denominator


def _ljung_box(
    series_length: int, lag_results: Sequence[AutocorrelationLagResult]
) -> tuple[float | None, float | None]:
    valid = [lag for lag in lag_results if series_length - lag.lag > 0]
    if not valid:
        return None, None

    q_stat = (
        series_length
        * (series_length + 2)
        * sum(
            (lag.coefficient**2) / (series_length - lag.lag)
            for lag in valid
            if series_length - lag.lag > 0
        )
    )
    p_value = stats.chi2.sf(q_stat, len(valid))
    return float(q_stat), float(p_value)


def number_autocorrelation(
    draws: Sequence[LottoDraw],
    max_lag: int = 5,
) -> List[NumberAutocorrelationResult]:
    if len(draws) < 2:
        raise ValueError("At least two draws are required for autocorrelation.")

    results: List[NumberAutocorrelationResult] = []
    for number in range(1, TOTAL_BALLS + 1):
        series = _binary_series_for_number(draws, number)
        lag_entries: List[AutocorrelationLagResult] = []
        for lag in range(1, max_lag + 1):
            coeff = _autocorrelation(series, lag)
            if coeff is None:
                continue
            lag_entries.append(
                AutocorrelationLagResult(
                    lag=lag,
                    coefficient=float(coeff),
                    sample_size=len(series) - lag,
                )
            )

        q_stat, p_value = _ljung_box(len(series), lag_entries)
        results.append(
            NumberAutocorrelationResult(
                number=number,
                lags=lag_entries,
                ljung_box_q=q_stat,
                p_value=p_value,
            )
        )
    return results


def carry_over_analysis(draws: Sequence[LottoDraw]) -> CarryOverAnalysisResult:
    if len(draws) < 2:
        raise ValueError("At least two draws are required for carry-over analysis.")

    prev_in_total = 0
    prev_in_success = 0
    prev_out_total = 0
    prev_out_success = 0

    for prev, curr in zip(draws, draws[1:]):
        prev_set = set(prev.numbers)
        curr_set = set(curr.numbers)

        prev_in_total += len(prev_set)
        prev_in_success += len(prev_set & curr_set)

        prev_out_total += TOTAL_BALLS - len(prev_set)
        prev_out_success += len(curr_set - prev_set)

    prev_in_fail = prev_in_total - prev_in_success
    prev_out_fail = prev_out_total - prev_out_success
    contingency = [
        [prev_in_success, prev_in_fail],
        [prev_out_success, prev_out_fail],
    ]

    chi2, p_value, _, _ = stats.chi2_contingency(contingency, correction=False)

    return CarryOverAnalysisResult(
        previous_hit_probability=(
            prev_in_success / prev_in_total if prev_in_total else 0.0
        ),
        previous_miss_probability=(
            prev_out_success / prev_out_total if prev_out_total else 0.0
        ),
        chi_square_statistic=float(chi2),
        p_value=float(p_value),
        contingency_table=contingency,
    )


def dependency_summary(max_lag: int = 5) -> Dict[str, object]:
    draws = load_stored_draws()
    if len(draws) < 2:
        raise ValueError("최소 2회 이상의 회차 데이터가 필요합니다. /lotto/sync를 실행하세요.")

    autocorr_results = number_autocorrelation(draws, max_lag=max_lag)
    carry_over = carry_over_analysis(draws)

    return {
        "autocorrelation": [
            {
                "number": entry.number,
                "ljung_box_q": entry.ljung_box_q,
                "p_value": entry.p_value,
                "lags": [
                    {
                        "lag": lag_result.lag,
                        "coefficient": lag_result.coefficient,
                        "sample_size": lag_result.sample_size,
                    }
                    for lag_result in entry.lags
                ],
            }
            for entry in autocorr_results
        ],
        "carry_over": {
            "previous_hit_probability": carry_over.previous_hit_probability,
            "previous_miss_probability": carry_over.previous_miss_probability,
            "chi_square_statistic": carry_over.chi_square_statistic,
            "p_value": carry_over.p_value,
            "contingency_table": carry_over.contingency_table,
        },
    }


def sum_runs_summary() -> SumRunsTestResult:
    draws = load_stored_draws()
    if len(draws) < 2:
        raise ValueError("최소 2회 이상의 회차가 필요합니다. /lotto/sync를 먼저 실행하세요.")
    return runs_test_on_sums(draws)


def _chi_square_from_dicts(
    observed: Dict[str, int], expected: Dict[str, float]
) -> tuple[float, float]:
    keys = list(expected.keys())
    observed_values = [observed.get(key, 0) for key in keys]
    expected_values = [expected[key] for key in keys]
    statistic, p_value = stats.chisquare(observed_values, expected_values)
    return float(statistic), float(p_value)


def parity_pattern_analysis(draws: Sequence[LottoDraw]) -> PatternChiSquareResult:
    if not draws:
        raise ValueError("No draws available for parity analysis.")

    counts: Counter[str] = Counter()
    for draw in draws:
        odd = sum(1 for num in draw.numbers if num % 2 == 1)
        key = f"{odd}:{BALLS_PER_DRAW - odd}"
        counts[key] += 1

    observed = {
        f"{odd}:{BALLS_PER_DRAW - odd}": counts.get(
            f"{odd}:{BALLS_PER_DRAW - odd}",
            0,
        )
        for odd in range(BALLS_PER_DRAW + 1)
    }
    expected: Dict[str, float] = {}
    for odd in range(BALLS_PER_DRAW + 1):
        ways = comb(ODD_BALLS, odd) * comb(EVEN_BALLS, BALLS_PER_DRAW - odd)
        probability = ways / TOTAL_COMBINATIONS
        key = f"{odd}:{BALLS_PER_DRAW - odd}"
        expected[key] = probability * len(draws)

    statistic, p_value = _chi_square_from_dicts(observed, expected)
    return PatternChiSquareResult(
        statistic=statistic,
        p_value=p_value,
        observed=observed,
        expected=expected,
    )


def low_high_pattern_analysis(draws: Sequence[LottoDraw]) -> PatternChiSquareResult:
    if not draws:
        raise ValueError("No draws available for low/high analysis.")

    counts: Counter[str] = Counter()
    for draw in draws:
        low = sum(1 for num in draw.numbers if num <= LOW_BALLS)
        key = f"{low}:{BALLS_PER_DRAW - low}"
        counts[key] += 1

    observed = {
        f"{low}:{BALLS_PER_DRAW - low}": counts.get(
            f"{low}:{BALLS_PER_DRAW - low}",
            0,
        )
        for low in range(BALLS_PER_DRAW + 1)
    }
    expected: Dict[str, float] = {}
    for low in range(BALLS_PER_DRAW + 1):
        ways = comb(LOW_BALLS, low) * comb(HIGH_BALLS, BALLS_PER_DRAW - low)
        probability = ways / TOTAL_COMBINATIONS
        key = f"{low}:{BALLS_PER_DRAW - low}"
        expected[key] = probability * len(draws)

    statistic, p_value = _chi_square_from_dicts(observed, expected)
    return PatternChiSquareResult(
        statistic=statistic,
        p_value=p_value,
        observed=observed,
        expected=expected,
    )


def last_digit_analysis(draws: Sequence[LottoDraw]) -> PatternChiSquareResult:
    if not draws:
        raise ValueError("No draws available for last digit analysis.")

    counts: Counter[str] = Counter()
    for draw in draws:
        for num in draw.numbers:
            counts[str(num % 10)] += 1

    observed = {str(digit): counts.get(str(digit), 0) for digit in range(10)}
    total_numbers = len(draws) * BALLS_PER_DRAW
    expected = {
        str(digit): (DIGIT_COUNTS[digit] / TOTAL_BALLS) * total_numbers
        for digit in range(10)
    }

    statistic, p_value = _chi_square_from_dicts(observed, expected)
    return PatternChiSquareResult(
        statistic=statistic,
        p_value=p_value,
        observed=observed,
        expected=expected,
    )


def pattern_analysis_summary() -> Dict[str, PatternChiSquareResult]:
    draws = load_stored_draws()
    if not draws:
        raise ValueError("No draws available. Run /lotto/sync first.")

    return {
        "parity": parity_pattern_analysis(draws),
        "low_high": low_high_pattern_analysis(draws),
        "last_digit": last_digit_analysis(draws),
    }


def _simulate_reference_draws(
    sample_size: int,
    seed: int | None = None,
) -> tuple[
    List[int],
    Counter[int],
    List[int],
    Counter[int],
]:
    rng = Random(seed)
    population = list(range(1, TOTAL_BALLS + 1))
    sum_samples: List[int] = []
    sum_hist: Counter[int] = Counter()
    gap_samples: List[int] = []
    gap_hist: Counter[int] = Counter()

    for _ in range(sample_size):
        draw = sorted(rng.sample(population, BALLS_PER_DRAW))
        draw_sum = sum(draw)
        sum_samples.append(draw_sum)
        sum_hist[draw_sum] += 1

        for prev, curr in zip(draw, draw[1:]):
            gap = curr - prev
            gap_samples.append(gap)
            gap_hist[gap] += 1

    return sum_samples, sum_hist, gap_samples, gap_hist


def _scale_simulated_hist(
    simulated_hist: Counter[int],
    simulated_total: int,
    observed_total: int,
) -> Dict[int, float]:
    if simulated_total == 0:
        raise ValueError("Simulated histogram total cannot be zero.")

    scaled: Dict[int, float] = {}
    for key, sim_count in simulated_hist.items():
        scaled[key] = (sim_count / simulated_total) * observed_total
    return scaled


def _chi_square_from_histograms(
    observed: Counter[int],
    expected_scaled: Dict[int, float],
) -> tuple[float, float, Dict[int, int], Dict[int, float]]:
    keys = sorted(set(observed.keys()) | set(expected_scaled.keys()))

    observed_hist = {key: observed.get(key, 0) for key in keys}
    expected_hist = {
        key: max(expected_scaled.get(key, 0.0), 1e-9) for key in keys
    }

    statistic, p_value = stats.chisquare(
        f_obs=[observed_hist[key] for key in keys],
        f_exp=[expected_hist[key] for key in keys],
    )
    return float(statistic), float(p_value), observed_hist, expected_hist


def sum_distribution_analysis(
    draws: Sequence[LottoDraw],
    sample_size: int = 100_000,
    simulated: tuple[List[int], Counter[int]] | None = None,
) -> DistributionComparisonResult:
    actual_sums = [sum(draw.numbers) for draw in draws]
    observed_hist = Counter(actual_sums)

    if simulated is None:
        simulated_sums, simulated_hist, _, _ = _simulate_reference_draws(
            sample_size=sample_size
        )
    else:
        simulated_sums, simulated_hist = simulated

    expected_scaled = _scale_simulated_hist(
        simulated_hist,
        simulated_total=len(simulated_sums),
        observed_total=len(actual_sums),
    )
    chi2, p_value, observed, expected = _chi_square_from_histograms(
        observed_hist,
        expected_scaled,
    )
    ks_stat, ks_p = stats.ks_2samp(actual_sums, simulated_sums)

    return DistributionComparisonResult(
        chi_square_statistic=chi2,
        chi_square_p_value=p_value,
        ks_statistic=float(ks_stat),
        ks_p_value=float(ks_p),
        observed_histogram=observed,
        expected_histogram=expected,
    )


def gap_distribution_analysis(
    draws: Sequence[LottoDraw],
    sample_size: int = 100_000,
    simulated: tuple[List[int], Counter[int]] | None = None,
) -> DistributionComparisonResult:
    observed_gaps: List[int] = []
    observed_hist: Counter[int] = Counter()
    for draw in draws:
        sorted_numbers = sorted(draw.numbers)
        for prev, curr in zip(sorted_numbers, sorted_numbers[1:]):
            gap = curr - prev
            observed_gaps.append(gap)
            observed_hist[gap] += 1

    if simulated is None:
        _, _, simulated_gaps, simulated_hist = _simulate_reference_draws(
            sample_size=sample_size
        )
    else:
        simulated_gaps, simulated_hist = simulated

    expected_scaled = _scale_simulated_hist(
        simulated_hist,
        simulated_total=len(simulated_gaps),
        observed_total=len(observed_gaps),
    )
    chi2, p_value, observed, expected = _chi_square_from_histograms(
        observed_hist,
        expected_scaled,
    )
    ks_stat, ks_p = stats.ks_2samp(observed_gaps, simulated_gaps)

    return DistributionComparisonResult(
        chi_square_statistic=chi2,
        chi_square_p_value=p_value,
        ks_statistic=float(ks_stat),
        ks_p_value=float(ks_p),
        observed_histogram=observed,
        expected_histogram=expected,
    )


def distribution_summary(sample_size: int = 100_000) -> Dict[str, DistributionComparisonResult]:
    draws = load_stored_draws()
    if not draws:
        raise ValueError("No draws available. Run /lotto/sync first.")

    (
        simulated_sums,
        simulated_sum_hist,
        simulated_gaps,
        simulated_gap_hist,
    ) = _simulate_reference_draws(sample_size=sample_size)

    return {
        "sum": sum_distribution_analysis(
            draws,
            sample_size=sample_size,
            simulated=(simulated_sums, simulated_sum_hist),
        ),
        "gap": gap_distribution_analysis(
            draws,
            sample_size=sample_size,
            simulated=(simulated_gaps, simulated_gap_hist),
        ),
    }


def _bit_sequence_from_draws(
    draws: Sequence[LottoDraw],
    encoding: str,
) -> List[int]:
    if encoding not in VALID_BIT_ENCODINGS:
        raise ValueError(
            f"지원하지 않는 인코딩 모드입니다: {encoding}. "
            f"허용값: {sorted(VALID_BIT_ENCODINGS)}",
        )

    bits: List[int] = []
    if encoding == "presence":
        for draw in draws:
            present = set(draw.numbers)
            for number in range(1, TOTAL_BALLS + 1):
                bits.append(1 if number in present else 0)
    elif encoding == "parity":
        for draw in draws:
            bits.extend(1 if num % 2 else 0 for num in draw.numbers)
    elif encoding == "binary":
        for draw in draws:
            for num in draw.numbers:
                for bit in f"{num:06b}":
                    bits.append(int(bit))
    return bits


def _frequency_monobit_test(bits: Sequence[int]) -> RandomnessTestResult:
    n = len(bits)
    if n < 100:
        raise ValueError("Monobit frequency test requires at least 100 bits.")

    s_obs = abs(sum(1 if bit else -1 for bit in bits)) / sqrt(n)
    p_value = erfc(s_obs / sqrt(2))
    return RandomnessTestResult(
        name="monobit_frequency",
        statistic=s_obs,
        p_value=float(p_value),
        passed=p_value >= RANDOMNESS_ALPHA,
        detail={"n": float(n)},
    )


def _block_frequency_test(bits: Sequence[int], block_size: int) -> RandomnessTestResult:
    n = len(bits)
    if block_size <= 0:
        raise ValueError("Block size must be positive.")
    num_blocks = n // block_size
    if num_blocks == 0:
        raise ValueError("Bit sequence length must exceed block size.")

    chi_square = 0.0
    for block_index in range(num_blocks):
        block = bits[block_index * block_size : (block_index + 1) * block_size]
        pi = sum(block) / block_size
        chi_square += (pi - 0.5) ** 2
    chi_square *= 4 * block_size
    p_value = gammaincc(num_blocks / 2, chi_square / 2)
    return RandomnessTestResult(
        name="block_frequency",
        statistic=chi_square,
        p_value=float(p_value),
        passed=p_value >= RANDOMNESS_ALPHA,
        detail={"num_blocks": float(num_blocks), "block_size": float(block_size)},
    )


def _runs_test(bits: Sequence[int]) -> RandomnessTestResult:
    n = len(bits)
    if n < 100:
        raise ValueError("Runs test requires at least 100 bits.")

    pi = sum(bits) / n
    tau = 2 / sqrt(n)
    if abs(pi - 0.5) >= tau:
        return RandomnessTestResult(
            name="runs",
            statistic=None,
            p_value=0.0,
            passed=False,
            detail={"pi": pi, "tau": tau},
        )

    Vn = 1
    for prev, curr in zip(bits, bits[1:]):
        if prev != curr:
            Vn += 1

    numerator = abs(Vn - 2 * n * pi * (1 - pi))
    denominator = 2 * sqrt(2 * n) * pi * (1 - pi)
    p_value = erfc(numerator / denominator)
    return RandomnessTestResult(
        name="runs",
        statistic=float(Vn),
        p_value=float(p_value),
        passed=p_value >= RANDOMNESS_ALPHA,
        detail={"pi": pi, "tau": tau},
    )


def _psi2(bits: Sequence[int], m: int) -> float:
    n = len(bits)
    if m == 0 or n == 0:
        return 0.0

    frequency: Counter[tuple[int, ...]] = Counter()
    extended = list(bits) + list(bits[: m - 1])
    for i in range(n):
        block = tuple(extended[i : i + m])
        frequency[block] += 1

    total = sum(count**2 for count in frequency.values())
    return (total * (2**m) / n) - n


def _serial_test(bits: Sequence[int], m: int) -> RandomnessTestResult:
    if m < 2:
        raise ValueError("Serial test requires m >= 2.")
    n = len(bits)
    if n < m:
        raise ValueError("Bit sequence too short for serial test.")

    psi_m = _psi2(bits, m)
    psi_m1 = _psi2(bits, m - 1)
    psi_m2 = _psi2(bits, m - 2)

    delta1 = psi_m - psi_m1
    delta2 = psi_m - 2 * psi_m1 + psi_m2

    p_value1 = gammaincc(2 ** (m - 1) / 2, delta1 / 2)
    p_value2 = gammaincc(2 ** (m - 2) / 2, delta2 / 2)

    passed = (p_value1 >= RANDOMNESS_ALPHA) and (p_value2 >= RANDOMNESS_ALPHA)
    return RandomnessTestResult(
        name=f"serial_m{m}",
        statistic=float(delta1),
        p_value=float(p_value1),
        passed=passed,
        detail={
            "p_value2": float(p_value2),
            "delta2": float(delta2),
        },
    )


def _cumulative_sums_p_value(partial_sums: Sequence[int]) -> float:
    n = len(partial_sums)
    if n == 0:
        return 1.0

    z = max(abs(value) for value in partial_sums)
    if z == 0:
        return 1.0

    sqrt_n = sqrt(n)

    def _range_sum(start: int, end: int, offset: int) -> float:
        total = 0.0
        for k in range(start, end + 1):
            term1 = ((4 * k + offset) * z) / sqrt_n
            term2 = ((4 * k + offset - 2) * z) / sqrt_n
            total += stats.norm.cdf(term1) - stats.norm.cdf(term2)
        return total

    start_k = int(((-n / z) + 1) / 4)
    end_k = int(((n / z) - 1) / 4)
    sum1 = _range_sum(start_k, end_k, 1) if start_k <= end_k else 0.0

    start_k = int(((-n / z) - 3) / 4)
    end_k = int(((n / z) - 1) / 4)
    sum2 = _range_sum(start_k, end_k, 3) if start_k <= end_k else 0.0

    return 1.0 - sum1 + sum2


def _cumulative_sums_test(bits: Sequence[int]) -> RandomnessTestResult:
    n = len(bits)
    if n < 100:
        raise ValueError("Cumulative sums test requires at least 100 bits.")

    adjusted = [1 if bit else -1 for bit in bits]
    forward_sums = list(accumulate(adjusted))
    backward_sums = list(accumulate(reversed(adjusted)))

    p_forward = _cumulative_sums_p_value(forward_sums)
    p_backward = _cumulative_sums_p_value(backward_sums)
    passed = (p_forward >= RANDOMNESS_ALPHA) and (p_backward >= RANDOMNESS_ALPHA)

    return RandomnessTestResult(
        name="cumulative_sums",
        statistic=max(abs(value) for value in forward_sums),
        p_value=min(p_forward, p_backward),
        passed=passed,
        detail={
            "p_value_forward": float(p_forward),
            "p_value_backward": float(p_backward),
        },
    )


def randomness_test_suite(
    bits: Sequence[int],
    block_size: int = 128,
    serial_block: int = 2,
) -> List[RandomnessTestResult]:
    return [
        _frequency_monobit_test(bits),
        _block_frequency_test(bits, block_size=block_size),
        _runs_test(bits),
        _serial_test(bits, m=serial_block),
        _cumulative_sums_test(bits),
    ]


def randomness_suite_summary(
    encoding: str = "presence",
    block_size: int = 128,
    serial_block: int = 2,
) -> Dict[str, object]:
    draws = load_stored_draws()
    if not draws:
        raise ValueError("No draws available. Run /lotto/sync first.")

    bits = _bit_sequence_from_draws(draws, encoding=encoding)
    if len(bits) < 100:
        raise ValueError("난수 검정을 위해 최소 100비트 이상 필요합니다.")

    tests = randomness_test_suite(
        bits,
        block_size=block_size,
        serial_block=serial_block,
    )

    return {
        "encoding": encoding,
        "total_bits": len(bits),
        "tests": [
            {
                "name": result.name,
                "statistic": result.statistic,
                "p_value": result.p_value,
                "passed": result.passed,
                "detail": result.detail,
            }
            for result in tests
        ],
    }
