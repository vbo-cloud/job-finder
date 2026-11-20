"""Add offer_fetch_signals and offer_fetch_pending_codes coordination tables.

Support tables for offer_fetching's move from a purely timer-triggered job to an
event-driven one (see docs/prompts/prompt-offer-fetching-event-driven-and-new-code-fetch.md).
A session-level Postgres advisory lock (OFFER_FETCH_LOCK_ID, agents/offer_fetching/main.py)
now serializes fetch cycles that used to be guaranteed non-overlapping simply by running on a
fixed 12h/20h schedule. These two tables let a cycle that arrives while another is already
running record what it needed instead of being silently dropped:

- offer_fetch_signals: single fixed row, full_refresh_pending set true when a scheduled
  (full active-codes) trigger arrives while busy. Looked up and updated via the natural
  singleton_key = 1 column, not the surrogate id.
- offer_fetch_pending_codes: one row per ROME code requested by a targeted (new-code) trigger
  that arrived while busy — drained (and cleared) by the running cycle before it releases the
  lock, so a CV's newly-merged ROME code is never silently skipped even under contention.

Both tables use a UUID v4 primary key, per conventions-sql's standard rule — an earlier draft
of this migration gave them non-UUID primary keys instead (offer_fetch_signals keyed on a fixed
id=1, offer_fetch_pending_codes keyed on rome_code itself), reasoning this was close enough to
conventions-sql's cache/stats-table exception (term_stats.term). reviewer-infra correctly
rejected that: the exception is explicitly scoped to a table "recomputed and replaced wholesale
each cycle, no ON CONFLICT" — offer_fetch_pending_codes is the opposite (incrementally
deduplicated via ON CONFLICT DO NOTHING on rome_code), and offer_fetch_signals's row is updated
in place, never replaced, so neither literally qualifies. The codebase already has an
established pattern for "identified and deduplicated by a natural key, but still needs a
regular primary key": a UUID id plus a separate UniqueConstraint on the natural key (see
Offer.id / offers.uq_offers_ft_id, on_conflict_do_update(constraint="uq_offers_ft_id") in
agents/offer_fetching/main.py). Both tables here now follow that same pattern instead:
offer_fetch_pending_codes keeps rome_code's uniqueness via uq_offer_fetch_pending_codes_rome_code
(ON CONFLICT DO NOTHING still targets that constraint, unchanged); offer_fetch_signals keeps its
single-row guarantee via a singleton_key column (UniqueConstraint + CHECK singleton_key = 1)
instead of the primary key itself. The one seed row's id value is otherwise never read or
compared against — a fixed literal is used only because some id must be inserted, not because
it carries meaning. Both tables also gained a NOT NULL created_at column, per conventions-sql's
unconditional "every table has created_at" rule (independent of the primary-key exception) --
term_stats, the exception's own reference example, keeps one despite its natural-key PK.

Revision ID: 030
Revises: 029
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None

# Arbitrary, never read back or compared against — the seed row is always looked up via
# singleton_key = 1, never via id. Only needed because the column is NOT NULL.
_OFFER_FETCH_SIGNALS_SEED_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "offer_fetch_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton_key", sa.SmallInteger(), nullable=False),
        sa.Column("full_refresh_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("singleton_key", name="uq_offer_fetch_signals_singleton_key"),
        sa.CheckConstraint("singleton_key = 1", name="ck_offer_fetch_signals_single_row"),
    )
    op.execute(
        f"INSERT INTO offer_fetch_signals (id, singleton_key, full_refresh_pending, created_at) "
        f"VALUES ('{_OFFER_FETCH_SIGNALS_SEED_ID}', 1, false, now())"
    )

    op.create_table(
        "offer_fetch_pending_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rome_code", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rome_code", name="uq_offer_fetch_pending_codes_rome_code"),
    )


def downgrade() -> None:
    op.drop_table("offer_fetch_pending_codes")
    op.drop_table("offer_fetch_signals")
