"""Add cv_analyses table — global CV quality analysis (ATS score, structure, intent coherence).

Revision ID: 017
Revises: 016
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cv_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("cv_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("ats_score", sa.Integer(), nullable=True),
        sa.Column("points_forts", postgresql.JSONB(), nullable=True),
        sa.Column("points_faibles", postgresql.JSONB(), nullable=True),
        sa.Column("suggestions", postgresql.JSONB(), nullable=True),
        sa.Column("coherence_intention", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cv_id"], ["cvs.id"], name="fk_cv_analyses_cv_id_ref_cvs"),
        sa.UniqueConstraint("cv_id", name="uq_cv_analyses_cv_id"),
    )


def downgrade() -> None:
    op.drop_table("cv_analyses")
