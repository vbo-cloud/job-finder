"""CV analysis agent — ROME code extraction and CV quality analysis via Azure OpenAI."""

import copy
import json
import os
import re
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import structlog
from alembic.util.exc import CommandError
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from openai import OpenAIError
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import flag_modified

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
OFFER_FETCH_REQUEST_QUEUE = "offer-fetch-request"

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
if not AZURE_OPENAI_ENDPOINT:
    raise ValueError("AZURE_OPENAI_ENDPOINT")

# Default matches the fixed deployment name used across all environments.
# A missing env var is safe — the deployment name is not secret and does not vary.
AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT", "gpt-5-mini")
MAX_ATTEMPTS = 2

# Azure OpenAI deployments known to reject a pinned temperature/seed outright (400 error)
# instead of silently ignoring it — confirmed for gpt-5-mini by a direct API error:
# "'temperature' does not support 0.0 with this model. Only the default (1) value is
# supported." Enrich this set if a future deployment has the same reasoning-model constraint.
MODELS_WITHOUT_TEMPERATURE_SEED = frozenset({"gpt-5-mini"})

ROME_CODE_PATTERN = re.compile(r"^[A-Z]\d{4}$")

_REFERENTIEL_PATH = Path(__file__).parent.parent.parent / "shared" / "rome_referentiel.json"
ROME_REFERENTIEL: dict[str, str] = json.loads(
    _REFERENTIEL_PATH.read_text(encoding="utf-8")
)

logger = structlog.get_logger()

# No I/O and no resolvable identity needed at import — the credential chain is only
# walked on the first token request (the first .chat.completions.create() call below).
# Unlike AZURE_OPENAI_ENDPOINT above, an unusable identity therefore surfaces at call
# time, not at module load — this module still imports cleanly with no Azure login
# available (e.g. under pytest, see conftest.py).
_openai_token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

_openai_client = AzureOpenAI(
    azure_ad_token_provider=_openai_token_provider,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version="2024-02-01",
)


def _sampling_kwargs() -> dict[str, float | int]:
    """Return temperature/seed kwargs for the configured deployment, empty if unsupported.

    See MODELS_WITHOUT_TEMPERATURE_SEED — some Azure OpenAI deployments (e.g. gpt-5-mini) reject
    a pinned temperature/seed with a 400 error rather than silently ignoring it, so the kwargs
    must be omitted from the call entirely for those, not passed with a default value.

    Returns:
        {"temperature": ANALYSIS_TEMPERATURE, "seed": ANALYSIS_SEED}, or {} if
        AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT is in MODELS_WITHOUT_TEMPERATURE_SEED.
    """
    if AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT in MODELS_WITHOUT_TEMPERATURE_SEED:
        return {}
    return {"temperature": ANALYSIS_TEMPERATURE, "seed": ANALYSIS_SEED}


# ==============================================================================
# CV fetch
# ==============================================================================


def _get_cv_text(cv_id: str) -> tuple[str, str, int | None]:
    """Fetch raw CV text, owner user_id, and detected layout column count from the database.

    Args:
        cv_id: UUID of the CV record.

    Returns:
        A tuple of (raw_text, user_id, layout_columns_detected). layout_columns_detected is
        None for CVs uploaded before column detection existed — see CV.layout_columns_detected.

    Raises:
        ValueError: If no CV with the given ID exists.
        SQLAlchemyError: On any database error.
    """
    logger.info("cv_fetch_started", cv_id=cv_id)
    try:
        with get_session() as session:
            row = session.execute(
                select(CV.raw_text, CV.user_id, CV.layout_columns_detected).where(CV.id == cv_id)
            ).one_or_none()
    except SQLAlchemyError:
        logger.error("cv_fetch_failed", cv_id=cv_id, exc_info=True)
        raise
    if row is None:
        raise ValueError(f"CV {cv_id} not found")
    raw_text, user_id, layout_columns_detected = row
    logger.info("cv_fetch_done", cv_id=cv_id, chars=len(raw_text))
    return raw_text, user_id, layout_columns_detected


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


