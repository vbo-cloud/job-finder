"""Profile endpoints — read and upsert the authenticated user's job search preferences."""

from datetime import datetime, timezone

import structlog
from azure.servicebus.exceptions import ServiceBusError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.bus import send_message
from shared.config import INTENT_DISPATCH_COOLDOWN_SECONDS
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
from profile_defaults import default_profile_values
from routers.cv import _delete_cv
from schemas import CreditsRefillOut, ProfileOut, ProfileUpdate

START_MATCHING_QUEUE = "start-matching"
CV_ANALYSIS_QUEUE = "cv-analysis"
ADMIN_CREDITS_REFILL_AMOUNT = 10
_INTENT_FIELDS = {"experience_level", "candidate_description"}

router = APIRouter(prefix="/profile", tags=["profile"])
logger = structlog.get_logger()


def _build_intent_text(candidate_description: str | None) -> str:
    """Return the text embedded as intent_embedding — candidate_description only.

    experience_level never contributes here; it only feeds the numeric
    experience malus in matching (see put_profile, agents/matching/main.py).
    """
    if candidate_description and candidate_description.strip():
        return candidate_description.strip()
    return ""


def _dispatch_start_matching(user_id: str, run_date: str) -> None:
    """Send a start-matching message so the matching agent re-scores existing offers.

    Fire-and-forget: a Service Bus failure is logged but never fails the request —
    the profile is already committed and the next scheduled matching run will pick
    up the new intent_embedding anyway.

    Args:
        user_id: Authenticated user ID, for log correlation only.
        run_date: ISO date (YYYY-MM-DD) stamped on the message.
    """
    try:
        send_message(
            START_MATCHING_QUEUE,
            {
                "run_date": run_date,
                "rome_codes": [],
                "new_offers_count": 0,
                "embedded_count": 0,
                "trigger": "profile_update",
            },
        )
        logger.info("profile_put_start_matching_sent", user_id=user_id)
    except ServiceBusError:
        logger.error("profile_put_start_matching_failed", user_id=user_id, exc_info=True)


def _dispatch_cv_reanalysis(session: Session, user_id: str) -> None:
    """Re-trigger the full CV analysis pipeline (ROME + quality) for every CV of the user.

    No retry_rome_only/retry_quality_only flag: the consumer's default branch
    (agents/cv_analysis/main.py's _handle_new_cv_analysis) already re-runs both together,
    same as at upload time — which means it also flips CV.status back through
    "processing"/"done" before matching completes, same as a fresh upload. A CV that was
    "matched" therefore visibly leaves that state for the duration of the reanalysis (the
    library badge and CVDetailSection's analysis panel briefly show "in progress" again) —
    an accepted trade-off of reusing the upload path rather than a narrower ROME-only
    re-dispatch. Free and automatic — naturally bounded by the user's own CV count, gated
    by the same cooldown as _dispatch_start_matching (see put_profile), no separate charge.

    Fire-and-forget per CV, same trade-off as _dispatch_start_matching: a Service Bus
    failure for one CV is logged but never fails the request nor blocks the remaining CVs.

    Args:
        session: Active database session.
        user_id: Owner of the CVs to re-dispatch.
    """
    logger.info("profile_put_cv_reanalysis_started", user_id=user_id)
    try:
        cv_ids = session.execute(select(CV.id).where(CV.user_id == user_id)).scalars().all()
    except SQLAlchemyError:
        # Best-effort, same as _backfill_cv_analysis (routers/cv.py): called after the
        # profile's own commit already succeeded — a failure reading the CV list here
        # must not turn an already-successful PUT /profile into a 500.
        logger.error("profile_put_cv_reanalysis_lookup_failed", user_id=user_id, exc_info=True)
        return
    for cv_id in cv_ids:
        try:
            send_message(CV_ANALYSIS_QUEUE, {"cv_id": str(cv_id)})
            logger.info("profile_put_cv_reanalysis_sent", user_id=user_id, cv_id=str(cv_id))
        except ServiceBusError:
            logger.error(
                "profile_put_cv_reanalysis_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True
            )


