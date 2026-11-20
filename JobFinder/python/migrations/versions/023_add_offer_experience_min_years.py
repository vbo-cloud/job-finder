"""Add experience_min_years column to offers.

Minimum required years of experience parsed from France Travail's
experienceLibelle field, used by the matching agent to apply a progressive
score penalty when an offer demands more experience than the candidate's
declared level. Nullable: absence of data is never treated as a requirement.

Revision ID: 023
Revises: 022
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "offers",
        sa.Column("experience_min_years", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("offers", "experience_min_years")
