"""Feedback endpoint — relays user reviews/bug reports to the portfolio's contact Function."""

import os

import requests
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth import UserIdentity, get_current_identity
from dependencies import get_db
from schemas import FeedbackCreate
from shared.models import UserProfile

# Anonymous-auth Azure Function URL (portfolio repo, sendContactEmail) — not a
# secret, but deliberately no fail-fast at import time like ENTRA_EXTERNAL_TENANT_ID:
# it stays unset until Vincent provisions it post-deploy (see docs/JOURNAL.md), and
# that must only degrade this one endpoint, never take down the whole webapp on boot.
PORTFOLIO_CONTACT_FUNCTION_URL = os.environ.get("PORTFOLIO_CONTACT_FUNCTION_URL", "")

CONTACT_FUNCTION_TIMEOUT_SECONDS = 15  # portfolio Function documents a 1-2s cold start
FALLBACK_EMAIL_DOMAIN = "jobfinder.local"

# Uppercase French labels for the "RESSENTI ..." line Vincent scans for when
# triaging his inbox — None means the (optional) smiley picker was left unset.
_SENTIMENT_LABELS = {"positif": "POSITIF", "neutre": "NEUTRE", "negatif": "NEGATIF"}

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = structlog.get_logger()


def _resolve_sender(identity: UserIdentity, session: Session) -> tuple[str, str, bool]:
    """Resolve the (name, email) pair to relay, falling back when the JWT omits them.

    identity.email/display_name are best-effort claims and are None for some Entra
    External ID user flows (see auth.py's UserIdentity docstring) — the relayed
    Function requires both fields non-empty, so a profile-stored value, then an
    unjoinable placeholder, keep the request valid either way.

    Args:
        identity: Authenticated identity claims from the JWT.
        session: Active database session, used only to read a UserProfile fallback.

    Returns:
        A (name, email, email_available) tuple — email_available is False when
        neither the JWT nor the stored profile had a real address, so the caller
        can flag the relayed message as unreachable.

    Raises:
        SQLAlchemyError: If the fallback UserProfile lookup fails.
    """
    profile = None
    # Skip the DB round-trip entirely when the JWT already carries both claims —
    # the common case, since most Entra External ID flows do emit them.
    if identity.email is None or identity.display_name is None:
        try:
            profile = session.execute(
                select(UserProfile).where(UserProfile.user_id == identity.user_id)
            ).scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(
                "feedback_create_profile_lookup_failed", user_id=identity.user_id, exc_info=True
            )
            raise

    email = identity.email or (profile.email if profile else None)
    email_available = email is not None
    if email is None:
        email = f"{identity.user_id}@{FALLBACK_EMAIL_DOMAIN}"

    name = identity.display_name or (profile.display_name if profile else None) or identity.user_id

    return name, email, email_available


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def create_feedback(
    body: FeedbackCreate,
    identity: UserIdentity = Depends(get_current_identity),
    session: Session = Depends(get_db),
) -> None:
    """Relay a user review or bug report to Vincent's inbox via the portfolio's Function.

    No dedicated table: this is an email-only relay, not a stored resource (see
    docs/JOURNAL.md for the decision). name/email always come from the validated
    JWT (or the stored profile as fallback) — never from body, so they can't be
    spoofed by the client. The relayed subject is prefixed
    "JOBFINDER - AVIS/BUG : <subject>" and the message body opens with a
    "RESSENTI POSITIF/NEUTRE/NEGATIF/NON INDIQUE" line so Vincent can triage
    his inbox without opening every message.

    Args:
        body: Feedback type, subject, message and optional sentiment.
        identity: Authenticated identity claims from the JWT.
        session: Active database session (fallback email/name lookup only).

    Raises:
        HTTPException: 502 if the relay Function is unreachable, unconfigured,
            or itself rejects the request.
        SQLAlchemyError: If the fallback UserProfile lookup fails (500).
    """
    user_id = identity.user_id
    logger.info("feedback_create_started", user_id=user_id, type=body.type)

    if not PORTFOLIO_CONTACT_FUNCTION_URL:
        logger.error("feedback_create_not_configured", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Feedback relay is not configured.",
        )

    name, email, email_available = _resolve_sender(identity, session)
    label = "BUG" if body.type == "bug" else "AVIS"
    subject = f"JOBFINDER - {label} : {body.subject}"

    sentiment_label = _SENTIMENT_LABELS.get(body.sentiment, "NON INDIQUE")
    message = f"RESSENTI {sentiment_label}\n\n{body.message}"
    if not email_available:
        message = f"{message}\n\n(email indisponible — impossible de répondre directement à cet utilisateur)"

    try:
        response = requests.post(
            PORTFOLIO_CONTACT_FUNCTION_URL,
            json={"name": name, "email": email, "subject": subject, "message": message},
            timeout=CONTACT_FUNCTION_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("feedback_create_relay_failed", user_id=user_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send feedback. Please try again later.",
        ) from e

    logger.info("feedback_create_completed", user_id=user_id, type=body.type)
