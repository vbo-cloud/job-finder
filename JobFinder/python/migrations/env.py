"""Alembic migration environment — online mode only.

Configures Alembic to use the shared SQLAlchemy engine from shared.db
(driven by DATABASE_URL) and the ORM metadata from
shared.models so Alembic can inspect the live schema and apply migrations.
The sqlalchemy.url in alembic.ini is intentionally left as a placeholder —
the real connection is always provided by get_engine() at runtime.
"""

from alembic import context
from shared.db import get_engine
from shared.models import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline mode is intentionally not implemented.

    This project always migrates against a live database (online mode).
    Offline mode — which generates SQL scripts without a DB connection — is
    not used and is explicitly disabled to avoid silent misconfiguration.
    """
    raise NotImplementedError(
        "Offline migrations are not supported in this project. "
        "Ensure DATABASE_URL is set and run in online mode."
    )


def run_migrations_online() -> None:
    """Run migrations against the live database using the shared engine."""
    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
