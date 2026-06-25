"""Add status and name to cvs table.

Revision ID: 005
Revises: 004
Create Date: 2026-06-25
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cvs", sa.Column("name", sa.String(), nullable=True))
    op.add_column(
        "cvs",
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
    )


def downgrade() -> None:
    op.drop_column("cvs", "status")
    op.drop_column("cvs", "name")
