"""Add synthese column to cv_analyses.

Prose overview paragraph (3-5 sentences, coach tone) written by the CV
quality analysis agent — the overall impression the CV gives a recruiter,
displayed above the points lists in the UI. Nullable: rows analysed before
this feature have no synthese.

Revision ID: 022
Revises: 021
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cv_analyses",
        sa.Column("synthese", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cv_analyses", "synthese")
