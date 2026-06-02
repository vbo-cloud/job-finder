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

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import case, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from ft_client import fetch_offers, get_access_token
from shared.bus import send_message
from shared.config import OFFER_MAX_AGE_DAYS
from shared.db import get_session, run_migrations
from shared.embedder import embed
from shared.models import Offer, UserProfile

FALLBACK_ROME_CODES = ["M1805", "M1802", "M1806", "M1810", "M1811"]
OFFER_READY_QUEUE = "offer-ready"

logger = structlog.get_logger()


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
            result = session.execute(
                select(func.unnest(UserProfile.rome_codes).distinct())
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
        values.append({
            "id": uuid.uuid4(),
            "ft_id": raw["id"],
            "title": raw["intitule"],
            "company": raw.get("entreprise", {}).get("nom", "Non renseigné"),
            "location": raw.get("lieuTravail", {}).get("libelle", "Non renseigné"),
            "contract_type": raw.get("typeContratLibelle", "Non renseigné"),
            "salary": raw.get("salaire", {}).get("libelle"),
            "description": raw.get("description", ""),
            "skills": [c["libelle"] for c in raw.get("competences", [])],
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
                    "contract_type": insert_stmt.excluded.contract_type,
                    "salary": insert_stmt.excluded.salary,
                    "description": insert_stmt.excluded.description,
                    "skills": insert_stmt.excluded.skills,
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


def main() -> None:
    """Run the offer-fetch job: fetch, upsert, embed, and signal readiness."""
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
