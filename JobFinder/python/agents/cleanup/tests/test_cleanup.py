"""Unit tests for cleanup/main.py._cleanup.

Tests use an in-memory SQLite DB created with raw DDL to avoid the pgvector
Vector type, which SQLite does not support. The _cleanup function only reads
and deletes on offers.id and offers.collected_at, so omitting the vector
column is safe here.

Datetime values are formatted with strftime('%Y-%m-%d %H:%M:%S.%f') to match
SQLAlchemy's SQLite DateTime bind-parameter representation, ensuring correct
string-based chronological comparison.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from main import _cleanup


def _utcstr(dt: datetime) -> str:
    """Serialize a datetime to the format SQLAlchemy's SQLite DateTime uses."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


@pytest.fixture()
def db_session():
    """In-memory SQLite session with the minimal schema required by _cleanup."""
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE offers (
                id          TEXT PRIMARY KEY,
                ft_id       TEXT UNIQUE NOT NULL,
                title       TEXT NOT NULL DEFAULT '',
                company     TEXT NOT NULL DEFAULT '',
                location    TEXT NOT NULL DEFAULT '',
                contract_type TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                skills      TEXT NOT NULL DEFAULT '[]',
                collected_at TIMESTAMP NOT NULL,
                ft_updated_at TIMESTAMP,
                expires_at  TIMESTAMP,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(sa.text("""
            CREATE TABLE matches (
                id          TEXT PRIMARY KEY,
                cv_id       TEXT NOT NULL,
                offer_id    TEXT NOT NULL REFERENCES offers(id),
                score       REAL NOT NULL,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    with Session(engine) as session:
        yield session
    engine.dispose()


def _add_offer(session: Session, collected_at: datetime) -> str:
    oid = str(uuid.uuid4())
    session.execute(
        sa.text(
            "INSERT INTO offers (id, ft_id, collected_at)"
            " VALUES (:id, :ft_id, :collected_at)"
        ),
        {"id": oid, "ft_id": oid, "collected_at": _utcstr(collected_at)},
    )
    return oid


def _add_match(session: Session, offer_id: str) -> str:
    mid = str(uuid.uuid4())
    session.execute(
        sa.text(
            "INSERT INTO matches (id, cv_id, offer_id, score)"
            " VALUES (:id, 'cv-test', :offer_id, 0.8)"
        ),
        {"id": mid, "offer_id": offer_id},
    )
    return mid


def test_stale_offer_deleted(db_session: Session) -> None:
    """An offer not refreshed in > CLEANUP_COLLECTED_AGE_DAYS is deleted."""
    now = datetime.now(timezone.utc)
    _add_offer(db_session, now - timedelta(days=3))
    db_session.flush()

    deleted_offers, _ = _cleanup(db_session)

    assert deleted_offers == 1


def test_stale_match_cascade_deleted(db_session: Session) -> None:
    """Matches on a stale offer are deleted before the offer itself."""
    now = datetime.now(timezone.utc)
    oid = _add_offer(db_session, now - timedelta(days=3))
    _add_match(db_session, oid)
    db_session.flush()

    deleted_offers, deleted_matches = _cleanup(db_session)

    assert deleted_offers == 1
    assert deleted_matches == 1


def test_fresh_offer_preserved(db_session: Session) -> None:
    """An offer refreshed within the grace period is not deleted."""
    now = datetime.now(timezone.utc)
    _add_offer(db_session, now - timedelta(hours=12))
    db_session.flush()

    deleted_offers, _ = _cleanup(db_session)

    assert deleted_offers == 0


def test_only_stale_deleted_in_mixed_set(db_session: Session) -> None:
    """With fresh and stale offers present, only the stale one is deleted."""
    now = datetime.now(timezone.utc)
    stale_id = _add_offer(db_session, now - timedelta(days=3))
    fresh_id = _add_offer(db_session, now - timedelta(hours=6))
    _add_match(db_session, stale_id)
    _add_match(db_session, fresh_id)
    db_session.flush()

    deleted_offers, deleted_matches = _cleanup(db_session)

    assert deleted_offers == 1
    assert deleted_matches == 1
    remaining = db_session.execute(
        sa.text("SELECT id FROM offers")
    ).scalars().all()
    assert set(remaining) == {fresh_id}
