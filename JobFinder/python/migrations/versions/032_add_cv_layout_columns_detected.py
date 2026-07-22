"""Add layout_columns_detected (cvs).

Support column for column-aware PDF text extraction — see
docs/prompts/prompt-cv-analysis-referentiel-model-upgrade-column-parsing.md. Upload-time PDF
parsing (routers/cv.py) now detects a two-column layout (sidebar + main block) and reconstitutes
raw_text in reading order per column instead of interleaving both blocks; this column stores how
many columns were detected so cv_analysis's quality prompt can warn about ATS risk from the
layout itself without inventing content-organization defects from what is now a clean text
extraction.

NULL = not yet computed (every CV uploaded before this deploy) — never interpreted as "1 column
detected". No backfill: the value becomes available again on that CV's next re-analysis: a
one-time backfill would require re-parsing every existing CV's stored PDF blob just to populate a
value only consumed as an ATS-risk hint, not worth the write cost for existing rows that already
completed their one-time analysis.

1 = single column (dominant case). 2 = two columns detected — the only multi-column case this
extraction handles; 3+ column or grid layouts fall back to the single-column path and are
reported as 1, not as a wrong guess.

No index: read only as a full-row value on a CV already fetched by primary key (see
_get_cv_text), same rationale as rome_analyzed_at in migration 031.

Revision ID: 032
Revises: 031
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cvs",
        sa.Column("layout_columns_detected", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cvs", "layout_columns_detected")
