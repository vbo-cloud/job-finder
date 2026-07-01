"""CV upload endpoint."""

import io
import os
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import pdfplumber
import pypdfium2 as pdfium
import structlog
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.servicebus.exceptions import ServiceBusError
from azure.storage.blob import BlobServiceClient
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from pdfminer.pdfparser import PDFSyntaxError
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.bus import send_message
from shared.constants import THUMBNAIL_SCALE
from shared.embedder import embed
from shared.models import CV, Match, UserProfile
from auth import get_current_user
from dependencies import get_db
from schemas import CVListItemOut, CVUploadOut

router = APIRouter(prefix="/cv", tags=["cv"])
logger = structlog.get_logger()

CV_ANALYSIS_QUEUE = "cv-analysis"
CV_BLOB_CONTAINER = "cvs"
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB

AZURE_STORAGE_ACCOUNT_URL = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
if not AZURE_STORAGE_ACCOUNT_URL:
    raise ValueError("AZURE_STORAGE_ACCOUNT_URL environment variable is not set")

# Module-level singleton — connection pool is intentionally shared across requests
# and never explicitly closed (correct for a long-lived server process).
_blob_service_client = BlobServiceClient(
    account_url=AZURE_STORAGE_ACCOUNT_URL,
    credential=DefaultAzureCredential(),
)


def _generate_cv_thumbnail(contents: bytes) -> bytes | None:
    """Render the first PDF page as a JPEG thumbnail. Returns None on failure.

    Non-critical — a failed thumbnail must not abort the upload.

    Args:
        contents: Raw PDF bytes.

    Returns:
        JPEG image bytes, or None if rendering failed.
    """
    try:
        pdf = pdfium.PdfDocument(contents)
        try:
            page = pdf[0]
            bitmap = page.render(scale=THUMBNAIL_SCALE)
            image = bitmap.to_pil()
            if image.mode != "RGB":
                image = image.convert("RGB")
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
        finally:
            pdf.close()
    except pdfium.PdfiumError:
        logger.error("cv_thumbnail_generation_failed", exc_info=True)
        return None


