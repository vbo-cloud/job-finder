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
    SHARED_TERM_BONUS_WEIGHT,
    TERM_STOPWORD_THRESHOLD,
)
from shared.db import get_session, run_migrations
from shared.models import CV, Match, MatchAnalysis, Offer
from shared.telemetry import configure_telemetry

OFFER_READY_QUEUE = "offer-ready"
MATCH_READY_QUEUE = "match-ready"
MATCH_ANALYSIS_QUEUE = "match-analysis"

logger = structlog.get_logger()


def _get_all_matches(session: Session) -> list[dict]:
    """Return offer matches above the score threshold for every CV with a non-null embedding.

    Uses a single query to avoid N+1 round-trips.
    One SQL statement regardless of the number of CVs.

    Returns:
        List of dicts with cv_id, offer_id, score.

    Note: base scores are computed as (1 - cosine_distance) between the CV and
    offer embeddings, blended with (1 - cosine_distance) against the profile's
    intent_embedding (experience/search query/candidate description) when one
    exists — weighted INTENT_EMBEDDING_WEIGHT / (1 - INTENT_EMBEDDING_WEIGHT).
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

    Finally a strictly additive skills bonus rewards terms shared between the
    CV text and the offer description, sector-agnostic by construction: both
    sides are tokenized/stemmed by Postgres full-text search (French config)
    and each shared lexeme is weighted by its rarity in the offer corpus,
    1 - doc_frequency/total_offers from term_stats (recomputed after every
    offer_fetching run). Lexemes present in more than TERM_STOPWORD_THRESHOLD
    of all offers are de facto stopwords and fully excluded — a hard cutoff,
    not a smooth downweighting, so moderately frequent but discriminating
    terms keep full weight. The bonus is the CV-covered share of the offer's
    total rarity mass, weighted by SHARED_TERM_BONUS_WEIGHT and capped so the
    total never exceeds 1.0. It is never negative — no shared term, an empty
    term_stats table, or an offer made only of stopwords all yield a zero
    bonus, never lowering the experience-penalized score. Lexemes absent from
    term_stats (offers newer than the last stats refresh) are ignored on both
    sides of the ratio, keeping numerator and denominator consistent.

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
                    END AS base_score,
                    CASE up.experience_level
                        WHEN '0-2' THEN 2
                        WHEN '2-5' THEN 5
                        ELSE NULL  -- '5+' ou profil sans experience_level : jamais pénalisé
                    END AS candidate_years_ceiling,
                    o.experience_min_years
                FROM cvs c
                JOIN offers o ON o.embedding IS NOT NULL
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
            ),
            offer_terms AS (
                -- Lexèmes français racinisés de chaque offre, pondérés par leur rareté
                -- dans le corpus (1 - fréquence documentaire relative). INNER JOIN sur
                -- term_stats : un lexème absent des stats (offre plus récente que le
                -- dernier calcul batch) est ignoré des deux côtés du ratio. Les termes
                -- quasi universels (au-delà du seuil) sont des mots vides de fait,
                -- écartés totalement — couperet net, pas de pondération graduelle.
                SELECT
                    o.id AS offer_id,
                    t.lexeme,
                    1 - ts.doc_frequency::float / ts.total_offers AS rarity
                FROM offers o
                CROSS JOIN LATERAL unnest(tsvector_to_array(to_tsvector('french', o.description))) AS t(lexeme)
                JOIN term_stats ts ON ts.term = t.lexeme
                WHERE o.embedding IS NOT NULL
                  AND ts.doc_frequency::float / ts.total_offers <= :stopword_threshold
            ),
            cv_terms AS (
                SELECT c.id AS cv_id, t.lexeme
                FROM cvs c
                CROSS JOIN LATERAL unnest(tsvector_to_array(to_tsvector('french', c.raw_text))) AS t(lexeme)
                WHERE c.embedding IS NOT NULL
            ),
            offer_rarity_mass AS (
                SELECT offer_id, SUM(rarity) AS total_rarity
                FROM offer_terms
                GROUP BY offer_id
            ),
            covered_rarity AS (
                SELECT ct.cv_id, ot.offer_id, SUM(ot.rarity) AS covered
                FROM cv_terms ct
                JOIN offer_terms ot ON ot.lexeme = ct.lexeme
                GROUP BY ct.cv_id, ot.offer_id
            ),
            final AS (
                -- Bonus strictement additif : part de la masse de rareté de l'offre
                -- couverte par le CV (dénominateur = termes discriminants de l'offre,
                -- pas l'union). COALESCE(..., 0) couvre l'absence de terme partagé,
                -- une table term_stats vide ou une offre faite uniquement de mots
                -- vides — bonus nul, jamais un malus.
                SELECT
                    ae.cv_id,
                    ae.offer_id,
                    LEAST(
                        1.0,
                        ae.score + COALESCE(
                            cr.covered / NULLIF(orm.total_rarity, 0),
                            0
                        ) * :shared_term_weight
                    ) AS score
                FROM after_experience ae
                LEFT JOIN offer_rarity_mass orm ON orm.offer_id = ae.offer_id
                LEFT JOIN covered_rarity cr
                    ON cr.cv_id = ae.cv_id AND cr.offer_id = ae.offer_id
            )
            SELECT cv_id, offer_id, score FROM final WHERE score >= :threshold
        """),
        {
            "threshold": MATCHING_SCORE_THRESHOLD,
            "intent_weight": INTENT_EMBEDDING_WEIGHT,
            "penalty_per_year": EXPERIENCE_PENALTY_PER_YEAR_GAP,
            "max_penalty": EXPERIENCE_MAX_PENALTY,
            "stopword_threshold": TERM_STOPWORD_THRESHOLD,
            "shared_term_weight": SHARED_TERM_BONUS_WEIGHT,
        },
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
