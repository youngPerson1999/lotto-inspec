"""MariaDB connection helpers built on SQLAlchemy."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by the SQLAlchemy models."""


_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def _initialize_engine() -> None:
    """Instantiate the singleton engine/session factory if needed."""

    global _engine, _session_factory  # noqa: PLW0603  # module-level cache
    if _engine is not None and _session_factory is not None:
        return

    settings = get_settings()
    if not settings.use_database_storage:
        raise RuntimeError(
            "LOTTO_STORAGE_BACKEND must be set to 'mariadb' "
            "to use the database backend.",
        )

    engine = create_engine(
        settings.mariadb_dsn,
        pool_pre_ping=True,
        future=True,
    )
    _engine = engine
    _session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )

    # Import models lazily so their metadata is registered before create_all.
    from app.core import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_engine() -> Engine:
    """Return the singleton SQLAlchemy engine."""

    _initialize_engine()
    assert _engine is not None  # narrow type for mypy/pyright
    return _engine


def get_session() -> Session:
    """Return a transactional Session bound to the global engine."""

    _initialize_engine()
    assert _session_factory is not None
    return _session_factory()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope for DB operations."""

    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:  # noqa: BLE001  # bubble up after rollback
        session.rollback()
        raise
    finally:
        session.close()


def ping_database() -> tuple[bool, int | None]:
    """Run a lightweight health check against MariaDB."""

    _initialize_engine()
    from app.core.models import LottoDrawORM

    with session_scope() as session:
        session.execute(text("SELECT 1"))
        total = session.scalar(
            select(func.count()).select_from(LottoDrawORM)
        )
    return True, int(total or 0)


__all__ = ["Base", "get_engine", "get_session", "session_scope", "ping_database"]
