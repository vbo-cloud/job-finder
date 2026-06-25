"""Add thumbnail_url to cvs table.

Revision ID: 006
Revises: 005
Create Date: 2026-06-25
"""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cvs", sa.Column("thumbnail_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("cvs", "thumbnail_url")
