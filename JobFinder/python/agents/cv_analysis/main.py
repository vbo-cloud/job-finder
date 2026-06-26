"""CV analysis agent — extracts ROME codes from CV text via GPT-4o-mini."""

import json
import os
import re
import time
from datetime import datetime, timezone

import structlog
from openai import AzureOpenAI
from openai import OpenAIError
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from azure.servicebus.exceptions import ServiceBusError

from shared.bus import receive_message, send_message
from shared.db import get_session, run_migrations
from shared.models import CV, UserProfile

# ==============================================================================
# Constants
# ==============================================================================

CV_ANALYSIS_QUEUE = "cv-analysis"
OFFER_READY_QUEUE = "offer-ready"

AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
if not AZURE_OPENAI_API_KEY:
    raise ValueError("AZURE_OPENAI_API_KEY")

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
if not AZURE_OPENAI_ENDPOINT:
    raise ValueError("AZURE_OPENAI_ENDPOINT")

# Default matches the fixed deployment name used across all environments.
# A missing env var is safe — the deployment name is not secret and does not vary.
AZURE_OPENAI_ROME_DEPLOYMENT = os.environ.get("AZURE_OPENAI_ROME_DEPLOYMENT", "gpt-4o-mini")
MAX_ATTEMPTS = 2

ROME_CODE_PATTERN = re.compile(r"^[A-Z]\d{4}$")

logger = structlog.get_logger()

_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version="2024-02-01",
)

# ==============================================================================
# CV fetch
# ==============================================================================


def _get_cv_text(cv_id: str) -> tuple[str, str]:
    """Fetch raw CV text and owner user_id from the database.

    Args:
        cv_id: UUID of the CV record.

    Returns:
        A tuple of (raw_text, user_id).

    Raises:
        ValueError: If no CV with the given ID exists.
        SQLAlchemyError: On any database error.
    """
    logger.info("cv_fetch_started", cv_id=cv_id)
    try:
        with get_session() as session:
            row = session.execute(
                select(CV.raw_text, CV.user_id).where(CV.id == cv_id)
            ).one_or_none()
    except SQLAlchemyError:
        logger.error("cv_fetch_failed", cv_id=cv_id, exc_info=True)
        raise
    if row is None:
        raise ValueError(f"CV {cv_id} not found")
    raw_text, user_id = row
    logger.info("cv_fetch_done", cv_id=cv_id, chars=len(raw_text))
    return raw_text, user_id


# ==============================================================================
# Status update
# ==============================================================================


def _set_cv_status(cv_id: str, status: str) -> None:
    """Update the processing status of a CV record.

    Args:
        cv_id: UUID of the CV record.
        status: New status value — one of 'processing', 'done', 'error'.

    Raises:
        SQLAlchemyError: On any database error.
    """
    logger.info("cv_status_update", cv_id=cv_id, status=status)
    try:
        with get_session() as session:
            session.execute(
                update(CV).where(CV.id == cv_id).values(status=status)
            )
            session.commit()
    except SQLAlchemyError:
        logger.error("cv_status_update_failed", cv_id=cv_id, status=status, exc_info=True)
        raise


# ==============================================================================
# ROME extraction
# ==============================================================================


