"""Profile endpoints — read and upsert the authenticated user's job search preferences."""

import uuid
from datetime import datetime, timezone

import structlog
from azure.servicebus.exceptions import ServiceBusError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.bus import send_message
from shared.embedder import embed
from shared.models import CV, UserProfile
from auth import (
    UserIdentity,
    get_current_admin_user,
    get_current_identity,
    get_current_user,
    is_admin,
)
from dependencies import get_db
from routers.cv import _delete_cv
from schemas import CreditsRefillOut, ProfileOut, ProfileUpdate

OFFER_READY_QUEUE = "offer-ready"
ADMIN_CREDITS_REFILL_AMOUNT = 10
_INTENT_FIELDS = {"experience_level", "candidate_description"}

router = APIRouter(prefix="/profile", tags=["profile"])
logger = structlog.get_logger()


def _build_intent_text(
    experience_level: str | None,
    candidate_description: str | None,
) -> str:
    """Combine experience/description into the text embedded as intent_embedding.

    Callers must resolve both arguments against the existing profile row first —
    a field absent from the PUT body should keep contributing its stored value,
    not silently drop out of the embedding (see put_profile).
    """
    fragments = []
    if experience_level == "0-2":
        fragments.append("Profil junior/débutant, 0 à 2 ans d'expérience")
    elif experience_level == "2-5":
        fragments.append("Profil confirmé, 2 à 5 ans d'expérience")
    elif experience_level == "5+":
        fragments.append("Profil senior, 5 ans d'expérience et plus")
    if candidate_description and candidate_description.strip():
        fragments.append(candidate_description.strip())
    return "\n".join(fragments)


def _dispatch_offer_ready(user_id: str, run_date: str) -> None:
    """Send an offer-ready message so the matching agent re-scores existing offers.

    Fire-and-forget: a Service Bus failure is logged but never fails the request —
    the profile is already committed and the next scheduled matching run will pick
    up the new intent_embedding anyway.

    Args:
        user_id: Authenticated user ID, for log correlation only.
        run_date: ISO date (YYYY-MM-DD) stamped on the message.
    """
    try:
        send_message(
            OFFER_READY_QUEUE,
            {
                "run_date": run_date,
                "rome_codes": [],
                "new_offers_count": 0,
                "embedded_count": 0,
                "trigger": "profile_update",
            },
        )
        logger.info("profile_put_offer_ready_sent", user_id=user_id)
    except ServiceBusError:
        logger.error("profile_put_offer_ready_failed", user_id=user_id, exc_info=True)


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

    return ProfileOut.model_validate(profile).model_copy(
        update={"is_admin": is_admin(user_id)}
    )


