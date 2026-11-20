"""Add thumbnail_url_lg to cvs table.

Revision ID: 011
Revises: 010
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cvs", sa.Column("thumbnail_url_lg", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("cvs", "thumbnail_url_lg")
