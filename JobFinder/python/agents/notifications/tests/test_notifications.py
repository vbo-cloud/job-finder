"""Unit tests for notifications/main.py.

Tests use an in-memory SQLite DB created with raw DDL for _load_cv_digest_entries_by_user,
same approach as agents/cleanup/tests/test_cleanup.py: only the columns the query
actually touches (cvs.id/user_id/name, offers.id/title/company/location/department/
contract_type, matches.id/cv_id/offer_id/score/seen_at) are created, skipping the
pgvector `embedding` column and the rest of the real schema.

_select_profiles_to_notify relies on UserProfile.notification_days.any(...), which
SQLAlchemy compiles to PostgreSQL's `<value> = ANY(notification_days)` — a construct
SQLite's ARRAY-less dialect cannot execute. That function is therefore covered by
mocking session.execute directly rather than against a real DB, the same pattern
cv_analysis/match_analysis already use for mocking _openai_client instead of a real
OpenAI client.

main()'s orchestration tests mock _load_recipients_and_entries directly rather than its
two DB-touching components — it is the single seam between the DB-facing half of main()
(one query batched across every opted-in profile, see its docstring for why) and the
per-recipient send loop under test here.
"""

import importlib.util
import sys
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from azure.core.exceptions import AzureError
from pytest_mock import MockerFixture
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

