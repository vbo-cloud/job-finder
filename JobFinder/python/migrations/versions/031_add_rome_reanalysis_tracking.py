"""Add description_updated_at (user_profiles) and rome_analyzed_at (cvs).

Support columns for a manual "reanalyze ROME codes" action, shown only when the profile's
candidate_description has changed more recently than a given CV's last ROME extraction — see
docs/prompts/prompt-cv-analysis-rome-reanalysis-button.md.

description_updated_at is set only in PUT /profile, only when candidate_description itself
changes (not on every profile write) — distinct from user_profiles.updated_at, which
_merge_rome_codes also touches on every CV analysis and is therefore unusable as a "did the
description change" signal.

rome_analyzed_at is set by cv_analysis whenever ROME extraction actually completes for a CV —
both on the normal upload path and on the new retry_rome_only path.

No backfill: both columns start at NULL for every existing profile/CV, which naturally disables
the button for everyone until their first candidate_description change after this deploy —
correct by construction, nothing to reconstruct.

Revision ID: 031
Revises: 030
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("description_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cvs",
        sa.Column("rome_analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cvs", "rome_analyzed_at")
    op.drop_column("user_profiles", "description_updated_at")
