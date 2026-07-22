"""Tests for agents/offer_fetch_scheduler/main.py.

Covers: _is_scheduled_local_hour (transposed from offer_fetching's own test of the same
function before it moved here — see
docs/prompts/prompt-offer-fetching-event-driven-and-new-code-fetch.md) and main().

The module is loaded via importlib under the unique name 'offer_fetch_scheduler_main' to
avoid sys.modules collision with the other agents' main.py.
"""
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_AGENTS_DIR = Path(__file__).parent.parent / "agents"
_spec = importlib.util.spec_from_file_location(
    "offer_fetch_scheduler_main", _AGENTS_DIR / "offer_fetch_scheduler" / "main.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["offer_fetch_scheduler_main"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_is_scheduled_local_hour = _mod._is_scheduled_local_hour


# ---------------------------------------------------------------------------
# _is_scheduled_local_hour
# ---------------------------------------------------------------------------


class TestIsScheduledLocalHour:
    @pytest.mark.parametrize(
        ("utc_hour", "expected"),
        [
            (10, True),   # CEST (UTC+2): 10:00 UTC -> 12:00 Europe/Paris
            (18, True),   # CEST (UTC+2): 18:00 UTC -> 20:00 Europe/Paris
            (11, False),  # CEST: would be 13:00 local -- the CET-only firing
            (19, False),  # CEST: would be 21:00 local -- the CET-only firing
        ],
    )
    def test_matches_cest_offset_in_july(self, utc_hour: int, expected: bool):
        # 2026-07-16 falls under CEST (Europe/Paris observes DST from late March to
        # late October) -- UTC+2.
        now_utc = datetime(2026, 7, 16, utc_hour, 0, tzinfo=timezone.utc)
        assert _is_scheduled_local_hour(now_utc) is expected

    @pytest.mark.parametrize(
        ("utc_hour", "expected"),
        [
            (11, True),   # CET (UTC+1): 11:00 UTC -> 12:00 Europe/Paris
            (19, True),   # CET (UTC+1): 19:00 UTC -> 20:00 Europe/Paris
            (10, False),  # CET: would be 11:00 local -- the CEST-only firing
            (18, False),  # CET: would be 19:00 local -- the CEST-only firing
        ],
    )
    def test_matches_cet_offset_in_january(self, utc_hour: int, expected: bool):
        # 2026-01-16 falls outside the DST window -- UTC+1.
        now_utc = datetime(2026, 1, 16, utc_hour, 0, tzinfo=timezone.utc)
        assert _is_scheduled_local_hour(now_utc) is expected

    def test_rejects_an_hour_outside_any_terraform_trigger(self):
        now_utc = datetime(2026, 7, 16, 3, 0, tzinfo=timezone.utc)
        assert _is_scheduled_local_hour(now_utc) is False


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def test_skips_and_does_not_send_outside_scheduled_local_hour(self, mocker):
        mocker.patch.object(_mod, "configure_telemetry")
        mocker.patch.object(_mod, "_is_scheduled_local_hour", return_value=False)
        mock_send = mocker.patch.object(_mod, "send_message")

        _mod.main()

        mock_send.assert_not_called()

    def test_sends_full_refresh_request_within_scheduled_local_hour(self, mocker):
        mocker.patch.object(_mod, "configure_telemetry")
        mocker.patch.object(_mod, "_is_scheduled_local_hour", return_value=True)
        mock_send = mocker.patch.object(_mod, "send_message")

        _mod.main()

        mock_send.assert_called_once_with(
            _mod.OFFER_FETCH_REQUEST_QUEUE, {"trigger": "scheduled"}
        )
