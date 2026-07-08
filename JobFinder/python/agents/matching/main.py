"""Matching agent — pairs CVs with job offers using pgvector cosine similarity.

"""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, literal_column, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from azure.servicebus.exceptions import ServiceBusError

from shared.bus import receive_message, send_message
from shared.config import INTENT_EMBEDDING_WEIGHT, MATCH_ANALYSIS_AUTO_TOP_N, MATCHING_SCORE_THRESHOLD
from shared.db import get_session, run_migrations
from shared.models import CV, Match, MatchAnalysis, Offer
from shared.telemetry import configure_telemetry

OFFER_READY_QUEUE = "offer-ready"
MATCH_READY_QUEUE = "match-ready"
MATCH_ANALYSIS_QUEUE = "match-analysis"

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


def _enqueue_top_n_analyses(session: Session, top_n: int) -> list[uuid.UUID]:
    """Insert pending match_analyses rows for each CV's current top-N unanalyzed matches.

    Ranking uses ALL of a CV's matches, not just those touched by this run — a match that
    climbs into the top N because a higher-ranked offer expired must still be captured
    (see ADR-018). on_conflict_do_nothing makes this safe if two matching runs overlap;
    RETURNING match_id ensures only genuinely new rows trigger a Service Bus message.

    Args:
        session: Active SQLAlchemy session (caller owns commit).
        top_n: Number of top-ranked unanalyzed matches to enqueue per CV.

    Returns:
        List of match IDs newly enqueued for analysis.
    """
    now = datetime.now(timezone.utc)
    ranked = session.execute(
        text("""
            WITH ranked AS (
                SELECT m.id AS match_id,
                       ROW_NUMBER() OVER (PARTITION BY m.cv_id ORDER BY m.score DESC) AS rn
                FROM matches m
            )
            SELECT r.match_id
            FROM ranked r
            LEFT JOIN match_analyses ma ON ma.match_id = r.match_id
            WHERE r.rn <= :top_n AND ma.id IS NULL
        """),
        {"top_n": top_n},
    ).all()
    if not ranked:
        return []
    values = [
        {
            "id": uuid.uuid4(),
            "match_id": row.match_id,
            "status": "pending",
            "triggered_by": "auto_top_n",
            "matched_skills": [],
            "requested_at": now,
        }
        for row in ranked
    ]
    insert_stmt = pg_insert(MatchAnalysis).values(values).on_conflict_do_nothing(
        constraint="uq_match_analyses_match_id"
    ).returning(MatchAnalysis.match_id)
    return [row.match_id for row in session.execute(insert_stmt)]


def main() -> None:
    """Consume one offer-ready message and run matching for all CVs."""
    configure_telemetry("matching")

    try:
        run_migrations()
    except Exception:  # intentional: any migration error must halt the agent
        logger.error("migrations_failed", exc_info=True)
        raise

    # receive_message is a @contextmanager that yields the decoded payload dict
    # and handles complete/abandon on exit. RuntimeError means no messages available.
    try:
        with receive_message(OFFER_READY_QUEUE) as msg:
            run_date = msg.get("run_date", "")
            logger.info("matching_run_started", run_date=run_date)

            all_matches: list[dict] = []
            new_matches = 0
            offers_available: int = 0
            newly_enqueued: list[uuid.UUID] = []
            try:
                with get_session() as session:
                    offers_available = session.execute(
                        select(func.count()).select_from(Offer).where(Offer.embedding.isnot(None))
                    ).scalar()
                    all_matches = _get_all_matches(session)
                    if all_matches:
                        new_matches = _upsert_matches(all_matches, session)
                    newly_enqueued = _enqueue_top_n_analyses(session, MATCH_ANALYSIS_AUTO_TOP_N)
                    # Advance CVs whose analysis is complete ("done") to "matched" so the
                    # frontend can distinguish "matching in progress" from "0 real results".
                    session.execute(
                        update(CV).where(CV.status == "done").values(status="matched")
                    )
                    session.commit()
            except SQLAlchemyError:
                logger.error("matching_failed", exc_info=True)
                raise

            # Dispatched after commit — fire-and-forget, never fails the matching run
            # (same trade-off as cv_upload_analysis_trigger_failed in routers/cv.py).
            for match_id in newly_enqueued:
                try:
                    send_message(MATCH_ANALYSIS_QUEUE, {"match_id": str(match_id)})
                except ServiceBusError:
                    logger.error("matching_analysis_dispatch_failed", match_id=str(match_id), exc_info=True)

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

    except RuntimeError:
        # receive_message returns without yielding when the queue is empty —
        # typically a manual "Run now" without a pending offer-ready message.
        # Unlike cv_analysis/match_analysis (per-message workers where an
        # empty-queue race is a normal no-op), a matching run that consumed
        # nothing must be reported Failed: it performed no matching and must
        # not look like a successful run. The log line states the cause; the
        # re-raise makes the execution exit non-zero.
        logger.error("matching_no_message_failing_run")
        raise


if __name__ == "__main__":
    main()
