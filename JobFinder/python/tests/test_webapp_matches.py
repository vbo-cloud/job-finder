"""Tests for agents/webapp/routers/matches.py.

A minimal FastAPI test app is created here (no lifespan, no run_migrations)
with dependency overrides for get_current_user and get_db.

Covers: GET /matches, GET /matches/cv/{cv_id}.
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
from routers.matches import router  # noqa: E402

TEST_USER_ID = "test-user-abc123"
TEST_CV_ID = uuid.uuid4()


def _make_offer() -> MagicMock:
    offer = MagicMock()
    offer.id = uuid.uuid4()
    offer.ft_id = "FT-001"
    offer.title = "Développeur Python"
    offer.company = "ACME"
    offer.location = "Paris (75)"
    offer.contract_type = "CDI"
    offer.description = "Description complète de l'offre de test."
    offer.salary = None
    offer.rome_code = "M1805"
    offer.skills = []
    offer.expires_at = None
    return offer


def _make_match(score: float = 0.85) -> MagicMock:
    match = MagicMock()
    match.score = score
    match.offer = _make_offer()
    return match


def _make_profile(rome_codes: dict | None = None) -> MagicMock:
    profile = MagicMock()
    profile.rome_codes = rome_codes or {
        "M1805": {"cv_ids": [str(TEST_CV_ID)], "label": "Dev info"}
    }
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
# GET /matches
# ---------------------------------------------------------------------------


class TestGetMatches:
    def test_returns_rome_codes_and_matches_when_profile_exists(
        self, test_client, mock_session
    ):
        profile = _make_profile()
        match = _make_match(0.9)
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        body = resp.json()
        assert "M1805" in body["rome_codes"]
        assert len(body["matches"]) == 1
        assert body["matches"][0]["score"] == pytest.approx(0.9)

    def test_returns_empty_rome_codes_when_no_profile(self, test_client, mock_session):
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": None}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        body = resp.json()
        assert body["rome_codes"] == {}
        assert body["matches"] == []

    def test_returns_empty_matches_list_when_no_matches(self, test_client, mock_session):
        profile = _make_profile()
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]

        resp = test_client.get("/matches")

        assert resp.status_code == 200
        assert resp.json()["matches"] == []

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.get("/matches")

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /matches/cv/{cv_id}
# ---------------------------------------------------------------------------


class TestGetMatchesForCv:
    def test_returns_matches_when_cv_found(self, test_client, mock_session):
        cv = MagicMock()
        cv.id = TEST_CV_ID
        profile = _make_profile()
        match = _make_match(0.75)
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"scalars.return_value.all.return_value": [match]}),
        ]

        resp = test_client.get(f"/matches/cv/{TEST_CV_ID}")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["matches"]) == 1

    def test_returns_404_when_cv_not_found_or_not_owned(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.get(f"/matches/cv/{uuid.uuid4()}")

        assert resp.status_code == 404

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.get(f"/matches/cv/{TEST_CV_ID}")

        assert resp.status_code == 500
