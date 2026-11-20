"""One-click unsubscribe endpoint for the notifications digest (RFC 8058).

Deliberately unauthenticated — no Depends(get_current_identity)/get_current_user here,
unlike every other route in this webapp. The caller is either a mail client/server
performing an automated POST (RFC 8058's List-Unsubscribe-Post), which never carries a
session or bearer token, or a human clicking the same footer link in a browser without
being logged in. Identity comes entirely from the signed token (see
shared/unsubscribe_token.py), not from a JWT.

GET never mutates, only POST does: GET is the method a human's browser uses when clicking
the visible footer link, and visible links in an email are routinely followed automatically
by mail-client link prefetchers and antivirus/anti-spam scanners — a GET that unsubscribed
immediately would silently opt out users who never clicked anything. RFC 8058 itself POSTs
(List-Unsubscribe-Post: List-Unsubscribe=One-Click), so a compliant mail client's automated
one-click flow is unaffected; a human instead sees a confirmation page and must submit a
form (a second explicit POST) to actually unsubscribe.
"""

import html

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from dependencies import get_db
from shared.models import UserProfile
from shared.unsubscribe_token import verify_unsubscribe_token

_INVALID_TOKEN_HTML = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Lien invalide — Job Finder</title></head>
<body style="font-family: Arial, Helvetica, sans-serif; background:#0a0a0f; color:#f2f2f4; text-align:center; padding-top:80px;">
<h1>Lien invalide</h1>
<p>Ce lien de désabonnement n'est plus valide.</p>
</body>
</html>"""

_UNSUBSCRIBED_HTML = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Désabonnement confirmé — Job Finder</title></head>
<body style="font-family: Arial, Helvetica, sans-serif; background:#0a0a0f; color:#f2f2f4; text-align:center; padding-top:80px;">
<h1>Vous êtes désabonné</h1>
<p>Vous ne recevrez plus le récap de nouvelles offres par email.</p>
<p>Vous pouvez réactiver les rappels à tout moment depuis votre profil Job Finder.</p>
</body>
</html>"""

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = structlog.get_logger()


def _render_confirm_html(token: str) -> str:
    """Render the unsubscribe confirmation page, with the token embedded in the form action.

    Args:
        token: The (already-verified) token from the request's query parameter. Escaped
            before embedding — verify_unsubscribe_token succeeding does NOT guarantee
            token's raw characters are HTML-safe: Python's base64 decoder silently
            discards out-of-alphabet bytes instead of rejecting them, so a token can be
            crafted with `"`/`<`/`>` spliced into the encoded_user_id segment (at
            positions that don't shift the decoded payload) and still verify. Same
            escaping discipline as CV.name/Offer.title/display_name elsewhere in this
            codebase — never trust a value's origin to make it markup-safe.

    Returns:
        Full HTML confirmation page.
    """
    escaped_token = html.escape(token)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Confirmer le désabonnement — Job Finder</title></head>
<body style="font-family: Arial, Helvetica, sans-serif; background:#0a0a0f; color:#f2f2f4; text-align:center; padding-top:80px;">
<h1>Se désabonner des rappels ?</h1>
<p>Vous ne recevrez plus le récap de nouvelles offres par email.</p>
<form method="post" action="/notifications/unsubscribe?token={escaped_token}">
<button type="submit" style="margin-top:20px; padding:12px 24px; border-radius:8px; background-color:#2563eb; color:#ffffff; border:none; font-size:15px; cursor:pointer;">Confirmer le désabonnement</button>
</form>
</body>
</html>"""


def _clear_notification_days(session: Session, user_id: str) -> None:
    """Set UserProfile.notification_days = [] for user_id — a plain UPDATE, not an upsert.

    Idempotent by construction: re-running this for an already-empty or non-existent
    profile matches 0 or 1 rows either way, never raises, and the caller always reports
    success regardless — the same response for "already unsubscribed" and "no such
    profile" avoids leaking whether an account exists to an unauthenticated caller.

    Args:
        session: Active database session.
        user_id: Verified from the unsubscribe token — never taken from client input
            directly (see verify_unsubscribe_token).

    Raises:
        SQLAlchemyError: If the update fails.
    """
    logger.info("notifications_unsubscribe_started", user_id=user_id)
    try:
        session.execute(
            update(UserProfile).where(UserProfile.user_id == user_id).values(notification_days=[])
        )
        session.commit()
    except SQLAlchemyError:
        logger.error("notifications_unsubscribe_failed", user_id=user_id, exc_info=True)
        raise
    logger.info("notifications_unsubscribe_completed", user_id=user_id)


@router.get("/unsubscribe", response_class=HTMLResponse)
def confirm_unsubscribe(token: str) -> HTMLResponse:
    """Show a confirmation page for a human clicking the footer link — never mutates.

    Args:
        token: Signed token from the `token` query parameter (see sign_unsubscribe_token).

    Returns:
        An HTML page with a form that POSTs the same token to actually unsubscribe, or
        the invalid-link page (400) if the token doesn't verify.
    """
    if verify_unsubscribe_token(token) is None:
        logger.info("notifications_unsubscribe_invalid_token")
        return HTMLResponse(_INVALID_TOKEN_HTML, status_code=400)
    return HTMLResponse(_render_confirm_html(token))


@router.post("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str, session: Session = Depends(get_db)) -> HTMLResponse:
    """Opt a user out of every reminder day, given a valid signed unsubscribe token.

    Reached either by a mail client/server's automated RFC 8058 one-click POST, or by a
    human submitting confirm_unsubscribe's confirmation form.

    Args:
        token: Signed token from the `token` query parameter (see sign_unsubscribe_token).
        session: Active database session.

    Returns:
        An HTML confirmation page. 200 whether or not a matching profile existed (see
        _clear_notification_days); the token itself is what's validated as
        valid/invalid, not the outcome of the update.

    Raises:
        SQLAlchemyError: Propagated from _clear_notification_days if the update fails —
            surfaces as a 500 to the caller (mail client or browser).
    """
    user_id = verify_unsubscribe_token(token)
    if user_id is None:
        logger.info("notifications_unsubscribe_invalid_token")
        return HTMLResponse(_INVALID_TOKEN_HTML, status_code=400)

    _clear_notification_days(session, user_id)
    return HTMLResponse(_UNSUBSCRIBED_HTML)