_NOTIFICATIONS_DIR = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("notifications_main", _NOTIFICATIONS_DIR / "main.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["notifications_main"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]


def _make_cv_entry(**overrides: object) -> "_mod.CvDigestEntry":
    """Build a CvDigestEntry with sensible defaults, overridable per test.

    Args:
        **overrides: Field values to override on top of the defaults below.

    Returns:
        A CvDigestEntry ready to pass into _build_email_content/_build_digest_subject.
    """
    defaults = {
        "cv_name": "Alternance Cloud",
        "unseen_count": 3,
        "top_offer_title": "Alternant DevOps",
        "top_offer_company": "Doctolib",
        "top_offer_location": "Paris (75)",
        "top_offer_contract_type": "Alternance",
        "top_offer_score_pct": 94,
    }
    defaults.update(overrides)
    return _mod.CvDigestEntry(**defaults)


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
    entry = _make_cv_entry(cv_name="Alternance Cloud", unseen_count=3)

    plain_text, html_body = _mod._build_email_content(
        None, [3], 3, [entry], "https://jobfinder.example"
    )

    assert "Alternance Cloud : 3 nouvelle(s) offre(s)" in plain_text
    assert "Alternance Cloud : 3 nouvelle(s) offre(s)" in html_body
    assert "https://jobfinder.example" in plain_text
    assert "https://jobfinder.example" in html_body


def test_build_email_content_uses_placeholder_for_unnamed_cv() -> None:
    entry = _make_cv_entry(cv_name=None, unseen_count=1)

    plain_text, html_body = _mod._build_email_content(
        None, [3], 3, [entry], "https://jobfinder.example"
    )

    assert "CV sans nom : 1 nouvelle(s) offre(s)" in plain_text
    assert "CV sans nom : 1 nouvelle(s) offre(s)" in html_body


def test_build_email_content_lists_every_cv() -> None:
    entries = [_make_cv_entry(cv_name="CV A", unseen_count=2), _make_cv_entry(cv_name="CV B", unseen_count=5)]

    plain_text, _ = _mod._build_email_content(None, [3], 3, entries, "https://jobfinder.example")

    assert "CV A : 2 nouvelle(s) offre(s)" in plain_text
    assert "CV B : 5 nouvelle(s) offre(s)" in plain_text


def test_build_email_content_escapes_cv_name_in_html() -> None:
    """A CV name containing HTML-significant characters must not break the markup."""
    entry = _make_cv_entry(cv_name="<script>", unseen_count=1)

    _, html_body = _mod._build_email_content(None, [3], 3, [entry], "https://jobfinder.example")

    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body


def test_build_email_content_escapes_offer_title_and_company_in_html() -> None:
    """Offer.title/Offer.company are free text (like CV.name) — must be escaped too."""
    entry = _make_cv_entry(top_offer_title="<b>Dev</b>", top_offer_company="<script>Corp</script>")

    _, html_body = _mod._build_email_content(None, [3], 3, [entry], "https://jobfinder.example")

    assert "<b>Dev</b>" not in html_body
    assert "&lt;b&gt;Dev&lt;/b&gt;" in html_body
    assert "<script>Corp</script>" not in html_body
    assert "&lt;script&gt;Corp&lt;/script&gt;" in html_body


def test_build_email_content_greets_generically_without_display_name() -> None:
    plain_text, html_body = _mod._build_email_content(
        None, [3], 3, [_make_cv_entry()], "https://jobfinder.example"
    )

    assert "Bonjour," in plain_text
    assert "Bonjour," in html_body
    assert "Bonjour None" not in plain_text
    assert "Bonjour None" not in html_body


def test_build_email_content_personalizes_greeting_with_display_name() -> None:
    plain_text, html_body = _mod._build_email_content(
        "Camille", [3], 3, [_make_cv_entry()], "https://jobfinder.example"
    )

    assert "Bonjour Camille," in plain_text
    assert "Bonjour Camille," in html_body


def test_build_email_content_escapes_display_name_in_html() -> None:
    """display_name is a best-effort JWT claim (free text) — must be escaped in HTML, same
    as CV.name/Offer.title/Offer.company. The plain-text greeting stays unescaped."""
    plain_text, html_body = _mod._build_email_content(
        "<script>", [3], 3, [_make_cv_entry()], "https://jobfinder.example"
    )

    assert "Bonjour <script>," in plain_text
    assert "<script>" not in html_body
    assert "Bonjour &lt;script&gt;," in html_body


def test_build_email_content_omits_location_separator_when_offer_location_is_blank() -> None:
    entry = _make_cv_entry(top_offer_location="", top_offer_company="Doctolib", top_offer_contract_type="CDI")

    plain_text, html_body = _mod._build_email_content(None, [3], 3, [entry], "https://jobfinder.example")

    assert "Doctolib · CDI" in plain_text
    assert "Doctolib · CDI" in html_body
    assert "Doctolib —" not in plain_text
    assert "Doctolib —" not in html_body


# ---------------------------------------------------------------------------
# _build_digest_subject
# ---------------------------------------------------------------------------


def test_build_digest_subject_singular_for_exactly_one_unseen_offer() -> None:
    subject = _mod._build_digest_subject([_make_cv_entry(unseen_count=1, top_offer_score_pct=94)])

    assert "Une offre" in subject
    assert "94" in subject


def test_build_digest_subject_plural_for_several_unseen_offers() -> None:
    entries = [
        _make_cv_entry(unseen_count=5, top_offer_score_pct=94),
        _make_cv_entry(unseen_count=2, top_offer_score_pct=78),
    ]

    subject = _mod._build_digest_subject(entries)

    assert "7" in subject
    assert "94" in subject


def test_build_digest_subject_handles_defensive_zero_offers_case() -> None:
    """main() never reaches this (it skips recipients with no unseen offers first), but
    the function itself must not crash on an empty list."""
    subject = _mod._build_digest_subject([])

    assert "0" in subject


def test_hero_copy_uses_singular_heading_for_exactly_one_unseen_offer() -> None:
    heading, _ = _mod._hero_copy(total_unseen=1, best_score=94)

    assert "Une nouvelle offre" in heading


def test_hero_copy_uses_plural_heading_for_several_unseen_offers() -> None:
    heading, lead_html = _mod._hero_copy(total_unseen=7, best_score=94)

    assert "7 nouvelles offres" in heading
    assert "94" in lead_html


# ---------------------------------------------------------------------------
# reminder calendar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("isoweekday", range(1, 8))
def test_calendar_day_style_today_wins_even_when_also_selected(isoweekday: int) -> None:
    band, _, _, weight = _mod._calendar_day_style(
        isoweekday, notification_days=[isoweekday], today_isoweekday=isoweekday
    )

    assert band == "#ef4444"
    assert weight == "800"


@pytest.mark.parametrize("isoweekday", range(1, 8))
def test_calendar_day_style_selected_and_not_today(isoweekday: int) -> None:
    other_day = isoweekday % 7 + 1

    band, _, _, weight = _mod._calendar_day_style(
        isoweekday, notification_days=[isoweekday], today_isoweekday=other_day
    )

    assert band == "#f2f2f4"
    assert weight == "800"


@pytest.mark.parametrize("isoweekday", range(1, 8))
def test_calendar_day_style_not_selected_and_not_today(isoweekday: int) -> None:
    other_day = isoweekday % 7 + 1

    band, _, _, weight = _mod._calendar_day_style(
        isoweekday, notification_days=[], today_isoweekday=other_day
    )

    assert band == "#4a4a54"
    assert weight == "700"


def test_render_calendar_text_marks_today_with_brackets() -> None:
    text = _mod._render_calendar_text([1, 3, 5, 7], today_isoweekday=7)

    assert text == "Rappels programmés : Lun · Mer · Ven · [Dim] (aujourd'hui)"


# ---------------------------------------------------------------------------
# _load_cv_digest_entries_by_user (real SQLite, minimal schema)
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """In-memory SQLite session with the minimal schema required by _load_cv_digest_entries_by_user."""
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
            CREATE TABLE offers (
                id            TEXT PRIMARY KEY,
                title         TEXT NOT NULL,
                company       TEXT NOT NULL,
                location      TEXT NOT NULL,
                department    TEXT,
                contract_type TEXT NOT NULL
            )
        """))
        conn.execute(sa.text("""
            CREATE TABLE matches (
                id       TEXT PRIMARY KEY,
                cv_id    TEXT NOT NULL,
                offer_id TEXT NOT NULL,
                score    REAL NOT NULL,
                seen_at  TIMESTAMP
            )
        """))
    with Session(engine) as session:
        yield session
    engine.dispose()


def _add_cv(session: Session, user_id: str, name: str | None) -> str:
    """Insert a minimal `cvs` row and return its generated id."""
    cid = str(uuid.uuid4())
    session.execute(
        sa.text("INSERT INTO cvs (id, user_id, name) VALUES (:id, :user_id, :name)"),
        {"id": cid, "user_id": user_id, "name": name},
    )
    return cid


def _add_offer(
    session: Session,
    title: str = "Alternant DevOps",
    company: str = "Doctolib",
    location: str = "Paris (75)",
    department: str | None = None,
    contract_type: str = "Alternance",
) -> str:
    """Insert a minimal `offers` row and return its generated id."""
    oid = str(uuid.uuid4())
    session.execute(
        sa.text(
            "INSERT INTO offers (id, title, company, location, department, contract_type) "
            "VALUES (:id, :title, :company, :location, :department, :contract_type)"
        ),
        {
            "id": oid,
            "title": title,
            "company": company,
            "location": location,
            "department": department,
            "contract_type": contract_type,
        },
    )
    return oid


def _add_match(session: Session, cv_id: str, offer_id: str, score: float, seen: bool) -> None:
    """Insert a minimal `matches` row linking the given cv_id and offer_id."""
    session.execute(
        sa.text(
            "INSERT INTO matches (id, cv_id, offer_id, score, seen_at) "
            "VALUES (:id, :cv_id, :offer_id, :score, :seen_at)"
        ),
        {
            "id": str(uuid.uuid4()),
            "cv_id": cv_id,
            "offer_id": offer_id,
            "score": score,
            "seen_at": "2026-01-01 00:00:00.000000" if seen else None,
        },
    )


def test_load_cv_digest_entries_by_user_returns_empty_dict_for_no_user_ids(
    db_session: Session,
) -> None:
    """An empty user_ids list is a no-op — no query issued, empty mapping returned."""
    assert _mod._load_cv_digest_entries_by_user(db_session, []) == {}


def test_load_cv_digest_entries_by_user_excludes_cv_without_match(db_session: Session) -> None:
    _add_cv(db_session, "user-1", "CV solo")
    db_session.flush()

    entries = _mod._load_cv_digest_entries_by_user(db_session, ["user-1"])

    assert entries == {}


def test_load_cv_digest_entries_by_user_excludes_already_seen_match(db_session: Session) -> None:
    cv_id = _add_cv(db_session, "user-1", "CV vu")
    offer_id = _add_offer(db_session)
    _add_match(db_session, cv_id, offer_id, score=0.8, seen=True)
    db_session.flush()

    entries = _mod._load_cv_digest_entries_by_user(db_session, ["user-1"])

    assert entries == {}


def test_load_cv_digest_entries_by_user_picks_top_scoring_unseen_match_and_excludes_seen(
    db_session: Session,
) -> None:
    """Top offer must be the best-scoring *unseen* match — a higher-scoring seen match must
    not win, and the count must not include it either."""
    cv_a = _add_cv(db_session, "user-1", "CV A")
    cv_b = _add_cv(db_session, "user-1", "CV B")
    offer_1 = _add_offer(db_session, title="Offer 1")
    offer_2 = _add_offer(db_session, title="Offer 2")
    offer_3 = _add_offer(db_session, title="Offer 3 (seen, highest score)")
    _add_match(db_session, cv_a, offer_1, score=0.5, seen=False)
    _add_match(db_session, cv_a, offer_2, score=0.7, seen=False)
    _add_match(db_session, cv_a, offer_3, score=0.99, seen=True)
    _add_match(db_session, cv_b, offer_1, score=0.6, seen=False)
    db_session.flush()

    entries = _mod._load_cv_digest_entries_by_user(db_session, ["user-1"])
    by_name = {entry.cv_name: entry for entry in entries["user-1"]}

    assert by_name["CV A"].unseen_count == 2
    assert by_name["CV A"].top_offer_title == "Offer 2"
    assert by_name["CV A"].top_offer_score_pct == 70
    assert by_name["CV B"].unseen_count == 1
    assert by_name["CV B"].top_offer_title == "Offer 1"


def test_load_cv_digest_entries_by_user_orders_cards_by_cv_name_not_insertion_order(
    db_session: Session,
) -> None:
    """The final ORDER BY cv_name makes card order deterministic regardless of DB insertion
    order — CV B is inserted first here, but must still come back after CV A."""
    cv_b = _add_cv(db_session, "user-1", "CV B")
    cv_a = _add_cv(db_session, "user-1", "CV A")
    offer = _add_offer(db_session)
    _add_match(db_session, cv_b, offer, score=0.5, seen=False)
    _add_match(db_session, cv_a, offer, score=0.5, seen=False)
    db_session.flush()

    entries = _mod._load_cv_digest_entries_by_user(db_session, ["user-1"])

    assert [entry.cv_name for entry in entries["user-1"]] == ["CV A", "CV B"]


def test_load_cv_digest_entries_by_user_breaks_score_ties_deterministically(
    db_session: Session,
) -> None:
    """Two unseen matches with an identical score must not make the top-match pick flaky
    across repeated calls — the Match.id tie-break in the window ordering covers this."""
    cv_id = _add_cv(db_session, "user-1", "CV")
    offer_1 = _add_offer(db_session, title="Offer 1")
    offer_2 = _add_offer(db_session, title="Offer 2")
    _add_match(db_session, cv_id, offer_1, score=0.8, seen=False)
    _add_match(db_session, cv_id, offer_2, score=0.8, seen=False)
    db_session.flush()

    first = _mod._load_cv_digest_entries_by_user(db_session, ["user-1"])["user-1"][0].top_offer_title
    second = _mod._load_cv_digest_entries_by_user(db_session, ["user-1"])["user-1"][0].top_offer_title

    assert first == second


def test_load_cv_digest_entries_by_user_batches_across_multiple_users(db_session: Session) -> None:
    """One call covering several user_ids returns each user's own entries, not mixed together."""
    cv_1 = _add_cv(db_session, "user-1", "CV 1")
    cv_2 = _add_cv(db_session, "user-2", "CV 2")
    offer_a = _add_offer(db_session, title="Offer A")
    offer_b = _add_offer(db_session, title="Offer B")
    offer_c = _add_offer(db_session, title="Offer C")
    _add_match(db_session, cv_1, offer_a, score=0.4, seen=False)
    _add_match(db_session, cv_2, offer_b, score=0.5, seen=False)
    _add_match(db_session, cv_2, offer_c, score=0.9, seen=False)
    db_session.flush()

    entries = _mod._load_cv_digest_entries_by_user(db_session, ["user-1", "user-2"])

    assert len(entries["user-1"]) == 1
    assert entries["user-1"][0].unseen_count == 1
    assert len(entries["user-2"]) == 1
    assert entries["user-2"][0].unseen_count == 2
    assert entries["user-2"][0].top_offer_title == "Offer C"


def test_load_cv_digest_entries_by_user_falls_back_to_department_when_location_blank(
    db_session: Session,
) -> None:
    cv_id = _add_cv(db_session, "user-1", "CV")
    offer_id = _add_offer(db_session, location="", department="75 - Paris")
    _add_match(db_session, cv_id, offer_id, score=0.8, seen=False)
    db_session.flush()

    entries = _mod._load_cv_digest_entries_by_user(db_session, ["user-1"])

    assert entries["user-1"][0].top_offer_location == "75 - Paris"


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

    # The mocked session can't execute the query, so inspect the compiled SQL itself
    # to pin down the ANY(notification_days) filter — the actual opt-in selection logic.
    statement = session.execute.call_args.args[0]
    compiled_sql = str(
        statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "3 = ANY (user_profiles.notification_days)" in compiled_sql


# ---------------------------------------------------------------------------
# main() — orchestration
# ---------------------------------------------------------------------------


class TestMainOrchestration:
    """Covers main()'s wiring: scheduling gate, per-recipient skips, and failure isolation."""

    def _mock_common_deps(self, mocker: MockerFixture) -> None:
        """Patch main()'s infra deps shared by every test in this class (telemetry, DB
        migrations, email client, scheduling gate defaulted to "on time")."""
        mocker.patch.object(_mod, "configure_telemetry")
        mocker.patch.object(_mod, "run_migrations")
        mocker.patch.object(_mod, "EmailClient")
        mocker.patch.object(_mod, "DefaultAzureCredential")
        mocker.patch.object(_mod, "_is_scheduled_local_hour", return_value=True)

    def test_nothing_sent_outside_scheduled_window(self, mocker: MockerFixture) -> None:
        self._mock_common_deps(mocker)
        mocker.patch.object(_mod, "_is_scheduled_local_hour", return_value=False)
        load_recipients = mocker.patch.object(_mod, "_load_recipients_and_entries")

        _mod.main()

        load_recipients.assert_not_called()

    def test_recipient_without_email_is_skipped_and_counted(self, mocker: MockerFixture) -> None:
        self._mock_common_deps(mocker)
        recipient = _mod.Recipient(user_id="user-1", email=None, display_name=None, notification_days=[3])
        mocker.patch.object(
            _mod, "_load_recipients_and_entries", return_value=([recipient], {})
        )
        send_digest = mocker.patch.object(_mod, "_send_digest")
        mock_logger_info = mocker.patch.object(_mod.logger, "info")

        _mod.main()

        send_digest.assert_not_called()
        mock_logger_info.assert_any_call(
            "notifications_completed",
            sent=0,
            skipped_no_email=1,
            skipped_no_unseen_offers=0,
            failed=0,
        )

    def test_recipient_without_unseen_offers_is_skipped_without_sending(
        self, mocker: MockerFixture
    ) -> None:
        self._mock_common_deps(mocker)
        recipient = _mod.Recipient(
            user_id="user-1", email="user@example.com", display_name=None, notification_days=[3]
        )
        mocker.patch.object(
            _mod,
            "_load_recipients_and_entries",
            return_value=([recipient], {}),
        )
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
        recipients = [
            _mod.Recipient(user_id="user-1", email="a@example.com", display_name=None, notification_days=[3]),
            _mod.Recipient(user_id="user-2", email="b@example.com", display_name=None, notification_days=[3]),
        ]
        entries_by_user = {
            "user-1": [_make_cv_entry(cv_name="CV A", unseen_count=2)],
            "user-2": [_make_cv_entry(cv_name="CV B", unseen_count=1)],
        }
        mocker.patch.object(
            _mod, "_load_recipients_and_entries", return_value=(recipients, entries_by_user)
        )
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
