"""CV upload endpoint."""

import io
import os
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Literal
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
from sqlalchemy import and_, delete, func, select, true, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.bus import send_message
from shared.constants import THUMBNAIL_SCALE, THUMBNAIL_SCALE_LG
from shared.embedder import embed
from shared.models import CV, CvAnalysis, Match, MatchAnalysis, Offer, UserProfile
from auth import UserIdentity, get_current_identity, get_current_user
from dependencies import get_db
from profile_defaults import default_profile_values
from routers.matches import commune_zone_condition
from schemas import CVListItemOut, CVUploadOut, CvAnalysisOut

router = APIRouter(prefix="/cv", tags=["cv"])
logger = structlog.get_logger()

CV_ANALYSIS_QUEUE = "cv-analysis"
CV_BLOB_CONTAINER = "cvs"
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB

# Minimum width (points) of a horizontal whitespace band to be considered a column gutter
# rather than ordinary inter-word spacing. Provisional — calibrated against synthetic word
# layouts covering typical CV font sizes (10-11pt body text, ~2-6pt inter-word space) and
# typical two-column gutter widths (15-40pt), not against real uploaded PDFs. Tune via the
# columns_detected field logged below once real upload data is observable (see the diagnostic
# referenced in _extract_page_text's docstring).
_MIN_COLUMN_GAP_WIDTH = 14.0
# Minimum fraction of text rows that must be undisturbed by a candidate gap for it to count as
# a real column break, not just an indented list or bullet block spanning a few lines. Same
# calibration caveat as above.
_MIN_GAP_ROW_COVERAGE = 0.6
# Minimum fraction of text rows that must have actual content on BOTH sides of a candidate gap.
# Without this, a single-column CV whose lines have very uneven lengths (e.g. short skill-badge
# lines next to long experience bullets) can have a wide blank margin on one side that no line
# ever crosses — satisfying _MIN_GAP_ROW_COVERAGE trivially without there being a real second
# column anywhere on the page. Calibrated as a starting point, not a fixed value — see the
# diagnostic referenced in _detect_column_gap's docstring.
_MIN_GAP_BILATERAL_ROWS = 0.3

AZURE_STORAGE_ACCOUNT_URL = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
if not AZURE_STORAGE_ACCOUNT_URL:
    raise ValueError("AZURE_STORAGE_ACCOUNT_URL environment variable is not set")

# Module-level singleton — connection pool is intentionally shared across requests
# and never explicitly closed (correct for a long-lived server process).
_blob_service_client = BlobServiceClient(
    account_url=AZURE_STORAGE_ACCOUNT_URL,
    credential=DefaultAzureCredential(),
)


def _generate_cv_thumbnail(contents: bytes, scale: float) -> bytes | None:
    """Render the first PDF page as a JPEG thumbnail at the given scale. Returns None on failure.

    Non-critical — a failed thumbnail must not abort the upload.

    Args:
        contents: Raw PDF bytes.
        scale: pypdfium2 render scale (e.g. 0.4 for a small card, 2.0 for the detail view).

    Returns:
        JPEG image bytes, or None if rendering failed.
    """
    try:
        pdf = pdfium.PdfDocument(contents)
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
    except pdfium.PdfiumError:
        logger.error("cv_thumbnail_generation_failed", exc_info=True)
        return None


def _upload_thumbnail_blob(
    contents: bytes, user_id: str, cv_id: uuid.UUID, suffix: str = "_thumb"
) -> str:
    """Upload a JPEG thumbnail to blob storage and return its URL.

    Blob name is ``{user_id}/{cv_id}{suffix}.jpg``.

    Args:
        contents: JPEG thumbnail bytes.
        user_id: Authenticated user ID, used as the blob path prefix.
        cv_id: CV UUID, used to build a deterministic blob name.
        suffix: Blob name suffix before the extension (default ``_thumb``).

    Returns:
        The full URL of the uploaded thumbnail blob.

    Raises:
        AzureError: If the upload fails for any storage-level reason.
    """
    blob_name = f"{user_id}/{cv_id}{suffix}.jpg"
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


