"""Tests for agents/webapp/routers/notifications.py — the one-click unsubscribe endpoint.

No auth dependency to override here (unlike every other webapp router test) — the whole
point of this endpoint is that it has none; identity comes from the signed token instead.

GET (confirm_unsubscribe) and POST (unsubscribe) are tested separately since they no
longer behave identically: GET never mutates (a mail-client link prefetcher/antivirus
scanner following the visible footer link must not silently unsubscribe anyone), only
POST does — see the module docstring for the full RFC 8058 rationale.
"""

import sys
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

from dependencies import get_db  # noqa: E402
from routers.notifications import router  # noqa: E402
from shared.unsubscribe_token import sign_unsubscribe_token, verify_unsubscribe_token  # noqa: E402

TEST_USER_ID = "test-user-unsubscribe"


@pytest.fixture()
def mock_session() -> MagicMock:
    return MagicMock()


def _build_client(mock_session: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: (yield mock_session)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def test_client(mock_session: MagicMock) -> TestClient:
    return _build_client(mock_session)


class TestConfirmUnsubscribeGet:
    """GET must never mutate — see module docstring."""

    def test_valid_token_returns_a_confirmation_form_without_mutating(
        self, test_client: TestClient, mock_session: MagicMock
    ):
        token = sign_unsubscribe_token(TEST_USER_ID)

        response = test_client.get("/notifications/unsubscribe", params={"token": token})

        assert response.status_code == 200
        assert "Confirmer" in response.text
        assert f'action="/notifications/unsubscribe?token={token}"' in response.text
        mock_session.execute.assert_not_called()

    def test_escapes_a_token_crafted_to_break_out_of_the_form_action_attribute(
        self, test_client: TestClient
    ):
        """Python's base64 decoder silently discards out-of-alphabet bytes instead of
        rejecting them, so a token can splice in HTML-breaking characters (at positions
        that don't shift the decoded payload) and still verify successfully — see
        _render_confirm_html's docstring. The confirmation page must escape it
        regardless of whether it verifies."""
        token = sign_unsubscribe_token(TEST_USER_ID)
        encoded_user_id, signature = token.split(".", 1)
        # 4 injected characters (a multiple of 4) keep the length-derived padding
        # calculation aligned, so the crafted token still verifies successfully.
        crafted = encoded_user_id[:3] + '"""\'' + encoded_user_id[3:] + "." + signature
        assert verify_unsubscribe_token(crafted) == TEST_USER_ID  # sanity: it does verify

        response = test_client.get("/notifications/unsubscribe", params={"token": crafted})

        assert response.status_code == 200
        assert '"""\'' not in response.text
        assert "&quot;&quot;&quot;&#x27;" in response.text

    def test_invalid_token_returns_400_without_touching_the_db(
        self, test_client: TestClient, mock_session: MagicMock
    ):
        response = test_client.get(
            "/notifications/unsubscribe", params={"token": "not-a-valid-token"}
        )

        assert response.status_code == 400
        assert "invalide" in response.text
        mock_session.execute.assert_not_called()

    def test_missing_token_param_is_a_422(self, test_client: TestClient):
        response = test_client.get("/notifications/unsubscribe")

        assert response.status_code == 422


class TestUnsubscribePost:
    """POST is what actually mutates — reached by RFC 8058's automated one-click flow or
    by a human submitting confirm_unsubscribe's form."""

    def test_valid_token_returns_200_and_confirmation_page(self, test_client: TestClient):
        token = sign_unsubscribe_token(TEST_USER_ID)

        response = test_client.post("/notifications/unsubscribe", params={"token": token})

        assert response.status_code == 200
        assert "désabonné" in response.text

    def test_clears_notification_days_for_the_token_s_user(
        self, test_client: TestClient, mock_session: MagicMock
    ):
        token = sign_unsubscribe_token(TEST_USER_ID)

        test_client.post("/notifications/unsubscribe", params={"token": token})

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        statement = mock_session.execute.call_args.args[0]
        compiled_sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        assert f"'{TEST_USER_ID}'" in compiled_sql
        assert "notification_days=ARRAY[]" in compiled_sql.replace(" ", "")

    def test_is_idempotent_across_two_calls(self, test_client: TestClient, mock_session: MagicMock):
        token = sign_unsubscribe_token(TEST_USER_ID)

        first = test_client.post("/notifications/unsubscribe", params={"token": token})
        second = test_client.post("/notifications/unsubscribe", params={"token": token})

        assert first.status_code == second.status_code == 200
        assert mock_session.execute.call_count == 2

    def test_rejects_a_tampered_token_without_touching_the_db(
        self, test_client: TestClient, mock_session: MagicMock
    ):
        token = sign_unsubscribe_token(TEST_USER_ID)
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

        response = test_client.post("/notifications/unsubscribe", params={"token": tampered})

        assert response.status_code == 400
        assert "invalide" in response.text
        mock_session.execute.assert_not_called()

    def test_rejects_garbage_input(self, test_client: TestClient):
        response = test_client.post(
            "/notifications/unsubscribe", params={"token": "not-a-valid-token"}
        )

        assert response.status_code == 400

    def test_missing_token_param_is_a_422(self, test_client: TestClient):
        response = test_client.post("/notifications/unsubscribe")

        assert response.status_code == 422

    def test_db_failure_surfaces_as_500(self, mock_session: MagicMock):
        mock_session.execute.side_effect = SQLAlchemyError("boom")
        client = _build_client(mock_session)
        token = sign_unsubscribe_token(TEST_USER_ID)

        response = client.post("/notifications/unsubscribe", params={"token": token})

        assert response.status_code == 500
