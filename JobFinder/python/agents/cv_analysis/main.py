"""CV analysis agent — ROME code extraction and CV quality analysis via GPT-4o-mini."""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog
from openai import AzureOpenAI
from openai import OpenAIError
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from azure.servicebus.exceptions import ServiceBusError

from shared.bus import receive_message, send_message
from shared.config import ANALYSIS_SEED, ANALYSIS_TEMPERATURE
from shared.db import get_session, run_migrations
from shared.models import CV, CvAnalysis, UserProfile
from shared.telemetry import configure_telemetry

# ==============================================================================
# Constants
# ==============================================================================

CV_ANALYSIS_QUEUE = "cv-analysis"
START_MATCHING_QUEUE = "start-matching"

AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
if not AZURE_OPENAI_API_KEY:
    raise ValueError("AZURE_OPENAI_API_KEY")

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
if not AZURE_OPENAI_ENDPOINT:
    raise ValueError("AZURE_OPENAI_ENDPOINT")

# Default matches the fixed deployment name used across all environments.
# A missing env var is safe — the deployment name is not secret and does not vary.
AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT", "gpt-4o-mini")
MAX_ATTEMPTS = 2

ROME_CODE_PATTERN = re.compile(r"^[A-Z]\d{4}$")

_REFERENTIEL_PATH = Path(__file__).parent.parent.parent / "shared" / "rome_referentiel.json"
ROME_REFERENTIEL: dict[str, str] = json.loads(
    _REFERENTIEL_PATH.read_text(encoding="utf-8")
)

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

ROME_EXTRACTION_SYSTEM_PROMPT = (
    "Tu es un expert en classification des métiers français selon le référentiel ROME. "
    "Analyse le CV fourni et retourne UNIQUEMENT un objet JSON valide "
    'de la forme {"rome_codes": ["M1805", "M1802", ...]} '
    "contenant entre 1 et 5 codes ROME pertinents "
    "(format : une lettre majuscule suivie de 4 chiffres, ex : M1805). "
    "RÈGLE — le code doit refléter le métier ou la fonction réellement exercée par LE "
    "CANDIDAT lui-même, jamais le secteur d'activité, les produits ou outils "
    "vendus/utilisés, ou le métier des personnes ou clients mentionnés dans le CV. "
    "Exemple : un commercial qui vend des solutions informatiques reste un métier "
    "commercial (codes de la famille vente/administration des ventes), pas un métier "
    "de développeur ou d'administrateur système, même si le CV contient beaucoup de "
    "vocabulaire technique. "
    "RÈGLE — ne complète jamais la liste avec un code supplémentaire seulement pour "
    "atteindre un nombre minimal : un CV clairement mono-métier peut n'avoir qu'un "
    "seul code pertinent. "
    "Ne retourne rien d'autre que le JSON."
)


def _extract_rome_codes(raw_text: str) -> list[dict[str, str]]:
    """Extract ROME occupation codes from CV text using GPT-4o-mini.

    GPT-4o-mini identifies candidate codes only — no labels. Each code is
    validated against ROME_REFERENTIEL: codes that fail the regex or are absent
    from the referential are silently rejected (hallucination protection). The
    label is always sourced from the referential, never from GPT output.

    Two invariants, both required after the same CV produced two disjoint code
    sets on consecutive uploads (see docs/prompts/prompt-cv-analysis-rome-code-
    determinism-and-precision.md for the full diagnostic):
    - Determinism: temperature/seed pinned to ANALYSIS_TEMPERATURE/ANALYSIS_SEED,
      same as _analyze_cv_quality and match_analysis's _analyze_match.
    - Precision: the system prompt requires codes to reflect the candidate's own
      occupation, never the sector/products/tools they work with or the
      occupation of people mentioned in the CV — and no longer pads the result
      to a 3-code floor when the CV is genuinely mono-occupation.

    Retries up to MAX_ATTEMPTS times on JSON parse errors or empty results.
    OpenAI API errors are not retried — they are fatal.

    Args:
        raw_text: Plain text content of the CV.

    Returns:
        A list of 1–5 dicts, each with "code" and "label" keys,
        e.g. [{"code": "M1805", "label": "Études et développement informatique"}].

    Raises:
        OpenAIError: If the API call fails.
        ValueError: If all retry attempts fail to produce valid ROME codes.
    """
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("rome_extraction_attempt", attempt=attempt, chars=len(raw_text))
            response = _openai_client.chat.completions.create(
                model=AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT,
                response_format={"type": "json_object"},
                temperature=ANALYSIS_TEMPERATURE,
                seed=ANALYSIS_SEED,
                messages=[
                    {"role": "system", "content": ROME_EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"CV :\n\n{raw_text[:8000]}",
                    },
                ],
            )
            raw_codes: list = json.loads(response.choices[0].message.content)["rome_codes"]
            valid_items = []
            for code in raw_codes:
                if not isinstance(code, str):
                    continue
                code = code.upper().strip()
                if not ROME_CODE_PATTERN.match(code):
                    continue
                if code not in ROME_REFERENTIEL:
                    logger.warning("rome_code_not_in_referentiel", code=code)
                    continue
                valid_items.append({"code": code, "label": ROME_REFERENTIEL[code]})
            if not valid_items:
                raise ValueError(f"No valid ROME codes after referential lookup: {raw_codes}")
            logger.info("rome_extraction_succeeded", attempt=attempt, codes=[i["code"] for i in valid_items])
            return valid_items
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