def _group_words_into_rows(words: list[dict], tolerance: float = 3.0) -> list[list[dict]]:
    """Cluster pdfplumber words into text rows by their 'top' coordinate.

    Words on the same printed line rarely share the exact same 'top' value (sub-pixel
    rendering differences), so rows are formed by grouping words whose 'top' falls within
    `tolerance` points of the row's first word.

    Args:
        words: pdfplumber word dicts (each with 'x0', 'x1', 'top', 'bottom', 'text').
        tolerance: Maximum 'top' distance (points) for a word to join the current row.

    Returns:
        Rows in top-to-bottom order, each a list of words in arbitrary horizontal order.
    """
    rows: list[list[dict]] = []
    for word in sorted(words, key=lambda w: w["top"]):
        if rows and abs(word["top"] - rows[-1][0]["top"]) <= tolerance:
            rows[-1].append(word)
        else:
            rows.append([word])
    return rows


def _words_to_lines(words: list[dict]) -> str:
    """Reconstitute reading-order text from a word list, independent of input order.

    Words are grouped into rows (see _group_words_into_rows) then, within each row, ordered
    left to right — so callers do not need to pre-sort the input.

    Args:
        words: pdfplumber word dicts.

    Returns:
        Newline-joined text, one row per line, words within a row space-joined.
    """
    rows = _group_words_into_rows(words)
    lines = [
        " ".join(w["text"] for w in sorted(row, key=lambda w: w["x0"]))
        for row in rows
    ]
    return "\n".join(lines)


def _gap_row_coverage(rows: list[list[dict]], gap_left: float, gap_right: float) -> float:
    """Fraction of rows whose words are entirely outside the [gap_left, gap_right] band.

    A row counts as clean even if it belongs entirely to one side of the gap (the normal case
    for a two-column layout, where a given row is either sidebar or main-block content, not
    both) — it only fails if some word actually straddles or crosses the band.

    Args:
        rows: Rows as returned by _group_words_into_rows.
        gap_left: Left edge of the candidate gap band.
        gap_right: Right edge of the candidate gap band.

    Returns:
        clean_rows / total_rows, or 0.0 if there are no rows.
    """
    if not rows:
        return 0.0
    clean_rows = sum(
        1
        for row in rows
        if all(w["x1"] <= gap_left or w["x0"] >= gap_right for w in row)
    )
    return clean_rows / len(rows)


def _gap_has_bilateral_content(rows: list[list[dict]], gap_left: float, gap_right: float) -> bool:
    """True if enough rows have at least one word strictly left of the gap AND at
    least one word strictly right of the gap — real two-column evidence, as
    opposed to a large blank margin that no row happens to cross (which passes
    _gap_row_coverage trivially without ever containing right-hand content).

    Args:
        rows: Rows as returned by _group_words_into_rows.
        gap_left: Left edge of the candidate gap band.
        gap_right: Right edge of the candidate gap band.

    Returns:
        Whether at least _MIN_GAP_BILATERAL_ROWS of rows have content on both sides.
    """
    if not rows:
        return False
    bilateral_rows = sum(
        1
        for row in rows
        if any(w["x1"] <= gap_left for w in row) and any(w["x0"] >= gap_right for w in row)
    )
    return (bilateral_rows / len(rows)) >= _MIN_GAP_BILATERAL_ROWS


