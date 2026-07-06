"""Add offers.region, backfill missed COM department codes and region fallback.

Revision ID: 015
Revises: 014
Create Date: 2026-07-07
"""

import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

# Duplicated from shared/geo.py on purpose — a migration must stay correct
# even if the application-level regex/table changes later. This one also
# covers "98[6-9]" (Wallis-et-Futuna, Polynésie, Nouvelle-Calédonie), added
# after migration 014 shipped without it — rows there still have
# department = NULL for those collectivités and need re-parsing here.
_DEPARTMENT_PREFIX_RE = re.compile(r"^\s*(2[AB]|97[1-8]|98[6-9]|\d{2})\s*-", re.IGNORECASE)

_REGION_NAMES = frozenset({
    "auvergne-rhone-alpes", "bourgogne-franche-comte", "bretagne",
    "centre-val de loire", "corse", "grand est", "hauts-de-france",
    "ile-de-france", "normandie", "nouvelle-aquitaine", "occitanie",
    "pays de la loire", "provence-alpes-cote dazur", "guadeloupe",
    "martinique", "guyane", "la reunion", "mayotte",
})


def _normalize_region(location: str) -> str:
    ascii_only = unicodedata.normalize("NFKD", location).encode("ascii", "ignore").decode()
    return ascii_only.replace("'", "").replace("’", "").strip().lower()


def upgrade() -> None:
    op.add_column("offers", sa.Column("region", sa.String(), nullable=True))
    op.create_index("ix_offers_region", "offers", ["region"])

    bind = op.get_bind()

    # Re-parse department for rows migration 014 missed (98[6-9] wasn't
    # recognized yet) before computing which rows still need a region.
    dept_rows = bind.execute(
        sa.text("SELECT id, location FROM offers WHERE department IS NULL")
    ).fetchall()
    dept_updates = []
    for row in dept_rows:
        match = _DEPARTMENT_PREFIX_RE.match(row.location or "")
        if match:
            dept_updates.append({"id": row.id, "department": match.group(1).upper()})
    if dept_updates:
        bind.execute(
            sa.text("UPDATE offers SET department = :department WHERE id = :id"),
            dept_updates,
        )

    region_rows = bind.execute(
        sa.text(
            "SELECT id, location FROM offers WHERE commune IS NULL AND department IS NULL"
        )
    ).fetchall()
    region_updates = []
    for row in region_rows:
        normalized = _normalize_region(row.location or "")
        if normalized in _REGION_NAMES:
            region_updates.append({"id": row.id, "region": normalized})
    if region_updates:
        bind.execute(
            sa.text("UPDATE offers SET region = :region WHERE id = :id"),
            region_updates,
        )


def downgrade() -> None:
    op.drop_index("ix_offers_region", table_name="offers")
    op.drop_column("offers", "region")
