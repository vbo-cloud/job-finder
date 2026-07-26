"""Notifications agent — sends a per-CV digest email of unseen matches to opted-in users.

Runs as a Container App Job on a timer targeting 19:00 Europe/Paris local time (see
container_apps.tf's job_notifications module) — Azure's schedule trigger has no
timezone/DST awareness, so Terraform fires this job at both UTC hours that could map to
19:00 Europe/Paris under CET or CEST; _is_scheduled_local_hour no-ops the firing that
doesn't match the current DST state, same pattern as offer_fetch_scheduler
(agents/offer_fetch_scheduler/main.py).

For each UserProfile whose notification_days includes today's ISO weekday
(1=Monday...7=Sunday, see shared/models.py), counts unseen matches (Match.seen_at IS
NULL) per CV and sends one digest email listing every CV with at least one unseen
match. Never writes Match.seen_at — that column is exclusively updated by user action
in the webapp (routers/cv.py's mark_all_seen/mark_match_seen) — so an unseen offer
stays in the digest across multiple sends until the user views it in the app. Not a
bug if a user who checks several notification_days receives the same unseen offer
more than once.

Deliberately does not replicate GET /cv's commune-zone filter (routers/matches.py's
commune_zone_condition, package webapp): no agent in this repo imports another agent's
code (cleanup, matching, offer_fetch_scheduler only ever import shared.*), and that
helper lives in webapp, not shared. The digest count can therefore run slightly ahead
of what a user with a small painted zone sees in the CV library.

Expected environment variables:
    DATABASE_URL: PostgreSQL connection string.
    ACS_EMAIL_ENDPOINT_HOSTNAME: Azure Communication Services Email data-plane hostname
        (endpoint = https://<hostname>).
    ACS_EMAIL_SENDER_ADDRESS: Verified sender address used in the From header.
    FRONTEND_URL: Base URL linked at the bottom of the digest email.
    AZURE_CLIENT_ID: Read implicitly by DefaultAzureCredential (caj managed identity).
    APPLICATIONINSIGHTS_CONNECTION_STRING: Optional, enables telemetry export.
"""

import html
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import structlog
from azure.communication.email import EmailClient
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.db import get_session, run_migrations
from shared.models import CV, Match, UserProfile
from shared.telemetry import configure_telemetry

PARIS_TZ = ZoneInfo("Europe/Paris")
# Kept in sync with the UTC hours covered by container_apps.tf's cron_expression
# for job_notifications — see _is_scheduled_local_hour.
SCHEDULED_LOCAL_HOURS = (19,)
DIGEST_SUBJECT = "Vos nouvelles offres Job Finder"

logger = structlog.get_logger()

_endpoint_hostname = os.environ.get("ACS_EMAIL_ENDPOINT_HOSTNAME")
if not _endpoint_hostname:
    raise ValueError("ACS_EMAIL_ENDPOINT_HOSTNAME environment variable is not set")

_sender_address = os.environ.get("ACS_EMAIL_SENDER_ADDRESS")
if not _sender_address:
    raise ValueError("ACS_EMAIL_SENDER_ADDRESS environment variable is not set")

_frontend_url = os.environ.get("FRONTEND_URL")
if not _frontend_url:
    raise ValueError("FRONTEND_URL environment variable is not set")


def _is_scheduled_local_hour(now_utc: datetime) -> bool:
    """Check whether now_utc falls on this job's intended Europe/Paris run hour.

    Azure Container Apps' schedule trigger only supports a UTC cron_expression, with no
    timezone or DST awareness. Terraform's cron_expression for job_notifications
    therefore fires at every UTC hour that could map to SCHEDULED_LOCAL_HOURS under
    either CET (UTC+1) or CEST (UTC+2) — this guard picks out the firing that is
    actually correct for the current DST state, so main() can no-op the other one.

    Args:
        now_utc: Current time, timezone-aware in UTC.

    Returns:
        True if now_utc's Europe/Paris local hour is one of SCHEDULED_LOCAL_HOURS.
    """
    return now_utc.astimezone(PARIS_TZ).hour in SCHEDULED_LOCAL_HOURS


def _select_profiles_to_notify(session: Session, today_isoweekday: int) -> list[UserProfile]:
    """Return every UserProfile opted in to receive a digest today.

    Args:
        session: Active SQLAlchemy session.
        today_isoweekday: ISO 8601 weekday (1=Monday...7=Sunday) for the current
            Europe/Paris local date.

    Returns:
        UserProfile rows whose notification_days contains today_isoweekday.
    """
    logger.info("notifications_profile_selection_started", today_isoweekday=today_isoweekday)
    return list(
        session.execute(
            select(UserProfile).where(UserProfile.notification_days.any(today_isoweekday))
        ).scalars()
    )


def _count_unseen_matches_by_user(
    session: Session, user_ids: list[str]
) -> dict[str, list[tuple[str | None, int]]]:
    """Count unseen matches per CV, grouped by owning user, for every given user_id.

    Issues a single batched query across all given users instead of one query per
    user, avoiding an N+1 pattern when a run notifies many profiles.

    Args:
        session: Active SQLAlchemy session.
        user_ids: Owning users' identifiers (CV.user_id) to count for.

    Returns:
        Mapping of user_id to (cv_name, unseen_count) pairs, one pair per CV with at
        least one unseen match. A user_id with no unseen matches is absent from the
        mapping rather than present with an empty list.
    """
    if not user_ids:
        return {}

    logger.info("notifications_unseen_count_started", profile_count=len(user_ids))
    rows = session.execute(
        select(CV.user_id, CV.name, func.count(Match.id))
        .join(Match, Match.cv_id == CV.id)
        .where(CV.user_id.in_(user_ids), Match.seen_at.is_(None))
        .group_by(CV.user_id, CV.id, CV.name)
    ).all()

    counts_by_user: dict[str, list[tuple[str | None, int]]] = {}
    for user_id, name, count in rows:
        if count > 0:
            counts_by_user.setdefault(user_id, []).append((name, count))
    return counts_by_user