def _upload_thumbnail_blob(contents: bytes, user_id: str, cv_id: uuid.UUID) -> str:
    """Upload a JPEG thumbnail to blob storage and return its URL.

    Blob name is ``{user_id}/{cv_id}_thumb.jpg``.

    Args:
        contents: JPEG thumbnail bytes.
        user_id: Authenticated user ID, used as the blob path prefix.
        cv_id: CV UUID, used to build a deterministic blob name.

    Returns:
        The full URL of the uploaded thumbnail blob.

    Raises:
        AzureError: If the upload fails for any storage-level reason.
    """
    blob_name = f"{user_id}/{cv_id}_thumb.jpg"
    blob_client = _blob_service_client.get_blob_client(
        container=CV_BLOB_CONTAINER,
        blob=blob_name,
    )
    try:
        blob_client.upload_blob(contents, overwrite=True)
    except AzureError:
        logger.error("cv_thumbnail_upload_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise
    return blob_client.url


def _upload_cv_blob(contents: bytes, user_id: str) -> str:
    """Upload raw PDF bytes to Azure Blob Storage and return the blob URL.

    Blob name is ``{user_id}/{uuid4}.pdf`` — UUID suffix prevents collisions
    between successive uploads from the same user.

    Args:
        contents: Raw PDF bytes.
        user_id: Authenticated user ID, used as the blob path prefix.

    Returns:
        The full URL of the uploaded blob.

    Raises:
        AzureError: If the upload fails for any storage-level reason.
    """
    blob_name = f"{user_id}/{uuid.uuid4()}.pdf"
    logger.info("cv_blob_upload_started", user_id=user_id, blob_name=blob_name)
    blob_client = _blob_service_client.get_blob_client(
        container=CV_BLOB_CONTAINER,
        blob=blob_name,
    )
    try:
        blob_client.upload_blob(contents, overwrite=False)
    except AzureError:
        logger.error("cv_blob_upload_failed", user_id=user_id, exc_info=True)
        raise
    logger.info("cv_blob_upload_done", user_id=user_id, blob_name=blob_name)
    return blob_client.url


def _download_blob(blob_url: str, container: str) -> bytes:
    """Download a blob by its full URL and return its raw bytes.

    Args:
        blob_url: Full Azure Blob Storage URL of the blob.
        container: The container name the blob lives in.

    Returns:
        Raw blob content as bytes.

    Raises:
        AzureError: If the download fails for any storage-level reason.
    """
    # Expected format: https://<account>.blob.core.windows.net/<container>/<blob_path>
    # path.parts = ('/', '<container>', '<blob_path_segment>', ...)
    parts = PurePosixPath(urlparse(blob_url).path).parts
    blob_name = str(PurePosixPath(*parts[2:]))  # drop leading '/' and container
    blob_client = _blob_service_client.get_blob_client(
        container=container, blob=blob_name
    )
    try:
        return blob_client.download_blob().readall()
    except AzureError:
        logger.error("blob_download_failed", blob_url=blob_url, exc_info=True)
        raise


def _delete_blob(blob_url: str, container: str) -> None:
    """Delete a blob by its full URL. No-op if the blob does not exist.

    Args:
        blob_url: Full Azure Blob Storage URL of the blob.
        container: Container name the blob lives in.

    Raises:
        AzureError: If the deletion fails for a reason other than the blob being absent.
    """
    parts = PurePosixPath(urlparse(blob_url).path).parts
    blob_name = str(PurePosixPath(*parts[2:]))  # drop leading '/' and container
    blob_client = _blob_service_client.get_blob_client(container=container, blob=blob_name)
    try:
        blob_client.delete_blob()
    except ResourceNotFoundError:
        pass
    except AzureError:
        logger.error("blob_delete_failed", blob_url=blob_url, exc_info=True)
        raise


@router.post("/upload", response_model=CVUploadOut)
async def upload_cv(
    file: UploadFile,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> CVUploadOut:
    """Upload a PDF CV, generate an embedding, and trigger ROME code analysis.

    Inserts a new CV row and a default user profile (if absent), then sends a
    message to the cv-analysis queue. The cv-analysis agent extracts ROME codes
    from the raw text and dispatches the offer-ready trigger once codes are populated.

    Args:
        file: The uploaded PDF file.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        CVUploadOut with the CV ID, blob URL, and a confirmation message.

    Raises:
        HTTPException 422: If the uploaded file is not a valid PDF.
        HTTPException 503: If Azure Blob Storage is unavailable.
    """
    logger.info("cv_upload_started", user_id=user_id, filename=file.filename)

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are accepted.",
        )

    contents = await file.read()
    if len(contents) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="PDF exceeds maximum allowed size of 10 MB.",
        )
    if not contents.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File does not appear to be a valid PDF.",
        )
    try:
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            raw_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except PDFSyntaxError as e:
        logger.error("cv_upload_pdf_invalid", user_id=user_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File is not a valid PDF",
        ) from e
    logger.info("cv_upload_text_extracted", user_id=user_id, chars=len(raw_text))

    try:
        blob_url = _upload_cv_blob(contents, user_id)
    except AzureError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage unavailable — CV upload failed",
        ) from e

    embedding = embed([raw_text])[0]
    logger.info("cv_upload_embedding_done", user_id=user_id)

    # Each upload creates a new CV row — the data model supports multiple
    # CVs per user (e.g. different roles). No upsert: every file is a
    # distinct entry visible in the library.
    cv_id = uuid.uuid4()

    # Generate and upload thumbnail (non-critical — failure does not abort the upload).
    thumbnail_url: str | None = None
    thumb_bytes = _generate_cv_thumbnail(contents)
    if thumb_bytes:
        try:
            thumbnail_url = _upload_thumbnail_blob(thumb_bytes, user_id, cv_id)
            logger.info("cv_thumbnail_uploaded", user_id=user_id, cv_id=str(cv_id))
        except AzureError:
            pass  # already logged in _upload_thumbnail_blob

    now = datetime.now(timezone.utc)
    try:
        session.add(CV(
            id=cv_id,
            user_id=user_id,
            name=file.filename,
            status="pending",
            raw_text=raw_text,
            blob_url=blob_url,
            thumbnail_url=thumbnail_url,
            embedding=embedding,
            uploaded_at=now,
            created_at=now,
        ))
        logger.info("cv_upload_cv_inserted", user_id=user_id, cv_id=str(cv_id))

        # Insert a default profile only if absent — never overwrite existing preferences.
        session.execute(
            pg_insert(UserProfile).values(
                id=uuid.uuid4(),
                user_id=user_id,
                rome_codes={},
                job_categories=[],
                location=None,
                contract_types=[],
                created_at=now,
            ).on_conflict_do_nothing(constraint="uq_user_profiles_user_id")
        )

        logger.info("cv_upload_profile_upserted", user_id=user_id)

        session.commit()
    except SQLAlchemyError:
        # Base class is intentional — any DB error (connection lost, constraint
        # violation, timeout) should abort the upload, be logged, and return 500.
        logger.error("cv_upload_db_failed", user_id=user_id, exc_info=True)
        raise

    # Sent after commit: the message is only dispatched if the DB write succeeded.
    try:
        send_message(
            CV_ANALYSIS_QUEUE,
            {"cv_id": str(cv_id)},
        )
        logger.info("cv_upload_analysis_triggered", user_id=user_id, cv_id=str(cv_id))
    except ServiceBusError:
        # Fire-and-forget: matching cron will pick up the CV on next run.
        # Do not fail the request — the CV was committed successfully.
        logger.error("cv_upload_analysis_trigger_failed", user_id=user_id, exc_info=True)

    return CVUploadOut(cv_id=cv_id, blob_url=blob_url, message="CV uploaded and analysis triggered")


