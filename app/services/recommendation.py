"""Recommendation helpers for Lotto numbers."""

from __future__ import annotations

from datetime import datetime, timezone
from secrets import SystemRandom
from typing import Callable, Dict, List, Optional, Tuple

from pymongo import ReturnDocument

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from analysis import calculate_number_frequencies
from app.core.config import get_settings
from app.core.db import get_mongo_client
from app.services.lotto import (
    LottoDraw,
    evaluate_ticket,
    fetch_draw_info,
    fetch_latest_draw_info,
    get_latest_stored_draw,
    get_stored_draw,
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


def _recommendation_draw_no() -> Optional[int]:
    latest_stored = _latest_draw_no()
    latest_remote = _latest_remote_draw_no()

    latest_known = None
    if latest_stored is not None and latest_remote is not None:
        latest_known = max(latest_stored, latest_remote)
    elif latest_stored is not None:
        latest_known = latest_stored
    elif latest_remote is not None:
        latest_known = latest_remote

    return latest_known + 1 if latest_known is not None else None


def _latest_known_draw_no() -> Optional[int]:
    latest_stored = _latest_draw_no()
    latest_remote = _latest_remote_draw_no()

    if latest_stored is not None and latest_remote is not None:
        return max(latest_stored, latest_remote)
    if latest_stored is not None:
        return latest_stored
    if latest_remote is not None:
        return latest_remote
    return None


def _latest_remote_draw_no() -> Optional[int]:
    try:
        return fetch_latest_draw_info().draw_no
    except ValueError:
        return None


def _frequency_table(draws: List[LottoDraw]) -> Dict[int, int]:
    return calculate_number_frequencies(draws)


def _resolve_target_draw_no(draw_no: int | None) -> int | None:
    if draw_no is not None:
        return draw_no
    return _recommendation_draw_no()


def recommend_random(draw_no: int | None = None) -> Dict[str, object]:
    numbers = sorted(_RNG.sample(range(1, 46), 6))
    target_draw_no = _resolve_target_draw_no(draw_no)
    return {
        "strategy": "random",
        "numbers": numbers,
        "explanation": "45개 중 6개를 균등 확률로 무작위 추천했습니다.",
        "draw_no": target_draw_no,
    }


def recommend_frequency_hot(draw_no: int | None = None) -> Dict[str, object]:
    draws, latest_draw_no = _ensure_draws()
    freq = _frequency_table(draws)
    top = sorted(freq.items(), key=lambda item: (-item[1], item[0]))[:6]
    numbers = sorted(num for num, _ in top)
    target_draw_no = _resolve_target_draw_no(draw_no) or (latest_draw_no + 1)
    return {
        "strategy": "frequency_hot",
        "numbers": numbers,
        "explanation": "최근까지 가장 자주 등장한 번호 Top 6 조합입니다.",
        "draw_no": target_draw_no,
    }


def recommend_frequency_cold(draw_no: int | None = None) -> Dict[str, object]:
    draws, latest_draw_no = _ensure_draws()
    freq = _frequency_table(draws)
    bottom = sorted(freq.items(), key=lambda item: (item[1], item[0]))[:6]
    numbers = sorted(num for num, _ in bottom)
    target_draw_no = _resolve_target_draw_no(draw_no) or (latest_draw_no + 1)
    return {
        "strategy": "frequency_cold",
        "numbers": numbers,
        "explanation": "오랫동안 잘 나오지 않은 번호 6개를 골랐습니다.",
        "draw_no": target_draw_no,
    }


def recommend_balanced_parity(draw_no: int | None = None) -> Dict[str, object]:
    draws, latest_draw_no = _ensure_draws()
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
    target_draw_no = _resolve_target_draw_no(draw_no) or (latest_draw_no + 1)
    return {
        "strategy": "balanced_parity",
        "numbers": numbers,
        "explanation": "최근 빈도를 기반으로 짝수 3개/홀수 3개 균형 조합을 추천합니다.",
        "draw_no": target_draw_no,
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


def _user_recommendation_collection():
    settings = get_settings()
    if not settings.use_mongo_storage:
        raise RecommendationError("MongoDB 백엔드에서만 사용자 추천 저장이 가능합니다.")

    client = get_mongo_client()
    collection = client[settings.mongo_db_name][
        settings.mongo_user_recommendation_collection_name
    ]
    collection.create_index(
        [("user_id", 1), ("draw_no", 1), ("strategy", 1)],
        unique=True,
    )
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


def _cache_lookup_batch(draw_no: int | None) -> Optional[List[Dict[str, object]]]:
    collection = _recommendation_collection()
    if collection is None or draw_no is None:
        return None

    documents = list(collection.find({"draw_no": draw_no}))
    if not documents:
        return None

    strategy_order = {name: index for index, name in enumerate(sorted(STRATEGIES))}

    def _key(document: Dict[str, object]) -> tuple[int, str]:
        result = document.get("result", {})
        strategy = result.get("strategy") or document.get("strategy") or ""
        return strategy_order.get(strategy, len(strategy_order)), strategy

    return [
        document["result"]
        for document in sorted(documents, key=_key)
        if document.get("result")
    ]


def _run_strategy(strategy: str, draw_no: int | None) -> Dict[str, object]:
    handler = STRATEGIES.get(strategy)
    if not handler:
        available = ", ".join(sorted(STRATEGIES))
        raise RecommendationError(
            f"지원하지 않는 전략입니다: {strategy} (가능: {available})"
        )
    return handler(draw_no)


def get_recommendation(strategy: str) -> Dict[str, object]:
    draw_no = _recommendation_draw_no()
    cached = _cache_lookup(strategy, draw_no)
    if cached:
        return cached

    result = _run_strategy(strategy, draw_no)
    _cache_store(strategy, draw_no, result)
    return result


def get_all_recommendations() -> List[Dict[str, object]]:
    draw_no = _recommendation_draw_no()
    cached_batch = _cache_lookup_batch(draw_no) if draw_no is not None else None
    if cached_batch:
        return cached_batch

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


def create_user_recommendation(user_id: str, strategy: str) -> Dict[str, object]:
    if not user_id:
        raise RecommendationError("userId가 비어 있습니다.")

    recommendation = get_recommendation(strategy)
    numbers = recommendation["numbers"]
    draw_no = recommendation.get("draw_no")

    collection = _user_recommendation_collection()
    now = datetime.now(timezone.utc)
    document = collection.find_one_and_update(
        {"user_id": user_id, "draw_no": draw_no, "strategy": strategy},
        {
            "$set": {
                "user_id": user_id,
                "strategy": strategy,
                "numbers": numbers,
                "draw_no": draw_no,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now, "evaluation": None},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if not document:
        raise RecommendationError("추천 정보를 저장하지 못했습니다.")

    return {
        "id": str(document["_id"]),
        "userId": document["user_id"],
        "strategy": document["strategy"],
        "numbers": document["numbers"],
        "draw_no": document.get("draw_no"),
        "created_at": document.get("created_at"),
        "evaluation": document.get("evaluation"),
    }


def get_user_recommendations(user_id: str) -> List[Dict[str, object]]:
    if not user_id:
        raise RecommendationError("userId가 비어 있습니다.")

    collection = _user_recommendation_collection()
    cursor = collection.find({"user_id": user_id}).sort("created_at", -1)

    results: List[Dict[str, object]] = []
    for document in cursor:
        results.append(
            {
                "id": str(document["_id"]),
                "userId": document["user_id"],
                "strategy": document["strategy"],
                "numbers": document["numbers"],
                "draw_no": document.get("draw_no"),
                "created_at": document.get("created_at"),
                "evaluation": document.get("evaluation"),
            }
        )
    return results


def evaluate_user_recommendation(
    user_id: str,
    recommendation_id: str,
    draw_no: int,
    numbers: List[int],
) -> Dict[str, object]:
    if not user_id:
        raise RecommendationError("userId가 비어 있습니다.")
    if not recommendation_id:
        raise RecommendationError("추천 ID가 필요합니다.")

    collection = _user_recommendation_collection()
    try:
        object_id = ObjectId(recommendation_id)
    except InvalidId as exc:
        raise RecommendationError("유효하지 않은 추천 ID입니다.") from exc

    document = collection.find_one({"_id": object_id, "user_id": user_id})
    if not document:
        raise RecommendationError("추천 정보를 찾을 수 없습니다.")

    stored_numbers = sorted(int(num) for num in document.get("numbers", []))
    provided_numbers = sorted(int(num) for num in numbers)
    if stored_numbers != provided_numbers:
        raise RecommendationError("요청 번호가 저장된 추천 번호와 일치하지 않습니다.")

    stored_draw_no = document.get("draw_no")
    if stored_draw_no != draw_no:
        raise RecommendationError("요청 회차가 저장된 추천 회차와 일치하지 않습니다.")

    latest_known_draw_no = _latest_known_draw_no()
    if latest_known_draw_no is not None and draw_no > latest_known_draw_no:
        raise RecommendationError(
            f"{draw_no}회차는 아직 추첨되지 않았어요. "
            f"가장 최근 추첨은 {latest_known_draw_no}회차입니다."
        )

    settings = get_settings()
    draw = None
    if settings.use_mongo_storage:
        draw = get_stored_draw(draw_no)
    if draw is None:
        draw = fetch_draw_info(draw_no)

    result = evaluate_ticket(draw, stored_numbers)
    evaluation_payload = {
        "rank": result.get("rank"),
        "match_count": result.get("match_count"),
        "matched_numbers": result.get("matched_numbers"),
        "bonus_matched": result.get("bonus_matched"),
    }

    collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "evaluation": evaluation_payload,
                "evaluated_at": datetime.now(timezone.utc),
            }
        },
    )

    return result


__all__ = [
    "get_recommendation",
    "get_all_recommendations",
    "RecommendationError",
    "STRATEGIES",
    "create_user_recommendation",
    "get_user_recommendations",
    "evaluate_user_recommendation",
]
