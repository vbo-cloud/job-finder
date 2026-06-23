"""FastAPI application — job-finder API entry point."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import cv, matches, profile
from shared.db import run_migrations

CORS_ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

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

# CORS — deny-by-default, non-blocking. Origins come from CORS_ALLOWED_ORIGINS;
# an empty list keeps the current behaviour (no cross-origin access) so the
# already-deployed webapp keeps working until the frontend origin is configured.
# allow_credentials stays False: auth uses a Bearer token in the Authorization
# header, not cookies.
if not CORS_ALLOWED_ORIGINS:
    logger.warning("cors_no_allowed_origins_configured")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(cv.router)
app.include_router(matches.router)
app.include_router(profile.router)