@router.get("/", response_model=list[CVListItemOut])
def list_cvs(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[CVListItemOut]:
    """Return all CVs belonging to the authenticated user.

    Args:
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        List of CVListItemOut ordered by uploaded_at descending.
    """
    logger.info("cv_list_started", user_id=user_id)
    try:
        match_count_sq = (
            select(
                Match.cv_id,
                func.count(Match.id).label("match_count"),
                func.count(Match.id).filter(Match.seen_at.is_(None)).label("unseen_count"),
            )
            .group_by(Match.cv_id)
            .subquery()
        )
        rows = session.execute(
            select(
                CV,
                func.coalesce(match_count_sq.c.match_count, 0).label("match_count"),
                func.coalesce(match_count_sq.c.unseen_count, 0).label("unseen_count"),
            )
            .outerjoin(match_count_sq, CV.id == match_count_sq.c.cv_id)
            .where(CV.user_id == user_id)
            .order_by(CV.uploaded_at.desc())
        ).all()
    except SQLAlchemyError:
        logger.error("cv_list_failed", user_id=user_id, exc_info=True)
        raise

    result = [
        CVListItemOut(
            id=cv.id,
            name=cv.name,
            status=cv.status,
            uploaded_at=cv.uploaded_at,
            match_count=match_count,
            unseen_count=unseen_count,
            has_thumbnail=cv.thumbnail_url is not None,
        )
        for cv, match_count, unseen_count in rows
    ]
    logger.info("cv_list_done", user_id=user_id, count=len(result))
    return result


@router.get("/{cv_id}/thumbnail", response_class=Response)
def get_cv_thumbnail(
    cv_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    """Return the JPEG thumbnail for a CV owned by the authenticated user.

    Args:
        cv_id: UUID of the CV.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        JPEG image bytes with media type image/jpeg.

    Raises:
        HTTPException 404: If the CV does not exist, is not owned by the user,
            or has no thumbnail.
        HTTPException 503: If Azure Blob Storage is unavailable.
    """
    logger.info("cv_thumbnail_fetch_started", user_id=user_id, cv_id=str(cv_id))
    try:
        cv = session.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        logger.error("cv_thumbnail_db_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    if cv is None or cv.thumbnail_url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")

    try:
        data = _download_blob(cv.thumbnail_url, CV_BLOB_CONTAINER)
    except AzureError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage unavailable",
        ) from e

    logger.info("cv_thumbnail_fetch_done", user_id=user_id, cv_id=str(cv_id))
    return Response(content=data, media_type="image/jpeg")


@router.get("/{cv_id}/pdf", response_class=Response)
def get_cv_pdf(
    cv_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    """Return the raw PDF for a CV owned by the authenticated user.

    Args:
        cv_id: UUID of the CV.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        PDF bytes with media type application/pdf, displayed inline.

    Raises:
        HTTPException 404: If the CV does not exist or is not owned by the user.
        HTTPException 503: If Azure Blob Storage is unavailable.
    """
    logger.info("cv_pdf_fetch_started", user_id=user_id, cv_id=str(cv_id))
    try:
        cv = session.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        logger.error("cv_pdf_db_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")

    try:
        data = _download_blob(cv.blob_url, CV_BLOB_CONTAINER)
    except AzureError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage unavailable",
        ) from e

    filename = cv.name or "cv.pdf"
    encoded_filename = quote(filename, safe="")
    logger.info("cv_pdf_fetch_done", user_id=user_id, cv_id=str(cv_id))
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"},
    )


