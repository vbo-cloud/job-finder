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
from shared.config import ANALYSIS_SEED, ANALYSIS_TEMPERATURE
from shared.db import get_session, run_migrations
from shared.models import CV, Match, MatchAnalysis, Offer, UserProfile
from shared.telemetry import configure_telemetry

# ==============================================================================
# Constants
# ==============================================================================

MATCH_ANALYSIS_QUEUE = "match-analysis"
MAX_ATTEMPTS = 2
CV_TEXT_MAX_CHARS = 8000
# Also gates key-skills extraction (KEY_SKILLS_INSTRUCTIONS_EXTRACT): a skill named only
# beyond this many characters into the description is invisible to the model and can never
# be extracted — not just a synthesis-quality tradeoff like it was before key_skills existed.
OFFER_TEXT_MAX_CHARS = 4000
MAX_KEY_SKILLS = 10

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

MATCH_ANALYSIS_SYSTEM_PROMPT = """\
Tu es un coach carrière expert du marché de l'emploi français. Tu analyses la
correspondance entre un CV et une offre d'emploi, et tu retournes UNIQUEMENT un
objet JSON valide, structuré exactement comme décrit ci-dessous.

RÈGLES ABSOLUES — tout doit être ancré dans les textes fournis :
- N'invente aucune information sur l'entreprise qui ne figure pas explicitement
  dans le texte de l'offre fourni. Si l'offre ne dit rien sur l'entreprise
  au-delà de son nom, mets "company_summary": null plutôt que de deviner ou de
  compléter avec des connaissances générales.
- Même exigence pour les lacunes : un "constat" de "points_amelioration" qui
  affirme l'absence d'une compétence (ex. "manque de compétences Linux") n'est
  permis que si cette compétence est explicitement demandée par l'offre
  (description ou compétences demandées) ET absente du texte du CV fourni.
  Ne déduis jamais une lacune d'une supposition générale sur le métier.

LE SCORE — ce que tu sais et ce que tu ne sais pas :
Le score de correspondance fourni en entrée est une similarité sémantique
globale entre le CV et l'offre, calculée en amont — tu ne le recalcules pas et
tu n'en connais pas la décomposition. Ne prétends donc jamais le décomposer en
pourcentages ou en poids par critère ("57 % dont X % de compétences et Y %
d'expérience" est interdit). Dans "score_explanation", décris qualitativement,
à partir des textes du CV et de l'offre, ce qui tire vraisemblablement le score
vers le haut et ce qui le tire vers le bas — en restant cohérent avec le niveau
du score : un score bas s'explique par des éléments dominants allant dans le
sens "bas", jamais par un mélange contradictoire de signaux positifs et
négatifs mis sur le même plan dans la même phrase.
❌ Interdit : "Le score de 57 % se décompose ainsi : 30 % de compétences
   techniques et 27 % d'expérience manquante."
✅ Attendu : "Le score reflète un bon alignement sur les compétences citées
   (Docker, Terraform, CI/CD), atténué par un écart de séniorité par rapport
   à ce que recherche l'offre."

NON-REDONDANCE ENTRE CHAMPS :
Chaque champ doit apporter une information distincte des autres. N'utilise pas
deux fois le même fait marquant (par exemple l'écart d'expérience) dans
plusieurs champs sous des formulations différentes. Si un fait est le point
central de l'analyse, développe-le une seule fois — dans "synthese",
"score_explanation" OU "points_amelioration", selon le champ le plus
approprié — et fais en sorte que les autres champs apportent un angle
différent (compétences spécifiques, contexte de l'offre, alignement avec
l'intention du candidat).

POINTS FORTS ANCRÉS DANS L'OFFRE :
Chaque élément de "points_forts" doit pouvoir être relié explicitement à un
besoin exprimé dans la description de l'offre ou ses compétences demandées.
Les formulations généralistes qui ne référencent aucun élément précis de
l'offre ("compétences en développement et programmation", "bon relationnel")
sont interdites. Si le CV ne contient aucun point fort clairement rattachable
à l'offre au-delà des compétences clés déjà identifiées comme présentes dans
le CV (voir "key_skills"), rends une liste plus courte plutôt que de la
remplir artificiellement.

SUGGESTIONS PERSONNALISÉES :
Avant d'écrire chaque "suggestion_concrete", identifie un élément concret et
vérifiable dans l'intention du candidat (un projet nommé, une certification,
une technologie mentionnée) — ou, si l'intention est vide ("Aucune intention
renseignée par l'utilisateur."), dans le texte du CV lui-même. La suggestion
doit citer explicitement cet élément. Si aucun élément concret n'est trouvable
ni dans l'intention ni dans le CV, formule la suggestion autour d'un point
précis de l'offre (description ou compétences demandées) — jamais un conseil
de carrière générique interchangeable ("suivre une formation", "travailler sur
des projets", "rechercher des stages ou missions temporaires").
Exemple (intention du candidat en entrée : "Reconversion Unity vers
Cloud/Azure, certification AZ-104 obtenue, projet Terraform personnel en
cours") :
❌ Interdit (générique, ignore l'intention) : "Suivre une formation ou
   travailler sur des projets utilisant ces technologies pour développer vos
   compétences."
✅ Attendu (cite l'élément trouvé dans l'intention) : "Mettez en avant la
   certification AZ-104 et le projet Terraform personnel comme preuve de
   montée en compétence rapide sur un stack cloud — un argument direct face à
   l'écart d'expérience, à présenter en entretien comme un cas concret plutôt
   que comme une lacune."

QUESTIONS D'ENTRETIEN DÉRIVÉES DE CETTE ANALYSE :
Au moins une question de "questions_entretien_potentielles" doit découler
directement d'un "constat" présent dans "points_amelioration" de cette même
analyse — reformule le gap identifié en question d'entretien plausible. Pas de
questions génériques de bibliothèque qui seraient valables pour n'importe quel
candidat du métier.

@@KEY_SKILLS_INSTRUCTIONS@@

Format de sortie JSON :
{
  "verdict": string,
  "synthese": string,               // ne commence JAMAIS par "Cette offre est
                                    // pertinente pour vous car". Varie
                                    // l'ouverture selon le point le plus
                                    // marquant (score, compétence clé, ou
                                    // écart bloquant). Exemples de styles :
                                    //   "Profil solide sur les compétences
                                    //    cœur — un point à travailler avant
                                    //    de postuler."
                                    //   "Match élevé (87%) : la mission
                                    //    colle à votre profil sur presque
                                    //    tous les points."
                                    //   "Écart notable sur [compétence],
                                    //    mais des atouts réels ailleurs."
  "key_skills": [{"name": string, "matched": bool}, ...],
  "company_summary": string|null,
  "mission_summary": string,
  "why_good_fit_for_user": string,
  "why_good_candidate": string,
  "score_explanation": string,
  "points_forts": [string, ...],
  "points_amelioration": [
    {"constat": string, "suggestion_concrete": string}
  ],
  "questions_entretien_potentielles": [string, ...]
}

Ton : coach bienveillant et constructif, jamais un audit froid.

Ne retourne rien d'autre que le JSON.
"""

