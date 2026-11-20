"""Add notification_days to user_profiles — day-of-week email digest preference.

ISO 8601 weekday integers (1=lundi ... 7=dimanche), matching Python's datetime.isoweekday() —
the future notification agent (PR 6/6 of the notifications plan) compares today's isoweekday()
directly against this array, no day-name mapping needed. server_default="{7}" backfills
existing rows to "dimanche uniquement", the product default agreed with Vincent.

ck_user_profiles_notification_days constrains every element to 1-7 at the schema level, on top
of the API-layer Literal[1..7] validation (ProfileUpdate) — same defense-in-depth pattern as
ck_cvs_status (migration 010).

Revision ID: 033
Revises: 032
Create Date: 2026-07-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "notification_days",
            ARRAY(sa.SmallInteger()),
            nullable=False,
            server_default="{7}",
        ),
    )
    # Schema-level backstop matching ck_cvs_status (migration 010): the API layer
    # already restricts values to 1-7 (ProfileUpdate's Literal[1..7]), but nothing
    # else guarantees that for a direct DB write.
    op.create_check_constraint(
        "ck_user_profiles_notification_days",
        "user_profiles",
        "notification_days <@ ARRAY[1,2,3,4,5,6,7]::smallint[]",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_profiles_notification_days", "user_profiles")
    op.drop_column("user_profiles", "notification_days")
