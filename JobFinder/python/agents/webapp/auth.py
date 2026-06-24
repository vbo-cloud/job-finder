"""JWT validation for Entra External ID using python-jose."""

import os
import time
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

JWKS_URL = f"https://jobfinderapp.ciamlogin.com/{ENTRA_EXTERNAL_TENANT_ID}/discovery/v2.0/keys"
# Entra External ID issues tokens with the tenant GUID as the subdomain regardless
# of the custom domain used during authentication. The iss claim takes the form
# https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0 — not the custom domain.
ISSUER = f"https://{ENTRA_EXTERNAL_TENANT_ID}.ciamlogin.com/{ENTRA_EXTERNAL_TENANT_ID}/v2.0"
JWKS_TTL_SECONDS = 86400  # 24h — Entra External ID rotates keys infrequently

_jwks_cache: dict[str, Any] = {}
_jwks_cached_at: float = 0.0

_bearer_scheme = HTTPBearer(auto_error=False)


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


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency — validate the Bearer JWT and return the user ID.

    On a generic JWTError (signature verification failure), the cached JWKS is
    refreshed once and the decode is retried. This handles key rotation that
    occurs within the 24-hour TTL window without requiring a container restart.

    Args:
        credentials: HTTP Bearer credentials extracted from the Authorization header.

    Returns:
        The ``sub`` claim from the validated JWT as a string (user ID).

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

    return user_id
