"""CV upload endpoint."""

import io
import os
import uuid
from datetime import datetime, timezone

import pdfplumber
import structlog
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.servicebus.exceptions import ServiceBusError
from azure.storage.blob import BlobServiceClient
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pdfminer.pdfparser import PDFSyntaxError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.bus import send_message
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

_blob_service_client = BlobServiceClient(
    account_url=AZURE_STORAGE_ACCOUNT_URL,
    credential=DefaultAzureCredential(),
)


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


@router.post("/upload", response_model=CVUploadOut)
async def upload_cv(
    file: UploadFile,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> CVUploadOut:
    """Upload a PDF CV, generate an embedding, and trigger ROME code analysis.

    Upserts the CV and a default user profile (if absent), then sends a message
    to the cv-analysis queue. The cv-analysis agent extracts ROME codes from the
    raw text and dispatches the offer-ready trigger once codes are populated.

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

    now = datetime.now(timezone.utc)
    try:
        # Note: no UNIQUE constraint on cvs.user_id — intentional design decision.
        # The data model supports multiple CVs per user (e.g. different roles).
        # A unique constraint would permanently prevent this use case.
        # The select-then-insert race condition is accepted for sequential uploads.
        # Mitigating factor: the webapp runs as a single Container App replica
        # during this phase — horizontal scaling would reintroduce the window.
        existing_cv = session.execute(
            select(CV).where(CV.user_id == user_id)
        ).scalar_one_or_none()

        if existing_cv is not None:
            existing_cv.raw_text = raw_text
            existing_cv.blob_url = blob_url
            existing_cv.embedding = embedding
            existing_cv.uploaded_at = now
            existing_cv.name = file.filename
            existing_cv.status = "pending"
            cv_id = existing_cv.id
        else:
            cv_id = uuid.uuid4()
            session.add(CV(
                id=cv_id,
                user_id=user_id,
                name=file.filename,
                status="pending",
                raw_text=raw_text,
                blob_url=blob_url,
                embedding=embedding,
                uploaded_at=now,
                created_at=now,
            ))
        logger.info("cv_upload_cv_upserted", user_id=user_id, cv_id=str(cv_id))

        # Insert a default profile only if absent — never overwrite existing preferences.
        session.execute(
            pg_insert(UserProfile).values(
                id=uuid.uuid4(),
                user_id=user_id,
                rome_codes=[],
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
            select(Match.cv_id, func.count(Match.id).label("match_count"))
            .group_by(Match.cv_id)
            .subquery()
        )
        rows = session.execute(
            select(CV, func.coalesce(match_count_sq.c.match_count, 0).label("match_count"))
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
        )
        for cv, match_count in rows
    ]
    logger.info("cv_list_done", user_id=user_id, count=len(result))
    return result
