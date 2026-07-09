"""Offer distillation agent — LLM distillation of offer text before embedding.

Consumes one offer_id from distillate-offer-fetched (published by
agents/offer_fetching after upsert, one message per offer with a NULL
embedding). Distills the offer's title+description down to skills/
technologies/methodologies/missions via GPT-4o-mini (verb+object phrasing —
validated in docs/prompts/prompt-matching-llm-distillation-manual-test.md),
embeds the distilled text, and writes both distilled_skills and embedding
back onto the Offer row. Publishes nothing — see
docs/prompts/prompt-offer-distillation-pipeline.md for why there is no
per-offer "done" signal (matching is re-triggered independently, by
agents/matching_heartbeat).

Idempotent: a replayed message (Service Bus at-least-once delivery) is a
no-op if the offer already has an embedding.

Expected environment variables:
    DATABASE_URL: PostgreSQL connection string.
    AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE: Service Bus namespace host.
    AZURE_OPENAI_API_KEY: Azure OpenAI API key.
    AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint URL.
"""

import os

import structlog
from openai import AzureOpenAI, OpenAIError
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from shared.bus import receive_message
from shared.config import ANALYSIS_SEED, ANALYSIS_TEMPERATURE
from shared.db import get_session, run_migrations
from shared.embedder import embed
from shared.models import Offer
from shared.telemetry import configure_telemetry

DISTILLATE_OFFER_FETCHED_QUEUE = "distillate-offer-fetched"
OFFER_TEXT_MAX_CHARS = 8000

AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
if not AZURE_OPENAI_API_KEY:
    raise ValueError("AZURE_OPENAI_API_KEY")

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
if not AZURE_OPENAI_ENDPOINT:
    raise ValueError("AZURE_OPENAI_ENDPOINT")

# Default matches the fixed deployment name used across all environments.
# A missing env var is safe — the deployment name is not secret and does not vary.
AZURE_OPENAI_OFFER_DISTILLATION_DEPLOYMENT = os.environ.get(
    "AZURE_OPENAI_OFFER_DISTILLATION_DEPLOYMENT", "gpt-4o-mini"
)

logger = structlog.get_logger()

_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version="2024-02-01",
)

# Validated prompt (docs/prompts/prompt-offer-distillation-pipeline.md, section 10) — use as-is,
# do not reword.
OFFER_DISTILLATION_SYSTEM_PROMPT = """\
Tu extrais les compétences techniques, technologies, méthodologies et missions professionnelles
concrètes de cette offre d'emploi, sous forme de phrases courtes verbe + objet qui précisent le
niveau de responsabilité (concevoir / opérer / administrer / architecturer un outil, plutôt
qu'utiliser ou exécuter dans un outil en tant qu'environnement). Ne réduis jamais un outil ou une
technologie à son seul nom : indique toujours l'action qui lui est associée dans le texte source.
Exclus explicitement : les avantages salariés et informations RH (mutuelle, salle de sport, tickets
restaurant...), la présentation de l'entreprise, les formules de politesse et de motivation
génériques. Retourne une liste dense, une compétence/mission par ligne, sans phrase d'introduction,
au format "verbe technique + objet" (ex. "opérer des pipelines CI/CD GitLab", pas seulement "CI/CD").
"""

# Reference only — CV-side distillation is not part of this pipeline (only offers are distilled
# here). Kept for if it is reintroduced later (see prompt section 10).
CV_DISTILLATION_SYSTEM_PROMPT = """\
Tu extrais du CV les compétences techniques, technologies, méthodologies et missions professionnelles
concrètes réalisées par le candidat, sous forme de phrases courtes verbe + objet qui précisent son
niveau de responsabilité réel (a-t-il conçu / opéré / architecturé l'outil, ou l'a-t-il seulement
utilisé dans un contexte plus large ?). Ne réduis jamais un outil ou une technologie à son seul nom :
indique l'action associée telle que décrite dans le CV. Exclus explicitement : toute section sans
rapport avec les compétences professionnelles recherchées (loisirs, centres d'intérêt personnels), les
formules de politesse et de motivation génériques. Retourne une liste dense, une compétence/mission
par ligne, sans phrase d'introduction, au format "verbe technique + objet".
"""


