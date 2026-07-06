"""Add offers.department — column, index, and backfill for existing NULL-commune rows.

Revision ID: 014
Revises: 013
Create Date: 2026-07-06
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

# Duplicated from shared/geo.py on purpose — a migration must stay correct
# even if the application-level regex changes later.
_DEPARTMENT_PREFIX_RE = re.compile(r"^\s*(2[AB]|97[1-8]|\d{2})\s*-", re.IGNORECASE)


def upgrade() -> None:
    op.add_column("offers", sa.Column("department", sa.String(), nullable=True))
    op.create_index("ix_offers_department", "offers", ["department"])

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, location FROM offers WHERE commune IS NULL")
    ).fetchall()

    updates = []
    for row in rows:
        match = _DEPARTMENT_PREFIX_RE.match(row.location or "")
        if match:
            updates.append({"id": row.id, "department": match.group(1).upper()})

    if updates:
        bind.execute(
            sa.text("UPDATE offers SET department = :department WHERE id = :id"),
            updates,
        )


def downgrade() -> None:
    op.drop_index("ix_offers_department", table_name="offers")
    op.drop_column("offers", "department")
