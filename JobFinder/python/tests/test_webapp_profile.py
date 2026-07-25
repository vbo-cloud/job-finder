"""Tests for agents/webapp/routers/profile.py.

Covers: GET /profile, PUT /profile (happy path, 404, 500, partial-update
upsert behaviour, intent_embedding recomputation, start-matching re-trigger on
intent change), DELETE /profile (account erasure).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from azure.servicebus.exceptions import ServiceBusError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

_PYTHON_DIR = Path(__file__).parent.parent
_WEBAPP_DIR = _PYTHON_DIR / "agents" / "webapp"
for _d in [str(_PYTHON_DIR), str(_WEBAPP_DIR)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

from auth import UserIdentity, get_current_identity, get_current_user  # noqa: E402
from dependencies import get_db  # noqa: E402
from routers.profile import router  # noqa: E402

TEST_USER_ID = "test-user-profile"
TEST_EMAIL = "vincent@example.test"
TEST_NAME = "Vincent Test"
_FAKE_EMBEDDING = [0.1] * 1536


def _make_profile() -> MagicMock:
    profile = MagicMock()
    profile.user_id = TEST_USER_ID
    profile.rome_codes = {}
    profile.commune_codes = ["75101", "75102"]
    profile.experience_level = None
    profile.notification_days = [7]
    profile.candidate_description = None
    profile.analysis_credits_remaining = 30
    # ProfileOut declares is_admin (computed field, not a DB column) — without a
    # concrete value, model_validate would read a MagicMock and fail validation.
    profile.is_admin = False
    return profile


@pytest.fixture()
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture(autouse=True)
def mock_send_message() -> MagicMock:
    """Patch the Service Bus dispatch so no test ever reaches Azure."""
    with patch("routers.profile.send_message") as mock:
        yield mock


def _build_client(mock_session, identity: UserIdentity | None = None) -> TestClient:
    ident = identity or UserIdentity(
        user_id=TEST_USER_ID, email=TEST_EMAIL, display_name=TEST_NAME
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ident.user_id
    app.dependency_overrides[get_current_identity] = lambda: ident
    app.dependency_overrides[get_db] = lambda: (yield mock_session)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def test_client(mock_session) -> TestClient:
    return _build_client(mock_session)


# ---------------------------------------------------------------------------
# GET /profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_returns_profile_when_found(self, test_client, mock_session):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        resp = test_client.get("/profile")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == TEST_USER_ID
        assert body["commune_codes"] == ["75101", "75102"]
        assert body["notification_days"] == [7]
        assert body["analysis_credits_remaining"] == 30

    def test_creates_profile_with_defaults_on_first_get(self, test_client, mock_session):
        """A user who reaches GET /profile before ever uploading a CV or calling
        PUT /profile must get their profile created with default values —
        including the 30 welcome credits — rather than a 404."""
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mock_session.execute.return_value.scalar_one.return_value = profile

        resp = test_client.get("/profile")

        assert resp.status_code == 200
        body = resp.json()
        assert body["analysis_credits_remaining"] == 30
        assert body["notification_days"] == [7]
        mock_session.commit.assert_called_once()

    def test_does_not_create_when_profile_exists(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = _make_profile()

        resp = test_client.get("/profile")

        assert resp.status_code == 200
        mock_session.commit.assert_not_called()

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.get("/profile")

        assert resp.status_code == 500

    def test_is_admin_false_for_regular_user(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = _make_profile()

        resp = test_client.get("/profile")

        assert resp.status_code == 200
        assert resp.json()["is_admin"] is False

    def test_is_admin_true_when_user_in_admin_list(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = _make_profile()

        with patch("auth.ADMIN_USER_IDS", frozenset({TEST_USER_ID})):
            resp = test_client.get("/profile")

        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True


# ---------------------------------------------------------------------------
# PUT /profile
# ---------------------------------------------------------------------------


class TestPutProfile:
    _PUT_BODY = {
        "commune_codes": ["69381", "69382"],
    }

    def test_creates_or_updates_profile_and_returns_it(self, test_client, mock_session):
        profile = _make_profile()
        profile.commune_codes = self._PUT_BODY["commune_codes"]
        # upsert execute + select scalar_one
        mock_session.execute.return_value.scalar_one.return_value = profile

        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put("/profile", json=self._PUT_BODY)

        assert resp.status_code == 200
        body = resp.json()
        assert body["commune_codes"] == ["69381", "69382"]
        mock_session.commit.assert_called_once()
        mock_embed.assert_not_called()

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.put("/profile", json=self._PUT_BODY)

        assert resp.status_code == 500

    def test_only_commune_codes_does_not_recompute_intent(self, test_client, mock_session):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put("/profile", json={"commune_codes": ["75101"]})

        assert resp.status_code == 200
        mock_embed.assert_not_called()

    def test_only_notification_days_does_not_recompute_intent(self, test_client, mock_session):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put("/profile", json={"notification_days": [1, 3, 5]})

        assert resp.status_code == 200
        mock_embed.assert_not_called()

    def test_notification_days_empty_list_disables_without_reverting_to_default(
        self, test_client, mock_session
    ):
        profile = _make_profile()
        profile.notification_days = []
        mock_session.execute.return_value.scalar_one.return_value = profile

        resp = test_client.put("/profile", json={"notification_days": []})

        assert resp.status_code == 200
        assert resp.json()["notification_days"] == []
        stmt = mock_session.execute.call_args_list[0].args[0]
        set_clause = dict(stmt._post_values_clause.update_values_to_set)
        assert set_clause["notification_days"] == []

    def test_notification_days_absent_defaults_insert_values_to_sunday(
        self, test_client, mock_session
    ):
        """A PUT that never mentions notification_days (e.g. commune_codes
        only) must still carry the [7] default in the INSERT .values() clause
        — `updated.get("notification_days") or []` would collapse "key
        absent" into "[]" here, the exact trap documented in
        routers/profile.py, and clobber a brand-new profile's default on the
        insert path."""
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        resp = test_client.put("/profile", json={"commune_codes": ["75101"]})

        assert resp.status_code == 200
        stmt = mock_session.execute.call_args_list[0].args[0]
        insert_values = stmt.compile().params
        assert insert_values["notification_days"] == [7]

    def test_experience_and_candidate_description_recomputes_intent_embedding(
        self, test_client, mock_session
    ):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        with patch("routers.profile.embed", return_value=[_FAKE_EMBEDDING]) as mock_embed:
            resp = test_client.put(
                "/profile",
                json={"experience_level": "0-2", "candidate_description": "profil autodidacte"},
            )

        assert resp.status_code == 200
        mock_embed.assert_called_once_with(["profil autodidacte"])

    @pytest.mark.parametrize("experience_level", ["0-2", "2-5", "5+"])
    def test_experience_level_alone_never_recomputes_embedding(
        self, test_client, mock_session, experience_level
    ):
        """experience_level only feeds the matching malus, never the embedded
        text — setting it alone (no candidate_description change) must never
        call embed()."""
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put("/profile", json={"experience_level": experience_level})

        assert resp.status_code == 200
        mock_embed.assert_not_called()

    def test_partial_put_preserves_existing_candidate_description_in_intent(
        self, test_client, mock_session
    ):
        """A PUT that only clears experience_level, with candidate_description
        unchanged, must not recompute the embedding at all — and must not
        overwrite the already-stored intent_embedding in the upsert."""
        profile = _make_profile()
        profile.candidate_description = "profil autodidacte"
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put("/profile", json={"experience_level": None})

        assert resp.status_code == 200
        mock_embed.assert_not_called()
        # call 0 is the existing-row lookup for the intent fallback, call 1 is
        # the upsert itself (see put_profile).
        stmt = mock_session.execute.call_args_list[1].args[0]
        set_clause = dict(stmt._post_values_clause.update_values_to_set)
        assert "intent_embedding" not in set_clause

    def test_intent_fields_present_but_empty_clears_embedding_without_calling_embed(
        self, test_client, mock_session
    ):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put(
                "/profile",
                json={
                    "experience_level": None,
                    "candidate_description": None,
                },
            )

        assert resp.status_code == 200
        mock_embed.assert_not_called()

    def test_empty_body_uses_on_conflict_do_nothing_without_error(self, test_client, mock_session):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put("/profile", json={})

        assert resp.status_code == 200
        mock_embed.assert_not_called()

    def test_candidate_description_over_1000_chars_returns_422(self, test_client, mock_session):
        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put("/profile", json={"candidate_description": "a" * 1001})

        assert resp.status_code == 422
        mock_embed.assert_not_called()

    def test_intent_change_dispatches_start_matching(
        self, test_client, mock_session, mock_send_message
    ):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed", return_value=[_FAKE_EMBEDDING]):
            resp = test_client.put(
                "/profile",
                json={"experience_level": "2-5", "candidate_description": "profil autodidacte"},
            )

        assert resp.status_code == 200
        mock_send_message.assert_called_once()
        queue, body = mock_send_message.call_args.args
        assert queue == "start-matching"
        assert body["trigger"] == "profile_update"
        assert body["rome_codes"] == []

    def test_experience_level_alone_still_dispatches_start_matching(
        self, test_client, mock_session, mock_send_message
    ):
        """experience_level alone must still re-trigger matching (the malus
        depends on it) even though it no longer recomputes the embedding —
        the two triggers are decoupled, not both suppressed together."""
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put("/profile", json={"experience_level": "2-5"})

        assert resp.status_code == 200
        mock_embed.assert_not_called()
        mock_send_message.assert_called_once()
        queue, body = mock_send_message.call_args.args
        assert queue == "start-matching"

    def test_unchanged_intent_values_do_not_dispatch_start_matching(
        self, test_client, mock_session, mock_send_message
    ):
        profile = _make_profile()
        profile.experience_level = "2-5"
        profile.candidate_description = "profil autodidacte"
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed", return_value=[_FAKE_EMBEDDING]):
            resp = test_client.put(
                "/profile",
                json={"experience_level": "2-5", "candidate_description": "profil autodidacte"},
            )

        assert resp.status_code == 200
        mock_send_message.assert_not_called()

    def test_commune_codes_only_does_not_dispatch_start_matching(
        self, test_client, mock_session, mock_send_message
    ):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        resp = test_client.put("/profile", json={"commune_codes": ["75101"]})

        assert resp.status_code == 200
        mock_send_message.assert_not_called()

    def test_put_refreshes_identity_claims_in_upsert(self, test_client, mock_session):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        resp = test_client.put("/profile", json={"commune_codes": ["75101"]})

        assert resp.status_code == 200
        stmt = mock_session.execute.call_args_list[0].args[0]
        # _post_values_clause is SQLAlchemy-private but stable: it holds the
        # ON CONFLICT DO UPDATE SET pairs passed to on_conflict_do_update(set_=...).
        set_clause = dict(stmt._post_values_clause.update_values_to_set)
        assert set_clause["email"] == TEST_EMAIL
        assert set_clause["display_name"] == TEST_NAME

    def test_put_with_claimless_token_does_not_clobber_stored_identity(self, mock_session):
        client = _build_client(
            mock_session,
            UserIdentity(user_id=TEST_USER_ID, email=None, display_name=None),
        )
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        resp = client.put("/profile", json={"commune_codes": ["75101"]})

        assert resp.status_code == 200
        stmt = mock_session.execute.call_args_list[0].args[0]
        set_clause = dict(stmt._post_values_clause.update_values_to_set)
        assert "email" not in set_clause
        assert "display_name" not in set_clause

    def test_start_matching_dispatch_failure_does_not_fail_request(
        self, test_client, mock_session, mock_send_message
    ):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile
        mock_send_message.side_effect = ServiceBusError("Service Bus unavailable")

        with patch("routers.profile.embed", return_value=[_FAKE_EMBEDDING]):
            resp = test_client.put("/profile", json={"experience_level": "5+"})

        assert resp.status_code == 200
        mock_send_message.assert_called_once()

    def test_description_change_stamps_description_updated_at(self, test_client, mock_session):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed", return_value=[_FAKE_EMBEDDING]):
            resp = test_client.put(
                "/profile", json={"candidate_description": "profil autodidacte"}
            )

        assert resp.status_code == 200
        stmt = mock_session.execute.call_args_list[1].args[0]
        set_clause = dict(stmt._post_values_clause.update_values_to_set)
        assert set_clause["description_updated_at"] is not None

    def test_first_time_description_stamps_description_updated_at_on_insert_path(
        self, test_client, mock_session
    ):
        """No existing profile row (existing = None, the brand-new-user path):
        description_changed is computed against that None fallback, so the
        INSERT .values() clause must carry description_updated_at too — not
        just the ON CONFLICT UPDATE set_ clause covered by the test above."""
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mock_session.execute.return_value.scalar_one.return_value = profile

        with patch("routers.profile.embed", return_value=[_FAKE_EMBEDDING]):
            resp = test_client.put(
                "/profile", json={"candidate_description": "profil autodidacte"}
            )

        assert resp.status_code == 200
        stmt = mock_session.execute.call_args_list[1].args[0]
        insert_values = stmt.compile().params
        assert insert_values["description_updated_at"] is not None

    def test_experience_level_alone_does_not_stamp_description_updated_at(
        self, test_client, mock_session
    ):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed") as mock_embed:
            resp = test_client.put("/profile", json={"experience_level": "2-5"})

        assert resp.status_code == 200
        mock_embed.assert_not_called()
        stmt = mock_session.execute.call_args_list[1].args[0]
        set_clause = dict(stmt._post_values_clause.update_values_to_set)
        assert "description_updated_at" not in set_clause

    def test_unchanged_description_value_does_not_stamp_description_updated_at(
        self, test_client, mock_session
    ):
        profile = _make_profile()
        profile.candidate_description = "profil autodidacte"
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed", return_value=[_FAKE_EMBEDDING]):
            resp = test_client.put(
                "/profile", json={"candidate_description": "profil autodidacte"}
            )

        assert resp.status_code == 200
        stmt = mock_session.execute.call_args_list[1].args[0]
        set_clause = dict(stmt._post_values_clause.update_values_to_set)
        assert "description_updated_at" not in set_clause


# ---------------------------------------------------------------------------
# POST /profile/credits/refill
# ---------------------------------------------------------------------------


class TestRefillCredits:
    _ADMIN_PATCH = patch("auth.ADMIN_USER_IDS", frozenset({TEST_USER_ID}))

    def test_returns_403_for_non_admin_without_touching_db(self, test_client, mock_session):
        resp = test_client.post("/profile/credits/refill")

        assert resp.status_code == 403
        mock_session.execute.assert_not_called()

    def test_admin_refill_returns_new_balance_and_commits(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = 40

        with self._ADMIN_PATCH:
            resp = test_client.post("/profile/credits/refill")

        assert resp.status_code == 200
        assert resp.json() == {"analysis_credits_remaining": 40}
        mock_session.commit.assert_called_once()

    def test_returns_404_when_admin_has_no_profile(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        with self._ADMIN_PATCH:
            resp = test_client.post("/profile/credits/refill")

        assert resp.status_code == 404
        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        with self._ADMIN_PATCH:
            resp = test_client.post("/profile/credits/refill")

        assert resp.status_code == 500
        mock_session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# DELETE /profile
# ---------------------------------------------------------------------------


class TestDeleteAccount:
    def test_no_cvs_is_idempotent_and_returns_204(self, test_client, mock_session):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        with patch("routers.profile._delete_cv") as mock_delete_cv:
            resp = test_client.delete("/profile")

        assert resp.status_code == 204
        mock_delete_cv.assert_not_called()
        mock_session.commit.assert_called_once()

    def test_deletes_every_cv_owned_by_user(self, test_client, mock_session):
        cv1, cv2 = MagicMock(), MagicMock()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [cv1, cv2]

        with patch("routers.profile._delete_cv") as mock_delete_cv:
            resp = test_client.delete("/profile")

        assert resp.status_code == 204
        assert mock_delete_cv.call_count == 2
        mock_delete_cv.assert_any_call(mock_session, cv1, TEST_USER_ID)
        mock_delete_cv.assert_any_call(mock_session, cv2, TEST_USER_ID)
        mock_session.commit.assert_called_once()

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        with patch("routers.profile._delete_cv") as mock_delete_cv:
            resp = test_client.delete("/profile")

        assert resp.status_code == 500
        mock_delete_cv.assert_not_called()