def _detect_column_gap(words: list[dict], page_width: float, page_height: float) -> float | None:
    """Detect the x-coordinate of a vertical whitespace band splitting the page into two columns.

    Candidate gaps are the whitespace bands between consecutive distinct word x0/x1 boundaries
    (cheap to enumerate, and guaranteed to include the true column gutter if one exists). A
    candidate only counts as a real column break if both hold:
    - its width exceeds _MIN_COLUMN_GAP_WIDTH — comfortably wider than normal inter-word
      spacing, so a single wide space within one column's own text is never mistaken for a
      column break;
    - at least _MIN_GAP_ROW_COVERAGE of the page's text rows have no word crossing it — measured
      per row (not against total page height), so a header or footer line that happens to span
      the full page width doesn't kill an otherwise-real gap, while an indented bullet list in
      an actually single-column CV (whose indentation only clears a handful of rows, not most of
      them) does not reach the coverage threshold and is correctly rejected;
    - at least _MIN_GAP_BILATERAL_ROWS of the page's text rows have actual content on both sides
      of the gap. The two conditions above only prove that nothing *crosses* the band — a
      single-column CV with very uneven line lengths (short skill-badge lines next to long
      experience bullets) routinely has a wide blank margin on one side that no line ever
      reaches, which satisfies both of them without there being a second column anywhere on the
      page. This third condition requires actual right-hand (and left-hand) content, not just
      an absence of crossings, to tell a real column gutter apart from a one-sided margin.

    3+ column layouts and grid/table layouts are out of scope: only the single widest qualifying
    gap is ever considered, so this never attempts to split a page into more than two columns —
    a page that doesn't fit the two-column model falls back to the default single-column
    behavior in _extract_page_text rather than producing a wrong split silently.

    Args:
        words: pdfplumber word dicts for the page.
        page_width: Page width in points (unused directly — kept for signature parity with the
            page context callers naturally have on hand, and for future width-relative tuning).
        page_height: Page height in points (unused directly, same rationale).

    Returns:
        The x-coordinate at the midpoint of the widest qualifying gap, or None if no candidate
        satisfies both thresholds.
    """
    if not words:
        return None

    rows = _group_words_into_rows(words)
    if len(rows) < 2:
        return None

    boundaries = sorted({w["x0"] for w in words} | {w["x1"] for w in words})

    best_gap: tuple[float, float] | None = None
    best_width = 0.0
    for left, right in zip(boundaries, boundaries[1:]):
        width = right - left
        if width <= _MIN_COLUMN_GAP_WIDTH:
            continue
        if _gap_row_coverage(rows, left, right) < _MIN_GAP_ROW_COVERAGE:
            continue
        if not _gap_has_bilateral_content(rows, left, right):
            continue
        if width > best_width:
            best_width = width
            best_gap = (left, right)

    if best_gap is None:
        return None
    return (best_gap[0] + best_gap[1]) / 2


def _extract_page_text(page: pdfplumber.page.Page) -> tuple[str, int]:
    """Extract a page's text, reconstituting reading order if a column layout is detected.

    Falls back to pdfplumber's default page.extract_text() — unchanged behavior — whenever no
    word is found, or no candidate gap in _detect_column_gap satisfies both thresholds. This is
    the dominant case (single-column CVs), and the fallback is byte-identical to the previous
    extraction, not just "equivalent" — see the diagnostic in
    docs/prompts/prompt-cv-analysis-referentiel-model-upgrade-column-parsing.md for why a CV with
    a two-column layout (sidebar + main block) previously produced raw_text with both blocks
    interleaved, corrupting downstream ROME extraction and quality analysis.

    When a gap is detected, words are split into a left and right group by the gap's x
    boundaries, each reconstituted independently via _words_to_lines, and concatenated left
    column first then right column. A word spanning the gap entirely (a full-width banner or
    section rule above an otherwise two-column body — routine, not rare) is assigned whole to
    whichever side it's closer to, never split or dropped. Only ever splits into at most two
    columns — see _detect_column_gap's docstring for why 3+ column and grid layouts are
    explicitly out of scope and fall back to the default single-column path instead of guessing.

    Args:
        page: A pdfplumber Page.

    Returns:
        A tuple of (extracted text, number of columns detected — 1 or 2).
    """
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    if not words:
        return page.extract_text() or "", 1

    gap = _detect_column_gap(words, page.width, page.height)
    if gap is None:
        return page.extract_text() or "", 1

    left_words = [w for w in words if w["x1"] <= gap]
    right_words = [w for w in words if w["x0"] >= gap]
    # Words that span the gap entirely (e.g. a full-width name banner or section rule above a
    # two-column body) land in neither group above — routine, not an edge case. Each such word
    # is assigned to whichever side its center is closer to (here, the left/sidebar column,
    # since such a word usually starts near the page's left margin) rather than dropped or
    # duplicated.
    straddling = [w for w in words if w not in left_words and w not in right_words]
    for w in straddling:
        (left_words if abs(w["x0"] - gap) < abs(w["x1"] - gap) else right_words).append(w)

    left_text = _words_to_lines(left_words)
    right_text = _words_to_lines(right_words)
    return f"{left_text}\n\n{right_text}", 2


