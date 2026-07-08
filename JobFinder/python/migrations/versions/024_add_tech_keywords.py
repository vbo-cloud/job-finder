"""Add tech_keywords columns to offers and cvs.

Lexical tech-keyword lists extracted at offer ingestion and CV upload
(shared/tech_keywords.py — no LLM call), used by the matching agent as a
strictly additive score bonus when CV and offer share precise technical
keywords. server_default '{}': existing rows start with no detected
keywords, which simply yields a null bonus.

Revision ID: 024
Revises: 023
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "offers",
        sa.Column("tech_keywords", ARRAY(sa.String()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "cvs",
        sa.Column("tech_keywords", ARRAY(sa.String()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("cvs", "tech_keywords")
    op.drop_column("offers", "tech_keywords")
