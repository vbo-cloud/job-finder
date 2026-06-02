"""FastAPI application — job-finder API entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from routers import cv, matches, profile
from shared.db import run_migrations

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan — run migrations on startup.

    Runs `alembic upgrade head` idempotently before the app starts
    accepting requests. A migration failure here is intentional —
    it prevents the app from starting with an inconsistent schema.

    Yields:
        None: Control is yielded to FastAPI after startup completes.
    """
    try:
        run_migrations()
    except Exception:  # intentional: any migration error must halt startup
        logger.error("migrations_failed", exc_info=True)
        raise
    yield


app = FastAPI(
    title="job-finder API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(cv.router)
app.include_router(matches.router)
app.include_router(profile.router)
