"""Cleanup agent — purges stale offers and associated matches from PostgreSQL.

Triggered by KEDA timer at 02:00 UTC daily. No queue interaction.

Expected environment variables:
    DATABASE_URL: PostgreSQL connection string.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.config import OFFER_MAX_AGE_DAYS
from shared.db import get_session, run_migrations
from shared.models import Match, Offer

logger = structlog.get_logger()


def _cleanup(session: Session) -> tuple[int, int]:
    """Delete stale offers and their associated matches atomically.

    Steps:
        1. Identify stale offer IDs.
        2. Delete matches referencing those offers.
        3. Delete the stale offers.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Tuple of (deleted_offers, deleted_matches).

    Note: does not call session.commit() — the caller owns the transaction boundary.

    Raises:
        SQLAlchemyError: If any database operation fails.
    """
    logger.info("cleanup_started", max_age_days=OFFER_MAX_AGE_DAYS)

    cutoff = datetime.now(timezone.utc) - timedelta(days=OFFER_MAX_AGE_DAYS)

    stale_offer_ids = session.scalars(
        select(Offer.id).where(
            or_(
                Offer.ft_updated_at < cutoff,
                and_(
                    Offer.ft_updated_at.is_(None),
                    Offer.collected_at < cutoff,
                ),
            )
        )
    ).all()

    logger.info("cleanup_stale_offers_found", count=len(stale_offer_ids))

    if not stale_offer_ids:
        logger.info("cleanup_no_stale_offers")
        return 0, 0

    match_result = session.execute(
        delete(Match).where(Match.offer_id.in_(stale_offer_ids))
    )

    offer_result = session.execute(
        delete(Offer).where(Offer.id.in_(stale_offer_ids))
    )

    return offer_result.rowcount, match_result.rowcount


def main() -> None:
    """Purge stale offers and orphaned matches."""
    run_migrations()

    deleted_offers, deleted_matches = 0, 0
    try:
        with get_session() as session:
            deleted_offers, deleted_matches = _cleanup(session)
            session.commit()
    except SQLAlchemyError:
        logger.error("cleanup_failed", exc_info=True)
        raise

    logger.info(
        "cleanup_completed",
        deleted_offers=deleted_offers,
        deleted_matches=deleted_matches,
    )


if __name__ == "__main__":
    main()
