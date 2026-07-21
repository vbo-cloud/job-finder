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
from shared.config import (
    EXPERIENCE_MAX_PENALTY,
    EXPERIENCE_PENALTY_PER_YEAR_GAP,
    INTENT_EMBEDDING_WEIGHT,
    MATCH_ANALYSIS_AUTO_TOP_N,
    MATCHING_SCORE_THRESHOLD,
)
from shared.db import get_session, run_migrations
from shared.models import CV, Match, MatchAnalysis, Offer
from shared.telemetry import configure_telemetry

START_MATCHING_QUEUE = "start-matching"
MATCH_READY_QUEUE = "match-ready"
MATCH_ANALYSIS_QUEUE = "match-analysis"

logger = structlog.get_logger()


def _get_all_matches(session: Session) -> list[dict]:
    """Return offer matches above the score threshold for every CV with a non-null embedding.

    Uses a single query to avoid N+1 round-trips.
    One SQL statement regardless of the number of CVs.

    Returns:
        List of dicts with cv_id, offer_id, score.

    Note: an offer is only a candidate for a CV if the offer's rome_code is a key of
    rome_codes on the CV owner's profile, with this specific cv_id present in that
    key's cv_ids list — not just any code anywhere on the profile. This matters for
    an account with e.g. one dev CV and one BTP CV (explicitly supported, see
    routers/cv.py CV upload comment): each CV must only ever match offers tagged
    with a ROME code it was itself analysed into, never a code that only came from
    a sibling CV on the same account. Before this filter, matching ran with zero
    domain/profession restriction — a single shared offer pool scored by cosine
    similarity alone let e.g. a construction CV surface developer or financial-
    analyst offers. See prompt-matching-rome-code-hard-filter.md for the diagnostic.

    Note: base scores are computed as (1 - cosine_distance) between the CV and
    offer embeddings, blended with (1 - cosine_distance) against the profile's
    intent_embedding (candidate_description only — experience_level feeds the
    separate experience malus below, never the embedding) when one exists —
    weighted INTENT_EMBEDDING_WEIGHT / (1 - INTENT_EMBEDDING_WEIGHT).
    Falls back to the CV-only score when the profile has no intent_embedding.
    OpenAI text-embedding-3-small produces normalized vectors, so scores are
    bounded in [0, 1] in practice.

    A progressive experience penalty is then subtracted: when the offer's
    experience_min_years exceeds the years ceiling of the candidate's declared
    experience_level ('0-2' -> 2, '2-5' -> 5), each missing year costs
    EXPERIENCE_PENALTY_PER_YEAR_GAP, capped at EXPERIENCE_MAX_PENALTY.
    A missing signal on either side ('5+' or no profile, offer without a
    parseable experience label) never penalizes — absence of data is not a
    candidate or offer defect.

    No lexical bonus is applied: the final score is the experience-penalized
    embedding similarity alone. Distinguishing a rare-but-relevant shared term
    from a rare-but-irrelevant one (e.g. "sport", "jeux") requires semantic
    judgment that no purely statistical measure over isolated words can make —
    see prompt-matching-remove-lexical-bonus.md for the diagnostic behind this.

    Args:
        session: Active SQLAlchemy session.

    Raises:
        SQLAlchemyError: If the database query fails.
    """
    logger.info("matching_batch_query_started", threshold=MATCHING_SCORE_THRESHOLD)
    result = session.execute(
        text("""
            WITH cv_rome_codes AS (
                -- offers.rome_code is a single column (not an array); an offer that is
                -- genuinely relevant to several ROME codes but was last upserted under only
                -- one of them stays invisible to CVs for which it's a *different* relevant
                -- code. Accepted trade-off for this filter — see
                -- prompt-matching-rome-code-hard-filter.md; fixing it needs offers.rome_code
                -- to become an array, out of scope here.
                SELECT c.id AS cv_id, code_entry.key AS rome_code
                FROM cvs c
                JOIN user_profiles up ON up.user_id = c.user_id
                CROSS JOIN LATERAL jsonb_each(up.rome_codes) AS code_entry(key, value)
                WHERE code_entry.value -> 'cv_ids' ? c.id::text
            ),
            scored AS (
                SELECT
                    c.id AS cv_id,
                    o.id AS offer_id,
                    CASE
                        WHEN up.intent_embedding IS NOT NULL THEN
                            (1 - :intent_weight) * (1 - (o.embedding <=> c.embedding))
                            + :intent_weight * (1 - (o.embedding <=> up.intent_embedding))
                        ELSE
                            1 - (o.embedding <=> c.embedding)
                    END AS base_score,
                    CASE up.experience_level
                        WHEN '0-2' THEN 2
                        WHEN '2-5' THEN 5
                        ELSE NULL  -- '5+' ou profil sans experience_level : jamais pénalisé
                    END AS candidate_years_ceiling,
                    o.experience_min_years
                FROM cvs c
                JOIN cv_rome_codes crc ON crc.cv_id = c.id
                JOIN offers o ON o.rome_code = crc.rome_code AND o.embedding IS NOT NULL
                LEFT JOIN user_profiles up ON up.user_id = c.user_id
                WHERE c.embedding IS NOT NULL
            ),
            after_experience AS (
                -- Le double COALESCE gère l'absence de signal sans branche explicite :
                -- candidate_years_ceiling NULL -> 999 -> écart toujours <= 0 -> pénalité nulle ;
                -- experience_min_years NULL -> 0 -> écart jamais positif -> pénalité nulle.
                SELECT
                    cv_id,
                    offer_id,
                    GREATEST(
                        0,
                        base_score - LEAST(
                            GREATEST(0, COALESCE(experience_min_years, 0) - COALESCE(candidate_years_ceiling, 999)),
                            :max_penalty / NULLIF(:penalty_per_year, 0)
                        ) * :penalty_per_year
                    ) AS score
                FROM scored
            )
            SELECT cv_id, offer_id, score FROM after_experience WHERE score >= :threshold
        """),
        {
            "threshold": MATCHING_SCORE_THRESHOLD,
            "intent_weight": INTENT_EMBEDDING_WEIGHT,
            "penalty_per_year": EXPERIENCE_PENALTY_PER_YEAR_GAP,
            "max_penalty": EXPERIENCE_MAX_PENALTY,
        },
    )

    return [
        {"cv_id": row.cv_id, "offer_id": row.offer_id, "score": float(row.score)}
        for row in result
    ]


