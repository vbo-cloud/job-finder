"""Unit tests for notifications/main.py.

Tests use an in-memory SQLite DB created with raw DDL for _count_unseen_matches_by_cv,
same approach as agents/cleanup/tests/test_cleanup.py: only the columns the query
actually touches (cvs.id/cvs.user_id/cvs.name, matches.id/matches.cv_id/matches.seen_at)
are created, skipping the pgvector `embedding` column and the rest of the real schema.

_select_profiles_to_notify relies on UserProfile.notification_days.any(...), which
SQLAlchemy compiles to PostgreSQL's `<value> = ANY(notification_days)` — a construct
SQLite's ARRAY-less dialect cannot execute. That function is therefore covered by
mocking session.execute directly rather than against a real DB, the same pattern
cv_analysis/match_analysis already use for mocking _openai_client instead of a real
OpenAI client.
"""

import importlib.util
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from azure.core.exceptions import AzureError
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

_NOTIFICATIONS_DIR = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("notifications_main", _NOTIFICATIONS_DIR / "main.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["notifications_main"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]


def _session_cm(session: MagicMock):
    """Return a contextmanager-compatible callable that yields the given session."""
    @contextmanager
    def _cm():
        yield session
    return _cm


# ---------------------------------------------------------------------------
# _is_scheduled_local_hour
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("month", "utc_hour"),
    [
        (7, 17),  # July: CEST (UTC+2) — 17:00 UTC = 19:00 Europe/Paris
        (1, 18),  # January: CET (UTC+1) — 18:00 UTC = 19:00 Europe/Paris
    ],
)
def test_is_scheduled_local_hour_true_for_the_matching_dst_candidate_hour(
    month: int, utc_hour: int
) -> None:
    """Each UTC hour covered by the cron_expression maps to 19:00 Europe/Paris under its DST state."""
    now_utc = datetime(2026, month, 1, utc_hour, 0, tzinfo=timezone.utc)

    assert _mod._is_scheduled_local_hour(now_utc) is True


@pytest.mark.parametrize("utc_hour", [0, 12, 16, 19, 23])
def test_is_scheduled_local_hour_false_outside_the_two_candidate_hours(utc_hour: int) -> None:
    """Any UTC hour other than the two DST candidates is outside the scheduled window."""
    now_utc = datetime(2026, 1, 1, utc_hour, 0, tzinfo=timezone.utc)

    assert _mod._is_scheduled_local_hour(now_utc) is False


# ---------------------------------------------------------------------------
# _build_email_content
# ---------------------------------------------------------------------------


def test_build_email_content_includes_cv_name_and_count() -> None:
    plain_text, html = _mod._build_email_content([("Alternance Cloud", 3)], "https://jobfinder.example")

    assert "Alternance Cloud : 3 nouvelle(s) offre(s)" in plain_text
    assert "Alternance Cloud : 3 nouvelle(s) offre(s)" in html
    assert "https://jobfinder.example" in plain_text
    assert "https://jobfinder.example" in html


def test_build_email_content_uses_placeholder_for_unnamed_cv() -> None:
    plain_text, html = _mod._build_email_content([(None, 1)], "https://jobfinder.example")

    assert "CV sans nom : 1 nouvelle(s) offre(s)" in plain_text
    assert "CV sans nom : 1 nouvelle(s) offre(s)" in html


def test_build_email_content_lists_every_cv() -> None:
    plain_text, _ = _mod._build_email_content(
        [("CV A", 2), ("CV B", 5)], "https://jobfinder.example"
    )

    assert "CV A : 2 nouvelle(s) offre(s)" in plain_text
    assert "CV B : 5 nouvelle(s) offre(s)" in plain_text


