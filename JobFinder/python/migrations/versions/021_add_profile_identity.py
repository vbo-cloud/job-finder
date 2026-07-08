"""Add identity claim columns (email, display_name) to user_profiles.

Captured from the validated JWT at profile creation (CV upload) and refreshed
on every profile PUT. They give the operator a human-readable mapping for the
otherwise opaque pairwise user_id (JWT sub claim) — the directory cannot
resolve a sub back to a user, so the application has to record it itself.
Nullable: the claims are only present when the Entra External ID user flow
emits them in the access token.

Revision ID: 021
Revises: 020
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("email", sa.String(), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column("display_name", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "display_name")
    op.drop_column("user_profiles", "email")
