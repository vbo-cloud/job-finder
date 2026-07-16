"""Offer fetching agent — fetch, upsert, and embed job offers from France Travail.

Runs as a Container App Job on a timer trigger, meant to actually execute at
12:00 and 20:00 Europe/Paris local time. Azure Container Apps' schedule trigger
only supports a UTC cron_expression with no timezone/DST awareness, so
Terraform fires this job at every UTC hour that could map to a target local
hour under either CET or CEST (see container_apps.tf) and main() no-ops the
firings that don't match the current DST state — see _is_scheduled_local_hour.

Fetch + upsert, then embed directly: offers with a NULL embedding (new offers,
or existing ones invalidated by a more recent ft_updated_at) are embedded on
their raw title+description text via shared.embedder.embed(), one batched
call for the whole pending set (embed() already batches internally by 100 —
no LLM distillation call per offer, so this stays fast even for thousands of
offers, unlike the retired agents/offer_distillation). If any offer was
embedded, publishes one start-matching message — the direct, event-driven
replacement for the retired agents/matching_heartbeat's periodic catch-up.

Expected environment variables:
    DATABASE_URL: PostgreSQL connection string.
    AZURE_SERVICEBUS_FULLY_QUALIFIED_NAMESPACE: Service Bus namespace host.
    AZURE_OPENAI_API_KEY: Azure OpenAI API key.
    AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint URL.
    FT_CLIENT_ID: France Travail OAuth2 client ID.
    FT_CLIENT_SECRET: France Travail OAuth2 client secret.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import structlog
from azure.servicebus.exceptions import ServiceBusError
from sqlalchemy import case, literal_column, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from ft_client import fetch_offers, get_access_token
from shared.bus import send_message
from shared.config import OFFER_MAX_AGE_DAYS
from shared.db import get_session, run_migrations
from shared.embedder import embed
from shared.geo import parse_department_from_location, parse_region_from_location
from shared.models import Offer
from shared.telemetry import configure_telemetry

FALLBACK_ROME_CODES = ["M1805", "M1802", "M1806", "M1810", "M1811"]
START_MATCHING_QUEUE = "start-matching"
PARIS_TZ = ZoneInfo("Europe/Paris")
# Kept in sync with the UTC hours covered by container_apps.tf's cron_expression
# for job_offer_fetching — see _is_scheduled_local_hour.
SCHEDULED_LOCAL_HOURS = (12, 20)

# Formats observés sur des payloads France Travail réels : "Expérience exigée de 6 An(s)",
# "Expérience exigée de 60 Mois", "Débutant accepté", ou "Expérience exigée" sans durée.
_EXPERIENCE_YEARS_PATTERN = re.compile(r"(\d+)\s*An", re.IGNORECASE)
_EXPERIENCE_MONTHS_PATTERN = re.compile(r"(\d+)\s*Mois", re.IGNORECASE)

logger = structlog.get_logger()


def _parse_experience_min_years(libelle: str | None) -> int | None:
    """Extract the minimum required years of experience from France Travail's experienceLibelle.

    Returns None if the field is absent or its format isn't recognized — absence of data must
    never be treated as "0 years required" (that would incorrectly favor offers with unparseable
    labels over honestly-labeled entry-level ones).

    Args:
        libelle: Raw experienceLibelle text from the France Travail API (e.g. "Expérience exigée
            de 6 An(s)", "Expérience exigée de 18 Mois"), or None if absent from the payload.

    Returns:
        Parsed integer years, or None if unparseable/absent. "Débutant accepté" (no duration)
        returns 0 explicitly — handled as a special case before the regexes. Month-based labels
        are floored to whole years (18 Mois -> 1): lenient by design, the penalty is progressive
        and must never over-penalize on a rounding.
    """
    if libelle is None:
        return None
    if "débutant" in libelle.lower():
        return 0
    years_match = _EXPERIENCE_YEARS_PATTERN.search(libelle)
    if years_match:
        return int(years_match.group(1))
    months_match = _EXPERIENCE_MONTHS_PATTERN.search(libelle)
    if months_match:
        return int(months_match.group(1)) // 12
    return None


def _get_active_rome_codes() -> list[str]:
    """Query distinct ROME codes across all user profiles.

    Falls back to FALLBACK_ROME_CODES if the user_profiles table is empty.

    Returns:
        List of ROME code strings to fetch.

    Raises:
        SQLAlchemyError: If the database query fails.
    """
    logger.info("rome_codes_query_started")
    try:
        with get_session() as session:
            # jsonb_object_keys is a set-returning function — use raw SQL to extract
            # distinct keys from the JSONB rome_codes column across all profiles.
            result = session.execute(
                text(
                    "SELECT DISTINCT jsonb_object_keys(rome_codes) "
                    "FROM user_profiles "
                    "WHERE rome_codes != '{}'::jsonb"
                )
            )
            codes = [row[0] for row in result if row[0] is not None]
    except SQLAlchemyError:
        logger.error("rome_codes_query_failed", exc_info=True)
        raise
    if not codes:
        logger.info("rome_codes_using_fallback", codes=FALLBACK_ROME_CODES)
        return FALLBACK_ROME_CODES
    logger.info("rome_codes_loaded", count=len(codes), codes=codes)
    return codes


def _build_offer_values(raw: dict, rome_code: str, now: datetime) -> dict:
    """Map one raw France Travail offer dict onto the offers table's insert columns.

    Args:
        raw: Raw offer dict from the France Travail API.
        rome_code: The ROME code this offer was fetched for.
        now: Timestamp to record as collected_at for this batch.

    Returns:
        dict of column name -> value, ready for a bulk insert.
    """
    raw_ft_updated_at = raw.get("dateActualisation")
    ft_updated_at = datetime.fromisoformat(raw_ft_updated_at) if raw_ft_updated_at else None
    libelle = raw.get("lieuTravail", {}).get("libelle", "Non renseigné")
    return {
        "id": uuid.uuid4(),
        "ft_id": raw["id"],
        "title": raw["intitule"],
        "company": raw.get("entreprise", {}).get("nom", "Non renseigné"),
        "location": libelle,
        "commune": raw.get("lieuTravail", {}).get("commune"),
        "department": parse_department_from_location(libelle),
        "region": parse_region_from_location(libelle),
        "latitude": raw.get("lieuTravail", {}).get("latitude"),
        "longitude": raw.get("lieuTravail", {}).get("longitude"),
        "contract_type": raw.get("typeContratLibelle", "Non renseigné"),
        "salary": raw.get("salaire", {}).get("libelle"),
        "experience_min_years": _parse_experience_min_years(raw.get("experienceLibelle")),
        "description": raw.get("description", ""),
        "skills": [c["libelle"] for c in raw.get("competences", [])],
        "rome_code": rome_code,
        "collected_at": now,
        "ft_updated_at": ft_updated_at,
    }


def _build_upsert_statement(values: list[dict]):
    """Build the on-conflict-do-update statement for a batch of offer values.

    embedding and key_skills both ride the same ft_updated_at-based CASE: reset
    to NULL only when the incoming offer is strictly newer than what's stored
    (or the stored value is NULL, which covers migrated rows) — this avoids
    invalidating either for unchanged offers. key_skills is a cache populated
    later by match_analysis; NULL is what makes it re-extract instead of
    matching against a stale list.

    Args:
        values: Column dicts as returned by _build_offer_values.

    Returns:
        The upsert statement, with a RETURNING clause flagging inserted rows.
    """
    insert_stmt = pg_insert(Offer).values(values)
    offer_changed = insert_stmt.excluded.ft_updated_at.isnot(None) & (
        Offer.ft_updated_at.is_(None)
        | (insert_stmt.excluded.ft_updated_at > Offer.ft_updated_at)
    )
    return insert_stmt.on_conflict_do_update(
        constraint="uq_offers_ft_id",
        set_={
            "title": insert_stmt.excluded.title,
            "company": insert_stmt.excluded.company,
            "location": insert_stmt.excluded.location,
            "commune": insert_stmt.excluded.commune,
            "department": insert_stmt.excluded.department,
            "region": insert_stmt.excluded.region,
            "latitude": insert_stmt.excluded.latitude,
            "longitude": insert_stmt.excluded.longitude,
            "contract_type": insert_stmt.excluded.contract_type,
            "salary": insert_stmt.excluded.salary,
            "experience_min_years": insert_stmt.excluded.experience_min_years,
            "description": insert_stmt.excluded.description,
            "skills": insert_stmt.excluded.skills,
            "rome_code": insert_stmt.excluded.rome_code,
            "collected_at": insert_stmt.excluded.collected_at,
            "ft_updated_at": insert_stmt.excluded.ft_updated_at,
            "embedding": case((offer_changed, None), else_=Offer.embedding),
            "key_skills": case((offer_changed, None), else_=Offer.key_skills),
        },
    ).returning((literal_column("xmax") == 0).label("inserted"))


def _upsert_offers(raw_offers: list[dict], rome_code: str) -> int:
    """Upsert raw API offers into the offers table.

    On conflict (ft_id), updates all mutable fields except created_at — see
    _build_upsert_statement for the embedding/key_skills invalidation rule.

    Args:
        raw_offers: Raw offer dicts from the France Travail API.
        rome_code: The ROME code these offers were fetched for.

    Returns:
        Number of newly inserted rows (not updates).

    Raises:
        SQLAlchemyError: If a database operation fails.
    """
    if not raw_offers:
        return 0

    # Dédupliquer par ft_id — France Travail peut retourner la même offre sur plusieurs pages
    seen: set[str] = set()
    unique_offers: list[dict] = []
    for raw in raw_offers:
        if raw["id"] not in seen:
            seen.add(raw["id"])
            unique_offers.append(raw)
    raw_offers = unique_offers

    now = datetime.now(timezone.utc)
    values = [_build_offer_values(raw, rome_code, now) for raw in raw_offers]

    try:
        with get_session() as session:
            result = session.execute(_build_upsert_statement(values))
            new_count = sum(1 for row in result if row.inserted)
            session.commit()
    except SQLAlchemyError:
        logger.error("upsert_offers_failed", rome_code=rome_code, exc_info=True)
        raise

    logger.info("offers_upserted", rome_code=rome_code, total=len(raw_offers), new=new_count)
    return new_count


def _embed_pending_offers() -> int:
    """Embed offers with a NULL embedding directly on their raw title+description text.

    Same selection condition the retired distillation publish step used:
    covers both newly upserted offers and offers whose embedding was
    invalidated by a more recent ft_updated_at (see the case() branch in
    _upsert_offers). Mirrors routers/cv.py's CV-side embedding: no text
    truncation before the call, no LLM distillation step first.

    Returns:
        Number of offers embedded.

    Raises:
        SQLAlchemyError: If a database operation fails.
    """
    # Two separate sessions around the embed() network call rather than one held open
    # across it. `pending` holds plain Row tuples (not ORM instances), so there is no
    # detached-instance risk in reusing them against the second session below.
    try:
        with get_session() as session:
            pending = session.execute(
                select(Offer.id, Offer.title, Offer.description).where(Offer.embedding.is_(None))
            ).all()
    except SQLAlchemyError:
        logger.error("embed_pending_fetch_pending_failed", exc_info=True)
        raise

    if not pending:
        logger.info("embed_pending_no_pending_offers")
        return 0

    logger.info("embed_pending_started", count=len(pending))
    vectors = embed([f"{row.title}\n\n{row.description}" for row in pending])

    # One UPDATE per offer — fine at the current cardinality (hundreds/day) since it's
    # a single transaction; revisit with a bulk UPDATE ... FROM/VALUES before running
    # this against a large backfill (thousands of offers), see docs/BACKLOG.md.
    try:
        with get_session() as session:
            for row, vector in zip(pending, vectors):
                session.execute(update(Offer).where(Offer.id == row.id).values(embedding=vector))
            session.commit()
    except SQLAlchemyError:
        logger.error("embed_pending_save_failed", exc_info=True)
        raise

    logger.info("embed_pending_completed", count=len(pending))
    return len(pending)


def _dispatch_start_matching(run_date: str, rome_codes: list[str], new_offers_count: int, embedded_count: int) -> None:
    """Send a start-matching message so the matching agent re-scores existing offers.

    The direct, event-driven replacement for the retired agents/matching_heartbeat's
    periodic catch-up — this agent is now the only producer that reacts to new offers.
    Fire-and-forget: a Service Bus failure is logged but never fails the run, same
    trade-off as the other start-matching producers (routers/profile.py, cv_analysis) —
    the offers are already embedded and committed, and the next scheduled fetch run
    will dispatch again regardless.

    Args:
        run_date: ISO date (YYYY-MM-DD) stamped on the message.
        rome_codes: ROME codes fetched in this run.
        new_offers_count: Number of newly inserted offers.
        embedded_count: Number of offers embedded in this run.
    """
    try:
        # rome_codes/new_offers_count/embedded_count/trigger are informational only —
        # agents/matching::main() currently reads just run_date from the payload and
        # recomputes everything else from the DB. No schema validation on the consumer
        # side depends on these fields; they exist for log correlation across agents.
        send_message(
            START_MATCHING_QUEUE,
            {
                "run_date": run_date,
                "rome_codes": rome_codes,
                "new_offers_count": new_offers_count,
                "embedded_count": embedded_count,
                "trigger": "offer_fetching",
            },
        )
        logger.info("offer_fetching_start_matching_sent", run_date=run_date)
    except ServiceBusError:
        logger.error("offer_fetching_start_matching_failed", run_date=run_date, exc_info=True)


def _is_scheduled_local_hour(now_utc: datetime) -> bool:
    """Check whether now_utc falls on one of this job's intended Europe/Paris run hours.

    Azure Container Apps' schedule trigger only supports a UTC cron_expression, with
    no timezone or DST awareness. Terraform's cron_expression for job_offer_fetching
    therefore fires at every UTC hour that could map to SCHEDULED_LOCAL_HOURS under
    either CET (UTC+1) or CEST (UTC+2) — this guard picks out the two firings that are
    actually correct for the current DST state, so main() can no-op the other two.
    That keeps the schedule correct across DST transitions without a manual Terraform
    change twice a year.

    Args:
        now_utc: Current time, timezone-aware in UTC.

    Returns:
        True if now_utc's Europe/Paris local hour is one of SCHEDULED_LOCAL_HOURS.
    """
    return now_utc.astimezone(PARIS_TZ).hour in SCHEDULED_LOCAL_HOURS


def main() -> None:
    """Run the offer-fetch job: fetch, upsert, embed pending offers, and trigger matching.

    No-ops outside SCHEDULED_LOCAL_HOURS in Europe/Paris local time — see
    _is_scheduled_local_hour.
    """
    configure_telemetry("offer-fetching")

    now_utc = datetime.now(timezone.utc)
    if not _is_scheduled_local_hour(now_utc):
        logger.info("offer_fetch_skipped_outside_local_window", utc_hour=now_utc.hour)
        return

    try:
        run_migrations()
    except Exception:  # intentional: any migration error must halt the agent
        logger.error("migrations_failed", exc_info=True)
        raise

    rome_codes = _get_active_rome_codes()
    token = get_access_token()

    cutoff = datetime.now(timezone.utc) - timedelta(days=OFFER_MAX_AGE_DAYS)
    min_date = cutoff.strftime("%Y-%m-%d")

    total_new = 0
    for rome_code in rome_codes:
        raw_offers = fetch_offers(token, rome_code, min_date=min_date)
        total_new += _upsert_offers(raw_offers, rome_code)

    embedded_count = _embed_pending_offers()

    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if embedded_count:
        _dispatch_start_matching(run_date, rome_codes, total_new, embedded_count)

    logger.info(
        "offer_fetch_run_completed",
        run_date=run_date,
        rome_codes=rome_codes,
        new_offers_count=total_new,
        embedded_count=embedded_count,
    )


if __name__ == "__main__":
    main()
