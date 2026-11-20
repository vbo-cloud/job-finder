"""HMAC-signed, single-purpose token for the notifications digest's one-click unsubscribe link.

Shared between agents/notifications (signs the token when sending the digest) and
agents/webapp (verifies it in POST/GET /notifications/unsubscribe) — kept here rather than
in either agent so neither imports the other's code (see agents/notifications/main.py's
module docstring: every agent only ever imports shared.*).

Deliberately not a JWT and not reusing agents/webapp/auth.py's Entra validation: this token
has exactly one purpose (identify a user_id for an unsubscribe action) and no session/identity
concept — a general-purpose JWT would tie it to Entra's key rotation/audience checks, which
have nothing to do with this use case.

No expiration, by design: an unsubscribe link that 401s because the user opened a days-old
email would be a worse outcome (an angry click on "Report spam" instead, which hurts sender
reputation) than a link that stays valid indefinitely — see
docs/prompts/prompt-email-one-click-unsubscribe.md. The worst case of a leaked or guessed
token is an unwanted opt-out (notification_days reset to []), not a data leak.

Operational consequence of the above: rotating NOTIFICATIONS_UNSUBSCRIBE_SECRET instantly
invalidates every unsubscribe link in every digest already sent — those emails are
immutable once delivered, so there is no way to reach affected recipients with a working
link afterward. Before ever rotating this secret, ship a transition period that accepts
both the old and new secret in verify_unsubscribe_token (or accept the breakage as a known,
one-time cost) rather than rotating it the same way as a typical credential.

Expected environment variables:
    NOTIFICATIONS_UNSUBSCRIBE_SECRET: HMAC signing key, shared by both consuming agents
        (see JobFinder/Terraform/envs/dev/notifications_unsubscribe_secret.tf).
"""

import base64
import hashlib
import hmac
import os

# Scopes the HMAC to this one purpose — if this secret were ever reused elsewhere, a token
# signed for that other purpose could not be replayed here.
_PURPOSE = "unsubscribe"

_UNSUBSCRIBE_SECRET = os.environ.get("NOTIFICATIONS_UNSUBSCRIBE_SECRET")
if not _UNSUBSCRIBE_SECRET:
    raise ValueError("NOTIFICATIONS_UNSUBSCRIBE_SECRET environment variable is not set")


def _signature(user_id: str) -> str:
    """Return the urlsafe-base64, unpadded HMAC-SHA256 signature for user_id."""
    digest = hmac.new(
        _UNSUBSCRIBE_SECRET.encode(), f"{_PURPOSE}:{user_id}".encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def sign_unsubscribe_token(user_id: str) -> str:
    """Build a signed, URL-safe unsubscribe token for a user.

    Args:
        user_id: UserProfile.user_id to encode.

    Returns:
        A token of the form "<urlsafe-base64 user_id>.<urlsafe-base64 HMAC signature>",
        safe to embed as a URL query parameter without further encoding.
    """
    encoded_user_id = base64.urlsafe_b64encode(user_id.encode()).decode().rstrip("=")
    return f"{encoded_user_id}.{_signature(user_id)}"


def verify_unsubscribe_token(token: str) -> str | None:
    """Verify a token built by sign_unsubscribe_token and recover its user_id.

    Args:
        token: Token as received in the unsubscribe request's `token` query parameter.

    Returns:
        The decoded user_id if the token is well-formed and its signature checks out,
        None otherwise (malformed token, tampered signature). Never raises on bad
        input — this backs an unauthenticated endpoint, so untrusted/garbage input is
        the expected case, not an exceptional one.
    """
    try:
        encoded_user_id, signature = token.split(".", 1)
        padding = "=" * (-len(encoded_user_id) % 4)
        user_id = base64.urlsafe_b64decode(encoded_user_id + padding).decode()
        signature_is_valid = hmac.compare_digest(signature, _signature(user_id))
    except ValueError:  # bad split, bad base64 padding/alphabet, or invalid UTF-8
        return None
    except TypeError:  # hmac.compare_digest rejects a non-ASCII `signature` this way
        return None

    if not signature_is_valid:
        return None
    return user_id