def _merge_rome_codes(user_id: str, cv_id: str, rome_items: list[dict[str, str]]) -> None:
    """Merge extracted ROME codes into the user profile dict with row-level locking.

    Each item in rome_items must have "code" and "label" keys. The cv_id is
    appended to the code's cv_ids list if not already present. The label is
    always updated to the latest value from the ROME referential.

    Uses SELECT ... FOR UPDATE to prevent concurrent analyses from overwriting
    each other's data.

    Args:
        user_id: The user whose profile to update.
        cv_id: UUID string of the CV being analysed.
        rome_items: List of dicts with "code" and "label" keys.

    Raises:
        ValueError: If no UserProfile exists for user_id.
        SQLAlchemyError: On any database error.
    """
    codes_log = [item["code"] for item in rome_items]
    logger.info("rome_merge_started", user_id=user_id, cv_id=cv_id, codes=codes_log)
    try:
        with get_session() as session:
            profile = session.execute(
                select(UserProfile)
                .where(UserProfile.user_id == user_id)
                .with_for_update()
            ).scalar_one_or_none()
            if profile is None:
                raise ValueError(f"UserProfile not found for user_id={user_id}")

            current: dict = dict(profile.rome_codes or {})
            for item in rome_items:
                code = item["code"]
                label = item["label"]
                if code not in current:
                    current[code] = {"cv_ids": [], "label": label}
                if cv_id not in current[code]["cv_ids"]:
                    current[code]["cv_ids"].append(cv_id)
                current[code]["label"] = label

            profile.rome_codes = current
            profile.updated_at = datetime.now(timezone.utc)
            session.commit()
    except SQLAlchemyError:
        logger.error("rome_merge_failed", user_id=user_id, cv_id=cv_id, exc_info=True)
        raise
    logger.info("rome_merge_done", user_id=user_id, cv_id=cv_id)


# ==============================================================================
# CV quality analysis
# ==============================================================================

