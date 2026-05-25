"""Add user_profiles table and rome_code column on offers.

Revision ID: 002
Revises: 001
Create Date: 2026-05-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("rome_codes", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("job_categories", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("contract_types", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])

    op.add_column("offers", sa.Column("rome_code", sa.String(), nullable=True))
    op.create_index("ix_offers_rome_code", "offers", ["rome_code"])
    op.add_column(
        "offers",
        sa.Column("ft_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("offers", "ft_updated_at")
    op.drop_index("ix_offers_rome_code", table_name="offers")
    op.drop_column("offers", "rome_code")
    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")
