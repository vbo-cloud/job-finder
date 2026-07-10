"""Remove offers.distilled_skills column.

Drops what migration 027 added. The LLM distillation step it stored the
output of has been removed entirely — offers are now embedded directly on
their raw title+description text (see agents/offer_fetching/main.py) — see
docs/prompts/prompt-remove-offer-distillation.md. No remaining code reads
this column after this migration.

Revision ID: 028
Revises: 027
Create Date: 2026-07-10
"""

import sqlalchemy as sa
from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("offers", "distilled_skills")


def downgrade() -> None:
    # Recreates schema only — no data restored, same convention as migration 026.
    op.add_column("offers", sa.Column("distilled_skills", sa.Text(), nullable=True))