CV_QUALITY_SYSTEM_PROMPT = """\
Tu es un coach carrière expert du marché de l'emploi français, spécialisé en optimisation de CV pour \
les systèmes ATS. Tu analyses le CV fourni et retournes UNIQUEMENT un objet JSON valide, structuré \
exactement comme décrit ci-dessous.

Format de sortie JSON :
{
  "ats_score": <entier 0-100>,
  "synthese": string,               // 3 à 5 phrases en prose, ton coach — l'impression générale que
                                    // donnerait ce CV à un recruteur qui le découvre. Ne reformule
                                    // pas points_forts/points_faibles sous forme de paragraphe : la
                                    // synthese apporte une lecture d'ensemble (ex. le fil conducteur
                                    // du parcours, l'impression de sérieux/clarté globale), les points
                                    // en dessous apportent le détail. Aucun fait ne doit apparaître à
                                    // la fois ici et dans un point_fort/point_faible avec la même
                                    // formulation.
  "points_forts": [string, ...],
  "points_faibles": [string, ...],
  "suggestions": [string, ...],
  "coherence_intention": string    // 1 à 3 phrases : le CV est-il cohérent avec l'expérience/la
                                    // description candidat fournies ci-dessous — chaîne vide si
                                    // aucune de ces informations n'est fournie.
}

RÈGLE — non-redondance : chaque fait ou observation n'apparaît qu'une seule fois dans l'ensemble de la
réponse, y compris à l'intérieur d'une même liste. Si l'absence de résultats chiffrés est un point
faible, il n'a besoin d'être mentionné qu'une fois dans points_faibles — ne le répète pas sous une
autre formulation dans suggestions, et ne propose pas deux suggestions différentes qui reviennent au
même correctif.
❌ Interdit (le même fait répété trois fois) :
  points_faibles: ["Les expériences ne mentionnent aucun résultat chiffré"]
  suggestions: ["Ajouter des chiffres aux réalisations de chaque expérience",
                 "Quantifier l'impact des projets dans une section dédiée"]
✅ Attendu (le fait une fois, une seule suggestion actionnable) :
  points_faibles: ["Les expériences ne mentionnent aucun résultat chiffré"]
  suggestions: ["Ajouter un résultat mesurable à chaque expérience (ex. gain de temps obtenu, taille
                 du projet, nombre d'utilisateurs)"]

RÈGLE — ancrage dans le texte réel : points_forts et points_faibles doivent référencer un élément
identifiable de CE CV (un intitulé de poste, un projet nommé, une compétence précise, une formulation
maladroite repérable) — jamais une observation générique qui s'appliquerait à n'importe quel CV bien
mis en page.
❌ Interdit : "Structure claire avec des sections bien définies"
✅ Attendu : "La section Projets détaille chaque réalisation avec un résultat mesurable (ex. votre
projet Job Finder), ce qui rend vos compétences vérifiables plutôt qu'affirmées"

RÈGLE — suggestions personnalisées à l'intention du candidat : avant d'écrire une suggestion, identifie
un élément concret et vérifiable dans l'intention du candidat fournie ci-dessous (niveau d'expérience,
description personnelle) ou, à défaut, dans le CV lui-même — la suggestion doit s'appuyer dessus plutôt
que proposer un conseil de carrière générique interchangeable.
Exemple (intention fournie : "Profil junior/débutant, 0 à 2 ans d'expérience\\nReconversion Unity vers
Cloud/Azure, certification AZ-104 obtenue") :
❌ Interdit (générique, ignore l'intention) : "Suivre une formation complémentaire pour renforcer vos
compétences techniques."
✅ Attendu (s'appuie sur l'intention) : "Mettre la certification AZ-104 en évidence dès le haut du CV,
pas seulement dans la section formation — c'est l'élément qui rassure le plus sur votre niveau réel en
reconversion."

RÈGLE — pas de décomposition inventée du score : si la synthese ou un autre champ évoque le score,
reste qualitatif — ne prétends jamais décomposer ats_score en un détail de points gagnés/perdus par
critère que tu ne connais pas réellement (ex. "75 = 40 points de structure + 35 de clarté" est interdit).

CHECKLIST OBLIGATOIRE — avant de rédiger points_faibles et suggestions, vérifie explicitement chacun
des quatre angles suivants sur CE CV — ne saute silencieusement aucun d'entre eux :
1. Cohérence chronologique : les dates de chaque expérience sont-elles dans le bon ordre (début avant
   fin) ? Y a-t-il des trous ou des chevauchements non expliqués entre deux expériences ?
2. Impact et formulation : les réalisations sont-elles quantifiées (résultat mesurable, taille de
   projet, gain de temps) ou seulement décrites en tâches ? Des verbes faibles ou des répétitions de
   formulation entre plusieurs expériences ?
3. Structure et lisibilité : la hiérarchie de l'information est-elle claire ? Une section est-elle
   disproportionnée (trop vide ou trop dense) par rapport à son importance réelle pour le poste visé ?
4. Cohérence interne : une information contredit-elle une autre partie du CV (ex. une compétence
   listée jamais illustrée dans les expériences, un intitulé de poste incohérent avec les tâches
   décrites) ?
Si un angle ne révèle réellement aucun problème après vérification, ne l'invente pas dans
points_faibles — mais la vérification elle-même n'est jamais optionnelle.
Exemple (dates fournies dans le CV : "Développeur X — Entreprise Y, 09/2024 - 09/2022") :
❌ Interdit (l'incohérence n'est pas relevée, alors qu'elle saute aux yeux à la simple lecture) :
points_faibles ne mentionne que des généralités de style ou de mise en forme.
✅ Attendu : points_faibles inclut "Les dates de l'expérience chez Entreprise Y semblent inversées
(09/2024 - 09/2022) — à corriger, une date de fin antérieure à la date de début nuit à la crédibilité
du document pour un recruteur ou un système ATS."

RÈGLE — exhaustivité : ne te limite pas à quelques points représentatifs. Relis le CV section par
section (objectif, expériences, formation, compétences, mise en forme) et note CHAQUE erreur ou
faiblesse réelle que tu identifies — faute de frappe, date incohérente, verbe faible, répétition,
information manquante, formulation ambiguë — même si cela produit une liste longue. Une liste courte
n'est acceptable que si le CV est réellement irréprochable sur ce point ; ce n'est pas un objectif de
longueur mais de couverture réelle. Ne t'arrête pas après 3 points par construction — continue tant
qu'il reste une observation authentique à faire.

RÈGLE — ne jamais suggérer d'ajouter une information personnelle ou une préférence (mode de travail,
disponibilité, prétentions salariales, mobilité géographique...) qui n'est mentionnée ni dans le CV ni
dans l'intention du candidat fournie ci-dessous. Si candidate_description est vide ou ne mentionne pas
ce point, ne le soulève pas comme point faible ni comme suggestion — l'absence d'une information que
l'utilisateur n'a jamais fournie n'est pas un défaut du CV. Par ailleurs, une préférence de télétravail
ne se formule normalement pas sur un CV français (plutôt en lettre de motivation ou en entretien) — ne
la recommande pas comme ajout au corps du CV même si elle est explicitement mentionnée dans l'intention
du candidat ; dans ce cas, signale plutôt que cette préférence gagnerait à être mise en avant ailleurs
dans la candidature (lettre de motivation, message de candidature), pas dans le CV lui-même.

RÈGLE — expertise perceptible : tu écris comme un recruteur technique senior spécialisé dans le domaine
du poste visé par le candidat (cloud, DevOps, IA, ou équivalent selon l'intention fournie), pas comme un
résumé générique. Quand tu cites un problème de formulation, reformule ou cite la phrase exacte du CV
concernée plutôt que de rester abstrait ("la description du poste chez X répète presque mot pour mot..."
plutôt que "certaines descriptions sont répétitives"). La synthese doit donner le sentiment d'une
lecture méthodique de bout en bout, pas d'un survol — et ne commence jamais par une formule générique
qui pourrait ouvrir n'importe quelle analyse, du type "Ce CV présente un candidat solide...".

Ton : coach bienveillant et constructif, jamais un audit froid. Ne retourne rien d'autre que le JSON.
"""


