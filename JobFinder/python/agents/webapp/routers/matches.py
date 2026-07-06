"""Matches endpoint — returns ranked job offers for the authenticated user's CV."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from shared.geo import department_from_commune, regions_intersecting
from shared.models import CV, Match, Offer, UserProfile
from auth import get_current_user
from dependencies import get_db
from schemas import MatchOut, MatchesOut

DEPT_TOKEN_PREFIX = "dept:"

router = APIRouter(prefix="/matches", tags=["matches"])
logger = structlog.get_logger()


def _commune_zone_condition(commune_codes: list[str]) -> ColumnElement[bool]:
    """Build the offer geographic condition for a stored commune zone.

    The stored zone mixes plain INSEE codes with department tokens
    ("dept:74") written by the frontend when every commune of a department
    is selected. A token matches offers by INSEE code prefix — INSEE codes
    always start with their department code — which keeps both the stored
    array and the SQL parameter list small.

    France Travail frequently leaves an offer's INSEE commune code empty
    even when it provides a specific city in the free-text location label
    (a source data-quality gap, not a remote/nationwide marker). Offers fall
    back through three levels of decreasing precision, each only applying
    when every finer level is unknown:

    1. Exact commune, or department prefix match (nominal case).
    2. Parsed department (shared.geo.parse_department_from_location) — for
       offers with a specific city but no INSEE code.
    3. Parsed region (shared.geo.parse_region_from_location) — for offers
       whose label is a bare region name (e.g. "Île-de-France") rather than
       a "DD - Ville" department prefix; included if any department of that
       region is in the zone.

    Offers where none of commune, department, or region can be determined
    (genuinely unlocatable postings, e.g. "France", "Luxembourg") always
    pass. An offer with a known commune or department outside the zone is
    never rescued by a coarser fallback — precise data always takes
    precedence.

    Args:
        commune_codes: Stored zone — INSEE codes and/or department tokens.

    Returns:
        SQLAlchemy boolean condition matching offers inside the zone.
    """
    codes = [c for c in commune_codes if not c.startswith(DEPT_TOKEN_PREFIX)]
    depts = {
        c.removeprefix(DEPT_TOKEN_PREFIX)
        for c in commune_codes
        if c.startswith(DEPT_TOKEN_PREFIX)
    }
    departments = depts | {department_from_commune(c) for c in codes}
    candidate_regions = regions_intersecting(departments) if departments else set()

    conditions: list[ColumnElement[bool]] = []
    if codes:
        conditions.append(Offer.commune.in_(codes))
    conditions.extend(Offer.commune.startswith(dept, autoescape=True) for dept in depts)

    region_level: list[ColumnElement[bool]] = [Offer.region.is_(None)]
    if candidate_regions:
        region_level.append(Offer.region.in_(candidate_regions))

    department_level: list[ColumnElement[bool]] = [
        and_(Offer.department.is_(None), or_(*region_level)),
    ]
    if departments:
        department_level.append(Offer.department.in_(departments))

    conditions.append(and_(Offer.commune.is_(None), or_(*department_level)))

    return or_(*conditions)


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
        # zone are never returned (except commune-less offers: remote or
        # nationwide postings). An empty zone means no filtering at all.
        if profile is not None and profile.commune_codes:
            stmt = stmt.join(Offer, Match.offer_id == Offer.id).where(
                _commune_zone_condition(profile.commune_codes)
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
                _commune_zone_condition(profile.commune_codes)
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