# ---------------------------------------------------------------------------
# _count_unseen_matches_by_cv (real SQLite, minimal schema)
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """In-memory SQLite session with the minimal schema required by _count_unseen_matches_by_cv."""
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE cvs (
                id      TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name    TEXT
            )
        """))
        conn.execute(sa.text("""
            CREATE TABLE matches (
                id      TEXT PRIMARY KEY,
                cv_id   TEXT NOT NULL,
                seen_at TIMESTAMP
            )
        """))
    with Session(engine) as session:
        yield session
    engine.dispose()


def _add_cv(session: Session, user_id: str, name: str | None) -> str:
    cid = str(uuid.uuid4())
    session.execute(
        sa.text("INSERT INTO cvs (id, user_id, name) VALUES (:id, :user_id, :name)"),
        {"id": cid, "user_id": user_id, "name": name},
    )
    return cid


def _add_match(session: Session, cv_id: str, seen: bool) -> None:
    session.execute(
        sa.text("INSERT INTO matches (id, cv_id, seen_at) VALUES (:id, :cv_id, :seen_at)"),
        {"id": str(uuid.uuid4()), "cv_id": cv_id, "seen_at": "2026-01-01 00:00:00.000000" if seen else None},
    )


def test_count_unseen_matches_by_cv_excludes_cv_without_match(db_session: Session) -> None:
    _add_cv(db_session, "user-1", "CV solo")
    db_session.flush()

    counts = _mod._count_unseen_matches_by_cv(db_session, "user-1")

    assert counts == []


def test_count_unseen_matches_by_cv_excludes_already_seen_match(db_session: Session) -> None:
    cv_id = _add_cv(db_session, "user-1", "CV vu")
    _add_match(db_session, cv_id, seen=True)
    db_session.flush()

    counts = _mod._count_unseen_matches_by_cv(db_session, "user-1")

    assert counts == []


def test_count_unseen_matches_by_cv_counts_correctly_across_multiple_cvs(db_session: Session) -> None:
    cv_a = _add_cv(db_session, "user-1", "CV A")
    cv_b = _add_cv(db_session, "user-1", "CV B")
    _add_match(db_session, cv_a, seen=False)
    _add_match(db_session, cv_a, seen=False)
    _add_match(db_session, cv_a, seen=True)
    _add_match(db_session, cv_b, seen=False)
    db_session.flush()

    counts = dict(_mod._count_unseen_matches_by_cv(db_session, "user-1"))

    assert counts == {"CV A": 2, "CV B": 1}


# ---------------------------------------------------------------------------
# _select_profiles_to_notify — mocked, see module docstring for why
# ---------------------------------------------------------------------------


def test_select_profiles_to_notify_returns_whatever_the_any_filter_matches(mocker: MockerFixture) -> None:
    session = MagicMock()
    profile = object()
    session.execute.return_value.scalars.return_value = [profile]

    result = _mod._select_profiles_to_notify(session, today_isoweekday=3)

    assert result == [profile]
    session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# main() — orchestration
# ---------------------------------------------------------------------------


class TestMainOrchestration:
    """Covers main()'s wiring: scheduling gate, per-profile skips, and failure isolation."""

    def _mock_common_deps(self, mocker: MockerFixture) -> None:
        mocker.patch.object(_mod, "configure_telemetry")
        mocker.patch.object(_mod, "run_migrations")
        mocker.patch.object(_mod, "get_session", _session_cm(MagicMock()))
        mocker.patch.object(_mod, "EmailClient")
        mocker.patch.object(_mod, "DefaultAzureCredential")
        mocker.patch.object(_mod, "_is_scheduled_local_hour", return_value=True)

    def test_nothing_sent_outside_scheduled_window(self, mocker: MockerFixture) -> None:
        self._mock_common_deps(mocker)
        mocker.patch.object(_mod, "_is_scheduled_local_hour", return_value=False)
        select_profiles = mocker.patch.object(_mod, "_select_profiles_to_notify")

        _mod.main()

        select_profiles.assert_not_called()

    def test_profile_without_email_is_skipped_and_counted(self, mocker: MockerFixture) -> None:
        self._mock_common_deps(mocker)
        profile = SimpleNamespace(email=None, user_id="user-1")
        mocker.patch.object(_mod, "_select_profiles_to_notify", return_value=[profile])
        count_unseen = mocker.patch.object(_mod, "_count_unseen_matches_by_cv")
        send_digest = mocker.patch.object(_mod, "_send_digest")
        mock_logger_info = mocker.patch.object(_mod.logger, "info")

        _mod.main()

        count_unseen.assert_not_called()
        send_digest.assert_not_called()
        mock_logger_info.assert_any_call(
            "notifications_completed",
            sent=0,
            skipped_no_email=1,
            skipped_no_unseen_offers=0,
            failed=0,
        )

    def test_profile_without_unseen_offers_is_skipped_without_sending(self, mocker: MockerFixture) -> None:
        self._mock_common_deps(mocker)
        profile = SimpleNamespace(email="user@example.com", user_id="user-1")
        mocker.patch.object(_mod, "_select_profiles_to_notify", return_value=[profile])
        mocker.patch.object(_mod, "_count_unseen_matches_by_cv", return_value=[])
        send_digest = mocker.patch.object(_mod, "_send_digest")
        mock_logger_info = mocker.patch.object(_mod.logger, "info")

        _mod.main()

        send_digest.assert_not_called()
        mock_logger_info.assert_any_call(
            "notifications_completed",
            sent=0,
            skipped_no_email=0,
            skipped_no_unseen_offers=1,
            failed=0,
        )

    def test_individual_send_failure_is_counted_without_stopping_the_loop(
        self, mocker: MockerFixture
    ) -> None:
        self._mock_common_deps(mocker)
        profile_1 = SimpleNamespace(email="a@example.com", user_id="user-1")
        profile_2 = SimpleNamespace(email="b@example.com", user_id="user-2")
        mocker.patch.object(
            _mod, "_select_profiles_to_notify", return_value=[profile_1, profile_2]
        )
        mocker.patch.object(_mod, "_count_unseen_matches_by_cv", return_value=[("CV A", 2)])
        mocker.patch.object(_mod, "_build_email_content", return_value=("text", "html"))
        send_digest = mocker.patch.object(
            _mod, "_send_digest", side_effect=[AzureError("send failed"), None]
        )
        mock_logger_info = mocker.patch.object(_mod.logger, "info")

        _mod.main()

        assert send_digest.call_count == 2
        mock_logger_info.assert_any_call(
            "notifications_completed",
            sent=1,
            skipped_no_email=0,
            skipped_no_unseen_offers=0,
            failed=1,
        )
