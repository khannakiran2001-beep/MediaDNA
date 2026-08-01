"""SQLAlchemy engine / session management.

Uses SQLite for a zero-config MVP. The models and repositories are written so
that swapping ``database_url`` to a PostgreSQL + pgvector instance requires no
application code changes (embeddings are stored as JSON here; a pgvector column
would be the production upgrade).
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()


def _normalize_db_url(url: str) -> str:
    """Ensure Postgres URLs use the psycopg (v3) driver we ship.

    Supabase/Heroku hand out ``postgres://`` or ``postgresql://``, which
    SQLAlchemy maps to psycopg2 (not installed). Rewrite to psycopg v3.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_db_url(settings.database_url)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
_engine_kwargs: dict = {"connect_args": _connect_args, "future": True}
if not DATABASE_URL.startswith("sqlite"):
    # Recycle pooled Postgres connections to survive Supabase pooler timeouts.
    _engine_kwargs.update(pool_pre_ping=True, pool_recycle=280)
engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from . import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
