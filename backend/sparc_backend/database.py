"""Database configuration and session management for the Sparc backend."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


_settings = get_settings()
_engine = create_engine(_settings.database_url, future=True)
SessionLocal = sessionmaker(
    bind=_engine, autoflush=False, autocommit=False, future=True
)


def get_engine():
    """Return the configured SQLAlchemy engine."""

    return _engine


def get_session() -> Iterator[Session]:
    """Provide a SQLAlchemy session for FastAPI dependencies."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope for background workers."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - error handling path
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["Base", "get_engine", "get_session", "session_scope", "SessionLocal"]
