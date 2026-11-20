"""Database engine, session management, and Alembic migration runner."""

import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Generator

import structlog
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Arbitrary but fixed 64-bit key: every process must agree on the same value for
# pg_advisory_lock() to serialize concurrent run_migrations() calls (see below).
ALEMBIC_MIGRATION_LOCK_ID = 847291056

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
    """Apply all pending Alembic migrations (idempotent), serialized via an advisory lock.

    Every agent and the webapp call this at startup, so two instances can start within
    the same window (overlapping timer triggers, a redeploy racing an in-flight job) and
    both read the same current revision before either has written the new one — without
    serialization, that's a real risk of two concurrent ALTER TABLE statements on the same
    table. A session-level Postgres advisory lock (`pg_advisory_lock`) forces the second
    caller to block until the first releases it; by then the migration is already applied,
    so the second caller's `alembic upgrade head` is a no-op.

    Raises:
        SQLAlchemyError: If acquiring/releasing the advisory lock fails, or if the
            migration itself fails with a database-level error (e.g. invalid SQL).
        CommandError: If Alembic itself reports a configuration or revision error.
    """
    logger.info("alembic_migrations_started")
    alembic_cfg_path = (Path(__file__).parent / ".." / "migrations" / "alembic.ini").resolve()
    cfg = Config(str(alembic_cfg_path))

    # Same engine/pool as command.upgrade()'s own connection (migrations/env.py calls
    # get_engine() too) — this checks out a second connection from the pool for the
    # duration of the lock, so the pool must stay large enough (default QueuePool,
    # pool_size=5) for both to be held open at once.
    with get_engine().connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        try:
            conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": ALEMBIC_MIGRATION_LOCK_ID})
        except SQLAlchemyError:
            logger.error("alembic_migration_lock_failed", exc_info=True)
            raise

        try:
            command.upgrade(cfg, "head")
        except (CommandError, SQLAlchemyError):
            logger.error("alembic_migrations_failed", exc_info=True)
            raise
        finally:
            try:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ALEMBIC_MIGRATION_LOCK_ID})
            except SQLAlchemyError:
                logger.error("alembic_migration_unlock_failed", exc_info=True)
                raise

    logger.info("alembic_migrations_applied")