def _get_profile_intent(user_id: str) -> tuple[str | None, str | None]:
    """Fetch the profile intent fields (experience level, candidate description) for a user.

    Args:
        user_id: The user whose profile to read.

    Returns:
        A tuple of (experience_level, candidate_description) — (None, None) if
        the user has no profile row.

    Raises:
        SQLAlchemyError: On any database error.
    """
    logger.info("profile_intent_fetch_started", user_id=user_id)
    try:
        with get_session() as session:
            row = session.execute(
                select(UserProfile.experience_level, UserProfile.candidate_description)
                .where(UserProfile.user_id == user_id)
            ).one_or_none()
    except SQLAlchemyError:
        logger.error("profile_intent_fetch_failed", user_id=user_id, exc_info=True)
        raise
    if row is None:
        logger.info("profile_intent_fetch_done", user_id=user_id, has_profile=False)
        return None, None
    experience_level, candidate_description = row
    logger.info("profile_intent_fetch_done", user_id=user_id, has_profile=True)
    return experience_level, candidate_description


def _analyze_cv_quality(
    raw_text: str, experience_level: str | None, candidate_description: str | None
) -> dict:
    """Analyze CV structure, phrasing, ATS-friendliness, and coherence with declared intent.

    Retries up to MAX_ATTEMPTS times on JSON parse errors — same policy as
    _extract_rome_codes. OpenAI API errors are not retried.

    Returns:
        dict with keys ats_score (int, clamped 0-100), synthese (str),
        points_forts (list[str]), points_faibles (list[str]),
        suggestions (list[str]), coherence_intention (str).

    Raises:
        OpenAIError: If the API call fails.
        ValueError: If all retry attempts fail to produce valid JSON.
    """
    # Same fragments as _build_intent_text in routers/profile.py — duplicated on
    # purpose: agents must not depend on agents/webapp.
    fragments = []
    if experience_level == "0-2":
        fragments.append("Profil junior/débutant, 0 à 2 ans d'expérience")
    elif experience_level == "2-5":
        fragments.append("Profil confirmé, 2 à 5 ans d'expérience")
    elif experience_level == "5+":
        fragments.append("Profil senior, 5 ans d'expérience et plus")
    if candidate_description and candidate_description.strip():
        fragments.append(candidate_description.strip())
    intent_text = "\n".join(fragments) if fragments else "Aucune intention renseignée par l'utilisateur."

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("cv_quality_analysis_attempt", attempt=attempt, chars=len(raw_text))
            response = _openai_client.chat.completions.create(
                model=AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT,
                response_format={"type": "json_object"},
                temperature=ANALYSIS_TEMPERATURE,
                seed=ANALYSIS_SEED,
                messages=[
                    {"role": "system", "content": CV_QUALITY_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Intention du candidat :\n{intent_text}\n\nCV :\n\n{raw_text[:8000]}"
                        ),
                    },
                ],
            )
            data = json.loads(response.choices[0].message.content)
            result = {
                "ats_score": max(0, min(100, int(data["ats_score"]))),
                "synthese": str(data.get("synthese", "")),
                "points_forts": [str(x) for x in data.get("points_forts", [])],
                "points_faibles": [str(x) for x in data.get("points_faibles", [])],
                "suggestions": [str(x) for x in data.get("suggestions", [])],
                "coherence_intention": str(data.get("coherence_intention", "")),
            }
            logger.info("cv_quality_analysis_succeeded", attempt=attempt, ats_score=result["ats_score"])
            return result
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning("cv_quality_analysis_attempt_failed", attempt=attempt, exc_info=True)
            last_error = e
            time.sleep(1)
        except OpenAIError:
            logger.error("cv_quality_analysis_openai_error", attempt=attempt, exc_info=True)
            raise
    logger.error("cv_quality_analysis_all_attempts_failed", attempts=MAX_ATTEMPTS)
    assert last_error is not None  # loop runs MAX_ATTEMPTS times — always set
    raise ValueError("CV quality analysis failed to produce valid JSON") from last_error


