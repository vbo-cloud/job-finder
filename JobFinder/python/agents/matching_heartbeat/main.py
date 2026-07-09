"""Matching heartbeat agent — periodic timer trigger to catch up on async-distilled offers.

Runs as a Container App Job on a timer trigger (every 15 minutes). Sends a
single message to start-matching so the matching agent re-scores existing
offers/CVs — a safety net now that offers get their embedding written
asynchronously by agents/offer_distillation, with no per-offer "done" signal
to trigger matching directly (see
docs/prompts/prompt-offer-distillation-pipeline.md — a shared counter across
parallel distillation executions was considered and rejected there).

No database access, no OpenAI call, no Azure OpenAI/France Travail secret —
this agent only sends one Service Bus message and exits (see Terraform module
job_matching_heartbeat, which deliberately omits DATABASE_URL and those
secrets from its environment).

Expected environment variables:
    AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE: Service Bus namespace host.
"""

from datetime import datetime, timezone

import structlog

from shared.bus import send_message
from shared.telemetry import configure_telemetry

START_MATCHING_QUEUE = "start-matching"

logger = structlog.get_logger()


def main() -> None:
    """Send a single heartbeat message to start-matching."""
    configure_telemetry("matching-heartbeat")

    run_date = datetime.now(timezone.utc).date().isoformat()
    send_message(START_MATCHING_QUEUE, {"run_date": run_date, "trigger": "heartbeat"})
    logger.info("matching_heartbeat_sent", run_date=run_date)


if __name__ == "__main__":
    main()
