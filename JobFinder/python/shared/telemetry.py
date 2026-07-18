"""Application Insights telemetry bootstrap via OpenTelemetry.

Also bridges structlog to the stdlib `logging` module. azure-monitor-opentelemetry
only instruments `logging`, never structlog directly: without this bridge,
structlog's default renderer writes straight to stdout and no `logger.info(...)`
event ever reaches Application Insights, even when `configure_azure_monitor()`
runs successfully. The bridge is applied unconditionally (connection string
present or not) so local dev and production log the same way.
"""

import logging
import os

import structlog

logger = structlog.get_logger()

APPLICATIONINSIGHTS_CONNECTION_STRING = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

_NOISY_THIRD_PARTY_LOGGERS = ("azure", "urllib3")

_RESERVED_LOG_RECORD_KEYS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message",
    "asctime",
}


def _rename_reserved_keys(_logger: object, _method_name: str, event_dict: dict) -> dict:
    """Prefix event fields whose name collides with a stdlib `LogRecord` attribute.

    `structlog.stdlib.render_to_log_kwargs` passes every non-event field
    through `logging`'s `extra=`, and `logging.Logger.makeRecord` raises
    `KeyError` if any key in `extra` already exists on `LogRecord` (`name`,
    `filename`, `module`, `process`, ...) — a hard crash at log time, before
    any handler runs, not something `exc_info`/`handleError` can catch. This
    runs before `render_to_log_kwargs` so a call site can log e.g.
    `filename=...` (a real collision found in `cv.py`'s upload flow) without
    needing to know this stdlib constraint.
    """
    for key in list(event_dict.keys()):
        if key in _RESERVED_LOG_RECORD_KEYS:
            event_dict[f"event_{key}"] = event_dict.pop(key)
    return event_dict


class _ConsoleFormatter(logging.Formatter):
    """Append structlog's custom event fields to the standard log line.

    Only affects what a human sees on local stdout — Application Insights
    export reads the same fields directly off the `LogRecord` regardless of
    this formatter (see `_configure_structlog` docstring).
    """

    _RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
        "message",
        "asctime",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extra = {key: value for key, value in vars(record).items() if key not in self._RESERVED}
        if not extra:
            return base
        rendered = " ".join(f"{key}={value!r}" for key, value in sorted(extra.items()))
        return f"{base} {rendered}"


def _configure_structlog() -> None:
    """Route structlog events through the stdlib `logging` root logger.

    Required so azure-monitor-opentelemetry (which instruments `logging`, not
    structlog) can export structured events to Application Insights.

    Uses `structlog.stdlib.render_to_log_kwargs` as the final processor rather
    than the more commonly documented `ProcessorFormatter.wrap_for_formatter`:
    the latter bundles the whole event dict into `record.msg`, so custom
    fields (e.g. `total`, `rome_code`) never become individual `LogRecord`
    attributes. Application Insights builds `customDimensions` from exactly
    those attributes (`vars(record)` — see
    opentelemetry-instrumentation-logging's `LoggingHandler._get_attributes`),
    so `wrap_for_formatter` would leave `customDimensions` empty. Verified
    empirically against the installed azure-monitor-opentelemetry==1.8.8
    before choosing this over the prescribed pattern.

    `render_to_log_kwargs` routes every custom field through stdlib's
    `extra=`, which raises `KeyError` if a field name collides with an
    existing `LogRecord` attribute (`filename`, `name`, `module`, ...) — a
    real call site (`cv.py`'s upload flow) logged `filename=...` and would
    have crashed at log time in production. `_rename_reserved_keys` runs
    first in the chain to prefix any such collision instead.

    No separate level/timestamp processor is needed: `render_to_log_kwargs`
    calls the stdlib logger method matching the structlog level (`.info()`,
    `.warning()`, ...), so `record.levelname`/`record.created` are already
    correct — adding `add_log_level`/`TimeStamper` on top would only
    duplicate them as redundant `level`/`timestamp` entries in
    `customDimensions`.

    Also sets the root logger to INFO: azure-monitor-opentelemetry's own
    `LoggingHandler` has no level filter of its own (NOTSET), so without this
    the root logger's default WARNING level would silently drop most
    business-event logs (e.g. `offers_upserted`) before they ever reach
    either handler. Third-party libraries are pinned back to WARNING since
    they get noisy at INFO (HTTP retries, etc.) and would otherwise drown out
    application events in AppTraces.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _rename_reserved_keys,
            structlog.stdlib.render_to_log_kwargs,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    if not any(isinstance(handler.formatter, _ConsoleFormatter) for handler in root_logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(_ConsoleFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root_logger.addHandler(handler)

    root_logger.setLevel(logging.INFO)
    for noisy_logger in _NOISY_THIRD_PARTY_LOGGERS:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def configure_telemetry(service_name: str) -> None:
    """Configure structlog routing and Azure Monitor OpenTelemetry export.

    The structlog→logging bridge always runs, so local dev and production
    log the same way. `configure_azure_monitor` stays conditional on
    `APPLICATIONINSIGHTS_CONNECTION_STRING` — telemetry export itself is
    silently disabled without it (local dev).

    Args:
        service_name: Logical name for this agent, used as cloud_role_name in
            Application Insights (e.g. "cv-analysis", "matching").
    """
    _configure_structlog()

    if not APPLICATIONINSIGHTS_CONNECTION_STRING:
        logger.info("telemetry_disabled", reason="APPLICATIONINSIGHTS_CONNECTION_STRING not set")
        return

    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(
        connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING,
        service_name=service_name,
    )
    logger.info("telemetry_configured", service=service_name)
