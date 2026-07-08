"""JWT validation for Entra External ID using python-jose."""

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
import structlog
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

load_dotenv()  # no-op in production — env vars are injected by the Container App

logger = structlog.get_logger()

ENTRA_EXTERNAL_TENANT_ID = os.environ.get("ENTRA_EXTERNAL_TENANT_ID")
if not ENTRA_EXTERNAL_TENANT_ID:
    raise ValueError("ENTRA_EXTERNAL_TENANT_ID environment variable is not set")

ENTRA_EXTERNAL_CLIENT_ID = os.environ.get("ENTRA_EXTERNAL_CLIENT_ID")
if not ENTRA_EXTERNAL_CLIENT_ID:
    raise ValueError("ENTRA_EXTERNAL_CLIENT_ID environment variable is not set")

# Comma-separated Entra user IDs (JWT sub claims) granted in-app admin features
# (e.g. the credits refill button). Deliberately optional with an empty default —
# an unset variable means "no admins", never a broken deployment.
ADMIN_USER_IDS = frozenset(
    uid.strip()
    for uid in os.environ.get("ADMIN_USER_IDS", "").split(",")
    if uid.strip()
)

JWKS_URL = f"https://jobfinderapp.ciamlogin.com/{ENTRA_EXTERNAL_TENANT_ID}/discovery/v2.0/keys"
# Entra External ID issues tokens with the tenant GUID as the subdomain regardless
# of the custom domain used during authentication. The iss claim takes the form
# https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0 — not the custom domain.
ISSUER = f"https://{ENTRA_EXTERNAL_TENANT_ID}.ciamlogin.com/{ENTRA_EXTERNAL_TENANT_ID}/v2.0"
JWKS_TTL_SECONDS = 86400  # 24h — Entra External ID rotates keys infrequently

_jwks_cache: dict[str, Any] = {}
_jwks_cached_at: float = 0.0

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UserIdentity:
    """Identity claims extracted from a validated JWT.

    email and display_name are None when the Entra External ID user flow does
    not emit the corresponding claims in the access token — callers must treat
    them as best-effort metadata, never as required fields.
    """

    user_id: str
    email: str | None
    display_name: str | None


def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Entra External ID, update the module-level cache, and reset the TTL.

    Returns:
        The refreshed JWKS document as a dict.

    Raises:
        HTTPException: 401 if the JWKS endpoint cannot be reached.
    """
    global _jwks_cached_at
    try:
        response = requests.get(JWKS_URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("jwks_fetch_failed", url=JWKS_URL, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to fetch token signing keys",
        ) from e
    _jwks_cache.clear()
    _jwks_cache.update(response.json())
    _jwks_cached_at = time.time()
    return _jwks_cache


def _get_jwks() -> dict[str, Any]:
    """Return JWKS from the in-memory cache, refreshing if the TTL has elapsed.

    Returns:
        The JWKS document as a dict.

    Raises:
        HTTPException: 401 if the JWKS endpoint cannot be reached on a cache miss.
    """
    if _jwks_cache and (time.time() - _jwks_cached_at) < JWKS_TTL_SECONDS:
        return _jwks_cache
    return _fetch_jwks()


def _decode_token(token: str, jwks: dict[str, Any]) -> dict[str, Any]:
    """Decode and validate a JWT against the provided JWKS.

    Args:
        token: Raw JWT string.
        jwks: JWKS document containing the public signing keys.

    Returns:
        Validated JWT payload as a dict.
    """
    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=ENTRA_EXTERNAL_CLIENT_ID,
        issuer=ISSUER,
    )


def get_current_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserIdentity:
    """FastAPI dependency — validate the Bearer JWT and return identity claims.

    On a generic JWTError (signature verification failure), the cached JWKS is
    refreshed once and the decode is retried. This handles key rotation that
    occurs within the 24-hour TTL window without requiring a container restart.

    Args:
        credentials: HTTP Bearer credentials extracted from the Authorization header.

    Returns:
        UserIdentity with the ``sub`` claim as user_id, plus the email and
        name claims when the token carries them (None otherwise).

    Raises:
        HTTPException: 401 if the token is absent, malformed, expired, or has invalid claims.
    """
    logger.info("auth_validate_token_started")

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = _decode_token(token, _get_jwks())
    except ExpiredSignatureError as e:
        logger.error("auth_token_expired", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except JWTClaimsError as e:
        logger.error("auth_token_invalid_claims", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except JWTError:
        # Signature verification failed — the cached JWKS may be stale due to a key
        # rotation that occurred within the TTL window. Refresh once and retry.
        logger.info("auth_jwks_stale_suspected_retrying")
        try:
            payload = _decode_token(token, _fetch_jwks())
        except (ExpiredSignatureError, JWTClaimsError, JWTError) as e:
            logger.error("auth_token_invalid", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    user_id: str = payload.get("sub", "")
    if not user_id:
        logger.error("auth_token_missing_sub")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing sub claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email")
    if email is None:
        # Some Entra External ID / B2C user flows emit a list-valued "emails"
        # claim instead of the singular "email".
        emails = payload.get("emails")
        if isinstance(emails, list) and emails:
            email = emails[0]

    return UserIdentity(
        user_id=user_id,
        email=email,
        display_name=payload.get("name"),
    )


def get_current_user(
    identity: UserIdentity = Depends(get_current_identity),
) -> str:
    """FastAPI dependency — validate the Bearer JWT and return the user ID.

    Thin wrapper over get_current_identity for the many endpoints that only
    need the ``sub`` claim.

    Args:
        identity: Identity claims extracted from the validated JWT.

    Returns:
        The ``sub`` claim from the validated JWT as a string (user ID).
    """
    return identity.user_id


def is_admin(user_id: str) -> bool:
    """Return whether this user ID is granted in-app admin features.

    Args:
        user_id: Authenticated user ID (JWT sub claim).

    Returns:
        True if the user ID appears in the ADMIN_USER_IDS environment variable.
    """
    return user_id in ADMIN_USER_IDS


def get_current_admin_user(user_id: str = Depends(get_current_user)) -> str:
    """FastAPI dependency — like get_current_user, but restricted to admins.

    Args:
        user_id: Authenticated user ID from the JWT sub claim.

    Returns:
        The authenticated admin's user ID.

    Raises:
        HTTPException: 403 if the authenticated user is not an admin.
    """
    if not is_admin(user_id):
        logger.info("auth_admin_denied", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user_id
