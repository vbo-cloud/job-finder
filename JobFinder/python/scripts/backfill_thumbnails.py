"""One-time backfill: generate and store thumbnails for CVs that have none.

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

from shared.models import CV  # noqa: E402 — path must be set first

logger = structlog.get_logger()

CV_BLOB_CONTAINER = "cvs"
THUMBNAIL_SCALE = 0.4

DATABASE_URL = os.environ.get("DATABASE_URL")
AZURE_STORAGE_ACCOUNT_URL = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
if not AZURE_STORAGE_ACCOUNT_URL:
    raise ValueError("AZURE_STORAGE_ACCOUNT_URL environment variable is not set")


def _generate_thumbnail(pdf_bytes: bytes) -> bytes:
    """Render the first PDF page as a JPEG at THUMBNAIL_SCALE.

    Args:
        pdf_bytes: Raw PDF bytes.

    Returns:
        JPEG image bytes.

    Raises:
        pdfium.PdfiumError: If the PDF cannot be rendered.
    """
    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    page = pdf[0]
    bitmap = page.render(scale=THUMBNAIL_SCALE)
    image = bitmap.to_pil()
    if image.mode != "RGB":
        image = image.convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


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


def main() -> None:
    """Iterate CVs without a thumbnail_url, generate, upload, and persist each one."""
    engine = create_engine(DATABASE_URL)
    blob_service = BlobServiceClient(
        account_url=AZURE_STORAGE_ACCOUNT_URL,
        credential=DefaultAzureCredential(),
    )

    with Session(engine) as session:
        rows = session.execute(
            select(CV).where(CV.thumbnail_url.is_(None), CV.blob_url.is_not(None))
        ).scalars().all()

        logger.info("backfill_start", total=len(rows))

        for cv in rows:
            log = logger.bind(cv_id=str(cv.id), user_id=cv.user_id)
            log.info("backfill_cv_start")

            try:
                blob_name = _blob_name_from_url(cv.blob_url)
                pdf_client = blob_service.get_blob_client(
                    container=CV_BLOB_CONTAINER, blob=blob_name
                )
                pdf_bytes = pdf_client.download_blob().readall()
            except AzureError:
                log.error("backfill_cv_download_failed", exc_info=True)
                continue

            try:
                thumb_bytes = _generate_thumbnail(pdf_bytes)
            except pdfium.PdfiumError:
                log.error("backfill_cv_render_failed", exc_info=True)
                continue

            thumb_blob_name = f"{cv.user_id}/{cv.id}_thumb.jpg"
            try:
                thumb_client = blob_service.get_blob_client(
                    container=CV_BLOB_CONTAINER, blob=thumb_blob_name
                )
                thumb_client.upload_blob(thumb_bytes, overwrite=True)
                thumbnail_url = thumb_client.url
            except AzureError:
                log.error("backfill_cv_upload_failed", exc_info=True)
                continue

            try:
                cv.thumbnail_url = thumbnail_url
                session.commit()
            except SQLAlchemyError:
                log.error("backfill_cv_db_failed", exc_info=True)
                session.rollback()
                continue

            log.info("backfill_cv_done", thumbnail_url=thumbnail_url)

    logger.info("backfill_complete")


if __name__ == "__main__":
    main()
