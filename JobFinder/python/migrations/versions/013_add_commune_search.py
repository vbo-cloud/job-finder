"""Add commune-based geographic search — offer geo columns and profile commune_codes.

Revision ID: 013
Revises: 012
Create Date: 2026-07-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("commune", sa.String(), nullable=True))
    op.add_column("offers", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("offers", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_index("ix_offers_commune", "offers", ["commune"])
    op.drop_column("user_profiles", "location")
    op.add_column(
        "user_profiles",
        sa.Column(
            "commune_codes",
            ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "commune_codes")
    op.add_column(
        "user_profiles",
        sa.Column("location", sa.String(), nullable=True),
    )
    op.drop_index("ix_offers_commune", table_name="offers")
    op.drop_column("offers", "longitude")
    op.drop_column("offers", "latitude")
    op.drop_column("offers", "commune")
