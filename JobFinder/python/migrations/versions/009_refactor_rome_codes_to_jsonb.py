"""Refactor rome_codes from ARRAY(String) to JSONB dict.

New format: {"M1805": {"cv_ids": ["uuid1"], "label": "Études et développement informatique"}, ...}
Existing data is discarded (no migration path — treat as blank slate).

Revision ID: 009
Revises: 008
Create Date: 2026-07-01
"""

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE user_profiles SET rome_codes = '{}'")
    op.execute(
        "ALTER TABLE user_profiles "
        "ALTER COLUMN rome_codes TYPE jsonb "
        "USING '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE user_profiles "
        "ALTER COLUMN rome_codes SET DEFAULT '{}'::jsonb"
    )


def downgrade() -> None:
    op.execute("UPDATE user_profiles SET rome_codes = '{}'")
    op.execute(
        "ALTER TABLE user_profiles "
        "ALTER COLUMN rome_codes TYPE text[] "
        "USING '{}'::text[]"
    )
    op.execute(
        "ALTER TABLE user_profiles "
        "ALTER COLUMN rome_codes SET DEFAULT '{}'::text[]"
    )