def _get_offer(offer_id: str) -> tuple[str, str] | None:
    """Fetch title+description for an offer still pending distillation.

    Returns None both when the offer no longer exists (deleted between
    enqueue and processing) and when it already has an embedding (message
    replayed after a prior successful run) — both are a clean no-op, not an
    error.

    Args:
        offer_id: UUID of the offer record.

    Returns:
        (title, description) tuple, or None if there is nothing to do.

    Raises:
        SQLAlchemyError: On any database error.
    """
    logger.info("offer_distillation_fetch_started", offer_id=offer_id)
    try:
        with get_session() as session:
            row = session.execute(
                select(Offer.title, Offer.description, Offer.embedding).where(Offer.id == offer_id)
            ).one_or_none()
    except SQLAlchemyError:
        logger.error("offer_distillation_fetch_failed", offer_id=offer_id, exc_info=True)
        raise
    if row is None:
        logger.info("offer_distillation_offer_gone", offer_id=offer_id)
        return None
    if row.embedding is not None:
        logger.info("offer_distillation_already_embedded", offer_id=offer_id)
        return None
    return row.title, row.description


def _distill(text: str) -> str:
    """Distill offer text down to skills/technologies/missions only, via GPT-4o-mini.

    No JSON parsing here (unlike cv_analysis's ROME/quality extraction) — the
    prompt returns plain text, one skill per line, so there is no parse
    failure mode to retry on. An OpenAIError (including an empty/blank
    response) propagates to the caller: main() lets it bubble out of
    receive_message, which abandons the message so Service Bus redelivers it
    at the transport level — there is no status column on offers to record
    an application-level error state (unlike cvs.status).

    Args:
        text: Raw "title\\n\\ndescription" text to distill.

    Returns:
        The distilled text (one skill/technology/mission per line).

    Raises:
        OpenAIError: If the API call fails or returns an empty response.
    """
    try:
        response = _openai_client.chat.completions.create(
            model=AZURE_OPENAI_OFFER_DISTILLATION_DEPLOYMENT,
            temperature=ANALYSIS_TEMPERATURE,
            seed=ANALYSIS_SEED,
            messages=[
                {"role": "system", "content": OFFER_DISTILLATION_SYSTEM_PROMPT},
                {"role": "user", "content": text[:OFFER_TEXT_MAX_CHARS]},
            ],
        )
    except OpenAIError:
        logger.error("offer_distillation_openai_error", exc_info=True)
        raise
    distilled = (response.choices[0].message.content or "").strip()
    if not distilled:
        raise OpenAIError("Offer distillation returned an empty response")
    return distilled


def _save_distillation(offer_id: str, distilled_skills: str, embedding: list[float]) -> None:
    """Write the distilled text and its embedding onto the Offer row.

    Args:
        offer_id: UUID of the offer record.
        distilled_skills: Plain-text distilled skills/technologies/missions.
        embedding: 1536-dim embedding vector of the distilled text.

    Raises:
        SQLAlchemyError: On any database error.
    """
    try:
        with get_session() as session:
            session.execute(
                update(Offer)
                .where(Offer.id == offer_id)
                .values(distilled_skills=distilled_skills, embedding=embedding)
            )
            session.commit()
    except SQLAlchemyError:
        logger.error("offer_distillation_save_failed", offer_id=offer_id, exc_info=True)
        raise
    logger.info("offer_distillation_saved", offer_id=offer_id)


def main() -> None:
    """Consume one distillate-offer-fetched message and distill+embed the offer."""
    configure_telemetry("offer-distillation")

    try:
        run_migrations()
    except Exception:  # intentional: any migration error must halt the agent
        logger.error("migrations_failed", exc_info=True)
        raise

    # receive_message is a @contextmanager that yields the decoded payload dict
    # and handles complete/abandon on exit. RuntimeError means no messages available.
    try:
        with receive_message(DISTILLATE_OFFER_FETCHED_QUEUE) as payload:
            offer_id = payload["offer_id"]
            logger.info("offer_distillation_started", offer_id=offer_id)

            fetched = _get_offer(offer_id)
            if fetched is None:
                # Offer deleted, or already distilled by a prior successful run
                # of a replayed message — both a clean no-op, not an error.
                logger.info("offer_distillation_skipped", offer_id=offer_id)
                return
            title, description = fetched

            distilled_skills = _distill(f"{title}\n\n{description}")
            embedding = embed([distilled_skills])[0]
            _save_distillation(offer_id, distilled_skills, embedding)

            logger.info("offer_distillation_completed", offer_id=offer_id)

    except RuntimeError:
        # receive_message returns without yielding when the queue is empty.
        logger.info("offer_distillation_no_message")


if __name__ == "__main__":
    main()
