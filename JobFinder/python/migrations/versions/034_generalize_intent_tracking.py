"""Rename description_updated_at to intent_updated_at, add last_intent_dispatch_at.

One logical change: generalizing intent-change tracking on user_profiles from
"description changed" to "experience_level or candidate_description changed" (see
docs/prompts/prompt-intent-driven-reanalysis.md).

intent_updated_at (renamed from description_updated_at, migration 031) is now stamped
on either intent field changing, not candidate_description alone — match_analysis's own
prompt context (agents/match_analysis/main.py's _build_intent_text) renders both fields,
so an experience_level-only change makes existing match analyses stale too, not just
ROME reanalysis.

last_intent_dispatch_at is new: throttles the start-matching + CV reanalysis dispatch
that PUT /profile fires on intent change (INTENT_DISPATCH_COOLDOWN_SECONDS,
shared/config.py) — independent of intent_updated_at, which always stamps regardless of
whether that dispatch was itself throttled.

No backfill for last_intent_dispatch_at (NULL = "never dispatched", correct by
construction — same no-backfill rationale as migration 031). Renaming
description_updated_at preserves existing values: a plain column rename, not a
drop+add, so no reset of what has already been tracked for existing profiles.

No index on either column — same rationale as migration 031: both are only ever read as
a full-row comparison in application code (PUT /profile, GET /matches, on a profile row
already fetched by primary key), never filtered or joined on in SQL.

Revision ID: 034
Revises: 033
Create Date: 2026-07-26
"""

import sqlalchemy as sa
from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "user_profiles",
        "description_updated_at",
        new_column_name="intent_updated_at",
        existing_type=sa.DateTime(timezone=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column("last_intent_dispatch_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "last_intent_dispatch_at")
    op.alter_column(
        "user_profiles",
        "intent_updated_at",
        new_column_name="description_updated_at",
        existing_type=sa.DateTime(timezone=True),
    )
