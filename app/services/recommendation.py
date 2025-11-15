"""Recommendation helpers for Lotto numbers."""

from __future__ import annotations

from datetime import datetime, timezone
from secrets import SystemRandom
from typing import Callable, Dict, List, Optional, Tuple

from analysis import calculate_number_frequencies
from app.core.config import get_settings
from app.core.db import get_mongo_client
from app.services.lotto import (
    LottoDraw,
    get_latest_stored_draw,
    load_stored_draws,
)

_RNG = SystemRandom()


class RecommendationError(ValueError):
    """Raised when recommendations cannot be generated."""


def _ensure_draws() -> Tuple[List[LottoDraw], int]:
    draws = load_stored_draws()
    if not draws:
        raise RecommendationError("저장된 회차가 없습니다. 먼저 /lotto/sync를 실행하세요.")
    return draws, draws[-1].draw_no


def _latest_draw_no() -> Optional[int]:
    latest = get_latest_stored_draw()
    return latest.draw_no if latest else None


def _frequency_table(draws: List[LottoDraw]) -> Dict[int, int]:
    return calculate_number_frequencies(draws)


def recommend_random(draw_no: int | None = None) -> Dict[str, object]:
    numbers = sorted(_RNG.sample(range(1, 46), 6))
    return {
        "strategy": "random",
        "numbers": numbers,
        "explanation": "45개 중 6개를 균등 확률로 무작위 추천했습니다.",
        "draw_no": draw_no,
    }


def recommend_frequency_hot(_: int | None = None) -> Dict[str, object]:
    draws, draw_no = _ensure_draws()
    freq = _frequency_table(draws)
    top = sorted(freq.items(), key=lambda item: (-item[1], item[0]))[:6]
    numbers = sorted(num for num, _ in top)
    return {
        "strategy": "frequency_hot",
        "numbers": numbers,
        "explanation": "최근까지 가장 자주 등장한 번호 Top 6 조합입니다.",
        "draw_no": draw_no,
    }


def recommend_frequency_cold(_: int | None = None) -> Dict[str, object]:
    draws, draw_no = _ensure_draws()
    freq = _frequency_table(draws)
    bottom = sorted(freq.items(), key=lambda item: (item[1], item[0]))[:6]
    numbers = sorted(num for num, _ in bottom)
    return {
        "strategy": "frequency_cold",
        "numbers": numbers,
        "explanation": "오랫동안 잘 나오지 않은 번호 6개를 골랐습니다.",
        "draw_no": draw_no,
    }


def recommend_balanced_parity(_: int | None = None) -> Dict[str, object]:
    draws, draw_no = _ensure_draws()
    freq = _frequency_table(draws)

    odds = sorted(
        ((num, count) for num, count in freq.items() if num % 2 == 1),
        key=lambda item: (-item[1], item[0]),
    )
    evens = sorted(
        ((num, count) for num, count in freq.items() if num % 2 == 0),
        key=lambda item: (-item[1], item[0]),
    )
    if len(odds) < 3 or len(evens) < 3:
        raise RecommendationError("짝수/홀수 데이터가 충분하지 않습니다.")

    numbers = sorted([num for num, _ in odds[:3]] + [num for num, _ in evens[:3]])
    return {
        "strategy": "balanced_parity",
        "numbers": numbers,
        "explanation": "최근 빈도를 기반으로 짝수 3개/홀수 3개 균형 조합을 추천합니다.",
        "draw_no": draw_no,
    }


StrategyHandler = Callable[[Optional[int]], Dict[str, object]]

STRATEGIES: Dict[str, StrategyHandler] = {
    "random": recommend_random,
    "frequency_hot": recommend_frequency_hot,
    "frequency_cold": recommend_frequency_cold,
    "balanced_parity": recommend_balanced_parity,
}


def _recommendation_collection():
    settings = get_settings()
    if not settings.use_mongo_storage:
        return None
    client = get_mongo_client()
    collection = client[settings.mongo_db_name][
        settings.mongo_recommendation_collection_name
    ]
    collection.create_index([("strategy", 1), ("draw_no", 1)], unique=True)
    return collection


def _cache_lookup(strategy: str, draw_no: int | None) -> Optional[Dict[str, object]]:
    collection = _recommendation_collection()
    if collection is None:
        return None
    document = collection.find_one({"strategy": strategy, "draw_no": draw_no})
    if not document:
        return None
    return document["result"]


def _cache_store(strategy: str, draw_no: int | None, result: Dict[str, object]) -> None:
    collection = _recommendation_collection()
    if collection is None:
        return
    collection.update_one(
        {"strategy": strategy, "draw_no": draw_no},
        {
            "$set": {
                "result": result,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


def _run_strategy(strategy: str, draw_no: int | None) -> Dict[str, object]:
    handler = STRATEGIES.get(strategy)
    if not handler:
        available = ", ".join(sorted(STRATEGIES))
        raise RecommendationError(
            f"지원하지 않는 전략입니다: {strategy} (가능: {available})"
        )
    return handler(draw_no)


def get_recommendation(strategy: str) -> Dict[str, object]:
    draw_no = _latest_draw_no()
    cached = _cache_lookup(strategy, draw_no)
    if cached:
        return cached

    result = _run_strategy(strategy, draw_no)
    _cache_store(strategy, draw_no, result)
    return result


def get_all_recommendations() -> List[Dict[str, object]]:
    draw_no = _latest_draw_no()
    results: List[Dict[str, object]] = []
    for strategy in sorted(STRATEGIES):
        cached = _cache_lookup(strategy, draw_no)
        if cached:
            results.append(cached)
            continue
        result = _run_strategy(strategy, draw_no)
        _cache_store(strategy, draw_no, result)
        results.append(result)
    return results


__all__ = [
    "get_recommendation",
    "get_all_recommendations",
    "RecommendationError",
    "STRATEGIES",
]