def _load_recipients_and_counts(
    today_isoweekday: int,
) -> tuple[list[tuple[str, str | None]], dict[str, list[tuple[str | None, int]]]]:
    """Fetch today's opted-in profiles and their unseen-match counts in one DB session.

    Args:
        today_isoweekday: ISO 8601 weekday (1=Monday...7=Sunday) for the current
            Europe/Paris local date.

    Returns:
        Tuple of (recipients, counts_by_user): recipients is a list of
        (user_id, email) pairs for every opted-in profile; counts_by_user maps
        user_id to its (cv_name, unseen_count) pairs (see
        _count_unseen_matches_by_user). The session is closed before returning, so
        the caller can send emails without holding a DB connection open.

    Raises:
        SQLAlchemyError: If either query fails.
    """
    try:
        with get_session() as session:
            profiles = _select_profiles_to_notify(session, today_isoweekday)
            recipients = [(profile.user_id, profile.email) for profile in profiles]
            counts_by_user = _count_unseen_matches_by_user(
                session, [user_id for user_id, email in recipients if email]
            )
    except SQLAlchemyError:
        logger.error("notifications_query_failed", exc_info=True)
        raise
    return recipients, counts_by_user


def _build_email_content(cv_counts: list[tuple[str | None, int]], frontend_url: str) -> tuple[str, str]:
    """Build the plain-text and HTML bodies of the digest email.

    Args:
        cv_counts: (cv_name, unseen_count) pairs, one per CV, in digest order.
        frontend_url: Base URL linked at the bottom of the email.

    Returns:
        Tuple of (plain_text, html).
    """
    lines = [f"{name or 'CV sans nom'} : {count} nouvelle(s) offre(s)" for name, count in cv_counts]
    plain_text = "\n".join(lines) + f"\n\n{frontend_url}"

    # cv_name is free text set by the user (CV.name) — escaped before going into the
    # HTML body so a name containing '<' or '&' can't break the markup.
    items_html = "".join(
        f"<li>{html.escape(name or 'CV sans nom')} : {count} nouvelle(s) offre(s)</li>"
        for name, count in cv_counts
    )
    html_body = f"<ul>{items_html}</ul><p><a href=\"{frontend_url}\">{frontend_url}</a></p>"

    return plain_text, html_body


def _send_digest(client: EmailClient, recipient: str, plain_text: str, html_body: str) -> None:
    """Send one digest email via Azure Communication Services Email.

    Args:
        client: Configured EmailClient.
        recipient: Destination address (UserProfile.email).
        plain_text: Plain-text body.
        html_body: HTML body.

    Raises:
        AzureError: If the send request fails. The caller counts this per user and
            continues with the next profile.
    """
    logger.info("notifications_send_started", recipient=recipient)
    try:
        poller = client.begin_send(
            {
                "senderAddress": _sender_address,
                "content": {"subject": DIGEST_SUBJECT, "plainText": plain_text, "html": html_body},
                "recipients": {"to": [{"address": recipient}]},
            }
        )
        poller.result()
    except AzureError:
        logger.error("notifications_send_failed", recipient=recipient, exc_info=True)
        raise
    logger.info("notifications_send_completed", recipient=recipient)


def main() -> None:
    """Send the daily digest email to every opted-in profile, unless outside the scheduled hour."""
    configure_telemetry("notifications")

    now_utc = datetime.now(timezone.utc)
    if not _is_scheduled_local_hour(now_utc):
        logger.info("notifications_skipped_outside_local_window", utc_hour=now_utc.hour)
        return

    try:
        run_migrations()
    except Exception:  # intentional: any migration error must halt the agent
        logger.error("migrations_failed", exc_info=True)
        raise

    today_isoweekday = now_utc.astimezone(PARIS_TZ).isoweekday()
    recipients, counts_by_user = _load_recipients_and_counts(today_isoweekday)

    client = EmailClient(f"https://{_endpoint_hostname}", DefaultAzureCredential())

    sent, skipped_no_email, skipped_no_unseen_offers, failed = 0, 0, 0, 0
    for user_id, email in recipients:
        if not email:
            logger.info("notifications_skipped_no_email", user_id=user_id)
            skipped_no_email += 1
            continue

        cv_counts = counts_by_user.get(user_id, [])
        if not cv_counts:
            logger.info("notifications_skipped_no_unseen_offers", user_id=user_id)
            skipped_no_unseen_offers += 1
            continue

        plain_text, html_body = _build_email_content(cv_counts, _frontend_url)
        try:
            _send_digest(client, email, plain_text, html_body)
            sent += 1
        except AzureError:
            failed += 1

    logger.info(
        "notifications_completed",
        sent=sent,
        skipped_no_email=skipped_no_email,
        skipped_no_unseen_offers=skipped_no_unseen_offers,
        failed=failed,
    )


if __name__ == "__main__":
    main()