@router.put("", response_model=ProfileOut)
def put_profile(
    body: ProfileUpdate,
    identity: UserIdentity = Depends(get_current_identity),
    session: Session = Depends(get_db),
) -> ProfileOut:
    """Create or update the job search profile for the authenticated user.

    Preferences only — rome_codes are managed by the CV upload pipeline
    and are never overwritten here.

    When experience_level or candidate_description actually changes, an
    offer-ready message is dispatched after commit so the matching agent
    re-scores existing offers against the new intent_embedding.

    Args:
        body: New profile preferences.
        identity: Authenticated identity claims from the JWT (sub, email, name).
        session: Active database session.

    Returns:
        ProfileOut reflecting the stored profile after upsert.
    """
    user_id = identity.user_id
    logger.info("profile_put_started", user_id=user_id)

    now = datetime.now(timezone.utc)
    # Only the keys actually present in the request body — lets a PUT from
    # the home page (commune_codes only) and a PUT from /profile (experience/
    # description only) coexist without clobbering each other's fields.
    updated = body.model_dump(exclude_unset=True)

    # Identity claims are server-derived from the validated token (absent from
    # ProfileUpdate, so never client input) and refreshed on every PUT so a
    # renamed account or changed email converges. Only when present in the
    # token: a claimless token must not null-out previously stored values.
    if identity.email is not None:
        updated["email"] = identity.email
    if identity.display_name is not None:
        updated["display_name"] = identity.display_name

    intent_embedding = None
    intent_changed = False
    if updated.keys() & _INTENT_FIELDS:
        # A partial PUT (e.g. experience_level only) must not drop the other
        # field from the embedding — fall back to the existing row for any
        # intent field absent from this request.
        existing = session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one_or_none()
        old_experience = existing.experience_level if existing else None
        old_description = existing.candidate_description if existing else None
        new_experience = updated.get("experience_level", old_experience)
        new_description = updated.get("candidate_description", old_description)
        experience_changed = new_experience != old_experience
        description_changed = new_description != old_description
        intent_changed = experience_changed or description_changed
        intent_text = _build_intent_text(new_experience, new_description)
        if intent_text:
            embedded = embed([intent_text])
            intent_embedding = embedded[0] if embedded else None
        updated["intent_embedding"] = intent_embedding

    if "commune_codes" in updated and updated["commune_codes"] is None:
        # commune_codes is NOT NULL in the DB — a null-clear over the wire
        # normalizes to "no codes" instead of hitting a DB constraint error.
        updated["commune_codes"] = []

    insert_values = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "email": identity.email,
        "display_name": identity.display_name,
        "rome_codes": {},
        "commune_codes": updated.get("commune_codes") or [],
        "experience_level": updated.get("experience_level"),
        "candidate_description": updated.get("candidate_description"),
        # Only meaningful on the INSERT path (new profile). On conflict, set_
        # only includes intent_embedding when an intent field was in the
        # request body, so an existing row's embedding is never clobbered
        # with this None default.
        "intent_embedding": intent_embedding,
        # Credit keys are never in `updated` (absent from ProfileUpdate), so
        # on_conflict_do_update never touches them for an existing profile.
        "analysis_credits_remaining": 30,
        "analysis_credits_reset_at": None,
        "created_at": now,
    }

    try:
        # rome_codes is intentionally absent from set_ — it is managed exclusively
        # by the GPT-4o-mini CV analysis agent and must never be overwritten here.
        if updated:
            session.execute(
                pg_insert(UserProfile)
                .values(**insert_values)
                .on_conflict_do_update(
                    constraint="uq_user_profiles_user_id",
                    set_=updated,
                )
            )
        else:
            # PUT {} — nothing to change; on_conflict_do_update would receive
            # an empty set_ and fail, so no-op on an existing profile instead.
            session.execute(
                pg_insert(UserProfile)
                .values(**insert_values)
                .on_conflict_do_nothing(constraint="uq_user_profiles_user_id")
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

    # Sent after commit: matching must see the new intent_embedding when it runs.
    if intent_changed:
        # Field values are deliberately not logged — candidate_description is
        # personal data; the boolean flags are enough to trace the dispatch.
        logger.info(
            "profile_intent_changed",
            user_id=user_id,
            experience_changed=experience_changed,
            description_changed=description_changed,
        )
        _dispatch_offer_ready(user_id, now.date().isoformat())

    logger.info("profile_put_completed", user_id=user_id)
    return ProfileOut.model_validate(profile).model_copy(
        update={"is_admin": is_admin(user_id)}
    )


@router.post("/credits/refill", response_model=CreditsRefillOut)
def refill_credits(
    user_id: str = Depends(get_current_admin_user),
    session: Session = Depends(get_db),
) -> CreditsRefillOut:
    """Add ADMIN_CREDITS_REFILL_AMOUNT analysis credits to the admin's own profile.

    Admin-only escape hatch while there is no purchase flow — the welcome
    credits (ADR-018) are otherwise non-renewable. The increment happens in a
    single atomic UPDATE, mirroring the atomic decrement in
    request_match_analysis.

    Args:
        user_id: Authenticated admin user ID (403 for non-admins via dependency).
        session: Active database session.

    Returns:
        CreditsRefillOut with the balance after the refill.

    Raises:
        HTTPException 404: If no profile exists for this user.
    """
    logger.info("credits_refill_started", user_id=user_id)

    try:
        new_balance = session.execute(
            update(UserProfile)
            .where(UserProfile.user_id == user_id)
            .values(
                analysis_credits_remaining=UserProfile.analysis_credits_remaining
                + ADMIN_CREDITS_REFILL_AMOUNT
            )
            .returning(UserProfile.analysis_credits_remaining)
        ).scalar_one_or_none()

        if new_balance is None:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found",
            )

        session.commit()
    except SQLAlchemyError:
        # Base class is intentional — any DB error (connection lost, timeout)
        # should abort the refill and return 500.
        logger.error("credits_refill_failed", user_id=user_id, exc_info=True)
        raise

    logger.info("credits_refill_completed", user_id=user_id, new_balance=new_balance)
    return CreditsRefillOut(analysis_credits_remaining=new_balance)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    """Delete all application data for the authenticated user (right to erasure).

    Deletes every CV owned by the user — DB row, blobs, thumbnails, matches — via
    the same logic as DELETE /cv/{id}, then the user's profile row, in a single
    transaction. Does not revoke the user's Microsoft Entra External ID identity;
    the account can sign up again with a fresh profile. Idempotent: a user with no
    CVs and no profile row still returns 204.
    """
    logger.info("account_delete_started", user_id=user_id)
    cv_index = 0
    try:
        cvs = session.execute(select(CV).where(CV.user_id == user_id)).scalars().all()
        for cv_index, cv in enumerate(cvs):
            # _delete_cv reloads rome_codes per CV rather than batching — fine at
            # today's per-user CV counts, same trade-off as DELETE /cv/{id}.
            _delete_cv(session, cv, user_id)
        session.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
        # Blobs are deleted inside _delete_cv, one CV at a time, before this
        # commit. A mid-loop failure here leaves earlier CVs' blobs gone but
        # their DB rows rolled back — same accepted trade-off as _delete_cv's
        # single-CV case, scaled to up to N CVs (see routers/cv.py).
        session.commit()
        logger.info("account_delete_done", user_id=user_id, cv_count=len(cvs))
    except HTTPException:
        # Raised by _delete_cv when blob storage is unavailable mid-loop — the
        # underlying blob_delete_failed is already logged in _delete_blob, but
        # that log has no user_id/account context, so record it here too.
        # cvs[:cv_index] are the CVs that fully completed _delete_cv (blobs +
        # DB row) before the one at cv_index failed — their blob URLs are
        # gone for good since the DB rows are rolled back with this
        # transaction; logging them here is the only remaining record.
        deleted_blob_urls = [
            url
            for prior_cv in cvs[:cv_index]
            for url in (prior_cv.blob_url, prior_cv.thumbnail_url, prior_cv.thumbnail_url_lg)
            if url
        ]
        logger.error(
            "account_delete_blob_failed",
            user_id=user_id,
            cv_total=len(cvs),
            cv_deleted_before_failure=cv_index,
            deleted_blob_urls=deleted_blob_urls,
            exc_info=True,
        )
        raise
    except SQLAlchemyError:
        logger.error("account_delete_db_failed", user_id=user_id, exc_info=True)
        raise
