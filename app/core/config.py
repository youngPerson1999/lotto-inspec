"""Application configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime configuration resolved from environment variables."""

    data_dir: Path = Path(os.getenv("LOTTO_DATA_DIR", "data"))
    lotto_result_url: str = os.getenv(
        "LOTTO_RESULT_URL",
        "https://dhlottery.co.kr/gameResult.do",
    )
    lotto_json_url: str = os.getenv(
        "LOTTO_JSON_URL",
        "https://www.dhlottery.co.kr/common.do",
    )
    user_agent: str = os.getenv(
        "LOTTO_USER_AGENT",
        "lotto-insec/1.0 (+https://github.com/youngin-ko/lotto-insec)",
    )
    request_timeout: float = float(os.getenv("LOTTO_REQUEST_TIMEOUT", "10"))

    @property
    def draw_storage_path(self) -> Path:
        return self.data_dir / "lotto_draws.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    settings = Settings()
    if not settings.data_dir.exists():
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings

