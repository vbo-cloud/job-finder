"""Add offers.distilled_skills column.

Persists the plain-text output of the LLM distillation step (skills,
technologies, methodologies and missions extracted from the offer
description before embedding — see agents/offer_distillation/main.py) for
debuggability: without this column, what the LLM actually extracted could
only be re-derived from the resulting embedding/scores, as had to be done
during the manual diagnostic that preceded this pipeline
(docs/prompts/prompt-matching-llm-distillation-manual-test.md). NULL for
offers ingested before this pipeline existed, and transiently NULL for any
offer whose distillation hasn't run yet.

Revision ID: 027
Revises: 026
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "offers",
        sa.Column("distilled_skills", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("offers", "distilled_skills")