@router.patch("/{cv_id}/mark-all-seen", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_seen(
    cv_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    """Mark all unseen matches for a CV as seen.

    Args:
        cv_id: UUID of the CV.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Raises:
        HTTPException 404: If the CV does not exist or is not owned by the user.
    """
    logger.info("mark_all_seen_started", user_id=user_id, cv_id=str(cv_id))
    try:
        cv = session.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        ).scalar_one_or_none()

        if cv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")

        session.execute(
            update(Match)
            .where(Match.cv_id == cv_id, Match.seen_at.is_(None))
            .values(seen_at=datetime.now(timezone.utc))
        )
        session.commit()
    except SQLAlchemyError:
        logger.error("mark_all_seen_db_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    logger.info("mark_all_seen_done", user_id=user_id, cv_id=str(cv_id))


def _remove_cv_from_rome_codes(session: Session, cv_id: uuid.UUID, user_id: str) -> None:
    """Remove a CV's contribution from the user's rome_codes dict.

    For each ROME code entry, removes cv_id from cv_ids. Entries whose cv_ids
    list becomes empty are pruned entirely. No-ops if the user has no profile.

    Uses SELECT ... FOR UPDATE to prevent concurrent writes from racing.

    Args:
        session: Active database session (caller owns commit).
        cv_id: UUID of the CV being deleted.
        user_id: Owner of the profile to update.

    Raises:
        SQLAlchemyError: On any database error.
    """
    profile = session.execute(
        select(UserProfile)
        .where(UserProfile.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not profile or not profile.rome_codes:
        return

    cv_id_str = str(cv_id)
    updated = {
        code: {**data, "cv_ids": [cid for cid in data["cv_ids"] if cid != cv_id_str]}
        for code, data in profile.rome_codes.items()
    }
    profile.rome_codes = {code: data for code, data in updated.items() if data["cv_ids"]}


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cv(
    cv_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    """Delete a CV and its associated blobs for the authenticated user.

    Matches linked to the CV are removed first to satisfy the FK constraint on
    matches.cv_id (no CASCADE DELETE is defined on that relationship).

    Args:
        cv_id: UUID of the CV to delete.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Raises:
        HTTPException 404: If the CV does not exist or is not owned by the user.
        HTTPException 503: If Azure Blob Storage is unavailable.
    """
    logger.info("cv_delete_started", user_id=user_id, cv_id=str(cv_id))
    try:
        cv = session.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        logger.error("cv_delete_db_fetch_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")

    # Blobs are deleted before the DB commit. If commit() fails after this point
    # the CV row survives but its storage objects are permanently gone — a known
    # inconsistency accepted as a trade-off (no compensating-transaction / saga).
    # The inverse order (commit first, then delete blobs) is equally lossy: a blob
    # leak is harder to detect than a row whose blob is missing.
    try:
        _delete_blob(cv.blob_url, CV_BLOB_CONTAINER)
        if cv.thumbnail_url:
            _delete_blob(cv.thumbnail_url, CV_BLOB_CONTAINER)
    except AzureError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage unavailable — CV deletion failed",
        ) from e

    try:
        # Delete matches first — FK constraint on matches.cv_id has no CASCADE.
        session.execute(delete(Match).where(Match.cv_id == cv_id))
        session.delete(cv)
        _remove_cv_from_rome_codes(session, cv_id, user_id)
        session.commit()
    except SQLAlchemyError:
        logger.error("cv_delete_db_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    logger.info("cv_delete_done", user_id=user_id, cv_id=str(cv_id))