def _resolve_intent_change(
    session: Session, user_id: str, updated: dict, now: datetime
) -> tuple[bool, bool, bool, bool, list[float] | None]:
    """Compute whether the user's intent changed on this PUT, and gate the resulting dispatch.

    Mutates `updated` in place — adds intent_embedding when candidate_description changed,
    and intent_updated_at/last_intent_dispatch_at when intent_changed — so put_profile's
    upsert set_/insert_values see exactly the same partial-update shape either way.

    A partial PUT (e.g. experience_level only) must not drop the other field from the
    embedding — falls back to the existing row for any intent field absent from `updated`.

    Args:
        session: Active database session.
        user_id: Authenticated user ID.
        updated: The partial-update dict being built by put_profile — mutated in place.
        now: Timestamp to stamp on intent_updated_at/last_intent_dispatch_at.

    Returns:
        (intent_changed, description_changed, experience_changed, dispatch_allowed,
        intent_embedding).
    """
    intent_embedding = None
    intent_changed = False
    description_changed = False
    experience_changed = False
    dispatch_allowed = False
    if not (updated.keys() & _INTENT_FIELDS):
        return intent_changed, description_changed, experience_changed, dispatch_allowed, intent_embedding

    logger.info("profile_put_intent_resolution_started", user_id=user_id)
    try:
        existing = session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        # Base class is intentional — any DB error (connection lost, timeout) should
        # abort the PUT and return 500, same as every other DB read in this file.
        logger.error("profile_put_intent_resolution_failed", user_id=user_id, exc_info=True)
        raise
    old_experience = existing.experience_level if existing else None
    old_description = existing.candidate_description if existing else None
    new_experience = updated.get("experience_level", old_experience)
    new_description = updated.get("candidate_description", old_description)
    experience_changed = new_experience != old_experience
    description_changed = new_description != old_description
    intent_changed = experience_changed or description_changed
    # experience_level only feeds the matching malus, never the embedding —
    # recomputing intent_embedding when only it changed would overwrite a
    # correctly-stored value with the same text, wastefully re-embedding it.
    if description_changed:
        intent_text = _build_intent_text(new_description)
        if intent_text:
            embedded = embed([intent_text])
            intent_embedding = embedded[0] if embedded else None
        updated["intent_embedding"] = intent_embedding
    if intent_changed:
        updated["intent_updated_at"] = now
        last_dispatch = existing.last_intent_dispatch_at if existing else None
        dispatch_allowed = (
            last_dispatch is None
            or (now - last_dispatch).total_seconds() >= INTENT_DISPATCH_COOLDOWN_SECONDS
        )
        if dispatch_allowed:
            updated["last_intent_dispatch_at"] = now

    return intent_changed, description_changed, experience_changed, dispatch_allowed, intent_embedding


