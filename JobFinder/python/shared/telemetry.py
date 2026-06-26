"""Application Insights telemetry bootstrap via OpenTelemetry."""

import os

import structlog

logger = structlog.get_logger()

APPLICATIONINSIGHTS_CONNECTION_STRING = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")


def configure_telemetry(service_name: str) -> None:
    """Configure Azure Monitor OpenTelemetry export for the given service.

    Safe to call even if APPLICATIONINSIGHTS_CONNECTION_STRING is absent —
    telemetry is silently disabled in that case (local dev).

    Args:
        service_name: Logical name for this agent, used as cloud_role_name in
            Application Insights (e.g. "cv-analysis", "matching").
    """
    if not APPLICATIONINSIGHTS_CONNECTION_STRING:
        logger.info("telemetry_disabled", reason="APPLICATIONINSIGHTS_CONNECTION_STRING not set")
        return

    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(
        connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING,
        service_name=service_name,
    )
    logger.info("telemetry_configured", service=service_name)
