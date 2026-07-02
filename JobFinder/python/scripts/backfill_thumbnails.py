"""One-time backfill: generate and store thumbnails for CVs that have none.

Two passes are run:
  1. CVs missing thumbnail_url (sm) — generates both sm and lg in one render pass.
  2. CVs with thumbnail_url but missing thumbnail_url_lg — generates lg only.

Usage:
    DATABASE_URL=... AZURE_STORAGE_ACCOUNT_URL=... python scripts/backfill_thumbnails.py

Requires Azure credentials resolvable by DefaultAzureCredential (e.g. az login or
managed identity). Run from the JobFinder/python/ directory so shared/ is on the path.
"""

import io
import os
import sys
import uuid
from urllib.parse import urlparse

import pypdfium2 as pdfium
import structlog
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.constants import THUMBNAIL_SCALE, THUMBNAIL_SCALE_LG  # noqa: E402 — path must be set first
from shared.models import CV  # noqa: E402 — path must be set first

logger = structlog.get_logger()

CV_BLOB_CONTAINER = "cvs"

DATABASE_URL = os.environ.get("DATABASE_URL")
AZURE_STORAGE_ACCOUNT_URL = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
if not AZURE_STORAGE_ACCOUNT_URL:
    raise ValueError("AZURE_STORAGE_ACCOUNT_URL environment variable is not set")


def _generate_thumbnail(pdf_bytes: bytes, scale: float) -> bytes:
    """Render the first PDF page as a JPEG at the given scale.

    Args:
        pdf_bytes: Raw PDF bytes.
        scale: pypdfium2 render scale.

    Returns:
        JPEG image bytes.

    Raises:
        pdfium.PdfiumError: If the PDF cannot be rendered.
    """
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page = pdf[0]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        if image.mode != "RGB":
            image = image.convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    finally:
        pdf.close()


def _blob_name_from_url(blob_url: str) -> str:
    """Extract the blob name from a full Azure Blob Storage URL.

    Args:
        blob_url: Full URL such as
            ``https://account.blob.core.windows.net/cvs/user/file.pdf``.

    Returns:
        Blob name relative to the container, e.g. ``user/file.pdf``.
    """
    path = urlparse(blob_url).path
    return path.split(f"/{CV_BLOB_CONTAINER}/", 1)[1]


def _download_pdf(blob_service: BlobServiceClient, cv: CV) -> bytes | None:
    """Download the PDF blob for a CV. Returns None on failure."""
    try:
        blob_name = _blob_name_from_url(cv.blob_url)
        pdf_client = blob_service.get_blob_client(container=CV_BLOB_CONTAINER, blob=blob_name)
        return pdf_client.download_blob().readall()
    except AzureError:
        logger.bind(cv_id=str(cv.id), user_id=cv.user_id).error(
            "backfill_cv_download_failed", exc_info=True
        )
        return None


def _upload_thumb(blob_service: BlobServiceClient, thumb_bytes: bytes, blob_name: str) -> str | None:
    """Upload a JPEG thumbnail blob. Returns its URL on success, None on failure."""
    try:
        client = blob_service.get_blob_client(container=CV_BLOB_CONTAINER, blob=blob_name)
        client.upload_blob(thumb_bytes, overwrite=True)
        return client.url
    except AzureError:
        logger.error("backfill_cv_upload_failed", blob_name=blob_name, exc_info=True)
        return None


def _backfill_sm_and_lg(blob_service: BlobServiceClient, session: Session) -> None:
    """Pass 1: generate both sm and lg thumbnails for CVs that have neither."""
    rows = session.execute(
        select(CV).where(CV.thumbnail_url.is_(None), CV.blob_url.is_not(None))
    ).scalars().all()

    logger.info("backfill_sm_start", total=len(rows))

    for cv in rows:
        log = logger.bind(cv_id=str(cv.id), user_id=cv.user_id)
        log.info("backfill_sm_cv_start")

        pdf_bytes = _download_pdf(blob_service, cv)
        if pdf_bytes is None:
            continue

        try:
            thumb_sm = _generate_thumbnail(pdf_bytes, THUMBNAIL_SCALE)
        except pdfium.PdfiumError:
            log.error("backfill_sm_render_failed", exc_info=True)
            continue

        sm_url = _upload_thumb(
            blob_service, thumb_sm, f"{cv.user_id}/{cv.id}_thumb.jpg"
        )
        if sm_url is None:
            continue

        try:
            thumb_lg = _generate_thumbnail(pdf_bytes, THUMBNAIL_SCALE_LG)
            lg_url = _upload_thumb(
                blob_service, thumb_lg, f"{cv.user_id}/{cv.id}_thumb_lg.jpg"
            )
        except pdfium.PdfiumError:
            log.error("backfill_lg_render_failed", exc_info=True)
            lg_url = None

        try:
            cv.thumbnail_url = sm_url
            cv.thumbnail_url_lg = lg_url
            session.commit()
        except SQLAlchemyError:
            log.error("backfill_sm_db_failed", exc_info=True)
            session.rollback()
            continue

        log.info("backfill_sm_cv_done", sm_url=sm_url, lg_url=lg_url)


def _backfill_lg_only(blob_service: BlobServiceClient, session: Session) -> None:
    """Pass 2: generate lg thumbnails for CVs that already have sm but not lg."""
    rows = session.execute(
        select(CV).where(
            CV.thumbnail_url.is_not(None),
            CV.thumbnail_url_lg.is_(None),
            CV.blob_url.is_not(None),
        )
    ).scalars().all()

    logger.info("backfill_lg_start", total=len(rows))

    for cv in rows:
        log = logger.bind(cv_id=str(cv.id), user_id=cv.user_id)
        log.info("backfill_lg_cv_start")

        pdf_bytes = _download_pdf(blob_service, cv)
        if pdf_bytes is None:
            continue

        try:
            thumb_lg = _generate_thumbnail(pdf_bytes, THUMBNAIL_SCALE_LG)
        except pdfium.PdfiumError:
            log.error("backfill_lg_render_failed", exc_info=True)
            continue

        lg_url = _upload_thumb(
            blob_service, thumb_lg, f"{cv.user_id}/{cv.id}_thumb_lg.jpg"
        )
        if lg_url is None:
            continue

        try:
            cv.thumbnail_url_lg = lg_url
            session.commit()
        except SQLAlchemyError:
            log.error("backfill_lg_db_failed", exc_info=True)
            session.rollback()
            continue

        log.info("backfill_lg_cv_done", lg_url=lg_url)


def main() -> None:
    """Run sm+lg backfill for CVs without thumbnails, then lg backfill for the rest."""
    engine = create_engine(DATABASE_URL)
    with BlobServiceClient(
        account_url=AZURE_STORAGE_ACCOUNT_URL,
        credential=DefaultAzureCredential(),
    ) as blob_service, Session(engine) as session:
        _backfill_sm_and_lg(blob_service, session)
        _backfill_lg_only(blob_service, session)

    logger.info("backfill_complete")


if __name__ == "__main__":
    main()