KEY_SKILLS_INSTRUCTIONS_EXTRACT = """\
COMPÉTENCES CLÉS DE L'OFFRE (extraction) :
Identifie, à partir du titre et de la description de l'offre UNIQUEMENT (aucune
liste de compétences n'est fournie séparément), les technologies et
compétences techniques les plus essentielles réellement demandées (langages,
frameworks, outils, plateformes cloud, méthodologies techniques — jamais de
soft skills génériques comme "autonomie" ou "esprit d'équipe"). Retourne au
maximum 10 compétences, SANS plancher artificiel : si l'offre ne présente
clairement que 3 technologies essentielles, n'en retourne que 3. Pour chacune,
indique "matched": true si elle apparaît explicitement dans le CV fourni,
"matched": false sinon."""

KEY_SKILLS_INSTRUCTIONS_MATCH_ONLY = """\
COMPÉTENCES CLÉS DE L'OFFRE (liste déjà figée) :
La liste des compétences clés de cette offre a déjà été établie et est fournie
dans le message utilisateur — NE LA MODIFIE PAS : n'ajoute, ne retire, ne
reformule AUCUN nom. Pour chaque nom EXACT de cette liste, indique
"matched": true s'il apparaît explicitement dans le CV fourni, "matched": false
sinon. Retourne exactement les mêmes noms, dans le même ordre."""


def _build_system_prompt(cached_key_skills: list[str] | None) -> str:
    """Build the match-analysis system prompt for the current cache state.

    Args:
        cached_key_skills: Offer.key_skills value — None when the offer's key
            skills have never been extracted (extraction branch), a (possibly
            empty) list when already cached (match-only branch).

    Returns:
        The full system prompt, with the key-skills section swapped in.
    """
    instructions = (
        KEY_SKILLS_INSTRUCTIONS_EXTRACT
        if cached_key_skills is None
        else KEY_SKILLS_INSTRUCTIONS_MATCH_ONLY
    )
    return MATCH_ANALYSIS_SYSTEM_PROMPT.replace("@@KEY_SKILLS_INSTRUCTIONS@@", instructions)


# ==============================================================================
# Match context fetch
# ==============================================================================


