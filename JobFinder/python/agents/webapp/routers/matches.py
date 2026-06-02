"""Matches endpoint — returns ranked job offers for the authenticated user's CV."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from shared.models import CV, Match, UserProfile
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

        results = session.execute(
            select(Match)
            .join(CV, Match.cv_id == CV.id)
            .where(CV.user_id == user_id)
            .options(selectinload(Match.offer))
            .order_by(Match.score.desc())
        ).scalars().all()
    except SQLAlchemyError:
        # Base class is intentional — any DB error (connection lost, timeout)
        # should abort the response and return 500.
        logger.error("matches_fetch_failed", user_id=user_id, exc_info=True)
        raise

    rome_codes = list(profile.rome_codes) if profile else []
    matches = [MatchOut.model_validate(m) for m in results]
    logger.info("matches_fetch_completed", user_id=user_id, count=len(matches))
    return MatchesOut(rome_codes=rome_codes, matches=matches)
