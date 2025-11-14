"""Utilities for retrieving Lotto draw information from the DhLottery site."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup

from crawler import fetch_text, fetch_url

LOTTO_RESULT_URL = "https://dhlottery.co.kr/gameResult.do"
LOTTO_JSON_URL = "https://www.dhlottery.co.kr/common.do"
DATA_DIR = Path("data")
DRAW_FILE = DATA_DIR / "lotto_draws.json"


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
    DATA_DIR.mkdir(parents=True, exist_ok=True)


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

    if not DRAW_FILE.exists():
        return []

    data = json.loads(DRAW_FILE.read_text())
    draws = [_dict_to_draw(item) for item in data]
    return sorted(draws, key=lambda draw: draw.draw_no)


def save_draws(draws: List[LottoDraw]) -> None:
    """Persist draws atomically to disk."""

    if not draws:
        return

    _ensure_data_dir()
    dedup: Dict[int, LottoDraw] = {}
    for draw in sorted(draws, key=lambda d: d.draw_no):
        dedup[draw.draw_no] = draw

    serialized = [_draw_to_dict(draw) for draw in dedup.values()]
    tmp_path = DRAW_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(serialized, indent=2))
    tmp_path.replace(DRAW_FILE)


def fetch_draw_info(draw_no: int) -> LottoDraw:
    """Fetch metadata for a specific Lotto draw via the DhLottery JSON endpoint."""

    response = fetch_url(
        LOTTO_JSON_URL,
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


def fetch_latest_draw_info() -> LottoDraw:
    """Fetch metadata for the latest Lotto draw available on DhLottery."""

    page_html = fetch_text(
        LOTTO_RESULT_URL,
        params={"method": "byWin"},
    )
    latest_draw_no = _extract_latest_draw_number(page_html)

    return fetch_draw_info(latest_draw_no)


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

    save_draws(stored + missing_draws)

    return LottoSyncResult(
        previous_max=previous_max,
        latest=latest_no,
        inserted=len(missing_draws),
        draws=missing_draws,
    )