def _get_match_context(match_id: str) -> dict:
    """Fetch the CV text, offer fields, and profile intent for a match in one query.

    Args:
        match_id: UUID of the match to analyse.

    Returns:
        dict with keys cv_text, offer_id, offer_title, offer_company,
        offer_description, offer_key_skills, experience_level,
        candidate_description, match_score.

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
                    Offer.id,
                    Offer.title,
                    Offer.company,
                    Offer.description,
                    Offer.key_skills,
                    Match.score,
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
        "offer_id": row.id,
        "offer_title": row.title,
        "offer_company": row.company,
        "offer_description": row.description,
        "offer_key_skills": list(row.key_skills) if row.key_skills is not None else None,
        "match_score": row.score,
        "experience_level": row.experience_level,
        "candidate_description": row.candidate_description,
    }


# ==============================================================================
# Pair analysis
# ==============================================================================


def _parse_key_skills(data: dict, cached_key_skills: list[str] | None) -> tuple[list[str], list[str] | None]:
    """Coerce the raw model key_skills payload into (matched_skills, new_offer_key_skills).

    Two branches, matching the two prompt variants built by _build_system_prompt:
    - Extraction (cached_key_skills is None): the model invented the names, so
      clamp to MAX_KEY_SKILLS and treat the parsed names as the offer's new
      cached key_skills, written once by the caller.
    - Match-only (cached_key_skills already a list): the model must reuse the
      exact given names — any name outside that list is a hallucination and is
      dropped defensively rather than trusted; new_offer_key_skills is None
      since the cache is not touched on this branch.

    Args:
        data: Parsed JSON object returned by the model.
        cached_key_skills: Offer.key_skills value passed into this analysis.

    Returns:
        Tuple of (matched_skills for MatchAnalysis, new key_skills for Offer or
        None if the offer's cache must not be written).
    """
    parsed: list[dict] = []
    seen: set[str] = set()
    for item in data.get("key_skills") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name in seen:
            continue
        seen.add(name)
        parsed.append({"name": name, "matched": bool(item.get("matched"))})

    if cached_key_skills is None:
        parsed = parsed[:MAX_KEY_SKILLS]
        new_offer_key_skills = [item["name"] for item in parsed]
        matched_skills = [item["name"] for item in parsed if item["matched"]]
        return matched_skills, new_offer_key_skills

    cached_set = set(cached_key_skills)
    dropped = [item["name"] for item in parsed if item["name"] not in cached_set]
    if dropped:
        logger.warning("match_analysis_key_skills_hallucinated", dropped=dropped)
    matched_skills = [item["name"] for item in parsed if item["matched"] and item["name"] in cached_set]
    return matched_skills, None


def _parse_analysis_payload(data: dict, cached_key_skills: list[str] | None) -> tuple[dict, list[str] | None]:
    """Coerce the raw model JSON into MatchAnalysis column values.

    Defensive coercion, same policy as the existing fields: text fields are cast
    to str (None preserved — the columns are nullable and company_summary is
    legitimately null when the offer says nothing about the company), list
    fields to lists of str. A points_amelioration item without a constat is
    silently dropped rather than failing the whole analysis; a missing
    suggestion_concrete becomes None, matching what the API already accepts
    for legacy pre-020 rows.

    Args:
        data: Parsed JSON object returned by the model.
        cached_key_skills: Offer.key_skills value passed into this analysis —
            see _parse_key_skills.

    Returns:
        Tuple of (dict whose keys map 1:1 to MatchAnalysis result columns,
        new key_skills to persist onto Offer or None to leave it untouched).
    """
    def _text(key: str) -> str | None:
        value = data.get(key)
        return str(value) if value is not None else None

    points_amelioration = []
    for item in data.get("points_amelioration") or []:
        if not isinstance(item, dict) or "constat" not in item:
            continue
        suggestion = item.get("suggestion_concrete")
        points_amelioration.append(
            {
                "constat": str(item["constat"]),
                "suggestion_concrete": str(suggestion) if suggestion is not None else None,
            }
        )
    matched_skills, new_offer_key_skills = _parse_key_skills(data, cached_key_skills)
    analysis_fields = {
        "matched_skills": matched_skills,
        "points_forts": [str(x) for x in data.get("points_forts") or []],
        "points_amelioration": points_amelioration,
        "synthese": _text("synthese"),
        "verdict": _text("verdict"),
        "company_summary": _text("company_summary"),
        "mission_summary": _text("mission_summary"),
        "why_good_fit_for_user": _text("why_good_fit_for_user"),
        "why_good_candidate": _text("why_good_candidate"),
        "score_explanation": _text("score_explanation"),
        "questions_entretien_potentielles": [
            str(x) for x in data.get("questions_entretien_potentielles") or []
        ],
    }
    return analysis_fields, new_offer_key_skills


def _build_intent_text(context: dict) -> str:
    """Render the candidate's profile intent as free text for the prompt.

    Same fragments as _build_intent_text in routers/profile.py — duplicated on
    purpose: agents must not depend on agents/webapp.

    Args:
        context: Match context dict as returned by _get_match_context.

    Returns:
        Intent text, or the "no intent" fallback sentence when both the
        experience level and candidate description are empty.
    """
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
    return "\n".join(fragments) if fragments else "Aucune intention renseignée par l'utilisateur."


def _build_user_content(context: dict, cached_key_skills: list[str] | None) -> str:
    """Render the match-analysis user message for the current cache state.

    Args:
        context: Match context dict as returned by _get_match_context.
        cached_key_skills: Offer.key_skills value — appended as a fixed list
            to reuse verbatim when not None (match-only prompt variant).

    Returns:
        The full user message content.
    """
    user_content = (
        f"Intention du candidat :\n{_build_intent_text(context)}\n\n"
        f"Score de correspondance déjà calculé : {context['match_score']:.0%}\n\n"
        f"CV :\n{context['cv_text'][:CV_TEXT_MAX_CHARS]}\n\n"
        f"Offre : {context['offer_title']} — {context['offer_company']}\n"
        f"Description :\n{context['offer_description'][:OFFER_TEXT_MAX_CHARS]}"
    )
    if cached_key_skills is not None:
        user_content += (
            f"\n\nCompétences clés déjà établies pour cette offre (noms exacts, ne "
            f"pas les modifier) : {', '.join(cached_key_skills)}"
        )
    return user_content


def _analyze_match(context: dict) -> tuple[dict, list[str] | None]:
    """Analyze one CV<->offer pair with GPT-4o-mini.

    Retries up to MAX_ATTEMPTS times on JSON parse errors — same policy as the
    cv_analysis agent. OpenAI API errors are not retried.

    Args:
        context: Match context dict as returned by _get_match_context.

    Returns:
        Tuple of (dict whose keys map 1:1 to MatchAnalysis result columns, new
        key_skills to persist onto Offer or None) — see _parse_analysis_payload.

    Raises:
        OpenAIError: If the API call fails.
        ValueError: If all retry attempts fail to produce valid JSON.
    """
    cached_key_skills = context.get("offer_key_skills")
    system_prompt = _build_system_prompt(cached_key_skills)
    user_content = _build_user_content(context, cached_key_skills)

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("match_analysis_attempt", attempt=attempt)
            response = _openai_client.chat.completions.create(
                model=AZURE_OPENAI_MATCH_ANALYSIS_DEPLOYMENT,
                response_format={"type": "json_object"},
                temperature=ANALYSIS_TEMPERATURE,
                seed=ANALYSIS_SEED,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            data = json.loads(response.choices[0].message.content)
            analysis_fields, new_offer_key_skills = _parse_analysis_payload(data, cached_key_skills)
            logger.info(
                "match_analysis_succeeded",
                attempt=attempt,
                matched_skills_count=len(analysis_fields["matched_skills"]),
            )
            return analysis_fields, new_offer_key_skills
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


def _persist_offer_key_skills(offer_id: str, key_skills: list[str]) -> None:
    """Cache a freshly extracted key_skills list onto its offer, once.

    The `Offer.key_skills.is_(None)` guard makes this write-once safe even if
    two analyses for the same offer race each other in the extraction branch
    (concurrent Container App Job replicas) — only the first write wins, the
    second becomes a no-op. Any later re-extraction goes through the
    ft_updated_at-based reset in offer_fetching, never through this function.

    Args:
        offer_id: UUID of the offer to cache key skills onto.
        key_skills: Extracted key skills (already clamped to MAX_KEY_SKILLS).

    Raises:
        SQLAlchemyError: On any database error.
    """
    logger.info("offer_key_skills_persist_started", offer_id=offer_id, count=len(key_skills))
    try:
        with get_session() as session:
            session.execute(
                update(Offer)
                .where(Offer.id == offer_id, Offer.key_skills.is_(None))
                .values(key_skills=key_skills)
            )
            session.commit()
    except SQLAlchemyError:
        logger.error("offer_key_skills_persist_failed", offer_id=offer_id, exc_info=True)
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
                analysis_fields, new_offer_key_skills = _analyze_match(context)
                if new_offer_key_skills is not None:
                    _persist_offer_key_skills(context["offer_id"], new_offer_key_skills)
                _update_match_analysis(match_id, "done", **analysis_fields)
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
