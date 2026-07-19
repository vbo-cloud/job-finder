"""Unit tests for cleanup/main.py._cleanup and _snapshot_totals.

Tests use an in-memory SQLite DB created with raw DDL to avoid the pgvector
Vector type, which SQLite does not support. _cleanup only reads and deletes on
offers.id/offers.collected_at/matches.id, and _snapshot_totals only issues
COUNT(*) queries with no column references, so omitting the vector column
(and the rest of the cvs schema beyond `id`) is safe here.

The db_session fixture enables PRAGMA foreign_keys=ON (off by default in
SQLite) so that the match_analyses -> matches foreign key is actually
enforced, matching PostgreSQL's default behavior. Without it,
test_stale_offer_with_analyzed_match_deleted_without_fk_violation would pass
even without the fix in _cleanup(), making it a false regression test.

Datetime values are formatted with strftime('%Y-%m-%d %H:%M:%S.%f') to match
SQLAlchemy's SQLite DateTime bind-parameter representation, ensuring correct
string-based chronological comparison.
"""

import importlib.util
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from pytest_mock import MockerFixture
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

_CLEANUP_DIR = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("cleanup_main", _CLEANUP_DIR / "main.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["cleanup_main"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_cleanup = _mod._cleanup
_snapshot_totals = _mod._snapshot_totals


def _session_cm(session: MagicMock):
    """Return a contextmanager-compatible callable that yields the given session."""
    @contextmanager
    def _cm():
        yield session
    return _cm


def _utcstr(dt: datetime) -> str:
    """Serialize a datetime to the format SQLAlchemy's SQLite DateTime uses."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


@pytest.fixture()
def db_session():
    """In-memory SQLite session with the minimal schema required by _cleanup."""
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text("PRAGMA foreign_keys=ON"))
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
        conn.execute(sa.text("""
            CREATE TABLE cvs (
                id          TEXT PRIMARY KEY
            )
        """))
        conn.execute(sa.text("""
            CREATE TABLE match_analyses (
                id          TEXT PRIMARY KEY,
                match_id    TEXT NOT NULL UNIQUE REFERENCES matches(id)
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


def _add_cv(session: Session) -> str:
    cid = str(uuid.uuid4())
    session.execute(sa.text("INSERT INTO cvs (id) VALUES (:id)"), {"id": cid})
    return cid


def _add_analysis(session: Session, match_id: str) -> str:
    aid = str(uuid.uuid4())
    session.execute(
        sa.text("INSERT INTO match_analyses (id, match_id) VALUES (:id, :match_id)"),
        {"id": aid, "match_id": match_id},
    )
    return aid


def test_stale_offer_deleted(db_session: Session) -> None:
    """An offer not refreshed in > CLEANUP_COLLECTED_AGE_DAYS is deleted."""
    now = datetime.now(timezone.utc)
    _add_offer(db_session, now - timedelta(days=3))
    db_session.flush()

    deleted_offers, _, _ = _cleanup(db_session)

    assert deleted_offers == 1


def test_stale_match_cascade_deleted(db_session: Session) -> None:
    """Matches on a stale offer are deleted before the offer itself."""
    now = datetime.now(timezone.utc)
    oid = _add_offer(db_session, now - timedelta(days=3))
    _add_match(db_session, oid)
    db_session.flush()

    deleted_offers, deleted_matches, _ = _cleanup(db_session)

    assert deleted_offers == 1
    assert deleted_matches == 1


def test_fresh_offer_preserved(db_session: Session) -> None:
    """An offer refreshed within the grace period is not deleted."""
    now = datetime.now(timezone.utc)
    _add_offer(db_session, now - timedelta(hours=12))
    db_session.flush()

    deleted_offers, _, _ = _cleanup(db_session)

    assert deleted_offers == 0


def test_only_stale_deleted_in_mixed_set(db_session: Session) -> None:
    """With fresh and stale offers present, only the stale one is deleted."""
    now = datetime.now(timezone.utc)
    stale_id = _add_offer(db_session, now - timedelta(days=3))
    fresh_id = _add_offer(db_session, now - timedelta(hours=6))
    _add_match(db_session, stale_id)
    _add_match(db_session, fresh_id)
    db_session.flush()

    deleted_offers, deleted_matches, _ = _cleanup(db_session)

    assert deleted_offers == 1
    assert deleted_matches == 1
    remaining = db_session.execute(
        sa.text("SELECT id FROM offers")
    ).scalars().all()
    assert set(remaining) == {fresh_id}


def test_stale_offer_with_analyzed_match_deleted_without_fk_violation(db_session: Session) -> None:
    """Regression: a stale offer whose match has a MatchAnalysis is cleaned up without a
    ForeignKeyViolation. match_analyses.match_id has a NOT NULL FK to matches.id with no
    ondelete=CASCADE, so the analysis must be deleted before its match (see PR description)."""
    now = datetime.now(timezone.utc)
    oid = _add_offer(db_session, now - timedelta(days=3))
    mid = _add_match(db_session, oid)
    _add_analysis(db_session, mid)
    db_session.flush()

    deleted_offers, deleted_matches, deleted_analyses = _cleanup(db_session)

    assert deleted_offers == 1
    assert deleted_matches == 1
    assert deleted_analyses == 1


def test_snapshot_totals_empty_database(db_session: Session) -> None:
    """With no rows in either table, both totals are 0."""
    total_offers, total_cvs = _snapshot_totals(db_session)

    assert total_offers == 0
    assert total_cvs == 0


def test_snapshot_totals_counts_offers_only(db_session: Session) -> None:
    """Offers are counted independently of CVs."""
    now = datetime.now(timezone.utc)
    _add_offer(db_session, now)
    _add_offer(db_session, now)
    db_session.flush()

    total_offers, total_cvs = _snapshot_totals(db_session)

    assert total_offers == 2
    assert total_cvs == 0


def test_snapshot_totals_counts_cvs_only(db_session: Session) -> None:
    """CVs are counted independently of offers."""
    _add_cv(db_session)
    db_session.flush()

    total_offers, total_cvs = _snapshot_totals(db_session)

    assert total_offers == 0
    assert total_cvs == 1


def test_snapshot_totals_counts_both(db_session: Session) -> None:
    """Offers and CVs are counted together, each against its own table."""
    now = datetime.now(timezone.utc)
    _add_offer(db_session, now)
    _add_offer(db_session, now)
    _add_offer(db_session, now)
    _add_cv(db_session)
    _add_cv(db_session)
    db_session.flush()

    total_offers, total_cvs = _snapshot_totals(db_session)

    assert total_offers == 3
    assert total_cvs == 2


# ---------------------------------------------------------------------------
# main() — daily_snapshot best-effort behavior
# ---------------------------------------------------------------------------


class TestMainDailySnapshot:
    """Covers main()'s wiring of the daily_snapshot step, including its best-effort failure path."""

    def _mock_main_deps(self, mocker: MockerFixture) -> None:
        """Patch main()'s startup/session/cleanup dependencies, leaving _snapshot_totals to the caller."""
        mocker.patch.object(_mod, "configure_telemetry")
        mocker.patch.object(_mod, "run_migrations")
        mocker.patch.object(_mod, "get_session", _session_cm(MagicMock()))
        mocker.patch.object(_mod, "_cleanup", return_value=(0, 0, 0))

    def test_daily_snapshot_logged_after_cleanup(self, mocker: MockerFixture) -> None:
        """main() logs daily_snapshot with the totals returned by _snapshot_totals."""
        self._mock_main_deps(mocker)
        mocker.patch.object(_mod, "_snapshot_totals", return_value=(42, 7))
        mock_logger_info = mocker.patch.object(_mod.logger, "info")

        _mod.main()

        mock_logger_info.assert_any_call("daily_snapshot", total_offers=42, total_cvs=7)

    def test_snapshot_failure_does_not_raise_or_fail_the_job(self, mocker: MockerFixture) -> None:
        """A _snapshot_totals failure is swallowed and logged, never propagated to the caller."""
        self._mock_main_deps(mocker)
        mocker.patch.object(
            _mod, "_snapshot_totals", side_effect=SQLAlchemyError("db down")
        )
        mock_logger_error = mocker.patch.object(_mod.logger, "error")

        _mod.main()  # must not raise

        mock_logger_error.assert_any_call("daily_snapshot_failed", exc_info=True)

    def test_cleanup_still_completes_normally_alongside_snapshot(self, mocker: MockerFixture) -> None:
        """cleanup_completed keeps logging as before, unaffected by the new snapshot step."""
        self._mock_main_deps(mocker)
        mocker.patch.object(_mod, "_cleanup", return_value=(3, 5, 2))
        mocker.patch.object(_mod, "_snapshot_totals", return_value=(0, 0))
        mock_logger_info = mocker.patch.object(_mod.logger, "info")

        _mod.main()

        mock_logger_info.assert_any_call(
            "cleanup_completed", deleted_offers=3, deleted_matches=5, deleted_analyses=2
        )