def _purge_stale_matches(session: Session) -> int:
    """Delete matches (and their match_analyses) whose offer.rome_code no longer belongs to
    the CV's own ROME codes.

    Self-healing companion to the ROME-code hard filter in _get_all_matches: matches
    inserted before this filter existed (or left over if a CV's rome_codes changed)
    are removed here every run, so the pipeline recovers without a separate backfill
    script.

    match_analyses are deleted first — matches.id has no CASCADE from
    fk_match_analyses_match_id_ref_matches (see routers/cv.py::_delete_cv for the same
    ordering). Deliberately does not refund analysis_credits_remaining for any
    manually-triggered analysis being purged — the analysis was genuinely delivered
    against a match that existed at the time; treated the same as other accepted
    trade-offs in this codebase (e.g. the blob-then-commit ordering in
    routers/cv.py::_delete_cv).

    Args:
        session: Active SQLAlchemy session (caller owns commit).

    Returns:
        Number of matches deleted.

    Raises:
        SQLAlchemyError: On any database error.
    """
    logger.info("matching_purge_started")
    stale_predicate = """
        NOT EXISTS (
            SELECT 1
            FROM user_profiles up
            CROSS JOIN LATERAL jsonb_each(up.rome_codes) AS code_entry(key, value)
            WHERE up.user_id = c.user_id
              AND code_entry.key = o.rome_code
              AND code_entry.value -> 'cv_ids' ? c.id::text
        )
    """
    session.execute(
        text(f"""
            DELETE FROM match_analyses
            WHERE match_id IN (
                SELECT m.id
                FROM matches m
                JOIN cvs c ON c.id = m.cv_id
                JOIN offers o ON o.id = m.offer_id
                WHERE c.embedding IS NOT NULL AND {stale_predicate}
            )
        """)
    )
    result = session.execute(
        text(f"""
            DELETE FROM matches m
            USING cvs c, offers o
            WHERE m.cv_id = c.id
              AND m.offer_id = o.id
              AND c.embedding IS NOT NULL
              AND {stale_predicate}
            RETURNING m.id
        """)
    )
    return len(result.fetchall())


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

    logger.info("matching_upsert_started", match_count=len(matches))
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
    logger.info("matching_enqueue_top_n_started", top_n=top_n)
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


def _advance_analyzed_cvs_to_matched(session: Session) -> int:
    """Advance CVs whose analysis is complete ("done") to "matched".

    Lets the frontend distinguish "matching in progress" from "0 real results" —
    a CV only reaches "matched" once at least one matching run has considered it.

    Args:
        session: Active SQLAlchemy session (caller owns commit).

    Returns:
        Number of CVs advanced.
    """
    logger.info("matching_advance_status_started")
    result = session.execute(
        update(CV).where(CV.status == "done").values(status="matched")
    )
    return result.rowcount


def main() -> None:
    """Consume one start-matching message and run matching for all CVs."""
    configure_telemetry("matching")

    try:
        run_migrations()
    except Exception:  # intentional: any migration error must halt the agent
        logger.error("migrations_failed", exc_info=True)
        raise

    # receive_message is a @contextmanager that yields the decoded payload dict
    # and handles complete/abandon on exit. RuntimeError means no messages available.
    try:
        with receive_message(START_MATCHING_QUEUE) as msg:
            run_date = msg.get("run_date", "")
            logger.info("matching_run_started", run_date=run_date)

            all_matches: list[dict] = []
            new_matches = 0
            offers_available: int = 0
            purged_matches = 0
            newly_enqueued: list[uuid.UUID] = []
            try:
                with get_session() as session:
                    offers_available = session.execute(
                        select(func.count()).select_from(Offer).where(Offer.embedding.isnot(None))
                    ).scalar()
                    all_matches = _get_all_matches(session)
                    if all_matches:
                        new_matches = _upsert_matches(all_matches, session)
                    # Must run before _enqueue_top_n_analyses: an obsolete match must
                    # never be enqueued for GPT-4o-mini analysis right before deletion.
                    purged_matches = _purge_stale_matches(session)
                    newly_enqueued = _enqueue_top_n_analyses(session, MATCH_ANALYSIS_AUTO_TOP_N)
                    _advance_analyzed_cvs_to_matched(session)
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
                purged_matches=purged_matches,
            )

    except RuntimeError:
        # receive_message returns without yielding when the queue is empty —
        # typically a manual "Run now" without a pending start-matching message.
        # Unlike cv_analysis/match_analysis (per-message workers where an
        # empty-queue race is a normal no-op), a matching run that consumed
        # nothing must be reported Failed: it performed no matching and must
        # not look like a successful run. The log line states the cause; the
        # re-raise makes the execution exit non-zero.
        logger.error("matching_no_message_failing_run")
        raise


if __name__ == "__main__":
    main()
