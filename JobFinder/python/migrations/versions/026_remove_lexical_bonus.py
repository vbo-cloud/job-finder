"""Remove lexical bonus mechanisms: tech_keywords columns and term_stats table.

Drops what migrations 024 (tech_keywords) and 025 (term_stats) added. Both
fed additive lexical bonuses in the matching score that were removed
entirely — see docs/prompts/prompt-matching-remove-lexical-bonus.md. Neither
column/table is read by any remaining code after this migration.

Revision ID: 026
Revises: 025
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("cvs", "tech_keywords")
    op.drop_column("offers", "tech_keywords")
    op.drop_table("term_stats")


def downgrade() -> None:
    # Recreates schema only — no data restored, expected for a rollback of a removal.
    op.add_column(
        "offers",
        sa.Column("tech_keywords", ARRAY(sa.String()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "cvs",
        sa.Column("tech_keywords", ARRAY(sa.String()), nullable=False, server_default="{}"),
    )
    op.create_table(
        "term_stats",
        sa.Column("term", sa.Text(), primary_key=True),
        sa.Column("doc_frequency", sa.Integer(), nullable=False),
        sa.Column("total_offers", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
