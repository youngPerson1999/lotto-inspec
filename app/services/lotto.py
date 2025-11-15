"""Utilities for retrieving Lotto draw information from the DhLottery site."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import UpdateOne

from app.core.config import get_settings
from app.core.db import get_draw_collection
from app.core.http_client import fetch_text, fetch_url


@dataclass
class LottoDraw:
    """Container holding the essential facts for a lotto drawing."""

    draw_no: int
    draw_date: str
    numbers: List[int]
    bonus: int


@dataclass
class LottoSyncResult:
    """Summary of a synchronization run against DhLottery."""

    previous_max: int
    latest: int
    inserted: int
    draws: List[LottoDraw]


def _draw_file() -> Path:
    return get_settings().draw_storage_path


def _deduplicate_draws(draws: List[LottoDraw]) -> List[LottoDraw]:
    dedup: Dict[int, LottoDraw] = {}
    for draw in sorted(draws, key=lambda d: d.draw_no):
        dedup[draw.draw_no] = draw
    return list(dedup.values())


def _extract_latest_draw_number(html: str) -> int:
    """Parse the DhLottery `byWin` page for the newest draw number."""

    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", id="dwrNoList")
    if not select:
        raise ValueError("Could not find select#dwrNoList in response HTML.")

    latest: int | None = None
    for option in select.find_all("option"):
        value = option.get("value")
        if not value or not value.isdigit():
            continue

        draw_number = int(value)
        if latest is None or draw_number > latest:
            latest = draw_number

    if latest is None:
        raise ValueError("No numeric draw numbers found in select#dwrNoList.")

    return latest


def _ensure_data_dir() -> None:
    data_dir = get_settings().data_dir
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)


def _draw_to_dict(draw: LottoDraw) -> Dict[str, object]:
    return {
        "draw_no": draw.draw_no,
        "draw_date": draw.draw_date,
        "numbers": draw.numbers,
        "bonus": draw.bonus,
    }


def _dict_to_draw(payload: Dict[str, object]) -> LottoDraw:
    return LottoDraw(
        draw_no=int(payload["draw_no"]),
        draw_date=str(payload["draw_date"]),
        numbers=[int(num) for num in payload["numbers"]],
        bonus=int(payload["bonus"]),
    )


def load_stored_draws() -> List[LottoDraw]:
    """Load locally cached draws (if any)."""

    if get_settings().use_mongo_storage:
        return _load_draws_from_mongo()

    return _load_draws_from_file()


def _load_draws_from_file() -> List[LottoDraw]:
    draw_path = _draw_file()
    if not draw_path.exists():
        return []

    data = json.loads(draw_path.read_text())
    draws = [_dict_to_draw(item) for item in data]
    return sorted(draws, key=lambda draw: draw.draw_no)


def _load_draws_from_mongo() -> List[LottoDraw]:
    collection = get_draw_collection()
    cursor = collection.find({}, sort=[("draw_no", ASCENDING)])
    return [_dict_to_draw(document) for document in cursor]


def save_draws(draws: List[LottoDraw]) -> None:
    """Persist draws using the configured backend."""

    if not draws:
        return

    if get_settings().use_mongo_storage:
        _save_draws_to_mongo(draws)
    else:
        _save_draws_to_file(draws)


def _save_draws_to_file(draws: List[LottoDraw]) -> None:
    _ensure_data_dir()
    dedup = _deduplicate_draws(draws)
    serialized = [_draw_to_dict(draw) for draw in dedup]
    draw_path = _draw_file()
    tmp_path = draw_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(serialized, indent=2))
    tmp_path.replace(draw_path)


def _save_draws_to_mongo(draws: List[LottoDraw]) -> None:
    collection = get_draw_collection()
    dedup = _deduplicate_draws(draws)
    operations = [
        UpdateOne(
            {"draw_no": draw.draw_no},
            {"$set": _draw_to_dict(draw)},
            upsert=True,
        )
        for draw in dedup
    ]
    if operations:
        collection.bulk_write(operations, ordered=False)


def fetch_draw_info(draw_no: int) -> LottoDraw:
    """Fetch metadata for a specific Lotto draw via the DhLottery JSON endpoint."""

    response = fetch_url(
        get_settings().lotto_json_url,
        params={"method": "getLottoNumber", "drwNo": draw_no},
    )
    payload = response.json()

    if payload.get("returnValue") != "success":
        raise ValueError(
            f"DhLottery API returned failure for draw {draw_no}: {payload}"
        )

    numbers = [payload[f"drwtNo{i}"] for i in range(1, 7)]

    return LottoDraw(
        draw_no=draw_no,
        draw_date=payload["drwNoDate"],
        numbers=numbers,
        bonus=payload["bnusNo"],
    )


def get_stored_draw(draw_no: int) -> LottoDraw | None:
    """저장소(파일/몽고)에서 특정 회차를 조회."""

    settings = get_settings()
    if settings.use_mongo_storage:
        document = get_draw_collection().find_one({"draw_no": draw_no})
        return _dict_to_draw(document) if document else None

    for draw in load_stored_draws():
        if draw.draw_no == draw_no:
            return draw
    return None


def fetch_latest_draw_info() -> LottoDraw:
    """Fetch metadata for the latest Lotto draw available on DhLottery."""

    page_html = fetch_text(
        get_settings().lotto_result_url,
        params={"method": "byWin"},
    )
    latest_draw_no = _extract_latest_draw_number(page_html)

    return fetch_draw_info(latest_draw_no)


def get_latest_stored_draw() -> LottoDraw | None:
    """저장소에서 가장 최신 회차를 반환."""

    settings = get_settings()
    if settings.use_mongo_storage:
        document = get_draw_collection().find_one(sort=[("draw_no", DESCENDING)])
        return _dict_to_draw(document) if document else None

    stored = load_stored_draws()
    return stored[-1] if stored else None


def sync_draw_storage() -> LottoSyncResult:
    """Download missing draws and append them to local storage."""

    stored = load_stored_draws()
    previous_max = stored[-1].draw_no if stored else 0

    latest_draw = fetch_latest_draw_info()
    latest_no = latest_draw.draw_no

    if latest_no <= previous_max:
        return LottoSyncResult(
            previous_max=previous_max,
            latest=latest_no,
            inserted=0,
            draws=[],
        )

    missing_draws: List[LottoDraw] = []
    for draw_no in range(previous_max + 1, latest_no):
        missing_draws.append(fetch_draw_info(draw_no))
    missing_draws.append(latest_draw)

    if get_settings().use_mongo_storage:
        save_draws(missing_draws)
    else:
        save_draws(stored + missing_draws)

    return LottoSyncResult(
        previous_max=previous_max,
        latest=latest_no,
        inserted=len(missing_draws),
        draws=missing_draws,
    )
