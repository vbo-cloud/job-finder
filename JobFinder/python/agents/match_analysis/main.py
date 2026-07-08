"""Match analysis agent — GPT-4o-mini analysis of a single CV<->offer pair (see ADR-018)."""

import json
import os
import time
from datetime import datetime, timezone

import structlog
from openai import AzureOpenAI
from openai import OpenAIError
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from shared.bus import receive_message
from shared.db import get_session, run_migrations
from shared.models import CV, Match, MatchAnalysis, Offer, UserProfile
from shared.telemetry import configure_telemetry

# ==============================================================================
# Constants
# ==============================================================================

MATCH_ANALYSIS_QUEUE = "match-analysis"
MAX_ATTEMPTS = 2
CV_TEXT_MAX_CHARS = 8000
OFFER_TEXT_MAX_CHARS = 4000

AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
if not AZURE_OPENAI_API_KEY:
    raise ValueError("AZURE_OPENAI_API_KEY")

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
if not AZURE_OPENAI_ENDPOINT:
    raise ValueError("AZURE_OPENAI_ENDPOINT")

# Default matches the fixed deployment name used across all environments.
# A missing env var is safe — the deployment name is not secret and does not vary.
AZURE_OPENAI_MATCH_ANALYSIS_DEPLOYMENT = os.environ.get("AZURE_OPENAI_MATCH_ANALYSIS_DEPLOYMENT", "gpt-4o-mini")

logger = structlog.get_logger()

_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version="2024-02-01",
)

MATCH_ANALYSIS_SYSTEM_PROMPT = (
    "Tu es un expert en recrutement. Compare le CV et l'offre d'emploi fournis, en tenant "
    "compte de l'intention du candidat (expérience et description personnelle) si elle est "
    "fournie. Retourne UNIQUEMENT un objet JSON valide de la forme "
    '{"matched_skills": [...], "points_forts": [...], "points_amelioration": [...], '
    '"synthese": "<texte>"}. matched_skills liste les compétences du CV qui correspondent aux '
    "besoins de l'offre (courtes, affichables en badge). points_forts et points_amelioration "
    "évaluent la pertinence du candidat pour cette offre précise. synthese est une phrase "
    'unique de 1 à 2 lignes, orientée candidat, du type "Cette offre est pertinente pour vous '
    'car...". Ne retourne rien d\'autre que le JSON.'
)


# ==============================================================================
# Match context fetch
# ==============================================================================


def _get_match_context(match_id: str) -> dict:
    """Fetch the CV text, offer fields, and profile intent for a match in one query.

    Args:
        match_id: UUID of the match to analyse.

    Returns:
        dict with keys cv_text, offer_title, offer_company, offer_description,
        offer_skills, experience_level, candidate_description.

    Raises:
        ValueError: If the match no longer exists (CV or match deleted between
            enqueue and processing — a normal case, not an error).
        SQLAlchemyError: On any database error.
    """
    logger.info("match_context_fetch_started", match_id=match_id)
    try:
        with get_session() as session:
            row = session.execute(
                select(
                    CV.raw_text,
                    Offer.title,
                    Offer.company,
                    Offer.description,
                    Offer.skills,
                    UserProfile.experience_level,
                    UserProfile.candidate_description,
                )
                .select_from(Match)
                .join(CV, Match.cv_id == CV.id)
                .join(Offer, Match.offer_id == Offer.id)
                .outerjoin(UserProfile, UserProfile.user_id == CV.user_id)
                .where(Match.id == match_id)
            ).one_or_none()
    except SQLAlchemyError:
        logger.error("match_context_fetch_failed", match_id=match_id, exc_info=True)
        raise
    if row is None:
        raise ValueError(f"Match {match_id} not found")
    logger.info("match_context_fetch_done", match_id=match_id)
    return {
        "cv_text": row.raw_text,
        "offer_title": row.title,
        "offer_company": row.company,
        "offer_description": row.description,
        "offer_skills": list(row.skills or []),
        "experience_level": row.experience_level,
        "candidate_description": row.candidate_description,
    }


# ==============================================================================
# Pair analysis
# ==============================================================================


