"""Database engine, session management, and Alembic migration runner."""

import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Generator

import structlog
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

logger = structlog.get_logger()

_connection_string = os.environ.get("DATABASE_URL")
if not _connection_string:
    raise ValueError("DATABASE_URL environment variable is not set")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the singleton SQLAlchemy engine."""
    return create_engine(_connection_string)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a database session with automatic rollback on exception and close on exit.

    Yields:
        Session: An active SQLAlchemy session.
    """
    with Session(get_engine()) as session:
        try:
            yield session
        except Exception:  # re-raise intentional — context manager pattern
            # Session.close() is called automatically by the `with` block above,
            # but SQLAlchemy 2.0 does NOT auto-rollback on exit — explicit rollback is required.
            session.rollback()
            raise


def run_migrations() -> None:
    """Apply all pending Alembic migrations (idempotent)."""
    logger.info("alembic_migrations_started")
    alembic_cfg_path = (Path(__file__).parent / ".." / "migrations" / "alembic.ini").resolve()
    cfg = Config(str(alembic_cfg_path))
    try:
        command.upgrade(cfg, "head")
    except Exception:  # alembic raises generic Exception on migration failure — no narrower type available
        logger.error("alembic_migrations_failed", exc_info=True)
        raise
    logger.info("alembic_migrations_applied")
