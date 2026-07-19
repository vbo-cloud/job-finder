"""Application Insights telemetry bootstrap via OpenTelemetry.

Also bridges structlog to the stdlib `logging` module. azure-monitor-opentelemetry
only instruments `logging`, never structlog directly: without this bridge,
structlog's default renderer writes straight to stdout and no `logger.info(...)`
event ever reaches Application Insights, even when `configure_azure_monitor()`
runs successfully. The bridge is applied unconditionally (connection string
present or not) so local dev and production log the same way.

Design notes for `_configure_structlog`'s processor chain:
- Uses `structlog.stdlib.render_to_log_kwargs` as the final processor rather
  than the more commonly documented `ProcessorFormatter.wrap_for_formatter`:
  the latter bundles the whole event dict into `record.msg`, so custom
  fields (e.g. `total`, `rome_code`) never become individual `LogRecord`
  attributes. Application Insights builds `customDimensions` from exactly
  those attributes (`vars(record)` — see opentelemetry-instrumentation-logging's
  `LoggingHandler._get_attributes`), so `wrap_for_formatter` would leave
  `customDimensions` empty. Verified empirically against the installed
  azure-monitor-opentelemetry==1.8.8 before choosing this over the
  prescribed pattern.
- No separate level/timestamp processor: `render_to_log_kwargs` calls the
  stdlib logger method matching the structlog level (`.info()`, `.warning()`,
  ...), so `record.levelname`/`record.created` are already correct —
  duplicating them would only add redundant `level`/`timestamp` entries to
  `customDimensions`.
- Root logger forced to INFO: azure-monitor-opentelemetry's own
  `LoggingHandler` has no level filter of its own (NOTSET), so the root
  logger's default WARNING level would otherwise silently drop most
  business-event logs (e.g. `offers_upserted`) before they ever reach either
  handler. Noisy third-party loggers (`azure`, `urllib3`) are pinned back to
  WARNING so they don't drown out application events in AppTraces.

The `unknown_service` AppRoleName pitfall (`configure_telemetry`):
`configure_azure_monitor(**kwargs)` in azure-monitor-opentelemetry==1.8.8 does
NOT accept a `service_name` keyword — its actual signature only recognizes a
`resource` keyword taking an `opentelemetry.sdk.resources.Resource` object
(confirmed by reading `_get_configurations` in the installed package: every
kwarg is copied into an internal dict, but only recognized keys, `resource`
among them, are ever read back out). An unrecognized kwarg like `service_name`
is silently absorbed and has no effect — no error, no warning. Without an
explicit `resource`, `_default_resource` falls back to `Resource.create()`
with no attributes, whose default `service.name` is exactly `"unknown_service"`
— which is what Application Insights then shows as `AppRoleName` for every
event, from every agent (all route through this same function). The fix is
to build the resource explicitly: `Resource.create({SERVICE_NAME: service_name})`.
This bug predates the structlog->logging bridge (see above) — it was just
never observable before, since AppTraces received no events at all until that
bridge was added.
"""

import logging
import os

import structlog

APPLICATIONINSIGHTS_CONNECTION_STRING = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

_NOISY_THIRD_PARTY_LOGGERS = ("azure", "urllib3")

# Deliberately not shared with _ConsoleFormatter._RESERVED below: this set
# feeds _rename_reserved_keys, which must NOT touch exc_info/stack_info (see
# that function's docstring) or render_to_log_kwargs stops routing tracebacks.
_RESERVED_LOG_RECORD_KEYS = (
    frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {"message", "asctime"}
) - {"exc_info", "stack_info", "stacklevel"}

_LEVEL_COLORS = {
    logging.DEBUG: "\033[37m",
    logging.INFO: "\033[36m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[41m",
}
_COLOR_RESET = "\033[0m"

logger = structlog.get_logger()


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

    Deliberately excludes `exc_info`, `stack_info`, and `stacklevel`:
    `render_to_log_kwargs` pulls those out of the event dict itself and
    passes them through as real stdlib kwargs (not `extra=`), which is how
    `logger.error(..., exc_info=True)` — mandatory on every error log per
    `conventions-python` — attaches its traceback. Renaming them here would
    silently swallow every traceback in the codebase instead.
    """
    for key in list(event_dict.keys()):
        if key in _RESERVED_LOG_RECORD_KEYS:
            event_dict[f"event_{key}"] = event_dict.pop(key)
    return event_dict


class _ConsoleFormatter(logging.Formatter):
    """Colorize by level (dev only) and append structlog's custom event fields.

    Only affects what a human sees on the console — Application Insights
    export reads the same fields directly off the `LogRecord` regardless of
    this formatter (see `_configure_structlog` docstring). Colorizes by
    level rather than gating JSON/color on a `LOG_LEVEL` env var: no module
    in this codebase reads `LOG_LEVEL` today, so wiring that up here would be
    new cross-cutting infrastructure well beyond this bridge's scope. Color
    is instead gated on `use_color` (see `__init__`): this same
    `logging.StreamHandler` also runs in production (root logger has no
    dev/prod split), and `envs/dev/monitoring.tf`'s diagnostic setting
    captures raw stdout/stderr into `ContainerAppConsoleLogs_CL` — ANSI
    codes would show up as literal `\x1b[36m` garbage in that Log Analytics
    stream instead of being rendered.
    """

    # Not shared with _RESERVED_LOG_RECORD_KEYS above: this one only decides
    # what's redundant to print on the console line, so — unlike that one —
    # it can safely include exc_info/stack_info (the traceback is rendered
    # separately by super().format(), not worth repeating as a trailing extra).
    _RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
        "message",
        "asctime",
        "taskName",
    }

    def __init__(self, fmt: str, use_color: bool) -> None:
        super().__init__(fmt)
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        color = _LEVEL_COLORS.get(record.levelno, "") if self._use_color else ""
        if color:
            base = f"{color}{base}{_COLOR_RESET}"
        extra = {key: value for key, value in vars(record).items() if key not in self._RESERVED}
        if not extra:
            return base
        rendered = " ".join(f"{key}={value!r}" for key, value in sorted(extra.items()))
        return f"{base} {rendered}"


def _configure_structlog() -> None:
    """Route structlog events through the stdlib `logging` root logger.

    Required so azure-monitor-opentelemetry (which instruments `logging`, not
    structlog) can export structured events to Application Insights. See the
    module docstring for the rationale behind each processor/config choice
    below, and `_rename_reserved_keys`' own docstring for why it runs first.
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
        formatter = _ConsoleFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            use_color=not APPLICATIONINSIGHTS_CONNECTION_STRING,
        )
        handler.setFormatter(formatter)
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
        service_name: Logical name for this agent, exported as the `service.name`
            resource attribute (Application Insights AppRoleName), e.g. "cv-analysis",
            "matching". Passed via an explicit `resource=`, not a `service_name=`
            kwarg — see the module docstring's `unknown_service` pitfall note.
    """
    _configure_structlog()

    if not APPLICATIONINSIGHTS_CONNECTION_STRING:
        logger.info("telemetry_disabled", reason="APPLICATIONINSIGHTS_CONNECTION_STRING not set")
        return

    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

    configure_azure_monitor(
        connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING,
        resource=Resource.create({SERVICE_NAME: service_name}),
    )
    logger.info("telemetry_configured", service=service_name)