def _mark_rome_analyzed(cv_id: str) -> None:
    """Stamp cvs.rome_analyzed_at after a ROME extraction completes for this CV.

    Compared against UserProfile.description_updated_at by GET /cv/ to decide whether a
    manual reanalysis is worth offering — see
    docs/prompts/prompt-cv-analysis-rome-reanalysis-button.md.

    Args:
        cv_id: UUID of the CV record.

    Raises:
        SQLAlchemyError: On any database error.
    """
    logger.info("cv_rome_analyzed_at_update", cv_id=cv_id)
    try:
        with get_session() as session:
            session.execute(
                update(CV).where(CV.id == cv_id).values(rome_analyzed_at=datetime.now(timezone.utc))
            )
            session.commit()
    except SQLAlchemyError:
        logger.error("cv_rome_analyzed_at_update_failed", cv_id=cv_id, exc_info=True)
        raise


# ==============================================================================
# ROME extraction
# ==============================================================================

# The referential is injected into the system prompt (not the user message) so the same prompt
# text is reused across calls and stays eligible for prompt caching — see date injection below
# for the counter-example (date goes in the user message precisely because it must vary).
_ROME_REFERENTIEL_TEXT = "\n".join(f"{code}: {label}" for code, label in ROME_REFERENTIEL.items())

ROME_EXTRACTION_SYSTEM_PROMPT = (
    "Tu es un expert en classification des métiers français selon le référentiel ROME. "
    "Voici la liste COMPLÈTE des codes ROME valides et leurs libellés :\n\n"
    f"{_ROME_REFERENTIEL_TEXT}\n\n"
    "Analyse le CV fourni (et l'intention de recherche du candidat si elle est transmise) et "
    'retourne UNIQUEMENT un objet JSON valide de la forme {"rome_codes": ["M1805", "M1802", ...]} '
    "contenant entre 1 et 5 codes ROME pertinents, choisis EXCLUSIVEMENT dans la liste ci-dessus "
    "(ne jamais inventer un code absent de cette liste). "
    "RÈGLE — le code doit refléter le métier ou la fonction réellement exercée par LE "
    "CANDIDAT lui-même, jamais le secteur d'activité, les produits ou outils "
    "vendus/utilisés, ou le métier des personnes ou clients mentionnés dans le CV. "
    "Exemple : un commercial qui vend des solutions informatiques reste un métier "
    "commercial (codes de la famille vente/administration des ventes), pas un métier "
    "de développeur ou d'administrateur système, même si le CV contient beaucoup de "
    "vocabulaire technique. "
    "RÈGLE — quand un objectif de poste explicite est identifiable (intitulé de poste "
    "recherché en tête de CV, ex. \"Développeur Web\", ou intention de recherche transmise "
    "séparément), privilégie fortement les codes ROME correspondant à cet objectif. Un "
    "candidat qui a exercé plusieurs métiers clairement distincts au fil de son parcours "
    "(ex. un job alimentaire ou saisonnier sans lien avec sa direction de carrière, en plus "
    "de son métier ou de sa formation principale) ne doit pas voir ces expériences annexes "
    "représentées à égalité avec son objectif réel — ne retourne un code pour une expérience "
    "annexe que si rien d'autre dans le CV ou l'intention transmise n'indique une direction de "
    "carrière plus cohérente. "
    "RÈGLE — ne complète jamais la liste avec un code supplémentaire seulement pour "
    "atteindre un nombre minimal : un CV clairement mono-métier peut n'avoir qu'un "
    "seul code pertinent. "
    "RÈGLE — niveau de qualification : le ou les codes choisis doivent correspondre au diplôme "
    "le plus élevé réellement obtenu et au poste réellement occupé par le candidat, jamais à "
    "une formation entamée puis abandonnée sans diplôme (ex. une seule année de classe "
    "préparatoire non validée ne justifie jamais un code d'ingénieur), ni à un niveau de "
    "responsabilité/encadrement supérieur à celui de l'expérience réellement démontrée dans le "
    "CV (ex. ne retourne pas un code d'architecte, de chef de chantier ou de conducteur de "
    "travaux pour un dessinateur-projeteur ou technicien sans expérience d'encadrement "
    "explicitement décrite). Cette exigence de preuve — une expérience réelle et distincte, pas "
    "une simple proximité de secteur — s'applique UNIQUEMENT à un code qui représenterait une "
    "direction de carrière DIFFÉRENTE de l'objectif principal déjà identifié (voir la RÈGLE — "
    "famille de métiers cible ci-dessous pour le cas contraire). "
    "RÈGLE — famille de métiers cible : une fois la direction de carrière principale établie "
    "(objectif de poste explicite en tête de CV, intention de recherche transmise séparément, "
    "ou métier dominant du parcours), inclure TOUTES les fiches ROME de la liste ci-dessus qui "
    "décrivent cette même direction au même niveau de qualification — même quand le référentiel "
    "la découpe en plusieurs fiches voisines plutôt qu'une seule (ex. un objectif Cloud "
    "Engineer/DevOps peut être couvert par plusieurs fiches administrateur systèmes, technicien "
    "cloud, ingénieur cloud selon le découpage du référentiel : ce sont des variantes du même "
    "objectif, pas des codes 'supplémentaires' à justifier séparément). Ne confonds pas cette "
    "situation avec une expérience annexe hors direction de carrière (voir la RÈGLE sur les "
    "expériences annexes ci-dessus), qui reste soumise à l'exigence de preuve. "
    "Ne retourne rien d'autre que le JSON."
)


