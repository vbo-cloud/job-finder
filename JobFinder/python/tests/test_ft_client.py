"""Tests for agents/offer_fetching/ft_client.py.

Covers: get_access_token, fetch_offers (pagination, 429 retry, min_date param).
All HTTP calls are mocked — no real network requests are made.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

_OFFER_FETCHING_DIR = Path(__file__).parent.parent / "agents" / "offer_fetching"
if str(_OFFER_FETCHING_DIR) not in sys.path:
    sys.path.insert(0, str(_OFFER_FETCHING_DIR))

import ft_client  # noqa: E402  (must come after sys.path mutation)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_http_response(
    status_code: int = 200,
    json_data: dict | None = None,
    headers: dict | None = None,
) -> MagicMock:
    """Build a minimal mock of a requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    mock.headers = headers or {}
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.HTTPError(response=mock)
    else:
        mock.raise_for_status.return_value = None
    return mock


def _make_session_mock(side_effects: list) -> MagicMock:
    """Build a requests.Session context-manager mock with ordered get() responses."""
    session = MagicMock()
    session.get.side_effect = side_effects
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


# ---------------------------------------------------------------------------
# get_access_token
# ---------------------------------------------------------------------------


class TestGetAccessToken:
    def test_returns_token_on_success(self, mocker):
        mock_resp = _make_http_response(200, json_data={"access_token": "my-token"})
        mocker.patch("ft_client.requests.post", return_value=mock_resp)

        assert ft_client.get_access_token() == "my-token"

    def test_reraises_request_exception_on_http_error(self, mocker):
        mock_resp = _make_http_response(401)
        mocker.patch("ft_client.requests.post", return_value=mock_resp)

        with pytest.raises(requests.HTTPError):
            ft_client.get_access_token()


# ---------------------------------------------------------------------------
# fetch_offers
# ---------------------------------------------------------------------------


class TestFetchOffers:
    def test_returns_single_page_when_results_below_page_size(self, mocker):
        page = [{"id": str(i)} for i in range(10)]
        resp = _make_http_response(
            200,
            json_data={"resultats": page},
            headers={"Content-Range": "0-9/10"},
        )
        mocker.patch("ft_client.requests.Session", return_value=_make_session_mock([resp]))

        result = ft_client.fetch_offers("token", "M1805")

        assert result == page

    def test_paginates_across_multiple_pages(self, mocker):
        page_size = ft_client.PAGE_SIZE
        page1 = [{"id": str(i)} for i in range(page_size)]
        page2 = [{"id": str(i + page_size)} for i in range(5)]
        total = page_size + 5
        resp1 = _make_http_response(
            200,
            json_data={"resultats": page1},
            headers={"Content-Range": f"0-{page_size - 1}/{total}"},
        )
        resp2 = _make_http_response(
            200,
            json_data={"resultats": page2},
            headers={"Content-Range": f"{page_size}-{total - 1}/{total}"},
        )
        mock_session = _make_session_mock([resp1, resp2])
        mocker.patch("ft_client.requests.Session", return_value=mock_session)
        mocker.patch("ft_client.time.sleep")

        result = ft_client.fetch_offers("token", "M1805")

        assert len(result) == total
        assert mock_session.get.call_count == 2

    def test_waits_and_retries_on_429(self, mocker):
        resp_429 = MagicMock(status_code=429, headers={"Retry-After": "2"})
        resp_200 = _make_http_response(
            200,
            json_data={"resultats": [{"id": "1"}]},
            headers={"Content-Range": "0-0/1"},
        )
        mocker.patch(
            "ft_client.requests.Session",
            return_value=_make_session_mock([resp_429, resp_200]),
        )
        mock_sleep = mocker.patch("ft_client.time.sleep")

        result = ft_client.fetch_offers("token", "M1805")

        assert len(result) == 1
        mock_sleep.assert_called_with(2)

    def test_raises_http_error_after_max_retries_on_429(self, mocker):
        resp_429 = MagicMock(status_code=429, headers={"Retry-After": "1"})
        mocker.patch(
            "ft_client.requests.Session",
            return_value=_make_session_mock([resp_429] * ft_client.MAX_RETRIES),
        )
        mocker.patch("ft_client.time.sleep")

        with pytest.raises(requests.HTTPError):
            ft_client.fetch_offers("token", "M1805")

    def test_reraises_request_exception_on_non_429_error(self, mocker):
        resp_500 = _make_http_response(500)
        mocker.patch(
            "ft_client.requests.Session",
            return_value=_make_session_mock([resp_500]),
        )

        with pytest.raises(requests.HTTPError):
            ft_client.fetch_offers("token", "M1805")

    def test_includes_min_date_param_when_provided(self, mocker):
        resp = _make_http_response(
            200,
            json_data={"resultats": [{"id": "1"}]},
            headers={"Content-Range": "0-0/1"},
        )
        mock_session = _make_session_mock([resp])
        mocker.patch("ft_client.requests.Session", return_value=mock_session)

        ft_client.fetch_offers("token", "M1805", min_date="2024-01-01")

        call_params = mock_session.get.call_args.kwargs["params"]
        assert call_params.get("minDateActualisation") == "2024-01-01"

    def test_omits_min_date_param_when_not_provided(self, mocker):
        resp = _make_http_response(
            200,
            json_data={"resultats": [{"id": "1"}]},
            headers={"Content-Range": "0-0/1"},
        )
        mock_session = _make_session_mock([resp])
        mocker.patch("ft_client.requests.Session", return_value=mock_session)

        ft_client.fetch_offers("token", "M1805")

        call_params = mock_session.get.call_args.kwargs["params"]
        assert "minDateActualisation" not in call_params
