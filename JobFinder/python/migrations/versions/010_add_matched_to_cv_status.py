"""Add 'matched' to ck_cvs_status check constraint.

Revision ID: 010
Revises: 009
Create Date: 2026-07-01
"""

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_cvs_status", "cvs")
    op.create_check_constraint(
        "ck_cvs_status",
        "cvs",
        "status IN ('pending', 'processing', 'done', 'matched', 'error')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_cvs_status", "cvs")
    op.create_check_constraint(
        "ck_cvs_status",
        "cvs",
        "status IN ('pending', 'processing', 'done', 'error')",
    )
