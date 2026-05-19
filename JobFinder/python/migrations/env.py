"""Alembic migration environment — online mode only.

Configures Alembic to use the shared SQLAlchemy engine from shared.db
(driven by POSTGRESQL_CONNECTION_STRING) and the ORM metadata from
shared.models so Alembic can inspect the live schema and apply migrations.
The sqlalchemy.url in alembic.ini is intentionally left as a placeholder —
the real connection is always provided by get_engine() at runtime.
"""

from alembic import context
from shared.db import get_engine
from shared.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations against the live database using the shared engine."""
    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
