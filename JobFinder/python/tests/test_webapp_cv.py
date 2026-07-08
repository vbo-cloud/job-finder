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

from auth import UserIdentity, get_current_identity, get_current_user  # noqa: E402
from dependencies import get_db  # noqa: E402

TEST_USER_ID = "test-user-cv"
TEST_CV_ID = uuid.uuid4()
TEST_IDENTITY = UserIdentity(
    user_id=TEST_USER_ID, email="test@example.test", display_name="Test User"
)


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
    app.dependency_overrides[get_current_identity] = lambda: TEST_IDENTITY
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

    def test_match_count_and_unseen_count_both_scoped_to_zone(self, test_client, mock_session):
        profile = MagicMock()
        profile.commune_codes = ["75101"]
        cv = MagicMock()
        cv.id = TEST_CV_ID
        cv.name = "Mon CV.pdf"
        cv.status = "done"
        cv.uploaded_at = "2024-01-15T10:00:00+00:00"
        cv.thumbnail_url = None
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"all.return_value": [(cv, 3, 1)]}),
        ]

        resp = test_client.get("/cv/")

        assert resp.status_code == 200
        # No real DB behind the mock — validate the zone filter is embedded
        # in both the match_count and unseen_count FILTER clauses by
        # inspecting the compiled statement passed to the second
        # session.execute call (profile lookup is first).
        stmt = str(mock_session.execute.call_args_list[1].args[0])
        assert "JOIN offers" in stmt
        assert stmt.count("offers.commune IN") == 2
        assert "count(matches.id) FILTER (WHERE offers.commune IN" in stmt
        assert "count(matches.id) FILTER (WHERE matches.seen_at IS NULL AND (offers.commune IN" in stmt

    def test_counts_unfiltered_when_zone_is_empty(self, test_client, mock_session):
        profile = MagicMock()
        profile.commune_codes = []
        cv = MagicMock()
        cv.id = TEST_CV_ID
        cv.name = "Mon CV.pdf"
        cv.status = "done"
        cv.uploaded_at = "2024-01-15T10:00:00+00:00"
        cv.thumbnail_url = None
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": profile}),
            MagicMock(**{"all.return_value": [(cv, 3, 3)]}),
        ]

        resp = test_client.get("/cv/")

        assert resp.status_code == 200
        stmt = str(mock_session.execute.call_args_list[1].args[0])
        assert "offers.commune" not in stmt

    def test_counts_unfiltered_when_no_profile(self, test_client, mock_session):
        cv = MagicMock()
        cv.id = TEST_CV_ID
        cv.name = "Mon CV.pdf"
        cv.status = "done"
        cv.uploaded_at = "2024-01-15T10:00:00+00:00"
        cv.thumbnail_url = None
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": None}),
            MagicMock(**{"all.return_value": [(cv, 3, 3)]}),
        ]

        resp = test_client.get("/cv/")

        assert resp.status_code == 200
        stmt = str(mock_session.execute.call_args_list[1].args[0])
        assert "offers.commune" not in stmt


# ---------------------------------------------------------------------------
# GET /cv/{cv_id}/analysis
# ---------------------------------------------------------------------------