def _analyze_match(context: dict) -> dict:
    """Analyze one CV<->offer pair with GPT-4o-mini.

    Retries up to MAX_ATTEMPTS times on JSON parse errors — same policy as the
    cv_analysis agent. OpenAI API errors are not retried.

    Args:
        context: Match context dict as returned by _get_match_context.

    Returns:
        dict with keys matched_skills (list[str]), points_forts (list[str]),
        points_amelioration (list[str]), synthese (str).

    Raises:
        OpenAIError: If the API call fails.
        ValueError: If all retry attempts fail to produce valid JSON.
    """
    # Same fragments as _build_intent_text in routers/profile.py — duplicated on
    # purpose: agents must not depend on agents/webapp.
    fragments = []
    experience_level = context.get("experience_level")
    if experience_level == "0-2":
        fragments.append("Profil junior/débutant, 0 à 2 ans d'expérience")
    elif experience_level == "2-5":
        fragments.append("Profil confirmé, 2 à 5 ans d'expérience")
    elif experience_level == "5+":
        fragments.append("Profil senior, 5 ans d'expérience et plus")
    candidate_description = context.get("candidate_description")
    if candidate_description and candidate_description.strip():
        fragments.append(candidate_description.strip())
    intent_text = "\n".join(fragments) if fragments else "Aucune intention renseignée par l'utilisateur."

    user_content = (
        f"Intention du candidat :\n{intent_text}\n\n"
        f"CV :\n{context['cv_text'][:CV_TEXT_MAX_CHARS]}\n\n"
        f"Offre : {context['offer_title']} — {context['offer_company']}\n"
        f"Description :\n{context['offer_description'][:OFFER_TEXT_MAX_CHARS]}\n"
        f"Compétences demandées : {', '.join(context['offer_skills'])}"
    )

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("match_analysis_attempt", attempt=attempt)
            response = _openai_client.chat.completions.create(
                model=AZURE_OPENAI_MATCH_ANALYSIS_DEPLOYMENT,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": MATCH_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            data = json.loads(response.choices[0].message.content)
            result = {
                "matched_skills": [str(x) for x in data.get("matched_skills", [])],
                "points_forts": [str(x) for x in data.get("points_forts", [])],
                "points_amelioration": [str(x) for x in data.get("points_amelioration", [])],
                "synthese": str(data.get("synthese", "")),
            }
            logger.info("match_analysis_succeeded", attempt=attempt, matched_skills_count=len(result["matched_skills"]))
            return result
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning("match_analysis_attempt_failed", attempt=attempt, exc_info=True)
            last_error = e
            time.sleep(1)
        except OpenAIError:
            logger.error("match_analysis_openai_error", attempt=attempt, exc_info=True)
            raise
    logger.error("match_analysis_all_attempts_failed", attempts=MAX_ATTEMPTS)
    assert last_error is not None  # loop runs MAX_ATTEMPTS times — always set
    raise ValueError("Match analysis failed to produce valid JSON") from last_error


# ==============================================================================
# Status update
# ==============================================================================


def _update_match_analysis(match_id: str, status: str, **fields) -> None:
    """Update the match_analyses row for a match.

    The row always exists at this point — created by the enqueuer (matching's
    auto top-N or the manual endpoint) — so a plain UPDATE suffices, unlike
    _upsert_cv_analysis in the cv_analysis agent. completed_at is only set when
    status is terminal ("done" or "error").

    Args:
        match_id: UUID string of the analysed match.
        status: New status value — one of 'processing', 'done', 'error'.
        **fields: Analysis result columns (matched_skills, points_forts, ...).

    Raises:
        SQLAlchemyError: On any database error.
    """
    logger.info("match_analysis_status_update", match_id=match_id, status=status)
    values = {"status": status, **fields}
    if status in ("done", "error"):
        values["completed_at"] = datetime.now(timezone.utc)
    try:
        with get_session() as session:
            session.execute(
                update(MatchAnalysis).where(MatchAnalysis.match_id == match_id).values(**values)
            )
            session.commit()
    except SQLAlchemyError:
        logger.error("match_analysis_status_update_failed", match_id=match_id, status=status, exc_info=True)
        raise


# ==============================================================================
# Entry point
# ==============================================================================


def main() -> None:
    """Consume one match-analysis message and analyse the CV<->offer pair."""
    configure_telemetry("match-analysis")

    try:
        run_migrations()
    except Exception:  # intentional: any migration error must halt the agent
        logger.error("migrations_failed", exc_info=True)
        raise

    # receive_message is a @contextmanager that yields the decoded payload dict
    # and handles complete/abandon on exit. RuntimeError means no messages available.
    try:
        with receive_message(MATCH_ANALYSIS_QUEUE) as payload:
            match_id = payload["match_id"]
            logger.info("match_analysis_started", match_id=match_id)
            _update_match_analysis(match_id, "processing")
            try:
                context = _get_match_context(match_id)
            except ValueError:
                # Match or CV deleted between enqueue and processing.
                # Complete the message cleanly — no retry, no dead-letter.
                logger.info("match_analysis_match_gone_skipping", match_id=match_id)
                return
            try:
                result = _analyze_match(context)
                _update_match_analysis(match_id, "done", **result)
            except (OpenAIError, SQLAlchemyError, ValueError):
                # ValueError — _analyze_match exhausted its JSON retries; must
                # mark the row errored, not be mistaken for a deleted match.
                _update_match_analysis(match_id, "error")
                raise
            logger.info("match_analysis_completed", match_id=match_id)

    except RuntimeError:
        # receive_message returns without yielding when the queue is empty.
        logger.info("match_analysis_no_message")


if __name__ == "__main__":
    main()