def _upsert_cv_analysis(cv_id: str, status: str, **fields) -> None:
    """Upsert the cv_analyses row for a CV — idempotent on Service Bus redelivery.

    completed_at is only set when status is terminal ("done" or "error").

    Args:
        cv_id: UUID string of the analysed CV.
        status: New status value — one of 'processing', 'done', 'error'.
        **fields: Analysis result columns (ats_score, points_forts, ...).

    Raises:
        SQLAlchemyError: On any database error.
    """
    now = datetime.now(timezone.utc)
    values = {"status": status, **fields}
    if status in ("done", "error"):
        values["completed_at"] = now
    try:
        with get_session() as session:
            session.execute(
                pg_insert(CvAnalysis)
                .values(id=uuid.uuid4(), cv_id=cv_id, requested_at=now, **values)
                .on_conflict_do_update(constraint="uq_cv_analyses_cv_id", set_=values)
            )
            session.commit()
    except SQLAlchemyError:
        logger.error("cv_analysis_upsert_failed", cv_id=cv_id, status=status, exc_info=True)
        raise


def _run_quality_analysis(cv_id: str, user_id: str, raw_text: str) -> None:
    """Run the CV quality analysis and persist its result — best-effort, never raises.

    Shared by the normal upload flow (run right after ROME extraction succeeds)
    and by a standalone retry (retry_quality_only message, see main()). A
    failure is logged and written to cv_analyses as status="error"; it never
    propagates to the caller, since this analysis is free and non-blocking
    (see ADR-018 addendum).

    Args:
        cv_id: UUID string of the CV being analysed.
        user_id: Owner of the CV, used to look up profile intent.
        raw_text: Plain text content of the CV.
    """
    try:
        _upsert_cv_analysis(cv_id, "processing")
        experience_level, candidate_description = _get_profile_intent(user_id)
        result = _analyze_cv_quality(raw_text, experience_level, candidate_description)
        _upsert_cv_analysis(cv_id, "done", **result)
        logger.info("cv_quality_analysis_completed", cv_id=cv_id)
    except (OpenAIError, SQLAlchemyError, ValueError, KeyError, TypeError):
        logger.error("cv_quality_analysis_failed", cv_id=cv_id, exc_info=True)
        try:
            _upsert_cv_analysis(cv_id, "error")
        except SQLAlchemyError:
            logger.error("cv_quality_analysis_error_status_write_failed", cv_id=cv_id, exc_info=True)


