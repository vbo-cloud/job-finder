"""Tests for agents/offer_fetching/ft_client.py.

Covers: get_access_token, fetch_offers (pagination, 429 retry, min_date param,
pagination-depth ceiling, 204 No Content), _probe_total, and fetch_all_offers
(adaptive creation-date sliding window). All HTTP calls are mocked — no real
network requests are made.
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

    def test_includes_creation_date_params_when_provided(self, mocker):
        resp = _make_http_response(
            200,
            json_data={"resultats": [{"id": "1"}]},
            headers={"Content-Range": "0-0/1"},
        )
        mock_session = _make_session_mock([resp])
        mocker.patch("ft_client.requests.Session", return_value=mock_session)

        ft_client.fetch_offers(
            "token", "M1805", min_creation_date="2026-01-01T00:00:00Z", max_creation_date="2026-02-01T00:00:00Z"
        )

        call_params = mock_session.get.call_args.kwargs["params"]
        assert call_params["minCreationDate"] == "2026-01-01T00:00:00Z"
        assert call_params["maxCreationDate"] == "2026-02-01T00:00:00Z"


# ---------------------------------------------------------------------------
# fetch_offers — pagination-depth ceiling (Task 1)
# ---------------------------------------------------------------------------


class TestFetchOffersPaginationCeiling:
    def test_raises_on_400_on_first_page(self, mocker):
        # A 400 on the very first page (start == 0) is a genuinely invalid request
        # (bad ROME code / date format), not a pagination ceiling — must still raise.
        resp_400 = _make_http_response(400)
        mocker.patch(
            "ft_client.requests.Session",
            return_value=_make_session_mock([resp_400]),
        )

        with pytest.raises(requests.HTTPError):
            ft_client.fetch_offers("token", "M1805")

    def test_returns_collected_offers_on_400_after_first_page(self, mocker):
        # France Travail's hard pagination ceiling: a 400 on a later page (start > 0),
        # after at least one successful page, returns what was collected instead of raising.
        page_size = ft_client.PAGE_SIZE
        page1 = [{"id": str(i)} for i in range(page_size)]  # full page -> a next page is attempted
        resp1 = _make_http_response(
            200,
            json_data={"resultats": page1},
            headers={"Content-Range": f"0-{page_size - 1}/{page_size * 3}"},
        )
        resp_400 = _make_http_response(400)
        mocker.patch(
            "ft_client.requests.Session",
            return_value=_make_session_mock([resp1, resp_400]),
        )
        mocker.patch("ft_client.time.sleep")

        result = ft_client.fetch_offers("token", "M1805")

        assert result == page1
        assert len(result) == page_size

    def test_returns_empty_list_on_204_no_content(self, mocker):
        # France Travail answers an empty result set with 204 No Content and no body —
        # response.json() would raise, so fetch_offers must guard on response.content.
        resp_204 = _make_http_response(204, headers={})
        resp_204.content = b""
        resp_204.json.side_effect = ValueError("no body to decode")
        mocker.patch("ft_client.requests.Session", return_value=_make_session_mock([resp_204]))

        result = ft_client.fetch_offers(
            "token", "M1805", min_creation_date="2026-01-01T00:00:00Z", max_creation_date="2026-02-01T00:00:00Z"
        )

        assert result == []


# ---------------------------------------------------------------------------
# _probe_total
# ---------------------------------------------------------------------------


class TestProbeTotal:
    def test_reads_total_from_content_range_with_range_zero(self, mocker):
        resp = _make_http_response(200, headers={"Content-Range": "offres 0-0/1234"})
        mock_session = _make_session_mock([resp])
        mocker.patch("ft_client.requests.Session", return_value=mock_session)

        total = ft_client._probe_total("token", "M1805", min_date="2026-01-01")

        assert total == 1234
        assert mock_session.get.call_args.kwargs["params"]["range"] == "0-0"

    def test_returns_zero_when_content_range_absent(self, mocker):
        # The API answers an empty result set with 204 No Content and no Content-Range.
        resp = _make_http_response(204, headers={})
        mocker.patch("ft_client.requests.Session", return_value=_make_session_mock([resp]))

        assert ft_client._probe_total("token", "M1805") == 0


# ---------------------------------------------------------------------------
# fetch_all_offers — adaptive creation-date sliding window (Task 2)
# ---------------------------------------------------------------------------


class TestFetchAllOffers:
    def test_single_fetch_when_first_probe_below_threshold(self, mocker):
        # Most ROME codes: the whole tail already fits under the threshold, so no windowing.
        mock_probe = mocker.patch.object(ft_client, "_probe_total", return_value=100)
        fake_offers = [{"id": "1"}, {"id": "2"}]
        mock_fetch = mocker.patch.object(ft_client, "fetch_offers", return_value=fake_offers)

        result = ft_client.fetch_all_offers("token", "M1805", min_date="2026-01-01")

        assert result == fake_offers
        mock_fetch.assert_called_once()
        # Single-fetch tail path never sets a minCreationDate lower bound.
        assert mock_fetch.call_args.kwargs.get("min_creation_date") is None
        mock_probe.assert_called_once()

    def test_shrinks_window_then_merges_and_dedups(self, mocker):
        # Probe call sequence (side_effect maps 1:1 to _probe_total calls):
        #   5000 = outer top probe (>= threshold) -> enter shrink
        #   3000 = _shrink_window @30d (>= threshold) -> halve
        #   1000 = _shrink_window @15d (< threshold) -> window retained + fetched
        #    500 = next outer top probe (< threshold, > 0) -> one tail fetch, then stop
        mocker.patch.object(ft_client, "_probe_total", side_effect=[5000, 3000, 1000, 500])
        mocker.patch.object(
            ft_client,
            "fetch_offers",
            side_effect=[
                [{"id": "1"}, {"id": "2"}],
                [{"id": "2"}, {"id": "3"}],  # id "2" overlaps the previous window
            ],
        )

        result = ft_client.fetch_all_offers("token", "M1805", min_date="2026-01-01")

        assert [o["id"] for o in result] == ["1", "2", "3"]

    def test_accepts_partial_result_when_floor_still_over_threshold(self, mocker):
        # Every shrink probe stays above the threshold down to the 1-day floor: no further
        # shrinking, a warning is logged, and the partial window fetch is accepted.
        mock_logger = mocker.patch.object(ft_client, "logger")
        # top probe (10000) + 5 shrink probes at widths 30/15/7/3/1 (all 9000) + next top (0).
        mocker.patch.object(
            ft_client, "_probe_total", side_effect=[10000, 9000, 9000, 9000, 9000, 9000, 0]
        )
        mock_fetch = mocker.patch.object(ft_client, "fetch_offers", return_value=[{"id": "1"}])

        result = ft_client.fetch_all_offers("token", "M1805", min_date="2026-01-01")

        assert result == [{"id": "1"}]
        mock_fetch.assert_called_once()
        assert any(
            call.args and call.args[0] == "ft_window_leaf_over_threshold"
            for call in mock_logger.warning.call_args_list
        )

    def test_skips_empty_window_without_fetching(self, mocker):
        # A creation-date gap below cursor_end: the shrink probe returns 0 while total_below is
        # still above threshold (an older burst). The empty window must be skipped without a
        # fetch (a 0-result fetch is a bodyless 204) and the walk must continue past it.
        mocker.patch.object(ft_client, "_probe_total", side_effect=[5000, 0, 3000, 1000, 0])
        mock_fetch = mocker.patch.object(ft_client, "fetch_offers", return_value=[{"id": "1"}])

        result = ft_client.fetch_all_offers("token", "M1805", min_date="2026-01-01")

        assert result == [{"id": "1"}]
        mock_fetch.assert_called_once()

    def test_stops_immediately_when_first_probe_is_zero(self, mocker):
        mock_probe = mocker.patch.object(ft_client, "_probe_total", return_value=0)
        mock_fetch = mocker.patch.object(ft_client, "fetch_offers")

        result = ft_client.fetch_all_offers("token", "M1805", min_date="2026-01-01")

        assert result == []
        mock_fetch.assert_not_called()
        mock_probe.assert_called_once()
