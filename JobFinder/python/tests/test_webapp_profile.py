"""Tests for agents/webapp/routers/profile.py.

Covers: GET /profile, PUT /profile (happy path, 404, 500, partial-update
upsert behaviour, intent_embedding recomputation, offer-ready re-trigger on
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

from auth import get_current_user  # noqa: E402
from dependencies import get_db  # noqa: E402
from routers.profile import router  # noqa: E402

TEST_USER_ID = "test-user-profile"
_FAKE_EMBEDDING = [0.1] * 1536


def _make_profile() -> MagicMock:
    profile = MagicMock()
    profile.user_id = TEST_USER_ID
    profile.rome_codes = {}
    profile.commune_codes = ["75101", "75102"]
    profile.experience_level = None
    profile.candidate_description = None
    profile.analysis_credits_remaining = 30
    return profile


@pytest.fixture()
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture(autouse=True)
def mock_send_message() -> MagicMock:
    """Patch the Service Bus dispatch so no test ever reaches Azure."""
    with patch("routers.profile.send_message") as mock:
        yield mock


@pytest.fixture()
def test_client(mock_session) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID
    app.dependency_overrides[get_db] = lambda: (yield mock_session)
    return TestClient(app, raise_server_exceptions=False)


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
        assert body["analysis_credits_remaining"] == 30

    def test_returns_404_when_profile_not_found(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.get("/profile")

        assert resp.status_code == 404

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.get("/profile")

        assert resp.status_code == 500


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
        mock_embed.assert_called_once_with(
            ["Profil junior/débutant, 0 à 2 ans d'expérience\nprofil autodidacte"]
        )

    @pytest.mark.parametrize(
        ("experience_level", "expected_text"),
        [
            ("0-2", "Profil junior/débutant, 0 à 2 ans d'expérience"),
            ("2-5", "Profil confirmé, 2 à 5 ans d'expérience"),
            ("5+", "Profil senior, 5 ans d'expérience et plus"),
        ],
    )
    def test_experience_level_bucket_text(
        self, test_client, mock_session, experience_level, expected_text
    ):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed", return_value=[_FAKE_EMBEDDING]) as mock_embed:
            resp = test_client.put("/profile", json={"experience_level": experience_level})

        assert resp.status_code == 200
        mock_embed.assert_called_once_with([expected_text])

    def test_partial_put_preserves_existing_candidate_description_in_intent(
        self, test_client, mock_session
    ):
        """A PUT that only clears experience_level must not drop the existing
        candidate_description from the recomputed intent_embedding."""
        profile = _make_profile()
        profile.candidate_description = "profil autodidacte"
        mock_session.execute.return_value.scalar_one.return_value = profile
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        with patch("routers.profile.embed", return_value=[_FAKE_EMBEDDING]) as mock_embed:
            resp = test_client.put("/profile", json={"experience_level": None})

        assert resp.status_code == 200
        mock_embed.assert_called_once_with(["profil autodidacte"])

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

    def test_intent_change_dispatches_offer_ready(
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
        assert queue == "offer-ready"
        assert body["trigger"] == "profile_update"
        assert body["rome_codes"] == []

    def test_unchanged_intent_values_do_not_dispatch_offer_ready(
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

    def test_commune_codes_only_does_not_dispatch_offer_ready(
        self, test_client, mock_session, mock_send_message
    ):
        profile = _make_profile()
        mock_session.execute.return_value.scalar_one.return_value = profile

        resp = test_client.put("/profile", json={"commune_codes": ["75101"]})

        assert resp.status_code == 200
        mock_send_message.assert_not_called()

    def test_offer_ready_dispatch_failure_does_not_fail_request(
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
