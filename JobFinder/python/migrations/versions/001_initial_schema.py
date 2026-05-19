"""Initial schema — create offers, cvs, and matches tables.

Revision ID: 001
Revises: -
Create Date: 2026-05-19
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ft_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("contract_type", sa.String(), nullable=False),
        sa.Column("salary", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("skills", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ft_id", name="uq_offers_ft_id"),
    )

    op.create_table(
        "cvs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("cv_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cv_id"], ["cvs.id"], name="fk_matches_cv_id_ref_cvs"),
        sa.ForeignKeyConstraint(
            ["offer_id"], ["offers.id"], name="fk_matches_offer_id_ref_offers"
        ),
    )


def downgrade() -> None:
    op.drop_table("matches")
    op.drop_table("cvs")
    op.drop_table("offers")
