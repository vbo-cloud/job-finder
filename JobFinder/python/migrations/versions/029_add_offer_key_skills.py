"""Add offers.key_skills column.

Replaces the unreliable France Travail skill badges (offers.skills, raw
"libelle" values, mostly empty or off-target) with a cache of the essential
technologies extracted once per offer by the match_analysis LLM call (see
docs/prompts/prompt-badges-competences-ia.md). NULL means "not yet
extracted" — distinct from an empty list, which means "extracted, no
essential technology identified". Reset to NULL by offer_fetching when
France Travail modifies an already-stored offer (same ft_updated_at-based
mechanism already used to invalidate `embedding`), so the next analysis
re-extracts instead of matching against a stale list.

Revision ID: 029
Revises: 028
Create Date: 2026-07-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "offers",
        sa.Column("key_skills", ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("offers", "key_skills")
