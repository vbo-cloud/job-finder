"""Tests for agents/webapp/routers/feedback.py.

Covers: POST /feedback happy path (avis/bug subject prefixing, RESSENTI line
including the sentiment-omitted default), email/name fallback when the JWT
omits them, relay failure (502), the not-configured case
(PORTFOLIO_CONTACT_FUNCTION_URL unset), and the profile-lookup DB error (500).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

_PYTHON_DIR = Path(__file__).parent.parent
_WEBAPP_DIR = _PYTHON_DIR / "agents" / "webapp"
for _d in [str(_PYTHON_DIR), str(_WEBAPP_DIR)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

from auth import UserIdentity, get_current_identity  # noqa: E402
from dependencies import get_db  # noqa: E402
from routers.feedback import router  # noqa: E402

TEST_USER_ID = "test-user-feedback"
TEST_EMAIL = "vincent@example.test"
TEST_NAME = "Vincent Test"


@pytest.fixture()
def mock_session() -> MagicMock:
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None
    return session


def _build_client(mock_session, identity: UserIdentity | None = None) -> TestClient:
    ident = identity or UserIdentity(
        user_id=TEST_USER_ID, email=TEST_EMAIL, display_name=TEST_NAME
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_identity] = lambda: ident
    app.dependency_overrides[get_db] = lambda: (yield mock_session)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def test_client(mock_session) -> TestClient:
    return _build_client(mock_session)


@pytest.fixture(autouse=True)
def configured_function_url():
    """Every test opts into a configured URL unless it overrides this itself."""
    with patch("routers.feedback.PORTFOLIO_CONTACT_FUNCTION_URL", "https://fn.example.test/api/sendContactEmail"):
        yield


class TestCreateFeedback:
    def test_relays_bug_report_with_subject_prefix(self, test_client, mock_session):
        with patch("routers.feedback.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            resp = test_client.post(
                "/feedback",
                json={
                    "type": "bug",
                    "subject": "Ça plante",
                    "message": "Détails ici.",
                    "sentiment": "negatif",
                },
            )

        assert resp.status_code == 204
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["subject"] == "JOBFINDER - BUG : Ça plante"
        assert payload["email"] == TEST_EMAIL
        assert payload["name"] == TEST_NAME
        assert payload["message"] == "RESSENTI NEGATIF\n\nDétails ici."

    def test_relays_avis_with_subject_prefix(self, test_client, mock_session):
        with patch("routers.feedback.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            resp = test_client.post(
                "/feedback",
                json={"type": "avis", "subject": "Super app", "message": "Bravo.", "sentiment": "positif"},
            )

        assert resp.status_code == 204
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["subject"] == "JOBFINDER - AVIS : Super app"
        assert kwargs["json"]["message"] == "RESSENTI POSITIF\n\nBravo."

    def test_defaults_to_non_indique_when_sentiment_omitted(self, test_client, mock_session):
        with patch("routers.feedback.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            resp = test_client.post(
                "/feedback", json={"type": "avis", "subject": "s", "message": "m"}
            )

        assert resp.status_code == 204
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["message"] == "RESSENTI NON INDIQUE\n\nm"

    def test_falls_back_to_profile_email_when_jwt_email_missing(self, test_client, mock_session):
        profile = MagicMock()
        profile.email = "stored@example.test"
        profile.display_name = "Stored Name"
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        client = _build_client(
            mock_session,
            identity=UserIdentity(user_id=TEST_USER_ID, email=None, display_name=None),
        )

        with patch("routers.feedback.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            resp = client.post(
                "/feedback", json={"type": "avis", "subject": "s", "message": "m"}
            )

        assert resp.status_code == 204
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["email"] == "stored@example.test"
        assert kwargs["json"]["name"] == "Stored Name"

    def test_falls_back_to_placeholder_email_when_nothing_available(self, test_client, mock_session):
        client = _build_client(
            mock_session,
            identity=UserIdentity(user_id=TEST_USER_ID, email=None, display_name=None),
        )

        with patch("routers.feedback.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            resp = client.post(
                "/feedback", json={"type": "avis", "subject": "s", "message": "m"}
            )

        assert resp.status_code == 204
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["email"] == f"{TEST_USER_ID}@jobfinder.local"
        assert "email indisponible" in kwargs["json"]["message"]

    def test_returns_502_when_relay_fails(self, test_client):
        with patch("routers.feedback.requests.post") as mock_post:
            mock_post.side_effect = requests.RequestException("boom")

            resp = test_client.post(
                "/feedback", json={"type": "bug", "subject": "s", "message": "m"}
            )

        assert resp.status_code == 502

    def test_returns_502_when_not_configured(self, test_client):
        with patch("routers.feedback.PORTFOLIO_CONTACT_FUNCTION_URL", ""):
            resp = test_client.post(
                "/feedback", json={"type": "bug", "subject": "s", "message": "m"}
            )

        assert resp.status_code == 502

    def test_returns_500_on_profile_lookup_db_error(self, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")
        client = _build_client(
            mock_session,
            identity=UserIdentity(user_id=TEST_USER_ID, email=None, display_name=None),
        )

        resp = client.post("/feedback", json={"type": "bug", "subject": "s", "message": "m"})

        assert resp.status_code == 500

    @pytest.mark.parametrize("field", ["subject", "message"])
    def test_rejects_whitespace_only_required_field(self, test_client, field):
        body = {"type": "bug", "subject": "s", "message": "m"}
        body[field] = "   "

        resp = test_client.post("/feedback", json=body)

        assert resp.status_code == 422