class TestGetCvAnalysis:
    def test_returns_404_when_cv_not_found(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.get(f"/cv/{uuid.uuid4()}/analysis")

        assert resp.status_code == 404

    def test_returns_pending_when_no_analysis_row(self, test_client, mock_session, mocker):
        # CV still in the upload pipeline — its analysis is genuinely on the
        # way, so no backfill dispatch must happen.
        mock_send = mocker.patch.object(cv_router_module, "send_message")
        cv = MagicMock()
        cv.status = "processing"
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),    # select CV
            MagicMock(**{"scalar_one_or_none.return_value": None}),  # select CvAnalysis
        ]

        resp = test_client.get(f"/cv/{TEST_CV_ID}/analysis")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        assert body["ats_score"] is None
        assert body["points_forts"] == []
        assert body["points_faibles"] == []
        assert body["suggestions"] == []
        assert body["coherence_intention"] is None
        mock_send.assert_not_called()

    def test_backfills_analysis_for_terminal_cv_without_row(self, test_client, mock_session, mocker):
        # CV past the upload pipeline with no analysis row (pre-feature CV or
        # agent crash) — the endpoint claims a pending row and re-dispatches.
        mock_send = mocker.patch.object(cv_router_module, "send_message")
        cv = MagicMock()
        cv.status = "matched"
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),           # select CV
            MagicMock(**{"scalar_one_or_none.return_value": None}),         # select CvAnalysis
            MagicMock(**{"scalar_one_or_none.return_value": uuid.uuid4()}),  # insert claim
        ]

        resp = test_client.get(f"/cv/{TEST_CV_ID}/analysis")

        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"
        mock_send.assert_called_once_with(
            "cv-analysis", {"cv_id": str(TEST_CV_ID), "retry_quality_only": True}
        )
        mock_session.commit.assert_called_once()

    def test_backfill_skips_dispatch_when_claim_already_taken(self, test_client, mock_session, mocker):
        # A concurrent poll (or the agent) already inserted the row — the
        # on_conflict_do_nothing claim returns no id, so nothing is dispatched.
        mock_send = mocker.patch.object(cv_router_module, "send_message")
        cv = MagicMock()
        cv.status = "matched"
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": None}),
            MagicMock(**{"scalar_one_or_none.return_value": None}),  # claim lost
        ]

        resp = test_client.get(f"/cv/{TEST_CV_ID}/analysis")

        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"
        mock_send.assert_not_called()

    def test_backfill_flips_claim_to_error_when_dispatch_fails(self, test_client, mock_session, mocker):
        # The claim was inserted but the Service Bus send failed — the row is
        # flipped to "error" so the UI offers the manual retry button, and the
        # response stays 200.
        from azure.servicebus.exceptions import ServiceBusError

        mocker.patch.object(cv_router_module, "send_message", side_effect=ServiceBusError("boom"))
        cv = MagicMock()
        cv.status = "matched"
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": None}),
            MagicMock(**{"scalar_one_or_none.return_value": uuid.uuid4()}),  # insert claim
            MagicMock(),                                                     # update to error
        ]

        resp = test_client.get(f"/cv/{TEST_CV_ID}/analysis")

        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"
        assert mock_session.commit.call_count == 2

    def test_backfill_claim_db_error_still_returns_pending(self, test_client, mock_session, mocker):
        # Healing is best-effort: a DB error on the claim insert must not turn
        # a successful read into a 500.
        mock_send = mocker.patch.object(cv_router_module, "send_message")
        cv = MagicMock()
        cv.status = "matched"
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": None}),
            SQLAlchemyError("DB error"),
        ]

        resp = test_client.get(f"/cv/{TEST_CV_ID}/analysis")

        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"
        mock_send.assert_not_called()

    def test_returns_done_analysis(self, test_client, mock_session):
        cv = MagicMock()
        analysis = MagicMock()
        analysis.status = "done"
        analysis.ats_score = 72
        analysis.synthese = "Un CV bien structuré et lisible."
        analysis.points_forts = ["Structure claire"]
        analysis.points_faibles = ["Objectif absent"]
        analysis.suggestions = ["Ajouter un titre"]
        analysis.coherence_intention = "Cohérent avec le profil."
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": analysis}),
        ]

        resp = test_client.get(f"/cv/{TEST_CV_ID}/analysis")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "done"
        assert body["ats_score"] == 72
        assert body["synthese"] == "Un CV bien structuré et lisible."
        assert body["points_forts"] == ["Structure claire"]
        assert body["coherence_intention"] == "Cohérent avec le profil."

    def test_coerces_null_lists_on_error_row(self, test_client, mock_session):
        # An "error" row written by the agent has all result columns NULL —
        # the schema must coerce the JSONB lists to [].
        cv = MagicMock()
        analysis = MagicMock()
        analysis.status = "error"
        analysis.ats_score = None
        analysis.synthese = None
        analysis.points_forts = None
        analysis.points_faibles = None
        analysis.suggestions = None
        analysis.coherence_intention = None
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(**{"scalar_one_or_none.return_value": analysis}),
        ]

        resp = test_client.get(f"/cv/{TEST_CV_ID}/analysis")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert body["points_forts"] == []

    def test_returns_500_on_db_error(self, test_client, mock_session):
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.get(f"/cv/{TEST_CV_ID}/analysis")

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /cv/{cv_id}/analysis/retry
# ---------------------------------------------------------------------------


