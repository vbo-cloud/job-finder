"""Tests for agents/webapp/routers/profile.py.

Covers: GET /profile, PUT /profile (happy path, 404, 500, upsert behaviour).
"""
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
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


def _make_profile() -> MagicMock:
    profile = MagicMock()
    profile.user_id = TEST_USER_ID
    profile.rome_codes = {}
    profile.location = "Paris"
    return profile


@pytest.fixture()
def mock_session() -> MagicMock:
    return MagicMock()


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
        assert body["location"] == "Paris"

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
        "location": "Lyon",
    }

    def test_creates_or_updates_profile_and_returns_it(self, test_client, mock_session):
        profile = _make_profile()
        profile.location = self._PUT_BODY["location"]
        # upsert execute + select scalar_one
        mock_session.execute.return_value.scalar_one.return_value = profile

        resp = test_client.put("/profile", json=self._PUT_BODY)

        assert resp.status_code == 200
        body = resp.json()
        assert body["location"] == "Lyon"
        mock_session.commit.assert_called_once()

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.put("/profile", json=self._PUT_BODY)

        assert resp.status_code == 500
