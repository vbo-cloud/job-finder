"""Remove unused job_categories and contract_types from user_profiles.

Revision ID: 012
Revises: 011
Create Date: 2026-07-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("user_profiles", "job_categories")
    op.drop_column("user_profiles", "contract_types")


def downgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "job_categories",
            ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "contract_types",
            ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