class TestRetryCvAnalysis:
    def test_returns_404_when_cv_not_found(self, test_client, mock_session, mocker):
        mock_send = mocker.patch.object(cv_router_module, "send_message")
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.post(f"/cv/{uuid.uuid4()}/analysis/retry")

        assert resp.status_code == 404
        mock_send.assert_not_called()

    def test_dispatches_retry_message_and_returns_202(self, test_client, mock_session, mocker):
        mock_send = mocker.patch.object(cv_router_module, "send_message")
        cv = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = cv

        resp = test_client.post(f"/cv/{TEST_CV_ID}/analysis/retry")

        assert resp.status_code == 202
        mock_send.assert_called_once_with(
            "cv-analysis", {"cv_id": str(TEST_CV_ID), "retry_quality_only": True}
        )

    def test_returns_202_even_if_dispatch_fails(self, test_client, mock_session, mocker):
        from azure.servicebus.exceptions import ServiceBusError

        mocker.patch.object(cv_router_module, "send_message", side_effect=ServiceBusError("boom"))
        cv = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = cv

        resp = test_client.post(f"/cv/{TEST_CV_ID}/analysis/retry")

        assert resp.status_code == 202

    def test_returns_500_on_db_error(self, test_client, mock_session, mocker):
        mock_send = mocker.patch.object(cv_router_module, "send_message")
        mock_session.execute.side_effect = SQLAlchemyError("DB error")

        resp = test_client.post(f"/cv/{TEST_CV_ID}/analysis/retry")

        assert resp.status_code == 500
        mock_send.assert_not_called()


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

    def test_returns_sm_thumbnail_by_default(self, test_client, mock_session, mock_blob_client):
        cv = MagicMock()
        cv.thumbnail_url = "https://account.blob.core.windows.net/cvs/user/cv_thumb.jpg"
        cv.thumbnail_url_lg = None
        mock_session.execute.return_value.scalar_one_or_none.return_value = cv
        fake_bytes = b"fake_sm_jpeg"
        mock_blob_client.get_blob_client.return_value.download_blob.return_value.readall.return_value = fake_bytes

        resp = test_client.get(f"/cv/{TEST_CV_ID}/thumbnail")

        assert resp.status_code == 200
        assert resp.content == fake_bytes

    def test_returns_lg_thumbnail_when_requested(self, test_client, mock_session, mock_blob_client):
        cv = MagicMock()
        cv.thumbnail_url = "https://account.blob.core.windows.net/cvs/user/cv_thumb.jpg"
        cv.thumbnail_url_lg = "https://account.blob.core.windows.net/cvs/user/cv_thumb_lg.jpg"
        mock_session.execute.return_value.scalar_one_or_none.return_value = cv
        fake_bytes = b"fake_lg_jpeg"
        mock_blob_client.get_blob_client.return_value.download_blob.return_value.readall.return_value = fake_bytes

        resp = test_client.get(f"/cv/{TEST_CV_ID}/thumbnail?size=lg")

        assert resp.status_code == 200
        assert resp.content == fake_bytes

    def test_falls_back_to_sm_when_lg_not_available(self, test_client, mock_session, mock_blob_client):
        cv = MagicMock()
        cv.thumbnail_url = "https://account.blob.core.windows.net/cvs/user/cv_thumb.jpg"
        cv.thumbnail_url_lg = None
        mock_session.execute.return_value.scalar_one_or_none.return_value = cv
        fake_bytes = b"fake_sm_jpeg_fallback"
        mock_blob_client.get_blob_client.return_value.download_blob.return_value.readall.return_value = fake_bytes

        resp = test_client.get(f"/cv/{TEST_CV_ID}/thumbnail?size=lg")

        assert resp.status_code == 200
        assert resp.content == fake_bytes


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
# PATCH /cv/{cv_id}/matches/{offer_id}/seen
# ---------------------------------------------------------------------------


