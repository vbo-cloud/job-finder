"""Tests for shared/telemetry.py — structlog -> stdlib logging bridge.

The bridge exists so azure-monitor-opentelemetry (which instruments `logging`,
never structlog directly) can export structured events to Application
Insights. The regression these tests guard against: a structlog event silently
never reaching the stdlib root logger, or reaching it without its custom
fields as individual `LogRecord` attributes (which is what Application
Insights reads into `customDimensions` — see `_configure_structlog`'s
docstring in shared/telemetry.py).
"""

import logging
from typing import Iterator

import pytest
import structlog

import shared.telemetry as telemetry


@pytest.fixture(autouse=True)
def _reset_logging_state() -> Iterator[None]:
    """Undo `configure_telemetry`'s global side effects after each test.

    `structlog.configure`, root logger handlers/level, and the noisy
    third-party logger levels are all process-global state, so a test that
    calls `configure_telemetry` would otherwise leak its logging setup into
    every test that runs after it.
    """
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    original_noisy_levels = {
        name: logging.getLogger(name).level for name in telemetry._NOISY_THIRD_PARTY_LOGGERS
    }
    yield
    root_logger.handlers = original_handlers
    root_logger.setLevel(original_level)
    for name, level in original_noisy_levels.items():
        logging.getLogger(name).setLevel(level)
    structlog.reset_defaults()


class TestStructlogStdlibBridge:
    def test_custom_fields_land_as_log_record_attributes(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(telemetry, "APPLICATIONINSIGHTS_CONNECTION_STRING", None)
        telemetry.configure_telemetry("test-service")

        captured: list[logging.LogRecord] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        logging.getLogger().addHandler(_CaptureHandler())

        structlog.get_logger().info("offers_upserted", total=5, rome_code="M1234")

        [record] = [r for r in captured if r.getMessage() == "offers_upserted"]
        assert record.total == 5
        assert record.rome_code == "M1234"

    def test_root_logger_captures_info_level(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(telemetry, "APPLICATIONINSIGHTS_CONNECTION_STRING", None)
        telemetry.configure_telemetry("test-service")

        assert logging.getLogger().getEffectiveLevel() == logging.INFO

    def test_noisy_third_party_loggers_pinned_to_warning(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(telemetry, "APPLICATIONINSIGHTS_CONNECTION_STRING", None)
        telemetry.configure_telemetry("test-service")

        for noisy_logger_name in telemetry._NOISY_THIRD_PARTY_LOGGERS:
            assert logging.getLogger(noisy_logger_name).getEffectiveLevel() == logging.WARNING

    def test_field_colliding_with_log_record_attribute_does_not_crash(self, monkeypatch: pytest.MonkeyPatch):
        """Regression test for the crash `render_to_log_kwargs` alone would cause:
        `logging.Logger.makeRecord` raises `KeyError` if an `extra` key already
        exists on `LogRecord` (e.g. `filename`, found in cv.py's upload flow).
        `_rename_reserved_keys` must prefix it instead of letting it collide."""
        monkeypatch.setattr(telemetry, "APPLICATIONINSIGHTS_CONNECTION_STRING", None)
        telemetry.configure_telemetry("test-service")

        captured: list[logging.LogRecord] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        logging.getLogger().addHandler(_CaptureHandler())

        structlog.get_logger().info("cv_upload_started", user_id="u1", filename="cv.pdf")

        [record] = [r for r in captured if r.getMessage() == "cv_upload_started"]
        assert record.event_filename == "cv.pdf"
        assert record.filename != "cv.pdf"

    def test_exc_info_still_captures_traceback(self, monkeypatch: pytest.MonkeyPatch):
        """Regression test: `_rename_reserved_keys` must not rename `exc_info`
        itself, since `render_to_log_kwargs` relies on finding it in the event
        dict to pass the traceback through as a real stdlib kwarg. Mandatory
        per conventions-python (`logger.error(..., exc_info=True)` on every
        error log) and used throughout the codebase (cleanup, auth, bus)."""
        monkeypatch.setattr(telemetry, "APPLICATIONINSIGHTS_CONNECTION_STRING", None)
        telemetry.configure_telemetry("test-service")

        captured: list[logging.LogRecord] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        logging.getLogger().addHandler(_CaptureHandler())

        try:
            raise ValueError("boom")
        except ValueError:
            structlog.get_logger().error("op_failed", exc_info=True)

        [record] = [r for r in captured if r.getMessage() == "op_failed"]
        assert record.exc_info is not None
        assert record.exc_info[1].args == ("boom",)
        assert not hasattr(record, "event_exc_info")


class TestConsoleFormatterColor:
    """Regression coverage for the console/prod split found via manual review:
    `_ConsoleFormatter` must only colorize when `use_color=True`, since the
    same handler also runs when APPLICATIONINSIGHTS_CONNECTION_STRING is set
    (production) — raw ANSI codes there would corrupt ContainerAppConsoleLogs_CL."""

    def test_colorizes_when_use_color_is_true(self):
        formatter = telemetry._ConsoleFormatter("%(levelname)s %(message)s", use_color=True)
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)

        assert formatter.format(record).startswith(telemetry._LEVEL_COLORS[logging.INFO])

    def test_no_color_when_use_color_is_false(self):
        formatter = telemetry._ConsoleFormatter("%(levelname)s %(message)s", use_color=False)
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)

        assert "\033[" not in formatter.format(record)
