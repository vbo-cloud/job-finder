"""Add partial index on matches (cv_id) WHERE seen_at IS NULL.

Revision ID: 008
Revises: 007
Create Date: 2026-06-30
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_matches_cv_id_unseen",
        "matches",
        ["cv_id"],
        postgresql_where="seen_at IS NULL",
    )


def downgrade() -> None:
    op.drop_index("ix_matches_cv_id_unseen", table_name="matches")
