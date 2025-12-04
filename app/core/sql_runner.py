"""Utility to execute raw SQL files for bootstrapping tables."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pymysql

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SQL_FILE_ORDER: tuple[str, ...] = (
    "lotto_draws.sql",
    "analysis_snapshots.sql",
    "users.sql",
    "refresh_tokens.sql",
    "user_tickets.sql",
    "recommendation_snapshots.sql",
    "user_recommendations.sql",
)


def _sql_directory() -> Path:
    """Return the absolute path to the SQL directory."""

    return Path(__file__).resolve().parents[2] / "sql"


def _read_sql_files(directory: Path, filenames: Iterable[str]) -> list[tuple[str, str]]:
    """Load SQL statements from disk."""

    statements: list[tuple[str, str]] = []
    for filename in filenames:
        path = directory / filename
        if not path.exists():
            logger.warning("SQL file not found: %s", path)
            continue
        sql = path.read_text(encoding="utf-8").strip()
        if not sql:
            logger.debug("SQL file empty: %s", path)
            continue
        statements.append((filename, sql))
    return statements


def ensure_database_tables() -> None:
    """Execute CREATE TABLE statements when the database backend is enabled."""

    settings = get_settings()
    if not settings.use_database_storage:
        logger.debug("Skipping SQL bootstrap; database backend disabled.")
        return

    sql_dir = _sql_directory()
    if not sql_dir.exists():
        logger.warning("SQL directory is missing: %s", sql_dir)
        return

    statements = _read_sql_files(sql_dir, SQL_FILE_ORDER)
    if not statements:
        logger.debug("No SQL statements loaded from %s", sql_dir)
        return

    connection = pymysql.connect(
        host=settings.mariadb_host,
        port=settings.mariadb_port,
        user=settings.mariadb_user,
        password=settings.mariadb_password,
        database=settings.mariadb_db_name,
        autocommit=True,
        charset="utf8mb4",
    )

    try:
        with connection.cursor() as cursor:
            for filename, statement in statements:
                logger.info("Ensuring table via %s", filename)
                cursor.execute(statement)
    finally:
        connection.close()


__all__ = ["ensure_database_tables"]
