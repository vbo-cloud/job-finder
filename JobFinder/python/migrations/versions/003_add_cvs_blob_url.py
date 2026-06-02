"""Add blob_url to cvs table.

Revision ID: 003
Revises: 002
Create Date: 2026-06-02
"""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cvs", sa.Column("blob_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("cvs", "blob_url")
