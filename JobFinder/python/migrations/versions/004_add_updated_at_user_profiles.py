"""Add updated_at to user_profiles.

Revision ID: 004
Revises: 003
Create Date: 2026-06-03
"""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "updated_at")
