"""Enrich match_analyses with coach-style analysis fields (see ADR-018).

Revision ID: 020
Revises: 019
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("match_analyses", sa.Column("verdict", sa.Text(), nullable=True))
    op.add_column("match_analyses", sa.Column("company_summary", sa.Text(), nullable=True))
    op.add_column("match_analyses", sa.Column("mission_summary", sa.Text(), nullable=True))
    op.add_column("match_analyses", sa.Column("why_good_fit_for_user", sa.Text(), nullable=True))
    op.add_column("match_analyses", sa.Column("why_good_candidate", sa.Text(), nullable=True))
    op.add_column("match_analyses", sa.Column("score_explanation", sa.Text(), nullable=True))
    op.add_column(
        "match_analyses",
        sa.Column("questions_entretien_potentielles", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("match_analyses", "questions_entretien_potentielles")
    op.drop_column("match_analyses", "score_explanation")
    op.drop_column("match_analyses", "why_good_candidate")
    op.drop_column("match_analyses", "why_good_fit_for_user")
    op.drop_column("match_analyses", "mission_summary")
    op.drop_column("match_analyses", "company_summary")
    op.drop_column("match_analyses", "verdict")