def _extract_rome_codes(raw_text: str, candidate_description: str | None = None) -> list[dict[str, str]]:
    """Extract ROME occupation codes from CV text using the configured Azure OpenAI deployment.

    The model identifies candidate codes only — no labels. Each code is
    validated against ROME_REFERENTIEL: codes that fail the regex or are absent
    from the referential are silently rejected (hallucination protection). The
    label is always sourced from the referential, never from GPT output.

    Two invariants, both required after the same CV produced two disjoint code
    sets on consecutive uploads (see docs/prompts/prompt-cv-analysis-rome-code-
    determinism-and-precision.md for the full diagnostic):
    - Determinism: temperature/seed pinned via _sampling_kwargs() (empty for
      deployments in MODELS_WITHOUT_TEMPERATURE_SEED), same as _analyze_cv_quality
      and match_analysis's _analyze_match.
    - Precision: the system prompt requires codes to reflect the candidate's own
      occupation, never the sector/products/tools they work with or the
      occupation of people mentioned in the CV — and no longer pads the result
      to a 3-code floor when the CV is genuinely mono-occupation.

    A third invariant, added when a CV mixing a declared developer objective with
    disjoint food-service/handling/coaching jobs diluted the extraction with a
    code per job actually held: candidate_description (the intention declared on
    the platform, distinct from what the CV text itself says) is passed to the
    model when available, and the system prompt tells it to prioritize the
    declared objective over annex experiences — see
    docs/prompts/prompt-cv-analysis-rome-reanalysis-button.md.

    A fourth invariant, added after a real misclassified CV (dessinateur-projeteur
    BTP scored under computer-science and taxidermist codes) traced back to the
    model producing a ROME code from free recall over ~1911 possible identifiers:
    ROME_EXTRACTION_SYSTEM_PROMPT now embeds the full referential so the model
    selects from a shown list instead of recalling an arbitrary code from memory
    — see docs/prompts/prompt-cv-analysis-referentiel-model-upgrade-column-
    parsing.md for the diagnostic that isolated this as the root cause (not text
    ordering, which was tested and ruled out first). The current date is also
    passed in the user message (not the system prompt, to keep it cache-eligible)
    so the model has a real anchor for chronological-coherence judgments.

    A fifth invariant, added because the qualification-level rule conflated two
    distinct situations: the system prompt now distinguishes sibling ROME codes
    that describe the same target occupation at the same qualification level
    — which the referential happens to split across several neighboring
    fiches (included together without separate proof) — from codes
    representing a genuinely different career direction (still requiring
    distinct proof). This was found while investigating the same real CV
    producing disjoint code sets (89/131/214 matches) across three
    consecutive uploads despite determinism pinning — partly explained by
    MODELS_WITHOUT_TEMPERATURE_SEED silently neutralizing the first invariant
    for gpt-5-mini, which rejects temperature/seed outright, but this
    invariant does not itself eliminate that residual sampling noise, only
    the flawed judgment the model had to make on every call regardless of
    sampling — see docs/prompts/prompt-cv-analysis-rome-code-family-coverage.md
    for the full diagnostic.

    Retries up to MAX_ATTEMPTS times on JSON parse errors or empty results.
    OpenAI API errors are not retried — they are fatal.

    Args:
        raw_text: Plain text content of the CV.
        candidate_description: The candidate's declared search intent
            (UserProfile.candidate_description), if any. Blank or whitespace-only
            values are treated the same as None.

    Returns:
        A list of 1–5 dicts, each with "code" and "label" keys,
        e.g. [{"code": "M1805", "label": "Études et développement informatique"}].

    Raises:
        OpenAIError: If the API call fails.
        ValueError: If all retry attempts fail to produce valid ROME codes.
    """
    # The 8000-char cap covers only raw_text — candidate_description is appended
    # uncapped below. Negligible in practice (a profile description is at most a
    # few hundred chars, far under the configured deployment's context window).
    today_str = date.today().isoformat()
    user_content = f"Date du jour : {today_str}\n\nCV :\n\n{raw_text[:8000]}"
    if candidate_description and candidate_description.strip():
        user_content += (
            f"\n\nIntention de recherche déclarée par le candidat : "
            f"{candidate_description.strip()}"
        )

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("rome_extraction_attempt", attempt=attempt, chars=len(raw_text))
            response = _openai_client.chat.completions.create(
                model=AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT,
                response_format={"type": "json_object"},
                **_sampling_kwargs(),
                messages=[
                    {"role": "system", "content": ROME_EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": user_content,
                    },
                ],
            )
            # Logged before json.loads(...): a parse failure below still consumed billable
            # tokens on this attempt, so this must stay ahead of the parse or a retry's cost
            # silently drops out of the token accounting.
            logger.info(
                "openai_call_completed",
                agent="cv-analysis",
                operation="rome_extraction",
                model=AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT,
                attempt=attempt,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
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


def _merge_rome_codes(user_id: str, cv_id: str, rome_items: list[dict[str, str]]) -> list[str]:
    """Reconcile this cv_id's ROME codes into the user profile dict with row-level locking.

    Each item in rome_items must have "code" and "label" keys. The cv_id is
    appended to the code's cv_ids list if not already present. The label is
    always updated to the latest value from the ROME referential. Codes
    previously associated with this cv_id that this extraction no longer
    produces are also removed (see the reconciliation note below) — this is
    not purely additive.

    Uses SELECT ... FOR UPDATE to prevent concurrent analyses from overwriting
    each other's data.

    Reconciliation, not pure addition: documented twice before (JOURNAL, PR #213,
    the shallow-copy fix) and only now actually fixed — a re-extraction that
    drops a code for this cv_id (e.g. the intent-aware prioritization above, or
    a manual retry_rome_only) must remove that code's reference to this cv_id,
    otherwise the profile keeps an obsolete code forever, additive-only merges
    never being able to retract anything. Mirrors the cleanup idiom already used
    by routers/cv.py::_remove_cv_from_rome_codes at CV deletion: drop this cv_id
    from a code's cv_ids, and drop the code entirely once its cv_ids is empty.

    Important: `profile.rome_codes` is a JSONB column mutated in place. A plain
    shallow copy (`dict(profile.rome_codes)`) is not enough — the nested
    per-code dicts stay shared with the value SQLAlchemy already tracks, so
    mutating them also mutates the tracked value, which defeats change
    detection at flush and silently drops the write for any code that already
    existed. Hence `copy.deepcopy` (a genuinely independent copy) and
    `flag_modified` (explicit marking, robust even against a future regression
    on this point).

    Args:
        user_id: The user whose profile to update.
        cv_id: UUID string of the CV being analysed.
        rome_items: List of dicts with "code" and "label" keys.

    Returns:
        ROME codes from rome_items that were not already keys of this profile's rome_codes
        before this call — i.e. genuinely new to this profile, regardless of whether other
        profiles already use them. Used by main() to trigger an immediate, targeted
        offer_fetching pass for exactly these codes instead of waiting for the next scheduled
        refresh — see docs/prompts/prompt-offer-fetching-event-driven-and-new-code-fetch.md.

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

            current: dict = copy.deepcopy(profile.rome_codes or {})
            fresh_codes = {item["code"] for item in rome_items}
            new_codes: list[str] = []

            # Reconcile first: drop this cv_id from any code this extraction no
            # longer produces, purging the code entirely once its cv_ids is empty.
            for code in list(current.keys()):
                if code not in fresh_codes:
                    current[code]["cv_ids"] = [cid for cid in current[code]["cv_ids"] if cid != cv_id]
                    if not current[code]["cv_ids"]:
                        del current[code]

            for item in rome_items:
                code = item["code"]
                label = item["label"]
                if code not in current:
                    current[code] = {"cv_ids": [], "label": label}
                    new_codes.append(code)
                if cv_id not in current[code]["cv_ids"]:
                    current[code]["cv_ids"].append(cv_id)
                current[code]["label"] = label

            profile.rome_codes = current
            # Defensive, not strictly required given the deepcopy above (see docstring):
            # guards against a future regression that reintroduces shared nested references.
            flag_modified(profile, "rome_codes")
            profile.updated_at = datetime.now(timezone.utc)
            session.commit()
    except SQLAlchemyError:
        logger.error("rome_merge_failed", user_id=user_id, cv_id=cv_id, exc_info=True)
        raise
    logger.info("rome_merge_done", user_id=user_id, cv_id=cv_id, new_codes=new_codes)
    return new_codes


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
   fin) ? Y a-t-il des trous ou des chevauchements non expliqués entre deux expériences ? La date du
   jour est fournie dans le message utilisateur (ligne "Date du jour") — sers-t'en comme seule
   référence pour juger si une date du CV est cohérente (passée, actuelle, ou anormalement future),
   ne te fie jamais à une estimation interne de "aujourd'hui".
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

RÈGLE — mise en page à colonnes : si le message utilisateur indique une mise en page à 2 colonnes ou
plus, le texte du CV qui te parvient a déjà été remis dans un ordre de lecture cohérent — ne déduis
JAMAIS de désorganisation du contenu, de tâches mal rattachées ou de sections fusionnées à partir de
cette seule information de mise en page (le texte que tu lis est propre). En revanche, mentionne
explicitement dans points_faibles ou suggestions le risque que cette mise en page à colonnes soit mal
interprétée par certains logiciels ATS automatisés lors d'une candidature en ligne, et suggère une
version à une seule colonne pour ce cas d'usage — c'est un vrai conseil de mise en forme, pas une
critique du contenu.

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
    raw_text: str,
    experience_level: str | None,
    candidate_description: str | None,
    columns_detected: int | None,
) -> dict:
    """Analyze CV structure, phrasing, ATS-friendliness, and coherence with declared intent.

    Retries up to MAX_ATTEMPTS times on JSON parse errors — same policy as
    _extract_rome_codes. OpenAI API errors are not retried.

    columns_detected (CV.layout_columns_detected, threaded through _get_cv_text ->
    _run_quality_analysis) is required, not optional with a None default: a CV whose PDF had a
    two-column layout must always surface the ATS-risk note below, and a silently-defaulted None
    here would mask a break anywhere upstream in that threading instead of surfacing it. See the
    RÈGLE — mise en page à colonnes block in CV_QUALITY_SYSTEM_PROMPT — this is the mechanism
    that lets the model warn about the ATS risk of a columnar layout without inventing
    content-organization defects from what _extract_page_text has already reordered into clean
    text (see docs/prompts/prompt-cv-analysis-referentiel-model-upgrade-column-parsing.md).

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

    today_str = date.today().isoformat()
    layout_note = (
        f"Mise en page détectée : {columns_detected} colonnes.\n\n"
        if columns_detected and columns_detected >= 2
        else ""
    )

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("cv_quality_analysis_attempt", attempt=attempt, chars=len(raw_text))
            response = _openai_client.chat.completions.create(
                model=AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT,
                response_format={"type": "json_object"},
                **_sampling_kwargs(),
                messages=[
                    {"role": "system", "content": CV_QUALITY_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Date du jour : {today_str}\n\n{layout_note}"
                            f"Intention du candidat :\n{intent_text}\n\nCV :\n\n{raw_text[:8000]}"
                        ),
                    },
                ],
            )
            # Logged before json.loads(...): a parse failure below still consumed billable
            # tokens on this attempt, so this must stay ahead of the parse or a retry's cost
            # silently drops out of the token accounting.
            logger.info(
                "openai_call_completed",
                agent="cv-analysis",
                operation="cv_quality_analysis",
                model=AZURE_OPENAI_CV_ANALYSIS_DEPLOYMENT,
                attempt=attempt,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
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
    logger.info("cv_analysis_upsert_started", cv_id=cv_id, status=status)
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


def _run_quality_analysis(
    cv_id: str, user_id: str, raw_text: str, columns_detected: int | None
) -> None:
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
        columns_detected: CV.layout_columns_detected for this cv_id, forwarded to
            _analyze_cv_quality — see that function's docstring for why this is required.
    """
    try:
        _upsert_cv_analysis(cv_id, "processing")
        experience_level, candidate_description = _get_profile_intent(user_id)
        result = _analyze_cv_quality(raw_text, experience_level, candidate_description, columns_detected)
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


def _handle_retry_quality_only(cv_id: str) -> None:
    """Handle a retry_quality_only cv-analysis message: re-run quality analysis only.

    Manual retry from GET /cv/{id}/analysis status="error" (see
    POST /cv/{id}/analysis/retry). Only the quality analysis re-runs — ROME
    codes already exist on the profile and matching is untouched.

    Args:
        cv_id: UUID string of the CV to retry.
    """
    logger.info("cv_analysis_retry_started", cv_id=cv_id)
    try:
        raw_text, user_id, columns_detected = _get_cv_text(cv_id)
    except ValueError:
        logger.info("cv_analysis_retry_cv_deleted_skipping", cv_id=cv_id)
        return
    _run_quality_analysis(cv_id, user_id, raw_text, columns_detected)
    logger.info("cv_analysis_retry_completed", cv_id=cv_id)


def _handle_retry_rome_only(cv_id: str) -> None:
    """Handle a retry_rome_only cv-analysis message: re-run ROME extraction only.

    Manual retry from POST /cv/{id}/rome/retry, offered when the profile's
    candidate_description has changed more recently than this CV's last ROME
    extraction. Only ROME extraction re-runs — CV quality analysis is untouched.
    _merge_rome_codes reconciles rather than only adds, so codes no longer
    produced by this fresh extraction are removed from the profile, not just
    supplemented. See docs/prompts/prompt-cv-analysis-rome-reanalysis-button.md.

    Unlike _handle_new_cv_analysis, a ROME extraction failure here does not flip
    the CV to status="error": the CV already completed its initial analysis
    successfully, and downgrading it to "error" over a reanalysis hiccup would
    hide the working CV and its existing matches behind an error state instead
    of simply leaving the manual retry button available for another attempt.

    Args:
        cv_id: UUID string of the CV to retry.

    Raises:
        OpenAIError: If the ROME extraction API call fails or exhausts its retries.
        SQLAlchemyError: If merging ROME codes into the profile fails.
        ValueError: If ROME extraction finds no valid codes.
        ServiceBusError: If the start-matching dispatch fails (see
            _dispatch_start_matching — the offer-fetch-request dispatch never
            raises).
    """
    logger.info("cv_analysis_rome_retry_started", cv_id=cv_id)
    try:
        raw_text, user_id, _ = _get_cv_text(cv_id)
    except ValueError:
        logger.info("cv_analysis_rome_retry_cv_deleted_skipping", cv_id=cv_id)
        return

    try:
        _, candidate_description = _get_profile_intent(user_id)
        rome_items = _extract_rome_codes(raw_text, candidate_description)
        new_rome_codes = _merge_rome_codes(user_id, cv_id, rome_items)
        _mark_rome_analyzed(cv_id)
    except (OpenAIError, SQLAlchemyError, ValueError):
        logger.error("cv_analysis_rome_retry_failed", cv_id=cv_id, exc_info=True)
        raise

    rome_codes = [item["code"] for item in rome_items]
    _dispatch_start_matching(cv_id, user_id, rome_codes, trigger="cv_analysis_rome_retry")
    _dispatch_offer_fetch_request(cv_id, user_id, new_rome_codes)

    logger.info("cv_analysis_rome_retry_completed", cv_id=cv_id, rome_codes=rome_codes)


def _dispatch_start_matching(
    cv_id: str, user_id: str, rome_codes: list[str], trigger: str = "cv_analysis"
) -> None:
    """Send a start-matching message so the matching agent re-scores existing offers.

    Args:
        cv_id: UUID string of the analysed CV.
        user_id: Owner of the CV, for log correlation only.
        rome_codes: ROME codes extracted for this CV.
        trigger: Value stamped on the message's "trigger" field — distinguishes
            the normal upload path ("cv_analysis") from a manual ROME-only retry
            ("cv_analysis_rome_retry") in downstream telemetry.

    Raises:
        ServiceBusError: If the send fails — unlike the offer-fetch-request dispatch
            below, this one must halt the agent so the message redelivers.
    """
    try:
        send_message(
            START_MATCHING_QUEUE,
            {
                "run_date": datetime.now(timezone.utc).date().isoformat(),
                "rome_codes": rome_codes,
                "new_offers_count": 0,
                "embedded_count": 0,
                "trigger": trigger,
            },
        )
        logger.info("cv_analysis_start_matching_sent", cv_id=cv_id, user_id=user_id)
    except ServiceBusError:
        logger.error("cv_analysis_start_matching_failed", cv_id=cv_id, user_id=user_id, exc_info=True)
        raise


def _dispatch_offer_fetch_request(cv_id: str, user_id: str, new_rome_codes: list[str]) -> None:
    """Best-effort dispatch of a targeted offer-fetch-request for newly-merged ROME codes.

    No-op if new_rome_codes is empty. Deliberately never re-raised, unlike
    _dispatch_start_matching: on a cv-analysis message redelivery,
    _merge_rome_codes would find these codes already merged by the first
    successful attempt and return new_rome_codes=[] — raising here would
    trigger a retry that could never re-send this exact message.
    offer_fetching's next scheduled full refresh covers these codes anyway,
    regardless of this send's outcome.

    Args:
        cv_id: UUID string of the analysed CV.
        user_id: Owner of the CV, for log correlation only.
        new_rome_codes: ROME codes genuinely new to this profile, as returned
            by _merge_rome_codes.
    """
    if not new_rome_codes:
        return
    try:
        send_message(
            OFFER_FETCH_REQUEST_QUEUE,
            {"trigger": "cv_analysis", "rome_codes": new_rome_codes},
        )
        logger.info(
            "cv_analysis_offer_fetch_request_sent",
            cv_id=cv_id,
            user_id=user_id,
            rome_codes=new_rome_codes,
        )
    except ServiceBusError:
        logger.error(
            "cv_analysis_offer_fetch_request_failed",
            cv_id=cv_id,
            user_id=user_id,
            rome_codes=new_rome_codes,
            exc_info=True,
        )


def _handle_new_cv_analysis(cv_id: str) -> None:
    """Handle a new cv-analysis message: extract ROME codes, run quality analysis, dispatch.

    Args:
        cv_id: UUID string of the CV to analyse.

    Raises:
        OpenAIError: If the ROME extraction API call fails or exhausts its retries.
        SQLAlchemyError: If merging ROME codes into the profile fails.
        ValueError: If ROME extraction finds no valid codes, or no matching
            UserProfile exists for this CV's owner.
        ServiceBusError: If the start-matching dispatch fails (see
            _dispatch_start_matching — the offer-fetch-request dispatch never
            raises).
    """
    logger.info("cv_analysis_started", cv_id=cv_id)

    _set_cv_status(cv_id, "processing")

    try:
        raw_text, user_id, columns_detected = _get_cv_text(cv_id)
    except ValueError:
        # CV was deleted between message enqueue and processing.
        # Complete the message cleanly — no retry, no dead-letter.
        logger.info("cv_analysis_cv_deleted_skipping", cv_id=cv_id)
        return

    try:
        _, candidate_description = _get_profile_intent(user_id)
        rome_items = _extract_rome_codes(raw_text, candidate_description)
        new_rome_codes = _merge_rome_codes(user_id, cv_id, rome_items)
        _mark_rome_analyzed(cv_id)
    except (OpenAIError, SQLAlchemyError, ValueError):
        # All three must mark the CV as errored before re-raising so the UI
        # reflects the failure instead of staying stuck in "processing".
        _set_cv_status(cv_id, "error")
        raise

    _set_cv_status(cv_id, "done")

    # CV quality analysis — best-effort, never billed, never blocks the
    # ROME -> matching pipeline. No raise here, unlike the ROME failure
    # handling above, which must halt the agent (see ADR-018 addendum).
    _run_quality_analysis(cv_id, user_id, raw_text, columns_detected)

    rome_codes = [item["code"] for item in rome_items]
    _dispatch_start_matching(cv_id, user_id, rome_codes)
    _dispatch_offer_fetch_request(cv_id, user_id, new_rome_codes)

    logger.info("cv_analysis_completed", cv_id=cv_id, user_id=user_id, rome_codes=rome_codes)


def main() -> None:
    """Consume one cv-analysis message and route it to the matching handler.

    Three mutually exclusive branches, keyed on flags in the message payload:
    retry_quality_only (re-run CV quality analysis only), retry_rome_only
    (re-run ROME extraction only), or — the default — a full new-CV analysis
    (ROME extraction, quality analysis, and dispatch of start-matching /
    offer-fetch-request).
    """
    configure_telemetry("cv-analysis")
    logger.info("rome_referentiel_loaded", entry_count=len(ROME_REFERENTIEL))

    try:
        run_migrations()
    except (SQLAlchemyError, CommandError):  # matches run_migrations()'s documented Raises
        logger.error("migrations_failed", exc_info=True)
        raise

    # receive_message is a @contextmanager that yields the decoded payload dict
    # and handles complete/abandon on exit. RuntimeError means no messages available.
    try:
        with receive_message(CV_ANALYSIS_QUEUE) as payload:
            cv_id = payload["cv_id"]
            if payload.get("retry_quality_only", False):
                _handle_retry_quality_only(cv_id)
                return
            if payload.get("retry_rome_only", False):
                _handle_retry_rome_only(cv_id)
                return
            _handle_new_cv_analysis(cv_id)
    except RuntimeError:
        # receive_message returns without yielding when the queue is empty.
        logger.info("cv_analysis_no_message")


if __name__ == "__main__":
    main()
