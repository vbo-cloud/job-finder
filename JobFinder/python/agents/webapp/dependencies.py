"""Shared FastAPI dependencies for the webapp."""

from typing import Generator

from sqlalchemy.orm import Session

from shared.db import get_session


def get_db() -> Generator[Session, None, None]:
    """Yield an active database session for the duration of a request.

    Rolls back automatically on exception (delegated to get_session).

    Yields:
        Session: An active SQLAlchemy session.
    """
    with get_session() as session:
        yield session
