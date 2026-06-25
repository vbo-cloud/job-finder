"""Alter cvs.thumbnail_url to VARCHAR(2048).

Revision ID: 007
Revises: 006
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "cvs",
        "thumbnail_url",
        type_=sa.String(2048),
        existing_type=sa.String(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "cvs",
        "thumbnail_url",
        type_=sa.String(),
        existing_type=sa.String(2048),
        existing_nullable=True,
    )
