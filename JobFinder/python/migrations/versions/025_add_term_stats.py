"""Add term_stats table — corpus-wide term document frequencies.

Document frequency of every lexeme (after French stemming) across all offer
descriptions, fully recomputed at the end of each offer_fetching run via
Postgres ts_stat(). The matching agent weights shared CV/offer terms by
rarity (1 - doc_frequency / total_offers) and excludes near-universal terms
above TERM_STOPWORD_THRESHOLD — sector-agnostic replacement for the fixed
tech_keywords list. total_offers is stored alongside so the ratio can be
recomputed exactly from the snapshot the frequencies were derived from.

Revision ID: 025
Revises: 024
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "term_stats",
        sa.Column("term", sa.Text(), primary_key=True),
        sa.Column("doc_frequency", sa.Integer(), nullable=False),
        sa.Column("total_offers", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("term_stats")
