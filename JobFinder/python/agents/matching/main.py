"""Matching agent — pairs CVs with job offers using pgvector cosine similarity.

"""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, literal_column, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.bus import receive_message, send_message
from shared.config import INTENT_EMBEDDING_WEIGHT, MATCHING_SCORE_THRESHOLD
from shared.db import get_session, run_migrations
from shared.models import CV, Match, Offer
from shared.telemetry import configure_telemetry

OFFER_READY_QUEUE = "offer-ready"
MATCH_READY_QUEUE = "match-ready"

logger = structlog.get_logger()


def _get_all_matches(session: Session) -> list[dict]:
    """Return top-K offer matches for every CV with a non-null embedding.

    Uses a single window-function query to avoid N+1 round-trips.
    One SQL statement regardless of the number of CVs.

    Returns:
        List of dicts with cv_id, offer_id, score.

    Note: scores are computed as (1 - cosine_distance) between the CV and offer
    embeddings, blended with (1 - cosine_distance) against the profile's
    intent_embedding (experience/search query/candidate description) when one
    exists — weighted INTENT_EMBEDDING_WEIGHT / (1 - INTENT_EMBEDDING_WEIGHT).
    Falls back to the CV-only score when the profile has no intent_embedding.
    OpenAI text-embedding-3-small produces normalized vectors, so scores are
    bounded in [0, 1] in practice.

    Raises:
        SQLAlchemyError: If the database query fails.
    """
    logger.info("matching_batch_query_started", threshold=MATCHING_SCORE_THRESHOLD)
    result = session.execute(
        text("""
            WITH scored AS (
                SELECT
                    c.id AS cv_id,
                    o.id AS offer_id,
                    CASE
                        WHEN up.intent_embedding IS NOT NULL THEN
                            (1 - :intent_weight) * (1 - (o.embedding <=> c.embedding))
                            + :intent_weight * (1 - (o.embedding <=> up.intent_embedding))
                        ELSE
                            1 - (o.embedding <=> c.embedding)
                    END AS score
                FROM cvs c
                JOIN offers o ON o.embedding IS NOT NULL
                LEFT JOIN user_profiles up ON up.user_id = c.user_id
                WHERE c.embedding IS NOT NULL
            )
            SELECT cv_id, offer_id, score FROM scored WHERE score >= :threshold
        """),
        {"threshold": MATCHING_SCORE_THRESHOLD, "intent_weight": INTENT_EMBEDDING_WEIGHT},
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
    configure_telemetry("matching")

    try:
        run_migrations()
    except Exception:  # intentional: any migration error must halt the agent
        logger.error("migrations_failed", exc_info=True)
        raise

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
                # Advance CVs whose analysis is complete ("done") to "matched" so the
                # frontend can distinguish "matching in progress" from "0 real results".
                session.execute(
                    update(CV).where(CV.status == "done").values(status="matched")
                )
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