class TestMarkMatchSeen:
    def test_returns_204_and_commits_when_unseen(self, test_client, mock_session):
        match = MagicMock()
        match.seen_at = None
        mock_session.execute.return_value.scalar_one_or_none.return_value = match

        resp = test_client.patch(f"/cv/{TEST_CV_ID}/matches/{uuid.uuid4()}/seen")

        assert resp.status_code == 204
        assert match.seen_at is not None
        mock_session.commit.assert_called_once()

    def test_skips_commit_when_already_seen(self, test_client, mock_session):
        match = MagicMock()
        match.seen_at = "2024-01-01T00:00:00+00:00"
        mock_session.execute.return_value.scalar_one_or_none.return_value = match

        resp = test_client.patch(f"/cv/{TEST_CV_ID}/matches/{uuid.uuid4()}/seen")

        assert resp.status_code == 204
        mock_session.commit.assert_not_called()

    def test_returns_404_when_match_not_found(self, test_client, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        resp = test_client.patch(f"/cv/{uuid.uuid4()}/matches/{uuid.uuid4()}/seen")

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
        cv.thumbnail_url_lg = None
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),   # select CV
            MagicMock(),                                              # delete(MatchAnalysis)
            MagicMock(),                                              # delete(Match)
            MagicMock(),                                              # delete(CvAnalysis)
            MagicMock(**{"scalar_one_or_none.return_value": None}),  # select UserProfile
        ]

        resp = test_client.delete(f"/cv/{TEST_CV_ID}")

        assert resp.status_code == 204
        mock_session.delete.assert_called_once_with(cv)
        mock_session.commit.assert_called_once()
        # Analyses are deleted before their parent rows — FK constraints have
        # no CASCADE. Validate the delete order via the compiled statements.
        stmts = [str(c.args[0]) for c in mock_session.execute.call_args_list[1:4]]
        assert "DELETE FROM match_analyses" in stmts[0]
        assert "DELETE FROM matches" in stmts[1]
        assert "DELETE FROM cv_analyses" in stmts[2]

    def test_also_deletes_thumbnail_blob_when_present(
        self, test_client, mock_session, mock_blob_client
    ):
        cv = MagicMock()
        cv.blob_url = "https://account.blob.core.windows.net/cvs/user/cv.pdf"
        cv.thumbnail_url = "https://account.blob.core.windows.net/cvs/user/cv_thumb.jpg"
        cv.thumbnail_url_lg = None
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(**{"scalar_one_or_none.return_value": None}),
        ]

        resp = test_client.delete(f"/cv/{TEST_CV_ID}")

        assert resp.status_code == 204
        blob_container = mock_blob_client.get_blob_client.return_value
        assert blob_container.delete_blob.call_count == 2

    def test_also_deletes_both_thumbnail_blobs_when_present(
        self, test_client, mock_session, mock_blob_client
    ):
        cv = MagicMock()
        cv.blob_url = "https://account.blob.core.windows.net/cvs/user/cv.pdf"
        cv.thumbnail_url = "https://account.blob.core.windows.net/cvs/user/cv_thumb.jpg"
        cv.thumbnail_url_lg = "https://account.blob.core.windows.net/cvs/user/cv_thumb_lg.jpg"
        mock_session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": cv}),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(**{"scalar_one_or_none.return_value": None}),
        ]

        resp = test_client.delete(f"/cv/{TEST_CV_ID}")

        assert resp.status_code == 204
        blob_container = mock_blob_client.get_blob_client.return_value
        assert blob_container.delete_blob.call_count == 3


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
