"""Matching agent — pairs CVs with job offers using pgvector cosine similarity.

"""

import os
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, literal_column, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.bus import receive_message, send_message
from shared.db import get_session, run_migrations
from shared.models import Match, Offer

OFFER_READY_QUEUE = "offer-ready"
MATCH_READY_QUEUE = "match-ready"
TOP_K = int(os.getenv("MATCHING_TOP_K", "20"))

logger = structlog.get_logger()


def _get_all_matches(session: Session) -> list[dict]:
    """Return top-K offer matches for every CV with a non-null embedding.

    Uses a single window-function query to avoid N+1 round-trips.
    One SQL statement regardless of the number of CVs.

    Returns:
        List of dicts with cv_id, offer_id, score.

    Raises:
        SQLAlchemyError: If the database query fails.
    """
    logger.info("matching_batch_query_started")
    result = session.execute(
        text("""
            SELECT cv_id, offer_id, score
            FROM (
                SELECT
                    c.id AS cv_id,
                    o.id AS offer_id,
                    (1 - (o.embedding <=> c.embedding)) AS score,
                    row_number() OVER (
                        PARTITION BY c.id
                        ORDER BY o.embedding <=> c.embedding
                    ) AS rn
                FROM cvs c
                JOIN offers o ON o.embedding IS NOT NULL
                WHERE c.embedding IS NOT NULL
            ) ranked
            WHERE rn <= :top_k
        """),
        {"top_k": TOP_K},
    )

    return [
        {"cv_id": row.cv_id, "offer_id": row.offer_id, "score": float(row.score)}
        for row in result
    ]


def _upsert_matches(matches: list[dict], session: Session) -> int:
    """Upsert matches into the matches table.

    On conflict (cv_id, offer_id), updates the score. Uses RETURNING xmax to
    count true inserts atomically.

    Args:
        matches: List of dicts with keys cv_id, offer_id, and score.
        session: Active SQLAlchemy session.

    Returns:
        Number of newly inserted matches (not updates).
    """
    if not matches:
        return 0

    now = datetime.now(timezone.utc)
    values = [
        {
            "id": uuid.uuid4(),
            "cv_id": m["cv_id"],
            "offer_id": m["offer_id"],
            "score": m["score"],
            "created_at": now,
        }
        for m in matches
    ]
    insert_stmt = pg_insert(Match).values(values)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        constraint="uq_matches_cv_offer",
        set_={"score": insert_stmt.excluded.score},
    ).returning((literal_column("xmax") == 0).label("inserted"))

    result = session.execute(upsert_stmt)
    new_count = sum(1 for row in result if row.inserted)
    return new_count


def main() -> None:
    """Consume one offer-ready message and run matching for all CVs."""
    run_migrations()

    with receive_message(OFFER_READY_QUEUE) as msg:
        run_date = msg.get("run_date", "")
        logger.info("matching_run_started", run_date=run_date)

        all_matches: list[dict] = []
        new_matches = 0
        offers_available: int = 0
        try:
            with get_session() as session:
                offers_available = session.execute(
                    select(func.count()).select_from(Offer).where(Offer.embedding.isnot(None))
                ).scalar()
                all_matches = _get_all_matches(session)
                if all_matches:
                    new_matches = _upsert_matches(all_matches, session)
                session.commit()
        except SQLAlchemyError:
            logger.error("matching_failed", exc_info=True)
            raise

        if not all_matches:
            logger.info("matching_no_cvs_found")
            return

        cvs_processed = len({m["cv_id"] for m in all_matches})

        send_message(
            MATCH_READY_QUEUE,
            {
                "run_date": run_date,
                "cvs_processed": cvs_processed,
                "new_matches": new_matches,
                "offers_available": offers_available,
            },
        )

        logger.info(
            "matching_run_completed",
            run_date=run_date,
            cvs_processed=cvs_processed,
            new_matches=new_matches,
            offers_available=offers_available,
        )


if __name__ == "__main__":
    main()
