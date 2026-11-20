"""Add more_credits_requested_at (user_profiles).

Support column for the "I'd like more credits" signal button, shown only when a user is
at 0 analysis credits — see docs/prompts/prompt-credits-signals-and-request-more.md.
Stamped by POST /credits/request-more only after a successful alert email send — never
on a deduplicated call (cooldown still running) nor on a failed ACS send, so a failed
send can never silently start the cooldown and block the user's next retry (see PR #254
in docs/JOURNAL.md).

No backfill: the column starts at NULL for every existing profile, which correctly means
"never requested" for everyone until their first request after this deploy — correct by
construction, same rationale as migration 031/034.

No index: only ever read as a full-row comparison in application code (POST
/credits/request-more, on a profile row already fetched by primary key) to enforce the
cooldown — never filtered or joined on in SQL.

Revision ID: 035
Revises: 034
Create Date: 2026-07-27
"""

import sqlalchemy as sa
from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("more_credits_requested_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "more_credits_requested_at")