def _extract_rome_codes(raw_text: str) -> list[str]:
    """Extract ROME occupation codes from CV text using GPT-4o-mini.

    Retries up to MAX_ATTEMPTS times on JSON parse errors or empty results.
    OpenAI API errors are not retried — they are fatal.

    Args:
        raw_text: Plain text content of the CV.

    Returns:
        A list of 3–5 valid ROME codes (letter + 4 digits, e.g. "M1805").

    Raises:
        OpenAIError: If the API call fails.
        ValueError: If all retry attempts fail to produce valid ROME codes.
    """
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("rome_extraction_attempt", attempt=attempt, chars=len(raw_text))
            response = _openai_client.chat.completions.create(
                model=AZURE_OPENAI_ROME_DEPLOYMENT,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Tu es un expert en classification des métiers. "
                            "Analyse le CV fourni et retourne UNIQUEMENT un objet JSON valide "
                            'de la forme {"rome_codes": ["XXXXX", ...]} contenant entre 3 et 5 '
                            "codes ROME pertinents (format : lettre + 4 chiffres, ex: M1805). "
                            "Ne retourne rien d'autre que le JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"CV :\n\n{raw_text[:8000]}",
                    },
                ],
            )
            raw_codes: list[str] = json.loads(
                response.choices[0].message.content
            )["rome_codes"]
            valid_codes = [c for c in raw_codes if ROME_CODE_PATTERN.match(c)]
            if not valid_codes:
                raise ValueError(f"No valid ROME codes in GPT response: {raw_codes}")
            logger.info("rome_extraction_succeeded", attempt=attempt, codes=valid_codes)
            return valid_codes
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("rome_extraction_attempt_failed", attempt=attempt, exc_info=True)
            last_error = e
            time.sleep(1)
        except OpenAIError:
            logger.error("rome_extraction_openai_error", attempt=attempt, exc_info=True)
            raise
    logger.error("rome_extraction_all_attempts_failed", attempts=MAX_ATTEMPTS)
    assert last_error is not None  # loop runs MAX_ATTEMPTS times — always set
    raise last_error


# ==============================================================================
# Profile update
# ==============================================================================


def _update_rome_codes(user_id: str, rome_codes: list[str]) -> None:
    """Update rome_codes on the user profile.

    Args:
        user_id: The user whose profile to update.
        rome_codes: Validated ROME codes extracted from the CV.

    Raises:
        SQLAlchemyError: On any database error.
    """
    logger.info("rome_update_started", user_id=user_id, rome_codes=rome_codes)
    try:
        with get_session() as session:
            now = datetime.now(timezone.utc)
            result = session.execute(
                update(UserProfile)
                .where(UserProfile.user_id == user_id)
                .values(rome_codes=rome_codes, updated_at=now)
            )
            if result.rowcount == 0:
                raise ValueError(f"UserProfile not found for user_id={user_id}")
            session.commit()
    except SQLAlchemyError:
        logger.error("rome_update_failed", user_id=user_id, exc_info=True)
        raise
    logger.info("rome_update_done", user_id=user_id)


# ==============================================================================
# Entry point
# ==============================================================================


def main() -> None:
    """Consume one cv-analysis message, extract ROME codes, and dispatch offer-ready."""
    from shared.telemetry import configure_telemetry
    configure_telemetry("cv-analysis")

    try:
        run_migrations()
    except Exception:  # intentional: Alembic can raise varied errors; any migration failure must halt the agent
        logger.error("migrations_failed", exc_info=True)
        raise

    # receive_message is a @contextmanager that yields the decoded payload dict
    # and handles complete/abandon on exit. RuntimeError means no messages available.
    try:
        with receive_message(CV_ANALYSIS_QUEUE) as payload:
            cv_id = payload["cv_id"]

            logger.info("cv_analysis_started", cv_id=cv_id)

            _set_cv_status(cv_id, "processing")

            try:
                raw_text, user_id = _get_cv_text(cv_id)
                rome_codes = _extract_rome_codes(raw_text)
                _update_rome_codes(user_id, rome_codes)
            except Exception:
                # Catch-all: any failure in extraction or ROME update must mark the CV
                # as errored before re-raising, regardless of which step failed.
                _set_cv_status(cv_id, "error")
                raise

            _set_cv_status(cv_id, "done")

            try:
                send_message(
                    OFFER_READY_QUEUE,
                    {
                        "run_date": datetime.now(timezone.utc).date().isoformat(),
                        "rome_codes": rome_codes,
                        "new_offers_count": 0,
                        "embedded_count": 0,
                        "trigger": "cv_analysis",
                    },
                )
                logger.info("cv_analysis_offer_ready_sent", cv_id=cv_id, user_id=user_id)
            except ServiceBusError:
                logger.error("cv_analysis_offer_ready_failed", cv_id=cv_id, user_id=user_id, exc_info=True)
                raise

            logger.info("cv_analysis_completed", cv_id=cv_id, user_id=user_id, rome_codes=rome_codes)

    except RuntimeError:
        # receive_message returns without yielding when the queue is empty.
        logger.info("cv_analysis_no_message")


if __name__ == "__main__":
    main()
