"""Add experience_level, candidate_description and intent_embedding to user_profiles.

Revision ID: 016
Revises: 015
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("experience_level", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("candidate_description", sa.Text(), nullable=True))
    op.add_column("user_profiles", sa.Column("intent_embedding", Vector(1536), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "intent_embedding")
    op.drop_column("user_profiles", "candidate_description")
    op.drop_column("user_profiles", "experience_level")
