"""Application configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from app.core.env_loader import load_env_file

load_env_file()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration resolved from environment variables."""

    data_dir: Path = Path(os.getenv("LOTTO_DATA_DIR", "data"))
    storage_backend: str = os.getenv("LOTTO_STORAGE_BACKEND", "file")
    mariadb_host: str = os.getenv("MARIADB_HOST", "127.0.0.1")
    mariadb_port: int = int(os.getenv("MARIADB_PORT", "3306"))
    mariadb_user: str = os.getenv("MARIADB_USER", "lotto")
    mariadb_password: str = os.getenv("MARIADB_PASSWORD", "")
    mariadb_db_name: str = os.getenv("MARIADB_DB_NAME", "lotto_insec")
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
    cors_allowed_origins: str = os.getenv(
        "LOTTO_ALLOWED_ORIGINS",
        "http://localhost:3000,https://lotto-inspec-front.vercel.app,https://www.lotto-inspec.com,https://lotto-inspec.com",
    )
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_exp_minutes: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    jwt_refresh_token_exp_days: int = int(
        os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "14")
    )
    @property
    def draw_storage_path(self) -> Path:
        return self.data_dir / "lotto_draws.json"

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    @property
    def use_database_storage(self) -> bool:
        """Return True when MariaDB/MySQL is configured as the storage backend."""

        return self.storage_backend.lower() in {
            "mariadb",
            "mysql",
            "db",
            "database",
        }

    @property
    def mariadb_dsn(self) -> str:
        """SQLAlchemy-compatible DSN for the configured MariaDB connection."""

        password = quote_plus(self.mariadb_password)
        user = quote_plus(self.mariadb_user)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.mariadb_host}:{self.mariadb_port}/{self.mariadb_db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    settings = Settings()
    if (
        not settings.use_database_storage
        and not settings.data_dir.exists()
    ):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
