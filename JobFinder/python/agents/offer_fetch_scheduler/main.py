"""Offer fetch scheduler — timer-triggered relay that asks offer_fetching to run a full refresh.

Runs as a Container App Job on the same UTC cron_expression job_offer_fetching used before this
agent existed (see container_apps.tf) — Azure's schedule trigger has no timezone/DST awareness, so
Terraform still fires this job at every UTC hour that could map to 12:00/20:00 Europe/Paris under
either CET or CEST; _is_scheduled_local_hour no-ops the two firings that don't match the current DST
state, exactly as offer_fetching's own main() used to before it became purely event-driven — see
docs/prompts/prompt-offer-fetching-event-driven-and-new-code-fetch.md.

This agent never talks to France Travail, OpenAI, or the database — its only job is publishing one
message to OFFER_FETCH_REQUEST_QUEUE with no rome_codes key, which offer_fetching's consumer treats
as "recompute and fetch every active ROME code" (a full refresh).

Expected environment variables:
    AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE: Service Bus namespace host.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import structlog

from shared.bus import send_message
from shared.telemetry import configure_telemetry

OFFER_FETCH_REQUEST_QUEUE = "offer-fetch-request"
PARIS_TZ = ZoneInfo("Europe/Paris")
# Kept in sync with the UTC hours covered by container_apps.tf's cron_expression
# for job_offer_fetch_scheduler — see _is_scheduled_local_hour.
SCHEDULED_LOCAL_HOURS = (12, 20)

logger = structlog.get_logger()


def _is_scheduled_local_hour(now_utc: datetime) -> bool:
    """Check whether now_utc falls on one of this job's intended Europe/Paris run hours.

    Azure Container Apps' schedule trigger only supports a UTC cron_expression, with no
    timezone or DST awareness. Terraform's cron_expression for job_offer_fetch_scheduler
    therefore fires at every UTC hour that could map to SCHEDULED_LOCAL_HOURS under either
    CET (UTC+1) or CEST (UTC+2) — this guard picks out the two firings that are actually
    correct for the current DST state, so main() can no-op the other two. That keeps the
    schedule correct across DST transitions without a manual Terraform change twice a year.

    Args:
        now_utc: Current time, timezone-aware in UTC.

    Returns:
        True if now_utc's Europe/Paris local hour is one of SCHEDULED_LOCAL_HOURS.
    """
    return now_utc.astimezone(PARIS_TZ).hour in SCHEDULED_LOCAL_HOURS


def main() -> None:
    """Publish one full-refresh offer-fetch-request, unless outside the scheduled local hour."""
    configure_telemetry("offer-fetch-scheduler")

    now_utc = datetime.now(timezone.utc)
    if not _is_scheduled_local_hour(now_utc):
        logger.info("offer_fetch_scheduler_skipped_outside_local_window", utc_hour=now_utc.hour)
        return

    send_message(OFFER_FETCH_REQUEST_QUEUE, {"trigger": "scheduled"})
    logger.info("offer_fetch_scheduler_request_sent")


if __name__ == "__main__":
    main()