# ==============================================================================
# Entry point
# ==============================================================================


def main() -> None:
    """Consume one cv-analysis message, extract ROME codes, and dispatch start-matching."""
    configure_telemetry("cv-analysis")
    logger.info("rome_referentiel_loaded", entry_count=len(ROME_REFERENTIEL))

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

            if payload.get("retry_quality_only", False):
                # Manual retry from GET /cv/{id}/analysis status="error" (see
                # POST /cv/{id}/analysis/retry). Only the quality analysis
                # re-runs — ROME codes already exist and matching is untouched.
                logger.info("cv_analysis_retry_started", cv_id=cv_id)
                try:
                    raw_text, user_id = _get_cv_text(cv_id)
                except ValueError:
                    logger.info("cv_analysis_retry_cv_deleted_skipping", cv_id=cv_id)
                    return
                _run_quality_analysis(cv_id, user_id, raw_text)
                logger.info("cv_analysis_retry_completed", cv_id=cv_id)
                return

            logger.info("cv_analysis_started", cv_id=cv_id)

            _set_cv_status(cv_id, "processing")

            try:
                raw_text, user_id = _get_cv_text(cv_id)
            except ValueError:
                # CV was deleted between message enqueue and processing.
                # Complete the message cleanly — no retry, no dead-letter.
                logger.info("cv_analysis_cv_deleted_skipping", cv_id=cv_id)
                return

            try:
                rome_items = _extract_rome_codes(raw_text)
                _merge_rome_codes(user_id, cv_id, rome_items)
            except (OpenAIError, SQLAlchemyError, ValueError):
                # OpenAIError  — API failure or all ROME extraction retries exhausted.
                # SQLAlchemyError — DB failure in _merge_rome_codes.
                # ValueError — _extract_rome_codes found no valid codes after MAX_ATTEMPTS,
                #              or _merge_rome_codes found no matching UserProfile.
                # All three must mark the CV as errored before re-raising so the UI
                # reflects the failure instead of staying stuck in "processing".
                _set_cv_status(cv_id, "error")
                raise

            _set_cv_status(cv_id, "done")

            # CV quality analysis — best-effort, never billed, never blocks the
            # ROME -> matching pipeline. No raise here, unlike the ROME failure
            # handling above, which must halt the agent (see ADR-018 addendum).
            _run_quality_analysis(cv_id, user_id, raw_text)

            rome_codes = [item["code"] for item in rome_items]
            try:
                send_message(
                    START_MATCHING_QUEUE,
                    {
                        "run_date": datetime.now(timezone.utc).date().isoformat(),
                        "rome_codes": rome_codes,
                        "new_offers_count": 0,
                        "embedded_count": 0,
                        "trigger": "cv_analysis",
                    },
                )
                logger.info("cv_analysis_start_matching_sent", cv_id=cv_id, user_id=user_id)
            except ServiceBusError:
                logger.error("cv_analysis_start_matching_failed", cv_id=cv_id, user_id=user_id, exc_info=True)
                raise

            logger.info("cv_analysis_completed", cv_id=cv_id, user_id=user_id, rome_codes=rome_codes)

    except RuntimeError:
        # receive_message returns without yielding when the queue is empty.
        logger.info("cv_analysis_no_message")


if __name__ == "__main__":
    main()
