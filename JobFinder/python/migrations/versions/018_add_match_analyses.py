"""Add match_analyses table — GPT-4o-mini analysis per CV<->offer pair (see ADR-018).

Revision ID: 018
Revises: 017
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("points_forts", postgresql.JSONB(), nullable=True),
        sa.Column("points_amelioration", postgresql.JSONB(), nullable=True),
        sa.Column(
            "matched_skills",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("synthese", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name="fk_match_analyses_match_id_ref_matches"
        ),
        sa.UniqueConstraint("match_id", name="uq_match_analyses_match_id"),
    )


def downgrade() -> None:
    op.drop_table("match_analyses")
