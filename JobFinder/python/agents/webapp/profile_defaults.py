"""Default values for a newly created UserProfile row — shared by upload_cv and
put_profile, the two endpoints that lazily create a profile on first
authenticated write (see docs/JOURNAL.md — there is no dedicated user-creation
step in this backend, identity lives entirely in Entra External ID)."""

import uuid
from datetime import datetime, timezone

from auth import UserIdentity


def default_profile_values(identity: UserIdentity) -> dict:
    """Return the base column values for a brand-new UserProfile row.

    Callers merge request-specific overrides (commune_codes, experience_level,
    candidate_description, intent_embedding, ...) on top of this dict before
    passing it to pg_insert(...).values(**defaults, **overrides). rome_codes is
    always {} here — it is managed exclusively by the cv_analysis agent and must
    never be set from a webapp request. email/display_name are the best-effort
    identity claims captured at creation (PR #170); PUT /profile refreshes them
    afterwards.

    Args:
        identity: Authenticated identity claims from the validated JWT.

    Returns:
        dict with keys id, user_id, email, display_name, rome_codes,
        analysis_credits_remaining, analysis_credits_reset_at, created_at.
    """
    return {
        "id": uuid.uuid4(),
        "user_id": identity.user_id,
        "email": identity.email,
        "display_name": identity.display_name,
        "rome_codes": {},
        "analysis_credits_remaining": 30,
        "analysis_credits_reset_at": None,
        "created_at": datetime.now(timezone.utc),
    }
