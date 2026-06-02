"""Profile endpoints — read and upsert the authenticated user's job search preferences."""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.models import UserProfile
from auth import get_current_user
from dependencies import get_db
from schemas import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])
logger = structlog.get_logger()


@router.get("", response_model=ProfileOut)
def get_profile(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ProfileOut:
    """Return the job search profile for the authenticated user.

    Args:
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        ProfileOut with the user's current job search preferences.

    Raises:
        HTTPException 404: If no profile exists for this user.
    """
    logger.info("profile_get_started", user_id=user_id)

    try:
        profile = session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        # Base class is intentional — any DB error (connection lost, timeout)
        # should abort the response and return 500.
        logger.error("profile_get_failed", user_id=user_id, exc_info=True)
        raise

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    return ProfileOut.model_validate(profile)


@router.put("", response_model=ProfileOut)
def put_profile(
    body: ProfileUpdate,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ProfileOut:
    """Create or update the job search profile for the authenticated user.

    Preferences only — rome_codes are managed by the CV upload pipeline
    and are never overwritten here.

    Args:
        body: New profile preferences.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        ProfileOut reflecting the stored profile after upsert.
    """
    logger.info("profile_put_started", user_id=user_id)

    now = datetime.now(timezone.utc)
    try:
        # rome_codes is intentionally absent from set_{} — it is managed exclusively
        # by the GPT-4o-mini CV analysis agent and must never be overwritten here.
        session.execute(
            pg_insert(UserProfile).values(
                id=uuid.uuid4(),
                user_id=user_id,
                rome_codes=[],
                job_categories=body.job_categories,
                location=body.location,
                contract_types=body.contract_types,
                created_at=now,
            ).on_conflict_do_update(
                constraint="uq_user_profiles_user_id",
                set_={
                    "job_categories": body.job_categories,
                    "location": body.location,
                    "contract_types": body.contract_types,
                },
            )
        )
        session.commit()

        profile = session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one()
    except SQLAlchemyError:
        # Base class is intentional — any DB error (connection lost, constraint
        # violation, timeout) should abort the upsert and return 500.
        logger.error("profile_put_failed", user_id=user_id, exc_info=True)
        raise

    logger.info("profile_put_completed", user_id=user_id)
    return ProfileOut.model_validate(profile)
