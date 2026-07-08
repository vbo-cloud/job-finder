"""Add analysis credit columns to user_profiles.

server_default="30" is intentional: existing beta users retroactively receive the
30 welcome credits too (see ADR-018 — beta-tester welcome gift).

Revision ID: 019
Revises: 018
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "analysis_credits_remaining",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column("analysis_credits_reset_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "analysis_credits_reset_at")
    op.drop_column("user_profiles", "analysis_credits_remaining")