@router.post("/upload", response_model=CVUploadOut)
async def upload_cv(
    file: UploadFile,
    identity: UserIdentity = Depends(get_current_identity),
    session: Session = Depends(get_db),
) -> CVUploadOut:
    """Upload a PDF CV, generate an embedding, and trigger ROME code analysis.

    Inserts a new CV row and a default user profile (if absent), then sends a
    message to the cv-analysis queue. The cv-analysis agent extracts ROME codes
    from the raw text and dispatches the start-matching trigger once codes are populated.

    Args:
        file: The uploaded PDF file.
        identity: Authenticated identity claims from the JWT (sub, email, name) —
            the profile created on first upload captures email/display_name.
        session: Active database session.

    Returns:
        CVUploadOut with the CV ID, blob URL, and a confirmation message.

    Raises:
        HTTPException 422: If the uploaded file is not a valid PDF.
        HTTPException 503: If Azure Blob Storage is unavailable.
    """
    user_id = identity.user_id
    logger.info("cv_upload_started", user_id=user_id, cv_filename=file.filename)

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
            page_results = [_extract_page_text(page) for page in pdf.pages]
        raw_text = "\n".join(text for text, _ in page_results)
        # Max across pages, not the last page's value — a single two-column page anywhere in
        # the document is enough to warrant the ATS-risk note in quality analysis.
        columns_detected = max((n for _, n in page_results), default=1)
    except PDFSyntaxError as e:
        logger.error("cv_upload_pdf_invalid", user_id=user_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File is not a valid PDF",
        ) from e
    logger.info(
        "cv_upload_text_extracted",
        user_id=user_id,
        chars=len(raw_text),
        columns_detected=columns_detected,
    )

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

    # Generate and upload thumbnails (non-critical — failure does not abort the upload).
    thumbnail_url: str | None = None
    thumbnail_url_lg: str | None = None
    thumb_bytes = _generate_cv_thumbnail(contents, THUMBNAIL_SCALE)
    if thumb_bytes:
        try:
            thumbnail_url = _upload_thumbnail_blob(thumb_bytes, user_id, cv_id)
            logger.info("cv_thumbnail_uploaded", user_id=user_id, cv_id=str(cv_id))
        except AzureError:
            pass  # already logged in _upload_thumbnail_blob
    thumb_bytes_lg = _generate_cv_thumbnail(contents, THUMBNAIL_SCALE_LG)
    if thumb_bytes_lg:
        try:
            thumbnail_url_lg = _upload_thumbnail_blob(thumb_bytes_lg, user_id, cv_id, suffix="_thumb_lg")
            logger.info("cv_thumbnail_lg_uploaded", user_id=user_id, cv_id=str(cv_id))
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
            thumbnail_url_lg=thumbnail_url_lg,
            embedding=embedding,
            uploaded_at=now,
            created_at=now,
            layout_columns_detected=columns_detected,
        ))
        logger.info("cv_upload_cv_inserted", user_id=user_id, cv_id=str(cv_id))

        # Insert a default profile only if absent — never overwrite existing
        # preferences. commune_codes stays explicit here (outside the shared
        # defaults): cv.py always creates with [], profile.py derives it from
        # the request body.
        session.execute(
            pg_insert(UserProfile)
            .values(**default_profile_values(identity), commune_codes=[])
            .on_conflict_do_nothing(constraint="uq_user_profiles_user_id")
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

    Both match_count and unseen_count only count matches whose offer falls
    inside the user's painted commune zone (same geographic filter as
    GET /matches) — otherwise the library could advertise matches, new or
    not, that never appear in the matches list actually shown for the
    selected zone.

    rome_reanalysis_available is True when the profile's description_updated_at
    is more recent than this CV's rome_analyzed_at (or the CV has never been
    ROME-analyzed at all) — signals the frontend to offer a manual ROME
    reanalysis button. Computed from the profile already loaded for
    zone_condition, no extra query.

    Args:
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        List of CVListItemOut ordered by uploaded_at descending.
    """
    logger.info("cv_list_started", user_id=user_id)
    try:
        profile = session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one_or_none()

        zone_condition = (
            commune_zone_condition(profile.commune_codes)
            if profile is not None and profile.commune_codes
            else true()
        )

        match_count_sq = (
            select(
                Match.cv_id,
                func.count(Match.id).filter(zone_condition).label("match_count"),
                func.count(Match.id)
                .filter(and_(Match.seen_at.is_(None), zone_condition))
                .label("unseen_count"),
            )
            .join(Offer, Match.offer_id == Offer.id)
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
            rome_reanalysis_available=(
                profile is not None
                and profile.description_updated_at is not None
                and (cv.rome_analyzed_at is None or profile.description_updated_at > cv.rome_analyzed_at)
            ),
        )
        for cv, match_count, unseen_count in rows
    ]
    logger.info("cv_list_done", user_id=user_id, count=len(result))
    return result


def _backfill_cv_analysis(session: Session, cv_id: uuid.UUID, user_id: str) -> None:
    """Create a pending cv_analyses row and dispatch a quality-only analysis.

    Self-healing for CVs that have no analysis row and whose upload-time
    dispatch will never recur: CVs uploaded before the cv_analyses feature
    existed, or whose agent run crashed before writing any row. Without this,
    GET /cv/{id}/analysis reports "pending" forever and the frontend polls
    a result that will never arrive.

    The pending row is inserted first, as a claim — the frontend polls every
    few seconds, and only the poll that wins the insert dispatches; otherwise
    each poll would enqueue a new message until the agent writes the row.
    On dispatch failure the claim is flipped to "error" so the UI offers the
    manual retry button instead of waiting on a message that never left.

    Best-effort: any DB error is logged and swallowed — the caller's read
    already succeeded and must not turn into a 500 because healing failed.

    Args:
        session: Active database session.
        cv_id: UUID of the CV missing its analysis row.
        user_id: Owner of the CV, for log correlation only.
    """
    try:
        claimed = session.execute(
            pg_insert(CvAnalysis)
            .values(
                id=uuid.uuid4(),
                cv_id=cv_id,
                status="pending",
                requested_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(constraint="uq_cv_analyses_cv_id")
            .returning(CvAnalysis.id)
        ).scalar_one_or_none()
        session.commit()
    except SQLAlchemyError:
        logger.error("cv_analysis_backfill_claim_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        return

    if claimed is None:
        # Another poll (or the agent itself) already created the row.
        return

    try:
        send_message(CV_ANALYSIS_QUEUE, {"cv_id": str(cv_id), "retry_quality_only": True})
        logger.info("cv_analysis_backfill_dispatched", user_id=user_id, cv_id=str(cv_id))
    except ServiceBusError:
        logger.error("cv_analysis_backfill_dispatch_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        try:
            session.execute(
                update(CvAnalysis).where(CvAnalysis.cv_id == cv_id).values(status="error")
            )
            session.commit()
        except SQLAlchemyError:
            logger.error("cv_analysis_backfill_error_status_write_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)


@router.get("/{cv_id}/analysis", response_model=CvAnalysisOut)
def get_cv_analysis(
    cv_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> CvAnalysisOut:
    """Return the CV quality analysis for a CV owned by the authenticated user.

    Returns status="pending" (all other fields empty/None) if the CV exists but the
    cv_analysis agent has not written a row yet — the row is only created by the
    agent itself, never at upload time.

    If no row exists and the CV is past the upload pipeline (status is neither
    "pending" nor "processing"), the upload-time analysis will never arrive —
    a quality-only analysis is re-dispatched (see _backfill_cv_analysis).

    Args:
        cv_id: UUID of the CV.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        CvAnalysisOut with the analysis status and results.

    Raises:
        HTTPException 404: If the CV does not exist or is not owned by the user.
    """
    logger.info("cv_analysis_fetch_started", user_id=user_id, cv_id=str(cv_id))
    try:
        cv = session.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        ).scalar_one_or_none()

        if cv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")

        analysis = session.execute(
            select(CvAnalysis).where(CvAnalysis.cv_id == cv_id)
        ).scalar_one_or_none()
    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.error("cv_analysis_fetch_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    logger.info(
        "cv_analysis_fetch_done",
        user_id=user_id,
        cv_id=str(cv_id),
        status=analysis.status if analysis else "pending",
    )
    if analysis is None:
        if cv.status not in ("pending", "processing"):
            # The CV finished (or failed) its upload pipeline without an
            # analysis row — predates the cv_analyses feature or the agent
            # crashed before writing anything. Heal it now.
            _backfill_cv_analysis(session, cv_id, user_id)
        return CvAnalysisOut(status="pending")
    return CvAnalysisOut.model_validate(analysis)


@router.post("/{cv_id}/analysis/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_cv_analysis(
    cv_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    """Manually re-trigger the CV quality analysis for a CV owned by the authenticated user.

    Free and unlimited — same cost regime as the automatic analysis run at
    upload time (see ADR-018 addendum). Only the quality analysis re-runs —
    ROME codes and matching are untouched. Idempotent: safe to call again if
    a previous retry also failed.

    Args:
        cv_id: UUID of the CV.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Raises:
        HTTPException 404: If the CV does not exist or is not owned by the user.
    """
    logger.info("cv_analysis_retry_requested", user_id=user_id, cv_id=str(cv_id))
    try:
        cv = session.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        logger.error("cv_analysis_retry_db_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")

    # Fire-and-forget — same trade-off as cv_upload_analysis_trigger_failed:
    # a Service Bus hiccup must not turn a 202 into a 500 for a background retry.
    try:
        send_message(CV_ANALYSIS_QUEUE, {"cv_id": str(cv_id), "retry_quality_only": True})
        logger.info("cv_analysis_retry_dispatched", user_id=user_id, cv_id=str(cv_id))
    except ServiceBusError:
        logger.error("cv_analysis_retry_dispatch_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)


@router.post("/{cv_id}/rome/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_rome_analysis(
    cv_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    """Manually re-trigger ROME code extraction for a CV owned by the authenticated user.

    Free and unlimited, same cost regime as retry_cv_analysis (quality) and the automatic
    extraction run at upload time. Only ROME extraction re-runs — CV quality analysis is
    untouched. _merge_rome_codes reconciles rather than only adds, so codes no longer produced
    by this fresh extraction are removed from the profile, not just supplemented — see
    docs/prompts/prompt-cv-analysis-rome-reanalysis-button.md.

    Args:
        cv_id: UUID of the CV.
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Raises:
        HTTPException 404: If the CV does not exist or is not owned by the user.
    """
    logger.info("cv_rome_retry_requested", user_id=user_id, cv_id=str(cv_id))
    try:
        cv = session.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        logger.error("cv_rome_retry_db_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")

    # Fire-and-forget — same trade-off as cv_analysis_retry_dispatch_failed above.
    try:
        send_message(CV_ANALYSIS_QUEUE, {"cv_id": str(cv_id), "retry_rome_only": True})
        logger.info("cv_rome_retry_dispatched", user_id=user_id, cv_id=str(cv_id))
    except ServiceBusError:
        logger.error("cv_rome_retry_dispatch_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)


@router.get("/{cv_id}/thumbnail", response_class=Response)
def get_cv_thumbnail(
    cv_id: uuid.UUID,
    size: Literal["sm", "lg"] = "sm",
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    """Return the JPEG thumbnail for a CV owned by the authenticated user.

    Args:
        cv_id: UUID of the CV.
        size: Thumbnail size — ``sm`` (default) for CVCards, ``lg`` for the detail view.
            Falls back to ``sm`` if ``lg`` has not been generated yet (pre-backfill CVs).
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Returns:
        JPEG image bytes with media type image/jpeg.

    Raises:
        HTTPException 404: If the CV does not exist, is not owned by the user,
            or has no thumbnail.
        HTTPException 503: If Azure Blob Storage is unavailable.
    """
    logger.info("cv_thumbnail_fetch_started", user_id=user_id, cv_id=str(cv_id), size=size)
    try:
        cv = session.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        logger.error("cv_thumbnail_db_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    if cv is None or cv.thumbnail_url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")

    url = cv.thumbnail_url_lg if (size == "lg" and cv.thumbnail_url_lg) else cv.thumbnail_url
    try:
        data = _download_blob(url, CV_BLOB_CONTAINER)
    except AzureError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage unavailable",
        ) from e

    logger.info("cv_thumbnail_fetch_done", user_id=user_id, cv_id=str(cv_id), size=size)
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


@router.patch("/{cv_id}/matches/{offer_id}/seen", status_code=status.HTTP_204_NO_CONTENT)
def mark_match_seen(
    cv_id: uuid.UUID,
    offer_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    """Mark a single match as seen.

    Args:
        cv_id: UUID of the CV that owns this match.
        offer_id: UUID of the offer (identifies the match uniquely within a CV).
        user_id: Authenticated user ID from the JWT sub claim.
        session: Active database session.

    Raises:
        HTTPException 404: If the CV does not exist, is not owned by the user, or
            no match exists for this CV/offer pair.
    """
    logger.info("mark_match_seen_started", user_id=user_id, cv_id=str(cv_id), offer_id=str(offer_id))
    try:
        match = session.execute(
            select(Match)
            .join(CV, Match.cv_id == CV.id)
            .where(Match.cv_id == cv_id, Match.offer_id == offer_id, CV.user_id == user_id)
        ).scalar_one_or_none()

        if match is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

        if match.seen_at is None:
            match.seen_at = datetime.now(timezone.utc)
            session.commit()
    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.error("mark_match_seen_db_failed", user_id=user_id, cv_id=str(cv_id), offer_id=str(offer_id), exc_info=True)
        raise

    logger.info("mark_match_seen_done", user_id=user_id, cv_id=str(cv_id), offer_id=str(offer_id))


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


def _delete_cv(session: Session, cv: CV, user_id: str) -> None:
    """Delete a CV's blobs, matches, and row, and prune it from rome_codes.

    Caller owns the commit — lets delete_account commit once for the whole
    account instead of once per CV. Matches are removed first to satisfy the
    FK constraint on matches.cv_id (no CASCADE DELETE is defined on it).

    Args:
        session: Active database session (caller owns commit).
        cv: The CV row to delete.
        user_id: Owner of the CV, used to update rome_codes.

    Raises:
        HTTPException 503: If Azure Blob Storage is unavailable.
        SQLAlchemyError: On any database error.
    """
    # Blobs are deleted before the DB commit. If commit() fails after this point
    # the CV row survives but its storage objects are permanently gone — a known
    # inconsistency accepted as a trade-off (no compensating-transaction / saga).
    # The inverse order (commit first, then delete blobs) is equally lossy: a blob
    # leak is harder to detect than a row whose blob is missing.
    try:
        _delete_blob(cv.blob_url, CV_BLOB_CONTAINER)
        if cv.thumbnail_url:
            _delete_blob(cv.thumbnail_url, CV_BLOB_CONTAINER)
        if cv.thumbnail_url_lg:
            _delete_blob(cv.thumbnail_url_lg, CV_BLOB_CONTAINER)
    except AzureError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage unavailable — CV deletion failed",
        ) from e

    # Delete analyses first, then matches — the FK constraints on
    # match_analyses.match_id, matches.cv_id, and cv_analyses.cv_id have no CASCADE.
    session.execute(
        delete(MatchAnalysis).where(
            MatchAnalysis.match_id.in_(select(Match.id).where(Match.cv_id == cv.id))
        )
    )
    session.execute(delete(Match).where(Match.cv_id == cv.id))
    session.execute(delete(CvAnalysis).where(CvAnalysis.cv_id == cv.id))
    session.delete(cv)
    _remove_cv_from_rome_codes(session, cv.id, user_id)


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

    try:
        _delete_cv(session, cv, user_id)
        session.commit()
    except SQLAlchemyError:
        logger.error("cv_delete_db_failed", user_id=user_id, cv_id=str(cv_id), exc_info=True)
        raise

    logger.info("cv_delete_done", user_id=user_id, cv_id=str(cv_id))
