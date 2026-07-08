"""Offer fetching agent — fetch, embed, and dispatch job offers from France Travail.

Runs as a Container App Job on a timer trigger (12:00 and 20:00 UTC).

Expected environment variables:
    DATABASE_URL: PostgreSQL connection string.
    AZURE_SERVICEBUS_CONNECTION_STRING: Service Bus connection string.
    AZURE_OPENAI_API_KEY: Azure OpenAI API key.
    AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint URL.
    FT_CLIENT_ID: France Travail OAuth2 client ID.
    FT_CLIENT_SECRET: France Travail OAuth2 client secret.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import case, func, literal_column, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from ft_client import fetch_offers, get_access_token
from shared.bus import send_message
from shared.config import OFFER_MAX_AGE_DAYS
from shared.db import get_session, run_migrations
from shared.embedder import embed
from shared.geo import parse_department_from_location, parse_region_from_location
from shared.models import Offer, UserProfile
from shared.tech_keywords import extract_tech_keywords
from shared.telemetry import configure_telemetry

FALLBACK_ROME_CODES = ["M1805", "M1802", "M1806", "M1810", "M1811"]
OFFER_READY_QUEUE = "offer-ready"

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


def _upsert_offers(raw_offers: list[dict], rome_code: str) -> int:
    """Upsert raw API offers into the offers table.

    On conflict (ft_id), updates all mutable fields except created_at.
    The embedding is reset to NULL only when the incoming ft_updated_at is
    more recent than the stored value (or when the stored value is NULL, which
    covers migrated rows). This avoids invalidating embeddings for unchanged offers.

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
    values = []
    for raw in raw_offers:
        raw_ft_updated_at = raw.get("dateActualisation")
        ft_updated_at = (
            datetime.fromisoformat(raw_ft_updated_at) if raw_ft_updated_at else None
        )
        libelle = raw.get("lieuTravail", {}).get("libelle", "Non renseigné")
        values.append({
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
            "tech_keywords": extract_tech_keywords(raw.get("description", "")),
            "rome_code": rome_code,
            "collected_at": now,
            "ft_updated_at": ft_updated_at,
        })

    try:
        with get_session() as session:
            insert_stmt = pg_insert(Offer).values(values)
            upsert_stmt = insert_stmt.on_conflict_do_update(
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
                    "tech_keywords": insert_stmt.excluded.tech_keywords,
                    "rome_code": insert_stmt.excluded.rome_code,
                    "collected_at": insert_stmt.excluded.collected_at,
                    "ft_updated_at": insert_stmt.excluded.ft_updated_at,
                    "embedding": case(
                        (
                            insert_stmt.excluded.ft_updated_at.isnot(None)
                            & (
                                Offer.ft_updated_at.is_(None)
                                | (insert_stmt.excluded.ft_updated_at > Offer.ft_updated_at)
                            ),
                            None,
                        ),
                        else_=Offer.embedding,
                    ),
                },
            ).returning((literal_column("xmax") == 0).label("inserted"))

            result = session.execute(upsert_stmt)
            new_count = sum(1 for row in result if row.inserted)
            session.commit()
    except SQLAlchemyError:
        logger.error("upsert_offers_failed", rome_code=rome_code, exc_info=True)
        raise

    logger.info("offers_upserted", rome_code=rome_code, total=len(raw_offers), new=new_count)
    return new_count


def _embed_pending_offers() -> int:
    """Embed all offers that have no embedding vector.

    Fetches offers with embedding IS NULL, calls the batch embed API,
    and writes vectors back to the database.

    Returns:
        Number of offers embedded.

    Raises:
        SQLAlchemyError: If a database operation fails.
        openai.OpenAIError: If the embedding API call fails.
    """
    try:
        with get_session() as session:
            pending = session.execute(
                select(Offer.id, Offer.description).where(Offer.embedding.is_(None))
            ).all()
    except SQLAlchemyError:
        logger.error("embed_fetch_pending_failed", exc_info=True)
        raise

    if not pending:
        logger.info("embedding_no_pending_offers")
        return 0

    logger.info("embedding_pending_offers", count=len(pending))
    descriptions = [row.description for row in pending]
    vectors = embed(descriptions)

    update_mappings = [
        {"id": row.id, "embedding": vector}
        for row, vector in zip(pending, vectors)
    ]
    try:
        with get_session() as session:
            # ORM bulk UPDATE by PK — SQLAlchemy generates UPDATE ... WHERE id = ?
            # from the PK in each dict; no .where() / .values() needed
            session.execute(update(Offer), update_mappings)
            session.commit()
    except SQLAlchemyError:
        logger.error("embed_update_failed", count=len(pending), exc_info=True)
        raise

    logger.info("embedding_completed", count=len(pending))
    return len(pending)


def _refresh_term_stats() -> int:
    """Recompute corpus-wide term document frequencies into term_stats.

    Uses Postgres ts_stat() over to_tsvector('french', description) applied to
    the whole offers table: one row per French-stemmed lexeme with the number
    of offers containing it (ndoc). The previous content is entirely replaced
    in the same transaction — the corpus changes at every fetch/cleanup cycle,
    stale frequencies have no value to keep. total_offers is captured in the
    same statement so the ratio doc_frequency/total_offers stays exact for the
    snapshot the frequencies were computed from.

    Returns:
        Number of distinct terms written to term_stats.

    Raises:
        SQLAlchemyError: If a database operation fails.
    """
    logger.info("term_stats_refresh_started")
    try:
        with get_session() as session:
            session.execute(text("DELETE FROM term_stats"))
            result = session.execute(
                text("""
                    INSERT INTO term_stats (term, doc_frequency, total_offers, computed_at, created_at)
                    SELECT stat.word,
                           stat.ndoc,
                           (SELECT COUNT(*) FROM offers),
                           NOW(),
                           NOW()
                    FROM ts_stat('SELECT to_tsvector(''french'', description) FROM offers') AS stat
                """)
            )
            term_count = result.rowcount
            session.commit()
    except SQLAlchemyError:
        logger.error("term_stats_refresh_failed", exc_info=True)
        raise

    logger.info("term_stats_refresh_completed", term_count=term_count)
    return term_count


def main() -> None:
    """Run the offer-fetch job: fetch, upsert, embed, and signal readiness."""
    configure_telemetry("offer-fetching")

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

    # Toujours rafraîchi (même sans nouvelle offre) : les descriptions d'offres
    # existantes peuvent avoir changé via l'upsert, et le cleanup fait aussi
    # évoluer le corpus entre deux fetches. Avant l'envoi d'offer-ready, pour
    # que le matching déclenché par ce message voie des statistiques fraîches.
    _refresh_term_stats()

    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if total_new > 0:
        send_message(
            OFFER_READY_QUEUE,
            {
                "run_date": run_date,
                "rome_codes": rome_codes,
                "new_offers_count": total_new,
                "embedded_count": embedded_count,
            },
        )
    else:
        logger.info("offer_ready_skipped", reason="no_new_offers")

    logger.info(
        "offer_fetch_run_completed",
        run_date=run_date,
        rome_codes=rome_codes,
        new_offers_count=total_new,
        embedded_count=embedded_count,
    )


if __name__ == "__main__":
    main()