def _upsert_profile(
    session: Session,
    user_id: str,
    identity: UserIdentity,
    updated: dict,
    intent_embedding: list[float] | None,
    intent_changed: bool,
    dispatch_allowed: bool,
    now: datetime,
) -> UserProfile:
    """Upsert the profile row for put_profile and return its state after commit.

    Defaults (id, identity claims, rome_codes, credits, created_at) are only meaningful
    on the INSERT path: on conflict, set_ only contains `updated`, so an existing row's
    credits or embedding are never clobbered by them.

    Args:
        session: Active database session.
        user_id: Authenticated user ID.
        identity: Authenticated identity claims, for the INSERT-path defaults.
        updated: ON CONFLICT DO UPDATE set_ clause, already normalized by put_profile.
        intent_embedding: Recomputed embedding, or None if unchanged/cleared.
        intent_changed: Whether experience_level or candidate_description changed.
        dispatch_allowed: Whether the intent-change dispatch cooldown allows a dispatch.
        now: Timestamp for intent_updated_at/last_intent_dispatch_at on the INSERT path.

    Returns:
        The profile row as committed.

    Raises:
        SQLAlchemyError: On any database error — the caller returns 500.
    """
    insert_values = {
        **default_profile_values(identity),
        "commune_codes": updated.get("commune_codes") or [],
        # Deliberately not `updated.get("notification_days") or []`: that would
        # collapse "key absent" (new profile, keep the [7] default) into the
        # same case as "key present with []" (explicit opt-out), clobbering the
        # default on any PUT that doesn't mention notification_days.
        "notification_days": updated.get("notification_days", [7]),
        "experience_level": updated.get("experience_level"),
        "candidate_description": updated.get("candidate_description"),
        "intent_embedding": intent_embedding,
        "intent_updated_at": now if intent_changed else None,
        "last_intent_dispatch_at": now if dispatch_allowed else None,
    }
    logger.info("profile_put_upsert_started", user_id=user_id)
    try:
        # rome_codes is intentionally absent from set_ — it is managed exclusively
        # by the GPT-4o-mini CV analysis agent and must never be overwritten here.
        if updated:
            session.execute(
                pg_insert(UserProfile)
                .values(**insert_values)
                .on_conflict_do_update(constraint="uq_user_profiles_user_id", set_=updated)
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
        return session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one()
    except SQLAlchemyError:
        # Base class is intentional — any DB error (connection lost, constraint
        # violation, timeout) should abort the upsert and return 500.
        logger.error("profile_put_failed", user_id=user_id, exc_info=True)
        raise


def _dispatch_intent_change(
    session: Session,
    user_id: str,
    now: datetime,
    intent_changed: bool,
    description_changed: bool,
    experience_changed: bool,
    dispatch_allowed: bool,
) -> None:
    """Log and fire the post-commit start-matching/CV-reanalysis dispatch, if any.

    No-op if intent_changed is False. Sent after commit — matching must see the new
    intent_embedding when it runs.

    Args:
        session: Active database session, for _dispatch_cv_reanalysis's CV lookup.
        user_id: Authenticated user ID.
        now: Timestamp for the start-matching message's run_date.
        intent_changed: Whether experience_level or candidate_description changed.
        description_changed: Whether candidate_description specifically changed — logged only.
        experience_changed: Whether experience_level specifically changed — logged only.
        dispatch_allowed: Whether the cooldown allows dispatching now.
    """
    if not intent_changed:
        return
    # Field values are deliberately not logged — candidate_description is
    # personal data; the boolean flags are enough to trace the dispatch.
    logger.info(
        "profile_intent_changed",
        user_id=user_id,
        experience_changed=experience_changed,
        description_changed=description_changed,
        dispatch_allowed=dispatch_allowed,
    )
    if dispatch_allowed:
        _dispatch_start_matching(user_id, now.date().isoformat())
        _dispatch_cv_reanalysis(session, user_id)
    else:
        # Cooldown still running — the profile is already saved above and
        # intent_updated_at already stamped; only the recompute itself is
        # delayed to the next out-of-cooldown save (see put_profile docstring).
        logger.info("profile_put_dispatch_throttled", user_id=user_id)


@router.get("", response_model=ProfileOut)
def get_profile(
    identity: UserIdentity = Depends(get_current_identity),
    session: Session = Depends(get_db),
) -> ProfileOut:
    """Return the job search profile for the authenticated user.

    Creates the profile with default values (including the 30 welcome analysis
    credits) if this is the user's first authenticated interaction with the app —
    a user can reach this endpoint before ever uploading a CV or calling
    PUT /profile, and must still see their credits rather than an error.

    Never returns 404: any user with a valid token has an accessible profile
    after this call.

    Args:
        identity: Authenticated identity claims from the JWT (sub, email, name).
        session: Active database session.

    Returns:
        ProfileOut with the user's current job search preferences — freshly
        created with defaults if this is their first visit.
    """
    user_id = identity.user_id
    logger.info("profile_get_started", user_id=user_id)

    try:
        profile = session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one_or_none()

        if profile is None:
            logger.info("profile_get_creating_default", user_id=user_id)
            session.execute(
                pg_insert(UserProfile)
                .values(**default_profile_values(identity), commune_codes=[])
                .on_conflict_do_nothing(constraint="uq_user_profiles_user_id")
            )
            session.commit()
            # scalar_one (not _or_none) is deliberate: after the upsert + commit
            # the row necessarily exists — either just created, or created by a
            # concurrent request (on_conflict_do_nothing makes that race safe).
            profile = session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            ).scalar_one()
    except SQLAlchemyError:
        # Base class is intentional — any DB error (connection lost, timeout)
        # should abort the response and return 500.
        logger.error("profile_get_failed", user_id=user_id, exc_info=True)
        raise

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

    intent_embedding reflects candidate_description only — experience_level
    never contributes to it, it only feeds the numeric experience malus in
    matching. Recomputing intent_embedding therefore only happens when
    candidate_description actually changes; a change to experience_level alone
    leaves the stored embedding untouched.

    When experience_level or candidate_description actually changes,
    intent_updated_at is stamped unconditionally (used by GET /matches to flag
    existing match analyses as stale — see routers/matches.py) and a
    start-matching message plus a full CV reanalysis (ROME + quality, every CV
    owned by the user) are dispatched after commit, so matching and CV data
    both catch up with the new intent. The malus depends on experience_level,
    so its change alone must still trigger a rescore even though the
    embedding itself is untouched.

    The dispatch (start-matching + CV reanalysis) is throttled by
    INTENT_DISPATCH_COOLDOWN_SECONDS per user — a user who spams profile edits
    must never trigger an unbounded volume of free AI calls. intent_updated_at
    itself is NOT throttled: it always reflects the latest saved intent, even
    on a PUT whose dispatch was skipped by the cooldown, so a stale-analysis
    badge (GET /matches) is never missed just because the recompute itself was
    delayed to the next out-of-cooldown save.

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

    intent_changed, description_changed, experience_changed, dispatch_allowed, intent_embedding = (
        _resolve_intent_change(session, user_id, updated, now)
    )

    if "commune_codes" in updated and updated["commune_codes"] is None:
        # commune_codes is NOT NULL in the DB — a null-clear over the wire
        # normalizes to "no codes" instead of hitting a DB constraint error.
        updated["commune_codes"] = []
    if "notification_days" in updated and updated["notification_days"] is None:
        # notification_days is NOT NULL in the DB — same null-clear normalization
        # as commune_codes above.
        updated["notification_days"] = []

    profile = _upsert_profile(
        session, user_id, identity, updated, intent_embedding, intent_changed, dispatch_allowed, now
    )
    _dispatch_intent_change(
        session, user_id, now, intent_changed, description_changed, experience_changed, dispatch_allowed
    )

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
