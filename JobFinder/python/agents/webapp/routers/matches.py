"""Matches endpoint — returns ranked job offers for the authenticated user's CV."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from shared.models import CV, Match, Offer, UserProfile
from auth import get_current_user
from dependencies import get_db
from schemas import MatchOut, MatchesOut

router = APIRouter(prefix="/matches", tags=["matches"])
logger = structlog.get_logger()


@router.get("", response_model=MatchesOut)
def get_matches(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> MatchesOut:
    """Return ranked job offer matches and the user's ROME codes for the authenticated user.

    rome_codes are included at the top level (readonly — managed by GPT-4o-mini)
    so the frontend can display which codes were used for matching without a
    separate GET /profile call.

    Returns an empty matches list if the user has no CV in the database.

    Args:
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        MatchesOut with rome_codes and a list of MatchOut sorted by descending score.
    """
    logger.info("matches_fetch_started", user_id=user_id)

    try:
        profile = session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one_or_none()

        stmt = (
            select(Match)
            .join(CV, Match.cv_id == CV.id)
            .where(CV.user_id == user_id)
            .options(selectinload(Match.offer))
            .order_by(Match.score.desc())
        )
        # Hard geographic filter — offers outside the user's painted commune
        # zone are never returned. An empty zone means no filtering at all.
        if profile is not None and profile.commune_codes:
            stmt = stmt.join(Offer, Match.offer_id == Offer.id).where(
                Offer.commune.in_(profile.commune_codes)
            )
        results = session.execute(stmt).scalars().all()
        rome_codes = dict(profile.rome_codes) if profile else {}
        matches = [MatchOut.model_validate(m) for m in results]
    except SQLAlchemyError:
        # Base class is intentional — any DB error (connection lost, timeout)
        # should abort the response and return 500.
        logger.error("matches_fetch_failed", user_id=user_id, exc_info=True)
        raise
    logger.info("matches_fetch_completed", user_id=user_id, count=len(matches))
    return MatchesOut(rome_codes=rome_codes, matches=matches)


@router.get("/cv/{cv_id}", response_model=MatchesOut)
def get_matches_for_cv(
    cv_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> MatchesOut:
    """Return ranked matches for a specific CV owned by the authenticated user.

    Args:
        cv_id: UUID of the CV to fetch matches for.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        MatchesOut with the user's rome_codes and matches sorted by descending score.

    Raises:
        HTTPException 404: If the CV does not exist or is not owned by the user.
        SQLAlchemyError: If a database error occurs during the query.
    """
    logger.info("cv_matches_fetch_started", user_id=user_id, cv_id=str(cv_id))
    try:
        cv = session.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        ).scalar_one_or_none()
        if cv is None:
            raise HTTPException(status_code=404, detail="CV not found")

        profile = session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one_or_none()

        stmt = (
            select(Match)
            .where(Match.cv_id == cv_id)
            .options(selectinload(Match.offer))
            .order_by(Match.score.desc())
        )
        # Hard geographic filter — same behaviour as GET /matches.
        if profile is not None and profile.commune_codes:
            stmt = stmt.join(Offer, Match.offer_id == Offer.id).where(
                Offer.commune.in_(profile.commune_codes)
            )
        results = session.execute(stmt).scalars().all()
        rome_codes = dict(profile.rome_codes) if profile else {}
        matches = [MatchOut.model_validate(m) for m in results]
    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.error("cv_matches_fetch_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise
    logger.info("cv_matches_fetch_done", user_id=user_id, cv_id=str(cv_id), count=len(matches))
    return MatchesOut(rome_codes=rome_codes, matches=matches)
