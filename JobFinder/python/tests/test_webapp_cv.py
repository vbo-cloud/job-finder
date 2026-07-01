"""Tests for agents/webapp/routers/cv.py.

Covers: POST /upload (content-type validation), GET /cv/ (list), GET thumbnail/pdf
(not found), PATCH mark-all-seen (happy path + not found), DELETE (not found).

POST /upload happy path is intentionally excluded: it requires mocking pdfplumber,
embed(), azure blob upload, and send_message() simultaneously — tested manually
via integration tests instead. The content-type rejection path is covered here.

Blob client (_blob_service_client) is patched before the cv router is imported so
the module-level BlobServiceClient(...) constructor never touches real Azure SDK
credentials.
"""
import sys
import uuid
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

_PYTHON_DIR = Path(__file__).parent.parent
_WEBAPP_DIR = _PYTHON_DIR / "agents" / "webapp"
for _d in [str(_PYTHON_DIR), str(_WEBAPP_DIR)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

# Patch the blob service client at module level so cv.py can be imported safely.
_mock_bsc = MagicMock()
with patch("azure.storage.blob.BlobServiceClient", return_value=_mock_bsc):
    from routers import cv as cv_router_module  # noqa: E402
    from routers.cv import router  # noqa: E402

from auth import get_current_user  # noqa: E402
from dependencies import get_db  # noqa: E402

TEST_USER_ID = "test-user-cv"
TEST_CV_ID = uuid.uuid4()


@pytest.fixture()
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def mock_blob_client(mocker) -> MagicMock:
    """Replace the module-level blob service client with a fresh mock per test."""
    mock = MagicMock()
    mocker.patch.object(cv_router_module, "_blob_service_client", mock)
    return mock


@pytest.fixture()
def test_client(mock_session) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID
    app.dependency_overrides[get_db] = lambda: (yield mock_session)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /cv/upload
# ---------------------------------------------------------------------------


class TestUploadCv:
    def test_rejects_non_pdf_content_type(self, test_client):
        resp = test_client.post(
            "/cv/upload",
            files={"file": ("resume.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 422

    def test_rejects_empty_pdf_magic_bytes(self, test_client):
        resp = test_client.post(
            "/cv/upload",
            files={"file": ("resume.pdf", b"NOT_A_PDF_HEADER", "application/pdf")},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /cv/
# ---------------------------------------------------------------------------


class TestListCvs:
    def test_returns_empty_list_when_no_cvs(self, test_client, mock_session):
        mock_session.execute.return_value.all.return_value = []

        resp = test_client.get("/cv/")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_cv_list_items(self, test_client, mock_session):
        cv = MagicMock()
        cv.id = TEST_CV_ID
        cv.name = "Mon CV.pdf"
        cv.status = "done"
        cv.uploaded_at = "2024-01-15T10:00:00+00:00"
        cv.thumbnail_url = None
        # execute().all() returns list of (cv, match_count, unseen_count) tuples
        mock_session.execute.return_value.all.return_value = [(cv, 3, 1)]

        resp = test_client.get("/cv/")

        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "Mon CV.pdf"
        assert items[0]["match_count"] == 3
        assert items[0]["unseen_count"] == 1
        assert items[0]["has_thumbnail"] is False

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.get("/cv/")

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /cv/{cv_id}/thumbnail
# ---------------------------------------------------------------------------


class TestGetCvThumbnail:
    def test_returns_404_when_cv_not_found(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.get(f"/cv/{uuid.uuid4()}/thumbnail")

        assert resp.status_code == 404

    def test_returns_404_when_cv_has_no_thumbnail(self, test_client, mock_session):
        cv = MagicMock()
        cv.thumbnail_url = None
        mock_session.execute.return_value.scalar_one_or_none.return_value = cv

        resp = test_client.get(f"/cv/{TEST_CV_ID}/thumbnail")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /cv/{cv_id}/pdf
# ---------------------------------------------------------------------------


class TestGetCvPdf:
    def test_returns_404_when_cv_not_found(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.get(f"/cv/{uuid.uuid4()}/pdf")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /cv/{cv_id}/mark-all-seen
# ---------------------------------------------------------------------------


class TestMarkAllSeen:
    def test_returns_204_and_commits(self, test_client, mock_session):
        cv = MagicMock()
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(),  # update(Match).where(...) execute
        ]

        resp = test_client.patch(f"/cv/{TEST_CV_ID}/mark-all-seen")

        assert resp.status_code == 204
        mock_session.commit.assert_called_once()

    def test_returns_404_when_cv_not_found(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.patch(f"/cv/{uuid.uuid4()}/mark-all-seen")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /cv/{cv_id}
# ---------------------------------------------------------------------------


class TestDeleteCv:
    def test_returns_404_when_cv_not_found(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.delete(f"/cv/{uuid.uuid4()}")

        assert resp.status_code == 404

    def test_deletes_cv_and_returns_204(
        self, test_client, mock_session, mock_blob_client
    ):
        cv = MagicMock()
        cv.blob_url = "https://account.blob.core.windows.net/cvs/user/cv.pdf"
        cv.thumbnail_url = None
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),   # select CV
            MagicMock(),                                              # delete(Match)
            MagicMock(**{"scalar_one_or_none.return_value": None}),  # select UserProfile
        ]

        resp = test_client.delete(f"/cv/{TEST_CV_ID}")

        assert resp.status_code == 204
        mock_session.delete.assert_called_once_with(cv)
        mock_session.commit.assert_called_once()

    def test_also_deletes_thumbnail_blob_when_present(
        self, test_client, mock_session, mock_blob_client
    ):
        cv = MagicMock()
        cv.blob_url = "https://account.blob.core.windows.net/cvs/user/cv.pdf"
        cv.thumbnail_url = "https://account.blob.core.windows.net/cvs/user/cv_thumb.jpg"
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(),
            MagicMock(**{"scalar_one_or_none.return_value": None}),
        ]

        resp = test_client.delete(f"/cv/{TEST_CV_ID}")

        assert resp.status_code == 204
        blob_container = mock_blob_client.get_blob_client.return_value
        assert blob_container.delete_blob.call_count == 2


# ---------------------------------------------------------------------------
# _remove_cv_from_rome_codes (helper)
# ---------------------------------------------------------------------------


class TestRemoveCvFromRomeCodes:
    def test_removes_cv_id_and_prunes_empty_entry(self):
        cv_id = uuid.uuid4()
        other_cv_id = str(uuid.uuid4())
        profile = MagicMock()
        profile.rome_codes = {
            "M1805": {"cv_ids": [str(cv_id), other_cv_id], "label": "Dev info"},
            "M1802": {"cv_ids": [str(cv_id)], "label": "BI"},
        }
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        cv_router_module._remove_cv_from_rome_codes(mock_session, cv_id, "user-1")

        assert "M1802" not in profile.rome_codes
        assert profile.rome_codes["M1805"]["cv_ids"] == [other_cv_id]

    def test_noop_when_no_profile(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        cv_router_module._remove_cv_from_rome_codes(mock_session, uuid.uuid4(), "user-1")

        mock_session.commit.assert_not_called()

    def test_noop_when_rome_codes_empty(self):
        profile = MagicMock()
        profile.rome_codes = {}
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = profile

        cv_router_module._remove_cv_from_rome_codes(mock_session, uuid.uuid4(), "user-1")

        assert profile.rome_codes == {}
