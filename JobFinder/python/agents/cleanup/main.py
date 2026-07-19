"""Cleanup agent — purges stale offers and associated matches from PostgreSQL.

Also logs a daily exact snapshot (`daily_snapshot`) of the total offers and CVs
currently in the database, for monitoring in Azure Monitor / Application Insights.

Triggered by KEDA timer at 02:00 UTC daily. No queue interaction.

Expected environment variables:
    DATABASE_URL: PostgreSQL connection string.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.config import CLEANUP_COLLECTED_AGE_DAYS
from shared.db import get_session, run_migrations
from shared.models import CV, Match, Offer
from shared.telemetry import configure_telemetry

logger = structlog.get_logger()


def _cleanup(session: Session) -> tuple[int, int]:
    """Delete stale offers and their associated matches atomically.

    An offer is considered stale when collected_at has not been refreshed within
    CLEANUP_COLLECTED_AGE_DAYS. The offer-fetching agent updates collected_at on
    every successful fetch; an offer absent from recent results has been closed on
    France Travail and will never be refreshed again.

    Assumption: collected_at is NOT NULL for all rows (enforced by the schema since
    migration 001_initial_schema). No NULL guard is needed in the predicate.

    Grace period: the offer-fetching agent runs 2×/day (12:00 and 20:00 Europe/Paris local time).
    With CLEANUP_COLLECTED_AGE_DAYS=2 an offer must miss 4 consecutive fetch cycles
    before being purged — enough to survive a transient fetching outage without
    wiping the offer pool.

    Steps:
        1. Delete matches whose offer_id is in the stale subquery.
        2. Delete the stale offers.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Tuple of (deleted_offers, deleted_matches).

    Note: does not call session.commit() — the caller owns the transaction boundary.

    Raises:
        SQLAlchemyError: If any database operation fails.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=CLEANUP_COLLECTED_AGE_DAYS)

    logger.info("cleanup_started", cutoff=cutoff.isoformat())

    stale_subquery = select(Offer.id).where(Offer.collected_at < cutoff)

    match_result = session.execute(
        delete(Match).where(Match.offer_id.in_(stale_subquery))
    )

    offer_result = session.execute(
        delete(Offer).where(Offer.id.in_(stale_subquery))
    )

    return offer_result.rowcount, match_result.rowcount


def _snapshot_totals(session: Session) -> tuple[int, int]:
    """Count offers and CVs currently in the database.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Tuple of (total_offers, total_cvs).

    Raises:
        SQLAlchemyError: If either count query fails. The caller in main() treats
            this step as best-effort and swallows the exception.
    """
    logger.info("daily_snapshot_started")

    total_offers = session.execute(select(func.count()).select_from(Offer)).scalar()
    total_cvs = session.execute(select(func.count()).select_from(CV)).scalar()
    return total_offers, total_cvs


def main() -> None:
    """Purge stale offers and orphaned matches, then log a daily exact snapshot of totals."""
    configure_telemetry("cleanup")

    try:
        run_migrations()
    except Exception:  # intentional: any migration error must halt the agent
        logger.error("migrations_failed", exc_info=True)
        raise

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

    # Best-effort, deliberate deviation from the usual log-and-re-raise pattern: a
    # snapshot failure must never fail the job, since the purge above already
    # succeeded and Container App Job metrics/alerts key off this exit status. No
    # `raise` here on purpose — swallowing is the intended behavior, not an omission.
    try:
        with get_session() as session:
            total_offers, total_cvs = _snapshot_totals(session)
        logger.info("daily_snapshot", total_offers=total_offers, total_cvs=total_cvs)
    except SQLAlchemyError:
        logger.error("daily_snapshot_failed", exc_info=True)


if __name__ == "__main__":
    main()
